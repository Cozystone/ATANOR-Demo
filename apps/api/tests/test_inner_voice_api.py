from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.inner_voice import router
from packages.inner_voice.proof import GLOBAL_INNER_VOICE_LOG


def _client() -> TestClient:
    GLOBAL_INNER_VOICE_LOG.frames.clear()
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_lab_emit_and_log() -> None:
    client = _client()

    emitted = client.post("/api/inner-voice/emit", json={"latest_user_input": "안녕"}).json()
    log = client.get("/api/inner-voice/log?workspace=lab").json()

    assert emitted["emitted"] is True
    assert emitted["frame"]["monologue_text"]
    assert log["frames"]
    assert emitted["local_brain_write"] is False
    assert emitted["production_store_mutated"] is False


def test_product_hides_raw_frame_but_exposes_safe_self_narration() -> None:
    client = _client()
    client.post("/api/inner-voice/emit", json={"latest_user_input": "안녕"})

    payload = client.get("/api/inner-voice/log?workspace=product").json()

    assert payload["raw_inner_voice_hidden"] is True
    assert payload["product_summary"]["visible_self_narration"]
    assert payload["product_summary"]["inner_voice_is_explicit_generated_channel"] is True
    assert "frames" not in payload
    assert payload["safety_flags"]["raw_hidden_cot_claim"] is False


def test_brief_endpoint() -> None:
    client = _client()
    client.post("/api/inner-voice/emit", json={"latest_user_input": "안녕"})

    payload = client.post("/api/inner-voice/brief", json={"workspace": "lab"}).json()

    assert payload["brief"]
    assert payload["external_llm"] is False


def test_generate_frame_product_hides_raw_frame_and_exposes_summary() -> None:
    client = _client()

    payload = client.post(
        "/api/inner-voice/generate-frame",
        json={"mode": "product_summary", "latest_user_input": "안녕"},
    ).json()

    assert payload["generated"] is True
    assert payload["raw_inner_voice_hidden"] is True
    assert payload["product_summary"]["visible_self_narration"]
    assert payload["product_summary"]["generation_basis"] == "asm_cgsr_construction_conditioned_inner_voice_v1"
    assert "frame" not in payload
    assert payload["external_llm"] is False
    assert payload["raw_hidden_cot_claim"] is False


def test_visible_summary_endpoint_keeps_product_redaction() -> None:
    client = _client()
    client.post("/api/inner-voice/emit", json={"latest_user_input": "안녕"})

    payload = client.get("/api/inner-voice/visible-summary?workspace=product").json()

    assert payload["product_summary"]["raw_inner_voice_hidden"] is True
    assert payload["product_summary"]["visible_self_narration"]
    assert payload["product_safe"] is True
