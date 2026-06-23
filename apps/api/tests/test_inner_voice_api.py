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


def test_product_hides_raw_inner_voice() -> None:
    client = _client()
    client.post("/api/inner-voice/emit", json={"latest_user_input": "안녕"})

    payload = client.get("/api/inner-voice/log?workspace=product").json()

    assert payload["raw_inner_voice_hidden"] is True
    assert "frames" not in payload
    assert payload["safety_flags"]["raw_hidden_cot_claim"] is False


def test_brief_endpoint() -> None:
    client = _client()
    client.post("/api/inner-voice/emit", json={"latest_user_input": "안녕"})

    payload = client.post("/api/inner-voice/brief", json={"workspace": "lab"}).json()

    assert payload["brief"]
    assert payload["external_llm"] is False
