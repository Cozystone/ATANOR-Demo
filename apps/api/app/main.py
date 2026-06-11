from datetime import datetime, timezone
from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.routers.datagate import router as datagate_router
from app.services.datagate_service import DataGateStatus, datagate_service

StageState = Literal["idle", "running", "warning", "complete"]


class PipelineStage(BaseModel):
    id: str
    name: str
    state: StageState
    progress: int
    summary: str
    metric_label: str
    metric_value: str


class PipelineStatus(BaseModel):
    generated_at: datetime
    system_state: str
    stages: list[PipelineStage]


app = FastAPI(
    title="Homage1.0 API",
    description="Mock API for the Homage1.0 BakeBoard skeleton.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(datagate_router)


def datagate_stage(status: DataGateStatus) -> PipelineStage:
    state_map: dict[str, StageState] = {
        "idle": "idle",
        "running": "running",
        "completed": "complete",
        "failed": "warning",
    }
    if status.state == "idle":
        progress = 0
        metric_value = "not run"
        summary = "Ready to score source quality, deduplicate, and filter unsafe inputs."
    elif status.state == "running":
        progress = 50
        metric_value = "running"
        summary = "DataGate is processing local raw documents."
    elif status.state == "completed":
        progress = 100
        metric_value = f"{status.accepted}/{status.total} accepted"
        summary = "Latest DataGate run completed with deterministic document partitioning."
    else:
        progress = 100
        metric_value = "failed"
        summary = status.error or "Latest DataGate run failed."

    return PipelineStage(
        id="datagate",
        name="DataGate",
        state=state_map[status.state],
        progress=progress,
        summary=summary,
        metric_label="quality gate",
        metric_value=metric_value,
    )


MOCK_STAGES = [
    PipelineStage(
        id="harvest",
        name="Harvest",
        state="running",
        progress=42,
        summary="Collecting source documents and recording provenance.",
        metric_label="documents",
        metric_value="128 queued",
    ),
    PipelineStage(
        id="ontology-forge",
        name="Ontology Forge",
        state="running",
        progress=35,
        summary="Extracting concepts, relations, and candidate graph triples.",
        metric_label="triples",
        metric_value="312 draft",
    ),
    PipelineStage(
        id="homage-oven",
        name="Homage Oven",
        state="idle",
        progress=10,
        summary="Preparing tokenizer, dataset builder, and training loop hooks.",
        metric_label="checkpoint",
        metric_value="not started",
    ),
    PipelineStage(
        id="graphrag",
        name="GraphRAG",
        state="complete",
        progress=100,
        summary="Mock retrieval trace is ready for dashboard integration.",
        metric_label="evidence",
        metric_value="7 bundles",
    ),
    PipelineStage(
        id="guardrail",
        name="Guardrail",
        state="running",
        progress=63,
        summary="Checking unsupported claims, ontology conflicts, and policy fit.",
        metric_label="guard score",
        metric_value="0.86",
    ),
    PipelineStage(
        id="gpu-monitor",
        name="GPU Monitor",
        state="idle",
        progress=22,
        summary="Mocking VRAM, utilization, and training telemetry.",
        metric_label="vram",
        metric_value="3.2 / 16 GB",
    ),
]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/pipeline/status", response_model=PipelineStatus)
def pipeline_status() -> PipelineStatus:
    datagate_status = datagate_service.status()
    stages = [
        MOCK_STAGES[0],
        datagate_stage(datagate_status),
        *MOCK_STAGES[1:],
    ]
    return PipelineStatus(
        generated_at=datetime.now(timezone.utc),
        system_state="mock",
        stages=stages,
    )
