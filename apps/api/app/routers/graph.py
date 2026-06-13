from __future__ import annotations

from fastapi import APIRouter, Query

from app.services.alpha_services import alpha_service


router = APIRouter(prefix="/api/graph", tags=["graph"])


@router.get("/subgraph")
def graph_subgraph(
    limit: int = Query(default=900, ge=1, le=5000),
    query: str | None = Query(default=None, min_length=1, max_length=240),
    max_depth: int = Query(default=3, ge=1, le=6),
    max_nodes: int = Query(default=900, ge=1, le=5000),
) -> dict:
    """Live graph view for the web UI.

    Without a query this returns the current long-term memory graph. With a
    query it returns a bounded activation subgraph. Both paths stay behind the
    same `/api/graph/subgraph` contract used by the production web proxy.
    """

    if query:
        result = alpha_service.activate_memory(query, max_nodes=min(max_nodes, limit), max_depth=max_depth)
        return {
            "state": result.get("state", "completed"),
            "source": "activation_subgraph",
            "query": query,
            "nodes": result.get("active_nodes", []),
            "edges": result.get("active_edges", []),
            "trace": result,
        }
    result = alpha_service.memory_graph(limit=limit)
    return {
        **result,
        "state": result.get("state", "completed"),
        "source": "long_term_memory_graph",
    }


@router.get("/stream")
def graph_stream(limit: int = Query(default=900, ge=1, le=5000)) -> dict:
    """JSON snapshot endpoint kept intentionally lightweight for polling clients."""

    result = alpha_service.memory_graph(limit=limit)
    return {
        **result,
        "state": result.get("state", "completed"),
        "source": "live_graph_poll_snapshot",
        "stream": "polling_json_v1",
    }
