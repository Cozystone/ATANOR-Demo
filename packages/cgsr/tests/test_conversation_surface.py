from __future__ import annotations

from packages.cgsr.cgsr.conversation_surface import generate_conversation_surface
from packages.cgsr.cgsr.korean_discourse import detect_awkward_korean_markers, score_korean_naturalness


def test_conversation_surface_generates_without_external_or_rule_engine() -> None:
    result = generate_conversation_surface("안녕", language="ko")

    assert result.answer
    assert score_korean_naturalness(result.answer) >= 0.68
    assert not detect_awkward_korean_markers(result.answer)
    assert "여기서 듣고 있어 천천히 말해줘" not in result.answer
    assert "먼저 의도와 경계를" not in result.answer
    assert result.diagnostics["generation_basis"] == "local_corpus_construction_transition_model"
    assert result.diagnostics["template_free_surface"] is True
    assert result.diagnostics["external_llm_used"] is False
    assert result.diagnostics["external_sllm_used"] is False
    assert result.diagnostics["rule_based_answer_engine"] is False
    assert result.diagnostics["rule_based_answer_used"] is False
    assert result.diagnostics["local_brain_write"] is False
    assert result.diagnostics["production_store_mutated"] is False
    assert result.diagnostics["candidate_promotion"] is False
    assert result.diagnostics["internal_trace_exposed"] is False


def test_conversation_surface_conditions_on_self_model_construction() -> None:
    result = generate_conversation_surface("지금 자기 모델을 설명해줘", language="ko")

    assert result.answer
    assert result.diagnostics["top_act"] == "self_model_question"
    assert result.diagnostics["selected_construction"] == "conv.self_model.loop"
    assert "진짜 의식" not in result.answer
    assert "AGI" not in result.answer


def test_conversation_surface_keeps_memory_request_in_approval_candidate() -> None:
    result = generate_conversation_surface("이거 기억해", language="ko")

    assert result.answer
    assert result.diagnostics["top_act"] == "memory_question"
    assert result.diagnostics["selected_construction"] == "conv.memory.approval_candidate"
    assert "바로 저장할게" not in result.answer
    assert result.diagnostics["local_brain_write"] is False


def test_conversation_surface_conditions_on_voice_question() -> None:
    result = generate_conversation_surface("음성으로 말할 수 있어?", language="ko")

    assert result.answer
    assert result.diagnostics["top_act"] == "voice_question"
    assert result.diagnostics["selected_construction"] == "conv.voice.optional_text_supported"
    assert "텍스트" in result.answer
