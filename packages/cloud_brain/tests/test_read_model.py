from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.cloud_brain.read_model import build_cloud_read_model, load_cloud_read_model_status, load_fast_graph_sample
from packages.cloud_brain.semantic_store import SemanticCloudStore


def _write_store(root: Path) -> None:
    store = root / "store"
    store.mkdir(parents=True, exist_ok=True)
    concepts = {
        "concept:kubernetes": {
            "concept_id": "concept:kubernetes",
            "canonical_name": "Kubernetes",
            "aliases": ["k8s"],
            "trust": 0.8,
            "confidence": 0.9,
            "seen_count": 2,
            "source_hashes": ["source-a"],
        },
        "concept:container": {
            "concept_id": "concept:container",
            "canonical_name": "Container",
            "aliases": ["container"],
            "trust": 0.8,
            "confidence": 0.9,
            "seen_count": 2,
            "source_hashes": ["source-a"],
        },
    }
    relations = {
        "rel:kubernetes:manages:container": {
            "relation_id": "rel:kubernetes:manages:container",
            "source_concept_id": "concept:kubernetes",
            "relation": "manages",
            "target_concept_id": "concept:container",
            "weight": 0.72,
            "confidence": 0.82,
            "seen_count": 2,
            "source_hashes": ["source-a"],
        }
    }
    (store / "semantic_concepts.json").write_text(json.dumps(concepts), encoding="utf-8")
    (store / "semantic_relations.json").write_text(json.dumps(relations), encoding="utf-8")
    (store / "semantic_evidence.jsonl").write_text(json.dumps({"source_hash": "source-a"}) + "\n", encoding="utf-8")


def test_build_and_read_cloud_read_model(tmp_path: Path) -> None:
    _write_store(tmp_path)

    result = build_cloud_read_model(tmp_path, limit_nodes=10, limit_edges=10)
    assert result["rebuilt"] is True
    assert (tmp_path / "index" / "fast_graph_sample.json").exists()
    assert result["status"]["concepts"] == 2
    assert result["status"]["relations"] == 1
    assert result["sample"]["nodes"]
    assert result["sample"]["edges"]

    status = load_cloud_read_model_status(tmp_path)
    sample = load_fast_graph_sample(tmp_path, limit_nodes=5, limit_edges=5)
    assert status["performance"]["cache_hit"] is True
    assert status["performance"]["full_store_scan"] is False
    assert sample["performance"]["cache_hit"] is True
    assert sample["performance"]["index_rebuild_during_request"] is False


def test_fast_read_path_does_not_load_full_store(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _write_store(tmp_path)
    build_cloud_read_model(tmp_path, limit_nodes=10, limit_edges=10)

    def fail_full_load(*args: object, **kwargs: object) -> object:
        raise AssertionError("fast read path must not load full semantic store")

    monkeypatch.setattr(SemanticCloudStore, "load_concepts", fail_full_load)
    monkeypatch.setattr(SemanticCloudStore, "load_relations", fail_full_load)
    status = load_cloud_read_model_status(tmp_path)
    sample = load_fast_graph_sample(tmp_path, limit_nodes=5, limit_edges=5)

    assert status["concepts"] == 2
    assert sample["nodes"]
    assert sample["performance"]["full_store_scan"] is False


def test_fast_status_does_not_scan_growth_shard_directory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _write_store(tmp_path)
    build_cloud_read_model(tmp_path, limit_nodes=10, limit_edges=10)

    from packages.cloud_brain import status_cache

    def fail_shard_scan(*args: object, **kwargs: object) -> object:
        raise AssertionError("fast status must not scan every growth shard")

    monkeypatch.setattr(status_cache, "shards_signature", fail_shard_scan)
    status = load_cloud_read_model_status(tmp_path)
    sample = load_fast_graph_sample(tmp_path, limit_nodes=5, limit_edges=5)

    assert status["performance"]["full_store_scan"] is False
    assert sample["performance"]["full_store_scan"] is False
    assert sample["performance"]["index_rebuild_during_request"] is False


def test_missing_read_model_returns_fast_unavailable_view(tmp_path: Path) -> None:
    status = load_cloud_read_model_status(tmp_path)
    sample = load_fast_graph_sample(tmp_path, limit_nodes=5, limit_edges=5)

    assert status["read_model_available"] is False
    assert status["performance"]["full_store_scan"] is False
    assert sample["nodes"] == []
    assert sample["edges"] == []
    assert sample["graph_unavailable_reason"] == "cloud_graph_sample_index_missing"
    assert sample["performance"]["index_rebuild_during_request"] is False
