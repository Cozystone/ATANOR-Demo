# -*- coding: utf-8 -*-
"""Multi-hop chain reasoning: energy-descent settles at the most general ancestor over
stored transitive edges, terminates without a hop cap, cannot loop, and verbalizes the
exact chain — no invented links."""
from __future__ import annotations

from packages.graph_scale.chain_reasoner import answer_relationship, reason_chain


def _store(edges):
    by_s: dict[str, list[tuple[str, str, str]]] = {}
    for s, p, o in edges:
        by_s.setdefault(s, []).append((s, p, o))
    return lambda subj: by_s.get(subj, [])


def test_climbs_multi_hop_is_a_chain():
    fa = _store([("참새", "is_a", "새"), ("새", "is_a", "동물"), ("동물", "is_a", "생물")])
    r = reason_chain("참새", fa, "is_a")
    assert r is not None
    assert r.conclusion == "생물"
    assert [o for _s, _p, o in r.chain] == ["새", "동물", "생물"]
    assert r.local_minimum is False


def test_verbalizes_chain_with_conclusion():
    fa = _store([("참새", "is_a", "새"), ("새", "is_a", "동물")])
    r = reason_chain("참새", fa, "is_a")
    ans = r.to_answer_ko()
    assert "참새는 새의 일종이고" in ans  # topic particle, nominal chain
    assert "새는 동물의 일종입니다" in ans
    assert "따라서 참새는 동물의 일종입니다" in ans


def test_cycle_cannot_loop_terminates():
    # a wrongly-stored cycle A->B->A must not hang: energy strictly decreases,
    # so a revisit is impossible; it settles at the first hop.
    fa = _store([("A", "is_a", "B"), ("B", "is_a", "A")])
    r = reason_chain("A", fa, "is_a")
    assert r is not None and r.conclusion == "B"  # B is visited once; A already seen


def test_no_outgoing_edge_returns_none():
    fa = _store([("고립개념", "defined_as", "설명")])  # no is_a edge
    assert reason_chain("고립개념", fa, "is_a") is None


def test_relationship_question_gated_on_cue_and_depth():
    fa = _store([("참새", "is_a", "새"), ("새", "is_a", "동물")])
    # cue present + 2-hop chain -> answered
    r = answer_relationship("참새는 결국 무엇인가?", fa, ["참새"])
    assert r is not None and r["answer_kind"] == "multi_hop_chain"
    assert len(r["reasoning_certificate"]["steps"]) == 2
    # no cue -> not this path's job
    assert answer_relationship("참새란?", fa, ["참새"]) is None
