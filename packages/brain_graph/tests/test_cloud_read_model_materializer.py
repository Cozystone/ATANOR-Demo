from __future__ import annotations

import json
from pathlib import Path

from packages.brain_graph import materializers
from packages.brain_graph.materializers import materialize_semantic_cloud_graph
from packages.cloud_brain.read_model import build_cloud_read_model


def _write_store(root: Path) -> None:
    store = root / "store"
    store.mkdir(parents=True, exist_ok=True)
    concepts = {
        "concept:a": {"concept_id": "concept:a", "canonical_name": "Alpha"},
        "concept:b": {"concept_id": "concept:b", "canonical_name": "Beta"},
    }
    relations = {
        "rel:a:b": {
            "relation_id": "rel:a:b",
            "source_concept_id": "concept:a",
            "relation": "supports",
            "target_concept_id": "concept:b",
        }
    }
    (store / "semantic_concepts.json").write_text(json.dumps(concepts), encoding="utf-8")
    (store / "semantic_relations.json").write_text(json.dumps(relations), encoding="utf-8")


def test_materializer_uses_read_model(monkeypatch, tmp_path: Path) -> None:
    _write_store(tmp_path)
    build_cloud_read_model(tmp_path, limit_nodes=10, limit_edges=10)
    monkeypatch.setattr(materializers, "CLOUD_ROOT", tmp_path)

    result = materialize_semantic_cloud_graph(10, 10)

    assert result.available is True
    assert len(result.nodes) == 2
    assert len(result.edges) == 1
    assert result.stats["read_model_available"] is True
    assert result.stats["performance"]["full_store_scan"] is False
    assert result.stats["visible_scale_chunks"] >= 1
    assert result.stats["scale_chunks_are_semantic_nodes"] is False
    assert result.stats["all_nodes_rendered"] is False
    assert result.stats["spherical_lod_shell"]["render_mode"] == "spherical_lod_shell"
    assert all(chunk["is_semantic_node"] is False for chunk in result.stats["density_chunks"])
    assert {node["id"] for node in result.nodes} == {"concept:a", "concept:b"}


def test_materializer_does_not_fallback_scan_when_read_model_missing(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(materializers, "CLOUD_ROOT", tmp_path)

    result = materialize_semantic_cloud_graph(10, 10)

    assert result.available is True
    assert result.nodes == []
    assert result.edges == []
    assert result.partial is True
    assert result.stats["read_model_available"] is False
    assert result.stats["graph_unavailable_reason"] == "cloud_graph_sample_index_missing"
    assert result.stats["performance"]["full_store_scan"] is False
