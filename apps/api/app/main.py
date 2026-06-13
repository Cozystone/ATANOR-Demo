from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.routers.cloud_brain import router as cloud_brain_router
from app.routers.datagate import router as datagate_router
from app.routers.factory import router as factory_router
from app.routers.graph import router as graph_router
from app.routers.graphrag import router as graphrag_router
from app.routers.guard import router as guard_router
from app.routers.harvest import router as harvest_router
from app.routers.hybrid_network import router as hybrid_network_router
from app.routers.learning import router as learning_router
from app.routers.memory import router as memory_router
from app.routers.neuro import router as neuro_router
from app.routers.ontology import router as ontology_router
from app.routers.oven import router as oven_router
from app.routers.telemetry import router as telemetry_router
from app.services.alpha_services import alpha_service, telemetry_gpu
from app.services.crash_safety import create_boot_shadow_backups
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


@asynccontextmanager
async def lifespan(_app: FastAPI):
    create_boot_shadow_backups()
    yield


app = FastAPI(
    title="Homage1.0 API",
    description="Mock API for the Homage1.0 BakeBoard skeleton.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3030",
        "http://127.0.0.1:3030",
        "https://homage-alpha.vercel.app",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app|http://localhost:\d+|http://127\.0\.0\.1:\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def allow_browser_local_companion(request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Private-Network"] = "true"
    return response

app.include_router(datagate_router)
app.include_router(harvest_router)
app.include_router(hybrid_network_router)
app.include_router(learning_router)
app.include_router(cloud_brain_router)
app.include_router(factory_router)
app.include_router(graph_router)
app.include_router(ontology_router)
app.include_router(graphrag_router)
app.include_router(guard_router)
app.include_router(memory_router)
app.include_router(neuro_router)
app.include_router(telemetry_router)
app.include_router(oven_router)


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


def alpha_stage(
    stage_id: str,
    name: str,
    status: dict,
    idle_summary: str,
    done_summary: str,
    metric_label: str,
    metric_value: str,
) -> PipelineStage:
    state = status.get("state", "idle")
    stage_state: StageState = (
        "running" if state == "running" else "complete" if state == "completed" else "warning" if state == "failed" else "idle"
    )
    return PipelineStage(
        id=stage_id,
        name=name,
        state=stage_state,
        progress=100 if state == "completed" else 50 if state == "running" else 0 if state == "idle" else 100,
        summary=done_summary if state == "completed" else status.get("error") or idle_summary,
        metric_label=metric_label,
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
    ontology_status = alpha_service.ontology_status()
    graphrag_status = alpha_service.graphrag_status()
    guard_status = alpha_service.guard_status()
    memory_status = alpha_service.memory_status()
    oven_status = alpha_service.oven_status()
    gpu_status = telemetry_gpu()
    stages = [
        MOCK_STAGES[0],
        datagate_stage(datagate_status),
        alpha_stage(
            "ontology-forge",
            "Ontology Forge",
            ontology_status,
            "Ready to extract concept nodes and relation edges from cleaned documents.",
            "Ontology graph files are available for GraphRAG.",
            "graph",
            f"{ontology_status.get('node_count', 0)} nodes / {ontology_status.get('edge_count', 0)} edges",
        ),
        alpha_stage(
            "homage-oven",
            "Homage Oven",
            oven_status,
            "Training scaffold is ready for a safe dry-run.",
            "Dry-run produced a loss trace and checkpoint manifest.",
            "last loss",
            str(oven_status.get("last_loss") or "not run"),
        ),
        alpha_stage(
            "graphrag",
            "GraphRAG",
            graphrag_status,
            "Ready to retrieve evidence from cleaned docs and ontology graph.",
            "Latest query produced an inspectable evidence bundle.",
            "confidence",
            str(graphrag_status.get("confidence") or 0),
        ),
        alpha_stage(
            "knowledge-bakery",
            "Knowledge Bakery",
            memory_status,
            "Ready to persist sentence components, token transitions, phrase nodes, and local 3D vectors.",
            "Local append-only memory store and activation index are available.",
            "memory",
            f"{memory_status.get('node_count', 0)} nodes / {memory_status.get('transition_count', 0)} transitions",
        ),
        alpha_stage(
            "guardrail",
            "Guardrail",
            guard_status,
            "Ready to check draft claims against evidence and ontology.",
            "Latest guard report is available.",
            "guard score",
            str(guard_status.get("overall_guard_score") or 0),
        ),
        PipelineStage(
            id="gpu-monitor",
            name="GPU Monitor",
            state="complete" if gpu_status.get("available") else "warning",
            progress=100 if gpu_status.get("available") else 35,
            summary=gpu_status.get("message") or "Local GPU telemetry is available.",
            metric_label="vram",
            metric_value=(
                f"{gpu_status.get('vram_used', 0)} / {gpu_status.get('vram_total', 0)} MB"
                if gpu_status.get("available")
                else "fallback"
            ),
        ),
    ]
    return PipelineStatus(
        generated_at=datetime.now(timezone.utc),
        system_state="alpha_active",
        stages=stages,
    )
