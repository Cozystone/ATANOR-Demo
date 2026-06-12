from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_cloud_brain_status_is_local_facade() -> None:
    response = client.get("/api/cloud-brain/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Cloud Brain"
    assert payload["mode"] == "shared-public-ontology-facade"
    assert payload["public_cloud_backend_enabled"] is False
    assert payload["answer_policy"]["external_llm"] is False


def test_cloud_brain_query_returns_fragments_without_external_llm() -> None:
    response = client.post("/api/cloud-brain/query", json={"query": "GraphRAG memory"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "local_cloud_brain_facade"
    assert payload["promotion_policy"]["writes_public_cloud"] is False
    assert "active_nodes" in payload["fragments"]


def test_cloud_brain_ingest_is_honest_until_public_backend_exists() -> None:
    response = client.post(
        "/api/cloud-brain/ingest",
        json={"source_url": "https://example.com", "text": "sample", "dry_run": False},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["accepted"] is False
    assert payload["state"] == "planned"
