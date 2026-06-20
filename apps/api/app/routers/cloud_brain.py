from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.brain_graph_state import build_brain_graph_states
from app.services.cloud_broker_client import CloudBrokerClient, CloudBrokerConfig, CloudBrokerError, public_fragment_from_text
from app.services.hybrid_network_manager import GraphFragmentEnvelope
from app.services.network_config import NetworkConfig
from app.services.alpha_services import alpha_service
from knowledge_bakery import daemon_status, memory_status, run_synaptic_decay, tick_daemon
from packages.cloud_brain.ingestion import cloud_store_status, query_ingested_fragments
from packages.cloud_brain.contributor_node import contributor_status
from packages.cloud_brain.proof_semantic_growth import run_semantic_cloud_growth_proof
from packages.cloud_brain.prove_controlled_self_growth import write_controlled_self_growth_proof
from packages.cloud_brain.remote_proof import load_last_remote_proof, write_remote_cloud_brain_proof
from packages.cloud_brain.prove_spherical_chunk_materialization import write_spherical_chunk_materialization_proof
from packages.cloud_brain.anna_archive_provider import fetch_metadata as fetch_anna_archive_metadata
from packages.cloud_brain.anna_archive_provider import load_config as load_anna_archive_config
from packages.cloud_brain.anna_archive_provider import metadata_to_semantic_text as anna_metadata_to_semantic_text
from packages.cloud_brain.sphere_materialization import (
    get_cloud_node,
    get_sphere_tile,
    get_sphere_tile_children,
    materialize_sphere_tile,
    sphere_manifest,
)
from packages.cloud_brain.web_seed_feeder import feeder_status, run_once as run_web_seed_feeder_once
from packages.cloud_brain.semantic_attach import attach_semantic_cloud_for_query
from packages.cloud_brain.semantic_growth import MAX_ACCELERATION_BATCH_SIZE, ingest_semantic_acceleration_batch, ingest_semantic_source
from packages.cloud_brain.semantic_handoff import write_semantic_cloud_growth_handoff
from packages.cloud_brain.semantic_store import get_semantic_cloud_growth_status
from packages.cloud_brain.read_model import build_cloud_read_model, load_fast_graph_sample
from packages.cloud_brain.continuous_learning import CloudSurfaceLearningLoop
from packages.cloud_brain.verified_payload_feeder import PayloadSourcePolicy, VerifiedPayloadFeeder, payload_from_mapping
from rag_engine.ghost_graph import GhostTopology
from rag_engine.fusion import epistemic_uncertainty, local_density_score, route_ratio, weighted_rrf


router = APIRouter(prefix="/api/cloud-brain", tags=["cloud-brain"])

HEX_HASH_RE = re.compile(r"^[0-9a-fA-F]{32,}$")


class CloudBrainQueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=400)
    max_nodes: int = Field(default=48, ge=1, le=240)
    max_depth: int = Field(default=3, ge=1, le=6)


class CloudBrainIngestRequest(BaseModel):
    source_url: str | None = Field(default=None, max_length=800)
    text: str | None = Field(default=None, max_length=20_000)
    dry_run: bool = True


class CloudBrainConsolidateRequest(BaseModel):
    force: bool = False


class CloudBrainPruneRequest(BaseModel):
    dry_run: bool = True
    min_weight: float = Field(default=0.05, ge=0.0, le=1.0)
    max_idle_days: int = Field(default=30, ge=1, le=3650)


class SemanticCloudIngestRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20_000)
    source_id: str = Field(min_length=1, max_length=240)
    language: str = Field(default="auto", pattern="^(ko|en|auto)$")
    url: str | None = Field(default=None, max_length=800)
    title: str | None = Field(default=None, max_length=400)
    license: str | None = Field(default=None, max_length=120)
    usage_allowed: bool = False


class SemanticCloudAttachRequest(BaseModel):
    query: str = Field(min_length=1, max_length=400)
    limit: int = Field(default=8, ge=1, le=48)


class SemanticCloudAccelerateRequest(BaseModel):
    batch_size: int = Field(default=1000, ge=1, le=MAX_ACCELERATION_BATCH_SIZE)
    async_run: bool = False


_SEMANTIC_ACCELERATION_LOCK = threading.Lock()
_SEMANTIC_ACCELERATION_STATE: dict[str, Any] = {
    "running": False,
    "last_result": None,
    "last_error": None,
}


def _run_semantic_acceleration_batch(batch_size: int) -> None:
    if not _SEMANTIC_ACCELERATION_LOCK.acquire(blocking=False):
        return
    try:
        _SEMANTIC_ACCELERATION_STATE.update({"running": True, "last_error": None})
        result = ingest_semantic_acceleration_batch(batch_size=batch_size)
        _SEMANTIC_ACCELERATION_STATE.update({"last_result": result, "last_error": None})
    except Exception as exc:
        _SEMANTIC_ACCELERATION_STATE.update({"last_error": str(exc)})
    finally:
        _SEMANTIC_ACCELERATION_STATE["running"] = False
        _SEMANTIC_ACCELERATION_LOCK.release()


class WebSeedFeederRunRequest(BaseModel):
    force_enabled: bool = False
    force_fetch: bool = False
    max_sources: int | None = Field(default=None, ge=1, le=1000)


class CloudLearningPayloadModel(BaseModel):
    payload_id: str | None = Field(default=None, max_length=240)
    source_type: str = Field(default="manual_public_sentence", max_length=120)
    source_id: str = Field(min_length=1, max_length=240)
    text: str = Field(min_length=1, max_length=2000)
    language: str = Field(default="ko", pattern="^(ko|en|unknown)$")
    provenance_hash: str | None = Field(default=None, max_length=128)
    source_url_or_path: str = Field(default="", max_length=800)
    license_hint: str = Field(default="CC BY-SA 4.0", max_length=120)
    collected_at: str | None = Field(default=None, max_length=80)
    is_private: bool = False
    is_generated: bool = False
    is_eval_row: bool = False
    quality_flags: list[str] = Field(default_factory=list)
    target_store: str = Field(default="verified_store_v0_candidate", pattern="^(verified_store_v0_candidate|verified_store_v0)$")
    learning_mode: str = Field(default="semantic_graph", max_length=80)


class CloudLearningRunRequest(BaseModel):
    dry_run: bool = False
    max_payloads_per_tick: int = Field(default=25, ge=1, le=100)
    max_accepted_per_run: int = Field(default=25, ge=1, le=100)
    promote_to_verified: bool = False
    candidate_store_root: str | None = Field(default=None, max_length=800)
    payloads: list[CloudLearningPayloadModel] = Field(default_factory=list)


class AnnaArchiveMetadataSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=240)
    ingest: bool = False


def _controlled_growth_summary_from_proof(proof: dict[str, Any] | None, *, proof_exists: bool) -> dict[str, Any]:
    proof = proof or {}
    return {
        "proof_exists": proof_exists,
        "controlled_self_growth": bool(proof.get("controlled_self_growth", False)) if proof_exists else False,
        "mode": str(proof.get("mode") or "controlled_fixture_only"),
        "autonomous_broad_crawling": bool(proof.get("autonomous_broad_crawling", False)),
        "fragment_id": proof.get("fragment_id"),
        "alignment_success": bool(proof.get("alignment_success", False)),
        "ingestion_success": bool(proof.get("ingestion_success", False)),
        "query_readback_success": bool(proof.get("query_readback_success", False)),
        "duplicate_fragment": bool(proof.get("duplicate_fragment", False)),
        "nodes_added": int(proof.get("nodes_added") or 0),
        "edges_added": int(proof.get("edges_added") or 0),
        "previous_cloud_nodes": int(proof.get("previous_cloud_nodes") or 0),
        "new_cloud_nodes": int(proof.get("new_cloud_nodes") or 0),
        "previous_cloud_edges": int(proof.get("previous_cloud_edges") or 0),
        "new_cloud_edges": int(proof.get("new_cloud_edges") or 0),
        "local_brain_state": proof.get("local_brain_state") or {
            "local_brain_initialized": False,
            "local_total_nodes": 0,
            "local_total_edges": 0,
        },
        "external_llm_used": bool(proof.get("external_llm_used", False)),
        "external_sllm_used": bool(proof.get("external_sllm_used", False)),
        "rule_based_answer_engine": bool(proof.get("rule_based_answer_engine", False)),
        "final_answer_generation_claimed": bool(proof.get("final_answer_generation_claimed", False)),
    }


def _latest_controlled_growth_summary() -> dict[str, Any]:
    path = Path("data/cloud_brain/proofs/controlled_self_growth_proof.json")
    if not path.exists():
        return _controlled_growth_summary_from_proof(None, proof_exists=False)
    try:
        proof = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return _controlled_growth_summary_from_proof(None, proof_exists=False)
    return _controlled_growth_summary_from_proof(proof, proof_exists=True)


def _remote_broker_snapshot() -> dict[str, Any]:
    config = CloudBrokerConfig.from_env()
    if config.cloud_mode != "remote":
        return {
            "cloud_provider": config.cloud_provider,
            "cloud_mode": config.cloud_mode,
            "broker_state": "disabled" if config.cloud_mode == "disabled" else "local_broker_mode",
            "remote_config": config.public_status(),
        }
    client = CloudBrokerClient(config)
    try:
        remote = client.status()
    except Exception as exc:
        return {
            "cloud_provider": config.cloud_provider,
            "cloud_mode": "remote",
            "broker_state": "remote_error",
            "remote_config": config.public_status(),
            "remote_error": str(exc),
        }
    shards: dict[str, Any] | None = None
    credits: dict[str, Any] | None = None
    try:
        shards = client._request_json("GET", "/cloud/shards")
    except Exception as exc:
        shards = {"state": "remote_error", "error": str(exc)}
    try:
        credits = client.credits(config.node_id)
    except Exception as exc:
        credits = {"state": "remote_error", "error": str(exc), "credits": []}
    try:
        network = client.network()
    except Exception as exc:
        network = {"state": "remote_error", "error": str(exc)}
    try:
        peers = client.peers()
    except Exception as exc:
        peers = {"state": "remote_error", "error": str(exc), "peers": []}
    return {
        "cloud_provider": config.cloud_provider,
        "cloud_mode": "remote",
        "broker_state": "remote_connected",
        "remote_config": config.public_status(),
        "remote_status": remote,
        "remote_shards": shards,
        "remote_credits": credits,
        "remote_network": network,
        "remote_peers": peers,
    }


def _remote_cloudflare_inspection() -> dict[str, Any]:
    config = CloudBrokerConfig.from_env()
    base: dict[str, Any] = {
        "configured": config.remote_enabled,
        "reachable": False,
        "provider": config.cloud_provider,
        "cloud_mode": config.cloud_mode,
        "endpoint_configured": bool(config.endpoint),
        "endpoint": config.endpoint or None,
        "broker_state": "local_broker_mode" if config.cloud_mode != "remote" else "remote_unverified",
        "storage_backend": "unknown",
        "remote_persistence": False,
        "fragment_submit_success": False,
        "fragment_query_success": False,
        "fragment_readback_success": False,
        "remote_fragments_preview_count": 0,
    }
    if not config.remote_enabled:
        base["reason_remote_cloud_brain_not_real"] = "ATANOR_CLOUD_MODE is not remote or ATANOR_CLOUD_ENDPOINT is missing."
        return base
    client = CloudBrokerClient(config)
    try:
        status = client.status()
        base.update(
            {
                "reachable": True,
                "broker_state": str(status.get("broker_state") or "remote_connected"),
                "storage_backend": str(status.get("fragment_store") or status.get("storage_backend") or "unknown"),
                "remote_status": status,
            }
        )
    except Exception as exc:
        base.update(
            {
                "reachable": False,
                "broker_state": "remote_error",
                "error": str(exc),
                "reason_remote_cloud_brain_not_real": f"Remote Cloudflare broker status check failed: {exc}",
            }
        )
        return base
    try:
        query = client.query_fragments("", limit=5)
        fragments = query.get("fragments") if isinstance(query, dict) else []
        base["fragment_query_success"] = True
        base["remote_fragments_preview_count"] = len(fragments) if isinstance(fragments, list) else 0
        base["remote_query_preview"] = query
    except Exception as exc:
        base["fragment_query_success"] = False
        base["query_error"] = str(exc)

    proof = load_last_remote_proof()
    if proof:
        base["last_remote_proof"] = {
            "result": proof.get("result"),
            "proved_at": proof.get("proved_at"),
            "content_hash": proof.get("content_hash"),
            "fragment_submit_success": bool(proof.get("fragment_submit_success")),
            "fragment_query_success": bool(proof.get("fragment_query_success")),
            "fragment_readback_success": bool(proof.get("fragment_readback_success")),
            "remote_persistence": bool(proof.get("remote_persistence")),
        }
        base["fragment_submit_success"] = bool(proof.get("fragment_submit_success"))
        base["fragment_readback_success"] = bool(proof.get("fragment_readback_success"))
        base["remote_persistence"] = bool(proof.get("remote_persistence"))
    if not base["remote_persistence"]:
        base["reason_remote_cloud_brain_not_real"] = "Remote status may be reachable, but submit/query/read-back persistence has not been proven."
    return base


def _cloud_source_inspector() -> dict[str, Any]:
    daemon = daemon_status()
    memory = memory_status()
    graph_states = build_brain_graph_states(daemon=daemon, memory=memory)
    proof_store = cloud_store_status()
    cloud_state = graph_states.get("cloud") or {}
    local_state = graph_states.get("local") or {}
    remote = _remote_cloudflare_inspection()
    contributor = contributor_status()
    local_proof_store = {
        "available": bool(proof_store),
        "fragments": int(proof_store.get("proof_ingested_fragments") or 0),
        "nodes": int(proof_store.get("cloud_total_nodes") or 0),
        "edges": int(proof_store.get("cloud_total_edges") or 0),
        "backend": proof_store.get("cloud_store_backend", "local_proof_store"),
    }
    cloud_mirror_snapshot = {
        "available": bool(cloud_state),
        "nodes": int(cloud_state.get("cloud_total_nodes") or 0),
        "edges": int(cloud_state.get("cloud_total_relations") or 0),
        "source": cloud_state.get("source", "unknown"),
        "source_is_remote": bool(cloud_state.get("public_cloud_backend_enabled", False)),
        "is_stale": bool(cloud_state.get("is_stale", False)),
        "is_growing": bool(cloud_state.get("is_growing", False)),
    }
    active_source_mode = "local_broker_mode"
    if remote.get("reachable") and remote.get("remote_persistence") and remote.get("fragment_readback_success"):
        active_source_mode = "remote_cloudflare_broker"
    elif contributor.get("available") and contributor.get("network_state") == "active_single_peer":
        active_source_mode = "single_peer_contributor_network"
    elif cloud_mirror_snapshot["available"] and cloud_mirror_snapshot["nodes"] > 0:
        active_source_mode = "cloud_mirror_snapshot"
    elif local_proof_store["available"] and local_proof_store["fragments"] > 0:
        active_source_mode = "local_proof_store"

    return {
        "schema": "atanor.cloud-brain-source-inspector.v1",
        "active_source_mode": active_source_mode,
        "contributor_network": contributor,
        "local_proof_store": local_proof_store,
        "cloud_mirror_snapshot": cloud_mirror_snapshot,
        "remote_cloudflare_broker": remote,
        "local_brain_state": {
            "local_brain_initialized": bool(local_state.get("local_brain_initialized", False)),
            "local_total_nodes": int(local_state.get("local_total_nodes") or 0),
            "local_total_edges": int(local_state.get("local_total_relations") or local_state.get("local_total_edges") or 0),
        },
        "honest_warning": (
            "You are viewing a verified remote Cloud Brain broker."
            if active_source_mode == "remote_cloudflare_broker"
            else "You are not viewing the live remote Cloud Brain. This view is local proof, local broker, or mirror snapshot."
        ),
    }


def _status_shell(daemon: dict[str, Any], memory: dict[str, Any] | None = None) -> dict[str, Any]:
    memory = memory or memory_status()
    graph_states = build_brain_graph_states(daemon=daemon, memory=memory)
    cloud_state = graph_states["cloud"]
    local_state = graph_states["local"]
    proof_store = cloud_store_status()
    semantic_status = get_semantic_cloud_growth_status()
    semantic_nodes = int(semantic_status.get("concepts") or semantic_status.get("node_count") or 0)
    semantic_edges = int(semantic_status.get("relations") or semantic_status.get("edge_count") or 0)
    cloud_nodes = semantic_nodes or int(cloud_state.get("cloud_total_nodes") or 0) + int(proof_store.get("cloud_total_nodes") or 0)
    cloud_edges = semantic_edges or int(cloud_state.get("cloud_total_relations") or 0) + int(proof_store.get("cloud_total_edges") or 0)
    web_feeder_state = feeder_status()
    audit = graph_states.get("audit") or {
        "operator_graph_source": cloud_state.get("source", "unavailable"),
        "render_graph_endpoint": "/api/graph/subgraph",
        "public_cloud_backend_enabled": False,
        "uses_fake_growth_counters": False,
    }
    return {
        "name": "Cloud Brain",
        "mode": "shared-public-ontology-control-plane",
        "implementation": "local-companion-backed",
        "state": daemon.get("state", "idle"),
        "viewer_only_on_deploy": True,
        "public_cloud_backend_enabled": False,
        "local_required": True,
        "counts": {
            "nodes": cloud_nodes,
            "edges": cloud_edges,
            "events": int(memory.get("event_count") or daemon.get("latest_event_count") or 0),
            "rounds": int(daemon.get("total_rounds") or 0),
            "learned_rounds": int(daemon.get("learned_rounds") or 0),
        },
        "cloud_graph_state": {
            **cloud_state,
            "cloud_total_nodes": cloud_nodes,
            "cloud_total_relations": cloud_edges,
            "cloud_store_backend": proof_store.get("cloud_store_backend", "local_proof_store"),
            "proof_ingested_fragments": int(proof_store.get("proof_ingested_fragments") or 0),
            "proof_store_nodes": int(proof_store.get("cloud_total_nodes") or 0),
            "proof_store_edges": int(proof_store.get("cloud_total_edges") or 0),
            "semantic_read_model_nodes": semantic_nodes,
            "semantic_read_model_relations": semantic_edges,
            "semantic_read_model_performance": semantic_status.get("performance") or {},
            "full_store_scan": False,
            "index_rebuild_during_request": False,
        },
        "controlled_self_growth_state": {
            "enabled": True,
            "mode": "controlled_fixture_only",
            "last_ingestion_success": bool(proof_store.get("last_ingestion_success", False)),
            "last_ingested_fragment_id": proof_store.get("last_ingested_fragment_id"),
            "autonomous_broad_crawling": False,
        },
        "local_graph_state": local_state,
        "web_feeder_state": web_feeder_state,
        "data_source_audit": audit,
        "synaptic_lifecycle": [
            "virtual_edge",
            "potentiation",
            "consolidation",
            "decay",
            "pruning",
        ],
        "lab_integration_order": [
            "local_private_graph",
            "governed_web_search",
            "cloud_brain_candidate_fragments",
            "working_memory_activation",
            "native_graph_token_generation",
            "guardrail_promotion_check",
        ],
        "answer_policy": {
            "external_llm": False,
            "local_quantized_llm": False,
            "pretrained_generation_weights": False,
            "template_only_answers": False,
        },
    }


def _cloud_fragment_raw_dir() -> Path:
    root = Path("data/raw/cloud_brain")
    root.mkdir(parents=True, exist_ok=True)
    return root


def _memory_db_path() -> Path:
    status = memory_status()
    return Path(str(status.get("db_path") or "data/memory/homage.db"))


def _connect_memory_readonly() -> sqlite3.Connection | None:
    db_path = _memory_db_path()
    if not db_path.exists():
        return None
    uri = f"file:{db_path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return bool(row)


def _ghost_node_from_row(row: sqlite3.Row) -> dict[str, Any]:
    node_hash = str(row["node_hash"])
    return {
        "id": node_hash,
        "node_hash": node_hash,
        "label": f"ghost:{node_hash[:12]}",
        "type": "ghost_hash",
        "x": float(row["dim0"] or 0.0) if "dim0" in row.keys() else 0.0,
        "y": float(row["dim1"] or 0.0) if "dim1" in row.keys() else 0.0,
        "z": float(row["dim2"] or 0.0) if "dim2" in row.keys() else 0.0,
        "payload_resolved": False,
    }


def _fallback_fragment_from_cloud_raw(concept_id: str, *, max_nodes: int, max_edges: int) -> dict[str, Any]:
    """Build hash-only topology from local public fragment files when Ghost Shell is empty.

    This keeps the peer payload contract alive during a fresh local broker test:
    `/ingest` can append a public fragment before the heavier memory builder has
    materialized ghost tables. Raw text stays disk-bound and is never exported.
    """

    query = concept_id.strip().lower()
    if not query:
        return {"nodes": [], "edges": [], "concept_ids": []}
    raw_dir = _cloud_fragment_raw_dir()
    candidates: list[tuple[float, Path, str]] = []
    for path in sorted(raw_dir.glob("cloud-fragment-*.md"), key=lambda item: item.stat().st_mtime, reverse=True)[:24]:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        score = 1.0 if query in text.lower() else 0.0
        if score <= 0:
            tokens = {token for token in re.split(r"[^0-9A-Za-z가-힣_+-]+", query) if token}
            lowered = text.lower()
            score = sum(1.0 for token in tokens if token.lower() in lowered)
        if score > 0:
            candidates.append((score, path, text))
    if not candidates:
        return {"nodes": [], "edges": [], "concept_ids": [concept_id]}

    _, path, text = candidates[0]
    words = [
        token
        for token in re.split(r"[^0-9A-Za-z가-힣_+-]+", text)
        if len(token) >= 3 and token.lower() not in {"source", "inline", "cloud", "brain"}
    ]
    ordered_terms = list(dict.fromkeys([concept_id, *words]))[: max(1, min(max_nodes, 18))]
    nodes: list[dict[str, Any]] = []
    for index, term in enumerate(ordered_terms):
        node_hash = hashlib.sha256(f"{path.name}:{term}".encode("utf-8", errors="ignore")).hexdigest()
        angle = (index / max(1, len(ordered_terms))) * 6.283185307179586
        radius = 0.35 + 0.04 * index
        nodes.append(
            {
                "id": node_hash,
                "node_hash": node_hash,
                "label": term[:48],
                "type": "cloud_fragment_hash",
                "x": round(radius * math.cos(angle), 6),
                "y": round(radius * math.sin(angle), 6),
                "z": round((index % 5 - 2) * 0.08, 6),
                "payload_resolved": False,
            }
        )
    edges: list[dict[str, Any]] = []
    for index in range(max(0, min(len(nodes) - 1, max_edges))):
        source_hash = nodes[index]["node_hash"]
        target_hash = nodes[index + 1]["node_hash"]
        edges.append(
            {
                "source_hash": source_hash,
                "target_hash": target_hash,
                "source": source_hash,
                "target": target_hash,
                "weight": round(max(0.1, 0.72 - index * 0.03), 3),
            }
        )
    return {
        "nodes": nodes,
        "edges": edges[:max_edges],
        "concept_ids": list(dict.fromkeys([concept_id, *ordered_terms[:6]])),
    }


def _local_fragment_for_concept(concept_id: str, *, max_nodes: int, max_edges: int) -> dict[str, Any]:
    concept_id = concept_id.strip()
    if not concept_id:
        return {"nodes": [], "edges": [], "concept_ids": []}

    conn = _connect_memory_readonly()
    if conn is None:
        return _fallback_fragment_from_cloud_raw(concept_id, max_nodes=max_nodes, max_edges=max_edges)
    try:
        if not (_table_exists(conn, "ghost_nodes") and _table_exists(conn, "ghost_edges")):
            return _fallback_fragment_from_cloud_raw(concept_id, max_nodes=max_nodes, max_edges=max_edges)
        seed_hashes: list[str] = []
        if HEX_HASH_RE.match(concept_id):
            row = conn.execute("SELECT node_hash FROM ghost_nodes WHERE node_hash = ? LIMIT 1", (concept_id,)).fetchone()
            if row:
                seed_hashes.append(str(row["node_hash"]))
        if not seed_hashes:
            topology = GhostTopology(_memory_db_path().parent)
            subgraph = topology.query(concept_id, max_nodes=max_nodes, max_edges=max_edges, active_hash_limit=min(22, max_nodes))
            seed_hashes.extend(str(node.get("node_hash") or node.get("id")) for node in subgraph.get("nodes", [])[: max(1, min(12, max_nodes))])
        seed_hashes = list(dict.fromkeys(hash_value for hash_value in seed_hashes if hash_value))[:max_nodes]
        if not seed_hashes:
            return _fallback_fragment_from_cloud_raw(concept_id, max_nodes=max_nodes, max_edges=max_edges)

        marks = ",".join("?" for _ in seed_hashes)
        edge_rows = conn.execute(
            f"""
            SELECT source_hash, target_hash, weight
            FROM ghost_edges
            WHERE source_hash IN ({marks}) OR target_hash IN ({marks})
            ORDER BY weight DESC
            LIMIT ?
            """,
            (*seed_hashes, *seed_hashes, max_edges),
        ).fetchall()
        connected_hashes = set(seed_hashes)
        edges: list[dict[str, Any]] = []
        for row in edge_rows:
            source_hash = str(row["source_hash"])
            target_hash = str(row["target_hash"])
            connected_hashes.add(source_hash)
            connected_hashes.add(target_hash)
            edges.append(
                {
                    "source_hash": source_hash,
                    "target_hash": target_hash,
                    "source": source_hash,
                    "target": target_hash,
                    "weight": float(row["weight"] or 0.0),
                }
            )
        hashes = list(dict.fromkeys(connected_hashes))[:max_nodes]
        marks = ",".join("?" for _ in hashes)
        node_rows = conn.execute(
            f"""
            SELECT node_hash, dim0, dim1, dim2
            FROM ghost_nodes
            WHERE node_hash IN ({marks})
            LIMIT ?
            """,
            (*hashes, max_nodes),
        ).fetchall()
        nodes = [_ghost_node_from_row(row) for row in node_rows]
        node_set = {node["node_hash"] for node in nodes}
        edges = [edge for edge in edges if edge["source_hash"] in node_set and edge["target_hash"] in node_set][:max_edges]
        if not nodes and not edges:
            return _fallback_fragment_from_cloud_raw(concept_id, max_nodes=max_nodes, max_edges=max_edges)
        return {"nodes": nodes, "edges": edges, "concept_ids": [concept_id, *seed_hashes[:6]]}
    finally:
        conn.close()


def _write_cloud_fragment(request: CloudBrainIngestRequest) -> dict[str, Any]:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    text = (request.text or "").strip()
    source_url = (request.source_url or "").strip()
    if not text and source_url:
        text = f"Cloud Brain public source pointer\nsource_url: {source_url}\ningested_at: {now}"
    if not text:
        return {"accepted": False, "reason": "No fragment text or source_url was supplied."}
    digest = hashlib.sha256(f"{source_url}\n{text}".encode("utf-8", errors="ignore")).hexdigest()
    file_path = _cloud_fragment_raw_dir() / f"cloud-fragment-{now.replace(':', '').replace('-', '')}-{digest[:12]}.md"
    file_path.write_text(
        "\n".join(
            [
                "---",
                "source: cloud_brain_ingest",
                f"source_url: {source_url or 'inline'}",
                f"fragment_hash: {digest}",
                f"ingested_at: {now}",
                "privacy_classification: public_fragment",
                "---",
                "",
                text,
                "",
            ]
        ),
        encoding="utf-8",
    )
    return {
        "accepted": True,
        "fragment_hash": digest,
        "raw_fragment_path": str(file_path),
        "ingested_at": now,
    }


@router.get("/status")
def cloud_brain_status() -> dict[str, Any]:
    daemon = daemon_status()
    memory = memory_status()
    remote = _remote_broker_snapshot()
    payload = {**_status_shell(daemon, memory), "daemon": daemon, "memory": memory, **remote}
    if remote.get("broker_state") == "remote_connected":
        payload["public_cloud_backend_enabled"] = True
        provider = str(remote.get("cloud_provider") or remote.get("remote_status", {}).get("provider") or "remote")
        payload["implementation"] = f"{provider}-remote-cloud-brain-broker"
    return payload


@router.get("/fragment")
def cloud_brain_fragment(
    peer_id: str = Query(default=""),
    concept_id: str = Query(min_length=1, max_length=256),
    max_nodes: int = Query(default=96, ge=1, le=512),
    max_edges: int = Query(default=384, ge=0, le=2048),
) -> dict[str, Any]:
    """Return a signed/hashed graph fragment for edge payload transport.

    This endpoint is the local-companion data-plane peer target used by the
    two-track network manager. It returns Ghost Shell topology only: hashes,
    coordinates, and weighted edges. Raw Payload Vault text is not exported.
    """

    config = NetworkConfig.from_env()
    local_peer_id = config.local_peer_id
    if peer_id and peer_id not in {local_peer_id, "local", "atanor-local-peer", "homage-local-peer"}:
        raise HTTPException(status_code=404, detail="peer_id is not served by this local companion")
    fragment = _local_fragment_for_concept(concept_id, max_nodes=max_nodes, max_edges=max_edges)
    if not fragment["nodes"] and not fragment["edges"]:
        raise HTTPException(status_code=404, detail="concept fragment not found in local Ghost Shell")
    envelope = GraphFragmentEnvelope.create(
        fragment_id=f"fragment-{hashlib.sha256(concept_id.encode('utf-8', errors='ignore')).hexdigest()[:16]}",
        source_peer_id=local_peer_id,
        concept_ids=list(dict.fromkeys(fragment["concept_ids"])),
        nodes=fragment["nodes"],
        edges=fragment["edges"],
        signing_key=config.signing_key,
    )
    envelope.validate(
        signing_key=config.signing_key,
        max_bytes=config.max_fragment_bytes,
        max_nodes=config.max_nodes,
        max_edges=config.max_edges,
    )
    payload = envelope.to_dict()
    payload["transport"] = {
        "kind": "http_fragment_payload",
        "raw_payload_exported": False,
        "payload_vault_policy": "hash_topology_only",
        "served_by": "local_companion",
    }
    return payload


@router.post("/query")
def cloud_brain_query(request: CloudBrainQueryRequest) -> dict[str, Any]:
    daemon = daemon_status()
    memory = memory_status()
    activation = alpha_service.activate_memory(
        request.query,
        max_nodes=request.max_nodes,
        max_depth=request.max_depth,
    )
    density = local_density_score(
        list(activation.get("active_nodes") or []),
        list(activation.get("active_edges") or []),
        [],
    )
    ratios = route_ratio(density)
    fused_fragments = weighted_rrf(
        [
            {
                "chunk_id": f"local-node-{index}",
                "doc_id": "local-cloud-brain",
                "snippet": item.get("label") or item.get("node") or item.get("id"),
                "score": item.get("activation_score", item.get("score", 0)),
            }
            for index, item in enumerate(activation.get("semantic_skeleton", []), start=1)
        ],
        [],
        ratios,
        limit=8,
    )
    remote = _remote_broker_snapshot()
    remote_fragments: dict[str, Any] | None = None
    if remote.get("broker_state") == "remote_connected":
        try:
            remote_fragments = CloudBrokerClient(CloudBrokerConfig.from_env()).query_fragments(request.query, limit=8)
        except Exception as exc:
            remote["broker_state"] = "remote_error"
            remote["remote_error"] = str(exc)
    return {
        **_status_shell(daemon, memory),
        **remote,
        "query": request.query,
        "state": activation.get("state", "unknown"),
        "source": "remote_cloud_brain_broker" if remote_fragments else "local_cloud_brain_facade",
        "public_cloud_backend_enabled": bool(remote_fragments),
        "remote_fragments": remote_fragments,
        "fragments": {
            "active_nodes": activation.get("active_nodes", []),
            "active_edges": activation.get("active_edges", []),
            "semantic_skeleton": activation.get("semantic_skeleton", []),
            "fused_evidence_preview": fused_fragments,
        },
        "fusion": {
            "local_density": density,
            "epistemic_uncertainty": epistemic_uncertainty(density),
            "ratio": ratios,
            "rrf": "weighted_reciprocal_rank_fusion",
        },
        "promotion_policy": {
            "requires_repeated_signal": True,
            "requires_provenance": True,
            "requires_guardrail_pass": True,
            "writes_public_cloud": False,
        },
        "drift_report": activation.get("drift_report"),
    }


@router.get("/fragments/query")
def cloud_brain_fragments_query(
    q: str = Query(min_length=1, max_length=400),
    limit: int = Query(default=5, ge=1, le=25),
) -> dict[str, Any]:
    return query_ingested_fragments(q, limit=limit)


@router.post("/semantic/ingest")
def semantic_cloud_ingest(request: SemanticCloudIngestRequest) -> dict[str, Any]:
    return ingest_semantic_source(
        request.text,
        request.source_id,
        request.language,
        url=request.url,
        title=request.title,
        license=request.license,
        usage_allowed=request.usage_allowed,
    )


@router.get("/semantic/status")
def semantic_cloud_status() -> dict[str, Any]:
    return get_semantic_cloud_growth_status()


def _learning_loop_for_request(request: CloudLearningRunRequest | None = None) -> CloudSurfaceLearningLoop:
    request = request or CloudLearningRunRequest()
    policy = PayloadSourcePolicy(target_store="verified_store_v0" if request.promote_to_verified else "verified_store_v0_candidate")
    feeder = VerifiedPayloadFeeder(policy=policy, max_payloads_per_tick=request.max_payloads_per_tick)
    kwargs: dict[str, Any] = {}
    if request.candidate_store_root:
        kwargs["candidate_store_root"] = request.candidate_store_root
    return CloudSurfaceLearningLoop(
        feeder=feeder,
        promote_to_verified=request.promote_to_verified,
        require_review_before_production=True,
        **kwargs,
    )


@router.get("/learning/status")
def cloud_brain_learning_status() -> dict[str, Any]:
    daemon = daemon_status()
    feeder = VerifiedPayloadFeeder().run_once(dry_run=True)
    return {
        "learning_status_endpoint": True,
        "daemon_running": daemon.get("state") == "running",
        "worker_alive": bool(daemon.get("worker_alive")),
        "actually_learning": daemon.get("current_learning_phase") == "learning",
        "waiting_for_payloads": daemon.get("current_learning_phase") == "waiting_for_payloads",
        "current_learning_phase": daemon.get("current_learning_phase"),
        "queue_state": daemon.get("queue_state"),
        "last_round_action": daemon.get("last_round_action"),
        "feeder_enabled": True,
        "feeder_state": feeder.state,
        "last_feeder_action": feeder.state,
        "approved_payloads_available": feeder.approved_payloads_available,
        "accepted_payloads_total": feeder.accepted_payloads_total,
        "rejected_payloads_total": feeder.rejected_payloads_total,
        "last_rejection_reasons": feeder.last_rejection_reasons,
        "no_approved_payload_source": feeder.state == "no_approved_payload_source",
        "cumulative_learning_seconds": int(daemon.get("cumulative_learning_seconds") or 0),
        "idle_waiting_seconds": int(daemon.get("idle_waiting_seconds") or 0),
        "local_brain_write": False,
        "external_llm_used": False,
        "external_sllm_used": False,
        "mock_growth": False,
        "pair_edges_sent": 0,
    }


@router.post("/learning/tick")
def cloud_brain_learning_tick(request: CloudLearningRunRequest) -> dict[str, Any]:
    rows = [payload_from_mapping(item.model_dump()) for item in request.payloads]
    result = _learning_loop_for_request(request).run_once(
        dry_run=request.dry_run,
        payloads=rows if rows else None,
        max_accepted_per_run=request.max_accepted_per_run,
    )
    return result.to_dict()


@router.post("/learning/run-once")
def cloud_brain_learning_run_once(request: CloudLearningRunRequest) -> dict[str, Any]:
    return cloud_brain_learning_tick(request)


@router.get("/surface-graph/status")
def cloud_brain_surface_graph_status() -> dict[str, Any]:
    semantic = get_semantic_cloud_growth_status()
    return {
        "surface_graph_status_endpoint": True,
        "source": "verified_store_v0_surface_projection_candidate",
        "semantic_store_backend": semantic.get("store_backend"),
        "semantic_concepts": int(semantic.get("concepts") or 0),
        "semantic_relations": int(semantic.get("relations") or 0),
        "case_frames": int(semantic.get("case_frames") or 0),
        "surface_projection": "available_on_learning_tick",
        "production_store_mutated": False,
        "cgsr_consumes_surface_projection": True,
        "rhfc_core_modified": False,
        "false_confident": 0,
        "forgetting_count": 0,
        "pair_edges_sent": 0,
    }


@router.get("/identity")
def cloud_brain_identity() -> dict[str, Any]:
    return {
        "identity_endpoint": True,
        "name": "ATANOR Cloud Brain",
        "role": "verified Semantic Cloud Graph with Surface Graph projection candidates",
        "global_cloud_claim": False,
        "public_cloud_backend_enabled": False,
        "store_backend": "verified_store_v0",
        "learning_default_target": "verified_store_v0_candidate",
        "promotion_default": "manual_review_required",
        "local_brain_write": False,
        "external_llm_used": False,
        "mock_growth_allowed": False,
    }


@router.post("/semantic/index/rebuild")
def semantic_cloud_index_rebuild(
    limit_nodes: int = Query(default=1200, ge=1, le=50000),
    limit_edges: int = Query(default=2400, ge=0, le=100000),
) -> dict[str, Any]:
    result = build_cloud_read_model(limit_nodes=limit_nodes, limit_edges=limit_edges)
    return {
        **result,
        "request_time_rebuild": True,
        "note": "Explicit index rebuild completed. Status and graph read endpoints do not rebuild during request.",
    }


@router.post("/semantic/attach")
def semantic_cloud_attach(request: SemanticCloudAttachRequest) -> dict[str, Any]:
    return attach_semantic_cloud_for_query(request.query, limit=request.limit)


@router.post("/semantic/accelerate")
def semantic_cloud_accelerate(request: SemanticCloudAccelerateRequest) -> dict[str, Any]:
    if request.async_run:
        already_running = bool(_SEMANTIC_ACCELERATION_STATE.get("running")) or _SEMANTIC_ACCELERATION_LOCK.locked()
        if not already_running:
            _SEMANTIC_ACCELERATION_STATE["running"] = True
            _SEMANTIC_ACCELERATION_STATE["scheduled_batch_size"] = request.batch_size
            thread = threading.Timer(0.5, _run_semantic_acceleration_batch, args=(request.batch_size,))
            thread.daemon = True
            thread.name = "atanor-semantic-cloud-accelerator"
            thread.start()
        return {
            "accepted": not already_running,
            "async_run": True,
            "state": "running" if already_running else "started",
            "batch_size_requested": request.batch_size,
            "batch_size_applied": request.batch_size,
            "last_result": _SEMANTIC_ACCELERATION_STATE.get("last_result"),
            "last_error": _SEMANTIC_ACCELERATION_STATE.get("last_error"),
            "fake_counter": False,
            "honesty": {
                "local_brain_write": False,
                "external_llm_used": False,
                "external_sllm_used": False,
                "web_api_call_used": False,
                "global_cloud_claim": False,
                "proof_store_only": True,
            },
        }
    return ingest_semantic_acceleration_batch(batch_size=request.batch_size)


@router.get("/web-seed-feeder/status")
def cloud_brain_web_seed_feeder_status() -> dict[str, Any]:
    return feeder_status()


@router.post("/web-seed-feeder/run")
def cloud_brain_web_seed_feeder_run(request: WebSeedFeederRunRequest) -> dict[str, Any]:
    result = run_web_seed_feeder_once(
        force_enabled=request.force_enabled,
        force_fetch=request.force_fetch,
        max_sources_checked_per_run=request.max_sources,
    )
    semantic = get_semantic_cloud_growth_status()
    return {
        "feeder": result.to_state(),
        "semantic_cloud": semantic,
        "local_brain_write": False,
        "external_llm_used": False,
        "external_sllm_used": False,
        "global_cloud_claim": False,
    }


@router.get("/anna-archive/status")
def anna_archive_metadata_status() -> dict[str, Any]:
    config = load_anna_archive_config()
    return {
        "provider": "anna_archive",
        "mode": "metadata_only",
        "status": "enabled" if config.enabled and config.endpoint else "disabled_or_unconfigured",
        "config": config.public_status(),
        "policy": {
            "full_text_downloads": False,
            "raw_text_storage": False,
            "download_url_storage": False,
            "local_brain_write": False,
            "semantic_cloud_write": "derived_metadata_only",
        },
    }


@router.post("/anna-archive/search")
def anna_archive_metadata_search(request: AnnaArchiveMetadataSearchRequest) -> dict[str, Any]:
    try:
        result = fetch_anna_archive_metadata(request.query)
    except Exception as exc:
        result = {
            "enabled": load_anna_archive_config().enabled,
            "configured": bool(load_anna_archive_config().endpoint),
            "status": "remote_error",
            "records": [],
            "rejected": 0,
            "error": str(exc),
            "honesty": {
                "metadata_only": True,
                "full_text_downloads": False,
                "local_brain_write": False,
            },
        }
    ingest_summaries: list[dict[str, Any]] = []
    if request.ingest and result.get("records"):
        for record in result.get("records") or []:
            if not isinstance(record, dict):
                continue
            summary = ingest_semantic_source(
                anna_metadata_to_semantic_text(record),
                source_id=str(record.get("source_id") or "anna_archive_metadata"),
                language=str(record.get("language") or "auto") if str(record.get("language") or "").lower() in {"ko", "en"} else "auto",
                url=str(record.get("source_url") or "") or None,
                title=str(record.get("title") or "") or None,
                license=str(record.get("license") or "unknown"),
                usage_allowed=False,
            )
            ingest_summaries.append(
                {
                    "run_id": summary.get("run_id"),
                    "concepts_created": summary.get("concepts_created", 0),
                    "concepts_merged": summary.get("concepts_merged", 0),
                    "relations_created": summary.get("relations_created", 0),
                    "relations_strengthened": summary.get("relations_strengthened", 0),
                    "evidence_added": summary.get("evidence_added", 0),
                    "honesty": summary.get("honesty"),
                }
            )
        if ingest_summaries:
            try:
                read_model_result = build_cloud_read_model(limit_nodes=1200, limit_edges=2400)
            except Exception as exc:
                read_model_result = {"error": str(exc), "rebuilt": False}
        else:
            read_model_result = {"rebuilt": False}
    else:
        read_model_result = {"rebuilt": False}
    return {
        "provider": "anna_archive",
        "mode": "metadata_only",
        **result,
        "semantic_ingest": {
            "requested": request.ingest,
            "records_ingested": len(ingest_summaries),
            "runs": ingest_summaries,
            "read_model": read_model_result,
            "local_brain_write": False,
            "raw_text_storage": False,
            "download_url_storage": False,
        },
        "policy": {
            "full_text_downloads": False,
            "raw_text_storage": False,
            "download_url_storage": False,
            "local_brain_write": False,
        },
    }


@router.get("/semantic/graph")
def semantic_cloud_graph(
    limit_nodes: int = Query(default=1000, ge=1, le=5000),
    limit_edges: int = Query(default=3000, ge=0, le=10000),
) -> dict[str, Any]:
    graph = load_fast_graph_sample(limit_nodes=limit_nodes, limit_edges=limit_edges)
    return {**graph, "proof_store_only": True, "old_mirror_snapshot_used": False}


@router.post("/semantic/proof")
def semantic_cloud_growth_proof() -> dict[str, Any]:
    return run_semantic_cloud_growth_proof()


@router.post("/semantic/handoff")
def semantic_cloud_growth_handoff() -> dict[str, Any]:
    return write_semantic_cloud_growth_handoff()


@router.get("/source-inspector")
def cloud_brain_source_inspector() -> dict[str, Any]:
    return _cloud_source_inspector()


@router.post("/prove-remote-cloud-brain")
def prove_remote_cloud_brain() -> dict[str, Any]:
    proof = write_remote_cloud_brain_proof()
    return {**_cloud_source_inspector(), "remote_proof": proof}


@router.post("/ingest")
def cloud_brain_ingest(request: CloudBrainIngestRequest) -> dict[str, Any]:
    daemon = daemon_status()
    memory = memory_status()
    has_payload = bool((request.source_url or "").strip() or (request.text or "").strip())
    remote = _remote_broker_snapshot()
    if request.dry_run:
        return {
            **_status_shell(daemon, memory),
            **remote,
            "state": "dry_run",
            "accepted": False,
            "payload_seen": has_payload,
            "fragment_store": "local_companion_payload_vault",
            "reason": "Dry run only. Send dry_run=false to append a public fragment into the local Cloud Brain broker path.",
            "next_backend_contract": "dry_run=false writes data/raw/cloud_brain/*.md and triggers persistent append into Ghost Shell/Payload Vault.",
        }
    remote_put: dict[str, Any] | None = None
    if remote.get("broker_state") == "remote_connected":
        try:
            public_fragment = public_fragment_from_text(
                text=(request.text or request.source_url or "").strip(),
                source_url=request.source_url,
                source_peer_id=CloudBrokerConfig.from_env().node_id,
            )
            remote_put = CloudBrokerClient(CloudBrokerConfig.from_env()).put_fragment(public_fragment)
        except Exception as exc:
            remote["broker_state"] = "remote_error"
            remote["remote_error"] = str(exc)

    fragment = _write_cloud_fragment(request)
    if not fragment.get("accepted"):
        return {
            **_status_shell(daemon, memory),
            **remote,
            "state": "rejected",
            "accepted": False,
            "payload_seen": has_payload,
            "fragment_store": "local_companion_payload_vault",
            "reason": fragment.get("reason"),
        }
    daemon_after = daemon_status()
    memory_after = memory_status()
    return {
        **_status_shell(daemon_after, memory_after),
        **remote,
        "state": "accepted",
        "accepted": True,
        "payload_seen": has_payload,
        "fragment_store": "local_companion_payload_vault",
        "fragment": fragment,
        "remote_fragment": remote_put,
        "daemon": daemon_after,
        "next_backend_contract": "Remote Cloud Brain can swap this local fragment store through ATANOR_GATEWAY_API without changing the UI contract.",
    }


@router.get("/controlled-self-growth-proof")
def controlled_self_growth_proof() -> dict[str, Any]:
    return _latest_controlled_growth_summary()


@router.post("/prove-controlled-self-growth")
def prove_controlled_self_growth() -> dict[str, Any]:
    result = write_controlled_self_growth_proof(seed_root="data/seed_research", cloud_root="data/cloud_brain")
    return _controlled_growth_summary_from_proof(result["proof"], proof_exists=True)


@router.get("/sphere/manifest")
def cloud_brain_sphere_manifest() -> dict[str, Any]:
    return sphere_manifest()


@router.get("/sphere/tile")
def cloud_brain_sphere_tile(
    level: int = Query(default=0, ge=0, le=6),
    x: int = Query(default=0, ge=0),
    y: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    return get_sphere_tile(level=level, x=x, y=y)


@router.get("/sphere/tile/{tile_id}/children")
def cloud_brain_sphere_tile_children(tile_id: str) -> dict[str, Any]:
    try:
        return get_sphere_tile_children(tile_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/sphere/materialize")
def cloud_brain_sphere_materialize(
    tile_id: str = Query(min_length=1, max_length=80),
    zoom: int = Query(default=0, ge=0, le=8),
    budget_nodes: int = Query(default=5000, ge=0, le=50_000),
    budget_edges: int = Query(default=10000, ge=0, le=100_000),
) -> dict[str, Any]:
    try:
        return materialize_sphere_tile(
            tile_id,
            zoom_level=zoom,
            render_budget_nodes=budget_nodes,
            render_budget_edges=budget_edges,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/sphere/node/{cloud_node_id}")
def cloud_brain_sphere_node(cloud_node_id: str) -> dict[str, Any]:
    return get_cloud_node(cloud_node_id)


@router.post("/sphere/proof")
def prove_spherical_chunk_materialization() -> dict[str, Any]:
    result = write_spherical_chunk_materialization_proof(seed_root="data/seed_research", cloud_root="data/cloud_brain")
    return result["proof"]


@router.post("/consolidate")
def cloud_brain_consolidate(request: CloudBrainConsolidateRequest) -> dict[str, Any]:
    daemon = tick_daemon(force=request.force)
    memory = memory_status()
    return {
        **_status_shell(daemon, memory),
        "state": daemon.get("state", "idle"),
        "consolidated": daemon.get("last_round_action") == "memory_rebuilt_from_inputs",
        "last_round_action": daemon.get("last_round_action"),
        "last_round_message": daemon.get("last_round_message"),
        "daemon": daemon,
    }


@router.post("/prune")
def cloud_brain_prune(request: CloudBrainPruneRequest) -> dict[str, Any]:
    prune = (
        {"state": "dry_run", "pruned_edges": 0}
        if request.dry_run
        else run_synaptic_decay(factor=0.95, threshold=request.min_weight)
    )
    daemon = daemon_status()
    memory = memory_status()
    return {
        **_status_shell(daemon, memory),
        "state": prune.get("state", "dry_run"),
        "pruned": int(prune.get("pruned_edges") or 0) > 0,
        "policy": {
            "min_weight": request.min_weight,
            "max_idle_days": request.max_idle_days,
            "decay_factor": 0.95,
        },
        "result": prune,
    }
