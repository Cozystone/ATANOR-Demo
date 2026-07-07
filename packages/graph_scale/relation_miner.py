# -*- coding: utf-8 -*-
"""Relation miner v0 — Phase 1-4: causal/part-of edges from prose already in the store.

Reasoning and creativity scale with the VARIETY of edge types (measured
conclusion), and the Wikidata profile lane only covers entities Wikidata curates.
This miner extracts relations from the attributed evidence/definitional PROSE the
knowledge learner already stored — real sentences with real provenance.

Precision over recall, three gates (the consensus-machine discipline):
  1. PATTERN gate — a small set of explicit Korean relation constructions;
     nothing is inferred from word co-occurrence.
  2. BOTH-KNOWN gate — both endpoints must already be subjects the store knows;
     an unknown string never becomes a node via mining (no junk nodes).
  3. JUDGE gate — curated_judge.filter_candidates quarantines contradictions.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
STORE_ROOT = REPO / "data" / "graph_scale" / "kg_triples"

_ENT = r"([가-힣A-Za-z0-9·\s]{2,16}?)"
# explicit relation constructions -> (predicate, subject_group, object_group).
# Direction convention matches the Wikidata profile lane: (X, 원인, Y) = X's cause
# is Y; (X, 상위개념, Y) = X is part of Y; (X, 구성요소, Y) = X has part Y.
_PATTERNS: list[tuple[re.Pattern[str], str, int, int]] = [
    (re.compile(_ENT + r"(?:으로|로)\s*인해\s*" + _ENT + r"[이가은는]"), "원인", 2, 1),
    (re.compile(_ENT + r"\s*때문에\s*" + _ENT + r"[이가은는]"), "원인", 2, 1),
    (re.compile(_ENT + r"[은는이가]\s*" + _ENT + r"의\s*일부"), "상위개념", 1, 2),
    (re.compile(_ENT + r"[은는이가]\s*" + _ENT + r"(?:으로|로)\s*구성"), "구성요소", 1, 2),
    (re.compile(_ENT + r"[은는이가]\s*" + _ENT + r"에\s*속(?:하는|한다)"), "상위개념", 1, 2),
]


def _clean(term: str) -> str:
    return re.sub(r"\s+", " ", term).strip(" ,.·")


def mine_relations(store: Any, max_rows: int = 30_000, dry_run: bool = False,
                   log: Any = print) -> dict[str, Any]:
    """Scan stored prose for explicit relation constructions. Returns counters;
    stores judge-passed edges with a 'mined:' source tag for auditability."""
    import numpy as np

    from .curated_judge import filter_candidates

    counters = {"rows": 0, "pattern_hits": 0, "both_known": 0,
                "stored": 0, "quarantined": 0}
    cols = store.open_columns()
    want = set()
    for pname in ("evidence", "defined_as"):
        pid = store.terms.lookup(pname)
        if pid is not None:
            want.add(pid)
    if not want:
        return counters
    pc = np.asarray(cols["p"][:])
    idxs = np.nonzero(np.isin(pc, np.array(sorted(want), dtype=pc.dtype)))[0][:max_rows]
    known_cache: dict[str, bool] = {}

    def _known(term: str) -> bool:
        if term not in known_cache:
            try:
                known_cache[term] = bool(store.facts_about(term, limit=1))
            except Exception:
                known_cache[term] = False
        return known_cache[term]

    candidates: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for i in idxs.tolist():
        text = store.terms.term(int(cols["o"][i]))
        if len(text) < 20:
            continue
        counters["rows"] += 1
        # SUBJECT-ANCHOR gate: the prose row is ABOUT its stored subject, so a
        # mined relation must involve that subject. Without this, at 25M terms
        # 'both known' passes almost any clipped fragment (measured: '모이 원인
        # 회의' — sentence shards that happen to be dictionary headwords).
        row_subj = store.terms.term(int(cols["s"][i]))
        for rx, pred, sg, og in _PATTERNS:
            for m in rx.finditer(text):
                counters["pattern_hits"] += 1
                s, o = _clean(m.group(sg)), _clean(m.group(og))
                if not (2 <= len(s) <= 16 and 2 <= len(o) <= 16) or s == o:
                    continue
                if row_subj not in (s, o):
                    continue  # anchor: the sentence's own topic must participate
                if not (_known(s) and _known(o)):
                    continue  # BOTH-KNOWN gate: mining never creates nodes
                trip = (s, pred, o)
                if trip in seen:
                    continue
                seen.add(trip)
                counters["both_known"] += 1
                candidates.append(trip)
    if not candidates:
        return counters
    verdicts = filter_candidates(candidates, store)
    counters["quarantined"] = len(verdicts.get("quarantined") or [])
    sid = store.intern_source("mined:prose_patterns", "") if not dry_run else None
    for s, p, o in verdicts.get("promotable") or []:
        log(f"  + {s} | {p} | {o}")
        if not dry_run and store.add(s, p, o, source=sid):
            counters["stored"] += 1
    if not dry_run and counters["stored"]:
        store.flush()
    return counters
