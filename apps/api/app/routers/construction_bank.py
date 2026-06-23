from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.routers.agentic_micro_os import REVIEW_QUEUE
from packages.construction_bank.extractor import extract_construction_candidates
from packages.construction_bank.models import INVARIANTS, get_default_construction_bank
from packages.construction_bank.promotion_guard import promotion_requirements
from packages.construction_bank.proof import run_proof
from packages.construction_bank.retriever import retrieve_constructions
from packages.construction_bank.review_adapter import export_to_review_queue


router = APIRouter(prefix="/api/construction-bank", tags=["construction-bank"])


class ExtractRequest(BaseModel):
    sources: list[dict[str, Any]] = Field(default_factory=list)
    store: bool = True


class RetrieveRequest(BaseModel):
    route_type: str = "open_chat"
    language: str = "ko"
    act: str | None = None
    audience: str = "lab"
    grounding_context: dict[str, Any] = Field(default_factory=dict)
    recent_output_history: list[str] = Field(default_factory=list)
    limit: int = Field(default=3, ge=1, le=10)


class ExportReviewRequest(BaseModel):
    candidate_id: str


@router.get("/status")
def construction_bank_status() -> dict[str, Any]:
    bank = get_default_construction_bank()
    return {
        **bank.status(),
        "promotion_guard": promotion_requirements(),
        "review_queue_items_total": REVIEW_QUEUE.status()["items_total"],
    }


@router.get("/candidates")
def construction_bank_candidates(status: str | None = None) -> dict[str, Any]:
    bank = get_default_construction_bank()
    return {
        **INVARIANTS,
        "candidates": [candidate.to_dict() for candidate in bank.list_candidates(status=status)],
    }


@router.post("/extract")
def construction_bank_extract(request: ExtractRequest) -> dict[str, Any]:
    bank = get_default_construction_bank()
    candidates = extract_construction_candidates(request.sources)
    stored = bank.add_many(candidates) if request.store else candidates
    return {
        **INVARIANTS,
        "extracted": len(candidates),
        "stored": len(stored) if request.store else 0,
        "candidates": [candidate.to_dict() for candidate in stored],
    }


@router.post("/retrieve")
def construction_bank_retrieve(request: RetrieveRequest) -> dict[str, Any]:
    return {
        **INVARIANTS,
        **retrieve_constructions(
            route_type=request.route_type,
            language=request.language,
            act=request.act,
            audience=request.audience,
            grounding_context=request.grounding_context,
            recent_output_history=request.recent_output_history,
            limit=request.limit,
        ),
    }


@router.post("/export-review-item")
def construction_bank_export_review_item(request: ExportReviewRequest) -> dict[str, Any]:
    bank = get_default_construction_bank()
    candidate = bank.candidates.get(request.candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="construction candidate not found")
    item = export_to_review_queue(candidate, REVIEW_QUEUE)
    return {
        **INVARIANTS,
        "review_item": item,
        "production_active": False,
        "mutation_performed": False,
    }


@router.get("/proof")
def construction_bank_proof() -> dict[str, Any]:
    return run_proof()
