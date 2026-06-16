from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.alpha_services import alpha_service
from packages.surface_brain.dual_projection import ingest_source_sentence_dual_projection
from packages.surface_brain.models import SourceSentence, honesty_flags
from packages.surface_brain.realization_planner import plan_speech, realize_answer


router = APIRouter(tags=["dual-brain"])


class DualBrainIngestRequest(BaseModel):
    text: str = Field(min_length=1, max_length=12000)
    source_id: str | None = None
    url: str | None = None
    title: str | None = None
    license: str = "unknown"
    usage_allowed: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class AtanorChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    language: str | None = None
    audience_level: str = "beginner"
    tone: str = "clear"
    mode: str = "default"
    web_search: bool = False
    brain_mode: str = "unified"
    include_trace: bool = False


def _flags() -> dict[str, Any]:
    return {
        **honesty_flags(),
        "final_answer_generation_claimed": True,
        "trace_hidden_by_default": True,
    }


@router.post("/api/dual-brain/ingest")
def dual_brain_ingest(request: DualBrainIngestRequest) -> dict[str, Any]:
    source = SourceSentence.from_text(
        request.text,
        source_id=request.source_id,
        url=request.url,
        title=request.title,
        license=request.license,
        usage_allowed=request.usage_allowed,
        metadata=request.metadata,
    )
    return {**ingest_source_sentence_dual_projection(source), **_flags()}


def _semantic_context_from_rag(result: dict[str, Any]) -> dict[str, Any]:
    concepts = list(result.get("active_concepts") or [])
    for node in result.get("matched_nodes") or []:
        label = node.get("label") or node.get("primary_name") or node.get("id")
        if label and label not in concepts:
            concepts.append(label)
    relations = []
    for edge in result.get("matched_edges") or []:
        relations.append(
            {
                "source": edge.get("source") or edge.get("source_hash"),
                "relation": edge.get("relation") or edge.get("predicate"),
                "target": edge.get("target") or edge.get("target_hash"),
                "confidence": edge.get("confidence") or edge.get("weight") or 0.5,
            }
        )
    return {
        "concepts": concepts,
        "relations": relations,
        "evidence": list(result.get("evidence_docs") or []),
        "claims": list(result.get("claim_plan") or []),
        "confidence": float(result.get("confidence") or 0.0),
        "local_coverage": "high" if result.get("memory_activation") else "low" if not concepts else "medium",
        "retrieval_trace": result.get("retrieval_trace", {}),
    }


@router.post("/api/chat/atanor")
async def chat_atanor(request: AtanorChatRequest) -> dict[str, Any]:
    rag_status = await alpha_service.query_graphrag(
        request.question,
        request.web_search,
        None,
        brain_mode=request.brain_mode,
        locale=request.language,
        include_trace=True,
    )
    rag_result = rag_status.get("result") or {}
    semantic_context = _semantic_context_from_rag(rag_result)
    language = request.language or ("ko" if any("\uac00" <= char <= "\ud7a3" for char in request.question) else "en")
    plan = plan_speech(
        request.question,
        semantic_context,
        language=language,
        audience_level=request.audience_level,
        tone=request.tone,
        mode=request.mode,
    )
    realized = realize_answer(plan, semantic_context, query=request.question)
    compact_trace = {
        "local_coverage": semantic_context.get("local_coverage"),
        "semantic_cloud_graph": {
            "attached_nodes": len(semantic_context.get("concepts") or []),
            "evidence_docs": len(semantic_context.get("evidence") or []),
        },
        "surface_graph": {
            "construction_families": realized["trace_summary"].get("selected_construction_families", []),
            "discourse_moves": realized["trace_summary"].get("selected_discourse_moves", []),
        },
        "q_cortex": {
            "used": bool(plan.get("q_cortex_used")),
            "run_id": plan.get("q_cortex_run_id"),
            "real_quantum_hardware_used": False,
        },
        "working_memory": {
            "temporary_context": bool((rag_result.get("retrieval_trace") or {}).get("working_memory_overlay")),
            "local_brain_write": False,
        },
        "confidence": "high" if realized["confidence"] >= 0.75 else "medium" if realized["confidence"] >= 0.5 else "low",
    }
    payload = {
        "answer": realized["answer"],
        "language": realized["language"],
        "confidence": realized["confidence"],
        "default_trace_visible": False,
        "trace": compact_trace if request.include_trace or request.mode in {"trace", "research"} else None,
        "compact_trace": compact_trace,
        "research_trace": {
            "semantic_context": semantic_context,
            "surface_plan": plan,
            "realized_answer": realized,
            "rag_retrieval_trace": rag_result.get("retrieval_trace", {}),
        } if request.mode == "research" else None,
        "evidence_docs": semantic_context.get("evidence", []),
        "surface_plan": {
            "plan_id": plan.get("plan_id"),
            "intent": plan.get("intent"),
            "construction_families": compact_trace["surface_graph"]["construction_families"],
            "q_cortex_used": plan.get("q_cortex_used"),
            "q_cortex_run_id": plan.get("q_cortex_run_id"),
        },
        "answer_engine": {
            "name": "ATANOR Surface Brain",
            "semantic_plane": "Semantic Cloud Graph",
            "surface_plane": "Surface Cloud Graph",
            "external_llm": False,
            "external_sllm": False,
            "local_brain_write": False,
            "trace_hidden_by_default": True,
            "q_cortex_optional": True,
            "network_barrier": "sealed_for_generation",
        },
        **_flags(),
    }
    return {"state": "completed", "result": payload, **_flags()}
