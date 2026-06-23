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
ANCHOR_STOPWORDS = {
    "therefore",
    "however",
    "because",
    "first",
    "second",
    "third",
    "따라서",
    "그러나",
    "그리고",
    "하지만",
    "또한",
    "첫",
    "번째",
    "단계",
    "항",
    "기존",
    "대한",
    "대해",
    "것",
    "이는",
    "그",
    "중",
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


def _fact_units(fact: str) -> list[str]:
    """Split a verified fact into scene-sized units without topic templates."""

    clean = _clean_phrase(fact, limit=420)
    if not clean:
        return []
    parts = re.split(r"(?<=[.!?。！？])\s+|[;；]\s*", clean)
    units = [_clean_phrase(part, limit=160) for part in parts if _clean_phrase(part, limit=160)]
    return units[:4] or [clean[:160]]


def _entity_spans(text: str) -> list[str]:
    """Extract text-local visual anchors; never map topics to invented props."""

    spans: list[str] = []
    for match in re.finditer(r"\b(?:[A-Z][a-z]+|[A-Z]{2,})(?:\s+(?:[A-Z][a-z]+|[A-Z]{2,})){0,3}\b", text):
        spans.append(match.group(0))
    for match in re.finditer(r"[가-힣A-Za-z0-9][가-힣A-Za-z0-9·\-]{2,}(?:\s+[가-힣A-Za-z0-9][가-힣A-Za-z0-9·\-]{2,}){0,2}", text):
        candidate = match.group(0).strip()
        if len(candidate) >= 3:
            spans.append(candidate)

    cleaned: list[str] = []
    for span in spans:
        tokens = [
            re.sub(r"(으로서|으로써|으로|에서|에게|에는|이다|입니다|하고|까지|부터|처럼|보다|이며|이나|거나|와|과|은|는|이|가|을|를|의|에|로)$", "", token)
            for token in span.split()
        ]
        tokens = [token for token in tokens if token and token.casefold() not in ANCHOR_STOPWORDS]
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
    return deduped[:3]


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
            prompt = anchors[0] if anchors else unit
            units.append(
                {
                    "prompt": prompt,
                    "narration": _clean_phrase(unit, limit=180),
                    "source_fact": clean_fact,
                    "semantic_role": "verified_fact_unit",
                }
            )

    if not units:
        for phrase in _visual_phrases(question, route_type=route_type, grounded_context=grounded_context):
            units.append(
                {
                    "prompt": phrase,
                    "narration": _narration_for_phrase(phrase),
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
    return deduped[:5]


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


def _narration_for_phrase(phrase: str) -> str:
    return _clean_phrase(phrase, limit=180)


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
        phrase = unit["prompt"]
        op = "spawn_object" if index == 0 else "morph"
        if index == len(scene_units) - 1 and index > 0:
            op = "focus_camera"
        object_seed = f"{index}:{unit['prompt']}:{unit['narration']}"
        beats.append(
            {
                "op": op,
                "prompt": phrase,
                "narration": unit["narration"],
                "object_id": f"grounded_visual_{index}_{_stable_index(object_seed, 100000):05d}",
                "semantic_role": unit["semantic_role"],
                "source_fact": unit["source_fact"],
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
            "text_anchor": "lower_left",
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
