from contextlib import asynccontextmanager
from datetime import datetime, timezone
import os
from pathlib import Path
import sys
from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.services.desktop_paths import configure_desktop_data_dir


def _configure_runtime_data_dir_from_args() -> None:
    """Honor the Tauri sidecar data directory before any data services run."""

    if "--operator" in sys.argv:
        os.environ["ATANOR_OPERATOR"] = "1"
        os.environ["ATANOR_AUTO_START_DAEMON"] = "1"
        os.environ["ATANOR_AUTOSTART_DAEMON"] = "1"
        os.environ["HOMAGE_OPERATOR"] = "1"
        os.environ["HOMAGE_AUTO_START_DAEMON"] = "1"
    if "--data-dir" not in sys.argv:
        return
    try:
        index = sys.argv.index("--data-dir")
        data_dir = sys.argv[index + 1]
    except (ValueError, IndexError):
        return
    configure_desktop_data_dir(data_dir, chdir=True)


_configure_runtime_data_dir_from_args()

from app.routers.brain_sync import router as brain_sync_router
from app.routers.answer_quality import router as answer_quality_router
from app.routers.base_brain import router as base_brain_router
from app.routers.brain_graph import router as brain_graph_router
from app.routers.cloud_brain import router as cloud_brain_router
from app.routers.contribution import router as contribution_router
from app.routers.cortex import router as cortex_router
from app.routers.datagate import router as datagate_router
from app.routers.dual_brain import router as dual_brain_router
from app.routers.factory import router as factory_router
from app.routers.graph import router as graph_router
from app.routers.graph_hub import router as graph_hub_router
from app.routers.graphrag import router as graphrag_router
from app.routers.guard import router as guard_router
from app.routers.harvest import router as harvest_router
from app.routers.hybrid_network import router as hybrid_network_router
from app.routers.learning import router as learning_router
from app.routers.memory import router as memory_router
from app.routers.neuro import router as neuro_router
from app.routers.ontology import router as ontology_router
from app.routers.oven import router as oven_router
from app.routers.q_cortex import router as q_cortex_router
from app.routers.seed_research import router as seed_research_router
from app.routers.storage import router as storage_router
from app.routers.surface_brain import router as surface_brain_router
from app.routers.telemetry import router as telemetry_router
from app.routers.working_memory import router as working_memory_router
from app.services.alpha_services import alpha_service, telemetry_gpu
from app.services.crash_safety import create_boot_shadow_backups
from app.services.datagate_service import DataGateStatus, datagate_service
from app.services.ingestion_stream import cleaned_directory_watcher, graph_event_hub
from knowledge_bakery import daemon_status as learning_daemon_status
from knowledge_bakery import start_daemon
from neuro_efficiency import build_hardware_benchmark

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
    try:
        skip_benchmark = os.getenv("ATANOR_SKIP_STARTUP_BENCHMARK", os.getenv("HOMAGE_SKIP_STARTUP_BENCHMARK")) == "1"
        build_hardware_benchmark({"run_probes": not skip_benchmark})
    except Exception:
        pass
    cleaned_directory_watcher.start()
    if os.getenv("ATANOR_AUTO_START_DAEMON", os.getenv("ATANOR_AUTOSTART_DAEMON", os.getenv("HOMAGE_AUTO_START_DAEMON"))) == "1":
        start_daemon(interval_seconds=30, resume=True)
    await graph_event_hub.publish_snapshot(event_type="graph_snapshot", trigger="api_startup", limit=5000)
    try:
        yield
    finally:
        await cleaned_directory_watcher.stop()


app = FastAPI(
    title="ATANOR API",
    description="ATANOR local-first Ghost Shell and Payload Vault API.",
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
        "http://localhost:3022",
        "http://127.0.0.1:3022",
        "tauri://localhost",
        "asset://localhost",
        "http://tauri.localhost",
        "https://tauri.localhost",
        "null",
        "https://atanor-alpha.vercel.app",
        "https://homage-alpha.vercel.app",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app|http://localhost:\d+|http://127\.0\.0\.1:\d+|tauri://.*|asset://.*|https?://.*\.tauri\.localhost",
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
app.include_router(answer_quality_router)
app.include_router(base_brain_router)
app.include_router(brain_graph_router)
app.include_router(harvest_router)
app.include_router(hybrid_network_router)
app.include_router(brain_sync_router)
app.include_router(learning_router)
app.include_router(cloud_brain_router)
app.include_router(contribution_router)
app.include_router(cortex_router)
app.include_router(dual_brain_router)
app.include_router(factory_router)
app.include_router(graph_router)
app.include_router(graph_hub_router)
app.include_router(ontology_router)
app.include_router(graphrag_router)
app.include_router(guard_router)
app.include_router(memory_router)
app.include_router(working_memory_router)
app.include_router(neuro_router)
app.include_router(q_cortex_router)
app.include_router(seed_research_router)
app.include_router(storage_router)
app.include_router(surface_brain_router)
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


def harvest_stage() -> PipelineStage:
    raw_dir = Path(os.environ.get("ATANOR_RAW_DIR", os.environ.get("HOMAGE_RAW_DIR", "data/raw")))
    cleaned_dir = Path(os.environ.get("ATANOR_CLEANED_DIR", os.environ.get("HOMAGE_CLEANED_DIR", "data/cleaned")))
    raw_files = [path for ext in ("*.txt", "*.md") for path in raw_dir.rglob(ext)] if raw_dir.exists() else []
    cleaned_files = [path for ext in ("*.txt", "*.md") for path in cleaned_dir.rglob(ext)] if cleaned_dir.exists() else []
    daemon = learning_daemon_status()
    worker_alive = bool(daemon.get("worker_alive"))
    queued = len(raw_files)
    processed = len(cleaned_files)
    state: StageState = "running" if worker_alive else "warning" if daemon.get("desired_running") else "idle"
    if worker_alive and queued == 0:
        summary = "Continuous ingestion stream is awake and waiting for payloads."
        progress = 1
    elif worker_alive:
        summary = "Continuous ingestion stream is ingesting raw payload files."
        progress = 50
    else:
        summary = "Continuous ingestion stream is not alive; self-healing daemon status should restart it."
        progress = 0
    return PipelineStage(
        id="harvest",
        name="Harvest",
        state=state,
        progress=progress,
        summary=summary,
        metric_label="stream",
        metric_value=f"{queued} queued / {processed} vaulted",
    )


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
        harvest_stage(),
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
            "atanor-oven",
            "ATANOR Oven",
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
