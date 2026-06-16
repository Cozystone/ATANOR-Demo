import os

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.services.alpha_services import alpha_service
from packages.cloud_brain.cloud_node_attachment import graph_overlay

router = APIRouter(prefix="/api/memory", tags=["memory"])


class MemoryActivateRequest(BaseModel):
    query: str
    max_nodes: int = Field(default=40, ge=1, le=240)
    max_depth: int = Field(default=3, ge=1, le=6)


@router.post("/build")
def build_memory() -> dict:
    return alpha_service.build_memory()


@router.get("/status")
def memory_status() -> dict:
    return alpha_service.memory_status()


@router.get("/graph")
def memory_graph(
    limit: int = Query(default=600, ge=1, le=5000),
    include_cloud_attached: bool = Query(default=False),
) -> dict:
    graph = alpha_service.memory_graph(limit=limit)
    if not include_cloud_attached:
        return graph
    local_brain_initialized = os.getenv("ATANOR_LOCAL_BRAIN_INITIALIZED", "").strip().lower() in {"1", "true", "yes", "on"}
    if not local_brain_initialized:
        graph = {
            **graph,
            "nodes": [],
            "edges": [],
            "local_brain_initialized": False,
            "local_brain_empty": True,
            "cloud_mirror_excluded_from_local_brain": True,
            "cloud_mirror_snapshot": {
                "nodes": len(graph.get("nodes") or []),
                "edges": len(graph.get("edges") or []),
                "source": graph.get("source") or graph.get("store") or "ghost_shell_mirror",
            },
        }
    overlay = graph_overlay()
    local_nodes = list(graph.get("nodes") or [])
    local_edges = list(graph.get("edges") or [])
    seed_anchor_nodes = list(overlay.get("seed_anchor_nodes") or [])
    cloud_nodes = list(overlay.get("cloud_attached_nodes") or [])
    cloud_edges = list(overlay.get("cloud_attached_edges") or [])
    return {
        **graph,
        "nodes": [*local_nodes, *seed_anchor_nodes, *cloud_nodes],
        "edges": [*local_edges, *cloud_edges],
        "local_nodes": local_nodes,
        "local_edges": local_edges,
        "seed_anchor_nodes": seed_anchor_nodes,
        "cloud_attached_nodes": cloud_nodes,
        "cloud_attached_edges": cloud_edges,
        "working_memory_overlay": overlay["working_memory_overlay"],
        "counts": {
            "local_nodes": len(local_nodes),
            "local_edges": len(local_edges),
            "seed_anchor_nodes": len(seed_anchor_nodes),
            "cloud_attached_nodes": len(cloud_nodes),
            "cloud_attached_edges": len(cloud_edges),
        },
    }


@router.post("/activate")
def activate_memory(request: MemoryActivateRequest) -> dict:
    return alpha_service.activate_memory(request.query, request.max_nodes, request.max_depth)


@router.get("/drift-check")
def memory_drift_check() -> dict:
    return alpha_service.memory_drift_check()
