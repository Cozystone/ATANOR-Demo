# -*- coding: utf-8 -*-
"""Episodic memory: record lived multimodal moments, recall a vague '그때…' cue
into a predictive completion, surface what the glasses saw — and NEVER invent one.
"""
from datetime import datetime, timezone


def _reset(monkeypatch, tmp_path):
    from packages.graph_scale import episodic_memory as em
    monkeypatch.setattr(em, "LEDGER", tmp_path / "episodes.jsonl")
    return em


def test_record_recall_and_predictive_completion(tmp_path, monkeypatch):
    em = _reset(monkeypatch, tmp_path)
    em.record_episode(
        "모터쇼", ["자동차", "모터쇼", "전시"], at="2026-07-15T14:00:00", place="코엑스",
        observations=[em.Observation("vision", "신형 제네시스", salience=0.9)],
        salience=0.8)
    now = datetime(2027, 1, 10, tzinfo=timezone.utc)
    # vague cue while the user trails off; only '자동차' is pinned so far
    comp = em.complete("아 그때 그 우리 갔던 그 뭐더라", ["자동차"], now=now)
    assert comp is not None and comp["hypothesis"] is True
    assert "작년 7월" in comp["completion"] and "모터쇼" in comp["completion"]
    # the smart-glasses observation is surfaced (it was really recorded)
    assert comp["salient_observation"]["label"] == "신형 제네시스"
    assert "신형 제네시스" in comp["completion"]


def test_abstains_when_no_episode_matches(tmp_path, monkeypatch):
    em = _reset(monkeypatch, tmp_path)
    em.record_episode("모터쇼", ["자동차"], at="2026-07-15T14:00:00")
    # a cue about something never experienced -> abstain, not a fabricated memory
    assert em.complete("그때 그 우리 갔던", ["등산"]) is None
    assert em.recall(["등산"]) == []


def test_vision_slot_is_smart_glasses_ready(tmp_path, monkeypatch):
    em = _reset(monkeypatch, tmp_path)
    ep = em.record_episode("카페", ["커피"], at="2026-08-01T09:00:00")
    # the entry point smart glasses / a mic stream would call later
    assert em.add_observation(ep["episode_id"], "vision", "라떼아트", salience=0.7) is True
    assert em.add_observation(ep["episode_id"], "badmodality", "x") is False
    hits = em.recall(["라떼아트"])          # an observation label is itself recallable memory
    assert hits and hits[0]["title"] == "카페"


def test_recall_prefers_salient_over_merely_recent(tmp_path, monkeypatch):
    em = _reset(monkeypatch, tmp_path)
    em.record_episode("잊은 약속", ["자동차"], at="2026-12-20T10:00:00", salience=0.1)
    em.record_episode("인상깊은 모터쇼", ["자동차"], at="2026-07-01T10:00:00", salience=0.95)
    now = datetime(2027, 1, 10, tzinfo=timezone.utc)
    hits = em.recall(["자동차"], now=now, k=2)
    assert hits[0]["title"] == "인상깊은 모터쇼"   # salience outweighs the small recency edge
