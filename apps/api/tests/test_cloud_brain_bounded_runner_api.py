from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
PRODUCTION_STORE = PROJECT_ROOT / "data" / "cloud_brain" / "verified_store_v0"


def _production_identity() -> tuple[str, str, dict[str, int]]:
    manifest_path = PRODUCTION_STORE / "manifest.json"
    schema_path = PRODUCTION_STORE / "schema.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return (
        hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        hashlib.sha256(schema_path.read_bytes()).hexdigest(),
        {key: int(value) for key, value in manifest.get("counts", {}).items()},
    )


def _payloads(count: int) -> list[dict[str, object]]:
    rows = []
    for index in range(count):
        text = f"후보 실행 {index}는 표면 그래프 후보를 안전하게 생성합니다."
        rows.append(
            {
                "payload_id": f"bounded_api_{index}",
                "source_type": "manual_public_sentence",
                "source_id": f"manual:bounded-api:{index}",
                "source_url_or_path": f"manual://bounded-api/{index}",
                "provenance_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "license_hint": "CC BY-SA 4.0 api test fixture",
                "language": "ko",
                "text": text,
                "is_private": False,
                "is_generated": False,
                "is_eval_row": False,
                "target_store": "verified_store_v0_candidate",
            }
        )
    return rows


def test_run_capped_execute_false_does_not_process_payloads(tmp_path: Path) -> None:
    response = client.post(
        "/api/cloud-brain/learning/run-capped",
        json={
            "execute": False,
            "dry_run": True,
            "target_candidate_store": str(tmp_path / "candidate"),
            "min_ram_free_gb": 0,
            "min_disk_free_gb": 0,
            "payloads": _payloads(5),
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "dry_run"
    assert payload["payloads_accepted"] == 0
    assert not (tmp_path / "candidate").exists()


def test_run_capped_execute_true_grows_candidate_only(tmp_path: Path) -> None:
    before = _production_identity()
    response = client.post(
        "/api/cloud-brain/learning/run-capped",
        json={
            "execute": True,
            "dry_run": False,
            "max_payloads": 12,
            "max_seconds": 60,
            "max_store_mb": 64,
            "min_ram_free_gb": 0,
            "min_disk_free_gb": 0,
            "max_cpu_percent": None,
            "max_candidate_files": None,
            "target_candidate_store": str(tmp_path / "candidate"),
            "payloads": _payloads(12),
        },
    )
    after = _production_identity()
    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "completed"
    assert payload["payloads_accepted"] == 12
    assert payload["surface_candidates"] == 12
    assert payload["cgsr_frames"] == 12
    assert payload["rhfc_candidates"] == 12
    assert payload["production_store_mutated"] is False
    assert payload["local_brain_write"] is False
    assert payload["false_confident"] == 0
    assert payload["forgetting_count"] == 0
    assert payload["unsupported_claims"] == 0
    assert before == after


def test_run_capped_rejects_production_promotion(tmp_path: Path) -> None:
    response = client.post(
        "/api/cloud-brain/learning/run-capped",
        json={
            "execute": True,
            "dry_run": False,
            "promote_to_verified": True,
            "target_candidate_store": str(tmp_path / "candidate"),
            "payloads": _payloads(1),
        },
    )
    assert response.status_code == 400


def test_learning_status_exposes_bounded_runner_readiness() -> None:
    response = client.get("/api/cloud-brain/learning/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["bounded_runner_available"] is True
    assert "safe_to_start_24h_candidate_run" in payload
    assert "current_resource_pressure" in payload
