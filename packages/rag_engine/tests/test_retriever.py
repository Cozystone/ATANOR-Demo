import json

from rag_engine import query_graphrag


def test_query_graphrag_matches_docs_and_graph(tmp_path):
    cleaned = tmp_path / "cleaned"
    ontology = tmp_path / "ontology"
    cleaned.mkdir()
    ontology.mkdir()
    (cleaned / "doc.txt").write_text("GraphRAG uses KnowledgeGraph for Evidence.", encoding="utf-8")
    (ontology / "nodes.json").write_text(json.dumps([{"id": "graphrag", "label": "GraphRAG"}]), encoding="utf-8")
    (ontology / "edges.json").write_text(json.dumps([{"source": "graphrag", "relation": "uses", "target": "knowledgegraph"}]), encoding="utf-8")

    result = query_graphrag("GraphRAG evidence", str(cleaned), str(ontology))

    assert result["evidence_docs"]
    assert result["matched_nodes"]
    assert result["answer"]
    assert result["citations"]
    assert result["retrieval_trace"]["ranked_chunk_ids"]
    assert result["method"] == "homage-native-graphrag-utterance-v1"
    assert result["answer_engine"]["external_llm"] is False
    assert result["pmv"]["intent"]
    assert result["claim_plan"]
    assert not result["answer"].startswith("질문 '")
    assert "읽힌 경로" not in result["answer"]
    assert result["confidence"] > 0


def test_query_graphrag_routes_greeting_without_evidence(tmp_path):
    cleaned = tmp_path / "cleaned"
    ontology = tmp_path / "ontology"
    cleaned.mkdir()
    ontology.mkdir()
    (cleaned / "doc.txt").write_text("GraphRAG uses KnowledgeGraph for Evidence.", encoding="utf-8")
    (ontology / "nodes.json").write_text(json.dumps([{"id": "evidence", "label": "Evidence"}]), encoding="utf-8")
    (ontology / "edges.json").write_text(json.dumps([]), encoding="utf-8")

    result = query_graphrag("안녕", str(cleaned), str(ontology))

    assert result["method"] == "homage-conversation-router-v1"
    assert result["answer_engine"]["external_llm"] is False
    assert result["evidence_docs"] == []
    assert result["matched_nodes"] == []
    assert result["retrieval_trace"]["ranked_chunk_ids"] == []
    assert "근거 문서를 억지로 붙이지" in result["answer"]


def test_query_graphrag_lists_nodes_without_retrieval(tmp_path):
    cleaned = tmp_path / "cleaned"
    ontology = tmp_path / "ontology"
    cleaned.mkdir()
    ontology.mkdir()
    (cleaned / "doc.txt").write_text("GraphRAG uses KnowledgeGraph for Evidence.", encoding="utf-8")
    (ontology / "nodes.json").write_text(
        json.dumps(
            [
                {"id": "graphrag", "label": "GraphRAG", "type": "concept", "confidence": 0.9},
                {"id": "evidence", "label": "Evidence", "type": "keyword", "confidence": 0.8},
            ]
        ),
        encoding="utf-8",
    )
    (ontology / "edges.json").write_text(json.dumps([{"source": "graphrag", "relation": "uses", "target": "evidence"}]), encoding="utf-8")

    result = query_graphrag("너한테 있는 노드 다 말해봐", str(cleaned), str(ontology))

    assert result["method"] == "homage-graph-inspection-v1"
    assert result["answer_engine"]["external_llm"] is False
    assert result["evidence_docs"] == []
    assert result["matched_nodes"][0]["id"] == "graphrag"
    assert result["retrieval_trace"]["ranked_chunk_ids"] == []
    assert "2개 노드" in result["answer"]


def test_query_graphrag_explains_color_legend_without_retrieval(tmp_path):
    cleaned = tmp_path / "cleaned"
    ontology = tmp_path / "ontology"
    cleaned.mkdir()
    ontology.mkdir()
    (cleaned / "doc.txt").write_text("GraphRAG uses KnowledgeGraph for Evidence.", encoding="utf-8")
    (ontology / "nodes.json").write_text(
        json.dumps(
            [
                {"id": "graphrag", "label": "GraphRAG", "type": "retrieval", "confidence": 0.9},
                {"id": "guardrail", "label": "Guardrail", "type": "guardrail", "confidence": 0.8},
            ]
        ),
        encoding="utf-8",
    )
    (ontology / "edges.json").write_text(json.dumps([{"source": "graphrag", "relation": "checks", "target": "guardrail"}]), encoding="utf-8")

    result = query_graphrag("색깔별 노드 의미가 뭐지", str(cleaned), str(ontology))

    assert result["method"] == "homage-graph-legend-v1"
    assert result["answer_engine"]["external_llm"] is False
    assert result["evidence_docs"] == []
    assert result["retrieval_trace"]["ranked_chunk_ids"] == []
    assert "색깔은 노드의 역할" in result["answer"]
    assert "검색" in result["answer"]


def test_query_graphrag_generates_structure_answer_without_direct_evidence(tmp_path):
    cleaned = tmp_path / "cleaned"
    ontology = tmp_path / "ontology"
    cleaned.mkdir()
    ontology.mkdir()
    (cleaned / "doc.txt").write_text("GraphRAG uses KnowledgeGraph for Evidence.", encoding="utf-8")
    (ontology / "nodes.json").write_text(
        json.dumps(
            [
                {"id": "graphrag", "label": "GraphRAG", "type": "retrieval", "confidence": 0.9},
                {"id": "guardrail", "label": "Guardrail", "type": "guardrail", "confidence": 0.8},
            ]
        ),
        encoding="utf-8",
    )
    (ontology / "edges.json").write_text(json.dumps([{"source": "graphrag", "relation": "checks", "target": "guardrail"}]), encoding="utf-8")

    result = query_graphrag("네 구조 설명해봐", str(cleaned), str(ontology))

    assert result["method"] == "homage-native-graphrag-utterance-v1"
    assert result["answer_engine"]["external_llm"] is False
    assert result["evidence_docs"] == []
    assert result["citations"] == []
    assert "직접 연결" not in result["answer"]
    assert "경로" not in result["answer"]
    assert "Homage" in result["answer"]
    assert "DataGate" in result["answer"] or "Ontology Forge" in result["answer"]
    assert result["follow_up_questions"]


def test_query_graphrag_unknown_external_entity_does_not_use_structure_context(tmp_path):
    cleaned = tmp_path / "cleaned"
    ontology = tmp_path / "ontology"
    cleaned.mkdir()
    ontology.mkdir()
    (cleaned / "doc.txt").write_text("GraphRAG uses KnowledgeGraph for Evidence.", encoding="utf-8")
    (ontology / "nodes.json").write_text(
        json.dumps([{"id": "graphrag", "label": "GraphRAG", "type": "retrieval", "confidence": 0.9}]),
        encoding="utf-8",
    )
    (ontology / "edges.json").write_text(json.dumps([]), encoding="utf-8")

    result = query_graphrag("유재석이 누구야", str(cleaned), str(ontology))

    assert result["answer_engine"]["external_llm"] is False
    assert result["evidence_docs"] == []
    assert result["citations"] == []
    assert "Homage1.0은 Harvest" not in result["answer"]
    assert "검증된 문서 근거" in result["answer"]
    assert "외부 LLM" in result["answer"]
