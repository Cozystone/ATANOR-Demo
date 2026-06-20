from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_cloud_learning_status_separates_running_from_learning(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    response = client.get("/api/cloud-brain/learning/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["learning_status_endpoint"] is True
    assert "daemon_running" in payload
    assert "actually_learning" in payload
    assert payload["mock_growth"] is False
    assert payload["local_brain_write"] is False
    assert payload["pair_edges_sent"] == 0


def test_cloud_learning_run_once_updates_candidate_path_not_production(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    response = client.post(
        "/api/cloud-brain/learning/run-once",
        json={
            "candidate_store_root": str(tmp_path / "candidate_store"),
            "payloads": [
                {
                    "source_type": "manual_public_sentence",
                    "source_id": "manual:api-learning:1",
                    "text": "GraphRAG는 근거 문서를 검증합니다.",
                    "language": "ko",
                    "license_hint": "CC BY-SA 4.0",
                    "source_url_or_path": "manual://public/api-learning/1",
                }
            ],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["active_learning_state"] == "learning"
    assert payload["semantic"]["payloads_accepted"] == 1
    assert payload["semantic"]["concepts_added"] > 0
    assert payload["surface"]["accepted_surface_candidates"] > 0
    assert payload["cgsr_rhfc"]["rhfc_candidates_added"] > 0
    assert payload["production_store_mutated"] is False
    assert payload["false_confident"] == 0
    assert payload["forgetting_count"] == 0
    assert payload["invariants"]["eval_rows_used_for_learning"] is False
    assert payload["pair_edges_sent"] == 0


def test_cloud_surface_graph_and_identity_endpoints(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    surface = client.get("/api/cloud-brain/surface-graph/status")
    identity = client.get("/api/cloud-brain/identity")
    assert surface.status_code == 200
    assert identity.status_code == 200
    assert surface.json()["cgsr_consumes_surface_projection"] is True
    assert surface.json()["production_store_mutated"] is False
    assert identity.json()["promotion_default"] == "manual_review_required"
    assert identity.json()["mock_growth_allowed"] is False
