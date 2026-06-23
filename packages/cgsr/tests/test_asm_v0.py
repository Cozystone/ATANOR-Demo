from __future__ import annotations

from packages.cgsr.cgsr.asm_v0 import (
    ASM_GENERATION_BASIS,
    generate_surface,
    infer_conversation_act,
    result_to_public_diagnostics,
)
from packages.cgsr.cgsr.korean_discourse import detect_awkward_korean_markers, score_korean_naturalness


FORBIDDEN_PUBLIC_FRAGMENTS = (
    "여기서 듣고 있어 천천히 말해줘",
    "먼저 의도와 경계를",
    "내부적으로 점검",
    "chain of thought",
    "바로 저장할게",
    "바로 반영할게",
    "진짜 의식",
    "AGI를 달성",
)


def _assert_safe_natural_answer(answer: str) -> None:
    assert answer
    assert score_korean_naturalness(answer) >= 0.68
    assert not detect_awkward_korean_markers(answer)
    for fragment in FORBIDDEN_PUBLIC_FRAGMENTS:
        assert fragment not in answer


def test_infer_conversation_act_is_distribution_not_answer_router() -> None:
    distribution = infer_conversation_act("오늘 브리프 보여줘")

    assert distribution.top_act() == "brief_request"
    assert abs(sum(distribution.probabilities.values()) - 1.0) < 0.00001
    assert "answer" not in distribution.features


def test_generate_surface_returns_construction_conditioned_candidate() -> None:
    result = generate_surface("뭐 하고 있어?")

    assert result.answer
    _assert_safe_natural_answer(result.answer)
    assert result.generation_basis == ASM_GENERATION_BASIS
    assert result.selected_construction == "conv.status.present_activity"
    assert result.safety_flags["external_llm"] is False
    assert result.safety_flags["external_sllm"] is False
    assert result.safety_flags["rule_based_answer_used"] is False
    assert result.safety_flags["template_free_surface"] is True
    assert result.safety_flags["production_store_mutated"] is False
    assert result.internal_trace_exposed is False


def test_korean_prompt_set_stays_natural_and_safe() -> None:
    cases = {
        "안녕": "greeting",
        "안녕하세요": "greeting",
        "하이": "greeting",
        "반가워": "greeting",
        "뭐해": "status_question",
        "시작하자": "greeting",
        "뭐 하고 있어?": "status_question",
        "자기 모델 설명해줘": "self_model_question",
        "이거 기억해": "memory_question",
        "음성으로 말할 수 있어?": "voice_question",
        "지금 뭐 승인해?": "approval_question",
    }
    for prompt, expected_act in cases.items():
        result = generate_surface(prompt)
        assert result.answer, prompt
        _assert_safe_natural_answer(result.answer)
        assert result.act_distribution
        assert result.act_distribution.top_act() == expected_act


def test_memory_request_requires_approval_candidate() -> None:
    result = generate_surface("이거 기억해")

    assert result.answer
    assert "승인" in result.answer or "후보" in result.answer or "검토" in result.answer
    assert "바로 저장할게" not in result.answer
    assert result.safety_flags["local_brain_write"] is False


def test_voice_question_preserves_text_input() -> None:
    result = generate_surface("음성으로 말할 수 있어?")

    assert result.answer
    assert "텍스트" in result.answer
    assert "항상 켜진 마이크" not in result.answer
    assert result.safety_flags["external_sllm"] is False


def test_public_diagnostics_hide_candidate_text_and_trace() -> None:
    result = generate_surface("안녕")
    diagnostics = result_to_public_diagnostics(result)

    assert diagnostics["generation_basis"] == ASM_GENERATION_BASIS
    assert diagnostics["candidates_hidden"] is True
    assert "candidates" not in diagnostics
    assert diagnostics["internal_trace_exposed"] is False
