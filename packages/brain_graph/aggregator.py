from __future__ import annotations

from collections import Counter
import math
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


def _float_or_default(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _spherical_position(node: dict[str, Any], lod: int) -> dict[str, Any]:
    """Derive stable spherical chunk coordinates from existing 3D node positions."""
    x = _float_or_default(node.get("x"))
    y = _float_or_default(node.get("y"))
    z = _float_or_default(node.get("z"))
    radius = max(math.sqrt((x * x) + (y * y) + (z * z)), 0.0001)
    theta = (math.atan2(z, x) + (math.pi * 2.0)) % (math.pi * 2.0)
    phi = math.acos(max(-1.0, min(1.0, y / radius)))
    shell = max(0, min(9, int(radius // 1.25)))
    theta_buckets = max(8, 8 * lod)
    phi_buckets = max(4, 4 * lod)
    sector_theta = min(theta_buckets - 1, int(theta / (math.pi * 2.0) * theta_buckets))
    sector_phi = min(phi_buckets - 1, int(phi / math.pi * phi_buckets))
    chunk_id = f"shell_{shell:02d}_theta_{sector_theta:02d}_phi_{sector_phi:02d}_lod_{lod:02d}"
    return {
        "r": radius,
        "theta": theta,
        "phi": phi,
        "shell": shell,
        "sector_theta": sector_theta,
        "sector_phi": sector_phi,
        "lod": lod,
        "chunk_id": chunk_id,
    }


def _active_spherical_chunks(nodes: list[dict[str, Any]], edges: list[dict[str, Any]], lod: int) -> list[dict[str, Any]]:
    positions_by_node: dict[str, dict[str, Any]] = {}
    chunks: dict[str, dict[str, Any]] = {}
    for node in nodes:
        position = _spherical_position(node, lod)
        node_id = str(node.get("id"))
        positions_by_node[node_id] = position
        chunk = chunks.setdefault(
            str(position["chunk_id"]),
            {
                "chunk_id": position["chunk_id"],
                "shell": position["shell"],
                "sector_theta": position["sector_theta"],
                "sector_phi": position["sector_phi"],
                "lod": lod,
                "bounds": {
                    "theta_sector": position["sector_theta"],
                    "phi_sector": position["sector_phi"],
                    "shell": position["shell"],
                },
                "logical_node_count": 0,
                "stored_relation_count": 0,
                "implicit_candidate_pairs": 0,
                "materialized_node_count": 0,
                "materialized_relation_count": 0,
            },
        )
        chunk["logical_node_count"] += 1
        chunk["materialized_node_count"] += 1

    for edge in edges:
        source_chunk = positions_by_node.get(str(edge.get("source")), {}).get("chunk_id")
        target_chunk = positions_by_node.get(str(edge.get("target")), {}).get("chunk_id")
        if source_chunk and source_chunk == target_chunk and source_chunk in chunks:
            chunks[source_chunk]["stored_relation_count"] += 1
            chunks[source_chunk]["materialized_relation_count"] += 1

    for chunk in chunks.values():
        count = int(chunk["materialized_node_count"])
        chunk["implicit_candidate_pairs"] = count * max(0, count - 1) // 2
    return sorted(chunks.values(), key=lambda row: (-int(row["materialized_node_count"]), str(row["chunk_id"])))


def aggregate_brain_graph(
    *,
    view: BrainGraphView,
    layers: list[str] | None = None,
    query: str | None = None,
    max_nodes: int = 1000,
    max_edges: int = 3000,
    focus_node_id: str | None = None,
    lod: int | None = None,
) -> dict[str, Any]:
    selected_layers = _normalize_layers(view, layers)
    unknown_layers = _missing_requested(view, layers)
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    layer_results: list[dict[str, Any]] = []
    side_panel: dict[str, Any] = {}
    missing: list[dict[str, Any]] = [{"layer": layer, "reason": "not_allowed_for_view"} for layer in unknown_layers]
    partial = False

    for layer in selected_layers:
        try:
            result = _materialize_layer(layer, view, max_nodes, max_edges, query)
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
    logical_node_count = len(nodes)
    stored_relation_count = len([
        edge for edge in edges
        if not ((edge.get("metadata") or {}).get("counts_as_stored_relation") is False)
    ])
    if view == "cloud":
        for result in layer_results:
            if result.get("layer") == "semantic_cloud":
                stats = result.get("stats") if isinstance(result.get("stats"), dict) else {}
                logical_node_count = max(logical_node_count, int(stats.get("concepts") or stats.get("semantic_cloud_nodes") or 0))
                stored_relation_count = max(stored_relation_count, int(stats.get("relations") or stats.get("semantic_cloud_edges") or 0))
                break
    possible_pair_candidates = logical_node_count * max(0, logical_node_count - 1) // 2
    materialized_node_count = len(nodes)
    materialized_relation_count = stored_relation_count if view == "cloud" else len(edges)
    verified_relation_count = len(edges)
    materialized_possible_pairs = materialized_node_count * max(0, materialized_node_count - 1) // 2
    culled_edges = max(0, materialized_relation_count - len(edges))
    effective_lod = max(1, min(6, int(lod))) if lod is not None else (3 if materialized_node_count >= 96 else 2)
    focus_relation_count = 0
    if focus_node_id:
        focus_relation_count = sum(
            1
            for edge in edges
            if str(edge.get("source")) == focus_node_id or str(edge.get("target")) == focus_node_id
        )
    active_chunks = _active_spherical_chunks(nodes, edges, effective_lod)
    active_chunk_ids = [str(chunk["chunk_id"]) for chunk in active_chunks[:16]]
    sphere_radius = max((_float_or_default(node.get("radius"), 1.0) for node in nodes), default=1.0)
    visualization_state = {
        "logical": {
            "node_count": logical_node_count,
            "stored_relation_count": stored_relation_count,
            "possible_candidate_pairs": possible_pair_candidates,
            "possible_pair_candidates": possible_pair_candidates,
            "sphere_topology": True,
            "density": (stored_relation_count / possible_pair_candidates) if possible_pair_candidates else 0.0,
        },
        "spherical_view": {
            "camera_shell": 0,
            "focus_node_id": focus_node_id,
            "zoom_level": effective_lod,
            "active_chunk_ids": active_chunk_ids,
            "active_chunks": len(active_chunks),
            "chunks": active_chunks[:16],
            "lod": effective_lod,
            "sphere_radius": sphere_radius,
        },
        "materialized": {
            "active_chunks": len(active_chunks),
            "chunk_ids": active_chunk_ids,
            "node_count": materialized_node_count,
            "relation_count": materialized_relation_count,
            "verified_relation_count": verified_relation_count,
            "focus_relation_count": focus_relation_count,
            "implicit_candidate_pairs": materialized_possible_pairs,
            "candidate_pair_edges_sent": 0,
            "zoom_level": effective_lod,
            "focus_node_id": focus_node_id,
        },
        "rendered": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "visual_edge_hints": min(len(active_chunks) * 8, 256),
            "edge_mode": "hybrid",
            "render_budget_nodes": max_nodes,
            "render_budget_edges": max_edges,
            "culled_edges": culled_edges,
            "sampling_reason": "viewport_chunk" if culled_edges else "none",
        },
        "virtualization": {
            "enabled": True,
            "mode": "spherical_minecraft_chunks",
            "candidate_pairs_implicit": True,
            "send_candidate_pairs_as_edges": False,
            "zoom_reveal_enabled": True,
            "full_graph_loaded_into_ram": False,
            "fake_aggregate_nodes": False,
            "sphere_shape_preserved": True,
        },
    }
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
            "visualization_state": visualization_state,
        },
        "visualization_state": visualization_state,
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
