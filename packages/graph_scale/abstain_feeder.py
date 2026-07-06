"""Drain the abstain queue into the curated store — the automated half of the
abstain-to-ingest loop. Callable from the CLI script AND the continuous-learning daemon
tick, so coverage grows with usage without an operator. Conservative by construction:
only clean copular definitions become facts; contradictions are judge-quarantined."""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from . import abstain_queue
from .corpus_adapters import extract_definition_triple
from .curated_judge import filter_candidates
from .triple_store import TripleStore

STORE_ROOT = Path(__file__).resolve().parents[2] / "data" / "graph_scale" / "kg_triples"
_UA = ("ATANOR-KG/1.0 (https://github.com/Cozystone/ATANOR; blueyjkim@gmail.com) "
       "urllib/3 abstain-queue-feeder")


def _rest_summary(host: str, term: str) -> str:
    url = f"https://{host}/api/rest_v1/page/summary/{urllib.parse.quote(term)}"
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode("utf-8"))
    if data.get("type") == "disambiguation":
        return ""
    return (data.get("extract") or "").strip()


def _term_lang(term: str) -> str:
    """Route by script — an English term on ko.wikipedia is a guaranteed 404 (the
    holdout drain measured 7/20 fetch failures from exactly this)."""
    return "ko" if any("가" <= ch <= "힣" for ch in term) else "en"


def _wiki_summary(term: str, lang: str | None = None) -> str:
    """Wikipedia first; Wiktionary as the fallback for dictionary-class words
    (동적, 근본… live there, not in the encyclopedia). Same conservative extractor
    downstream either way — a source change never loosens the honesty gate."""
    lang = lang or _term_lang(term)
    try:
        extract = _rest_summary(f"{lang}.wikipedia.org", term)
    except Exception:
        extract = ""
    if extract:
        return extract
    try:
        return _rest_summary(f"{lang}.wiktionary.org", term)
    except Exception:
        return ""


def _definition_sentences(term: str, extract: str) -> list[str]:
    sents = [s.strip() for s in re.split(r"(?<=다\.)\s+|(?<=[.?!])\s+", extract) if s.strip()]
    tl = term.lower()
    return [s for s in sents[:3] if term in s or tl in s.lower()]


def drain(limit: int = 5, dry_run: bool = False, log: Any = print) -> dict[str, int]:
    """Process up to `limit` pending terms. Returns counters; never raises (each term's
    failure is recorded on the queue and skipped)."""
    counters = {"terms": 0, "ingested": 0, "quarantined": 0, "no_definition": 0, "failed": 0}
    records = abstain_queue.pending_records(limit)
    if not records:
        return counters
    store = TripleStore(STORE_ROOT)
    for rec in records:
        term = str(rec.get("term") or "")
        counters["terms"] += 1
        try:
            extract = _wiki_summary(term)
        except Exception as exc:
            abstain_queue.mark(term, "fetch_failed", str(exc)[:80])
            counters["failed"] += 1
            continue
        candidates = [t for s in _definition_sentences(term, extract)
                      if (t := extract_definition_triple(s))]
        if not candidates:
            abstain_queue.mark(term, "no_definition")
            counters["no_definition"] += 1
            log(f"  {term}: no clean definition (honest gap, stays visible)")
            continue
        verdicts = filter_candidates(candidates, store)
        counters["quarantined"] += len(verdicts["quarantined"])
        for q in verdicts["quarantined"]:
            log(f"  {term}: QUARANTINED {q['fact']} — curated evidence {q['evidence']}")
        if dry_run:
            log(f"  {term}: would ingest {verdicts['promotable']}")
            continue
        r = store.bulk_ingest(verdicts["promotable"])
        counters["ingested"] += r["added"]
        abstain_queue.mark(term, "ingested", f"{r['added']} facts")
        for s, p, o in verdicts["promotable"]:
            log(f"  {term}: + {s} | {p} | {o}")
        if r["added"]:
            # measured outcome for the routing policy: the query this term came from was
            # definitional after all (a judge-passed definition now exists in the store).
            try:
                from packages.base_brain.answer_experience import label_reingest_success

                label_reingest_success(term, str(rec.get("query") or ""))
            except Exception:
                pass
    return counters
