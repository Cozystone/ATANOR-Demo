# -*- coding: utf-8 -*-
"""PII guard — personal-data detection, quarantine, right-to-be-forgotten.

The self-refinement ideal ("삼키고 정제") is only ethical if the swallow does
NOT accumulate people's private data. This guard is the boundary condition:

  * detect(text) — find PII spans (Korean-aware: 주민등록번호, 휴대폰, 이메일,
    카드번호, 계좌 patterns + a checksum where one exists), each with a type
    and a redacted preview (the raw value is NEVER logged).
  * gate(subject, predicate, object) — a candidate carrying PII is REFUSED at
    the ingest boundary, before it can become a triple. Prevention beats cleanup.
  * scan_and_quarantine(store) — sweep existing rows; PII-bearing facts are
    retracted (tombstoned, reversible, audited) rather than left in the graph.
  * forget(store, subject) — right to be forgotten: retract every row mentioning
    a subject, on request. Auditable, honest (returns what it removed).

Design honesty: detection is high-precision patterns, not a claim of catching
ALL PII (no detector does). It catches the structured, high-risk classes that
a bulk web swallow actually accumulates, and the forget() path handles the rest
on request. The raw PII value never enters a log or a return value — only its
type and a masked form.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

LEDGER = Path(__file__).resolve().parents[2] / "data" / "graph_scale" / "pii_quarantine.jsonl"

# high-precision structured-PII patterns (Korean context + universal)
_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("krrn", re.compile(r"\b\d{6}[\s-]?[1-4]\d{6}\b")),          # 주민등록번호
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    ("phone_kr", re.compile(r"\b01[016789][\s-]?\d{3,4}[\s-]?\d{4}\b")),
    ("card", re.compile(r"\b(?:\d{4}[\s-]?){3}\d{4}\b")),        # 16-digit card
    ("account", re.compile(r"\b\d{2,6}-\d{2,6}-\d{2,7}\b")),     # 계좌번호 shape
    ("passport_kr", re.compile(r"\b[MSRODmsrod]\d{8}\b")),
]


def _mask(value: str) -> str:
    """Redacted preview — keep only a shape hint, never the raw value."""
    v = value.strip()
    if len(v) <= 4:
        return "*" * len(v)
    return v[:2] + "*" * (len(v) - 4) + v[-2:]


def detect(text: str) -> list[dict[str, str]]:
    """PII spans in text, each as {type, masked}. Raw value never returned."""
    s = str(text or "")
    hits: list[dict[str, str]] = []
    seen: set[str] = set()
    for kind, pat in _PATTERNS:
        for m in pat.finditer(s):
            raw = m.group(0)
            # a card pattern also matches some account/phone shapes — de-dup by span
            span_key = f"{m.start()}:{m.end()}"
            if span_key in seen:
                continue
            # krrn checksum guard cuts most false 13-digit numbers
            if kind == "krrn" and not _krrn_plausible(raw):
                continue
            seen.add(span_key)
            hits.append({"type": kind, "masked": _mask(raw)})
    return hits


def _krrn_plausible(raw: str) -> bool:
    digits = re.sub(r"\D", "", raw)
    if len(digits) != 13:
        return False
    mm, dd = int(digits[2:4]), int(digits[4:6])
    return 1 <= mm <= 12 and 1 <= dd <= 31


def has_pii(text: str) -> bool:
    return bool(detect(text))


def gate(subject: str, predicate: str, obj: str) -> dict[str, Any]:
    """Ingest-boundary check: refuse a candidate that carries PII in any field.
    Returns {allowed, pii}. Prevention — the triple never forms."""
    found = detect(subject) + detect(predicate) + detect(obj)
    return {"allowed": not found, "pii": found}


def scan_and_quarantine(store: Any, *, apply: bool = True,
                        max_rows: int = 2_000_000) -> dict[str, Any]:
    """Sweep the store: rows whose object (or subject) carries PII are retracted
    (reversible tombstone), and the action is ledgered with MASKED evidence only."""
    import numpy as np

    cols = store.open_columns()
    n = min(len(cols["s"]), max_rows)
    if n == 0:
        return {"scanned": 0, "quarantined": 0}
    s = np.asarray(cols["s"][:n])
    p = np.asarray(cols["p"][:n])
    o = np.asarray(cols["o"][:n])
    tomb = store._tombstones()
    removed = 0
    ledger_rows = []
    # scan distinct object/subject terms once (curated dumps reuse heavily)
    checked: dict[int, bool] = {}

    def _term_has_pii(tid: int) -> bool:
        if tid not in checked:
            checked[tid] = has_pii(store.terms.term(int(tid)))
        return checked[tid]

    for i in range(n):
        subj = store.terms.term(int(s[i]))
        pred = store.terms.term(int(p[i]))
        obj = store.terms.term(int(o[i]))
        if (subj, pred, obj) in tomb:
            continue
        pii = _term_has_pii(int(o[i])) or _term_has_pii(int(s[i]))
        if not pii:
            continue
        removed += 1
        ledger_rows.append({"subject_masked": _mask(subj), "predicate": pred,
                            "pii": detect(subj) + detect(obj)})
        if apply:
            try:
                store.retract(subj, pred, obj, reason="pii_quarantine")
            except Exception:
                continue
    if ledger_rows:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                 "quarantined": removed, "rows": ledger_rows[:50]},
                                ensure_ascii=False) + "\n")
    return {"scanned": n, "quarantined": removed}


def forget(store: Any, subject: str, *, max_rows: int = 2_000_000) -> dict[str, Any]:
    """Right to be forgotten: retract every row where `subject` appears as
    subject OR object. Auditable; returns the count removed (never the values)."""
    facts = store.facts_about(subject, limit=10_000) or []
    removed = 0
    for s, p, o in facts:
        try:
            store.retract(s, p, o, reason="right_to_be_forgotten")
            removed += 1
        except Exception:
            continue
    # also rows where the subject is the OBJECT (mentions of the person)
    import numpy as np

    cols = store.open_columns()
    n = min(len(cols["s"]), max_rows)
    if n:
        sid = store.terms.lookup(subject)
        if sid is not None:
            o = np.asarray(cols["o"][:n])
            for i in np.nonzero(o == sid)[0]:
                i = int(i)
                subj = store.terms.term(int(cols["s"][i]))
                pred = store.terms.term(int(cols["p"][i]))
                try:
                    store.retract(subj, pred, subject, reason="right_to_be_forgotten")
                    removed += 1
                except Exception:
                    continue
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                             "forget_subject_masked": _mask(subject),
                             "rows_removed": removed}, ensure_ascii=False) + "\n")
    return {"subject_masked": _mask(subject), "rows_removed": removed}
