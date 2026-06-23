from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from packages.neural_emotion import safety_flags
from packages.neural_emotion.agentic_bridge import agentic_controls
from packages.neural_emotion.event_bus import (
    EVENT_BUS,
    RuntimeEventSource,
    RuntimeEventType,
    SUPPORTED_EVENT_TYPES,
    SUPPORTED_SOURCES,
)
from packages.neural_emotion.models import EmotionEvent
from packages.neural_emotion.splatra_bridge import splatra_controls
from packages.neural_emotion.surface_bridge import surface_bias
from packages.neural_emotion.voice_bridge import voice_controls


router = APIRouter(prefix="/api/neural-emotion", tags=["neural-emotion"])


class EmotionEventRequest(BaseModel):
    event_type: EmotionEvent | None = None
    text: str = ""
    intensity: float = Field(default=1.0, ge=0.0, le=2.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DecayRequest(BaseModel):
    half_life_seconds: float = Field(default=480.0, ge=1.0)


class ControlsRequest(BaseModel):
    risk: float = Field(default=0.0, ge=0.0, le=1.0)
    selected_engine: str = "fallback"
    audio_available: bool = False


class RuntimeEventRequest(BaseModel):
    source: RuntimeEventSource = "user_action"
    event_type: RuntimeEventType
    intensity: float = Field(default=1.0, ge=0.0, le=2.0)
    payload_summary: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    private_payload: bool = False


class ResetRequest(BaseModel):
    workspace: str = "lab"
    clear_events: bool = True


def _payload(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    snapshot = EVENT_BUS.engine.snapshot().to_dict()
    payload = {
        "available": True,
        "proof_only": True,
        "module": "neural_emotion_engine_v0",
        "snapshot": snapshot,
        "safety_flags": safety_flags(),
    }
    if extra:
        payload.update(extra)
    return payload


@router.get("/status")
def status() -> dict[str, Any]:
    return _payload({
        "status": "available",
        "event_log_size": len(EVENT_BUS.events()),
        "supported_sources": list(SUPPORTED_SOURCES),
        "supported_event_types": list(SUPPORTED_EVENT_TYPES),
    })


@router.get("/snapshot")
def snapshot() -> dict[str, Any]:
    return _payload()


@router.post("/event")
def event(request: EmotionEventRequest) -> dict[str, Any]:
    if request.event_type:
        vector = EVENT_BUS.engine.update(request.event_type, intensity=request.intensity, metadata=request.metadata)
        inferred = request.event_type
    elif request.text:
        vector = EVENT_BUS.engine.update_from_user_input(request.text)
        inferred = "from_text"
    else:
        vector = EVENT_BUS.engine.update("resting", intensity=request.intensity, metadata=request.metadata)
        inferred = "resting"
    return _payload({"updated": True, "inferred_event": inferred, "vector": vector.to_dict()})


@router.post("/decay")
def decay(request: DecayRequest) -> dict[str, Any]:
    vector = EVENT_BUS.engine.decay()
    return _payload({"decayed": True, "half_life_seconds": request.half_life_seconds, "vector": vector.to_dict()})


@router.post("/controls")
def controls(request: ControlsRequest) -> dict[str, Any]:
    assert EVENT_BUS.engine.vector is not None
    vector = EVENT_BUS.engine.vector
    return _payload(
        {
            "controls": {
                "surface_bias": surface_bias(vector, EVENT_BUS.engine.profile),
                "voice_controls": voice_controls(
                    vector,
                    selected_engine=request.selected_engine,
                    audio_available=request.audio_available,
                ),
                "splatra_controls": splatra_controls(vector),
                "agentic_controls": agentic_controls(vector, risk=request.risk),
            }
        }
    )


@router.get("/events")
def events() -> dict[str, Any]:
    return _payload({"events": EVENT_BUS.events(), "max_events": EVENT_BUS.max_events})


@router.post("/events/emit")
def emit_event(request: RuntimeEventRequest) -> dict[str, Any]:
    result = EVENT_BUS.emit(
        source=request.source,
        event_type=request.event_type,
        intensity=request.intensity,
        payload=request.payload,
        payload_summary=request.payload_summary,
        private_payload=request.private_payload,
    ).to_dict()
    return _payload({"result": result, "events": EVENT_BUS.events()[-20:]})


@router.get("/controls/current")
def current_controls() -> dict[str, Any]:
    assert EVENT_BUS.engine.vector is not None
    vector = EVENT_BUS.engine.vector
    return _payload(
        {
            "controls": {
                "surface_bias": surface_bias(vector, EVENT_BUS.engine.profile),
                "voice_controls": voice_controls(vector),
                "splatra_controls": splatra_controls(vector),
                "agentic_controls": agentic_controls(vector),
            },
            "events": EVENT_BUS.events()[-20:],
        }
    )


@router.post("/reset")
def reset(request: ResetRequest) -> dict[str, Any]:
    if request.workspace not in {"lab", "dev", "developer"}:
        return _payload({"allowed": False, "reset": False, "reason": "reset_is_lab_dev_only"})
    snapshot_after = EVENT_BUS.reset(clear_events=request.clear_events)
    return _payload({"allowed": True, "reset": True, "snapshot_after": snapshot_after, "events": EVENT_BUS.events()})
