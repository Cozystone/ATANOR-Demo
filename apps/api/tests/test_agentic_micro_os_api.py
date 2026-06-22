from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.agentic_micro_os import router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_status_is_proof_only_and_external_models_disabled() -> None:
    payload = _client().get("/api/agentic-os/status").json()

    assert payload["proof_only"] is True
    assert payload["external_llm"] is False
    assert payload["external_sllm"] is False
    assert payload["hermes_runtime_executed"] is False
    assert payload["hermes_code_copied"] is False
    assert payload["modules"]["splatra_cosmos_cell"] == "available"


def test_action_validation_accepts_safe_dashboard_action() -> None:
    response = _client().post(
        "/api/agentic-os/action/validate",
        json={"action_type": "set_orb_state", "payload": {"state": "thinking"}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["allowed"] is True
    assert payload["ui_command"]["execute_js"] is False


def test_action_validation_rejects_arbitrary_js_eval() -> None:
    payload = _client().post(
        "/api/agentic-os/action/validate",
        json={"action_type": "arbitrary_js_eval", "payload": {"code": "alert(1)"}},
    ).json()

    assert payload["allowed"] is False
    assert payload["arbitrary_js_eval"] is False


def test_brain_access_blocks_direct_local_write() -> None:
    payload = _client().post(
        "/api/agentic-os/brain-access/request",
        json={
            "target": "local_brain",
            "operation": "local_brain_direct_write",
            "query": "write memory",
        },
    ).json()

    assert payload["response"]["allowed"] is False
    assert payload["response"]["mutation_performed"] is False
    assert payload["local_brain_direct_write"] is False


def test_brain_access_candidate_draft_requires_approval() -> None:
    payload = _client().post(
        "/api/agentic-os/brain-access/request",
        json={
            "target": "local_brain",
            "operation": "local_brain_memory_candidate_draft",
            "query": "draft memory only",
        },
    ).json()

    assert payload["response"]["allowed"] is True
    assert payload["response"]["approval_required"] is True
    assert payload["response"]["mutation_performed"] is False


def test_loop_propose_returns_approval_required_patch_without_git() -> None:
    payload = _client().post("/api/agentic-os/loop/propose", json={"goal": "proof", "max_cycles": 1}).json()

    assert payload["approval_required"] is True
    assert payload["patch_proposals"]
    assert payload["auto_commit"] is False
    assert payload["auto_push"] is False


def test_hermes_intake_status_never_executes_runtime() -> None:
    payload = _client().get("/api/agentic-os/hermes-intake/status").json()

    assert payload["hermes_runtime_executed"] is False
    assert payload["hermes_code_copied"] is False
