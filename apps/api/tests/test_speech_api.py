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
