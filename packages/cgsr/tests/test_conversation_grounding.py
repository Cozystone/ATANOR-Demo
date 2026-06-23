from __future__ import annotations

from packages.cgsr.cgsr.conversation_grounding import (
    gather_grounded_context,
    honesty_metadata,
    realize_grounded_context,
)
from packages.cgsr.cgsr.conversation_router import route_conversation_request


def test_local_cloud_grounding_has_correct_architecture_facts() -> None:
    route = route_conversation_request("로컬 브레인과 클라우드 브레인의 차이를 설명해줘")
    context = gather_grounded_context("로컬 브레인과 클라우드 브레인의 차이를 설명해줘", route)
    answer = realize_grounded_context("로컬 브레인과 클라우드 브레인의 차이를 설명해줘", context)

    assert context.grounding_quality == "high"
    assert context.grounding_source == "local_state"
    assert "private/user memory" in " ".join(context.facts)
    assert "public/common verified knowledge" in " ".join(context.facts)
    assert answer
    assert "로컬 브레인" in answer
    assert "클라우드 브레인" in answer
    assert "승인 없이는 쓰지 않습니다" in answer


def test_memory_grounding_never_claims_direct_write() -> None:
    route = route_conversation_request("내 기억에 바로 저장해줘")
    context = gather_grounded_context("내 기억에 바로 저장해줘", route)
    answer = realize_grounded_context("내 기억에 바로 저장해줘", context)

    assert context.safety_flags["local_brain_write"] is False
    assert "바로 저장하지는 않습니다" in answer
    assert "승인 뒤에만" in answer


def test_honesty_metadata_is_explicit() -> None:
    route = route_conversation_request("규칙기반 답변 쓰고 있냐?")
    context = gather_grounded_context("규칙기반 답변 쓰고 있냐?", route)
    metadata = honesty_metadata(route=route, grounded_context=context, semantic_grounding_used=True, answer_mode="grounded_explanation")

    assert metadata["external_llm_used"] is False
    assert metadata["external_sllm_used"] is False
    assert metadata["direct_prompt_answer_table_used"] is False
    assert metadata["hand_authored_construction_used"] is True
    assert metadata["heuristic_act_inference_used"] is True
    assert metadata["semantic_grounding_metadata_present"] is True
    assert metadata["honesty_metadata_present"] is True
