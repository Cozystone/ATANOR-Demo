from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.services.alpha_services import alpha_service

router = APIRouter(prefix="/api/memory", tags=["memory"])


class MemoryActivateRequest(BaseModel):
    query: str
    max_nodes: int = Field(default=40, ge=1, le=240)
    max_depth: int = Field(default=3, ge=1, le=6)


@router.post("/build")
def build_memory() -> dict:
    return alpha_service.build_memory()


@router.get("/status")
def memory_status() -> dict:
    return alpha_service.memory_status()


@router.get("/graph")
def memory_graph(limit: int = Query(default=600, ge=1, le=5000)) -> dict:
    return alpha_service.memory_graph(limit=limit)


@router.post("/activate")
def activate_memory(request: MemoryActivateRequest) -> dict:
    return alpha_service.activate_memory(request.query, request.max_nodes, request.max_depth)


@router.get("/drift-check")
def memory_drift_check() -> dict:
    return alpha_service.memory_drift_check()
