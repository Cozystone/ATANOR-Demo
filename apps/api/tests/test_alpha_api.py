from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.web_search import is_fresh_search_query


def test_alpha_endpoints_smoke(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    cleaned = tmp_path / "data" / "cleaned"
    cleaned.mkdir(parents=True)
    (cleaned / "doc1.txt").write_text(
        "# GraphRAG\nGraphRAG uses KnowledgeGraph. Evidence reduces HallucinationRisk. Guardrail requires Evidence.",
        encoding="utf-8",
    )
    client = TestClient(app)

    ontology = client.post("/api/ontology/run")
    assert ontology.status_code == 200
    assert ontology.json()["node_count"] > 0

    graph = client.get("/api/ontology/graph")
    assert graph.status_code == 200
    assert graph.json()["nodes"]

    rag = client.post("/api/graphrag/query", json={"query": "GraphRAG evidence"})
    assert rag.status_code == 200
    assert rag.json()["result"]["evidence_docs"]
    assert rag.json()["result"]["answer"]
    assert rag.json()["result"]["citations"]
    assert rag.json()["result"]["method"] == "homage-native-graphrag-utterance-v1"
    assert rag.json()["result"]["answer_engine"]["external_llm"] is False

    web_rag = client.post("/api/graphrag/query", json={"query": "Grounding with Bing architecture", "web_search": True})
    assert web_rag.status_code == 200
    web_result = web_rag.json()["result"]
    assert web_result["method"] == "homage-native-web-search-rag-v1"
    assert web_result["web_search"]["provider"] == "static"
    assert web_result["evidence_docs"]
    assert web_result["answer_engine"]["external_llm"] is False

    fresh_query = "\uC624\uB298 \uB274\uC2A4 \uC54C\uB824\uC918"
    assert is_fresh_search_query(fresh_query)
    fresh_rag = client.post("/api/graphrag/query", json={"query": fresh_query})
    assert fresh_rag.status_code == 200
    fresh_result = fresh_rag.json()["result"]
    assert fresh_result["method"] == "homage-native-web-search-rag-v1"
    assert "raw_no_node::" not in fresh_result["answer"]
    assert fresh_result["web_search"]["provider"] in {"news-rss", "static"}
    assert fresh_result["answer_engine"]["external_llm"] is False

    greeting = client.post("/api/graphrag/query", json={"query": "안녕"})
    assert greeting.status_code == 200
    greeting_result = greeting.json()["result"]
    assert greeting_result["method"] == "homage-conversation-router-v1"
    assert greeting_result["evidence_docs"] == []
    assert greeting_result["matched_nodes"] == []

    inventory = client.post("/api/graphrag/query", json={"query": "너한테 있는 노드 다 말해봐"})
    assert inventory.status_code == 200
    inventory_result = inventory.json()["result"]
    assert inventory_result["method"] == "homage-graph-inspection-v1"
    assert inventory_result["evidence_docs"] == []
    assert inventory_result["matched_nodes"]
    assert inventory_result["answer_engine"]["external_llm"] is False

    legend = client.post("/api/graphrag/query", json={"query": "색깔별 노드 의미가 뭐지"})
    assert legend.status_code == 200
    legend_result = legend.json()["result"]
    assert legend_result["method"] == "homage-graph-legend-v1"
    assert legend_result["evidence_docs"] == []
    assert legend_result["answer_engine"]["external_llm"] is False
    assert "색깔은 노드의 역할" in legend_result["answer"]

    guard = client.post("/api/guard/check", json={"draft_answer": "GraphRAG always guarantees perfect answers."})
    assert guard.status_code == 200
    assert guard.json()["overall_guard_score"] < 100

    oven = client.post("/api/oven/dry-run")
    assert oven.status_code == 200
    assert oven.json()["last_loss"] > 0

    gpu = client.get("/api/telemetry/gpu")
    assert gpu.status_code == 200
    assert "available" in gpu.json()

    pipeline = client.get("/api/pipeline/status")
    assert pipeline.status_code == 200
    assert len(pipeline.json()["stages"]) == 7
