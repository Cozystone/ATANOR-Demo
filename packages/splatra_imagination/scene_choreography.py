from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from .models import ARCHETYPES, Archetype, default_safety_flags


SceneBeatOp = Literal["spawn_object", "morph", "move", "focus_camera", "label", "despawn"]
StageLayout = Literal["conversation", "scene_focus"]
OrbAnchor = Literal["center", "lower_right"]
TextAnchor = Literal["auto", "upper_left", "lower_left", "upper_right", "lower_center"]


@dataclass(frozen=True)
class SceneBeat:
    op: SceneBeatOp
    prompt: str = ""
    narration: str = ""
    object_id: str = ""
    semantic_role: str = ""
    source_fact: str = ""
    archetype: Archetype | None = None
    t_start: float = 0.0
    duration: float = 1.0
    position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    camera: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SceneChoreographyPlan:
    plan_id: str
    stage_layout: StageLayout
    orb_anchor: OrbAnchor
    text_anchor: TextAnchor
    primary_surface: str
    beats: list[SceneBeat]
    safety_flags: dict[str, bool]
    external_splatra_called: bool = False
    raw_buffer_in_agent_context: bool = False
    topic_scene_templates: bool = False
    proof_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["beats"] = [beat.to_dict() for beat in self.beats]
        return payload


def _stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def _clean_text(value: Any, *, limit: int = 360) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())[:limit]


def _coerce_float(value: Any, default: float, *, minimum: float, maximum: float) -> float:
    try:
      number = float(value)
    except (TypeError, ValueError):
      return default
    return max(minimum, min(maximum, number))


def _coerce_position(value: Any) -> tuple[float, float, float]:
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        return (0.0, 0.0, 0.0)
    return (
        _coerce_float(value[0], 0.0, minimum=-4.0, maximum=4.0),
        _coerce_float(value[1], 0.0, minimum=-4.0, maximum=4.0),
        _coerce_float(value[2], 0.0, minimum=-4.0, maximum=4.0),
    )


def _coerce_beat(raw: dict[str, Any], index: int) -> SceneBeat:
    op = str(raw.get("op") or "spawn_object")
    if op not in {"spawn_object", "morph", "move", "focus_camera", "label", "despawn"}:
        op = "spawn_object"
    archetype = raw.get("archetype")
    if archetype not in ARCHETYPES:
        archetype = None
    prompt = _clean_text(raw.get("prompt") or raw.get("label") or raw.get("description"))
    narration = _clean_text(raw.get("narration") or raw.get("speech") or "", limit=240)
    object_id = _clean_text(raw.get("object_id") or raw.get("id") or _stable_id("scene_obj", f"{index}:{prompt}"), limit=96)
    semantic_role = _clean_text(raw.get("semantic_role") or raw.get("role") or "", limit=80)
    source_fact = _clean_text(raw.get("source_fact") or "", limit=360)
    return SceneBeat(
        op=op,  # type: ignore[arg-type]
        prompt=prompt,
        narration=narration,
        object_id=object_id,
        semantic_role=semantic_role,
        source_fact=source_fact,
        archetype=archetype,  # type: ignore[arg-type]
        t_start=_coerce_float(raw.get("t_start"), index * 1.25, minimum=0.0, maximum=600.0),
        duration=_coerce_float(raw.get("duration"), 1.0, minimum=0.1, maximum=60.0),
        position=_coerce_position(raw.get("position")),
        camera=raw.get("camera") if isinstance(raw.get("camera"), dict) else {},
    )


def _coerce_text_anchor(value: Any, stage_layout: StageLayout) -> TextAnchor:
    text_anchor = str(value or "auto")
    if text_anchor not in {"auto", "upper_left", "lower_left", "upper_right", "lower_center"}:
        text_anchor = "auto"
    if text_anchor == "auto" and stage_layout == "scene_focus":
        return "lower_left"
    return text_anchor  # type: ignore[return-value]


def compile_scene_choreography(plan: dict[str, Any]) -> SceneChoreographyPlan:
    """Validate an agent-authored SPLATRA scene plan without inventing content.

    This is the boundary needed for non-template visual explanation: the
    conversation/scene agent may author beats, while this module only clamps,
    validates, and marks the dashboard layout that should host them.
    """

    raw_beats = plan.get("beats") if isinstance(plan.get("beats"), list) else []
    beats = [_coerce_beat(item, index) for index, item in enumerate(raw_beats[:32]) if isinstance(item, dict)]
    stage_layout: StageLayout = "scene_focus" if plan.get("stage_layout") == "scene_focus" or beats else "conversation"
    orb_anchor: OrbAnchor = "lower_right" if stage_layout == "scene_focus" or plan.get("orb_anchor") == "lower_right" else "center"
    text_anchor = _coerce_text_anchor(plan.get("text_anchor"), stage_layout)
    seed = f"{stage_layout}:{orb_anchor}:{text_anchor}:{[(beat.op, beat.prompt, beat.object_id) for beat in beats]}"
    return SceneChoreographyPlan(
        plan_id=_stable_id("scene_choreo", seed),
        stage_layout=stage_layout,
        orb_anchor=orb_anchor,
        text_anchor=text_anchor,
        primary_surface="splatra_stage" if stage_layout == "scene_focus" else "conversation",
        beats=beats,
        safety_flags=default_safety_flags(),
    )
