from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from typing import Any

from packages.cgsr.cgsr.conversation_grounding import GroundedContext
from packages.cgsr.cgsr.conversation_router import ConversationRoute
from packages.splatra_imagination import ARCHETYPES, compile_scene_choreography
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


def _visual_phrases(question: str, *, route_type: str, grounded_context: GroundedContext) -> list[str]:
    phrases: list[str] = []
    clean_question = _clean_phrase(question)
    if route_type == "splatra_request" and clean_question:
        phrases.append(clean_question)
    for fact in grounded_context.facts:
        clean = _clean_phrase(fact)
        if clean:
            phrases.append(clean)
    if not phrases:
        if clean_question:
            phrases.append(clean_question)
    deduped: list[str] = []
    seen: set[str] = set()
    for phrase in phrases:
        key = phrase.casefold()
        if key not in seen:
            seen.add(key)
            deduped.append(phrase)
    return deduped[:4]


def _archetype_for_phrase(phrase: str, index: int) -> Archetype:
    # This is deliberately not a topic dictionary. It only chooses a bounded
    # visual carrier deterministically so the scene planner does not smuggle in
    # prompt-specific templates such as "gravity -> Newton/apple/tree".
    return PRODUCT_ARCHETYPES[_stable_index(f"{index}:{phrase}", len(PRODUCT_ARCHETYPES))]


def _position_for_phrase(phrase: str, index: int) -> list[float]:
    # Phrase-dependent placement gives the renderer room to move without
    # smuggling in topic templates. The same grounded phrase always lands in
    # the same bounded area, but there is no dictionary such as gravity->tree.
    x_bucket = _stable_index(f"x:{index}:{phrase}", 9) - 4
    y_bucket = _stable_index(f"y:{index}:{phrase}", 7) - 3
    return [round(x_bucket * 0.22, 2), round(y_bucket * 0.16, 2), 0.0]


def _camera_for_phrase(phrase: str, index: int) -> dict[str, Any]:
    zoom_bucket = _stable_index(f"z:{index}:{phrase}", 5)
    return {
        "target": _position_for_phrase(phrase, index),
        "zoom": round(0.94 + zoom_bucket * 0.07, 2),
    }


def plan_visual_imagination(
    question: str,
    *,
    route: ConversationRoute,
    grounded_context: GroundedContext,
    diagnostics: dict[str, Any],
    answer_available: bool,
) -> VisualImaginationPlan:
    """Plan whether the response may use SPLATRA without inventing scene content.

    The planner is intentionally content-conservative. It can ask the dashboard
    for a larger visual stage and convert grounded phrases into generic
    SPLATRA beats, but it does not encode subject templates or final answers.
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
                "visual_imagination_planner": "cgsr_visual_imagination_v0",
                "route_type": route_type,
                "grounding_quality": grounding_quality,
                "topic_scene_templates": False,
                "reason": "no_grounded_visual_plan_available",
            },
        )

    phrases = _visual_phrases(question, route_type=route_type, grounded_context=grounded_context)
    beats: list[dict[str, Any]] = []
    for index, phrase in enumerate(phrases[:3]):
        op = "spawn_object" if index == 0 else "morph"
        if index == min(2, len(phrases[:3]) - 1) and index > 0:
            op = "focus_camera"
        beats.append(
            {
                "op": op,
                "prompt": phrase,
                "object_id": f"grounded_visual_{index}",
                "archetype": _archetype_for_phrase(phrase, index),
                "t_start": round(index * 1.35, 2),
                "duration": 1.25,
                "position": _position_for_phrase(phrase, index),
                "camera": _camera_for_phrase(phrase, index) if op == "focus_camera" else {},
            }
        )
    if not beats:
        return VisualImaginationPlan(
            enabled=False,
            reason="empty_visual_phrases",
            scene_choreography=None,
            diagnostics={
                "visual_imagination_planner": "cgsr_visual_imagination_v0",
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
            "primary_surface": "splatra_stage",
            "beats": beats,
        }
    ).to_dict()
    return VisualImaginationPlan(
        enabled=True,
        reason="grounded_visual_affordance",
        scene_choreography=choreography,
        diagnostics={
            "visual_imagination_planner": "cgsr_visual_imagination_v0",
            "route_type": route_type,
            "grounding_quality": grounding_quality,
            "topic_scene_templates": False,
            "beats": len(beats),
            "source": "grounded_context_or_user_surface",
        },
    )
