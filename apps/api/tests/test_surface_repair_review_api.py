from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api.app.main import app


def test_surface_repair_review_queue_api(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)

    created = client.post(
        "/api/surface-brain/feedback-to-repair-candidates",
        json={
            "run_id": "api-review-run",
            "feedback_items": [{
                "feedback_id": "api-feedback-1",
                "type": "trace_leakage",
                "suggestion": "Move Cloud Brain route details to trace.",
                "flags": ["trace_leakage"],
            }],
        },
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["created_candidates"] == 1
    candidate_id = created_body["candidate_ids"][0]
    assert created_body["requires_review"] is True
    assert created_body["auto_promoted"] is False

    listed = client.get("/api/surface-brain/repair-candidates?status=pending")
    assert listed.status_code == 200
    assert listed.json()["count"] == 1

    approved = client.post(
        f"/api/surface-brain/repair-candidates/{candidate_id}/approve",
        json={"reviewer": "api_tester", "comment": "approved"},
    )
    assert approved.status_code == 200
    rule_id = approved.json()["production_rule"]["rule_id"]

    production = client.get("/api/surface-brain/production-rules")
    assert production.status_code == 200
    assert any(row["rule_id"] == rule_id for row in production.json()["production_rules"])

    rollback = client.post(f"/api/surface-brain/production-rules/{rule_id}/rollback")
    assert rollback.status_code == 200
    assert rollback.json()["rollback"]["enabled"] is False

    rejected_create = client.post(
        "/api/surface-brain/feedback-to-repair-candidates",
        json={
            "run_id": "api-review-run-2",
            "feedback_items": [{
                "feedback_id": "api-feedback-2",
                "type": "language_native_style",
                "suggestion": "Korean unnatural wording.",
            }],
        },
    )
    reject_id = rejected_create.json()["candidate_ids"][0]
    rejected = client.post(
        f"/api/surface-brain/repair-candidates/{reject_id}/reject",
        json={"reviewer": "api_tester", "comment": "style review later"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["candidate"]["status"] == "rejected"

    audit = client.get("/api/surface-brain/repair-audit")
    assert audit.status_code == 200
    events = {row["event_type"] for row in audit.json()["events"]}
    assert "candidate_created" in events
    assert "candidate_approved" in events
    assert "candidate_rejected" in events
    assert "rule_rolled_back" in events
