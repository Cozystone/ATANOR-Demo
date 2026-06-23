from __future__ import annotations

from packages.splatra_imagination.command_adapter import compile_splatra_command
from packages.splatra_imagination.scene_choreography import compile_scene_choreography


def test_command_adapter_compiles_prompt_to_scene_action_without_raw_buffers() -> None:
    plan, frame = compile_splatra_command("show a bounded particle object", particle_budget=320)

    assert plan.scene_command == "spawn_object"
    assert plan.scene_action["op"] == "spawn_object"
    assert plan.scene_action["args"]["particle_budget"] == 320
    assert plan.raw_buffer_in_agent_context is False
    assert plan.external_splatra_called is False
    assert plan.splatra_contract["raw_buffers_in_agent_context"] is False
    assert plan.splatra_contract["topic_scene_templates"] is False
    assert frame.objects[0].metadata["splatra_command_plan"]["scene_action"]["execute_js"] is False
    assert frame.objects[0].particle_count <= 320


def test_command_adapter_respects_agent_authored_action_without_keyword_templates() -> None:
    plan, _frame = compile_splatra_command(
        "agent-authored visual beat",
        particle_budget=128,
        scene_command="morph",
        archetype="tree",
    )

    assert plan.scene_command == "morph"
    assert plan.archetype == "tree"
    assert plan.scene_action["op"] == "morph"
    assert plan.splatra_contract["topic_scene_templates"] is False


def test_scene_choreography_validates_agent_authored_beats_without_inventing_content() -> None:
    plan = compile_scene_choreography({
        "stage_layout": "scene_focus",
        "beats": [
            {"op": "spawn_object", "object_id": "figure", "prompt": "historical figure", "archetype": "creature"},
            {"op": "move", "object_id": "falling_object", "position": [0.2, -0.8, 0.0]},
        ],
    })

    assert plan.stage_layout == "scene_focus"
    assert plan.orb_anchor == "lower_right"
    assert plan.text_anchor == "lower_left"
    assert plan.primary_surface == "splatra_stage"
    assert len(plan.beats) == 2
    assert plan.topic_scene_templates is False
    assert plan.external_splatra_called is False
    assert plan.raw_buffer_in_agent_context is False
    assert plan.safety_flags["local_brain_write"] is False
    assert plan.safety_flags["production_store_mutated"] is False


def test_scene_choreography_preserves_timing_position_and_camera_hints() -> None:
    plan = compile_scene_choreography({
        "stage_layout": "scene_focus",
        "text_anchor": "upper_right",
        "beats": [
            {
                "op": "focus_camera",
                "object_id": "focus_subject",
                "prompt": "agent-authored subject",
                "narration": "agent-authored visible narration",
                "t_start": 2.5,
                "duration": 4.0,
                "position": [1.5, -1.0, 0.25],
                "camera": {"target": [0.5, -0.25, 0], "zoom": 1.2},
            },
        ],
    })

    beat = plan.beats[0]
    assert plan.text_anchor == "upper_right"
    assert beat.op == "focus_camera"
    assert beat.narration == "agent-authored visible narration"
    assert beat.t_start == 2.5
    assert beat.duration == 4.0
    assert beat.position == (1.5, -1.0, 0.25)
    assert beat.camera == {"target": [0.5, -0.25, 0], "zoom": 1.2}
    assert plan.topic_scene_templates is False


def test_command_adapter_keeps_safety_flags_closed() -> None:
    plan, frame = compile_splatra_command("visual scene request", particle_budget=128)

    assert plan.safety_flags["external_llm"] is False
    assert plan.safety_flags["external_sllm"] is False
    assert plan.safety_flags["image_model_used"] is False
    assert plan.safety_flags["local_brain_write"] is False
    assert plan.safety_flags["production_store_mutated"] is False
    assert plan.safety_flags["generated_scene_committed"] is False
    assert frame.objects[0].is_verified_knowledge is False
