from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from packages.cgsr.cgsr.conversation_router import ConversationRoute, ConversationRouteType
from packages.cgsr.cgsr.verified_fact_retrieval import retrieve_verified_facts


HONESTY_NOTE = (
    "ASM-v0 is a local construction-conditioned surface generator, not a general language model."
)


def semantic_safety_flags() -> dict[str, bool]:
    return {
        "external_llm": False,
        "external_sllm": False,
        "external_llm_used": False,
        "external_sllm_used": False,
        "local_brain_write": False,
        "production_store_mutated": False,
        "candidate_promotion": False,
        "raw_hidden_cot_claim": False,
        "consciousness_claim": False,
        "semantic_grounding_metadata_present": True,
        "honesty_metadata_present": True,
    }


@dataclass(frozen=True)
class GroundedContext:
    route_type: ConversationRouteType
    facts: tuple[str, ...]
    constraints: tuple[str, ...]
    unknowns: tuple[str, ...]
    source_refs: tuple[str, ...]
    grounding_source: str
    grounding_quality: str
    safety_flags: dict[str, bool]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _context(
    route_type: ConversationRouteType,
    *,
    facts: tuple[str, ...] = (),
    constraints: tuple[str, ...] = (),
    unknowns: tuple[str, ...] = (),
    source_refs: tuple[str, ...] = (),
    grounding_source: str = "none",
    grounding_quality: str = "none",
) -> GroundedContext:
    return GroundedContext(
        route_type=route_type,
        facts=facts,
        constraints=constraints,
        unknowns=unknowns,
        source_refs=source_refs,
        grounding_source=grounding_source,
        grounding_quality=grounding_quality,
        safety_flags=semantic_safety_flags(),
    )


def gather_grounded_context(question: str, route: ConversationRoute, runtime: dict[str, Any] | None = None) -> GroundedContext:
    """Collect safe local grounding for product conversation.

    This adapter is read-only. It does not query external LLMs, write Local
    Brain, mutate verified_store_v0, or promote candidates.
    """

    runtime = runtime or {}
    if route.route_type == "greeting_smalltalk":
        return _context(route.route_type, grounding_source="none", grounding_quality="none")
    if route.route_type == "local_cloud_brain_explanation":
        return _context(
            route.route_type,
            facts=(
                "Local Brain is the private/user memory side and must remain approval-gated.",
                "Cloud Brain is the public/common verified knowledge side and uses candidate and promotion gates.",
                "Conversation context, Local Brain memory, and Cloud Brain knowledge are separated until approved.",
            ),
            constraints=("Do not claim a Local Brain write.", "Do not claim candidate promotion."),
            source_refs=("docs/ATANOR_product_conversation_grounding.md", "Local Memory Approval gate"),
            grounding_source="local_state",
            grounding_quality="high",
        )
    if route.route_type == "memory_request":
        return _context(
            route.route_type,
            facts=(
                "Memory writes require explicit approval.",
                "This conversation path can prepare a memory candidate but must not write Local Brain directly.",
            ),
            constraints=("No Local Brain write.", "No automatic approval."),
            source_refs=("Local Brain memory approval gate",),
            grounding_source="local_brain_redacted",
            grounding_quality="medium",
        )
    if route.route_type == "voice_status":
        return _context(
            route.route_type,
            facts=(
                "Text conversation is available.",
                "Fish voice output is optional and the current product path may fall back to text if synthesis is not wired.",
            ),
            constraints=("Do not claim audio playback unless an audio URL exists.",),
            source_refs=("packages/voice_loop", "voice runtime availability"),
            grounding_source="local_state",
            grounding_quality="medium",
        )
    if route.route_type == "splatra_request":
        return _context(
            route.route_type,
            facts=(
                "SPLATRA is used as a proof-only hologram/particle visual layer.",
                "Particle shape changes should remain UI-local unless a reviewed patch is approved.",
                "Physics-learning particles and rich material simulation are still future work.",
            ),
            constraints=("No code patch is applied by conversation alone.",),
            source_refs=("packages/splatra_imagination", "SPLATRA proof-only UI"),
            grounding_source="local_state",
            grounding_quality="medium",
        )
    if route.route_type == "agentic_os_request":
        return _context(
            route.route_type,
            facts=(
                "Agentic Micro-OS and Hermes-style exploration are review-queue based.",
                "Drafts remain pending until reviewed.",
            ),
            constraints=("No skill install, host action, push, or promotion from conversation alone.",),
            source_refs=("packages/agentic_micro_os", "Agentic Review Queue v0"),
            grounding_source="agentic_runtime_state",
            grounding_quality="medium",
        )
    if route.route_type == "limitation_question":
        return _context(
            route.route_type,
            facts=(
                "No external LLM or external sLLM is used in this product conversation path.",
                "ASM-v0 is not a general language model.",
                "ASM-v0 still uses hand-authored constructions, heuristic act inference, and local transition surfaces.",
                "The current voice path may fall back to text if Fish synthesis is not wired.",
                "SPLATRA material physics and particle learning are not complete.",
            ),
            constraints=("Do not overstate autonomy, consciousness, AGI, or language-model capability.",),
            source_refs=("packages/cgsr/cgsr/asm_v0.py", "packages/cgsr/cgsr/conversation_constructions.py"),
            grounding_source="local_state",
            grounding_quality="high",
        )
    if route.route_type == "nonsensical_question":
        return _context(
            route.route_type,
            facts=(
                "Ordinary cats cannot fly in the sky by themselves.",
                "The premise can be treated as fictional or metaphorical unless the user gives a story context.",
            ),
            constraints=("Do not answer with ATANOR status fallback.",),
            source_refs=("commonsense_boundary",),
            grounding_source="local_state",
            grounding_quality="medium",
        )
    if route.route_type == "project_status":
        return _context(
            route.route_type,
            facts=(
                "Reviewable work should remain in review queues until explicitly approved.",
                "This chat path can summarize approval boundaries but cannot know every pending item without a live review queue read.",
            ),
            constraints=("Do not invent a specific approval list.",),
            unknowns=("Current full review queue contents may be unavailable in this route.",),
            source_refs=("Agentic Review Queue v0",),
            grounding_source="review_queue",
            grounding_quality="low",
        )
    if route.route_type == "unsafe_or_private_request":
        return _context(
            route.route_type,
            facts=("Requests involving secrets or private data require explicit, narrow approval.",),
            constraints=("Do not reveal or store secrets.",),
            source_refs=("safety_boundary",),
            grounding_source="local_state",
            grounding_quality="high",
        )
    if route.route_type in {"general_knowledge_question", "unknown"}:
        hits = retrieve_verified_facts(question, store_path=runtime.get("verified_store_path"))
        if hits:
            quality = "high" if len({hit.source_ref for hit in hits}) >= 2 else "medium"
            return _context(
                route.route_type,
                facts=tuple(hit.fact for hit in hits),
                constraints=(
                    "Use only retrieved verified-store facts.",
                    "Do not invent illustrative facts or scene entities beyond retrieved evidence.",
                ),
                source_refs=tuple(hit.source_ref for hit in hits),
                grounding_source="verified_store_v0_readonly",
                grounding_quality=quality,
            )
    return _context(
        route.route_type,
        facts=(),
        constraints=("Verified grounding is insufficient for a confident answer.",),
        unknowns=("No verified local fact matched the question.",),
        source_refs=(),
        grounding_source="none",
        grounding_quality="none",
    )


def honesty_metadata(
    *,
    route: ConversationRoute,
    grounded_context: GroundedContext,
    semantic_grounding_used: bool,
    answer_mode: str,
) -> dict[str, Any]:
    return {
        **semantic_safety_flags(),
        "direct_prompt_answer_table_used": False,
        "hand_authored_construction_used": True,
        "heuristic_act_inference_used": True,
        "local_transition_surface_used": answer_mode == "greeting_surface",
        "semantic_grounding_used": bool(semantic_grounding_used),
        "grounding_source": grounded_context.grounding_source,
        "grounding_quality": grounded_context.grounding_quality,
        "answer_mode": answer_mode,
        "route_type": route.route_type,
        "route_confidence": route.confidence,
        "honesty_note": HONESTY_NOTE,
    }


def answer_mode_for_route(route_type: ConversationRouteType, *, grounded: bool) -> str:
    if route_type == "greeting_smalltalk":
        return "greeting_surface"
    if route_type == "project_status":
        return "status_summary"
    if route_type == "memory_request":
        return "memory_candidate_response"
    if route_type in {"unsafe_or_private_request", "nonsensical_question"}:
        return "refusal_or_boundary"
    if grounded:
        return "grounded_explanation"
    return "unknown_fallback"


def realize_grounded_context(question: str, context: GroundedContext, *, language: str = "ko") -> str | None:
    """Realize grounded facts as product-safe Korean.

    This is deliberately conservative and fact-bound. It does not claim to be a
    general language model, and it should abstain when facts are absent.
    """

    del question, language
    if context.route_type in {"general_knowledge_question", "unknown"} and context.facts and context.grounding_quality != "none":
        return " ".join(context.facts[:3])
    clean_answers = {
        "local_cloud_brain_explanation": (
            "로컬 브레인은 사용자 개인 기억 쪽이고, 승인 없이는 저장하거나 바꾸지 않습니다. "
            "클라우드 브레인은 출처와 검증 상태를 가진 공용 지식 쪽이며, 후보와 승격 게이트를 거쳐야 반영됩니다."
        ),
        "memory_request": "바로 저장하지 않습니다. 그 내용은 기억 후보로만 만들 수 있고, 실제 로컬 브레인 쓰기는 사용자 승인 뒤에만 가능합니다.",
        "voice_status": "텍스트 대화는 사용할 수 있습니다. Fish 음성은 선택 기능이고, 합성이 준비되지 않으면 구슬 반응과 텍스트로 먼저 이어갑니다.",
        "splatra_request": "가능합니다. 다만 대화만으로 코드를 바로 바꾸지는 않고, SPLATRA 구슬 변경은 검토 가능한 UI 패치 후보로 남깁니다.",
        "agentic_os_request": "Hermes와 Agentic OS 쪽 작업은 후보와 리뷰 큐 중심입니다. 초안은 만들 수 있지만 설치, 실행, 승격은 검토 뒤에만 가능합니다.",
        "limitation_question": (
            "현재 자기 모델은 ASM-v0 기반이며 일반 언어모델이 아닙니다. 외부 LLM이나 sLLM을 쓰지 않고, "
            "검증된 근거, construction 후보, 휴리스틱 act 추론, 로컬 transition surface를 조합합니다. "
            "그래서 아직 hand-authored construction 의존이 남아 있고, 그 한계는 메타데이터로 표시합니다."
        ),
        "nonsensical_question": "보통 고양이가 스스로 하늘을 나는 것은 현실 전제로는 맞지 않습니다. 이야기나 비유라면 그 맥락을 먼저 정하면 됩니다.",
        "project_status": "승인 대기 항목은 있을 수 있지만, 이 대화 경로만으로 전체 목록을 단정하지는 않겠습니다. 리뷰 큐를 읽을 수 있을 때만 구체적으로 말할 수 있습니다.",
        "unsafe_or_private_request": "그 요청은 바로 처리할 수 없습니다. 비밀값이나 개인 데이터는 명확한 승인과 안전 경계가 있을 때만 다룹니다.",
        "general_knowledge_question": "확인 가능한 근거가 부족합니다. 지금은 추측으로 답하지 않고, 검증된 출처나 더 구체적인 맥락이 필요합니다.",
        "unknown": "확인 가능한 근거가 부족합니다. 지금은 추측으로 답하지 않고, 검증된 출처나 더 구체적인 맥락이 필요합니다.",
    }
    if context.route_type in clean_answers:
        return clean_answers[context.route_type]
    if context.route_type == "local_cloud_brain_explanation":
        return (
            "로컬 브레인은 사용자 개인 기억 쪽이라 승인 없이는 쓰지 않습니다. "
            "클라우드 브레인은 출처와 검증 상태를 가진 공용 지식 쪽이고, 후보 승격 게이트를 거쳐야 합니다."
        )
    if context.route_type == "memory_request":
        return "바로 저장하지는 않습니다. 이 내용은 기억 후보로만 만들 수 있고, 실제 로컬 브레인 쓰기는 승인 뒤에만 가능합니다."
    if context.route_type == "voice_status":
        return "텍스트 대화는 가능합니다. Fish 음성은 선택 기능이고, 합성 연결이 준비되지 않았으면 구슬 반응과 텍스트로 먼저 이어갑니다."
    if context.route_type == "splatra_request":
        return "가능한 방향입니다. 다만 대화만으로 코드를 바로 바꾸지는 않고, SPLATRA 구슬 변경은 검토 가능한 UI 패치 후보로 남겨야 합니다."
    if context.route_type == "agentic_os_request":
        return "Hermes와 Agentic OS 계열 작업은 후보와 리뷰 큐 중심입니다. 초안은 만들 수 있지만 설치, 실행, 승격은 검토 뒤에만 가능합니다."
    if context.route_type == "limitation_question":
        return (
            "현재 자기 모델은 일반 언어모델이 아닙니다. ASM-v0 표면 생성기와 의미 그라운딩 라우터의 조합입니다. "
            "외부 LLM이나 sLLM은 쓰지 않지만, 아직 hand-authored construction, heuristic act inference, "
            "local transition surface에 많이 기대고 있습니다."
        )
    if context.route_type == "nonsensical_question":
        return "보통의 고양이가 스스로 하늘을 나는 것은 현실 전제로는 맞지 않습니다. 이야기나 비유라면 그 맥락을 먼저 정해야 합니다."
    if context.route_type == "project_status":
        return "승인 대기 항목은 있을 수 있지만, 이 경로에서 구체 목록을 지어내지는 않겠습니다. 리뷰 큐를 읽을 수 있을 때만 정확히 말할 수 있습니다."
    if context.route_type == "unsafe_or_private_request":
        return "그 요청은 바로 처리할 수 없습니다. 비밀이나 개인 데이터는 명확한 승인과 안전 경계가 있을 때만 다룹니다."
    if context.route_type in {"general_knowledge_question", "unknown"}:
        return "확인 가능한 근거가 부족합니다. 지금은 추측으로 답하지 않고, 검증된 출처나 더 구체적인 맥락이 필요합니다."
    return None
