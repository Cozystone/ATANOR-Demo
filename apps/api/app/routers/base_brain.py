from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from packages.base_brain.benchmark_runner import run_zero_user_benchmark
from packages.base_brain.models import PACK_PATH, honesty_flags
from packages.base_brain.pack_builder import build_base_brain_pack_v0
from packages.base_brain.pack_loader import load_base_brain_pack
from packages.base_brain.proof import run_base_brain_proof
from packages.base_brain.zero_user_answer import answer_with_base_brain


router = APIRouter(prefix="/api/base-brain", tags=["base-brain"])


class BaseBrainAnswerRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    language: str = "ko"
    audience_level: str = "beginner"
    mode: str = "default"
    # Persona styling is opt-in: general QA stays neutral; set True to speak AS the
    # attached persona (e.g. socratic). Default False so plain questions are unwrapped.
    apply_persona: bool = False


class BaseBrainBenchmarkRequest(BaseModel):
    limit: int | None = Field(default=None, ge=1, le=100)


def _status_payload() -> dict[str, Any]:
    pack = load_base_brain_pack()
    semantic = pack.semantic_graph.get("concepts", [])
    surface = pack.surface_graph.get("constructions", [])
    return {
        "state": "active",
        "pack_exists": PACK_PATH.exists(),
        "pack_id": pack.pack_id,
        "version": pack.version,
        "seed_graph_id": pack.seed_graph.get("seed_graph_id"),
        "seed_relation_primitive_count": len(pack.seed_graph.get("relation_primitives", [])),
        "seed_reasoning_primitive_count": len(pack.seed_graph.get("reasoning_primitives", [])),
        "semantic_node_count": len(semantic),
        "semantic_relation_count": pack.semantic_graph.get("relation_count", 0),
        "surface_construction_count": len(surface),
        "benchmark_prompt_count": len(pack.benchmark.get("prompts", [])),
        "zero_user_data": True,
        "feedback_auto_promoted": False,
        **honesty_flags(),
    }


@router.get("/status")
def base_brain_status() -> dict[str, Any]:
    return _status_payload()


@router.post("/build")
def base_brain_build() -> dict[str, Any]:
    pack = build_base_brain_pack_v0()
    return {"built": True, "pack": pack, **honesty_flags()}


@router.post("/answer")
def base_brain_answer(request: BaseBrainAnswerRequest) -> dict[str, Any]:
    result = answer_with_base_brain(
        request.query,
        language=request.language,  # type: ignore[arg-type]
        audience_level=request.audience_level,  # type: ignore[arg-type]
        mode=request.mode,  # type: ignore[arg-type]
        apply_persona=request.apply_persona,
    )
    # abstain backstop 1: the curated triple store (facts ingested by the abstain-to-ingest
    # loop land there) — verbatim, cited, never inferred. Only consulted on abstain, so the
    # existing quality paths are untouched.
    try:
        answer_text = str(result.get("answer") or "")
        # abstain detection is language-aware: the KO abstain says '근거가 부족',
        # the EN abstain says 'do not have enough base concepts'. Checking only the
        # Korean string meant English abstentions never reached the curated bridge
        # (incl. the English realizer) — measured: 'What is a concerto?' abstained
        # while the concerto facts sat in the store.
        abstained = ("근거가 부족" in answer_text) or ("do not have enough" in answer_text.lower())
        realtime = ("실시간" in answer_text) or ("real-time" in answer_text.lower())
        # neighborhood synthesis is the LAST-resort lane ("no exact definition, but
        # related facts…") — the curated triple store is a HIGHER-quality source and
        # must outrank it. At 25M rows the neighborhood pool is full of entity names
        # (measured: '서울이란?' -> 서울이문초등학교 anchor while the store held the
        # real definition), so a synthesis answer is treated as bridge-eligible too.
        cert = result.get("reasoning_certificate")
        neighborhoodish = isinstance(cert, dict) and (
            cert.get("derivation_kind") == "grounded_neighborhood_synthesis")
        # COMPOUND-SPLIT miss: '인공지능이란?' answered about '지능' — the base path
        # split the compound and defined a FRAGMENT. When the answer's leading subject
        # is a proper substring of the query's compound noun, it's the wrong referent;
        # the curated bridge (which now tries the maximal compound first) outranks it.
        compound_miss = False
        _qm = re.match(r"\s*([가-힣]{3,})(?:이?란|이란 ?뭐|은|는|이|가|의)", request.query)
        if _qm and answer_text:
            _asub = re.match(r"\s*([가-힣]{2,})(?:은|는|이|가|란)", answer_text)
            if _asub and _asub.group(1) != _qm.group(1) and _asub.group(1) in _qm.group(1):
                compound_miss = True
        if (abstained or neighborhoodish or compound_miss) and not realtime:
            from packages.graph_scale.answer_bridge import answer_from_triples

            bridged = answer_from_triples(request.query, request.language or "ko")
            if bridged:
                result = {**result, **bridged}
            elif abstained:
                # abstain backstop 2: queue the query's knowledge terms as ingest targets
                # (the abstain-to-ingest loop). Never affects the response.
                from packages.graph_scale.abstain_queue import record_abstain

                record_abstain(request.query)
    except Exception:
        pass
    return result


@router.post("/benchmark")
def base_brain_benchmark(request: BaseBrainBenchmarkRequest) -> dict[str, Any]:
    return run_zero_user_benchmark(limit=request.limit)


@router.get("/proof")
def base_brain_proof() -> dict[str, Any]:
    return run_base_brain_proof()
