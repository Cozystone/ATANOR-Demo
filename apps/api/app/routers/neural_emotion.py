from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from packages.neural_emotion import EmotionEngine, safety_flags
from packages.neural_emotion.agentic_bridge import agentic_controls
from packages.neural_emotion.models import EmotionEvent
from packages.neural_emotion.splatra_bridge import splatra_controls
from packages.neural_emotion.surface_bridge import surface_bias
from packages.neural_emotion.voice_bridge import voice_controls


router = APIRouter(prefix="/api/neural-emotion", tags=["neural-emotion"])
ENGINE = EmotionEngine()


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


def _payload(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    snapshot = ENGINE.snapshot().to_dict()
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
    return _payload({"status": "available"})


@router.get("/snapshot")
def snapshot() -> dict[str, Any]:
    return _payload()


@router.post("/event")
def event(request: EmotionEventRequest) -> dict[str, Any]:
    if request.event_type:
        vector = ENGINE.update(request.event_type, intensity=request.intensity, metadata=request.metadata)
        inferred = request.event_type
    elif request.text:
        vector = ENGINE.update_from_user_input(request.text)
        inferred = "from_text"
    else:
        vector = ENGINE.update("resting", intensity=request.intensity, metadata=request.metadata)
        inferred = "resting"
    return _payload({"updated": True, "inferred_event": inferred, "vector": vector.to_dict()})


@router.post("/decay")
def decay(request: DecayRequest) -> dict[str, Any]:
    vector = ENGINE.decay()
    return _payload({"decayed": True, "half_life_seconds": request.half_life_seconds, "vector": vector.to_dict()})


@router.post("/controls")
def controls(request: ControlsRequest) -> dict[str, Any]:
    assert ENGINE.vector is not None
    vector = ENGINE.vector
    return _payload(
        {
            "controls": {
                "surface_bias": surface_bias(vector, ENGINE.profile),
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
