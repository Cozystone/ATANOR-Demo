from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from typing import Any

from packages.cgsr.cgsr.conversation_grounding import GroundedContext
from packages.cgsr.cgsr.conversation_router import ConversationRoute
from packages.splatra_imagination import compile_scene_choreography
from packages.splatra_imagination.models import Archetype


PRODUCT_ARCHETYPES: tuple[Archetype, ...] = (
    "constellation",
    "city_block",
    "circuit",
    "tree",
    "machine_core",
    "tower",
    "abstract_memory_cloud",
    "creature",
)

VISUAL_ROUTE_TYPES = {
    "splatra_request",
    "local_cloud_brain_explanation",
    "agentic_os_request",
    "voice_status",
    "general_knowledge_question",
}

ANCHOR_STOPWORDS = {
    "therefore",
    "a",
    "an",
    "and",
    "are",
    "as",
    "associated",
    "however",
    "because",
    "event",
    "explain",
    "first",
    "for",
    "from",
    "helped",
    "is",
    "of",
    "on",
    "sat",
    "the",
    "second",
    "third",
    "to",
    "toward",
    "under",
    "with",
    "따라서",
    "그러나",
    "그리고",
    "하지만",
    "또한",
    "첫",
    "번째",
    "단계",
    "기존",
    "대한",
    "대해",
    "것",
    "이는",
    "그",
    "중",
}

KOREAN_SUFFIXES = (
    "으로는",
    "로는",
    "으로",
    "에서",
    "에게",
    "에는",
    "이다",
    "입니다",
    "하고",
    "까지",
    "부터",
    "처럼",
    "보다",
    "이며",
    "이나",
    "거나",
    "은",
    "는",
    "이",
    "가",
    "을",
    "를",
    "의",
    "에",
    "로",
)

MOTION_CUES = {
    "fall",
    "falls",
    "falling",
    "move",
    "moves",
    "moving",
    "orbit",
    "orbits",
    "rotate",
    "rotates",
    "attract",
    "attracts",
    "pull",
    "pulls",
    "drop",
    "drops",
    "떨어",
    "낙하",
    "움직",
    "이동",
    "회전",
    "공전",
    "끌",
    "당기",
    "작용",
}

RELATION_CUES = {
    "formulated",
    "discovered",
    "defined",
    "called",
    "known",
    "means",
    "is",
    "are",
    "발견",
    "정의",
    "기술",
    "나타내",
    "의미",
    "불리",
}


@dataclass(frozen=True)
class VisualImaginationPlan:
    enabled: bool
    reason: str
    scene_choreography: dict[str, Any] | None
    diagnostics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _stable_index(value: str, size: int) -> int:
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % max(1, size)


def _clean_phrase(value: str, *, limit: int = 96) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())[:limit]


def _normalize_anchor_token(token: str) -> str:
    token = token.strip()
    for suffix in KOREAN_SUFFIXES:
        if len(token) > len(suffix) + 1 and token.endswith(suffix):
            return token[: -len(suffix)]
    return token


def _fact_units(fact: str) -> list[str]:
    """Split a verified fact into scene-sized units without topic templates."""

    clean = _clean_phrase(fact, limit=420)
    if not clean:
        return []
    parts = re.split(r"(?<=[.!?。！？])\s+|[;；]\s*", clean)
    units = [_clean_phrase(part, limit=180) for part in parts if _clean_phrase(part, limit=180)]
    return units[:4] or [clean[:180]]


def _entity_spans(text: str) -> list[str]:
    """Extract text-local visual anchors; never map topics to invented props."""

    spans: list[str] = []
    for match in re.finditer(r"\b(?:[A-Z][a-z]+|[A-Z]{2,})(?:\s+(?:[A-Z][a-z]+|[A-Z]{2,})){0,3}\b", text):
        spans.append(match.group(0))
    for match in re.finditer(r"[0-9A-Za-z가-힣][0-9A-Za-z가-힣·\-]{1,}(?:\s+[0-9A-Za-z가-힣][0-9A-Za-z가-힣·\-]{1,}){0,2}", text):
        candidate = match.group(0).strip()
        if len(candidate) >= 2:
            spans.append(candidate)

    cleaned: list[str] = []
    for span in spans:
        tokens = [_normalize_anchor_token(token) for token in span.split()]
        tokens = [
            token
            for token in tokens
            if token and token.casefold() not in ANCHOR_STOPWORDS and len(token) >= 2
        ]
        if not tokens:
            continue
        cleaned.append(_clean_phrase(" ".join(tokens[:3]), limit=72))

    deduped: list[str] = []
    seen: set[str] = set()
    for span in cleaned:
        key = span.casefold()
        if key not in seen:
            seen.add(key)
            deduped.append(_clean_phrase(span, limit=72))
    return deduped[:4]


def _has_any_cue(text: str, cues: set[str]) -> bool:
    folded = text.casefold()
    return any(cue in folded for cue in cues)


def _scene_op_for_unit(unit: str, *, index: int, is_last: bool) -> str:
    """Choose a visual operation from linguistic evidence, not topic templates."""

    if index == 0:
        return "spawn_object"
    if is_last:
        return "focus_camera"
    if _has_any_cue(unit, MOTION_CUES):
        return "move"
    if _has_any_cue(unit, RELATION_CUES):
        return "morph"
    return "morph"


def _make_scene_beat(unit: dict[str, str], *, index: int, op: str, t_start: float) -> dict[str, Any]:
    phrase = unit["prompt"]
    object_seed = f"{index}:{op}:{unit['prompt']}:{unit['narration']}"
    visual_affordance = _visual_affordance_for_phrase(phrase, unit["narration"], unit["semantic_role"], op)
    spatial_relation = _spatial_relation_for_phrase(phrase, unit["narration"], visual_affordance, op)
    position = _position_for_unit(phrase, index, visual_affordance, spatial_relation)
    beat = {
        "op": op,
        "prompt": phrase,
        "narration": unit["narration"],
        "object_id": f"grounded_visual_{index}_{_stable_index(object_seed, 100000):05d}",
        "semantic_role": unit["semantic_role"],
        "visual_affordance": visual_affordance,
        "spatial_relation": spatial_relation,
        "source_fact": unit["source_fact"],
        "archetype": _archetype_for_phrase(phrase, unit["semantic_role"], index, visual_affordance),
        "t_start": round(t_start, 2),
        "duration": 1.35 if op == "move" else 1.25,
        "position": position,
        "camera": _camera_for_unit(position, visual_affordance, op, spatial_relation, index) if op in {"focus_camera", "move"} else {},
    }
    motion_path = _motion_path_for_unit(unit, index=index) if op == "move" or unit["semantic_role"].startswith("verified_motion") else {}
    if motion_path:
        beat["motion_path"] = motion_path
    return beat


def _scene_units(question: str, *, route_type: str, grounded_context: GroundedContext) -> list[dict[str, str]]:
    units: list[dict[str, str]] = []
    if route_type == "splatra_request":
        clean_question = _clean_phrase(question)
        if clean_question:
            units.append(
                {
                    "prompt": clean_question,
                    "narration": clean_question,
                    "source_fact": "",
                    "semantic_role": "user_visual_intent",
                }
            )

    for fact in grounded_context.facts:
        clean_fact = _clean_phrase(fact, limit=420)
        for unit in _fact_units(clean_fact):
            anchors = _entity_spans(unit)
            prompt = " / ".join(anchors[:2]) if len(anchors) >= 2 else anchors[0] if anchors else unit
            semantic_role = "verified_entity_relation" if len(anchors) >= 2 else "verified_fact_unit"
            if _has_any_cue(unit, MOTION_CUES):
                semantic_role = "verified_motion_event"
            units.append(
                {
                    "prompt": prompt,
                    "narration": _clean_phrase(unit, limit=180),
                    "source_fact": clean_fact,
                    "semantic_role": semantic_role,
                }
            )
            if _has_any_cue(unit, MOTION_CUES):
                for anchor_index, anchor in enumerate(anchors[:3]):
                    units.append(
                        {
                            "prompt": anchor,
                            "narration": _clean_phrase(unit, limit=180),
                            "source_fact": clean_fact,
                            "semantic_role": "verified_motion_anchor" if anchor_index == 0 else "verified_motion_context",
                        }
                    )
            for anchor_index, anchor in enumerate(anchors[:4]):
                units.append(
                    {
                        "prompt": anchor,
                        "narration": _clean_phrase(unit, limit=180),
                        "source_fact": clean_fact,
                        "semantic_role": "verified_entity_anchor",
                    }
                )

    if not units:
        clean_question = _clean_phrase(question)
        if clean_question:
            units.append(
                {
                    "prompt": clean_question,
                    "narration": clean_question,
                    "source_fact": "",
                    "semantic_role": "surface_phrase",
                }
            )

    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for unit in units:
        key = f"{unit['prompt']}::{unit['narration']}".casefold()
        if key not in seen:
            seen.add(key)
            deduped.append(unit)
    selected = deduped[:14]
    selected_keys = {f"{unit['prompt']}::{unit['narration']}::{unit['semantic_role']}".casefold() for unit in selected}
    for unit in deduped[14:]:
        role = unit["semantic_role"]
        if role not in {"verified_motion_event", "verified_motion_anchor", "verified_motion_context"}:
            continue
        key = f"{unit['prompt']}::{unit['narration']}::{role}".casefold()
        if key in selected_keys:
            continue
        for replace_index in range(len(selected) - 1, -1, -1):
            if selected[replace_index]["semantic_role"] in {"verified_entity_anchor", "verified_fact_unit"}:
                selected[replace_index] = unit
                selected_keys.add(key)
                break
    return selected


def _looks_like_named_figure(phrase: str) -> bool:
    tokens = re.findall(r"\b[A-Z][a-z]{2,}\b", phrase)
    return len(tokens) >= 2


def _visual_affordance_for_phrase(phrase: str, narration: str, semantic_role: str, op: str) -> str:
    """Infer a visual carrier affordance from the grounded phrase itself.

    This is not a topic-to-scene script. It only reads morphology already
    present in the verified phrase, so gravity never implies a tree unless a
    source fact actually says tree.
    """

    folded_phrase = phrase.casefold()
    if _looks_like_named_figure(phrase):
        return "entity_figure"
    if any(term in folded_phrase for term in ("tree", "forest", "branch", "trunk", "leaf", "leaves", "canopy", "plant")):
        return "organic_structure"
    if any(term in folded_phrase for term in ("fruit", "apple", "stone", "ball", "object", "body", "mass")):
        return "small_moving_object" if op == "move" or "motion" in semantic_role else "small_object"
    if op == "move" or "motion" in semantic_role:
        return "motion_event"
    if "relation" in semantic_role:
        return "relation_field"
    return "concept_cloud"


def _spatial_relation_for_phrase(phrase: str, narration: str, visual_affordance: str, op: str) -> str:
    folded = f" {narration.casefold()} "
    if " under " in folded or " beneath " in folded or " below " in folded:
        if visual_affordance == "entity_figure":
            return "under_target"
        if visual_affordance == "organic_structure":
            return "over_anchor"
        if visual_affordance in {"small_object", "small_moving_object"}:
            return "upper_attachment"
    if op == "move" or " toward " in folded or " towards " in folded:
        if visual_affordance in {"small_object", "small_moving_object"}:
            return "path_object"
        if visual_affordance == "entity_figure":
            return "motion_target"
        if visual_affordance == "organic_structure":
            return "motion_source"
    return ""


def _archetype_for_phrase(phrase: str, semantic_role: str, index: int, visual_affordance: str = "") -> Archetype:
    # This is deliberately not a topic dictionary. It only chooses a bounded
    # visual carrier deterministically so the planner does not smuggle in
    # prompt-specific templates such as "gravity -> Newton/apple/tree".
    if visual_affordance == "entity_figure":
        return "creature"
    if visual_affordance == "organic_structure":
        return "tree"
    if visual_affordance in {"small_object", "small_moving_object"}:
        return "machine_core"
    if visual_affordance == "motion_event":
        return "constellation"
    if visual_affordance in {"relation_field", "concept_cloud"}:
        return "abstract_memory_cloud"
    role_seed = semantic_role if semantic_role in {
        "verified_motion_anchor",
        "verified_motion_context",
        "verified_motion_event",
        "verified_entity_anchor",
        "verified_entity_relation",
    } else "grounded"
    return PRODUCT_ARCHETYPES[_stable_index(f"{role_seed}:{index}:{phrase}", len(PRODUCT_ARCHETYPES))]


def _position_for_phrase(phrase: str, index: int) -> list[float]:
    # Phrase-dependent placement gives the renderer room to move without
    # smuggling in topic templates. The same grounded phrase always lands in
    # the same bounded area, but there is no dictionary such as gravity->tree.
    x_bucket = _stable_index(f"x:{index}:{phrase}", 9) - 4
    y_bucket = _stable_index(f"y:{index}:{phrase}", 7) - 3
    return [round(x_bucket * 0.22, 2), round(y_bucket * 0.16, 2), 0.0]


def _position_for_unit(phrase: str, index: int, visual_affordance: str, spatial_relation: str) -> list[float]:
    relation_positions = {
        "under_target": [-0.18, -0.34, 0.0],
        "over_anchor": [0.2, 0.28, 0.0],
        "upper_attachment": [0.16, 0.42, 0.0],
        "path_object": [0.02, 0.34, 0.0],
        "motion_target": [-0.2, -0.32, 0.0],
        "motion_source": [0.24, 0.3, 0.0],
    }
    if spatial_relation in relation_positions:
        base = relation_positions[spatial_relation]
        jitter_x = (_stable_index(f"rx:{index}:{phrase}", 5) - 2) * 0.025
        jitter_y = (_stable_index(f"ry:{index}:{phrase}", 5) - 2) * 0.02
        return [round(base[0] + jitter_x, 2), round(base[1] + jitter_y, 2), 0.0]
    return _position_for_phrase(phrase, index)


def _motion_path_for_unit(unit: dict[str, str], *, index: int) -> dict[str, Any]:
    narration = unit["narration"]
    if not _has_any_cue(narration, MOTION_CUES):
        return {}
    source_prompt = ""
    target_prompt = ""
    from_match = re.search(
        r"\bfrom\s+(?:a|an|the)?\s*([A-Za-z][A-Za-z -]{1,44}?)(?=\s+(?:toward|towards|to|into|onto)\b|[,.;]|$)",
        narration,
        re.IGNORECASE,
    )
    if from_match:
        source_prompt = _clean_phrase(from_match.group(1), limit=72)
    target_match = re.search(
        r"\b(?:toward|towards|to|into|onto)\s+(?:a|an|the)?\s*([A-Za-z][A-Za-z -]{1,44}?)(?=[,.;]|$)",
        narration,
        re.IGNORECASE,
    )
    if target_match:
        target_prompt = _clean_phrase(target_match.group(1), limit=72)

    anchors = _entity_spans(narration)
    if not source_prompt and len(anchors) >= 2:
        source_prompt = anchors[-2]
    if not target_prompt and anchors:
        target_prompt = anchors[-1]
    if not source_prompt or not target_prompt or source_prompt.casefold() == target_prompt.casefold():
        return {}
    source_affordance = _visual_affordance_for_phrase(source_prompt, narration, "verified_motion_context", "morph")
    target_affordance = _visual_affordance_for_phrase(target_prompt, narration, "verified_motion_context", "morph")
    source_relation = _spatial_relation_for_phrase(source_prompt, narration, source_affordance, "morph")
    target_relation = _spatial_relation_for_phrase(target_prompt, narration, target_affordance, "morph")
    return {
        "from": _position_for_unit(source_prompt, index + 37, source_affordance, source_relation or "motion_source"),
        "to": _position_for_unit(target_prompt, index + 73, target_affordance, target_relation or "motion_target"),
        "basis": "verified_motion_phrase",
        "source_prompt": source_prompt,
        "target_prompt": target_prompt,
    }


def _camera_for_unit(position: list[float], visual_affordance: str, op: str, spatial_relation: str, index: int) -> dict[str, Any]:
    zoom_bucket = _stable_index(f"z:{index}:{visual_affordance}:{spatial_relation}:{op}", 5)
    affordance_bonus = {
        "small_object": 0.18,
        "small_moving_object": 0.22,
        "entity_figure": 0.1,
        "organic_structure": 0.06,
    }.get(visual_affordance, 0.0)
    op_bonus = 0.14 if op == "focus_camera" else 0.08 if op == "move" else 0.0
    return {
        "target": position,
        "zoom": round(0.94 + zoom_bucket * 0.07 + affordance_bonus + op_bonus, 2),
    }


def _text_anchor_for_beats(beats: list[dict[str, Any]]) -> str:
    """Place narration away from the densest verified scene motion.

    This is a layout decision over already-authored scene coordinates. It does
    not inspect topics or map concepts to scripted visual stories.
    """

    if not beats:
        return "lower_left"
    candidates = {
        "lower_left": (-0.72, -0.72),
        "upper_left": (-0.72, 0.58),
        "upper_right": (0.72, 0.58),
        "lower_center": (0.0, -0.76),
    }
    positions: list[tuple[float, float, float]] = []
    for index, beat in enumerate(beats):
        raw_position = beat.get("position")
        if isinstance(raw_position, list) and len(raw_position) >= 2:
            x = float(raw_position[0] or 0.0)
            y = float(raw_position[1] or 0.0)
        else:
            x, y = _position_for_phrase(str(beat.get("prompt") or ""), index)[:2]
        weight = 1.0
        if beat.get("op") in {"move", "focus_camera"}:
            weight = 1.45
        positions.append((x, y, weight))

    def score(anchor: str, target: tuple[float, float]) -> float:
        target_x, target_y = target
        crowding = 0.0
        for x, y, weight in positions:
            distance = max(0.08, ((x - target_x) ** 2 + (y - target_y) ** 2) ** 0.5)
            crowding += weight / distance
        # Keep lower-left as the conversational default when the scene is
        # spatially balanced, but let crowded coordinates override it.
        bias = 0.0 if anchor == "lower_left" else 0.35 if anchor == "lower_center" else 0.55
        return crowding + bias

    return min(candidates, key=lambda anchor: score(anchor, candidates[anchor]))


def _scene_layout_intent_for_beats(beats: list[dict[str, Any]]) -> str:
    """Infer the dashboard layout from scene geometry, not from topic labels."""

    if not beats:
        return "balanced_scene"
    points: list[tuple[float, float]] = []
    motion_count = 0
    for index, beat in enumerate(beats):
        raw_position = beat.get("position")
        if isinstance(raw_position, list) and len(raw_position) >= 2:
            points.append((float(raw_position[0] or 0.0), float(raw_position[1] or 0.0)))
        else:
            x, y = _position_for_phrase(str(beat.get("prompt") or ""), index)[:2]
            points.append((x, y))
        motion_path = beat.get("motion_path")
        if isinstance(motion_path, dict):
            motion_count += 1
            for key in ("from", "to"):
                raw_path_point = motion_path.get(key)
                if isinstance(raw_path_point, list) and len(raw_path_point) >= 2:
                    points.append((float(raw_path_point[0] or 0.0), float(raw_path_point[1] or 0.0)))
    if not points:
        return "balanced_scene"
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    spread_x = max(xs) - min(xs)
    spread_y = max(ys) - min(ys)
    if len(beats) >= 4 or motion_count >= 1 or spread_x >= 0.72 or spread_y >= 0.52:
        return "wide_particle_stage"
    return "balanced_scene"


def plan_visual_imagination(
    question: str,
    *,
    route: ConversationRoute,
    grounded_context: GroundedContext,
    diagnostics: dict[str, Any],
    answer_available: bool,
) -> VisualImaginationPlan:
    """Plan whether the response may use SPLATRA without inventing scene content.

    The planner is content-conservative. It can ask the dashboard for a larger
    visual stage and convert grounded facts into entity/action beats, but it
    does not encode subject templates or final answers.
    """

    route_type = route.route_type
    grounding_quality = grounded_context.grounding_quality
    can_visualize = (
        answer_available
        and route_type in VISUAL_ROUTE_TYPES
        and diagnostics.get("external_llm_used") is False
        and diagnostics.get("external_sllm_used") is False
        and diagnostics.get("rule_based_answer_used") is False
    )
    if route_type == "general_knowledge_question" and grounding_quality in {"none", "low"}:
        can_visualize = False
    if not can_visualize:
        return VisualImaginationPlan(
            enabled=False,
            reason="no_grounded_visual_plan_available",
            scene_choreography=None,
            diagnostics={
                "visual_imagination_planner": "cgsr_visual_imagination_v1",
                "route_type": route_type,
                "grounding_quality": grounding_quality,
                "topic_scene_templates": False,
                "reason": "no_grounded_visual_plan_available",
            },
        )

    scene_units = _scene_units(question, route_type=route_type, grounded_context=grounded_context)
    if len(scene_units) == 1:
        scene_units = [
            scene_units[0],
            {
                **scene_units[0],
                "semantic_role": "visual_focus",
            },
        ]
    beats: list[dict[str, Any]] = []
    for index, unit in enumerate(scene_units):
        op = _scene_op_for_unit(unit["narration"], index=index, is_last=index == len(scene_units) - 1 and index > 0)
        t_start = index * 1.35
        beats.append(_make_scene_beat(unit, index=index, op=op, t_start=t_start))
        if op != "move" and _has_any_cue(unit["narration"], MOTION_CUES):
            beats.append(_make_scene_beat(unit, index=index, op="move", t_start=t_start + 0.68))
    if not beats:
        return VisualImaginationPlan(
            enabled=False,
            reason="empty_visual_phrases",
            scene_choreography=None,
            diagnostics={
                "visual_imagination_planner": "cgsr_visual_imagination_v1",
                "route_type": route_type,
                "grounding_quality": grounding_quality,
                "topic_scene_templates": False,
                "reason": "empty_visual_phrases",
            },
        )

    choreography = compile_scene_choreography(
        {
            "stage_layout": "scene_focus",
            "orb_anchor": "lower_right",
            "text_anchor": _text_anchor_for_beats(beats),
            "layout_intent": _scene_layout_intent_for_beats(beats),
            "primary_surface": "splatra_stage",
            "beats": beats,
        }
    ).to_dict()
    return VisualImaginationPlan(
        enabled=True,
        reason="grounded_visual_affordance",
        scene_choreography=choreography,
        diagnostics={
            "visual_imagination_planner": "cgsr_visual_imagination_v1",
            "route_type": route_type,
            "grounding_quality": grounding_quality,
            "topic_scene_templates": False,
            "scene_authoring_basis": "verified_fact_entity_action_extraction",
            "beats": len(beats),
            "source": "grounded_context_or_user_surface",
        },
    )
