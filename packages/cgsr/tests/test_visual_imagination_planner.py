from __future__ import annotations

import json
from pathlib import Path

from packages.cgsr.cgsr.conversation_grounding import gather_grounded_context
from packages.cgsr.cgsr.conversation_router import route_conversation_request
from packages.cgsr.cgsr.visual_imagination_planner import plan_visual_imagination


TEXT_ANCHORS = {"upper_left", "lower_left", "upper_right", "lower_center"}


def _plan(question: str, store_path: Path | None = None):
    route = route_conversation_request(question)
    runtime = {"verified_store_path": str(store_path)} if store_path else None
    context = gather_grounded_context(question, route, runtime=runtime)
    return plan_visual_imagination(
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


def test_visual_planner_abstains_without_grounded_general_knowledge() -> None:
    plan = _plan("Explain gravity with a visual scene")

    assert plan.enabled is False
    assert plan.scene_choreography is None
    assert plan.diagnostics["topic_scene_templates"] is False


def test_visual_planner_uses_grounded_phrases_without_topic_templates() -> None:
    question = "Use SPLATRA to visualize gravity as moving particles"
    plan = _plan(question)

    assert plan.enabled is True
    assert plan.scene_choreography is not None
    assert plan.scene_choreography["stage_layout"] == "scene_focus"
    assert plan.scene_choreography["orb_anchor"] == "lower_right"
    assert plan.scene_choreography["text_anchor"] in TEXT_ANCHORS
    assert plan.scene_choreography["layout_intent"] in {"balanced_scene", "wide_particle_stage"}
    assert plan.scene_choreography["scene_extent"]["beat_count"] == len(plan.scene_choreography["beats"])
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
    plan = _plan("What is the law of gravity?", tmp_path)

    assert plan.enabled is True
    assert plan.scene_choreography is not None
    prompts = [beat["prompt"] for beat in plan.scene_choreography["beats"]]
    assert any("Isaac Newton" in prompt for prompt in prompts)
    assert any("Isaac Newton" in beat["narration"] for beat in plan.scene_choreography["beats"])
    assert len({beat["object_id"] for beat in plan.scene_choreography["beats"]}) >= 2
    assert all(beat["semantic_role"] for beat in plan.scene_choreography["beats"])
    assert any("Gravity is a force" in beat["source_fact"] for beat in plan.scene_choreography["beats"])
    assert all("apple" not in beat["prompt"].casefold() for beat in plan.scene_choreography["beats"])
    assert plan.scene_choreography["stage_layout"] == "scene_focus"
    assert plan.scene_choreography["text_anchor"] in TEXT_ANCHORS
    assert plan.scene_choreography["layout_intent"] in {"balanced_scene", "wide_particle_stage"}
    assert plan.scene_choreography["topic_scene_templates"] is False
    assert plan.diagnostics["scene_authoring_basis"] == "verified_fact_entity_action_extraction"


def test_visual_planner_uses_contentful_korean_scene_anchors(tmp_path: Path) -> None:
    (tmp_path / "evidence.jsonl").write_text(
        json.dumps(
            {
                "text": "첫 번째 항은 뉴턴 중력의 힘을 나타내며, 역제곱 법칙으로 기술된다. 따라서 일반 상대론은 뉴턴의 중력 법칙과 비교된다.",
                "verification": {"status": "verified"},
                "provenance": {"source_name": "licensed_fixture", "title": "중력"},
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    plan = _plan("중력의 법칙에 대해 설명해줘", tmp_path)

    assert plan.enabled is True
    assert plan.scene_choreography is not None
    prompts = [beat["prompt"] for beat in plan.scene_choreography["beats"]]
    assert all(prompt not in {"따라서", "단계", "첫 번째"} for prompt in prompts)
    assert any("뉴턴" in prompt or "중력" in prompt for prompt in prompts)


def test_visual_planner_only_adds_motion_when_verified_fact_contains_motion(tmp_path: Path) -> None:
    (tmp_path / "evidence.jsonl").write_text(
        json.dumps(
            {
                "text": "아이작 뉴턴은 중력 법칙과 관련해 사과가 나무에서 떨어지는 장면을 관찰했다. 그 사건은 물체가 지구 쪽으로 끌리는 현상을 설명하는 단서가 되었다.",
                "verification": {"status": "verified"},
                "provenance": {"source_name": "licensed_fixture", "title": "뉴턴"},
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    plan = _plan("중력의 법칙에 대해 설명해줘", tmp_path)

    assert plan.enabled is True
    assert plan.scene_choreography is not None
    beats = plan.scene_choreography["beats"]
    assert any(beat["op"] == "move" for beat in beats)
    assert any("사과" in beat["narration"] for beat in beats)
    assert any("떨어지는" in beat["narration"] for beat in beats)
    assert all(beat["source_fact"] for beat in beats)


def test_visual_planner_extracts_korean_figure_tree_apple_motion_without_topic_script(tmp_path: Path) -> None:
    (tmp_path / "evidence.jsonl").write_text(
        json.dumps(
            {
                "text": (
                    "아이작 뉴턴은 중력 법칙과 관련해 사과가 나무에서 떨어지는 장면을 관찰했다. "
                    "어느 날 뉴턴이 사과나무 밑에 앉아 있었고 사과가 뉴턴의 머리 위로 떨어졌다."
                ),
                "verification": {"status": "verified"},
                "provenance": {"source_name": "licensed_fixture", "title": "뉴턴 사과나무"},
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    plan = _plan("중력의 법칙에 대해 설명해줘", tmp_path)

    assert plan.enabled is True
    assert plan.scene_choreography is not None
    beats = plan.scene_choreography["beats"]
    assert any("뉴턴" in beat["prompt"] and beat["visual_affordance"] == "entity_figure" for beat in beats)
    assert any("나무" in beat["prompt"] and beat["visual_affordance"] == "organic_structure" for beat in beats)
    assert any(beat["prompt"] == "사과" and beat["visual_affordance"] == "small_moving_object" for beat in beats)
    assert any("뉴턴" in beat["prompt"] and beat["spatial_relation"] == "under_target" for beat in beats)
    apple_motion = next(beat for beat in beats if beat["prompt"] == "사과" and beat.get("motion_path"))
    assert "나무" in apple_motion["motion_path"]["source_prompt"]
    assert "뉴턴" in apple_motion["motion_path"]["target_prompt"]
    assert apple_motion["motion_path"]["from"][1] > apple_motion["motion_path"]["to"][1]
    assert plan.scene_choreography["topic_scene_templates"] is False
    assert plan.diagnostics["scene_authoring_basis"] == "verified_fact_entity_action_extraction"


def test_visual_planner_text_anchor_is_scene_position_dependent(tmp_path: Path) -> None:
    (tmp_path / "evidence.jsonl").write_text(
        json.dumps(
            {
                "text": "A river moves through a lower valley. The falling water shifts from the left channel to the center basin.",
                "verification": {"status": "verified"},
                "provenance": {"source_name": "licensed_fixture", "title": "River"},
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    plan = _plan("Explain how the water moves", tmp_path)

    assert plan.enabled is True
    assert plan.scene_choreography is not None
    assert plan.scene_choreography["text_anchor"] in TEXT_ANCHORS
    assert plan.scene_choreography["text_anchor"] != "auto"


def test_visual_planner_decomposes_verified_motion_scene_without_topic_script(tmp_path: Path) -> None:
    (tmp_path / "evidence.jsonl").write_text(
        json.dumps(
            {
                "text": (
                    "Gravity is associated with Isaac Newton. "
                    "Isaac Newton sat under an apple tree. "
                    "An apple fell from the tree toward Newton, and the event helped explain gravitational attraction."
                ),
                "verification": {"status": "verified"},
                "provenance": {"source_name": "licensed_fixture", "title": "Newton apple tree"},
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    plan = _plan("What is gravity?", tmp_path)

    assert plan.enabled is True
    assert plan.scene_choreography is not None
    beats = plan.scene_choreography["beats"]
    prompts = [beat["prompt"] for beat in beats]
    starts = [beat["t_start"] for beat in beats]
    assert starts == sorted(starts)
    assert all(beat["duration"] >= 1.05 for beat in beats)
    assert len({beat["duration"] for beat in beats}) >= 2
    assert any(prompt == "Isaac Newton" for prompt in prompts)
    assert any(prompt == "apple" for prompt in prompts)
    assert any(prompt == "tree" for prompt in prompts)
    assert any("apple fell" in prompt for prompt in prompts)
    assert any(beat["visual_affordance"] == "entity_figure" and beat["archetype"] == "creature" for beat in beats if "Isaac Newton" in beat["prompt"])
    assert any(beat["visual_affordance"] == "organic_structure" and beat["archetype"] == "tree" for beat in beats if beat["prompt"] == "tree")
    assert any(beat["visual_affordance"] == "small_moving_object" and beat["archetype"] == "machine_core" for beat in beats if "apple fell" in beat["prompt"])
    assert all(beat["archetype"] == "abstract_memory_cloud" for beat in beats if beat["visual_affordance"] == "concept_cloud")
    seated_newton = next(beat for beat in beats if beat["prompt"] == "Isaac Newton" and beat["spatial_relation"] == "under_target")
    tree_anchor = next(beat for beat in beats if beat["prompt"] == "tree" and beat["spatial_relation"] in {"over_anchor", "motion_source"})
    assert seated_newton["position"][1] < tree_anchor["position"][1]
    assert any(beat["op"] == "move" and "apple fell" in beat["prompt"] for beat in beats)
    assert all("speech_cue" in beat for beat in beats)
    assert all("speech_cue_basis" in beat for beat in beats)
    assert all("scene_group_id" in beat for beat in beats)
    assert all("scene_group_role" in beat for beat in beats)
    assert all(beat["speech_cue"] is True for beat in beats if beat["semantic_role"] in {"verified_entity_relation", "verified_motion_event"})
    assert all(beat["speech_cue"] is False for beat in beats if beat["semantic_role"] in {"verified_entity_anchor", "verified_motion_anchor", "verified_motion_context"})
    assert any(beat["speech_cue_basis"] == "visual_anchor_only" and beat["prompt"] == "tree" for beat in beats)
    assert any(beat["speech_cue_basis"] == "verified_evidence_unit" and "apple fell" in beat["prompt"] for beat in beats)
    speech_groups = {beat["scene_group_id"] for beat in beats if beat["scene_group_role"] == "speech_unit"}
    visual_anchor_groups = {beat["scene_group_id"] for beat in beats if beat["scene_group_role"] == "visual_anchor"}
    assert speech_groups
    assert visual_anchor_groups <= speech_groups
    tree_group = next(beat["scene_group_id"] for beat in beats if beat["prompt"] == "tree")
    assert any(beat["scene_group_id"] == tree_group and beat["scene_group_role"] == "speech_unit" for beat in beats)
    motion_beats = [beat for beat in beats if beat["op"] == "move" and beat.get("motion_path")]
    assert motion_beats
    assert all(beat["motion_path"]["basis"] == "verified_motion_phrase" for beat in motion_beats)
    assert any(beat["motion_path"].get("source_prompt") for beat in motion_beats)
    assert any(beat["motion_path"].get("target_prompt") for beat in motion_beats)
    apple_motion = next(beat for beat in motion_beats if "apple fell" in beat["prompt"])
    assert apple_motion["motion_path"]["from"][1] > apple_motion["motion_path"]["to"][1]
    assert tuple(apple_motion["camera"]["target"]) == tuple(apple_motion["position"])
    assert apple_motion["camera"]["zoom"] > 1.0
    focus_beats = [beat for beat in beats if beat["op"] == "focus_camera"]
    assert focus_beats
    assert all(tuple(beat["camera"]["target"]) == tuple(beat["position"]) for beat in focus_beats)
    assert plan.scene_choreography["layout_intent"] == "wide_particle_stage"
    assert plan.scene_choreography["scene_extent"]["motion_count"] >= 1
    assert plan.scene_choreography["dashboard_layout"]["planning_basis"] == "scene_geometry_extent"
    assert plan.scene_choreography["dashboard_layout"]["agent_layout_decision"]["decision_basis"] == "verified_scene_geometry"
    assert plan.scene_choreography["dashboard_layout"]["agent_layout_decision"]["agent_action"] == "yield_center_to_particle_scene"
    assert plan.scene_choreography["dashboard_layout"]["agent_layout_decision"]["text_rendering"] == "dom_text_not_particles"
    assert plan.scene_choreography["dashboard_layout"]["orb"]["anchor"] == "lower_right"
    assert plan.scene_choreography["dashboard_layout"]["orb"]["size_vmin"] < 24
    assert plan.scene_choreography["dashboard_layout"]["speech"]["max_vw"] < 50
    assert plan.scene_choreography["dashboard_layout"]["speech"]["upper_left_top_vh"] < 23
    assert plan.scene_choreography["dashboard_layout"]["speech"]["lower_center_bottom_vh"] > 17
    assert plan.scene_choreography["dashboard_layout"]["self_narration"]["anchor"] == "upper_right"
    assert plan.scene_choreography["dashboard_layout"]["stage_safe_region"]["primary"] == "center_particle_stage"
    assert all("apple" in beat["source_fact"].casefold() for beat in beats if "apple" in beat["prompt"].casefold())
    assert plan.scene_choreography["topic_scene_templates"] is False
    assert plan.diagnostics["scene_authoring_basis"] == "verified_fact_entity_action_extraction"
