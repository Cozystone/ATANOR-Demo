from packages.base_brain.zero_user_answer import answer_with_base_brain


FORBIDDEN = ["Local Brain", "Cloud Brain", "Working Memory", "Q-Cortex", "source_hash", "node_id"]


def test_zero_user_answer_known_prompt_is_clean() -> None:
    result = answer_with_base_brain("쿠버네티스가 뭐야?", language="ko")
    assert result["answer"]
    assert result["semantic_context_count"] > 0
    assert result["surface_candidate_count"] > 0
    assert result["local_user_brain_used"] is False
    assert result["external_llm_used"] is False
    assert result["external_sllm_used"] is False
    assert result["external_web_used"] is False
    assert not any(term in result["answer"] for term in FORBIDDEN)


def test_zero_user_answer_unsupported_question_does_not_hallucinate() -> None:
    result = answer_with_base_brain("오늘 내 동네 비가 올지 알려줘.", language="ko")
    assert "부족" in result["answer"] or "외부" in result["answer"]
    assert result["external_web_used"] is False
