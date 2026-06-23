from __future__ import annotations

from packages.splatra_imagination.command_adapter import compile_splatra_command


def test_command_adapter_compiles_prompt_to_scene_action_without_raw_buffers() -> None:
    plan, frame = compile_splatra_command("파란 회로 도시를 파티클로 만들어줘", particle_budget=320)

    assert plan.scene_command == "spawn_object"
    assert plan.archetype in {"circuit", "city_block"}
    assert plan.scene_action["op"] == "spawn_object"
    assert plan.scene_action["args"]["particle_budget"] == 320
    assert plan.raw_buffer_in_agent_context is False
    assert plan.external_splatra_called is False
    assert plan.splatra_contract["raw_buffers_in_agent_context"] is False
    assert frame.objects[0].metadata["splatra_command_plan"]["scene_action"]["execute_js"] is False
    assert frame.objects[0].particle_count <= 320


def test_command_adapter_keeps_safety_flags_closed() -> None:
    plan, frame = compile_splatra_command("별자리를 보여줘", particle_budget=128)

    assert plan.safety_flags["external_llm"] is False
    assert plan.safety_flags["external_sllm"] is False
    assert plan.safety_flags["image_model_used"] is False
    assert plan.safety_flags["local_brain_write"] is False
    assert plan.safety_flags["production_store_mutated"] is False
    assert plan.safety_flags["generated_scene_committed"] is False
    assert frame.objects[0].is_verified_knowledge is False
