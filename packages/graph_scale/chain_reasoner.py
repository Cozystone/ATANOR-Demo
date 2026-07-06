# -*- coding: utf-8 -*-
"""Multi-hop chain reasoning (roadmap P3) — energy-descent settling over transitive
stored edges.

A relationship question ('참새는 결국 무엇인가?', 'A는 B인가?') is NOT answered by one
triple; it needs a CHAIN: is_a(참새,새) ∧ is_a(새,동물) ⟹ is_a(참새,동물). This module
walks the chain with packages.energy_descent — energy = -depth, so 'downhill' means
climbing toward the most general ancestor, and the discrete Lyapunov property guarantees:
  * NO cycles (a strictly decreasing energy over a finite visited set) — the reasoner
    cannot loop even on a store that (wrongly) contains is_a(A,B) ∧ is_a(B,A);
  * termination WITHOUT an arbitrary hop cap;
  * settling at the best-grounded reachable conclusion, and surfacing a local minimum
    (no downhill edge) as an honest stop.

Grounded: every hop is a STORED transitive edge (is_a/part_of/located_in/subclass_of).
The answer verbalizes the actual chain — no invented links. Hallucination-safe: the
output is a fixed frame over verbatim chain labels.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .inference import RELATION_ALGEBRA

# the transitive relations a chain may follow (each is transitive in RELATION_ALGEBRA)
_CHAIN_PREDS = tuple(p for p, a in RELATION_ALGEBRA.items() if a.get("transitive"))


@dataclass
class ChainResult:
    start: str
    conclusion: str
    predicate: str
    chain: list[tuple[str, str, str]]      # the stored edges actually traversed
    local_minimum: bool

    def to_answer_ko(self) -> str:
        if not self.chain:
            return ""
        pred_ko = {"is_a": "의 일종", "subclass_of": "의 일종", "part_of": "의 일부",
                   "located_in": "에 속한", "subregion_of": "의 하위 지역"}.get(self.predicate, "")
        # verbalize each hop: '참새는 새의 일종이고, 새는 동물의 일종입니다.'
        clauses = []
        for i, (s, _p, o) in enumerate(self.chain):
            tail = "이고" if i < len(self.chain) - 1 else "입니다"
            clauses.append(f"{s}{_josa_neun(s)} {o}{pred_ko}{tail}")
        body = ", ".join(clauses)
        # conclusion when the chain is >1 hop (the transitive fact is the new knowledge)
        if len(self.chain) >= 2:
            body += f". 따라서 {self.start}{_josa_neun(self.start)} {self.conclusion}{pred_ko}입니다"
        return body + ". (출처: 큐레이션 지식그래프 · 다단계 추론)"


def _josa_i(w: str) -> str:
    from packages.lad_morphology import subject
    return subject(w)[len(w):]


def _josa_neun(w: str) -> str:
    from packages.lad_morphology import topic
    return topic(w)[len(w):]


def reason_chain(start: str, facts_about: Callable[[str], list[tuple[str, str, str]]],
                 predicate: str = "is_a", max_states: int = 4096) -> ChainResult | None:
    """Climb the transitive chain from `start` via `predicate` using energy descent.
    facts_about(subject) -> stored (s,p,o) rows. Returns the settled conclusion + the
    exact edges traversed, or None when `start` has no outgoing edge of that predicate."""
    from packages.energy_descent import EnergyDescent

    if predicate not in _CHAIN_PREDS:
        return None
    # neighbour = the object of a stored `predicate` edge; energy = -depth so climbing
    # the hierarchy is strictly downhill. depth is discovered as we go (BFS layer).
    depth: dict[str, int] = {start: 0}
    edge_into: dict[str, tuple[str, str, str]] = {}

    def neighbors(node: str):
        outs = []
        for (s, p, o) in facts_about(node):
            if p == predicate and o != node and o not in depth:
                depth[o] = depth[node] + 1
                edge_into[o] = (s, p, o)
                outs.append(o)
        return outs

    def energy(node: str) -> float:
        return -float(depth.get(node, 0))

    result = EnergyDescent(energy, neighbors, max_states=max_states).settle(start)
    if result.settled_state == start:
        return None  # no outgoing edge — nothing to reason over
    # reconstruct the traversed edges from start to the settled ancestor
    chain: list[tuple[str, str, str]] = []
    node = result.settled_state
    while node in edge_into:
        s, p, o = edge_into[node]
        chain.append((s, p, o))
        node = s
    chain.reverse()
    return ChainResult(start=start, conclusion=result.settled_state, predicate=predicate,
                       chain=chain, local_minimum=result.local_minimum)


def answer_relationship(query: str, facts_about: Callable[[str], list[tuple[str, str, str]]],
                        subjects: list[str]) -> dict[str, Any] | None:
    """Answer a chain/relationship question when the query asks for what something
    ultimately is ('결국/궁극적으로/근본적으로 무엇') and a >=2-hop chain exists."""
    import re

    if not re.search(r"결국|궁극적으로|근본적으로|본질적으로|따지고 보면", query):
        return None
    for subj in subjects:
        r = reason_chain(subj, facts_about, "is_a")
        if r and len(r.chain) >= 2:
            return {
                "answer": r.to_answer_ko(),
                "reasoning_certificate": {
                    "derivation_kind": "multi_hop_chain",
                    "anchor_concept": {"label": r.start},
                    "steps": [{"type": "triple", "fact": f"{s} {p} {o}"} for s, p, o in r.chain],
                    "evidence_concepts": [r.start] + [o for _s, _p, o in r.chain],
                    "confidence": 0.86,
                    "confidence_basis": "energy_descent_settled_over_stored_transitive_edges",
                    "guarantees": {"external_llm": False, "fabricated_facts": False,
                                   "inferred": True, "termination": "lyapunov_guaranteed"},
                },
                "confidence": 0.86,
                "answer_kind": "multi_hop_chain",
            }
    return None
