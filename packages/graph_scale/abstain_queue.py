"""Abstain-to-ingest feedback loop — every honest '근거 부족' becomes a growth target.

Measured: sealed-holdout coverage is 32%; the engine abstains honestly but nothing ever
LEARNS from the abstention. The terms it abstained on (성남시, Roblox, 장관급…) are literally
the highest-value ingest targets — a user just asked about them. This module closes the loop:

  answer path abstains -> record_abstain(query) extracts the knowledge terms and appends
  them to a deduped queue -> scripts/feed_abstain_queue.py drains the queue, fetches a
  grounded definition for each term (Wikipedia REST summary, proper UA), routes it through
  the CONSERVATIVE definition extractor (only clean copular definitions become facts), and
  ingests into the curated TripleStore — where the answer bridge can serve it next time.

Honesty: the consumer stores only verbatim definitional sentences that pass the extractor;
a term whose page yields no clean definition stays queued as 'no_definition' (visible gap,
not a fabricated fact)."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2] / "data" / "graph_scale"
QUEUE_PATH = _ROOT / "abstain_queue.jsonl"

_STOP = {"뭐", "무엇", "누구", "어디", "언제", "설명", "정의", "뜻", "말", "이유", "방법",
         "지금", "오늘", "내일", "현재", "그거", "이거", "질문", "answer", "what", "who"}


def _terms(query: str) -> list[str]:
    """Knowledge terms worth ingesting: content nouns of the query, particles stripped."""
    out: list[str] = []
    try:
        from packages.base_brain.neighborhood import _kiwi

        kw = _kiwi()
        if kw is not None:
            for tok in kw.tokenize(query):
                if tok.tag in ("NNP", "NNG", "SL") and len(tok.form) >= 2 and tok.form not in _STOP:
                    if tok.form not in out:
                        out.append(tok.form)
            return out[:4]
    except Exception:
        pass
    from packages.base_brain.neighborhood import _strip_ko_tail

    for t in re.findall(r"[가-힣A-Za-z0-9]{2,}", query):
        st = _strip_ko_tail(t)
        if len(st) >= 2 and st not in _STOP and st not in out:
            out.append(st)
    return out[:4]


def _load() -> dict[str, dict[str, Any]]:
    if not QUEUE_PATH.exists():
        return {}
    entries: dict[str, dict[str, Any]] = {}
    for line in QUEUE_PATH.open(encoding="utf-8"):
        try:
            rec = json.loads(line)
            entries[rec["term"]] = rec          # last state wins
        except Exception:
            continue
    return entries


def _append(rec: dict[str, Any]) -> None:
    QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with QUEUE_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def record_abstain(query: str) -> list[str]:
    """Log the query's knowledge terms as pending ingest targets (deduped). Returns the
    newly queued terms. Cheap enough for the live answer path; never raises."""
    try:
        existing = _load()
        added: list[str] = []
        for term in _terms(query):
            if term not in existing:
                _append({"term": term, "status": "pending", "query": query[:120],
                         "ts": time.strftime("%Y-%m-%dT%H:%M:%S")})
                added.append(term)
        return added
    except Exception:
        return []


def pending(limit: int = 50) -> list[str]:
    return [t for t, rec in _load().items() if rec.get("status") == "pending"][:limit]


def pending_records(limit: int = 50) -> list[dict[str, Any]]:
    """Pending entries WITH their originating query — the feeder needs the query to
    label the routing decision once the term is successfully grounded."""
    return [rec for rec in _load().values() if rec.get("status") == "pending"][:limit]


def mark(term: str, status: str, note: str = "") -> None:
    _append({"term": term, "status": status, "note": note,
             "ts": time.strftime("%Y-%m-%dT%H:%M:%S")})
