from __future__ import annotations

from typing import Any


def _avg_confidence(items: list[dict[str, Any]]) -> float:
    values = [float(item.get("confidence") or 0.0) for item in items if isinstance(item.get("confidence"), (int, float))]
    if not values:
        return 0.0
    return sum(values) / len(values)


def local_density_score(
    nodes: list[dict[str, Any]] | None,
    edges: list[dict[str, Any]] | None,
    evidence_docs: list[dict[str, Any]] | None,
) -> float:
    """Estimate how much of the answer can be handled locally.

    The score intentionally uses bounded counts, not global graph size. A dense
    local activation window means Cloud Brain / web reliance should decay.
    """

    nodes = nodes or []
    edges = edges or []
    evidence_docs = evidence_docs or []
    node_density = min(1.0, len(nodes) / 24)
    edge_density = min(1.0, len(edges) / 48)
    evidence_density = min(1.0, len(evidence_docs) / 5)
    confidence = min(1.0, (_avg_confidence(nodes) * 0.6) + (_avg_confidence(edges) * 0.4))
    score = node_density * 0.25 + edge_density * 0.3 + evidence_density * 0.3 + confidence * 0.15
    return round(max(0.0, min(1.0, score)), 3)


def route_ratio(local_density: float) -> dict[str, float]:
    """Mathematically decay cloud reliance as local density rises."""

    local_density = max(0.0, min(1.0, float(local_density)))
    cloud = max(0.0, min(0.7, 0.7 - local_density * 0.7))
    local = 1.0 - cloud
    return {"local": round(local, 3), "cloud": round(cloud, 3)}


def _doc_key(doc: dict[str, Any], fallback_rank: int) -> str:
    return str(
        doc.get("chunk_id")
        or doc.get("id")
        or doc.get("url")
        or doc.get("path")
        or f"doc-{fallback_rank}"
    )


def weighted_rrf(
    local_docs: list[dict[str, Any]] | None,
    cloud_docs: list[dict[str, Any]] | None,
    ratio: dict[str, float] | None,
    *,
    k: int = 60,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Weighted Reciprocal Rank Fusion for local and cloud evidence buckets."""

    local_docs = local_docs or []
    cloud_docs = cloud_docs or []
    ratio = ratio or {"local": 1.0, "cloud": 0.0}
    weights = {
        "local": max(0.0, float(ratio.get("local", 0.0))),
        "cloud": max(0.0, float(ratio.get("cloud", 0.0))),
    }
    score_by_key: dict[str, float] = {}
    doc_by_key: dict[str, dict[str, Any]] = {}
    source_by_key: dict[str, str] = {}

    for source, docs in [("local", local_docs), ("cloud", cloud_docs)]:
        weight = weights[source]
        if weight <= 0:
            continue
        for rank, doc in enumerate(docs, start=1):
            key = _doc_key(doc, rank)
            previous = score_by_key.get(key, 0.0)
            score_by_key[key] = previous + weight / (k + rank)
            if key not in doc_by_key or source == "local":
                doc_by_key[key] = dict(doc)
            source_by_key[key] = source if previous == 0 else "fused"

    fused: list[dict[str, Any]] = []
    for key, score in sorted(score_by_key.items(), key=lambda item: (-item[1], item[0]))[:limit]:
        doc = dict(doc_by_key[key])
        doc["fusion_score"] = round(score, 6)
        doc["fusion_source"] = source_by_key.get(key, "local")
        doc["fusion_ratio"] = {"local": round(weights["local"], 3), "cloud": round(weights["cloud"], 3)}
        fused.append(doc)
    return fused


def epistemic_uncertainty(local_density: float) -> float:
    return round(1.0 - max(0.0, min(1.0, float(local_density))), 3)
