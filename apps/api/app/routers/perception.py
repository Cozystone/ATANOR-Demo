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
