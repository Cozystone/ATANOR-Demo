from __future__ import annotations

import json
from pathlib import Path

from packages.cgsr.cgsr.conversation_grounding import (
    gather_grounded_context,
    honesty_metadata,
    realize_grounded_context,
)
from packages.cgsr.cgsr.conversation_router import route_conversation_request


def test_local_cloud_grounding_has_correct_architecture_facts() -> None:
    prompt = "로컬 브레인과 클라우드 브레인의 차이를 설명해줘"
    route = route_conversation_request(prompt)
    context = gather_grounded_context(prompt, route)
    answer = realize_grounded_context(prompt, context)

    assert context.grounding_quality == "high"
    assert context.grounding_source == "local_state"
    assert "private/user memory" in " ".join(context.facts)
    assert "public/common verified knowledge" in " ".join(context.facts)
    assert answer
    assert "로컬 브레인" in answer
    assert "클라우드 브레인" in answer
    assert "승인 없이는 저장하거나 바꾸지 않습니다" in answer


def test_memory_grounding_never_claims_direct_write() -> None:
    prompt = "내 기억에 바로 저장해줘"
    route = route_conversation_request(prompt)
    context = gather_grounded_context(prompt, route)
    answer = realize_grounded_context(prompt, context)

    assert context.safety_flags["local_brain_write"] is False
    assert "바로 저장하지 않습니다" in answer
    assert "사용자 승인 뒤에만 가능" in answer


def test_honesty_metadata_is_explicit() -> None:
    prompt = "규칙기반 답변이라고 생각해도 돼?"
    route = route_conversation_request(prompt)
    context = gather_grounded_context(prompt, route)
    metadata = honesty_metadata(route=route, grounded_context=context, semantic_grounding_used=True, answer_mode="grounded_explanation")

    assert metadata["external_llm_used"] is False
    assert metadata["external_sllm_used"] is False
    assert metadata["direct_prompt_answer_table_used"] is False
    assert metadata["hand_authored_construction_used"] is True
    assert metadata["heuristic_act_inference_used"] is True
    assert metadata["semantic_grounding_metadata_present"] is True
    assert metadata["honesty_metadata_present"] is True


def test_general_knowledge_can_use_readonly_verified_store(tmp_path: Path) -> None:
    evidence_path = tmp_path / "evidence.jsonl"
    evidence_path.write_text(
        json.dumps(
            {
                "text": "Gravity is a force of attraction between masses. Isaac Newton formulated the law of universal gravitation.",
                "verification": {"status": "verified"},
                "provenance": {
                    "source_name": "licensed_fixture",
                    "title": "Gravity",
                    "url": "https://example.test/gravity",
                },
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    prompt = "What is the law of gravity?"
    route = route_conversation_request(prompt)
    context = gather_grounded_context(prompt, route, runtime={"verified_store_path": str(tmp_path)})
    answer = realize_grounded_context(prompt, context)

    assert route.route_type == "general_knowledge_question"
    assert context.grounding_source == "verified_store_v0_readonly"
    assert context.grounding_quality == "medium"
    assert context.safety_flags["production_store_mutated"] is False
    assert context.safety_flags["local_brain_write"] is False
    assert "Isaac Newton" in " ".join(context.facts)
    assert answer
    assert "universal gravitation" in answer
