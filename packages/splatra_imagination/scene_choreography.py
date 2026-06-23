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
LayoutIntent = Literal["conversation", "balanced_scene", "wide_particle_stage"]


@dataclass(frozen=True)
class SceneBeat:
    op: SceneBeatOp
    prompt: str = ""
    narration: str = ""
    object_id: str = ""
    semantic_role: str = ""
    visual_affordance: str = ""
    spatial_relation: str = ""
    source_fact: str = ""
    archetype: Archetype | None = None
    t_start: float = 0.0
    duration: float = 1.0
    position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    motion_path: dict[str, Any] = field(default_factory=dict)
    camera: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SceneChoreographyPlan:
    plan_id: str
    stage_layout: StageLayout
    orb_anchor: OrbAnchor
    text_anchor: TextAnchor
    layout_intent: LayoutIntent
    scene_extent: dict[str, Any]
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


def _coerce_motion_path(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    path: dict[str, Any] = {}
    if "from" in value:
        path["from"] = _coerce_position(value.get("from"))
    if "to" in value:
        path["to"] = _coerce_position(value.get("to"))
    if "basis" in value:
        path["basis"] = _clean_text(value.get("basis"), limit=80)
    if "source_prompt" in value:
        path["source_prompt"] = _clean_text(value.get("source_prompt"), limit=96)
    if "target_prompt" in value:
        path["target_prompt"] = _clean_text(value.get("target_prompt"), limit=96)
    return path


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
    visual_affordance = _clean_text(raw.get("visual_affordance") or "", limit=80)
    spatial_relation = _clean_text(raw.get("spatial_relation") or "", limit=80)
    source_fact = _clean_text(raw.get("source_fact") or "", limit=360)
    return SceneBeat(
        op=op,  # type: ignore[arg-type]
        prompt=prompt,
        narration=narration,
        object_id=object_id,
        semantic_role=semantic_role,
        visual_affordance=visual_affordance,
        spatial_relation=spatial_relation,
        source_fact=source_fact,
        archetype=archetype,  # type: ignore[arg-type]
        t_start=_coerce_float(raw.get("t_start"), index * 1.25, minimum=0.0, maximum=600.0),
        duration=_coerce_float(raw.get("duration"), 1.0, minimum=0.1, maximum=60.0),
        position=_coerce_position(raw.get("position")),
        motion_path=_coerce_motion_path(raw.get("motion_path")),
        camera=raw.get("camera") if isinstance(raw.get("camera"), dict) else {},
    )


def _coerce_text_anchor(value: Any, stage_layout: StageLayout) -> TextAnchor:
    text_anchor = str(value or "auto")
    if text_anchor not in {"auto", "upper_left", "lower_left", "upper_right", "lower_center"}:
        text_anchor = "auto"
    if text_anchor == "auto" and stage_layout == "scene_focus":
        return "lower_left"
    return text_anchor  # type: ignore[return-value]


def _coerce_layout_intent(value: Any, stage_layout: StageLayout, beats: list[SceneBeat]) -> LayoutIntent:
    if stage_layout == "conversation":
        return "conversation"
    layout_intent = str(value or "")
    if layout_intent in {"balanced_scene", "wide_particle_stage"}:
        return layout_intent  # type: ignore[return-value]
    motion_count = sum(1 for beat in beats if beat.op == "move" or beat.motion_path)
    if len(beats) >= 4 or motion_count:
        return "wide_particle_stage"
    return "balanced_scene"


def _scene_extent(beats: list[SceneBeat]) -> dict[str, Any]:
    points: list[tuple[float, float]] = []
    motion_count = 0
    for beat in beats:
        points.append((beat.position[0], beat.position[1]))
        if beat.motion_path:
            motion_count += 1
            raw_from = beat.motion_path.get("from")
            raw_to = beat.motion_path.get("to")
            if isinstance(raw_from, tuple) and len(raw_from) >= 2:
                points.append((float(raw_from[0]), float(raw_from[1])))
            if isinstance(raw_to, tuple) and len(raw_to) >= 2:
                points.append((float(raw_to[0]), float(raw_to[1])))
    if not points:
        return {"beat_count": 0, "motion_count": 0, "spread_x": 0.0, "spread_y": 0.0}
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return {
        "beat_count": len(beats),
        "motion_count": motion_count,
        "spread_x": round(max(xs) - min(xs), 3),
        "spread_y": round(max(ys) - min(ys), 3),
        "min_x": round(min(xs), 3),
        "max_x": round(max(xs), 3),
        "min_y": round(min(ys), 3),
        "max_y": round(max(ys), 3),
    }


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
    layout_intent = _coerce_layout_intent(plan.get("layout_intent"), stage_layout, beats)
    scene_extent = _scene_extent(beats)
    seed = f"{stage_layout}:{orb_anchor}:{text_anchor}:{layout_intent}:{[(beat.op, beat.prompt, beat.object_id) for beat in beats]}"
    return SceneChoreographyPlan(
        plan_id=_stable_id("scene_choreo", seed),
        stage_layout=stage_layout,
        orb_anchor=orb_anchor,
        text_anchor=text_anchor,
        layout_intent=layout_intent,
        scene_extent=scene_extent,
        primary_surface="splatra_stage" if stage_layout == "scene_focus" else "conversation",
        beats=beats,
        safety_flags=default_safety_flags(),
    )
