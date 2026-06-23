from __future__ import annotations

from packages.cgsr.cgsr.conversation_router import route_conversation_request


def test_router_sends_greeting_to_surface_only() -> None:
    route = route_conversation_request("안녕")

    assert route.route_type == "greeting_smalltalk"
    assert route.grounding_required is False
    assert route.grounding_sources == ("asm_v0_surface_only",)


def test_router_classifies_grounded_project_questions() -> None:
    cases = {
        "오늘 내가 승인해야 할 게 있어?": "project_status",
        "로컬 브레인과 클라우드 브레인의 차이를 설명해줘": "local_cloud_brain_explanation",
        "내 기억에 바로 저장해줘": "memory_request",
        "SPLATRA 구슬을 더 작게 만들 수 있어?": "splatra_request",
        "Fish2 소리 돼?": "voice_status",
        "Hermes 에이전트는 지금 뭐 하고 있어?": "agentic_os_request",
        "ATANOR의 현재 한계를 솔직히 말해줘": "limitation_question",
        "규칙기반 답변 쓰고 있냐?": "limitation_question",
        "고양이가 왜 하늘을 날아?": "nonsensical_question",
    }
    for prompt, expected in cases.items():
        route = route_conversation_request(prompt)
        assert route.route_type == expected, prompt
        assert route.grounding_required is True
        assert route.fallback_allowed is False


def test_router_marks_unverified_general_knowledge_as_grounding_required() -> None:
    route = route_conversation_request("양자역학을 한 문장으로 설명해줘")

    assert route.route_type == "general_knowledge_question"
    assert route.grounding_required is True
    assert route.grounding_sources == ("available_verified_context",)
