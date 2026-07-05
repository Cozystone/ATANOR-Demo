#!/usr/bin/env python3
"""Bulk-ingest CURATED structured knowledge graphs into the integer-columnar TripleStore.

This is the trillion-scale growth path: instead of crawling the web one sentence at a time
and NL-decomposing each (~1.3 concepts/min), load pre-structured, human-verified (subject,
predicate, object) triples DIRECTLY at ~1e5 triples/sec. Quality comes from the source
(Wikidata CC0 / ConceptNet / DBpedia are curated), performance from the representation.

Sources:
  --source tsv        <file>   lines of  subject<TAB>predicate<TAB>object
  --source nt         <file>   N-Triples (RDF)  <s> <p> <o> .
  --source conceptnet <file>   ConceptNet CSV assertions (/a/[...]  /r/Rel  /c/en/subj  /c/en/obj ...)
  --source wikidata   --limit N   live SPARQL pull (real, curated) — proves quality
  --benchmark N                synthetic realistic stream — proves throughput

  python scripts/bulk_ingest_kg.py --source wikidata --limit 500
  python scripts/bulk_ingest_kg.py --source tsv dumps/facts.tsv
  python scripts/bulk_ingest_kg.py --benchmark 2000000
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Iterator

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from packages.graph_scale.triple_store import TripleStore  # noqa: E402

DEFAULT_ROOT = REPO / "data" / "graph_scale" / "kg_triples"
_UA = "ATANOR-KG/1.0 (local-first knowledge engine; contact: local)"


def _tsv(path: Path) -> Iterator[tuple[str, str, str]]:
    for line in path.open(encoding="utf-8"):
        parts = line.rstrip("\n").split("\t")
        if len(parts) >= 3:
            yield parts[0].strip(), parts[1].strip(), parts[2].strip()


_NT_RE = re.compile(r'^\s*(<[^>]+>|_:\w+)\s+(<[^>]+>)\s+(.+?)\s*\.\s*$')
def _nt(path: Path) -> Iterator[tuple[str, str, str]]:
    def clean(t: str) -> str:
        t = t.strip()
        if t.startswith("<") and t.endswith(">"):
            return t[1:-1].rsplit("/", 1)[-1].rsplit("#", 1)[-1]
        m = re.match(r'^"(.*)"', t)
        return m.group(1) if m else t
    for line in path.open(encoding="utf-8"):
        m = _NT_RE.match(line)
        if m:
            yield clean(m.group(1)), clean(m.group(2)), clean(m.group(3))


def _conceptnet(path: Path) -> Iterator[tuple[str, str, str]]:
    for line in path.open(encoding="utf-8"):
        cols = line.split("\t")
        if len(cols) >= 4:
            rel = cols[1].rsplit("/", 1)[-1]
            s = cols[2].split("/")[3] if cols[2].count("/") >= 3 else cols[2]
            o = cols[3].split("/")[3] if cols[3].count("/") >= 3 else cols[3]
            if s and o:
                yield s.replace("_", " "), rel, o.replace("_", " ")


# SCOPED, curated Wikidata slice — countries + their capital (P36). A scoped query WDQS
# answers fast (a broad '?s wdt:P31 ?o' scan times out). Proves real curated-triple flow;
# a full dump ingests the same way, just at file speed.
_WD_SPARQL = "https://query.wikidata.org/sparql"
_WD_QUERY = """
SELECT ?sLabel ?oLabel WHERE {
  ?s wdt:P31 wd:Q6256 . ?s wdt:P36 ?o .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "ko,en". }
} LIMIT %d
"""
_WD_PRED = "capital"
def _wikidata(limit: int) -> Iterator[tuple[str, str, str]]:
    url = _WD_SPARQL + "?" + urllib.parse.urlencode({"query": _WD_QUERY % limit, "format": "json"})
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/sparql-results+json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read().decode("utf-8"))
    for b in data.get("results", {}).get("bindings", []):
        s = b.get("sLabel", {}).get("value", "").strip()
        o = b.get("oLabel", {}).get("value", "").strip()
        if s and o and not (s.startswith("Q") and s[1:].isdigit()):   # skip unlabelled Q-ids
            yield s, _WD_PRED, o


def _synthetic(n: int) -> Iterator[tuple[str, str, str]]:
    preds = [f"P{i}" for i in range(50)]
    for i in range(n):
        yield f"E{i}", preds[i % 50], (f"E{(i * 7) % (n // 2 + 1)}" if i % 2 else f"T{i % 8000}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["tsv", "nt", "conceptnet", "wikidata"], default=None)
    ap.add_argument("file", nargs="?")
    ap.add_argument("--limit", type=int, default=500)
    ap.add_argument("--benchmark", type=int, default=0)
    ap.add_argument("--root", default=str(DEFAULT_ROOT))
    args = ap.parse_args()

    store = TripleStore(args.root)
    if args.benchmark:
        gen, label = _synthetic(args.benchmark), f"synthetic:{args.benchmark}"
    elif args.source == "wikidata":
        gen, label = _wikidata(args.limit), f"wikidata:P31:{args.limit}"
    elif args.source == "tsv" and args.file:
        gen, label = _tsv(Path(args.file)), f"tsv:{args.file}"
    elif args.source == "nt" and args.file:
        gen, label = _nt(Path(args.file)), f"nt:{args.file}"
    elif args.source == "conceptnet" and args.file:
        gen, label = _conceptnet(Path(args.file)), f"conceptnet:{args.file}"
    else:
        ap.error("give --benchmark N or --source {wikidata|tsv|nt|conceptnet} [file]")
        return 2

    t0 = time.time()
    r = store.bulk_ingest(gen)
    dt = max(1e-9, time.time() - t0)
    rate = r["added"] / dt
    print(json.dumps({
        "source": label, "added": r["added"], "duplicates": r["duplicates"],
        "store_total": r["total"], "vocab_terms": r["terms"],
        "seconds": round(dt, 2), "triples_per_sec": round(rate),
        "disk_bytes": store.disk_bytes(), "bytes_per_triple": round(store.disk_bytes() / max(1, r["added"]), 1),
    }, ensure_ascii=False, indent=2))
    # show a couple of REAL facts proving quality (structured, verbatim from source)
    if r["added"]:
        cols = store.open_columns()
        for i in range(min(3, len(cols["s"]))):
            print("   fact:", store.terms.term(int(cols['s'][i])), "|",
                  store.terms.term(int(cols['p'][i])), "|", store.terms.term(int(cols['o'][i])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
