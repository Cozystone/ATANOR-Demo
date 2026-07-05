"""Curated-KG-as-judge: a learned fact that contradicts a curated fact must be quarantined
(the 퀴리→핵분열 / 중력 is_a 이론 class), while facts the curated store confirms or knows
nothing about pass through to the normal consensus gate. Disjointness lives IN the store
(disjoint_with edges), never in code."""
from __future__ import annotations

import tempfile
from pathlib import Path

from packages.graph_scale.curated_judge import filter_candidates, judge
from packages.graph_scale.triple_store import TripleStore


def _store(triples):
    ts = TripleStore(Path(tempfile.mkdtemp()) / "kg")
    ts.bulk_ingest(triples)
    return ts


def test_functional_contradiction_quarantined():
    ts = _store([("일본", "capital", "도쿄도")])
    v = judge("일본", "capital", "오사카", ts)
    assert v["verdict"] == "contradicted"
    assert "일본 capital 도쿄도" in v["evidence"]


def test_consistent_and_unknown():
    ts = _store([("일본", "capital", "도쿄도")])
    assert judge("일본", "capital", "도쿄도", ts)["verdict"] == "consistent"
    assert judge("퀴리", "discovered", "라듐", ts)["verdict"] == "unknown"  # no evidence -> consensus gate decides


def test_non_functional_predicate_never_contradicts():
    # a person can discover MANY things; a second object is not a contradiction
    ts = _store([("퀴리", "discovered", "라듐")])
    assert judge("퀴리", "discovered", "폴로늄", ts)["verdict"] == "unknown"


def test_type_conflict_via_disjoint_with_edges():
    # the 중력 is_a 이론 class: the store asserts 중력 is_a 상호작용 and that 상호작용 and
    # 이론 are disjoint TYPES — so the learned parent is quarantined. Knowledge in the graph.
    ts = _store([("중력", "is_a", "상호작용"), ("상호작용", "disjoint_with", "이론")])
    v = judge("중력", "is_a", "이론", ts)
    assert v["verdict"] == "type_conflict"


def test_filter_candidates_splits():
    ts = _store([("일본", "capital", "도쿄도")])
    r = filter_candidates([("일본", "capital", "오사카"), ("한국", "capital", "서울")], ts)
    assert r["promotable"] == [("한국", "capital", "서울")]
    assert len(r["quarantined"]) == 1 and r["quarantined"][0]["fact"] == ("일본", "capital", "오사카")


def test_abstain_queue_roundtrip(tmp_path, monkeypatch):
    from packages.graph_scale import abstain_queue as aq

    monkeypatch.setattr(aq, "QUEUE_PATH", tmp_path / "q.jsonl")
    added = aq.record_abstain("성남시가 어디야?")
    assert "성남시" in added
    assert "성남시" in aq.pending()
    aq.mark("성남시", "ingested", "2 facts")
    assert "성남시" not in aq.pending()          # status transition consumed it
    # re-recording the same term does not duplicate
    assert aq.record_abstain("성남시 알려줘") == []
