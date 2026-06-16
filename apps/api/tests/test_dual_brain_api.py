from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_dual_brain_ingest_links_semantic_and_surface(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)

    response = client.post(
        "/api/dual-brain/ingest",
        json={"text": "쉽게 말하면, 쿠버네티스는 많은 컨테이너를 자동으로 배치하고 관리합니다."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["semantic_projection"]["source_hash"] == payload["surface_projection"]["source_hash"]
    assert payload["stored_raw_text"] is False
    assert payload["external_llm_used"] is False

