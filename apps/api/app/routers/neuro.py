from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from neuro_efficiency import build_hardware_benchmark, build_neuro_efficiency_plan, build_sustained_run_plan


router = APIRouter(prefix="/api/neuro", tags=["neuro-efficiency"])


class NeuroPlanRequest(BaseModel):
    text: str | None = None
    task_type: str | None = None
    target_device: str | None = None
    token_budget: int | None = Field(default=None, ge=64, le=8192)
    module_budget: int | None = Field(default=None, ge=2, le=7)


class SustainedRunPlanRequest(BaseModel):
    hardware_profile: dict[str, Any] | None = None
    target_nodes: int | None = Field(default=None, ge=1_000, le=250_000)
    target_edges: int | None = Field(default=None, ge=2_000, le=1_500_000)
    duration_hours: int | None = Field(default=None, ge=1, le=720)


class HardwareBenchmarkRequest(BaseModel):
    hardware_profile: dict[str, Any] | None = None
    run_probes: bool = True


@router.get("/plan")
def neuro_plan() -> dict[str, Any]:
    return build_neuro_efficiency_plan()


@router.post("/plan")
def neuro_plan_for_workload(payload: NeuroPlanRequest) -> dict[str, Any]:
    return build_neuro_efficiency_plan(payload.model_dump(exclude_none=True))


@router.get("/stability")
def sustained_run_plan() -> dict[str, Any]:
    return build_sustained_run_plan()


@router.post("/stability")
def sustained_run_plan_for_profile(payload: SustainedRunPlanRequest) -> dict[str, Any]:
    return build_sustained_run_plan(payload.model_dump(exclude_none=True))


@router.get("/benchmark")
def hardware_benchmark() -> dict[str, Any]:
    return build_hardware_benchmark()


@router.post("/benchmark")
def hardware_benchmark_for_profile(payload: HardwareBenchmarkRequest) -> dict[str, Any]:
    return build_hardware_benchmark(payload.model_dump(exclude_none=True))
