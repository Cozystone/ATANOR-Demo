# -*- coding: utf-8 -*-
"""Soft resolution — the softness-gap bridge (owner blueprint, 2026-07-09).

The symbolic graph is HARD geometry: a query answers only on exact symbols and
stated edges. Human meaning flows; the owner's directive is to soften lookup
WITHOUT softening truth. This module is that boundary, drawn precisely:

  * the PHASE SPACE (trained RotatE-lite) PROPOSES nearby concepts — soft,
    contextual, high-dimensional;
  * the SYMBOLIC GRAPH VERIFIES every proposal — a neighbor only survives if it
    shares a stated is_a parent with the query term (type compatibility read
    from stated edges, never guessed). Today's measured lesson (polysemy noise:
    커피's raw phase neighbors were Spanish provinces) is why the verify step
    is not optional.

Consumers use survivors as SUGGESTIONS ("가장 가까운 검증 개념은 B") — never as
silent substitutions. Facts still come only from stated, sourced edges."""
from __future__ import annotations

from typing import Any

from .phase_space import neighbors as _phase_neighbors


def _is_a_parents(store: Any, term: str, limit: int = 24) -> set[str]:
    """The term's stated type parents, CLOSED OVER TYPE ALIASES: the Korean and
    DBpedia scrapes label the same type differently (동물 vs Animal — measured:
    they partition disjoint entity sets, so co-occurrence can't bridge them).
    The reviewed type_alignment alias edges are that bridge; expanding parents
    one alias hop lets a 동물-typed term and an Animal-typed term verify as
    type-compatible."""
    out: set[str] = set()
    try:
        # SENSE-KEYED READ (stage-4 consumption): a registered hub reads its
        # dominant-sense parents from the sense registry — trust-filtered and
        # partitioned at build time, a cheap JSON lookup at answer time — so
        # the hub's garbage batch (capital is_a Animal/…) never enters type
        # verification. REPLACES raw parents for registered hubs (union would
        # re-admit the garbage); unregistered terms read stated edges as before.
        try:
            from .sense_registry import sense_scoped_parents

            out.update(sense_scoped_parents(term)[:limit])
        except Exception:
            pass
        if not out:
            for s, p, o in store.facts_about(term, limit=limit) or []:
                if p in ("is_a", "instance_of", "subclass_of"):
                    out.add(str(o))
        for parent in list(out):
            for s, p, o in store.facts_about(parent, limit=12) or []:
                if p == "alias" and o:
                    out.add(str(o))
    except Exception:
        pass
    return out


def soft_neighbors(term: str, k: int = 8, floor: float = 0.75) -> list[tuple[str, float]]:
    """Raw phase-space proposals above a resonance floor. UNVERIFIED — callers
    that surface anything to a user must go through typed_soft_match."""
    try:
        return [(t, w) for t, w in (_phase_neighbors(term, k) or []) if w >= floor]
    except Exception:
        return []


def typed_soft_match(store: Any, term: str, k: int = 5,
                     floor: float = 0.8) -> list[dict[str, Any]]:
    """Phase proposals that the SYMBOLIC graph confirms are type-compatible:
    a neighbor survives only if it shares at least one stated is_a parent with
    the query term. Returns [{term, resonance, shared_types}] best-first —
    honest soft context, safe to show a user as a suggestion."""
    mine = _is_a_parents(store, term)
    if not mine:
        return []
    out: list[dict[str, Any]] = []
    for cand, w in soft_neighbors(term, k=max(k * 4, 16), floor=floor):
        if cand == term:
            continue
        shared = mine & _is_a_parents(store, cand)
        if shared:
            out.append({"term": cand, "resonance": round(float(w), 4),
                        "shared_types": sorted(shared)[:4]})
        if len(out) >= k:
            break
    return out


def soft_context_line(store: Any, term: str, language: str = "ko") -> dict[str, Any] | None:
    """One SUGGESTION line for an abstain path: the nearest verified concept and
    its stated definition head. Asserts nothing about `term` itself — it offers
    the neighbor explicitly AS a neighbor, with the shared type as the reason.
    Returns {text, neighbor, resonance, shared_types} or None."""
    matches = typed_soft_match(store, term, k=1)
    if not matches:
        return None
    m = matches[0]
    ndef = ""
    try:
        for _s, p, o in store.facts_about(m["term"], limit=12) or []:
            if p == "defined_as" and any("가" <= ch <= "힣" for ch in str(o)):
                ndef = str(o).split(".")[0][:80]
                break
    except Exception:
        pass
    shared = m["shared_types"][0] if m["shared_types"] else ""
    if language == "ko":
        text = (f"이 그래프에서 '{term}'와 위상적으로 가장 가까운 검증 개념은 "
                f"'{m['term']}'입니다 (공명 {m['resonance']:.2f}, 공통 유형: {shared})."
                + (f" {m['term']}은(는) {ndef}." if ndef else ""))
    else:
        text = (f"The verified concept nearest to '{term}' in the phase space is "
                f"'{m['term']}' (resonance {m['resonance']:.2f}, shared type: {shared})."
                + (f" {m['term']}: {ndef}." if ndef else ""))
    return {"text": text, "neighbor": m["term"], "resonance": m["resonance"],
            "shared_types": m["shared_types"]}
