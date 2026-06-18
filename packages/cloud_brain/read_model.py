from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .status_cache import (
    DEFAULT_CLOUD_ROOT,
    INDEX_VERSION,
    fast_store_signature,
    load_graph_sample_cache,
    load_manifest,
    load_status_cache,
    read_json,
    semantic_store_paths,
    store_signature,
    utc_now_iso,
    write_graph_sample_cache,
    write_manifest,
    write_status_cache,
)


def _elapsed_ms(started_at: float) -> float:
    return round((time.perf_counter() - started_at) * 1000.0, 3)


def _candidate_pairs(count: int) -> int | str:
    pairs = count * max(0, count - 1) // 2
    return str(pairs) if pairs > 9_007_199_254_740_991 else pairs


def _read_latest_growth_run(root: str | Path) -> dict[str, Any] | None:
    runs_dir = semantic_store_paths(root)["growth_runs"]
    if not runs_dir.exists():
        return None
    for path in sorted(runs_dir.glob("*.json"), key=lambda item: item.stat().st_mtime_ns, reverse=True):
        payload = read_json(path, None)
        if isinstance(payload, dict):
            return {
                "run_id": payload.get("run_id"),
                "sentences_processed": payload.get("sentences_processed"),
                "concepts_created": payload.get("concepts_created"),
                "concepts_merged": payload.get("concepts_merged"),
                "relations_created": payload.get("relations_created"),
                "relations_strengthened": payload.get("relations_strengthened"),
                "evidence_added": payload.get("evidence_added"),
            }
    return None


def _read_feeder_state(root: str | Path) -> dict[str, Any]:
    payload = read_json(semantic_store_paths(root)["feeder_state"], {})
    return payload if isinstance(payload, dict) else {}


def _read_shard_index(root: str | Path) -> dict[str, Any]:
    payload = read_json(semantic_store_paths(root)["shard_index"], {})
    return payload if isinstance(payload, dict) else {}


def _status_from_cache_payload(root: str | Path, cache: dict[str, Any], *, cache_hit: bool, started_at: float) -> dict[str, Any]:
    current_signature = fast_store_signature(root)
    cached_signature = cache.get("store_signature") if isinstance(cache.get("store_signature"), dict) else {}
    cached_signature = {
        key: cached_signature.get(key)
        for key in ("concepts", "relations", "evidence", "shard_index", "feeder_state")
    }
    shard_index = _read_shard_index(root)
    feeder_state = _read_feeder_state(root)
    web_seed_active = bool(feeder_state.get("enabled"))
    concept_count = int(cache.get("concepts") or cache.get("node_count") or 0)
    relation_count = int(cache.get("relations") or cache.get("edge_count") or 0)
    shard_concepts = int(shard_index.get("concepts_count") or 0)
    shard_relations = int(shard_index.get("relations_count") or 0)
    main_store_concepts = int(cache.get("main_store_concepts") or 0)
    main_store_relations = int(cache.get("main_store_relations") or 0)
    if shard_concepts > 0:
        concept_count = max(concept_count, shard_concepts + main_store_concepts, shard_concepts)
    if shard_relations > 0:
        relation_count = max(relation_count, shard_relations + main_store_relations, shard_relations)
    evidence_count = int(cache.get("evidence") or 0)
    performance = dict(cache.get("performance") if isinstance(cache.get("performance"), dict) else {})
    performance.update(
        {
            "cache_hit": cache_hit,
            "status_cache_ms": _elapsed_ms(started_at),
            "sample_load_ms": 0.0,
            "payload_build_ms": 0.0,
            "serialization_ms": 0.0,
            "total_ms": _elapsed_ms(started_at),
            "payload_bytes": int(cache.get("payload_bytes") or 0),
            "full_store_scan": False,
            "index_rebuild_during_request": False,
        }
    )
    return {
        **cache,
        "index_version": int(cache.get("index_version") or INDEX_VERSION),
        "proof_store_path": str(semantic_store_paths(root)["store"]),
        "store_path": str(semantic_store_paths(root)["store"]),
        "store_backend": str(cache.get("store_backend") or "local_semantic_proof_store"),
        "concepts": concept_count,
        "relations": relation_count,
        "evidence": evidence_count,
        "node_count": concept_count,
        "edge_count": relation_count,
        "implicit_candidate_pairs": _candidate_pairs(concept_count),
        "last_growth_run": cache.get("last_growth_run") or _read_latest_growth_run(root),
        "old_mirror_snapshot_used_as_live_cloud": False,
        "proof_store_only": True,
        "local_brain_write": False,
        "external_llm_used": False,
        "external_sllm_used": False,
        "global_cloud_claim": False,
        "self_growth_active": web_seed_active,
        "web_seed_feeder_active": web_seed_active,
        "web_seed_feeder_status": feeder_state.get("last_status") or ("listening" if web_seed_active else "disabled"),
        "sample_or_proof_data_visible": bool(concept_count or relation_count),
        "data_provenance_label": "semantic_cloud_read_model",
        "read_model_available": cache_hit,
        "read_model_stale": cached_signature != current_signature,
        "stale": cached_signature != current_signature,
        "graph_unavailable_reason": cache.get("graph_unavailable_reason"),
        "provenance_summary": {
            "semantic_cloud_proof_store": {
                "concepts": concept_count,
                "relations": relation_count,
                "evidence": evidence_count,
            },
            "mirror_snapshot": {"used_as_live_cloud": False},
        },
        "performance": performance,
    }


def load_cloud_read_model_status(root: str | Path = DEFAULT_CLOUD_ROOT) -> dict[str, Any]:
    started_at = time.perf_counter()
    cache = load_status_cache(root)
    if isinstance(cache, dict):
        return _status_from_cache_payload(root, cache, cache_hit=True, started_at=started_at)
    return _status_from_cache_payload(
        root,
        {
            "concepts": 0,
            "relations": 0,
            "evidence": 0,
            "read_model_available": False,
            "read_model_stale": True,
            "graph_unavailable_reason": "cloud_read_model_missing",
            "created_at": utc_now_iso(),
            "store_signature": {},
        },
        cache_hit=False,
        started_at=started_at,
    )


def load_fast_graph_sample(
    root: str | Path = DEFAULT_CLOUD_ROOT,
    *,
    limit_nodes: int = 1200,
    limit_edges: int = 2400,
) -> dict[str, Any]:
    started_at = time.perf_counter()
    status = load_cloud_read_model_status(root)
    sample_started_at = time.perf_counter()
    sample = load_graph_sample_cache(root)
    if not isinstance(sample, dict):
        return {
            "nodes": [],
            "edges": [],
            "bounded": False,
            "proof_store_only": True,
            "read_model_available": False,
            "graph_unavailable_reason": "cloud_graph_sample_index_missing",
            "counts": {
                "concepts": int(status.get("concepts") or 0),
                "relations": int(status.get("relations") or 0),
                "evidence": int(status.get("evidence") or 0),
            },
            "performance": {
                "cache_hit": False,
                "status_cache_ms": float((status.get("performance") or {}).get("status_cache_ms") or 0.0),
                "sample_load_ms": _elapsed_ms(sample_started_at),
                "payload_build_ms": 0.0,
                "serialization_ms": 0.0,
                "total_ms": _elapsed_ms(started_at),
                "payload_bytes": 0,
                "full_store_scan": False,
                "index_rebuild_during_request": False,
            },
        }

    nodes = list(sample.get("nodes") or [])[: max(0, int(limit_nodes))]
    node_ids = {str(node.get("id") or node.get("concept_id")) for node in nodes}
    edges = [
        edge for edge in list(sample.get("edges") or [])
        if str(edge.get("source")) in node_ids and str(edge.get("target")) in node_ids
    ][: max(0, int(limit_edges))]
    counts = dict(sample.get("counts") if isinstance(sample.get("counts"), dict) else {})
    counts.setdefault("concepts", int(status.get("concepts") or 0))
    counts.setdefault("relations", int(status.get("relations") or 0))
    counts.setdefault("evidence", int(status.get("evidence") or 0))
    paths = semantic_store_paths(root)
    sample_path = paths["graph_sample"] if paths["graph_sample"].exists() else paths["legacy_graph_sample"]
    try:
        payload_bytes = int(sample_path.stat().st_size)
    except FileNotFoundError:
        payload_bytes = int(sample.get("payload_bytes") or 0)
    performance = dict(sample.get("performance") if isinstance(sample.get("performance"), dict) else {})
    performance.update(
        {
            "cache_hit": True,
            "status_cache_ms": float((status.get("performance") or {}).get("status_cache_ms") or 0.0),
            "sample_load_ms": _elapsed_ms(sample_started_at),
            "payload_build_ms": 0.0,
            "serialization_ms": 0.0,
            "total_ms": _elapsed_ms(started_at),
            "payload_bytes": payload_bytes,
            "full_store_scan": False,
            "index_rebuild_during_request": False,
        }
    )
    return {
        **sample,
        "nodes": nodes,
        "edges": edges,
        "bounded": bool(sample.get("bounded")) or len(list(sample.get("nodes") or [])) > len(nodes) or len(list(sample.get("edges") or [])) > len(edges),
        "proof_store_only": True,
        "read_model_available": True,
        "read_model_stale": bool(status.get("read_model_stale") or status.get("stale")),
        "counts": counts,
        "performance": performance,
    }


def _read_evidence_count(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                count += 1
    return count


def _build_sample_from_rows(concepts: list[dict[str, Any]], relations: list[dict[str, Any]], *, limit_nodes: int, limit_edges: int) -> dict[str, Any]:
    nodes = [
        {
            "id": row["concept_id"],
            "label": row.get("canonical_name") or row["concept_id"],
            "concept_id": row["concept_id"],
            "aliases": row.get("aliases", []),
            "language_labels": row.get("language_labels", {}),
            "trust": row.get("trust", 0.5),
            "confidence": row.get("confidence", 0.5),
            "seen_count": row.get("seen_count", 1),
            "source_scope": "cloud",
            "proof_store_only": True,
            "provenance_type": (row.get("metadata", {}).get("provenance_type") if isinstance(row.get("metadata"), dict) else None) or "manual_sample_ingest",
            "source_run_id": row.get("metadata", {}).get("run_id") if isinstance(row.get("metadata"), dict) else None,
            "source_text_hash": (row.get("source_hashes") or [None])[0] if isinstance(row.get("source_hashes"), list) else None,
            "source_label": "Semantic Cloud proof store",
            "is_demo_sample": True,
            "is_autonomous_growth": False,
            "local_brain_write": False,
        }
        for row in concepts[:limit_nodes]
        if row.get("concept_id")
    ]
    node_ids = {str(node["id"]) for node in nodes}
    edges = [
        {
            "id": row["relation_id"],
            "source": row["source_concept_id"],
            "target": row["target_concept_id"],
            "relation": row["relation"],
            "weight": row.get("weight", 0.5),
            "confidence": row.get("confidence", 0.5),
            "seen_count": row.get("seen_count", 1),
            "source_scope": "cloud",
            "proof_store_only": True,
            "local_brain_write": False,
        }
        for row in relations
        if row.get("relation_id")
        and row.get("source_concept_id") in node_ids
        and row.get("target_concept_id") in node_ids
    ][:limit_edges]
    return {"nodes": nodes, "edges": edges}


def build_cloud_read_model(
    root: str | Path = DEFAULT_CLOUD_ROOT,
    *,
    limit_nodes: int = 1200,
    limit_edges: int = 2400,
) -> dict[str, Any]:
    started_at = time.perf_counter()
    from .semantic_store import SemanticCloudStore

    store = SemanticCloudStore(root)
    concepts = list(store.load_concepts().values())
    relations = list(store.load_relations().values())
    sample = _build_sample_from_rows(concepts, relations, limit_nodes=limit_nodes, limit_edges=limit_edges)
    current_signature = store_signature(root)
    paths = semantic_store_paths(root)
    evidence_count = _read_evidence_count(paths["evidence"])
    status_payload = {
        "index_version": INDEX_VERSION,
        "created_at": utc_now_iso(),
        "store_signature": current_signature,
        "proof_store_path": str(paths["store"]),
        "store_path": str(paths["store"]),
        "store_backend": "local_semantic_proof_store",
        "concepts": len(concepts),
        "relations": len(relations),
        "evidence": evidence_count,
        "node_count": len(concepts),
        "edge_count": len(relations),
        "last_growth_run": _read_latest_growth_run(root),
        "old_mirror_snapshot_used_as_live_cloud": False,
        "proof_store_only": True,
        "read_model_available": True,
        "read_model_stale": False,
        "sample_or_proof_data_visible": bool(concepts or relations),
        "performance": {
            "cache_hit": False,
            "status_cache_ms": 0.0,
            "sample_load_ms": 0.0,
            "payload_build_ms": _elapsed_ms(started_at),
            "serialization_ms": 0.0,
            "total_ms": _elapsed_ms(started_at),
            "payload_bytes": 0,
            "full_store_scan": True,
            "index_rebuild_during_request": False,
        },
    }
    sample_payload = {
        "index_version": INDEX_VERSION,
        "created_at": utc_now_iso(),
        "store_signature": current_signature,
        "nodes": sample["nodes"],
        "edges": sample["edges"],
        "bounded": len(concepts) > limit_nodes or len(relations) > limit_edges,
        "proof_store_only": True,
        "read_model_available": True,
        "compression_used": False,
        "semantic_aggregate_nodes_used": False,
        "counts": {
            "concepts": len(concepts),
            "relations": len(relations),
            "evidence": evidence_count,
        },
        "performance": {**status_payload["performance"], "full_store_scan": True},
    }
    manifest = {
        "index_version": INDEX_VERSION,
        "created_at": utc_now_iso(),
        "store_signature": current_signature,
        "status_cache": paths["status_cache"].name,
        "graph_sample": paths["graph_sample"].name,
        "sample_nodes": len(sample_payload["nodes"]),
        "sample_edges": len(sample_payload["edges"]),
        "logical_nodes": len(concepts),
        "logical_edges": len(relations),
        "full_store_scan": True,
        "request_time_rebuild": False,
    }
    write_status_cache(root, status_payload)
    write_graph_sample_cache(root, sample_payload)
    write_manifest(root, manifest)
    return {
        "status": load_cloud_read_model_status(root),
        "sample": load_fast_graph_sample(root, limit_nodes=limit_nodes, limit_edges=limit_edges),
        "manifest": load_manifest(root) or manifest,
        "rebuilt": True,
        "performance": {
            "total_ms": _elapsed_ms(started_at),
            "full_store_scan": True,
            "index_rebuild_during_request": False,
        },
    }
