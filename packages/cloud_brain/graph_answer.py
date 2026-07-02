"""Graph-grounded answer that LEARNS from being asked — the live seam for online Hebbian.

When a question matches a concept in the learned candidate graph, pull that concept's relations
(weight-ranked), state them as a grounded answer, and REINFORCE the ones used — so a concept that
keeps getting asked about strengthens its most-used edges (LTP), while unused edges decay (LTD).
This is real (the reinforced weight changes the next answer's ordering) and bounded to the asked
concept's few edges (O(path), not O(graph)). Only the learnable candidate store is mutated.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .hebbian_retrieval import apply_answer_reinforcement, rank_by_weight


def _load_names(root: Path) -> tuple[dict[str, str], dict[str, str]]:
    id_to_name: dict[str, str] = {}
    name_to_id: dict[str, str] = {}
    cpath = root / "concepts.jsonl"
    if cpath.exists():
        for line in cpath.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            cid, nm = str(d.get("concept_id") or ""), str(d.get("canonical_name") or "")
            if cid and nm:
                id_to_name[cid] = nm
                name_to_id.setdefault(nm, cid)
    return id_to_name, name_to_id


def _resolve_concept(query: str, name_to_id: dict[str, str]) -> tuple[str, str] | None:
    q = (query or "").strip()
    if not q:
        return None
    if q in name_to_id:
        return name_to_id[q], q
    # longest name that appears in the query (entity mention)
    best = ""
    for name in name_to_id:
        if len(name) >= 2 and name in q and len(name) > len(best):
            best = name
    return (name_to_id[best], best) if best else None


def graph_answer_and_learn(
    store_path: str | Path,
    query: str,
    now: datetime | None = None,
    *,
    max_relations: int = 3,
) -> dict[str, Any]:
    """Answer `query` from the candidate graph and reinforce the edges used. Returns the answer +
    which relation edges were strengthened (empty/None-answer when nothing matches — no fabrication)."""
    now = now or datetime.now().astimezone()
    root = Path(store_path)
    rel_path = root / "relations.jsonl"
    if not rel_path.exists():
        return {"answer": None, "reason": "no_store", "reinforced": []}
    id_to_name, name_to_id = _load_names(root)
    resolved = _resolve_concept(query, name_to_id)
    if not resolved:
        return {"answer": None, "reason": "no_matching_concept", "reinforced": []}
    cid, name = resolved
    rels = [json.loads(l) for l in rel_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    concept_rels = [r for r in rels if str(r.get("source_concept_id")) == cid]
    if not concept_rels:
        return {"answer": None, "reason": "concept_has_no_edges", "reinforced": []}
    top = rank_by_weight(concept_rels, now)[:max_relations]
    clauses = [f"{id_to_name.get(str(r.get('target_concept_id')), '?')}({r.get('relation')})" for r in top]
    answer = f"{name}: " + ", ".join(clauses)
    result = apply_answer_reinforcement(rel_path, cid, now, max_relations=max_relations)  # LTP + persist
    return {
        "answer": answer,
        "concept": name,
        "concept_id": cid,
        "grounding": [{"relation": r.get("relation"), "target": id_to_name.get(str(r.get("target_concept_id")))} for r in top],
        "reinforced": result.get("relation_ids", []),
        "guarantees": {"external_llm": False, "fabricated_facts": False, "learnable_store_only": True},
    }
