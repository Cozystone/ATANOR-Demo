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
from .neuroplasticity import decayed_weight, predicate_informativeness


def _has_batchim(word: str) -> bool:
    o = ord(word[-1]) if word else 0
    return 0xAC00 <= o <= 0xD7A3 and (o - 0xAC00) % 28 != 0


def coverage_score(concept_rels: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    """Does the graph KNOW this concept well enough to answer from it? Graph statistics, no rule
    table: count DISTINCT (relation, target) facts, each weighted by its predicate's data-derived
    informativeness × its learned (decayed) edge weight. One generic taxonomy edge scores low; a
    concept with several distinct, informative, reinforced facts scores high."""
    scores = predicate_informativeness(concept_rels)
    seen: set[tuple[str, str]] = set()
    quality = 0.0
    isa_targets: set[str] = set()
    for r in concept_rels:
        key = (str(r.get("relation") or ""), str(r.get("target_concept_id") or ""))
        if key in seen or not key[1]:
            continue
        seen.add(key)
        pred = key[0]
        info = 1.0 if pred == "IS_A" else (0.0 if pred.endswith("_OF") else scores.get(pred, 0.5))
        quality += info * decayed_weight(r.get("weight", 0.5), r.get("updated_at"), now)
        if pred == "IS_A":
            isa_targets.add(key[1])
    distinct = len(seen)
    if distinct == 0:
        return {"distinct_facts": 0, "coverage": 0.0}
    # COHERENCE, not volume: a real concept has a FEW coherent facts. A stopword/parsing-noise hub
    # (일 → 무신·디자이너·장군…) has MANY distinct IS_A parents — penalise that. Cap the reward for
    # sheer degree so a noise hub can't win on count alone.
    mean_quality = quality / distinct
    hub_penalty = 1.0 / (1.0 + 0.6 * max(0, len(isa_targets) - 3))
    coverage = mean_quality * min(distinct, 5) * hub_penalty
    return {"distinct_facts": distinct, "isa_parents": len(isa_targets), "coverage": round(coverage, 3)}


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
    min_coverage: float = 1.0,
) -> dict[str, Any]:
    """Answer `query` from the candidate graph and reinforce the edges used — but ONLY when the
    graph's coverage of the concept passes the trust gate (else answer=None so the caller defers to
    web/pack). Returns the answer + which relation edges were strengthened. No fabrication."""
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
    # QUALITY FILTER: drop extraction-noise IS_A edges (adjective/fragment/polysemy parents) using
    # graph statistics before the concept is even scored — so noise can't reach the answer.
    from .relation_quality import filter_trusted_relations, graph_stats

    stats = graph_stats(rels, id_to_name)
    concept_rels = filter_trusted_relations([r for r in rels if str(r.get("source_concept_id")) == cid], id_to_name, stats)
    if not concept_rels:
        return {"answer": None, "reason": "concept_has_no_edges", "reinforced": []}
    # TRUST GATE: only answer from the graph when it genuinely covers the concept — else defer
    # (the caller falls back to web/pack). This is what keeps a noisy learned graph honest.
    cov = coverage_score(concept_rels, now)
    if cov["distinct_facts"] < 2 or cov["coverage"] < min_coverage:
        return {"answer": None, "reason": "low_graph_coverage", "coverage": cov, "reinforced": []}
    # dedup (relation, target) and realize a clean, josa-correct statement from the top facts
    ranked = rank_by_weight(concept_rels, now)
    facts: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for r in ranked:
        rel, tgt = str(r.get("relation") or ""), id_to_name.get(str(r.get("target_concept_id")), "")
        # skip copula / auxiliary parse artifacts ("be", "is", "was", "의") — not real relations
        if rel.lower() in {"be", "is", "are", "was", "were", "been", "have", "has", "의", "가"}:
            continue
        key = (rel, tgt)
        if tgt and key not in seen:
            seen.add(key)
            facts.append(key)
        if len(facts) >= max_relations:
            break
    answer = _realize(name, facts)
    result = apply_answer_reinforcement(rel_path, cid, now, max_relations=max_relations)  # LTP + persist
    return {
        "answer": answer,
        "concept": name,
        "concept_id": cid,
        "coverage": cov,
        "grounding": [{"relation": rel, "target": tgt} for rel, tgt in facts],
        "reinforced": result.get("relation_ids", []),
        "guarantees": {"external_llm": False, "fabricated_facts": False, "learnable_store_only": True},
    }


_REL_PHRASE = {
    "IS_A": "{t}의 한 종류", "USED_FOR": "{t}에 쓰이는 것", "ENABLES": "{t}을(를) 가능하게 하는 것",
    "HAS": "{t}을(를) 가진 것", "HAS_PART": "{t}(으)로 이루어진 것", "PART_OF": "{t}의 일부",
    "LOCATED_IN": "{t}에 위치한 것", "CAUSES": "{t}을(를) 일으키는 것",
}


def _realize(name: str, facts: list[tuple[str, str]]) -> str:
    """Surface realization (LAD) of graph facts — generic per-relation phrasing, not per-entity
    rules. Groups by relation so '회사, 기업의 한 종류' reads once."""
    by_rel: dict[str, list[str]] = {}
    for rel, tgt in facts:
        by_rel.setdefault(rel, [])
        if tgt not in by_rel[rel]:
            by_rel[rel].append(tgt)
    parts: list[str] = []
    for rel, tgts in by_rel.items():
        joined = ", ".join(tgts)
        template = _REL_PHRASE.get(rel, f"{{t}}와(과) {rel} 관계인 것")
        parts.append(template.format(t=joined))
    topic = "은" if _has_batchim(name) else "는"
    return f"{name}{topic} " + ", ".join(parts) + "입니다."
