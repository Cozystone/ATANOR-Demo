from __future__ import annotations

import socket
from pathlib import Path

from knowledge_bakery import build_memory
from rag_engine import LocalSynthesizer, query_graphrag


def test_local_synthesizer_builds_autonomous_context_without_templates() -> None:
    result = LocalSynthesizer().synthesize(
        "What is GraphRAG?",
        [{"chunk_id": "doc#1", "doc_id": "doc", "text": "GraphRAG uses KnowledgeGraph for grounded retrieval."}],
        [{"id": "graphrag", "label": "GraphRAG"}, {"id": "knowledgegraph", "label": "KnowledgeGraph"}],
        [{"source": "graphrag", "relation": "uses", "target": "knowledgegraph"}],
        [["graphrag", "uses", "knowledgegraph"]],
    )

    assert result["answer_engine"]["name"] == "ATANOR LocalSynthesizer"
    assert result["answer_engine"]["external_llm"] is False
    assert result["answer_engine"]["network_barrier"] == "sealed_for_generation"
    assert result["answer_engine"]["surface_generation"] == "local_autonomous_context_synthesis"
    assert result["answer_engine"]["prediction_basis"] == "ghost_context_bundle_autonomous_synthesis"
    assert "<context>" in result["answer_engine"]["context_block"]
    assert "raw_no_node::" not in result["answer"]
    assert "CONTROL_INTENT" not in result["answer"]


def test_ghost_lazy_fetch_synthesis_does_not_open_network_socket(tmp_path: Path, monkeypatch) -> None:
    cleaned = tmp_path / "data" / "cleaned"
    ontology = tmp_path / "data" / "ontology"
    memory = tmp_path / "data" / "memory"
    cleaned.mkdir(parents=True)
    ontology.mkdir(parents=True)
    (cleaned / "ghost.md").write_text(
        "GhostTopology signals hashes first. PayloadVault resolves raw text from local SQLite WAL only.",
        encoding="utf-8",
    )
    (ontology / "nodes.json").write_text("[]", encoding="utf-8")
    (ontology / "edges.json").write_text("[]", encoding="utf-8")
    build_memory(str(cleaned), str(ontology), str(memory))

    def blocked_connect(*_args, **_kwargs):
        raise AssertionError("generation path attempted an outbound socket connection")

    monkeypatch.setattr(socket.socket, "connect", blocked_connect)
    result = query_graphrag("How does PayloadVault resolve text?", memory_dir=str(memory))

    assert result["answer_kind"] == "local_synthesis"
    assert result["answer_engine"]["external_llm"] is False
    assert result["answer_engine"]["surface_generation"] == "local_autonomous_context_synthesis"
    assert result["answer_engine"]["diagnostics"]["outbound_http_calls"] == 0
    assert result["retrieval_trace"]["fetch_sequence"]


def test_local_synthesizer_prioritizes_newer_temporal_context_without_deleting_old_fact() -> None:
    result = LocalSynthesizer().synthesize(
        "ATANOR temporal behavior",
        [
            {
                "chunk_id": "old#payload",
                "doc_id": "old",
                "text": "2023 ATANOR used a one-shot graph batch.",
                "score": 0.2,
                "temporal": {
                    "timestamp": "2023-01-01T00:00:00Z",
                    "combined_weight": 0.2,
                    "collision_detected": True,
                    "rank": 2,
                },
                "temporal_rank": 2,
            },
            {
                "chunk_id": "new#payload",
                "doc_id": "new",
                "text": "2026 ATANOR uses Ghost Shell temporal decay and continuous ingestion.",
                "score": 1.4,
                "temporal": {
                    "timestamp": "2026-06-13T00:00:00Z",
                    "combined_weight": 1.4,
                    "collision_detected": True,
                    "rank": 1,
                },
                "temporal_rank": 1,
            },
        ],
        [],
        [],
        [],
    )

    answer = result["answer"]
    diagnostics = result["answer_engine"]["diagnostics"]
    assert diagnostics["temporal_collision_detected"] is True
    assert diagnostics["temporal_priority"][0]["timestamp"] == "2026-06-13T00:00:00Z"
    assert "2026 ATANOR uses Ghost Shell temporal decay" in answer
    assert "2023 ATANOR used a one-shot graph batch" in answer
