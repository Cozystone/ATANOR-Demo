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
                "object_track_id": "verified_track_focus_subject",
                "object_track_basis": "verified_source_anchor",
                "prompt": "agent-authored subject",
                "narration": "agent-authored visible narration",
                "t_start": 2.5,
                "duration": 4.0,
                "position": [1.5, -1.0, 0.25],
                "pose_hint": "reaching",
                "surface_features": ["fruit_cluster"],
                "particle_behavior": "gravity_arc",
                "scene_directive": {
                    "directive_owner": "cgsr_visual_imagination_planner",
                    "basis": "verified_scene_beat",
                    "narrative_function": "demonstrate_verified_motion",
                    "stage_instruction": "animate_verified_motion_path",
                    "particle_text": False,
                },
                "physics_hint": {"basis": "verified_motion_phrase", "field": "downward_attraction", "gravity_bias": 0.7},
                "motion_path": {"from": [-0.5, 0.25, 0], "to": [0.5, -0.25, 0], "basis": "verified_motion_phrase"},
                "camera": {"target": [0.5, -0.25, 0], "zoom": 1.2},
            },
        ],
    })

    beat = plan.beats[0]
    assert plan.text_anchor == "upper_right"
    assert beat.op == "focus_camera"
    assert beat.object_track_id == "verified_track_focus_subject"
    assert beat.object_track_basis == "verified_source_anchor"
    assert beat.narration == "agent-authored visible narration"
    assert beat.t_start == 2.5
    assert beat.duration == 4.0
    assert beat.position == (1.5, -1.0, 0.25)
    assert beat.pose_hint == "reaching"
    assert beat.surface_features == ("fruit_cluster",)
    assert beat.particle_behavior == "gravity_arc"
    assert beat.scene_directive["directive_owner"] == "cgsr_visual_imagination_planner"
    assert beat.scene_directive["stage_instruction"] == "animate_verified_motion_path"
    assert beat.scene_directive["particle_text"] is False
    assert beat.scene_evidence["source_type"] == "verified_evidence_unit"
    assert beat.scene_evidence["prompt_span"] == "agent-authored subject"
    assert beat.scene_evidence["text_rendering"] == "dom_text_not_particles"
    assert beat.scene_evidence["particle_text"] is False
    assert beat.scene_evidence["topic_scene_templates"] is False
    assert beat.scene_evidence["renderer_may_infer_topic"] is False
    assert beat.physics_hint == {"basis": "verified_motion_phrase", "field": "downward_attraction", "gravity_bias": 0.7}
    assert beat.motion_path == {"from": (-0.5, 0.25, 0.0), "to": (0.5, -0.25, 0.0), "basis": "verified_motion_phrase"}
    assert beat.camera == {"target": [0.5, -0.25, 0], "zoom": 1.2}
    assert plan.topic_scene_templates is False


def test_scene_choreography_exports_verified_speech_timeline() -> None:
    plan = compile_scene_choreography({
        "stage_layout": "scene_focus",
        "beats": [
            {
                "op": "spawn_object",
                "object_id": "tree_anchor",
                "prompt": "tree",
                "narration": "A tree is the visible anchor.",
                "speech_cue": False,
                "speech_cue_basis": "visual_anchor_only",
                "t_start": 0.0,
            },
            {
                "op": "move",
                "object_id": "apple_motion",
                "prompt": "apple",
                "narration": "The apple moves downward in the verified account.",
                "speech_cue": True,
                "speech_cue_basis": "verified_evidence_unit",
                "scene_group_id": "gravity_example",
                "scene_group_role": "motion_event",
                "t_start": 1.4,
                "duration": 2.2,
                "particle_behavior": "gravity_arc",
                "physics_hint": {"basis": "verified_motion_phrase", "field": "downward_attraction", "gravity_bias": 0.7},
                "motion_path": {"from": [0.0, 0.5, 0.0], "to": [0.0, -0.6, 0.0], "basis": "verified_motion_phrase"},
            },
        ],
    })

    assert len(plan.speech_timeline) == 1
    item = plan.speech_timeline[0]
    assert item["beat_index"] == 1
    assert item["text"] == "The apple moves downward in the verified account."
    assert item["text_source"] == "verified_beat_narration"
    assert item["speech_cue_basis"] == "verified_evidence_unit"
    assert item["scene_group_id"] == "gravity_example"
    assert "object_track_id" in item
    assert item["particle_behavior"] == "gravity_arc"
    assert item["scene_directive"]["stage_instruction"] == "animate_verified_motion_path"
    assert item["scene_directive"]["particle_text"] is False
    assert item["scene_evidence"]["source_type"] == "verified_evidence_unit"
    assert item["scene_evidence"]["prompt_span"] == "apple"
    assert item["scene_evidence"]["motion_basis"] == "verified_motion_phrase"
    assert item["scene_evidence"]["particle_text"] is False
    assert item["scene_evidence"]["topic_scene_templates"] is False
    assert item["scene_evidence"]["renderer_may_infer_topic"] is False
    assert item["physics_hint"]["field"] == "downward_attraction"
    assert item["motion_path"]["basis"] == "verified_motion_phrase"
    assert plan.dashboard_layout["agent_layout_decision"]["text_rendering"] == "dom_text_not_particles"
    assert plan.dashboard_layout["agent_layout_decision"]["decision_owner"] == "cgsr_scene_choreography_agent"
    assert plan.dashboard_layout["agent_layout_decision"]["content_source"] == "verified_beats_only"
    assert plan.dashboard_layout["agent_layout_decision"]["topic_scene_templates"] is False
    assert plan.dashboard_layout["agent_layout_decision"]["renderer_may_infer_topic"] is False
    assert plan.dashboard_layout["agent_layout_decision"]["scene_geometry_inputs"]["motion_count"] == 1
    assert plan.dashboard_layout["stage_safe_region"]["footprint"]["basis"] == "verified_scene_geometry_extent"
    assert plan.dashboard_layout["stage_safe_region"]["footprint"]["block_text"] is True
    assert plan.layout_timeline[0]["action"] in {"share_center_with_particle_scene", "yield_center_to_particle_scene"}
    assert plan.layout_timeline[0]["decision_basis"] == "verified_scene_geometry"
    assert plan.layout_timeline[0]["decision_owner"] == "cgsr_scene_choreography_agent"
    assert plan.layout_timeline[0]["text_rendering"] == "dom_text_not_particles"
    active_layout = next(item for item in plan.layout_timeline if item["action"] == "sync_orb_text_with_particle_beat" and item["beat_index"] == 1)
    assert active_layout["text_rendering"] == "dom_text_not_particles"
    assert active_layout["decision_owner"] == "cgsr_scene_choreography_agent"
    assert active_layout["scene_directive"]["stage_instruction"] == "animate_verified_motion_path"
    assert active_layout["scene_evidence"]["source_type"] == "verified_evidence_unit"
    assert active_layout["scene_evidence"]["motion_basis"] == "verified_motion_phrase"
    assert active_layout["scene_evidence"]["renderer_may_infer_topic"] is False
    assert "object_track_id" in active_layout
    assert active_layout["orb_movement"] == "lower_right_lifted"
    assert active_layout["text_anchor"] == "lower_left"
    assert active_layout["text_anchor_basis"] == "verified_vertical_motion_path_conversational_clearance"
    assert active_layout["text_anchor_points"] == 3
    assert active_layout["self_narration_anchor"] in {"upper_left", "upper_right"}
    assert plan.topic_scene_templates is False


def test_layout_timeline_places_speech_away_from_active_scene_focus() -> None:
    plan = compile_scene_choreography({
        "stage_layout": "scene_focus",
        "beats": [
            {
                "op": "spawn_object",
                "prompt": "verified right-side particle focus",
                "narration": "The verified focus is on the right side.",
                "position": [0.72, 0.24, 0.0],
                "speech_cue": True,
                "t_start": 0.0,
                "duration": 1.4,
            },
            {
                "op": "spawn_object",
                "prompt": "verified left-side particle focus",
                "narration": "The verified focus shifts to the left side.",
                "position": [-0.72, 0.24, 0.0],
                "speech_cue": True,
                "t_start": 1.4,
                "duration": 1.4,
            },
        ],
    })

    first = next(item for item in plan.layout_timeline if item.get("beat_index") == 0)
    second = next(item for item in plan.layout_timeline if item.get("beat_index") == 1)
    assert first["text_anchor"] == "upper_left"
    assert second["text_anchor"] == "upper_right"
    assert first["text_rendering"] == second["text_rendering"] == "dom_text_not_particles"
    footprint = plan.dashboard_layout["stage_safe_region"]["footprint"]
    assert footprint["basis"] == "verified_scene_geometry_extent"
    assert footprint["min_x"] < 0 < footprint["max_x"]


def test_layout_timeline_nudges_orb_from_active_lower_right_focus() -> None:
    plan = compile_scene_choreography({
        "stage_layout": "scene_focus",
        "beats": [
            {
                "op": "move",
                "prompt": "verified lower-right moving object",
                "narration": "The verified object moves through the lower right.",
                "position": [0.58, -0.36, 0.0],
                "motion_path": {"from": [0.45, 0.22, 0.0], "to": [0.62, -0.46, 0.0], "basis": "verified_motion_phrase"},
                "speech_cue": True,
                "t_start": 0.0,
                "duration": 1.6,
            },
        ],
    })

    active = next(item for item in plan.layout_timeline if item.get("beat_index") == 0)
    assert active["decision_basis"] == "verified_speech_cue_beat"
    assert active["orb_movement"] == "lower_right_lifted_compact"
    assert active["text_rendering"] == "dom_text_not_particles"


def test_layout_timeline_places_speech_away_from_motion_path_even_when_position_is_centered() -> None:
    plan = compile_scene_choreography({
        "stage_layout": "scene_focus",
        "beats": [
            {
                "op": "move",
                "prompt": "verified right-side falling object",
                "narration": "The verified object moves down on the right side.",
                "position": [0.0, 0.0, 0.0],
                "motion_path": {"from": [0.66, 0.48, 0.0], "to": [0.72, -0.42, 0.0], "basis": "verified_motion_phrase"},
                "speech_cue": True,
                "t_start": 0.0,
                "duration": 1.6,
            },
        ],
    })

    active = next(item for item in plan.layout_timeline if item.get("beat_index") == 0)
    assert active["decision_basis"] == "verified_speech_cue_beat"
    assert active["text_anchor"] == "upper_left"
    assert active["text_anchor_basis"] == "verified_motion_path_horizontal_clearance"
    assert active["text_anchor_points"] == 3
    assert active["text_rendering"] == "dom_text_not_particles"


def test_command_adapter_keeps_safety_flags_closed() -> None:
    plan, frame = compile_splatra_command("visual scene request", particle_budget=128)

    assert plan.safety_flags["external_llm"] is False
    assert plan.safety_flags["external_sllm"] is False
    assert plan.safety_flags["image_model_used"] is False
    assert plan.safety_flags["local_brain_write"] is False
    assert plan.safety_flags["production_store_mutated"] is False
    assert plan.safety_flags["generated_scene_committed"] is False
    assert frame.objects[0].is_verified_knowledge is False
