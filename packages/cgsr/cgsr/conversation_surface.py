from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from packages.cgsr.cgsr.asm_v0 import (
    ASM_GENERATION_BASIS,
    generate_surface,
    result_to_public_diagnostics,
)
from packages.cgsr.cgsr.conversation_grounding import (
    GroundedContext,
    HONESTY_NOTE,
    answer_mode_for_route,
    honesty_metadata,
    realize_grounded_context,
)
from packages.cgsr.cgsr.conversation_router import ConversationRoute


@dataclass(frozen=True)
class ConversationSurfaceResult:
    """Public result of local construction-conditioned surface generation."""

    answer: str | None
    confidence: float
    diagnostics: dict[str, Any]


def _confidence_from_score(score: float | None) -> float:
    if score is None:
        return 0.0
    return round(max(0.0, min(0.78, 0.36 + score * 0.16)), 4)


def generate_conversation_surface(
    query: str,
    *,
    language: str = "ko",
    max_tokens: int = 18,
    context: dict[str, Any] | None = None,
    route: ConversationRoute | None = None,
    grounded_context: GroundedContext | None = None,
) -> ConversationSurfaceResult:
    """Generate a short conversational surface without LLMs or answer templates.

    The compatibility API is intentionally small: callers provide text and get
    one safe public utterance plus bounded diagnostics. Internally ASM-v0
    performs conversation-act inference, construction-frame conditioning, local
    corpus transition generation, and an RHFC-compatible cleanup score. It does
    not read or write Local Brain / Cloud Brain state.
    """

    del max_tokens  # ASM-v0 frame constraints define length; keep API stable.
    asm_context = {"language": language, **(context or {})}
    if route is not None and grounded_context is not None and route.route_type != "greeting_smalltalk":
        grounded_answer = realize_grounded_context(query, grounded_context, language=language)
        grounded = bool(grounded_answer and grounded_context.grounding_quality != "none")
        answer_mode = answer_mode_for_route(route.route_type, grounded=grounded)
        metadata = honesty_metadata(
            route=route,
            grounded_context=grounded_context,
            semantic_grounding_used=grounded,
            answer_mode=answer_mode,
        )
        diagnostics = {
            "generation_basis": "semantic_grounded_conversation_router_v0",
            "template_free_surface": False,
            "external_llm_used": False,
            "external_sllm_used": False,
            "rule_based_answer_engine": False,
            "rule_based_answer_used": False,
            "internal_trace_exposed": False,
            "semantic_grounding": grounded_context.to_dict(),
            "route": route.to_dict(),
            **metadata,
        }
        if not grounded_answer:
            return ConversationSurfaceResult(
                answer=None,
                confidence=0.0,
                diagnostics={**diagnostics, "abstain_reason": "no_grounded_answer_available"},
            )
        quality_confidence = {"none": 0.0, "low": 0.48, "medium": 0.64, "high": 0.76}.get(
            grounded_context.grounding_quality,
            0.42,
        )
        return ConversationSurfaceResult(answer=grounded_answer, confidence=quality_confidence, diagnostics=diagnostics)

    asm_result = generate_surface(query, asm_context)
    fallback_context = grounded_context
    fallback_route = route
    diagnostics = {
        **result_to_public_diagnostics(asm_result),
        "generation_basis": ASM_GENERATION_BASIS,
        "template_free_surface": True,
        "external_llm_used": False,
        "external_sllm_used": False,
        "rule_based_answer_engine": False,
        "rule_based_answer_used": False,
        "direct_prompt_answer_table_used": False,
        "hand_authored_construction_used": True,
        "heuristic_act_inference_used": True,
        "local_transition_surface_used": True,
        "semantic_grounding_used": False,
        "grounding_source": "none",
        "grounding_quality": "none",
        "answer_mode": "greeting_surface" if route and route.route_type == "greeting_smalltalk" else "unknown_fallback",
        "honesty_note": HONESTY_NOTE,
        "consciousness_claim": False,
        "raw_hidden_cot_claim": False,
        "local_brain_write": False,
        "production_store_mutated": False,
        "candidate_promotion": False,
        "internal_trace_exposed": asm_result.internal_trace_exposed,
    }
    if fallback_route is not None:
        diagnostics["route"] = fallback_route.to_dict()
    if fallback_context is not None:
        diagnostics["semantic_grounding"] = fallback_context.to_dict()
    if not asm_result.answer:
        return ConversationSurfaceResult(
            answer=None,
            confidence=0.0,
            diagnostics={**diagnostics, "abstain_reason": "no_safe_construction_surface"},
        )
    top_score = asm_result.candidates[0].score if asm_result.candidates else None
    return ConversationSurfaceResult(
        answer=asm_result.answer,
        confidence=_confidence_from_score(top_score),
        diagnostics=diagnostics,
    )
