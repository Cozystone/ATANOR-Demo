from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.agentic_micro_os import router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_imagination_status_is_proof_only() -> None:
    payload = _client().get("/api/agentic-os/splatra/imagination/status").json()

    assert payload["available"] is True
    assert payload["proof_only"] is True
    assert payload["is_verified_knowledge"] is False
    assert payload["external_llm"] is False
    assert payload["image_model_used"] is False
    assert "orb" in payload["archetypes"]
    assert payload["visible_object"] is True
    assert payload["product_visible"] is True
    assert payload["clear_radius"] == 0.34


def test_imagination_generate_returns_particles_and_safety_flags() -> None:
    payload = _client().post(
        "/api/agentic-os/splatra/imagination/generate",
        json={"seed_id": "api_test", "archetype": "machine_core", "particle_budget": 300},
    ).json()
    frame = payload["frame"]
    item = frame["objects"][0]

    assert payload["allowed"] is True
    assert item["particle_count"] <= 300
    assert item["is_verified_knowledge"] is False
    assert item["compressed_ref"]["compression_ratio"] > 1.0
    assert payload["local_brain_write"] is False
    assert payload["production_store_mutated"] is False
    assert payload["visible_object"] is True
    assert payload["product_visible"] is True
    assert payload["active_archetype"] == "machine_core"
    assert payload["particle_count"] == item["particle_count"]
    assert payload["clear_radius"] == 0.34


def test_imagination_rejects_unknown_archetype() -> None:
    payload = _client().post(
        "/api/agentic-os/splatra/imagination/generate",
        json={"seed_id": "api_test", "archetype": "forbidden_memory_fact", "particle_budget": 300},
    ).json()

    assert payload["allowed"] is False
    assert payload["production_store_mutated"] is False


def test_imagination_evaluate_runs_all_archetypes() -> None:
    payload = _client().post("/api/agentic-os/splatra/imagination/evaluate", json={"particle_budget": 180}).json()

    assert payload["passed"] is True
    assert len(payload["archetypes"]) == 9
    assert payload["safety_flags"]["generated_scene_committed"] is False


def test_imagination_command_exposes_agent_usable_scene_action() -> None:
    payload = _client().post(
        "/api/agentic-os/splatra/imagination/command",
        json={"command": "make a bounded visual object", "particle_budget": 240, "scene_command": "morph", "archetype": "tree"},
    ).json()

    assert payload["allowed"] is True
    assert payload["agent_can_use"] is True
    assert payload["splatra_command_adapter"] is True
    assert payload["external_splatra_called"] is False
    assert payload["raw_buffer_in_agent_context"] is False
    assert payload["command_plan"]["scene_action"]["execute_js"] is False
    assert payload["command_plan"]["scene_command"] == "morph"
    assert payload["command_plan"]["archetype"] == "tree"
    assert payload["command_plan"]["splatra_contract"]["compatible_source"] == "Cozystone/SPLATRA"
    assert payload["command_plan"]["splatra_contract"]["topic_scene_templates"] is False
    assert payload["frame"]["objects"][0]["particle_count"] <= 240
    assert payload["local_brain_write"] is False
    assert payload["production_store_mutated"] is False


def test_scene_choreography_endpoint_accepts_agent_authored_beats_only() -> None:
    payload = _client().post(
        "/api/agentic-os/splatra/imagination/choreography",
        json={
            "stage_layout": "scene_focus",
            "beats": [
                {"op": "spawn_object", "object_id": "concept_a", "prompt": "concept figure", "archetype": "creature"},
                {"op": "focus_camera", "object_id": "concept_a", "camera": {"zoom": 1.4}},
            ],
        },
    ).json()

    assert payload["allowed"] is True
    assert payload["agent_can_use"] is True
    assert payload["splatra_choreography_adapter"] is True
    assert payload["external_splatra_called"] is False
    assert payload["raw_buffer_in_agent_context"] is False
    assert payload["topic_scene_templates"] is False
    assert payload["scene_choreography"]["stage_layout"] == "scene_focus"
    assert payload["scene_choreography"]["orb_anchor"] == "lower_right"
    assert len(payload["scene_choreography"]["beats"]) == 2
    assert payload["local_brain_write"] is False
    assert payload["production_store_mutated"] is False
