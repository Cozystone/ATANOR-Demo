"""Continuously-alive self — the always-on inner life (난제: continuity, not cron).

Starts ONE long-lived loop that eases a persistent self-state forward from real
observations (the cloud-brain learner's activity, disk pressure, open deficits). It
never wakes/sleeps on a schedule; it flows and, on restart, RESUMES the same self.
Read-only and bounded: it mutates no code, no graph, no store — it only feels and
reports its own state. Two endpoints feed the "living-mind" UI:
    GET /api/selfhood/live    → the current self snapshot
    GET /api/selfhood/stream  → SSE, pushes the self as it changes (hash-diffed)
"""
from __future__ import annotations

import asyncio
import json
import shutil
import time
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from packages.continuous_self.loop import ContinuousSelf
from packages.continuous_self.self_state import Observation

router = APIRouter(prefix="/api/selfhood", tags=["continuous-self"])

_STATE_PATH = Path(__file__).resolve().parents[4] / "runtime" / "continuous_self" / "self_state.json"

# delta tracking across observations (net-new growth is what the self "feels")
_prev = {"concepts": None, "relations": None}


def _disk_pressure() -> float:
    try:
        usage = shutil.disk_usage(str(Path(__file__).resolve().parents[4]))
        free_ratio = usage.free / max(1, usage.total)
        # pressure rises as free space falls below ~8%
        return max(0.0, min(1.0, (0.08 - free_ratio) / 0.08)) if free_ratio < 0.08 else 0.0
    except Exception:
        return 0.0


def _observe() -> Observation:
    """Gather the self's real signals THIS instant. Grounded, never fabricated."""
    learning_active = False
    c_delta = r_delta = 0
    uncertainty = 0.3
    deficits = 0
    try:
        from .cloud_brain import cloud_brain_continuous_metrics

        m = cloud_brain_continuous_metrics()
        learning_active = bool(m.get("running"))
        c = int(m.get("concepts_added") or 0)
        r = int(m.get("relations_added") or 0)
        if _prev["concepts"] is not None:
            c_delta = max(0, c - int(_prev["concepts"]))
            r_delta = max(0, r - int(_prev["relations"]))
        _prev["concepts"], _prev["relations"] = c, r
        # accept-rate below 1 means unresolved / rejected material → felt as uncertainty
        acc = float(m.get("accept_rate") or 1.0)
        uncertainty = max(0.0, min(1.0, 1.0 - acc))
    except Exception:
        pass
    try:
        hist = _STATE_PATH.parent.parent.parent / "data" / "self_improve_history.jsonl"
        if hist.exists():
            last = hist.read_text(encoding="utf-8").strip().splitlines()[-1]
            deficits = int(json.loads(last).get("hard_remaining") or 0)
    except Exception:
        pass
    return Observation(
        learning_active=learning_active,
        concepts_delta=c_delta,
        relations_delta=r_delta,
        uncertainty_signal=uncertainty,
        resource_pressure=_disk_pressure(),
        deficit_count=deficits,
    )


def _self_probe(kind: str) -> dict[str, Any]:
    """A READ-ONLY probe the mind runs on ITSELF to serve a goal. OBSERVE-tier only —
    it never writes to the graph, a store, or code. It measures; it does not change."""
    if kind == "measure_coverage_gaps":
        try:
            hist = _STATE_PATH.parent.parent.parent / "data" / "self_improve_history.jsonl"
            last = json.loads(hist.read_text(encoding="utf-8").strip().splitlines()[-1])
            return {"open_gaps": int(last.get("hard_remaining") or 0),
                    "answered": int(last.get("answered_after") or 0)}
        except Exception:
            return {}
    if kind == "probe_uncertainty":
        try:
            from .cloud_brain import cloud_brain_continuous_metrics

            m = cloud_brain_continuous_metrics()
            return {"accept_rate": m.get("accept_rate"), "last_error": m.get("last_error")}
        except Exception:
            return {}
    if kind == "scan_frontier":
        # a read-only peek at what the learner is reaching toward next (no side effects).
        try:
            from .cloud_brain import cloud_brain_continuous_metrics

            titles = cloud_brain_continuous_metrics().get("last_titles") or []
            return {"frontier": titles[0]} if titles else {}
        except Exception:
            return {}
    return {"observed": True}


_SELF = ContinuousSelf(
    _STATE_PATH, _observe, base_interval=2.0, observe_fn=_self_probe, initiative_every=15,
)


def _ensure_alive() -> None:
    if not _SELF.running:
        _SELF.start()


@router.get("/live")
def selfhood_live() -> dict[str, Any]:
    _ensure_alive()
    return _SELF.snapshot()


# ---- gated self-modification: operator approval API -------------------------------
# The mind proposes; ONLY a human decides here. Nothing auto-applies anywhere.
@router.get("/self-modification/proposals")
def selfmod_proposals() -> dict[str, Any]:
    from packages.continuous_self.self_modification import list_proposals

    rows = list_proposals(_SELF.selfmod_ledger)
    return {"proposals": rows[-20:], "pending": [r for r in rows if r["status"] == "pending"],
            "current_params": dict(_SELF.params)}


@router.post("/self-modification/decide")
def selfmod_decide(payload: dict[str, Any]) -> dict[str, Any]:
    """Operator decision. Body: {proposal_id, approve: bool, confirm: "SELF_MOD",
    note?}. The confirm phrase is a deliberate friction — a human must mean it."""
    from packages.continuous_self.self_modification import apply_approved, decide

    if str(payload.get("confirm") or "") != "SELF_MOD":
        return {"ok": False, "reason": "confirm phrase 'SELF_MOD' required — operator only"}
    hit = decide(_SELF.selfmod_ledger, str(payload.get("proposal_id") or ""),
                 bool(payload.get("approve")), str(payload.get("note") or ""))
    if hit is None:
        return {"ok": False, "reason": "proposal not found or not pending"}
    applied = apply_approved(_SELF.selfmod_ledger, _SELF.params) if hit["status"] == "approved" else []
    # clear the bid once decided
    if _SELF.state.attention_bid.get("proposal_id") == hit["id"]:
        _SELF.state.attention_bid = {}
    return {"ok": True, "decision": hit["status"], "applied": [a["id"] for a in applied],
            "current_params": dict(_SELF.params)}


@router.get("/stream")
async def selfhood_stream() -> StreamingResponse:
    _ensure_alive()

    async def _events() -> AsyncIterator[str]:
        last = ""
        last_sent = 0.0
        while True:
            snap = _SELF.snapshot()
            body = json.dumps(snap, ensure_ascii=False)
            now = time.time()
            # the clock-ish fields change every step; hash the felt content instead so
            # a quiet mind streams quietly.
            felt = json.dumps(
                {"vitals": snap["vitals"], "mode": snap["mode"], "focus": snap["focus"],
                 "current_thought": snap["current_thought"]},
                ensure_ascii=False, sort_keys=True,
            )
            if felt != last:
                last = felt
                last_sent = now
                yield f"data: {body}\n\n"
            elif now - last_sent >= 20.0:
                last_sent = now
                yield ": heartbeat\n\n"
            await asyncio.sleep(1.0)

    return StreamingResponse(
        _events(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# Begin living as soon as the API imports this router — the self should already be
# awake when the first observer looks. Guarded so an import-time hiccup can't crash
# app startup.
try:
    _SELF.start()
except Exception:
    pass
