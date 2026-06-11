from ontology_forge import run_ontology


def test_run_ontology_extracts_nodes_and_edges(tmp_path):
    cleaned = tmp_path / "cleaned"
    cleaned.mkdir()
    (cleaned / "doc1.txt").write_text(
        "# GraphRAG\nGraphRAG uses KnowledgeGraph. Evidence reduces HallucinationRisk. GraphRAG GraphRAG",
        encoding="utf-8",
    )

    result = run_ontology(str(cleaned), str(tmp_path / "ontology"))

    assert result["report"]["node_count"] >= 3
    assert any(edge["relation"] == "uses" for edge in result["edges"])
    assert any(node["type"] == "verb" for node in result["nodes"])
    assert any(node["type"] == "phrase" for node in result["nodes"])
    assert any(edge["relation"] in {"acts_on", "co_occurs", "precedes"} for edge in result["edges"])
    assert (tmp_path / "ontology" / "nodes.json").exists()
