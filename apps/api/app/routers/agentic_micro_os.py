from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from packages.agentic_micro_os.action_bus import DashboardActionBus
from packages.agentic_micro_os.brain_access import BrainAccessRequest, BrainAccessRoad
from packages.agentic_micro_os.browser_read import BrowserReadConnector, BrowserReadRequest
from packages.agentic_micro_os.capabilities import CapabilityKernel
from packages.agentic_micro_os.loop import BoundedAgentLoop, draft_skill_from_loop
from packages.agentic_micro_os.mcp_allowlist import MCPAllowlistGateway, MCPValidationRequest, default_descriptors
from packages.agentic_micro_os.splatra_evaluator import SplatraCosmosEvaluator, SplatraEvaluationRequest
from packages.agentic_micro_os.web_explorer_loop import HermesWebExplorerLoop, WebExplorerConfig, WebPageInput
from packages.hermes_intake.scanner import scan_repo


router = APIRouter(prefix="/api/agentic-os", tags=["agentic-micro-os"])

PROJECT_ROOT = Path(__file__).resolve().parents[4]
HERMES_REPO = PROJECT_ROOT / "external_repos" / "hermes-agent"


SAFETY_FLAGS = {
    "agentic_micro_os_available": True,
    "proof_only": True,
    "hermes_runtime_executed": False,
    "hermes_code_copied": False,
    "external_llm": False,
    "external_sllm": False,
    "local_brain_direct_write": False,
    "local_brain_write": False,
    "production_store_direct_write": False,
    "production_store_mutated": False,
    "candidate_promotion": False,
    "unrestricted_shell": False,
    "arbitrary_js_eval": False,
    "auto_commit": False,
    "auto_push": False,
    "human_approval_required": True,
}

MODULE_STATUS = {
    "capability_kernel": "available",
    "virtual_fs": "available",
    "brain_access_road": "available",
    "splatra_cosmos_cell": "available",
    "dashboard_action_bus": "available",
    "tool_gateway": "mock_only",
    "mcp_gateway_mock": "available",
    "browser_gateway_mock": "available",
    "browser_read": "proof_only",
    "mcp_allowlist_gateway": "proof_only",
    "splatra_evaluator": "proof_only",
    "web_explorer_loop": "proof_only",
    "cloud_gateway_mock": "available",
    "hermes_intake": "architecture_extracted",
}

WEB_EXPLORER_RUNS: dict[str, dict[str, Any]] = {}
WEB_EXPLORER_SKILL_DRAFTS: list[dict[str, Any]] = []


class DashboardActionRequest(BaseModel):
    action_type: str = Field(..., examples=["set_orb_state"])
    payload: dict[str, Any] = Field(default_factory=dict)


class BrainAccessApiRequest(BaseModel):
    target: str = "local_brain"
    operation: str = "local_brain_read_redacted_summary"
    query: str = ""
    scope: str = "proof"
    redaction_level: str = "redacted"
    purpose: str = "proof-only API request"
    requested_by_loop_id: str = "agentic_os_api"


class LoopProposeRequest(BaseModel):
    goal: str = "Inspect SPLATRA Cosmos Cell and draft a safe proposal."
    max_cycles: int = 1


class BrowserReadApiRequest(BaseModel):
    url: str = "http://127.0.0.1:3041/?section=agent-os"
    visible_text: str = "Agentic Micro-OS proof-only status"
    metadata: dict[str, Any] = Field(default_factory=dict)
    max_chars: int = 1200


class MCPValidateApiRequest(BaseModel):
    descriptor: str = "render_preview"
    descriptor_hash: str | None = None
    method: str = "render_preview"
    payload: dict[str, Any] = Field(default_factory=lambda: {"scene": "orb"})


class SplatraEvaluateApiRequest(BaseModel):
    candidate_id: str = "splatra_candidate_0"
    particle_budget: int = 50_000
    target_fps: int = 60
    include_city_proof: bool = False
    emotion_probe: dict[str, float] = Field(default_factory=lambda: {"valence": 0.2, "arousal": 0.6, "audio_energy": 0.0})


class WebExplorerPageApiInput(BaseModel):
    url: str
    title: str = ""
    visible_text: str = ""
    depth: int = 0


class WebExplorerRunOnceApiRequest(BaseModel):
    goal: str = "research local TTS alternatives and SPLATRA particle rendering"
    allowed_domains: list[str] = Field(default_factory=lambda: ["docs.local", "127.0.0.1", "localhost"])
    pages: list[WebExplorerPageApiInput] = Field(default_factory=list)
    max_pages: int = 30
    max_depth: int = 2
    max_runtime_sec: int = 21600
    max_candidate_drafts: int = 100
    max_skill_drafts: int = 20


@router.get("/status")
def status() -> dict[str, Any]:
    browser = BrowserReadConnector()
    mcp = MCPAllowlistGateway()
    splatra = SplatraCosmosEvaluator()
    return {
        **SAFETY_FLAGS,
        "modules": MODULE_STATUS,
        "tool_gateway_phase1": {
            "browser_read": browser.status(),
            "mcp_allowlist": mcp.status(),
            "splatra_evaluator": splatra.status(),
            "web_explorer_loop": {
                "available": True,
                "proof_only": True,
                "real_long_daemon": False,
                "private_credentialed_browsing": False,
                "aggressive_crawling": False,
            },
        },
        "blocked_actions": [
            "unrestricted_shell",
            "arbitrary_js_eval",
            "local_brain_direct_write",
            "production_store_direct_write",
            "candidate_promotion",
            "auto_commit",
            "auto_push",
        ],
    }


@router.get("/browser-read/status")
def browser_read_status() -> dict[str, Any]:
    return {**SAFETY_FLAGS, **BrowserReadConnector().status()}


@router.post("/browser-read")
def browser_read(request: BrowserReadApiRequest) -> dict[str, Any]:
    kernel = CapabilityKernel()
    token = kernel.issue("browser_read", reason="agentic-os browser-read proof")
    result = BrowserReadConnector(kernel=kernel).read(
        BrowserReadRequest(
            url=request.url,
            visible_text=request.visible_text,
            metadata=request.metadata,
            max_chars=request.max_chars,
        ),
        token,
    )
    return {**SAFETY_FLAGS, **result.to_dict()}


@router.get("/mcp/status")
def mcp_status() -> dict[str, Any]:
    return {**SAFETY_FLAGS, **MCPAllowlistGateway().status()}


@router.post("/mcp/validate")
def mcp_validate(request: MCPValidateApiRequest) -> dict[str, Any]:
    kernel = CapabilityKernel()
    token = kernel.issue("mcp_allowlist_validate", reason="agentic-os MCP allowlist proof")
    descriptors = default_descriptors()
    descriptor_hash = request.descriptor_hash or descriptors.get(request.descriptor, descriptors["render_preview"]).descriptor_hash
    result = MCPAllowlistGateway(descriptors=descriptors, kernel=kernel).validate(
        MCPValidationRequest(
            descriptor=request.descriptor,
            descriptor_hash=descriptor_hash,
            method=request.method,
            payload=request.payload,
        ),
        token,
    )
    return {**SAFETY_FLAGS, **result.to_dict()}


@router.post("/splatra/evaluate")
def splatra_evaluate(request: SplatraEvaluateApiRequest) -> dict[str, Any]:
    kernel = CapabilityKernel()
    token = kernel.issue("splatra_cosmos_evaluate", reason="agentic-os SPLATRA evaluator proof")
    result = SplatraCosmosEvaluator(kernel=kernel).evaluate(
        SplatraEvaluationRequest(
            candidate_id=request.candidate_id,
            particle_budget=request.particle_budget,
            target_fps=request.target_fps,
            include_city_proof=request.include_city_proof,
            emotion_probe=request.emotion_probe,
        ),
        token,
    )
    return {**SAFETY_FLAGS, **result.to_dict()}


@router.get("/web-explorer/status")
def web_explorer_status() -> dict[str, Any]:
    return {
        **SAFETY_FLAGS,
        "available": True,
        "proof_only": True,
        "runs": len(WEB_EXPLORER_RUNS),
        "skill_drafts": len(WEB_EXPLORER_SKILL_DRAFTS),
        "default_limits": {
            "max_pages": 30,
            "max_depth": 2,
            "max_runtime_sec": 21600,
            "max_candidate_drafts": 100,
            "max_skill_drafts": 20,
        },
    }


@router.post("/web-explorer/run-once")
def web_explorer_run_once(request: WebExplorerRunOnceApiRequest) -> dict[str, Any]:
    config = WebExplorerConfig(
        goal=request.goal,
        allowed_domains=request.allowed_domains,
        pages=[
            WebPageInput(
                url=page.url,
                title=page.title,
                visible_text=page.visible_text,
                depth=page.depth,
            )
            for page in request.pages
        ],
        max_pages=max(1, min(request.max_pages, 30)),
        max_depth=max(0, min(request.max_depth, 4)),
        max_runtime_sec=max(1, min(request.max_runtime_sec, 21600)),
        max_candidate_drafts=max(0, min(request.max_candidate_drafts, 100)),
        max_skill_drafts=max(0, min(request.max_skill_drafts, 20)),
    )
    result = HermesWebExplorerLoop(config).run_once().to_dict()
    WEB_EXPLORER_RUNS[str(result["run_id"])] = result
    WEB_EXPLORER_SKILL_DRAFTS.extend(result["skill_drafts"])  # type: ignore[arg-type]
    return {**SAFETY_FLAGS, **result}


@router.get("/web-explorer/runs/{run_id}")
def web_explorer_run(run_id: str) -> dict[str, Any]:
    return {**SAFETY_FLAGS, "run": WEB_EXPLORER_RUNS.get(run_id)}


@router.get("/skills/drafts")
def skill_drafts() -> dict[str, Any]:
    return {**SAFETY_FLAGS, "skill_drafts": WEB_EXPLORER_SKILL_DRAFTS}


@router.post("/action/validate")
def validate_action(request: DashboardActionRequest) -> dict[str, Any]:
    kernel = CapabilityKernel()
    token = kernel.issue("dashboard_action", reason="agentic-os status surface proof")
    result = DashboardActionBus(kernel).validate(request.action_type, request.payload, token)
    return {**SAFETY_FLAGS, **result}


@router.post("/brain-access/request")
def brain_access_request(request: BrainAccessApiRequest) -> dict[str, Any]:
    road = BrainAccessRoad()
    response = road.request(
        BrainAccessRequest(
            target=request.target,  # type: ignore[arg-type]
            operation=request.operation,
            query=request.query,
            scope=request.scope,
            redaction_level=request.redaction_level,
            purpose=request.purpose,
            requested_by_loop_id=request.requested_by_loop_id,
        )
    )
    return {**SAFETY_FLAGS, "request": request.model_dump(), "response": asdict(response)}


@router.post("/loop/propose")
def loop_propose(request: LoopProposeRequest) -> dict[str, Any]:
    loop = BoundedAgentLoop(goal=request.goal, max_cycles=max(1, min(request.max_cycles, 3)))
    state = loop.run()
    skill = draft_skill_from_loop(state)
    return {
        **SAFETY_FLAGS,
        "loop": state.to_dict(),
        "skill_draft": asdict(skill),
        "patch_proposals": [asdict(proposal) for proposal in state.patch_proposals],
        "approval_required": True,
    }


@router.get("/hermes-intake/status")
def hermes_intake_status() -> dict[str, Any]:
    if not HERMES_REPO.exists():
        return {
            **SAFETY_FLAGS,
            "repo_present": False,
            "status": "not_cloned",
            "architecture_extracted": False,
        }
    report = scan_repo(HERMES_REPO)
    return {
        **SAFETY_FLAGS,
        "repo_present": True,
        "status": "architecture_extracted",
        "architecture_extracted": True,
        "source_commit": report.source_commit,
        "license": report.license_detected,
        "mit_compatible": report.mit_compatible,
        "reusable_architecture_patterns": report.reusable_architecture_patterns,
        "rejected_patterns": report.forbidden_or_high_risk_components,
    }
