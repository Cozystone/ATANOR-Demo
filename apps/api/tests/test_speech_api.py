from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_chat_atanor_returns_clean_answer_and_compact_trace(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)

    response = client.post(
        "/api/chat/atanor",
        json={"question": "GraphRAG가 근거 문서를 어떻게 사용해서 답변을 검증하나요?", "language": "ko", "include_trace": True},
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert "Local Brain" not in result["answer"]
    assert "Cloud Brain" not in result["answer"]
    assert result["compact_trace"]["working_memory"]["local_brain_write"] is False
    assert result["answer_engine"]["external_llm"] is False
    assert result["answer_engine"]["external_sllm"] is False


def test_dashboard_conversation_voice_output_is_audio_truthful(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)

    response = client.post(
        "/api/chat/atanor",
        json={"question": "안녕", "language": "ko", "mode": "conversation", "brain_mode": "conversation"},
    )

    assert response.status_code == 200
    result = response.json()["result"]
    voice_output = result["voice_output"]
    assert voice_output["requested"] is True
    assert voice_output["enabled"] is True
    assert voice_output["selected_engine"] in {"none", "fish_2", "fish_1_5"}
    assert voice_output["audio_available"] is False
    assert voice_output["audio_url"] is None
    assert voice_output["error_reason"] in {"fish_runtime_missing", "fish_model_missing", "synthesis_adapter_not_wired"}
    assert voice_output["text_fallback"] is True
    assert voice_output["microphone_enabled"] is False
    assert voice_output["always_listening_enabled"] is False
    assert voice_output["raw_voice_saved"] is False
    assert voice_output["external_service"] is False
    assert voice_output["generated_audio_persisted"] is False
    assert result["local_brain_write"] is False
