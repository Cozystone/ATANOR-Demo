from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from guard import check_guard
from ontology_forge import run_ontology
from rag_engine import query_graphrag
from trainer import run_dry_run


AlphaState = Literal["idle", "running", "completed", "failed"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _base_status() -> dict[str, Any]:
    return {
        "state": "idle",
        "started_at": None,
        "finished_at": None,
        "error": None,
    }


class AlphaService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.ontology = _base_status() | {"node_count": 0, "edge_count": 0, "newest_nodes": [], "newest_edges": []}
        self.graphrag = _base_status() | {"last_query": None, "confidence": 0, "result": None}
        self.guard = _base_status() | {"overall_guard_score": 0, "result": None}
        self.oven = _base_status() | {"last_loss": None, "checkpoint_path": None, "losses": []}

    def run_ontology(self) -> dict[str, Any]:
        with self._lock:
            self.ontology = self.ontology | {"state": "running", "started_at": utc_now_iso(), "finished_at": None, "error": None}
        try:
            result = run_ontology()
            nodes = result["nodes"]
            edges = result["edges"]
            status = {
                "state": "completed",
                "started_at": self.ontology["started_at"],
                "finished_at": utc_now_iso(),
                "error": None,
                "node_count": len(nodes),
                "edge_count": len(edges),
                "newest_nodes": nodes[:8],
                "newest_edges": edges[:8],
            }
        except Exception as exc:  # pragma: no cover - defensive runtime guard
            status = self.ontology | {"state": "failed", "finished_at": utc_now_iso(), "error": str(exc)}
        with self._lock:
            self.ontology = status
            return dict(self.ontology)

    def ontology_status(self) -> dict[str, Any]:
        with self._lock:
            return dict(self.ontology)

    def ontology_graph(self) -> dict[str, Any]:
        root = Path("data/ontology")
        nodes = json.loads((root / "nodes.json").read_text(encoding="utf-8")) if (root / "nodes.json").exists() else []
        edges = json.loads((root / "edges.json").read_text(encoding="utf-8")) if (root / "edges.json").exists() else []
        return {"nodes": nodes, "edges": edges, "status": self.ontology_status()}

    def query_graphrag(self, query: str) -> dict[str, Any]:
        with self._lock:
            self.graphrag = self.graphrag | {"state": "running", "started_at": utc_now_iso(), "finished_at": None, "error": None, "last_query": query}
        try:
            result = query_graphrag(query)
            status = {
                "state": "completed",
                "started_at": self.graphrag["started_at"],
                "finished_at": utc_now_iso(),
                "error": None,
                "last_query": query,
                "confidence": result["confidence"],
                "result": result,
            }
        except Exception as exc:  # pragma: no cover
            status = self.graphrag | {"state": "failed", "finished_at": utc_now_iso(), "error": str(exc)}
        with self._lock:
            self.graphrag = status
            return dict(self.graphrag)

    def graphrag_status(self) -> dict[str, Any]:
        with self._lock:
            return dict(self.graphrag)

    def check_guard(self, draft_answer: str, evidence_bundle: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            self.guard = self.guard | {"state": "running", "started_at": utc_now_iso(), "finished_at": None, "error": None}
        try:
            ontology = self.ontology_graph()
            if evidence_bundle is None:
                evidence_bundle = self.graphrag.get("result") or query_graphrag(draft_answer[:80])
            result = check_guard(draft_answer, evidence_bundle, ontology)
            status = {
                "state": "completed",
                "started_at": self.guard["started_at"],
                "finished_at": utc_now_iso(),
                "error": None,
                "overall_guard_score": result["overall_guard_score"],
                "result": result,
            }
        except Exception as exc:  # pragma: no cover
            status = self.guard | {"state": "failed", "finished_at": utc_now_iso(), "error": str(exc)}
        with self._lock:
            self.guard = status
            return dict(self.guard)

    def guard_status(self) -> dict[str, Any]:
        with self._lock:
            return dict(self.guard)

    def run_oven_dry_run(self) -> dict[str, Any]:
        with self._lock:
            self.oven = self.oven | {"state": "running", "started_at": utc_now_iso(), "finished_at": None, "error": None}
        try:
            result = run_dry_run()
            status = {
                "state": "completed",
                "started_at": self.oven["started_at"],
                "finished_at": result["finished_at"],
                "error": None,
                "last_loss": result["last_loss"],
                "checkpoint_path": result["checkpoint_path"],
                "losses": result["losses"],
                "result": result,
            }
        except Exception as exc:  # pragma: no cover
            status = self.oven | {"state": "failed", "finished_at": utc_now_iso(), "error": str(exc)}
        with self._lock:
            self.oven = status
            return dict(self.oven)

    def oven_status(self) -> dict[str, Any]:
        with self._lock:
            return dict(self.oven)


def telemetry_gpu() -> dict[str, Any]:
    command = shutil.which("nvidia-smi")
    if not command:
        return {
            "available": False,
            "state": "fallback",
            "message": "nvidia-smi is not available on this machine.",
            "gpu_name": "Unavailable",
            "utilization": 0,
            "vram_used": 0,
            "vram_total": 0,
            "temperature": None,
            "power_draw": None,
        }
    try:
        output = subprocess.check_output(
            [
                command,
                "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            timeout=3,
        ).strip().splitlines()[0]
        name, util, mem_used, mem_total, temp, power = [part.strip() for part in output.split(",")]
        return {
            "available": True,
            "state": "completed",
            "gpu_name": name,
            "utilization": float(util),
            "vram_used": float(mem_used),
            "vram_total": float(mem_total),
            "temperature": float(temp),
            "power_draw": None if power in {"[Not Supported]", "N/A"} else float(power),
            "message": None,
        }
    except Exception as exc:  # pragma: no cover - hardware dependent
        return {
            "available": False,
            "state": "fallback",
            "message": f"nvidia-smi failed: {exc}",
            "gpu_name": "Unavailable",
            "utilization": 0,
            "vram_used": 0,
            "vram_total": 0,
            "temperature": None,
            "power_draw": None,
        }


def telemetry_system() -> dict[str, Any]:
    return {
        "cpu_count": os.cpu_count(),
        "disk_total_gb": round(shutil.disk_usage(".").total / (1024 ** 3), 2),
        "disk_used_gb": round(shutil.disk_usage(".").used / (1024 ** 3), 2),
        "timestamp": utc_now_iso(),
    }


alpha_service = AlphaService()
