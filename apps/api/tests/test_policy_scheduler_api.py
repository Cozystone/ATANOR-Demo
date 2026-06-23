from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import agentic_micro_os as router_module
from app.routers.agentic_micro_os import router
from packages.neural_emotion.event_bus import EVENT_BUS


def _client() -> TestClient:
    EVENT_BUS.reset(clear_events=True)
    router_module.POLICY_SCHEDULER_RUNS.clear()
    router_module.REVIEW_QUEUE.items.clear()
    router_module.REVIEW_QUEUE.decisions.clear()
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_scheduler_disabled_by_default() -> None:
    payload = _client().get("/api/agentic-os/policy-scheduler/status").json()

    assert payload["enabled"] is False
    assert payload["safety_flags"]["scheduler_opt_in"] is True
    assert payload["safety_flags"]["scheduler_stoppable"] is True


def test_scheduler_start_requires_explicit_request() -> None:
    client = _client()

    denied = client.post("/api/agentic-os/policy-scheduler/start", json={"operator_confirmed": False}).json()
    allowed = client.post("/api/agentic-os/policy-scheduler/start", json={"operator_confirmed": True, "max_cycles": 2}).json()

    assert denied["allowed"] is False
    assert allowed["allowed"] is True
    assert allowed["enabled"] is True


def test_scheduler_stop_works() -> None:
    client = _client()
    client.post("/api/agentic-os/policy-scheduler/start", json={"operator_confirmed": True})

    stopped = client.post("/api/agentic-os/policy-scheduler/stop", json={"reason": "api_test_stop"}).json()

    assert stopped["enabled"] is False
    assert stopped["stopped_reason"] == "api_test_stop"


def test_scheduler_tick_runs_one_policy_loop() -> None:
    client = _client()
    client.post("/api/agentic-os/policy-scheduler/start", json={"operator_confirmed": True, "max_cycles": 3})

    payload = client.post("/api/agentic-os/policy-scheduler/tick").json()

    assert payload["ran"] is True
    assert payload["cycle_count"] == 1
    assert payload["last_result"]["cycles_completed"] == 1
    assert payload["local_brain_write"] is False
    assert payload["production_store_mutated"] is False
    assert payload["candidate_promotion"] is False
    assert payload["auto_commit"] is False
    assert payload["auto_push"] is False


def test_scheduler_max_cycles_stops() -> None:
    client = _client()
    client.post("/api/agentic-os/policy-scheduler/start", json={"operator_confirmed": True, "max_cycles": 1})

    payload = client.post("/api/agentic-os/policy-scheduler/tick").json()

    assert payload["enabled"] is False
    assert payload["stopped_reason"] == "max_cycles"


def test_scheduler_run_lookup() -> None:
    client = _client()
    client.post("/api/agentic-os/policy-scheduler/start", json={"operator_confirmed": True, "scheduler_id": "api_scheduler_lookup"})
    client.post("/api/agentic-os/policy-scheduler/tick")

    lookup = client.get("/api/agentic-os/policy-scheduler/runs/api_scheduler_lookup").json()

    assert lookup["run"]["scheduler_id"] == "api_scheduler_lookup"


def test_scheduler_review_pressure_pauses_exploration() -> None:
    client = _client()
    web_run = client.post("/api/agentic-os/web-explorer/open/run", json={"max_pages": 1, "per_domain_delay_sec": 0}).json()
    for _ in range(5):
        client.post("/api/agentic-os/review/import-web-run", json={"run_payload": web_run})
    client.post("/api/agentic-os/policy-scheduler/start", json={"operator_confirmed": True, "max_cycles": 3})

    payload = client.post("/api/agentic-os/policy-scheduler/tick").json()

    assert payload["last_result"]["stopped_reason"] == "review_requested"


def test_scheduler_status_has_no_mutation_flags() -> None:
    payload = _client().get("/api/agentic-os/policy-scheduler/status").json()

    assert payload["local_brain_write"] is False
    assert payload["production_store_mutated"] is False
    assert payload["candidate_promotion"] is False
    assert payload["auto_commit"] is False
    assert payload["auto_push"] is False
