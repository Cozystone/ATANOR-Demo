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
import bz2
import gzip
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Iterator, TextIO

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from packages.graph_scale.triple_store import TripleStore  # noqa: E402

DEFAULT_ROOT = REPO / "data" / "graph_scale" / "kg_triples"
_UA = "ATANOR-KG/1.0 (local-first knowledge engine; contact: local)"


def _open_text(path: Path) -> TextIO:
    """Open a dump transparently whether it's plain, .gz, or .bz2 — real KG dumps ship
    compressed, and this streams them line by line (bounded memory), never loading the file."""
    suffix = path.suffix.lower()
    if suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    if suffix == ".bz2":
        return bz2.open(path, "rt", encoding="utf-8")
    return path.open(encoding="utf-8")


def _tsv(path: Path) -> Iterator[tuple[str, str, str]]:
    with _open_text(path) as fh:
        for line in fh:
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
    with _open_text(path) as fh:
        for line in fh:
            m = _NT_RE.match(line)
            if m:
                yield clean(m.group(1)), clean(m.group(2)), clean(m.group(3))


def _conceptnet(path: Path) -> Iterator[tuple[str, str, str]]:
    """ConceptNet assertions CSV. Keeps only Korean/English concept edges so the store stays
    on-language; a concept URI is /c/<lang>/<term>[/...]."""
    with _open_text(path) as fh:
        for line in fh:
            cols = line.split("\t")
            if len(cols) < 4:
                continue
            rel = cols[1].rsplit("/", 1)[-1]
            sp, op = cols[2].split("/"), cols[3].split("/")
            if len(sp) < 4 or len(op) < 4:
                continue
            if sp[2] not in ("ko", "en") or op[2] not in ("ko", "en"):  # language filter
                continue
            s, o = sp[3], op[3]
            if s and o:
                yield s.replace("_", " "), rel, o.replace("_", " ")


def _progress(gen: Iterator[tuple[str, str, str]], every: int) -> Iterator[tuple[str, str, str]]:
    """Wrap a triple stream to print throughput every `every` rows — dumps run for minutes,
    so a heartbeat matters. Pure pass-through; adds no buffering."""
    t0 = time.time()
    n = 0
    for row in gen:
        n += 1
        if every and n % every == 0:
            dt = max(1e-9, time.time() - t0)
            sys.stderr.write(f"\r  ...{n:,} rows  {n / dt:,.0f}/s  {dt:.0f}s")
            sys.stderr.flush()
        yield row
    if every and n >= every:
        sys.stderr.write("\n")


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


# ---- open sentence corpora (Tatoeba / OpenSubtitles / OSCAR / AI Hub / Wiktionary) ------
# These are SENTENCES, not triples. corpus_adapters routes them: definitional sentences ->
# (subject, is_a/defined_as, object) facts; Tatoeba translation pairs -> cross-lingual alias
# triples. Conservative extraction => only clear definitions become facts (no fabrication).

def _sentences_defs(path: Path) -> Iterator[tuple[str, str, str]]:
    from packages.graph_scale.corpus_adapters import iter_definition_triples, iter_line_sentences

    yield from iter_definition_triples(iter_line_sentences(path))


def _oscar_defs(path: Path) -> Iterator[tuple[str, str, str]]:
    from packages.graph_scale.corpus_adapters import iter_definition_triples, iter_oscar_sentences

    yield from iter_definition_triples(iter_oscar_sentences(path))


def _wiktionary(path: Path) -> Iterator[tuple[str, str, str]]:
    from packages.graph_scale.corpus_adapters import iter_wiktionary_definitions

    yield from iter_wiktionary_definitions(path)


def _tatoeba_alias(sentences_path: Path, links_path: Path) -> Iterator[tuple[str, str, str]]:
    from packages.graph_scale.corpus_adapters import iter_tatoeba_alias_pairs

    yield from iter_tatoeba_alias_pairs(sentences_path, links_path)


def _synthetic(n: int) -> Iterator[tuple[str, str, str]]:
    preds = [f"P{i}" for i in range(50)]
    for i in range(n):
        yield f"E{i}", preds[i % 50], (f"E{(i * 7) % (n // 2 + 1)}" if i % 2 else f"T{i % 8000}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=None, choices=[
        "tsv", "nt", "conceptnet", "wikidata",
        "wiktionary", "sentences", "oscar", "tatoeba-alias"])
    ap.add_argument("file", nargs="?")
    ap.add_argument("--links", help="Tatoeba links.csv (for --source tatoeba-alias)")
    ap.add_argument("--limit", type=int, default=500)
    ap.add_argument("--benchmark", type=int, default=0)
    ap.add_argument("--root", default=str(DEFAULT_ROOT))
    ap.add_argument("--derive", action="store_true",
                    help="after ingest, run derived-edge inference (transitive/symmetric/"
                         "inverse) to multiply edges deductively from the stored structure")
    ap.add_argument("--no-dedup", action="store_true",
                    help="disable the in-RAM dedup set (bounded memory for billion-row dumps "
                         "that are already deduplicated at source, e.g. a Wikidata truthy dump)")
    ap.add_argument("--progress", type=int, default=1_000_000,
                    help="print a throughput heartbeat every N rows (0 = off)")
    args = ap.parse_args()

    store = TripleStore(args.root)
    if args.no_dedup:
        store._dedupe_enabled = False
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
    elif args.source == "wiktionary" and args.file:
        gen, label = _wiktionary(Path(args.file)), f"wiktionary:{args.file}"
    elif args.source == "sentences" and args.file:
        gen, label = _sentences_defs(Path(args.file)), f"sentences:{args.file}"
    elif args.source == "oscar" and args.file:
        gen, label = _oscar_defs(Path(args.file)), f"oscar:{args.file}"
    elif args.source == "tatoeba-alias" and args.file and args.links:
        gen, label = _tatoeba_alias(Path(args.file), Path(args.links)), f"tatoeba-alias:{args.file}"
    else:
        ap.error("give --benchmark N or --source {wikidata|tsv|nt|conceptnet|wiktionary|"
                 "sentences|oscar|tatoeba-alias} [file] (tatoeba-alias also needs --links)")
        return 2

    if args.progress and not args.benchmark:
        gen = _progress(gen, args.progress)
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

    if args.derive:
        from packages.graph_scale.inference import derive_into_store

        t1 = time.time()
        dr = derive_into_store(store)
        print(json.dumps({
            "derive": True, "stated": dr["stated"], "derived_added": dr["derived_added"],
            "store_total": dr["total"],
            "multiplier": round(dr["total"] / max(1, dr["stated"]), 2),
            "seconds": round(time.time() - t1, 2),
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
