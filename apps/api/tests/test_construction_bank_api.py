from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_construction_bank_api_extract_retrieve_and_export(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)

    extract = client.post(
        "/api/construction-bank/extract",
        json={
            "sources": [
                {
                    "source_type": "operator_example",
                    "language": "ko",
                    "route_type": "voice_status",
                    "act": "voice_question",
                    "text": "Fish 직접 합성은 아직 연결 전이라 Windows 로컬 음성으로 먼저 발화합니다.",
                    "source_refs": ["test"],
                    "grounding_quality": "medium",
                }
            ],
            "store": True,
        },
    )
    assert extract.status_code == 200
    payload = extract.json()
    assert payload["external_llm"] is False
    assert payload["construction_auto_promoted"] is False
    candidate_id = payload["candidates"][0]["candidate_id"]

    retrieve = client.post(
        "/api/construction-bank/retrieve",
        json={"route_type": "voice_status", "language": "ko", "act": "voice_question", "audience": "lab"},
    )
    assert retrieve.status_code == 200
    assert retrieve.json()["retrieved_self_grown_construction"] is True
    assert retrieve.json()["production_active"] is False

    exported = client.post("/api/construction-bank/export-review-item", json={"candidate_id": candidate_id})
    assert exported.status_code == 200
    body = exported.json()
    assert body["review_item"]["item_type"] == "construction_candidate"
    assert body["mutation_performed"] is False

    status = client.get("/api/construction-bank/status")
    assert status.status_code == 200
    assert status.json()["production_active_count"] == 0
