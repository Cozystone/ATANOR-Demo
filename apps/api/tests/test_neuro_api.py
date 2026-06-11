from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_neuro_plan_api() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/neuro/plan",
        json={
            "text": "SNN event neuromorphic modular continual few-shot masking pruning quantization guardrail",
            "target_device": "low-power edge",
            "module_budget": 4,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["architecture"] == "Homage Neuro-Efficiency Layer"
    assert body["event_gate"]["sparsity"] > 0
    assert len(body["module_routing"]["active_modules"]) <= 4
    assert body["energy_estimate"]["reduction_ratio"] > 0.5
