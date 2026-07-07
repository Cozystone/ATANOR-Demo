# -*- coding: utf-8 -*-
"""Temporal KG v0 — the owner's TRUE 4D: the ontology graph gains a TIME AXIS.

'5년 전 한국 대통령'과 '현재 한국 대통령' are different FACTS that must be
structurally distinguishable — not one overwritten value. The mechanism is the
4D-fluents pattern (temporal-part modeling: a time-varying property holds only
within a validity slice). Reference framing: TechRxiv 10.36227/
techrxiv.174494561.19053524 (owner-provided; 4D = 3D ontology + time axis).

v0 representation (auditable JSONL, same discipline as the episodic layer):
  {subject, predicate, object, valid_from, valid_to|null}
  assert_temporal('대한민국', '대통령', '윤석열', '2022-05-10', '2025-04-04')
  at_time('대한민국', '대통령', '2020-06-01')  -> 문재인 fact
  current('대한민국', '대통령')                -> the open-interval fact

Honesty: a query outside every recorded interval returns None (never the
nearest guess); every answer carries its validity interval so the user SEES
the time slice that grounded it.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
FACTS_PATH = REPO / "data" / "graph_scale" / "temporal_facts.jsonl"


def assert_temporal(subject: str, predicate: str, obj: str, valid_from: str,
                    valid_to: str | None = None, source: str = "curated") -> dict[str, Any]:
    row = {"subject": subject.strip(), "predicate": predicate.strip(),
           "object": obj.strip(), "valid_from": str(valid_from)[:10],
           "valid_to": (str(valid_to)[:10] if valid_to else None),
           "source": source, "recorded": time.strftime("%Y-%m-%d")}
    FACTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with FACTS_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def _rows() -> list[dict[str, Any]]:
    if not FACTS_PATH.exists():
        return []
    out = []
    for line in FACTS_PATH.open(encoding="utf-8"):
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def at_time(subject: str, predicate: str, when: str) -> dict[str, Any] | None:
    """The fact valid at `when` (YYYY[-MM[-DD]]); None outside every interval."""
    w = str(when)[:10]
    if len(w) == 4:
        w += "-07-01"  # a bare year asks about mid-year
    best = None
    for r in _rows():
        if r["subject"] != subject or r["predicate"] != predicate:
            continue
        if r["valid_from"] <= w and (r["valid_to"] is None or w <= r["valid_to"]):
            if best is None or r["valid_from"] > best["valid_from"]:
                best = r
    return best


def current(subject: str, predicate: str) -> dict[str, Any] | None:
    return at_time(subject, predicate, time.strftime("%Y-%m-%d"))


def timeline_of(subject: str, predicate: str) -> list[dict[str, Any]]:
    hits = [r for r in _rows()
            if r["subject"] == subject and r["predicate"] == predicate]
    hits.sort(key=lambda r: r["valid_from"])
    return hits
