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
    # self-awareness -> answer depth: if the self is currently pondering this
    # subject, weave in MORE grounded relations. Defensive + additive; boost is 0
    # (identical behaviour) unless genuinely engaged — and the self ponders ITSELF,
    # so factual answers are untouched. hallucination-0 preserved (grounded only).
    _boost = 0
    _self_engaged = False
    try:
        from packages.continuous_self.inquiry_fusion import depth_bias, extra_relation_budget
        from packages.graph_scale.query_frame import parse as _qf_parse
        from app.routers.continuous_self import _SELF as _self_loop

        _st = _self_loop.state
        _state = {
            "self_question": getattr(_st, "self_question", "") or "",
            "self_question_open": bool(getattr(_st, "self_question_open", False)),
            "last_inquiry_topic": getattr(_st, "_last_inquiry_topic", "") or "",
            "curiosity": float(getattr(_st, "curiosity", 0.5) or 0.5),
        }
        _subj = _qf_parse(request.query).subject or request.query
        _bias = depth_bias(_subj, _state)
        if _bias >= 0.5:
            _boost = max(0, extra_relation_budget(_bias) - 3)
            _self_engaged = _boost > 0
    except Exception:
        _boost = 0

    result = answer_with_base_brain(
        request.query,
        language=request.language,  # type: ignore[arg-type]
        audience_level=request.audience_level,  # type: ignore[arg-type]
        mode=request.mode,  # type: ignore[arg-type]
        apply_persona=request.apply_persona,
        self_depth_boost=_boost,
    )
    if _self_engaged and isinstance(result, dict):
        result["self_engaged"] = True
        result["self_depth_boost"] = _boost
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
                # NO DEAD-END (owner directive 2026-07-09): a bare '근거가 부족'
                # is a letdown. Replace it with a SUBSTANTIVE engagement built
                # only from what the graph really holds (nearest verified
                # concept + related facts + a live-web path) — honest, never
                # fabricated. The abstain queue above still learns the gap.
                try:
                    from packages.graph_scale.engage import engage
                    from packages.graph_scale.answer_bridge import _store

                    _eng = engage(request.query, request.language or "ko", store=_store())
                    if _eng:
                        result = {**result, **_eng}
                except Exception:
                    pass
    except Exception:
        pass
    return result


@router.get("/interference-scene")
def base_brain_interference_scene() -> dict[str, Any]:
    """Phase-interference visualization data — REAL trained concepts + true
    resonance pairs from the phase space (nothing staged)."""
    try:
        from packages.graph_scale.phase_space import interference_scene

        return interference_scene()
    except Exception:
        return {"nodes": [], "links": [], "prunes": []}


@router.get("/graph-health")
def base_brain_graph_health() -> dict[str, Any]:
    """Read-only integrity report: the self-refinement flywheel made observable.
    Runs every defect detector with apply=False (nothing is modified) and returns
    counts + a 0..1 integrity score. Safe to poll."""
    try:
        from packages.graph_scale.graph_health import health_report

        return health_report()
    except Exception as exc:
        return {"available": False, "reason": f"{type(exc).__name__}"}


@router.post("/surgeon/review")
def base_brain_surgeon_review(request: dict) -> dict[str, Any]:
    """The Surgeon — real-time contamination review of candidate is_a edges.
    The self-aware loop (or an operator) posts a small batch of freshly-derived
    (subject, object) candidates; the Surgeon returns the type-disjoint ones to
    excise, WITH a stated reason. Read-only: it flags, it does not delete —
    quarantine stays gated. Body: {"edges": [["방콕","청교도"], ...]}."""
    try:
        from packages.graph_scale.answer_bridge import _store
        from packages.graph_scale.surgeon import scan

        edges = [(str(e[0]), str(e[1])) for e in (request.get("edges") or [])
                 if isinstance(e, (list, tuple)) and len(e) >= 2][:500]
        return scan(_store(), edges, cap=500)
    except Exception as exc:
        return {"available": False, "reason": f"{type(exc).__name__}"}


@router.get("/visual-memory/{concept}")
def base_brain_visual_recall(concept: str, learn: bool = False) -> dict[str, Any]:
    """Perceptual grounding v0: the measured visual signature of a concept
    (color bands/palette/texture from REAL photos, provenance attached), as
    particle-scene parameters. learn=true fetches+measures when unknown."""
    try:
        from packages.perception import learn_visual, recall_scene

        scene = recall_scene(concept)
        if scene is None and learn:
            learn_visual(concept, log=lambda *_: None)
            scene = recall_scene(concept)
        return scene or {"kind": "visual_recall", "concept": concept,
                         "known": False}
    except Exception:
        return {"kind": "visual_recall", "concept": concept, "known": False}


@router.post("/benchmark")
def base_brain_benchmark(request: BaseBrainBenchmarkRequest) -> dict[str, Any]:
    return run_zero_user_benchmark(limit=request.limit)


@router.get("/proof")
def base_brain_proof() -> dict[str, Any]:
    return run_base_brain_proof()
