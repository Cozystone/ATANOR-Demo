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
    particle_behavior: str = ""
    physics_hint: dict[str, Any] = field(default_factory=dict)
    source_fact: str = ""
    speech_cue: bool = True
    speech_cue_basis: str = "verified_evidence_unit"
    scene_group_id: str = ""
    scene_group_role: str = ""
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
    dashboard_layout: dict[str, Any]
    primary_surface: str
    beats: list[SceneBeat]
    safety_flags: dict[str, bool]
    speech_timeline: list[dict[str, Any]] = field(default_factory=list)
    layout_timeline: list[dict[str, Any]] = field(default_factory=list)
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
    particle_behavior = _clean_text(raw.get("particle_behavior") or "", limit=80)
    physics_hint = raw.get("physics_hint") if isinstance(raw.get("physics_hint"), dict) else {}
    source_fact = _clean_text(raw.get("source_fact") or "", limit=360)
    speech_cue = bool(raw.get("speech_cue", True))
    speech_cue_basis = _clean_text(raw.get("speech_cue_basis") or "verified_evidence_unit", limit=80)
    scene_group_id = _clean_text(raw.get("scene_group_id") or "", limit=96)
    scene_group_role = _clean_text(raw.get("scene_group_role") or "", limit=80)
    return SceneBeat(
        op=op,  # type: ignore[arg-type]
        prompt=prompt,
        narration=narration,
        object_id=object_id,
        semantic_role=semantic_role,
        visual_affordance=visual_affordance,
        spatial_relation=spatial_relation,
        particle_behavior=particle_behavior,
        physics_hint=physics_hint,
        source_fact=source_fact,
        speech_cue=speech_cue,
        speech_cue_basis=speech_cue_basis,
        scene_group_id=scene_group_id,
        scene_group_role=scene_group_role,
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


def _dashboard_layout(stage_layout: StageLayout, orb_anchor: OrbAnchor, text_anchor: TextAnchor, layout_intent: LayoutIntent, scene_extent: dict[str, Any]) -> dict[str, Any]:
    """Derive dashboard placement from scene geometry, not subject templates."""

    if stage_layout != "scene_focus":
        return {
            "planning_basis": "conversation_default",
            "stage": stage_layout,
            "layout_intent": layout_intent,
            "orb": {"anchor": "center"},
            "speech": {"anchor": text_anchor},
            "scene": {"field_opacity": 0.72},
            "agent_layout_decision": {
                "decision_basis": "conversation_default",
                "agent_action": "keep_orb_primary",
                "text_rendering": "dom_text_not_particles",
            },
        }

    beat_count = float(scene_extent.get("beat_count") or 0.0)
    motion_count = float(scene_extent.get("motion_count") or 0.0)
    spread_x = float(scene_extent.get("spread_x") or 0.0)
    spread_y = float(scene_extent.get("spread_y") or 0.0)
    load = min(1.0, max(0.0, 0.18 + beat_count * 0.08 + motion_count * 0.2 + spread_x * 0.22 + spread_y * 0.18))
    if layout_intent == "wide_particle_stage":
        load = max(load, 0.72)

    orb_size_vmin = round(25.0 - load * 7.5, 2)
    orb_min_px = round(170.0 - load * 38.0)
    orb_max_px = round(262.0 - load * 44.0)
    orb_right_vw = round(12.0 - load * 3.4, 2)
    orb_bottom_vh = round(18.2 - load * 4.1, 2)
    speech_max_vw = round(50.0 - load * 14.0, 2)
    speech_right_vw = round(29.0 - load * 5.0, 2)
    speech_bottom_vh = round(18.0 - load * 2.0, 2)
    upper_left_top_vh = round(23.0 - load * 4.2, 2)
    upper_right_top_vh = round(17.0 + load * 3.8, 2)
    lower_left_bottom_vh = round(16.0 + load * 3.2, 2)
    lower_center_bottom_vh = round(17.0 + load * 3.4, 2)
    self_narration_top_vh = round(16.0 - load * 2.2, 2)
    self_narration_right_vw = round(8.0 - load * 1.4, 2)
    self_narration_max_vw = round(28.0 - load * 4.0, 2)

    return {
        "planning_basis": "scene_geometry_extent",
        "stage": stage_layout,
        "layout_intent": layout_intent,
        "stage_pressure": round(load, 3),
        "orb": {
            "anchor": orb_anchor,
            "size_vmin": orb_size_vmin,
            "min_px": orb_min_px,
            "max_px": orb_max_px,
            "right_vw": orb_right_vw,
            "bottom_vh": orb_bottom_vh,
        },
        "speech": {
            "anchor": text_anchor,
            "max_vw": speech_max_vw,
            "right_vw": speech_right_vw,
            "bottom_vh": speech_bottom_vh,
            "upper_left_top_vh": upper_left_top_vh,
            "upper_right_top_vh": upper_right_top_vh,
            "lower_left_bottom_vh": lower_left_bottom_vh,
            "lower_center_bottom_vh": lower_center_bottom_vh,
        },
        "self_narration": {
            "anchor": "upper_right" if load >= 0.72 else "upper_left",
            "top_vh": self_narration_top_vh,
            "right_vw": self_narration_right_vw,
            "max_vw": self_narration_max_vw,
        },
        "stage_safe_region": {
            "primary": "center_particle_stage",
            "orb_exclusion": "lower_right",
            "text_exclusion": text_anchor,
            "composer_exclusion": "bottom_center",
        },
        "scene": {
            "field_opacity": round(0.9 + load * 0.07, 3),
            "central_scale": round(1.0 + load * 0.14, 3),
        },
        "agent_layout_decision": {
            "decision_basis": "verified_scene_geometry",
            "agent_action": "yield_center_to_particle_scene" if load >= 0.72 else "share_center_with_particle_scene",
            "orb_movement": "lower_right_scaled_down",
            "text_strategy": "dom_text_collision_avoidance",
            "text_rendering": "dom_text_not_particles",
            "scene_region": "dashboard_center",
            "avoid_regions": ["orb", "composer", "self_narration", "scene_motion_paths"],
        },
    }


def _speech_timeline(beats: list[SceneBeat]) -> list[dict[str, Any]]:
    """Expose verified speech beats as a renderer timeline without inventing text."""

    timeline: list[dict[str, Any]] = []
    previous_text = ""
    for index, beat in enumerate(beats):
        if beat.speech_cue is False:
            continue
        text = _clean_text(beat.narration or beat.prompt, limit=240)
        if not text or text == previous_text:
            continue
        previous_text = text
        timeline.append({
            "beat_index": index,
            "object_id": beat.object_id,
            "scene_group_id": beat.scene_group_id,
            "scene_group_role": beat.scene_group_role,
            "text": text,
            "text_source": "verified_beat_narration",
            "speech_cue_basis": beat.speech_cue_basis,
            "t_start": beat.t_start,
            "duration": beat.duration,
            "particle_behavior": beat.particle_behavior,
            "physics_hint": dict(beat.physics_hint),
            "motion_path": dict(beat.motion_path),
            "semantic_role": beat.semantic_role,
            "visual_affordance": beat.visual_affordance,
        })
    return timeline


def _layout_timeline(stage_layout: StageLayout, dashboard_layout: dict[str, Any], beats: list[SceneBeat]) -> list[dict[str, Any]]:
    """Expose orb/text/stage placement decisions as geometry-derived actions."""

    decision = dashboard_layout.get("agent_layout_decision") if isinstance(dashboard_layout.get("agent_layout_decision"), dict) else {}
    if stage_layout != "scene_focus":
        return [{
            "t_start": 0.0,
            "duration": 999.0,
            "action": "keep_orb_primary",
            "decision_basis": "conversation_default",
            "orb_anchor": "center",
            "text_rendering": "dom_text_not_particles",
            "stage_region": "conversation_center",
        }]

    timeline = [{
        "t_start": 0.0,
        "duration": 999.0,
        "action": decision.get("agent_action") or "share_center_with_particle_scene",
        "decision_basis": decision.get("decision_basis") or "verified_scene_geometry",
        "orb_anchor": dashboard_layout.get("orb", {}).get("anchor", "lower_right"),
        "orb_movement": decision.get("orb_movement") or "lower_right_scaled_down",
        "text_rendering": decision.get("text_rendering") or "dom_text_not_particles",
        "text_strategy": decision.get("text_strategy") or "dom_text_collision_avoidance",
        "stage_region": decision.get("scene_region") or "dashboard_center",
    }]
    for index, beat in enumerate(beats):
        if beat.speech_cue is False:
            continue
        timeline.append({
            "t_start": beat.t_start,
            "duration": beat.duration,
            "action": "sync_orb_text_with_particle_beat",
            "decision_basis": "verified_speech_cue_beat",
            "beat_index": index,
            "scene_group_id": beat.scene_group_id,
            "object_id": beat.object_id,
            "orb_anchor": dashboard_layout.get("orb", {}).get("anchor", "lower_right"),
            "text_rendering": "dom_text_not_particles",
            "stage_region": "dashboard_center",
            "particle_behavior": beat.particle_behavior,
        })
    return timeline


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
    dashboard_layout = _dashboard_layout(stage_layout, orb_anchor, text_anchor, layout_intent, scene_extent)
    speech_timeline = _speech_timeline(beats)
    layout_timeline = _layout_timeline(stage_layout, dashboard_layout, beats)
    seed = f"{stage_layout}:{orb_anchor}:{text_anchor}:{layout_intent}:{[(beat.op, beat.prompt, beat.object_id) for beat in beats]}"
    return SceneChoreographyPlan(
        plan_id=_stable_id("scene_choreo", seed),
        stage_layout=stage_layout,
        orb_anchor=orb_anchor,
        text_anchor=text_anchor,
        layout_intent=layout_intent,
        scene_extent=scene_extent,
        dashboard_layout=dashboard_layout,
        primary_surface="splatra_stage" if stage_layout == "scene_focus" else "conversation",
        beats=beats,
        speech_timeline=speech_timeline,
        layout_timeline=layout_timeline,
        safety_flags=default_safety_flags(),
    )
