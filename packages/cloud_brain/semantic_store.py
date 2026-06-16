from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SEMANTIC_CLOUD_ROOT = PROJECT_ROOT / "data" / "cloud_brain"
STORE_BACKEND = "local_semantic_proof_store"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def semantic_store_paths(root: str | Path = DEFAULT_SEMANTIC_CLOUD_ROOT) -> dict[str, Path]:
    base = Path(root)
    store = base / "store"
    store.mkdir(parents=True, exist_ok=True)
    return {
        "root": base,
        "store": store,
        "concepts": store / "semantic_concepts.json",
        "relations": store / "semantic_relations.json",
        "evidence": store / "semantic_evidence.jsonl",
        "growth_runs": base / "growth_runs",
        "proofs": base / "proofs",
        "semantic_ingest": base / "semantic_ingest",
    }


def _read_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


class SemanticCloudStore:
    def __init__(self, root: str | Path = DEFAULT_SEMANTIC_CLOUD_ROOT):
        self.root = Path(root)
        self.paths = semantic_store_paths(self.root)
        for key in ["growth_runs", "proofs", "semantic_ingest"]:
            self.paths[key].mkdir(parents=True, exist_ok=True)

    def load_concepts(self) -> dict[str, dict[str, Any]]:
        payload = _read_json(self.paths["concepts"], {})
        return payload if isinstance(payload, dict) else {}

    def save_concepts(self, concepts: dict[str, dict[str, Any]]) -> None:
        _write_json(self.paths["concepts"], concepts)

    def load_relations(self) -> dict[str, dict[str, Any]]:
        payload = _read_json(self.paths["relations"], {})
        return payload if isinstance(payload, dict) else {}

    def save_relations(self, relations: dict[str, dict[str, Any]]) -> None:
        _write_json(self.paths["relations"], relations)

    def load_evidence(self) -> list[dict[str, Any]]:
        return _read_jsonl(self.paths["evidence"])

    def add_evidence(self, evidence: dict[str, Any]) -> bool:
        rows = self.load_evidence()
        source_hash = str(evidence.get("source_hash") or "")
        if source_hash and any(str(row.get("source_hash")) == source_hash for row in rows):
            return False
        _append_jsonl(self.paths["evidence"], evidence)
        return True

    def status(self) -> dict[str, Any]:
        concepts = self.load_concepts()
        relations = self.load_relations()
        evidence = self.load_evidence()
        return {
            "proof_store_path": str(self.paths["store"]),
            "concepts": len(concepts),
            "relations": len(relations),
            "evidence": len(evidence),
            "store_path": str(self.paths["store"]),
            "store_backend": STORE_BACKEND,
            "last_growth_run": self.latest_growth_run(),
            "old_mirror_snapshot_used_as_live_cloud": False,
            "proof_store_only": True,
            "local_brain_write": False,
            "external_llm_used": False,
            "external_sllm_used": False,
            "global_cloud_claim": False,
        }

    def graph_sample(self, limit_nodes: int = 1000, limit_edges: int = 3000) -> dict[str, Any]:
        concepts = list(self.load_concepts().values())
        relations = list(self.load_relations().values())
        nodes = [
            {
                "id": row["concept_id"],
                "label": row.get("canonical_name") or row["concept_id"],
                "concept_id": row["concept_id"],
                "aliases": row.get("aliases", []),
                "language_labels": row.get("language_labels", {}),
                "trust": row.get("trust", 0.5),
                "confidence": row.get("confidence", 0.5),
                "seen_count": row.get("seen_count", 1),
                "source_scope": "cloud",
                "proof_store_only": True,
            }
            for row in concepts[:limit_nodes]
        ]
        node_ids = {node["id"] for node in nodes}
        edges = [
            {
                "id": row["relation_id"],
                "source": row["source_concept_id"],
                "target": row["target_concept_id"],
                "relation": row["relation"],
                "weight": row.get("weight", 0.5),
                "confidence": row.get("confidence", 0.5),
                "seen_count": row.get("seen_count", 1),
                "source_scope": "cloud",
                "proof_store_only": True,
            }
            for row in relations
            if row.get("source_concept_id") in node_ids and row.get("target_concept_id") in node_ids
        ][:limit_edges]
        return {
            "nodes": nodes,
            "edges": edges,
            "bounded": len(concepts) > limit_nodes or len(relations) > limit_edges,
            "proof_store_only": True,
            "counts": {
                "concepts": len(concepts),
                "relations": len(relations),
                "evidence": len(self.load_evidence()),
            },
        }

    def latest_growth_run(self) -> dict[str, Any] | None:
        runs = sorted(self.paths["growth_runs"].glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
        for path in runs:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    return {
                        "run_id": payload.get("run_id"),
                        "sentences_processed": payload.get("sentences_processed"),
                        "concepts_created": payload.get("concepts_created"),
                        "concepts_merged": payload.get("concepts_merged"),
                        "relations_created": payload.get("relations_created"),
                        "relations_strengthened": payload.get("relations_strengthened"),
                        "evidence_added": payload.get("evidence_added"),
                    }
            except Exception:
                continue
        return None


def get_semantic_cloud_growth_status(root: str | Path = DEFAULT_SEMANTIC_CLOUD_ROOT) -> dict[str, Any]:
    return SemanticCloudStore(root).status()
