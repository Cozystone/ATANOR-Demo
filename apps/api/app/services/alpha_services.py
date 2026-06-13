from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from guard import check_guard
from knowledge_bakery import activate_memory, build_memory, drift_check, export_graph, memory_status
from ontology_forge import run_ontology
from rag_engine import query_graphrag
from rag_engine.fusion import epistemic_uncertainty, fusion_ratio_from_context, local_density_score, route_ratio, weighted_rrf
from rag_engine.synthesizer import LocalSynthesizer
from trainer import run_dry_run

from app.services.web_search import is_fresh_search_query, is_knowledge_lookup_query, search_web, web_results_to_evidence


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
        self.memory = memory_status()

    def run_ontology(self) -> dict[str, Any]:
        with self._lock:
            self.ontology = self.ontology | {"state": "running", "started_at": utc_now_iso(), "finished_at": None, "error": None}
        try:
            result = run_ontology()
            nodes = result["nodes"]
            edges = result["edges"]
            memory_result = build_memory()
            status = {
                "state": "completed",
                "started_at": self.ontology["started_at"],
                "finished_at": utc_now_iso(),
                "error": None,
                "node_count": len(nodes),
                "edge_count": len(edges),
                "newest_nodes": nodes[:8],
                "newest_edges": edges[:8],
                "memory_status": memory_result,
            }
            with self._lock:
                self.memory = memory_result
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

    def build_memory(self) -> dict[str, Any]:
        with self._lock:
            self.memory = self.memory | {"state": "running", "started_at": utc_now_iso(), "finished_at": None, "error": None}
        try:
            result = build_memory()
            status = {
                **result,
                "state": "completed",
                "started_at": self.memory.get("started_at"),
                "finished_at": utc_now_iso(),
                "error": None,
            }
        except Exception as exc:  # pragma: no cover
            status = self.memory | {"state": "failed", "finished_at": utc_now_iso(), "error": str(exc)}
        with self._lock:
            self.memory = status
            return dict(self.memory)

    def memory_status(self) -> dict[str, Any]:
        status = memory_status()
        with self._lock:
            self.memory = {**self.memory, **status}
            return dict(self.memory)

    def memory_graph(self, limit: int = 600) -> dict[str, Any]:
        return export_graph(limit=limit)

    def activate_memory(self, query: str, max_nodes: int = 40, max_depth: int = 3) -> dict[str, Any]:
        result = activate_memory(query, max_nodes=max_nodes, max_depth=max_depth)
        with self._lock:
            self.memory = {**self.memory, **memory_status()}
        return result

    def memory_drift_check(self) -> dict[str, Any]:
        report = drift_check()
        with self._lock:
            self.memory = {**self.memory, **report.get("status", {})}
        return report

    async def query_graphrag(self, query: str, web_search: bool = False, web_search_provider: str | None = None) -> dict[str, Any]:
        with self._lock:
            self.graphrag = self.graphrag | {"state": "running", "started_at": utc_now_iso(), "finished_at": None, "error": None, "last_query": query}
        try:
            result = query_graphrag(query)
            is_conversation = _is_conversation_result(result)
            is_control = _is_control_result(result)
            memory_activation: dict[str, Any] | None = None
            if not is_conversation and not is_control and memory_status().get("state") == "completed":
                memory_activation = activate_memory(query)
            local_nodes = list(result.get("matched_nodes") or [])
            local_edges = list(result.get("matched_edges") or [])
            if memory_activation is not None:
                local_nodes.extend(memory_activation.get("active_nodes", []))
                local_edges.extend(memory_activation.get("active_edges", []))
            local_evidence_docs = list(result.get("evidence_docs") or [])
            density = local_density_score(local_nodes, local_edges, local_evidence_docs)
            ratios = fusion_ratio_from_context(
                query=query,
                matched_nodes=local_nodes,
                matched_edges=local_edges,
                evidence_docs=local_evidence_docs,
                local_answer_confidence=float(result.get("confidence") or 0.0),
            )
            local_only_graph_query = _is_local_operational_query(query)
            low_information_query = _is_low_information_conversation_query(query)
            should_search = not low_information_query and not local_only_graph_query and not is_conversation and not is_control and (
                web_search
                or is_fresh_search_query(query)
                or is_knowledge_lookup_query(query)
                or _should_web_search(result)
                or ratios["cloud"] >= 0.35
            )
            if should_search:
                search_payload = await search_web(query, 5, web_search_provider)
                result = _merge_web_search_result(query, result, search_payload, ratios, density)
            elif not is_conversation and not is_control:
                result = {
                    **result,
                    "fusion_ratio": ratios,
                    "fusion": {
                        "local_density": density,
                        "epistemic_uncertainty": epistemic_uncertainty(density),
                        "ratio": ratios,
                        "rrf": "skipped_no_cloud_needed",
                    },
                    "retrieval_trace": {
                        **result.get("retrieval_trace", {}),
                        "fusion_ratio": ratios,
                        "local_density": density,
                    },
                }
            if memory_activation is not None:
                result = {
                    **result,
                    "memory_activation": memory_activation,
                    "answer_engine": {
                        **result.get("answer_engine", {}),
                        "memory_activation": "knowledge_bakery_spread_activation_v1",
                    },
                    "retrieval_trace": {
                        **result.get("retrieval_trace", {}),
                        "active_memory_node_ids": [node["id"] for node in memory_activation.get("active_nodes", [])[:16]],
                    },
                }
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
            status = self.graphrag | {"state": "failed", "finished_at": utc_now_iso(), "error": str(exc), "confidence": 0, "result": None}
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
    disk = shutil.disk_usage(".")
    payload: dict[str, Any] = {
        "source": "local-fastapi",
        "cpu_count": os.cpu_count(),
        "disk_total_gb": round(disk.total / (1024 ** 3), 2),
        "disk_used_gb": round(disk.used / (1024 ** 3), 2),
        "disk_free_gb": round(disk.free / (1024 ** 3), 2),
        "timestamp": utc_now_iso(),
    }
    try:
        import psutil  # type: ignore

        memory = psutil.virtual_memory()
        payload |= {
            "ram_total_gb": round(memory.total / (1024 ** 3), 2),
            "ram_available_gb": round(memory.available / (1024 ** 3), 2),
            "ram_used_gb": round(memory.used / (1024 ** 3), 2),
            "ram_used_percent": round(float(memory.percent), 1),
            "cpu_percent": psutil.cpu_percent(interval=None),
        }
    except Exception:
        payload |= {
            "ram_total_gb": None,
            "ram_available_gb": None,
            "ram_used_gb": None,
            "ram_used_percent": None,
            "cpu_percent": None,
        }
    return payload


alpha_service = AlphaService()


def _is_conversation_result(result: dict[str, Any]) -> bool:
    return result.get("method") == "atanor-conversation-router-v1" or result.get("answer_kind") in {"greeting", "thanks", "conversation"}


def _is_control_result(result: dict[str, Any]) -> bool:
    return result.get("answer_kind") == "inspection" or result.get("method") in {
        "atanor-graph-inspection-v1",
        "atanor-graph-legend-v1",
    }


def _is_local_operational_query(query: str) -> bool:
    normalized = query.strip().lower()
    if not normalized:
        return False
    graph_terms = {"node", "nodes", "inventory", "legend", "color", "colors", "graph", "edge", "edges"}
    action_terms = {"show", "list", "all", "available", "meaning", "mean", "label"}
    tokens = set(re.findall(r"[a-z0-9_-]+", normalized))
    return ({"legend", "color"} <= tokens) or (bool(tokens & graph_terms) and bool(tokens & action_terms))


def _is_low_information_conversation_query(query: str) -> bool:
    normalized = query.strip().lower()
    if not normalized:
        return True
    compact = re.sub(r"[\s!.?,。！？~]+", "", normalized)
    if compact in {"hi", "hello", "hey", "yo", "thanks", "thankyou", "안녕", "안녕하세요", "하이", "고마워", "감사", "감사합니다"}:
        return True
    tokens = re.findall(r"[a-z0-9가-힣_-]+", normalized)
    return len(tokens) <= 2 and any(token in {"hi", "hello", "hey", "안녕", "안녕하세요", "하이"} for token in tokens)


def _should_web_search(result: dict[str, Any]) -> bool:
    return (
        result.get("method") in {"atanor-native-no-node-utterance-v1", "atanor-research-no-evidence-v1"}
        or not result.get("evidence_docs")
        or float(result.get("confidence") or 0) < 0.42
    )


def _make_graph_token_web_utterance(query: str, evidence_docs: list[dict[str, Any]]) -> dict[str, Any]:
    return LocalSynthesizer().synthesize(query, evidence_docs, [], [], [])


def _merge_web_search_result(
    query: str,
    base: dict[str, Any],
    search_payload: dict[str, Any],
    ratios: dict[str, float] | None = None,
    local_density: float | None = None,
) -> dict[str, Any]:
    cloud_docs = web_results_to_evidence(search_payload.get("results", []))
    local_docs = list(base.get("evidence_docs") or [])
    local_density = local_density if local_density is not None else local_density_score(
        list(base.get("matched_nodes") or []),
        list(base.get("matched_edges") or []),
        local_docs,
    )
    ratios = ratios or route_ratio(local_density)
    evidence_docs = weighted_rrf(local_docs, cloud_docs, ratios, limit=8)
    if not evidence_docs:
        return {
            **base,
            "web_search": search_payload,
            "fusion_ratio": ratios,
            "fusion": {
                "local_density": local_density,
                "epistemic_uncertainty": epistemic_uncertainty(local_density),
                "ratio": ratios,
                "rrf": "no_candidates",
            },
            "retrieval_trace": {
                **base.get("retrieval_trace", {}),
                "web_search_provider": search_payload.get("provider"),
                "web_search_status": search_payload.get("status"),
                "fusion_ratio": ratios,
                "local_density": local_density,
            },
        }
    utterance = _make_graph_token_web_utterance(query, evidence_docs)
    return {
        **base,
        "method": "atanor-graph-token-web-rag-v1",
        "answer": utterance["answer"],
        "evidence_docs": evidence_docs,
        "fusion_ratio": ratios,
        "citations": [
            {
                "doc_id": doc["chunk_id"],
                "source_doc_id": doc["doc_id"],
                "path": doc.get("url") or doc.get("path"),
                "url": doc.get("url"),
                "score": doc.get("score"),
            }
            for doc in evidence_docs
        ],
        "web_search": search_payload,
        "fusion": {
            "local_density": local_density,
            "epistemic_uncertainty": epistemic_uncertainty(local_density),
            "ratio": ratios,
            "rrf": "weighted_reciprocal_rank_fusion",
            "local_candidate_count": len(local_docs),
            "cloud_candidate_count": len(cloud_docs),
            "fused_candidate_count": len(evidence_docs),
        },
        "answer_engine": {
            **base.get("answer_engine", {}),
            **utterance["answer_engine"],
            "name": "ATANOR NativeGraphTokenDecoder",
            "mode": "native-web-fragment-evidence-alpha",
            "external_llm": False,
            "surface_generation": "native_graph_token_generation",
            "cloud_fragment_role": "evidence_only",
            "network_barrier": "sealed_for_generation",
        },
        "retrieval_trace": {
            **base.get("retrieval_trace", {}),
            "strategy": "raw web search harvest + ontology token transition graph + graph-token prediction",
            "web_search_provider": search_payload.get("provider"),
            "web_search_status": search_payload.get("status"),
            "web_result_urls": [doc.get("url") for doc in evidence_docs],
            "fusion_ratio": ratios,
            "local_density": local_density,
            "epistemic_uncertainty": epistemic_uncertainty(local_density),
        },
        "pmv": utterance["pmv"],
        "claim_plan": utterance["claim_plan"],
        "active_concepts": utterance["active_concepts"],
        "answer_kind": utterance["answer_kind"],
        "raw_native_output": utterance.get("raw_native_output", utterance["answer"]),
        "native_generation_failed_quality_check": utterance.get("native_generation_failed_quality_check"),
        "degeneration": utterance.get("degeneration", {}),
        "native_stop_reason": utterance.get("native_stop_reason"),
        "training_feedback_recorded": utterance.get("training_feedback_recorded", False),
        "confidence": max(float(base.get("confidence") or 0), 0.52),
    }
