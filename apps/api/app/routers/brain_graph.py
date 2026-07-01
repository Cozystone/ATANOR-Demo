from __future__ import annotations

import threading
import time
from typing import Any, Literal

from fastapi import APIRouter, Query

from packages.brain_graph import aggregate_brain_graph, brain_graph_status, get_overlay_status
from packages.brain_graph.proof import run_tab_aware_brain_graph_proof


router = APIRouter(prefix="/api/brain", tags=["brain-graph"])

# Stale-while-revalidate cache for /api/brain/graph (~1s aggregate each). The dashboard
# polls it repeatedly with the SAME params; a plain TTL cache still made the FIRST request
# after each expiry pay the full recompute (a periodic ~700ms-1.4s spike). SWR instead:
# within TTL serve the cached value; once stale (but not ancient) serve the STALE value
# INSTANTLY and refresh in a background thread — so no request ever waits for the recompute
# after the first cold fill. Params vary little (view/layers), so the working set is tiny.
_GRAPH_CACHE: dict[tuple, tuple[float, dict]] = {}
_GRAPH_TTL = 5.0        # fresh window (graph changes slowly; halves refresh-spike frequency)
_GRAPH_STALE_MAX = 60.0  # beyond this a stale entry is too old to serve; recompute inline
_GRAPH_REFRESHING: set[tuple] = set()
_GRAPH_LOCK = threading.Lock()


def _graph_params(view, mode, layer_list, query, max_nodes, max_edges, focus_node_id, lod) -> dict:
    return dict(view=view, layers=layer_list, query=query, max_nodes=max_nodes,
                max_edges=max_edges, focus_node_id=focus_node_id, lod=lod, mode=mode)


def _graph_store(key: tuple, value: dict) -> None:
    _GRAPH_CACHE[key] = (time.time(), value)
    if len(_GRAPH_CACHE) > 64:
        for k, _v in sorted(_GRAPH_CACHE.items(), key=lambda kv: kv[1][0])[:32]:
            _GRAPH_CACHE.pop(k, None)


def _graph_refresh_async(key: tuple, params: dict) -> None:
    with _GRAPH_LOCK:
        if key in _GRAPH_REFRESHING:
            return
        _GRAPH_REFRESHING.add(key)

    def _work() -> None:
        try:
            _graph_store(key, aggregate_brain_graph(**params))
        except Exception:  # pragma: no cover - keep the last good value on failure
            pass
        finally:
            with _GRAPH_LOCK:
                _GRAPH_REFRESHING.discard(key)

    threading.Thread(target=_work, daemon=True).start()


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
    params = _graph_params(view, mode, layer_list, query, max_nodes, max_edges, focus_node_id, lod)
    now = time.time()
    hit = _GRAPH_CACHE.get(key)
    if hit:
        age = now - hit[0]
        if age < _GRAPH_TTL:
            return hit[1]                     # fresh
        if age < _GRAPH_STALE_MAX:
            _graph_refresh_async(key, params)  # serve stale NOW, refresh off the request path
            return hit[1]
    result = aggregate_brain_graph(**params)   # cold (or too-stale) miss: compute inline
    _graph_store(key, result)
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
