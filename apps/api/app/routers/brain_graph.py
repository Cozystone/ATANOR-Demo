from __future__ import annotations

import time
from typing import Any, Literal

from fastapi import APIRouter, Query

from packages.brain_graph import aggregate_brain_graph, brain_graph_status, get_overlay_status
from packages.brain_graph.proof import run_tab_aware_brain_graph_proof


router = APIRouter(prefix="/api/brain", tags=["brain-graph"])

# Short-TTL response cache: the dashboard polls /api/brain/graph repeatedly with the SAME
# params (~1.9s aggregate each). The graph doesn't change sub-second, so caching by param
# key for a couple seconds makes repeated polls instant without a stale UX — decoupling
# poll frequency from backend cost (query=... focus requests bypass via their own key).
_GRAPH_CACHE: dict[tuple, tuple[float, dict]] = {}
_GRAPH_CACHE_TTL = 2.5


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
    key = (view, mode, layers, query, max_nodes, max_edges, focus_node_id, lod)
    now = time.time()
    hit = _GRAPH_CACHE.get(key)
    if hit and (now - hit[0]) < _GRAPH_CACHE_TTL:
        return hit[1]
    result = aggregate_brain_graph(
        view=view,
        layers=layer_list,
        query=query,
        max_nodes=max_nodes,
        max_edges=max_edges,
        focus_node_id=focus_node_id,
        lod=lod,
        mode=mode,
    )
    _GRAPH_CACHE[key] = (now, result)
    if len(_GRAPH_CACHE) > 64:
        for k, _v in sorted(_GRAPH_CACHE.items(), key=lambda kv: kv[1][0])[:32]:
            _GRAPH_CACHE.pop(k, None)
    return result


@router.get("/overlay-status")
def overlay_status() -> dict:
    return get_overlay_status()


@router.get("/graph/status")
def graph_status() -> dict:
    return brain_graph_status()


@router.post("/graph/proof")
def graph_proof() -> dict:
    return run_tab_aware_brain_graph_proof()
