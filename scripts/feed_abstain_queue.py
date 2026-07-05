#!/usr/bin/env python3
"""Drain the abstain queue: for each term the engine abstained on, fetch a grounded
definition (Wikipedia REST summary, policy-compliant UA), keep only sentences that pass the
CONSERVATIVE definition extractor, judge them against the curated store (contradiction
quarantine), and ingest the survivors — so the next user who asks gets an answer.

  python scripts/feed_abstain_queue.py            # drain up to --limit pending terms
  python scripts/feed_abstain_queue.py --dry-run  # show what would be ingested
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from packages.graph_scale import abstain_queue  # noqa: E402
from packages.graph_scale.corpus_adapters import extract_definition_triple  # noqa: E402
from packages.graph_scale.curated_judge import filter_candidates  # noqa: E402
from packages.graph_scale.triple_store import TripleStore  # noqa: E402

STORE_ROOT = REPO / "data" / "graph_scale" / "kg_triples"
_UA = ("ATANOR-KG/1.0 (https://github.com/Cozystone/ATANOR; blueyjkim@gmail.com) "
       "urllib/3 abstain-queue-feeder")


def _wiki_summary(term: str, lang: str = "ko") -> str:
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(term)}"
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode("utf-8"))
    if data.get("type") == "disambiguation":
        return ""
    return (data.get("extract") or "").strip()


def _definition_sentences(term: str, extract: str) -> list[str]:
    """First sentences of the summary that actually DEFINE the term (must name it)."""
    sents = [s.strip() for s in re.split(r"(?<=다\.)\s+|(?<=[.?!])\s+", extract) if s.strip()]
    return [s for s in sents[:3] if term in s]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    terms = abstain_queue.pending(args.limit)
    if not terms:
        print("abstain queue: nothing pending")
        return 0
    store = TripleStore(STORE_ROOT)
    total_ingested = 0
    for term in terms:
        try:
            extract = _wiki_summary(term)
        except Exception as exc:
            print(f"  {term}: fetch failed ({exc})")
            abstain_queue.mark(term, "fetch_failed", str(exc)[:80])
            continue
        candidates = []
        for sent in _definition_sentences(term, extract):
            t = extract_definition_triple(sent)
            if t:
                candidates.append(t)
        if not candidates:
            print(f"  {term}: no clean definition (honest gap, stays visible)")
            abstain_queue.mark(term, "no_definition")
            continue
        verdicts = filter_candidates(candidates, store)
        for q in verdicts["quarantined"]:
            print(f"  {term}: QUARANTINED {q['fact']} — curated evidence {q['evidence']}")
        if args.dry_run:
            print(f"  {term}: would ingest {verdicts['promotable']}")
            continue
        r = store.bulk_ingest(verdicts["promotable"])
        total_ingested += r["added"]
        abstain_queue.mark(term, "ingested", f"{r['added']} facts")
        for s, p, o in verdicts["promotable"]:
            print(f"  {term}: + {s} | {p} | {o}")
    print(f"done: {total_ingested} facts ingested, store total {len(store)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
