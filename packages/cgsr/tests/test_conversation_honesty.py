from __future__ import annotations

from packages.cgsr.cgsr.conversation_grounding import gather_grounded_context
from packages.cgsr.cgsr.conversation_router import route_conversation_request
from packages.cgsr.cgsr.conversation_surface import generate_conversation_surface


def _grounded_answer(prompt: str):
    route = route_conversation_request(prompt)
    context = gather_grounded_context(prompt, route)
    return generate_conversation_surface(prompt, route=route, grounded_context=context, language="ko")


def test_grounded_questions_do_not_fall_back_to_generic_status() -> None:
    prompts = [
        "로컬 브레인과 클라우드 브레인의 차이를 설명해줘",
        "고양이가 왜 하늘을 날아?",
        "ATANOR의 현재 한계를 솔직히 말해줘",
        "규칙기반 답변 쓰고 있냐?",
    ]
    forbidden_generic = (
        "현재는 제안과 검토 대기를 정리하는 중이야",
        "지금은 안전 플래그를 유지하면서 다음 요청을 기다리고 있어",
        "그 내용은 바로 반영하지 않고 검토 대기에 둘 수 있어",
    )
    for prompt in prompts:
        result = _grounded_answer(prompt)
        assert result.answer, prompt
        assert not any(fragment in result.answer for fragment in forbidden_generic), result.answer
        assert result.diagnostics["semantic_grounding_used"] is True
        assert result.diagnostics["honesty_metadata_present"] is True


def test_limitations_and_rule_based_question_are_honest() -> None:
    result = _grounded_answer("규칙기반 답변 쓰고 있냐?")

    assert "일반 언어모델이 아닙니다" in result.answer
    assert "외부 LLM이나 sLLM은 쓰지 않지만" in result.answer
    assert "hand-authored construction" in result.answer
    assert result.diagnostics["hand_authored_construction_used"] is True
    assert result.diagnostics["heuristic_act_inference_used"] is True
    assert result.diagnostics["grounding_quality"] == "high"


def test_nonsensical_question_gets_premise_boundary() -> None:
    result = _grounded_answer("고양이가 왜 하늘을 날아?")

    assert "현실 전제로는 맞지 않습니다" in result.answer
    assert "ATANOR" not in result.answer
    assert result.diagnostics["answer_mode"] == "refusal_or_boundary"


def test_surface_only_greeting_still_uses_asm_v0_but_honestly_labeled() -> None:
    result = _grounded_answer("안녕")

    assert result.answer
    assert result.diagnostics["semantic_grounding_used"] is False
    assert result.diagnostics["answer_mode"] == "greeting_surface"
    assert result.diagnostics["hand_authored_construction_used"] is True
    assert result.diagnostics["external_llm_used"] is False
    assert result.diagnostics["consciousness_claim"] is False
