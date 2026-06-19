from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query

from packages.brain_graph import aggregate_brain_graph, brain_graph_status, get_overlay_status
from packages.brain_graph.proof import run_tab_aware_brain_graph_proof


router = APIRouter(prefix="/api/brain", tags=["brain-graph"])


@router.get("/graph")
def brain_graph(
    view: Literal["local", "cloud"] = Query(default="local"),
    mode: Literal["fast", "full", "debug"] = Query(default="fast"),
    layers: str | None = Query(default=None),
    query: str | None = Query(default=None),
    max_nodes: int = Query(default=1000, ge=1, le=5000),
    max_edges: int = Query(default=3000, ge=1, le=30_000),
    focus_node_id: str | None = Query(default=None),
    lod: int | None = Query(default=None, ge=1, le=6),
) -> dict:
    layer_list = [part.strip() for part in layers.split(",") if part.strip()] if layers else None
    return aggregate_brain_graph(
        view=view,
        layers=layer_list,
        query=query,
        max_nodes=max_nodes,
        max_edges=max_edges,
        focus_node_id=focus_node_id,
        lod=lod,
        mode=mode,
    )


@router.get("/overlay-status")
def overlay_status() -> dict:
    return get_overlay_status()


@router.get("/graph/status")
def graph_status() -> dict:
    return brain_graph_status()


@router.post("/graph/proof")
def graph_proof() -> dict:
    return run_tab_aware_brain_graph_proof()
