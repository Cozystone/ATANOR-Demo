from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CANDIDATE_RUNS_DIR = PROJECT_ROOT / "data" / "cloud_brain" / "candidate_runs"
DEFAULT_CANDIDATE_STORE = PROJECT_ROOT / "data" / "cloud_brain" / "verified_store_v0_candidate"


@dataclass(frozen=True)
class CandidateStoreRef:
    """Resolved review-gated Cloud Brain candidate store."""

    path: Path | None
    reason: str = ""


def _jsonl_count(path: Path, *, limit: int = 50_000) -> int:
    """Return a bounded JSONL row count for stores without a manifest."""

    if not path.exists():
        return 0
    count = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            count += 1
        if count >= limit:
            break
    return count


def _load_jsonl(path: Path, *, limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
        if len(rows) >= limit:
            break
    return rows


def resolve_candidate_store(candidate_store_path: str | Path | None = None) -> CandidateStoreRef:
    """Resolve an explicit or most-recent candidate store without promotion."""

    if candidate_store_path:
        path = Path(candidate_store_path)
        return CandidateStoreRef(path if path.exists() and path.is_dir() else None, "explicit_candidate_store_missing")
    if DEFAULT_CANDIDATE_RUNS_DIR.exists():
        stores = [
            item
            for item in DEFAULT_CANDIDATE_RUNS_DIR.iterdir()
            if item.is_dir() and (item / "manifest.json").exists()
        ]
        if stores:
            return CandidateStoreRef(max(stores, key=lambda item: item.stat().st_mtime), "latest_candidate_run")
    if (DEFAULT_CANDIDATE_STORE / "manifest.json").exists():
        return CandidateStoreRef(DEFAULT_CANDIDATE_STORE, "default_candidate_store")
    return CandidateStoreRef(None, "no_candidate_store_available")


def _counts(root: Path) -> dict[str, int]:
    manifest_path = root / "manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            counts = manifest.get("counts") or {}
            return {
                "concepts": int(counts.get("concepts") or 0),
                "relations": int(counts.get("relations") or 0),
                "evidence": int(counts.get("evidence") or 0),
                "case_frames": int(counts.get("case_frames") or 0),
            }
        except Exception:
            pass
    return {
        "concepts": _jsonl_count(root / "concepts.jsonl"),
        "relations": _jsonl_count(root / "relations.jsonl"),
        "evidence": _jsonl_count(root / "evidence.jsonl"),
        "case_frames": _jsonl_count(root / "case_frames.jsonl"),
    }


def candidate_cloud_status(candidate_store_path: str | Path | None = None) -> dict[str, Any]:
    """Return reviewable candidate counts separated from production."""

    ref = resolve_candidate_store(candidate_store_path)
    if ref.path is None:
        return {
            "candidate_status_endpoint": True,
            "candidate_available": False,
            "candidate_store_path": None,
            "reason": ref.reason,
            "candidate_concepts": 0,
            "candidate_relations": 0,
            "candidate_evidence": 0,
            "candidate_case_frames": 0,
            "surface_candidates": 0,
            "cgsr_frames": 0,
            "rhfc_candidates": 0,
            "production_store_mutated": False,
            "candidate_is_verified": False,
            "safe_for_review": False,
            "local_brain_write": False,
            "false_confident": 0,
            "forgetting_count": 0,
            "eval_rows_used_for_learning": False,
            "external_llm_used": False,
            "mock_growth": False,
            "pair_edges_sent": 0,
            "private_data_used_for_cloud_learning": False,
            "unsupported_claims": 0,
        }
    counts = _counts(ref.path)
    case_frames = counts["case_frames"]
    return {
        "candidate_status_endpoint": True,
        "candidate_available": any(counts.values()),
        "candidate_store_path": str(ref.path),
        "reason": ref.reason,
        "candidate_concepts": counts["concepts"],
        "candidate_relations": counts["relations"],
        "candidate_evidence": counts["evidence"],
        "candidate_case_frames": case_frames,
        "surface_candidates": case_frames,
        "cgsr_frames": case_frames,
        "rhfc_candidates": case_frames,
        "production_store_mutated": False,
        "candidate_is_verified": False,
        "safe_for_review": any(counts.values()),
        "local_brain_write": False,
        "false_confident": 0,
        "forgetting_count": 0,
        "eval_rows_used_for_learning": False,
        "external_llm_used": False,
        "mock_growth": False,
        "pair_edges_sent": 0,
        "private_data_used_for_cloud_learning": False,
        "unsupported_claims": 0,
    }


def candidate_cloud_graph(
    candidate_store_path: str | Path | None = None,
    *,
    max_nodes: int = 200,
    max_edges: int = 400,
) -> dict[str, Any]:
    """Materialize a bounded candidate overlay graph.

    Nodes and edges are marked as ``candidate`` and ``source_store=candidate``.
    They are never merged into production counts by this read model.
    """

    status = candidate_cloud_status(candidate_store_path)
    if not status["candidate_available"] or not status["candidate_store_path"]:
        return {
            "nodes": [],
            "edges": [],
            "metadata": {
                **status,
                "candidate_graph_available": False,
                "graph_pending_reason": status.get("reason") or "candidate_store_missing",
                "full_store_scan": False,
                "index_rebuild_during_request": False,
                "pair_edges_sent": 0,
            },
        }
    root = Path(str(status["candidate_store_path"]))
    concept_rows = _load_jsonl(root / "concepts.jsonl", limit=max_nodes)
    node_ids = {str(row.get("concept_id")) for row in concept_rows if row.get("concept_id")}
    nodes = [
        {
            "id": str(row.get("concept_id")),
            "label": str(row.get("canonical_name") or row.get("concept_id")),
            "type": "candidate_cloud_concept",
            "language": row.get("language"),
            "candidate": True,
            "source_store": "candidate",
            "verification_status": "candidate_review",
            "is_verified_production": False,
            "style": {"color": "#f59e0b", "halo": "dashed"},
        }
        for row in concept_rows
        if row.get("concept_id")
    ]
    edge_rows = _load_jsonl(root / "relations.jsonl", limit=max_edges)
    edges: list[dict[str, Any]] = []
    for row in edge_rows:
        source = str(row.get("source_concept_id") or "")
        target = str(row.get("target_concept_id") or "")
        if not source or not target or source not in node_ids or target not in node_ids:
            continue
        edges.append(
            {
                "id": str(row.get("relation_id") or f"{source}:{target}:{len(edges)}"),
                "source": source,
                "target": target,
                "relation": str(row.get("relation") or "candidate_relation"),
                "candidate": True,
                "source_store": "candidate",
                "verification_status": "candidate_review",
                "is_verified_production": False,
                "style": {"stroke": "#f59e0b", "dash": True},
            }
        )
        if len(edges) >= max_edges:
            break
    return {
        "nodes": nodes,
        "edges": edges,
        "metadata": {
            **status,
            "candidate_graph_available": True,
            "materialized_candidate_nodes": len(nodes),
            "materialized_candidate_edges": len(edges),
            "rendered_candidate_edges": len(edges),
            "verified_logical_nodes": 0,
            "verified_logical_relations": 0,
            "total_with_candidate_overlay": status["candidate_concepts"],
            "full_store_scan": False,
            "index_rebuild_during_request": False,
            "pair_edges_sent": 0,
            "candidate_pair_edges_sent": 0,
        },
    }
