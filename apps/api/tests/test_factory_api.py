from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_factory_build_start_marks_target_as_long_run_budget() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/factory/build/start",
        json={"learning_volume": "lite", "target_nodes": 3_000},
    )

    assert response.status_code == 200
    body = response.json()
    gate = body["training_gate"]
    assert body["mode"] == "alpha-live-harvest"
    assert body["learning_profile"]["target_nodes"] == 3_000
    assert gate["target_nodes"] == 3_000
    assert gate["target_semantics"] == "long_run_storage_goal"
    assert gate["representative_node_count"] == len(body["graph_3d"]["nodes"])
    assert gate["representative_node_count"] < gate["target_nodes"]
    assert gate["target_realized"] is False
    assert "representative sample" in gate["sampling_explanation"]


def test_factory_standard_uses_representative_render_budget() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/factory/build/start",
        json={"learning_volume": "standard", "target_nodes": 10_000},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["learning_profile"]["visual_node_budget"] == 210
    assert body["training_gate"]["representative_node_count"] == 181
    assert body["training_gate"]["visual_node_budget"] == 210
    assert body["training_gate"]["target_nodes"] == 10_000

