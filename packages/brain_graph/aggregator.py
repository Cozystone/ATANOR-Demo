from __future__ import annotations

from collections import Counter
from typing import Any

from .materializers import (
    materialize_cloud_attached_graph,
    materialize_contributor_graph,
    materialize_graph_cartridge_graph,
    materialize_local_base_graph,
    materialize_local_memory_candidates,
    materialize_local_user_graph,
    materialize_seed_graph,
    materialize_semantic_cloud_graph,
    materialize_surface_trace_summary,
    materialize_working_memory_local,
)
from .models import CLOUD_LAYERS, DEFAULT_CLOUD_LAYERS, DEFAULT_LOCAL_LAYERS, LOCAL_LAYERS, BrainGraphView, LayerResult, utc_now_iso
from .overlay_status import get_overlay_status


def _normalize_layers(view: str, layers: list[str] | None) -> list[str]:
    allowed = LOCAL_LAYERS if view == "local" else CLOUD_LAYERS
    defaults = DEFAULT_LOCAL_LAYERS if view == "local" else DEFAULT_CLOUD_LAYERS
    requested = layers or defaults
    return [layer for layer in requested if layer in allowed]


def _missing_requested(view: str, layers: list[str] | None) -> list[str]:
    if not layers:
        return []
    allowed = set(LOCAL_LAYERS if view == "local" else CLOUD_LAYERS)
    return [layer for layer in layers if layer not in allowed]


def _materialize_layer(layer: str, view: BrainGraphView, max_nodes: int, max_edges: int, query: str | None) -> LayerResult:
    if view == "local":
        if layer == "local_user":
            return materialize_local_user_graph(max_nodes, max_edges)
        if layer == "working_memory_local":
            return materialize_working_memory_local(max_nodes, max_edges)
        if layer == "local_base":
            return materialize_local_base_graph(max_nodes, max_edges, query)
        if layer == "seed":
            return materialize_seed_graph(max_nodes, max_edges)
        if layer == "local_memory_candidate":
            return materialize_local_memory_candidates()
    if layer == "semantic_cloud":
        return materialize_semantic_cloud_graph(max_nodes, max_edges)
    if layer == "cloud_attached":
        return materialize_cloud_attached_graph(max_nodes, max_edges, "cloud_attached")
    if layer == "graph_cartridge":
        return materialize_graph_cartridge_graph(max_nodes, max_edges)
    if layer == "contributor":
        return materialize_contributor_graph(max_nodes, max_edges)
    if layer == "working_memory_cloud":
        return materialize_cloud_attached_graph(max_nodes, max_edges, "working_memory_cloud")
    if layer == "surface_trace_summary":
        return materialize_surface_trace_summary()
    return LayerResult(layer=layer, available=False, missing_reason="unknown_layer")


def aggregate_brain_graph(
    *,
    view: BrainGraphView,
    layers: list[str] | None = None,
    query: str | None = None,
    max_nodes: int = 1000,
    max_edges: int = 3000,
) -> dict[str, Any]:
    selected_layers = _normalize_layers(view, layers)
    unknown_layers = _missing_requested(view, layers)
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    layer_results: list[dict[str, Any]] = []
    side_panel: dict[str, Any] = {}
    missing: list[dict[str, Any]] = [{"layer": layer, "reason": "not_allowed_for_view"} for layer in unknown_layers]
    partial = False

    per_layer_node_budget = max(1, max_nodes // max(len(selected_layers), 1))
    per_layer_edge_budget = max(1, max_edges // max(len(selected_layers), 1))
    for layer in selected_layers:
        try:
            result = _materialize_layer(layer, view, per_layer_node_budget, per_layer_edge_budget, query)
        except Exception as exc:
            result = LayerResult(layer=layer, available=False, missing_reason=f"materializer_error: {exc}")
        layer_payload = result.to_dict()
        layer_results.append(layer_payload)
        partial = partial or result.partial
        if not result.available:
            missing.append({"layer": result.layer, "reason": result.missing_reason or "unavailable"})
        nodes.extend(result.nodes)
        edges.extend(result.edges)
        if result.side_panel:
            side_panel[result.layer] = result.side_panel

    nodes = nodes[:max_nodes]
    node_ids = {str(node.get("id")) for node in nodes}
    edges = [edge for edge in edges if str(edge.get("source")) in node_ids and str(edge.get("target")) in node_ids][:max_edges]
    layer_counts = Counter(str(node.get("layer")) for node in nodes)
    edge_layer_counts = Counter(str(edge.get("layer")) for edge in edges)
    overlay = get_overlay_status()
    graph_id = f"{view}-brain-graph-{utc_now_iso()}"
    return {
        "graph_id": graph_id,
        "view": view,
        "generated_at": utc_now_iso(),
        "layers_enabled": selected_layers,
        "nodes": nodes,
        "edges": edges,
        "layer_results": layer_results,
        "layers_missing": missing,
        "side_panel": side_panel,
        "stats": {
            "rendered_nodes": len(nodes),
            "rendered_edges": len(edges),
            "layer_counts": dict(layer_counts),
            "edge_layer_counts": dict(edge_layer_counts),
            "partial": partial or len(nodes) >= max_nodes or len(edges) >= max_edges,
            "max_nodes": max_nodes,
            "max_edges": max_edges,
            "overlay": overlay,
            "local_user_nodes": layer_counts.get("local_user", 0),
            "cloud_attached_nodes": overlay.get("cloud_attached_nodes", 0),
            "cloud_attached_counts_as_local": False,
        },
        "honesty": {
            "view_is_tab_aware": True,
            "local_view_excludes_semantic_cloud": view == "local",
            "cloud_attached_counts_as_local": False,
            "surface_graph_full_render_disabled": True,
            "missing_layers_are_reported": True,
            "external_llm_used": False,
            "external_sllm_used": False,
        },
    }


def brain_graph_status() -> dict[str, Any]:
    return {
        "status": "ok",
        "pipeline": "tab_aware_brain_graph_render_pipeline",
        "views": {
            "local": {"layers": LOCAL_LAYERS, "default_layers": DEFAULT_LOCAL_LAYERS},
            "cloud": {"layers": CLOUD_LAYERS, "default_layers": DEFAULT_CLOUD_LAYERS},
        },
        "overlay": get_overlay_status(),
        "surface_graph_full_render_disabled": True,
        "cloud_attached_counts_as_local": False,
    }
