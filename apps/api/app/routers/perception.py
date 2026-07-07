# -*- coding: utf-8 -*-
"""Perception stream API — the local context ledger the orb reads and the daemon feeds.

POST /api/perception/ingest  {app, window_title}  -> distill + record (raw discarded)
GET  /api/perception/status                        -> events, redactions, interests
GET  /api/perception/interests                     -> recency-weighted current context
POST /api/perception/clear                         -> wipe the ledger (user owns it)
POST /api/perception/tick                          -> probe the active window once (Linux)

The ingest endpoint accepts observations from ANY source (the OS daemon, a browser
extension) — the atomic-ingestion contract. It NEVER stores the raw title or a
screenshot; only concepts + app + time land in the ledger, and nothing leaves 127.0.0.1.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from packages.perception_stream import ContextLedger, ProbeUnavailable, distill_activity

router = APIRouter(prefix="/api/perception", tags=["perception"])

_LEDGER_PATH = Path(__file__).resolve().parents[4] / "data" / "perception" / "context_ledger.jsonl"
_LEDGER = ContextLedger(_LEDGER_PATH)


class IngestIn(BaseModel):
    app: str = Field(default="unknown", max_length=120)
    window_title: str = Field(default="", max_length=600)


@router.post("/ingest")
def ingest(body: IngestIn) -> dict[str, Any]:
    ev = distill_activity(body.app, body.window_title, time.strftime("%Y-%m-%dT%H:%M:%S"))
    _LEDGER.record(ev)
    # echo back the CONCEPTS only — proving the raw never round-trips
    return {"recorded": True, "app": ev.app, "concepts": ev.concepts,
            "redacted": ev.redacted, "raw_discarded": True, "left_device": False}


@router.post("/tick")
def tick() -> dict[str, Any]:
    from packages.perception_stream.capture import probe_active_window

    try:
        app, title = probe_active_window()
    except ProbeUnavailable as exc:
        return {"probed": False, "reason": str(exc)}
    ev = distill_activity(app, title, time.strftime("%Y-%m-%dT%H:%M:%S"))
    _LEDGER.record(ev)
    return {"probed": True, "app": ev.app, "concepts": ev.concepts, "redacted": ev.redacted}


class Detection(BaseModel):
    label: str = Field(max_length=80)
    score: float = 0.0


class VisualIngestIn(BaseModel):
    detections: list[Detection] = Field(default_factory=list, max_length=32)


# per-label cooldown so a bottle sitting in frame for a minute is ONE event,
# not forty — the timeline stays a life log, not a frame log
_SEEN_COOLDOWN_S = 60.0
_last_seen: dict[str, float] = {}


@router.post("/visual-ingest")
def visual_ingest(body: VisualIngestIn) -> dict[str, Any]:
    """Phase 4-5 v0: the browser page detects objects ON DEVICE and sends ONLY
    labels here (frames never leave the page). Each new sighting lands on the
    universal episodic timeline; possessions old enough trigger the 물병
    suggestion primitive — grounded in recorded events, or silent."""
    from packages.episodic_memory.timeline import record_event, repurchase_suggestion

    now = time.time()
    recorded: list[str] = []
    suggestions: list[dict[str, Any]] = []
    for det in body.detections:
        label = det.label.strip()
        if not label or det.score < 0.5:
            continue
        if now - _last_seen.get(label, 0.0) < _SEEN_COOLDOWN_S:
            continue
        _last_seen[label] = now
        record_event("사용자", "목격", label,
                     note=f"카메라 감지 score={det.score:.2f}", source="camera")
        recorded.append(label)
        try:
            s = repurchase_suggestion(label)
            if s:
                suggestions.append(s)
        except Exception:
            continue
    return {"recorded": recorded, "suggestions": suggestions,
            "frames_received": 0, "left_device": False}


@router.get("/status")
def status() -> dict[str, Any]:
    return _LEDGER.stats()


@router.get("/interests")
def interests() -> dict[str, Any]:
    return {"interests": _LEDGER.interests(), "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S")}


@router.post("/clear")
def clear() -> dict[str, Any]:
    try:
        _LEDGER_PATH.unlink()
    except FileNotFoundError:
        pass
    return {"cleared": True}
