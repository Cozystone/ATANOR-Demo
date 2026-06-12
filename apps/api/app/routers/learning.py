from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from knowledge_bakery import daemon_checkpoint, daemon_status, resume_daemon, start_daemon, stop_daemon, tick_daemon


router = APIRouter(prefix="/api/learning/daemon", tags=["learning"])


class DaemonStartRequest(BaseModel):
    interval_seconds: int = Field(default=30, ge=5, le=3600)
    resume: bool = True


class DaemonStopRequest(BaseModel):
    reason: str = Field(default="manual", min_length=1, max_length=80)


class DaemonCheckpointRequest(BaseModel):
    reason: str = Field(default="manual", min_length=1, max_length=80)


class DaemonTickRequest(BaseModel):
    force: bool = False


@router.get("/status")
def learning_daemon_status() -> dict:
    return daemon_status()


@router.post("/start")
def learning_daemon_start(request: DaemonStartRequest) -> dict:
    return start_daemon(interval_seconds=request.interval_seconds, resume=request.resume)


@router.post("/resume")
def learning_daemon_resume(request: DaemonStartRequest) -> dict:
    return resume_daemon(interval_seconds=request.interval_seconds)


@router.post("/stop")
def learning_daemon_stop(request: DaemonStopRequest) -> dict:
    return stop_daemon(reason=request.reason)


@router.post("/checkpoint")
def learning_daemon_checkpoint(request: DaemonCheckpointRequest) -> dict:
    return daemon_checkpoint(reason=request.reason)


@router.post("/tick")
def learning_daemon_tick(request: DaemonTickRequest) -> dict:
    return tick_daemon(force=request.force)
