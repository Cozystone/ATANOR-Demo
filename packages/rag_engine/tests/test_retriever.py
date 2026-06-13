import json

from knowledge_bakery import build_memory
from rag_engine import query_graphrag


def _build_query_memory(cleaned, ontology):
    memory = cleaned.parent / "memory"
    build_memory(str(cleaned), str(ontology), str(memory))
    return str(memory)


def test_query_graphrag_matches_docs_and_graph(tmp_path):
    cleaned = tmp_path / "cleaned"
    ontology = tmp_path / "ontology"
    cleaned.mkdir()
    ontology.mkdir()
    (cleaned / "doc.txt").write_text("GraphRAG uses KnowledgeGraph for Evidence.", encoding="utf-8")
    (ontology / "nodes.json").write_text(json.dumps([{"id": "graphrag", "label": "GraphRAG"}]), encoding="utf-8")
    (ontology / "edges.json").write_text(json.dumps([{"source": "graphrag", "relation": "uses", "target": "knowledgegraph"}]), encoding="utf-8")

    memory = _build_query_memory(cleaned, ontology)
    result = query_graphrag("GraphRAG evidence", str(cleaned), str(ontology), memory)

    assert result["evidence_docs"]
    assert result["matched_nodes"]
    assert result["answer"]
    assert result["citations"]
    assert result["retrieval_trace"]["ranked_chunk_ids"]
    assert result["method"] == "atanor-graph-token-rag-v1"
    assert result["answer_engine"]["external_llm"] is False
    assert result["answer_engine"]["mode"] == "local-ghost-shell-autonomous-alpha"
    assert result["answer_kind"] == "local_synthesis"
    assert result["answer_engine"]["prediction_basis"] == "ghost_context_bundle_autonomous_synthesis"
    assert result["answer_engine"]["network_barrier"] == "sealed_for_generation"
    assert result["answer_engine"]["diagnostics"]["outbound_http_calls"] == 0
    assert result["confidence"] > 0


def test_query_graphrag_routes_greeting_without_evidence(tmp_path):
    cleaned = tmp_path / "cleaned"
    ontology = tmp_path / "ontology"
    cleaned.mkdir()
    ontology.mkdir()
    (cleaned / "doc.txt").write_text("GraphRAG uses KnowledgeGraph for Evidence.", encoding="utf-8")
    (ontology / "nodes.json").write_text(json.dumps([{"id": "evidence", "label": "Evidence"}]), encoding="utf-8")
    (ontology / "edges.json").write_text(json.dumps([]), encoding="utf-8")

    result = query_graphrag("hello", str(cleaned), str(ontology))

    assert result["method"] == "atanor-conversation-router-v1"
    assert result["answer_engine"]["external_llm"] is False
    assert result["answer_engine"]["surface_generation"] == "native_conversation_surface"
    assert result["evidence_docs"] == []
    assert result["matched_nodes"] == []
    assert result["retrieval_trace"]["ranked_chunk_ids"] == []
    assert "CONTROL_INTENT" not in result["answer"]
    assert "ATANOR" in result["answer"]
    assert result["answer_kind"] == "conversation"


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

    memory = _build_query_memory(cleaned, ontology)
    result = query_graphrag("show all nodes", str(cleaned), str(ontology), memory)

    assert result["method"] == "atanor-graph-inspection-v1"
    assert result["answer_engine"]["external_llm"] is False
    assert result["answer_kind"] == "inspection"
    assert result["answer_engine"]["surface_generation"] == "disabled"
    assert result["evidence_docs"] == []
    assert any(node["id"] == "graphrag" for node in result["matched_nodes"])
    assert result["retrieval_trace"]["ranked_chunk_ids"] == []
    assert "visible nodes" in result["answer"]


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

    memory = _build_query_memory(cleaned, ontology)
    result = query_graphrag("color legend", str(cleaned), str(ontology), memory)

    assert result["method"] == "atanor-graph-legend-v1"
    assert result["answer_engine"]["external_llm"] is False
    assert result["answer_kind"] == "inspection"
    assert result["answer_engine"]["surface_generation"] == "disabled"
    assert result["evidence_docs"] == []
    assert result["retrieval_trace"]["ranked_chunk_ids"] == []
    assert "graph colors" in result["answer"]


def test_query_graphrag_unknown_external_entity_uses_no_external_llm(tmp_path):
    cleaned = tmp_path / "cleaned"
    ontology = tmp_path / "ontology"
    cleaned.mkdir()
    ontology.mkdir()
    (cleaned / "doc.txt").write_text("GraphRAG uses KnowledgeGraph for Evidence.", encoding="utf-8")
    (ontology / "nodes.json").write_text(json.dumps([{"id": "graphrag", "label": "GraphRAG", "type": "retrieval", "confidence": 0.9}]), encoding="utf-8")
    (ontology / "edges.json").write_text(json.dumps([]), encoding="utf-8")

    memory = _build_query_memory(cleaned, ontology)
    result = query_graphrag("unknown external person", str(cleaned), str(ontology), memory)

    assert result["method"] == "atanor-research-no-evidence-v1"
    assert result["answer_engine"]["external_llm"] is False
    assert result["answer_engine"]["mode"] == "local-no-evidence-diagnostic-alpha"
    assert result["answer_kind"] == "no_evidence"
    assert result["evidence_docs"] == []
    assert result["citations"] == []
    assert "raw_no_node::" not in result["answer"]
    assert result["follow_up_questions"] == []
