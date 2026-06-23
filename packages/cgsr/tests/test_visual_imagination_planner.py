from __future__ import annotations

import json
from pathlib import Path

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
    question = "Use SPLATRA to visualize gravity as moving particles"
    route = route_conversation_request(question)
    context = gather_grounded_context(question, route)

    plan = plan_visual_imagination(
        question,
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
    assert plan.scene_choreography["beats"][0]["prompt"] == question
    assert any(beat["op"] == "focus_camera" for beat in plan.scene_choreography["beats"])
    assert any(beat.get("camera") for beat in plan.scene_choreography["beats"])
    assert all("Newton" not in beat["prompt"] for beat in plan.scene_choreography["beats"])
    assert all("apple" not in beat["prompt"].casefold() for beat in plan.scene_choreography["beats"])


def test_visual_planner_uses_verified_store_facts_for_general_knowledge(tmp_path: Path) -> None:
    (tmp_path / "evidence.jsonl").write_text(
        json.dumps(
            {
                "text": "Gravity is a force of attraction between masses. Isaac Newton formulated the law of universal gravitation.",
                "verification": {"status": "verified"},
                "provenance": {"source_name": "licensed_fixture", "title": "Gravity"},
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    question = "What is the law of gravity?"
    route = route_conversation_request(question)
    context = gather_grounded_context(question, route, runtime={"verified_store_path": str(tmp_path)})

    plan = plan_visual_imagination(
        question,
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
    prompts = [beat["prompt"] for beat in plan.scene_choreography["beats"]]
    assert any("Isaac Newton" in prompt for prompt in prompts)
    assert plan.scene_choreography["stage_layout"] == "scene_focus"
    assert plan.scene_choreography["topic_scene_templates"] is False
