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
    assert result["method"] == "homage-hybrid-graphrag-v1"
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
    assert result["evidence_docs"] == []
    assert result["matched_nodes"][0]["id"] == "graphrag"
    assert result["retrieval_trace"]["ranked_chunk_ids"] == []
    assert "2개 노드" in result["answer"]
