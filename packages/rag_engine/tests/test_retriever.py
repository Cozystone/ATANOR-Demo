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
