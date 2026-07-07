# -*- coding: utf-8 -*-
"""Phase 4-5 v0: visual-ingest — labels only, cooldown, grounded suggestions."""

from __future__ import annotations

import importlib

from fastapi.testclient import TestClient


def _client(monkeypatch, tmp_path):
    # the package __init__ re-exports a `timeline` FUNCTION that shadows the
    # submodule on attribute import — go through importlib for the real module
    tl = importlib.import_module("packages.episodic_memory.timeline")

    monkeypatch.setattr(tl, "EVENTS_PATH", tmp_path / "events.jsonl")
    from app.routers import perception

    importlib.reload(perception)  # fresh cooldown map per test
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(perception.router)
    return TestClient(app), tl


def test_ingest_records_labels_and_never_frames(monkeypatch, tmp_path):
    client, tl = _client(monkeypatch, tmp_path)
    r = client.post("/api/perception/visual-ingest", json={
        "detections": [{"label": "물병", "score": 0.83},
                       {"label": "노이즈", "score": 0.2}]})
    out = r.json()
    assert out["recorded"] == ["물병"]  # low-score dropped
    assert out["frames_received"] == 0 and out["left_device"] is False
    rows = tl.timeline("물병")
    assert rows and rows[0]["predicate"] == "목격" and rows[0]["source"] == "camera"


def test_cooldown_dedupes_repeat_sightings(monkeypatch, tmp_path):
    client, tl = _client(monkeypatch, tmp_path)
    for _ in range(3):
        client.post("/api/perception/visual-ingest", json={
            "detections": [{"label": "컵", "score": 0.9}]})
    assert len(tl.timeline("컵", limit=50)) == 1  # one event, not three


def test_old_possession_triggers_grounded_suggestion(monkeypatch, tmp_path):
    client, tl = _client(monkeypatch, tmp_path)
    # a REAL recorded purchase 3 years ago — the 물병 시나리오 precondition
    tl.record_event("사용자", "구매", "물병", at="2023-06-01", note="스텐 500ml")
    r = client.post("/api/perception/visual-ingest", json={
        "detections": [{"label": "물병", "score": 0.9}]})
    out = r.json()
    assert out["suggestions"], "3-year-old possession must trigger the primitive"
    s = out["suggestions"][0]
    assert s["object"] == "물병" and s["age_days"] > 900
    assert "basis" in s  # the suggestion carries its evidence
