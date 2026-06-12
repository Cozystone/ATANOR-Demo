from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.alpha_services import alpha_service
from knowledge_bakery import daemon_status, tick_daemon


router = APIRouter(prefix="/api/cloud-brain", tags=["cloud-brain"])


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


def _status_shell(daemon: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": "Cloud Brain",
        "mode": "shared-public-ontology-facade",
        "implementation": "local-daemon-backed-alpha",
        "state": daemon.get("state", "idle"),
        "viewer_only_on_deploy": True,
        "public_cloud_backend_enabled": False,
        "local_required": True,
        "counts": {
            "nodes": int(daemon.get("latest_node_count") or 0),
            "edges": int(daemon.get("latest_edge_count") or 0),
            "events": int(daemon.get("latest_event_count") or 0),
            "rounds": int(daemon.get("total_rounds") or 0),
            "learned_rounds": int(daemon.get("learned_rounds") or 0),
        },
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


@router.get("/status")
def cloud_brain_status() -> dict[str, Any]:
    daemon = daemon_status()
    return {**_status_shell(daemon), "daemon": daemon}


@router.post("/query")
def cloud_brain_query(request: CloudBrainQueryRequest) -> dict[str, Any]:
    daemon = daemon_status()
    activation = alpha_service.activate_memory(
        request.query,
        max_nodes=request.max_nodes,
        max_depth=request.max_depth,
    )
    return {
        **_status_shell(daemon),
        "query": request.query,
        "state": activation.get("state", "unknown"),
        "source": "local_cloud_brain_facade",
        "public_cloud_backend_enabled": False,
        "fragments": {
            "active_nodes": activation.get("active_nodes", []),
            "active_edges": activation.get("active_edges", []),
            "semantic_skeleton": activation.get("semantic_skeleton", []),
        },
        "promotion_policy": {
            "requires_repeated_signal": True,
            "requires_provenance": True,
            "requires_guardrail_pass": True,
            "writes_public_cloud": False,
        },
        "drift_report": activation.get("drift_report"),
    }


@router.post("/ingest")
def cloud_brain_ingest(request: CloudBrainIngestRequest) -> dict[str, Any]:
    daemon = daemon_status()
    has_payload = bool((request.source_url or "").strip() or (request.text or "").strip())
    return {
        **_status_shell(daemon),
        "state": "dry_run" if request.dry_run else "planned",
        "accepted": False,
        "payload_seen": has_payload,
        "reason": (
            "Public Cloud Brain ingestion is not enabled yet. "
            "Use the lab harvest/DataGate path for local experiments until the shared graph backend exists."
        ),
        "next_backend_contract": "/api/cloud-brain/ingest will append provenance-scored virtual edges before consolidation.",
    }


@router.post("/consolidate")
def cloud_brain_consolidate(request: CloudBrainConsolidateRequest) -> dict[str, Any]:
    daemon = tick_daemon(force=request.force)
    return {
        **_status_shell(daemon),
        "state": daemon.get("state", "idle"),
        "consolidated": daemon.get("last_round_action") == "memory_rebuilt_from_inputs",
        "last_round_action": daemon.get("last_round_action"),
        "last_round_message": daemon.get("last_round_message"),
        "daemon": daemon,
    }


@router.post("/prune")
def cloud_brain_prune(request: CloudBrainPruneRequest) -> dict[str, Any]:
    daemon = daemon_status()
    return {
        **_status_shell(daemon),
        "state": "dry_run" if request.dry_run else "planned",
        "pruned": False,
        "policy": {
            "min_weight": request.min_weight,
            "max_idle_days": request.max_idle_days,
            "decay_factor": "planned",
        },
        "reason": "Edge decay/pruning is specified but not yet mutating the local memory store.",
    }
