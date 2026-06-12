from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_learning_daemon_status_endpoint() -> None:
    response = client.get("/api/learning/daemon/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "local-daemon"
    assert payload["local_required"] is True
    assert payload["llm_policy"]["external_llm"] is False


def test_learning_daemon_checkpoint_endpoint() -> None:
    response = client.post("/api/learning/daemon/checkpoint", json={"reason": "api-test"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["last_checkpoint_at"]
    assert payload["checkpoint_count"] >= 1
