from __future__ import annotations

from packages.cgsr.cgsr.conversation_grounding import gather_grounded_context
from packages.cgsr.cgsr.conversation_router import route_conversation_request
from packages.cgsr.cgsr.visual_imagination_planner import plan_visual_imagination


def test_visual_planner_abstains_without_grounded_general_knowledge() -> None:
    route = route_conversation_request("Explain gravity with a visual scene")
    context = gather_grounded_context("Explain gravity with a visual scene", route)

    plan = plan_visual_imagination(
        "Explain gravity with a visual scene",
        route=route,
        grounded_context=context,
        diagnostics={
            "external_llm_used": False,
            "external_sllm_used": False,
            "rule_based_answer_used": False,
        },
        answer_available=True,
    )

    assert plan.enabled is False
    assert plan.scene_choreography is None
    assert plan.diagnostics["topic_scene_templates"] is False


def test_visual_planner_uses_grounded_phrases_without_topic_templates() -> None:
    route = route_conversation_request("Use SPLATRA to visualize this")
    context = gather_grounded_context("Use SPLATRA to visualize this", route)

    plan = plan_visual_imagination(
        "Use SPLATRA to visualize this",
        route=route,
        grounded_context=context,
        diagnostics={
            "external_llm_used": False,
            "external_sllm_used": False,
            "rule_based_answer_used": False,
        },
        answer_available=True,
    )

    assert plan.enabled is True
    assert plan.scene_choreography is not None
    assert plan.scene_choreography["stage_layout"] == "scene_focus"
    assert plan.scene_choreography["orb_anchor"] == "lower_right"
    assert plan.diagnostics["topic_scene_templates"] is False
    assert plan.scene_choreography["topic_scene_templates"] is False
    assert plan.scene_choreography["beats"]
    assert all("Newton" not in beat["prompt"] for beat in plan.scene_choreography["beats"])
