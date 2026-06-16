from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_semantic_cloud_growth_api_ingest_status_graph_and_attach():
    sample = "쿠버네티스는 컨테이너화된 애플리케이션을 자동으로 배포하고 관리하는 오픈소스 플랫폼입니다."
    ingest = client.post(
        "/api/cloud-brain/semantic/ingest",
        json={"text": sample, "source_id": "api-semantic-growth-test", "language": "ko", "usage_allowed": False},
    )
    assert ingest.status_code == 200
    assert ingest.json()["honesty"]["local_brain_write"] is False

    status = client.get("/api/cloud-brain/semantic/status")
    assert status.status_code == 200
    status_payload = status.json()
    assert status_payload["concepts"] > 0
    assert status_payload["old_mirror_snapshot_used_as_live_cloud"] is False

    graph = client.get("/api/cloud-brain/semantic/graph")
    assert graph.status_code == 200
    assert graph.json()["nodes"]
    assert graph.json()["old_mirror_snapshot_used"] is False

    attach = client.post("/api/cloud-brain/semantic/attach", json={"query": "쿠버네티스가 뭐야?", "limit": 8})
    assert attach.status_code == 200
    assert attach.json()["temporary"] is True
    assert attach.json()["local_brain_write"] is False
