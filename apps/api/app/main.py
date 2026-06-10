from datetime import datetime, timezone
from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


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
        id="datagate",
        name="DataGate",
        state="warning",
        progress=58,
        summary="Scoring source quality, deduplicating, and filtering unsafe inputs.",
        metric_label="quality",
        metric_value="0.74 avg",
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
    return PipelineStatus(
        generated_at=datetime.now(timezone.utc),
        system_state="mock",
        stages=MOCK_STAGES,
    )
