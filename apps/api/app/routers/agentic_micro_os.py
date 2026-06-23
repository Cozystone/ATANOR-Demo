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
from packages.agentic_micro_os.host_executor import HostExecutionRequest, HostExecutor
from packages.agentic_micro_os.loop import BoundedAgentLoop, draft_skill_from_loop
from packages.agentic_micro_os.mcp_allowlist import MCPAllowlistGateway, MCPValidationRequest, default_descriptors
from packages.agentic_micro_os.permission_gate import (
    AutonomySubSwitches,
    AutonomyTier,
    PermissionGate,
    PermissionScope,
)
from packages.agentic_micro_os.review_queue import ReviewQueue, ReviewStatus
from packages.agentic_micro_os.splatra_evaluator import SplatraCosmosEvaluator, SplatraEvaluationRequest
from packages.agentic_micro_os.web_explorer_loop import (
    FixtureOpenWebFetcher,
    HermesWebExplorerLoop,
    OpenWebExplorerConfig,
    OpenWebExplorerLoop,
    WebExplorerConfig,
    WebPageInput,
)
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
    "skill_auto_promoted": False,
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
OPEN_WEB_EXPLORER_RUNS: dict[str, dict[str, Any]] = {}
REVIEW_QUEUE = ReviewQueue()
PERMISSION_GATE = PermissionGate()


def _make_host_executor(base_path: Path | None = None) -> HostExecutor:
    root = base_path or PROJECT_ROOT
    return HostExecutor(
        gate=PERMISSION_GATE,
        project_root=PROJECT_ROOT,
        runtime_tmp_dir=root / "runtime" / "agentic_micro_os" / "tmp",
    )


HOST_EXECUTOR = _make_host_executor()


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


class OpenWebFixtureApiInput(BaseModel):
    url: str
    html: str


class OpenWebExplorerRunApiRequest(BaseModel):
    goal: str = "open web research for ATANOR local TTS, SPLATRA, Turbovec, MCP security, Hermes-style agents"
    seed_urls: list[str] = Field(default_factory=lambda: ["https://example.com/fish"])
    fixtures: list[OpenWebFixtureApiInput] = Field(default_factory=lambda: [
        OpenWebFixtureApiInput(
            url="https://example.com/fish",
            html="<html><title>Fish S2 runtime</title><body>Fish Speech local TTS runtime requires isolated Python and model weights outside the repository. <a href='https://example.com/splatra'>SPLATRA particles</a></body></html>",
        ),
        OpenWebFixtureApiInput(
            url="https://example.com/splatra",
            html="<html><title>SPLATRA particles</title><body>SPLATRA WebGPU particle rendering uses compression, quantization, and bounded LOD budgets.</body></html>",
        ),
    ])
    max_pages: int = 300
    max_depth: int = 3
    max_runtime_sec: int = 21600
    max_bytes_per_page: int = 250_000
    per_domain_delay_sec: float = 3.0
    max_pages_per_domain: int = 50
    max_candidate_drafts: int = 200
    max_skill_drafts: int = 50
    live_web: bool = False


class ReviewDecideApiRequest(BaseModel):
    item_id: str
    decision: ReviewStatus
    reviewer: str = "operator"
    reason: str = ""
    approved_for: str = "draft_only"


class ReviewImportWebRunApiRequest(BaseModel):
    run_id: str | None = None
    run_payload: dict[str, Any] | None = None


class PermissionTierSetApiRequest(BaseModel):
    tier: str = "DRAFT_PROPOSAL"
    operator_id: str = "operator"


class FullHostEnableApiRequest(BaseModel):
    enabled_by: str = "operator"
    typed_phrase: str = ""
    duration_sec: int = 600
    sub_switches: dict[str, bool] = Field(default_factory=dict)


class FullHostDisableApiRequest(BaseModel):
    operator_id: str = "operator"
    reason: str = "operator disabled"


class PermissionVerifyActionApiRequest(BaseModel):
    scope: str = "read_summary"
    action: str = "status check"
    operator_id: str = "operator"
    signed_token: str | None = None


class EmergencyStopApiRequest(BaseModel):
    operator_id: str = "operator"
    reason: str = "operator emergency stop"


class HostExecutorExecuteApiRequest(BaseModel):
    action_type: str = "echo"
    path: str = ""
    content: str = ""
    max_bytes: int = 4096
    max_entries: int = 50
    safe_test_token: str = ""
    operator_id: str = "operator"


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
                "open_web_v1": True,
                "fixed_allowlist_required": False,
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
        "permission_gate": PERMISSION_GATE.status(),
    }


@router.get("/permission/tier")
def permission_tier() -> dict[str, Any]:
    return {**SAFETY_FLAGS, **PERMISSION_GATE.status()}


@router.post("/permission/tier/set")
def permission_tier_set(request: PermissionTierSetApiRequest) -> dict[str, Any]:
    try:
        result = PERMISSION_GATE.set_tier(AutonomyTier(request.tier), operator_id=request.operator_id)
    except ValueError as exc:
        return {**SAFETY_FLAGS, "allowed": False, "reason": str(exc), **PERMISSION_GATE.status()}
    return {**SAFETY_FLAGS, **result}


@router.post("/permission/full-host/enable")
def permission_full_host_enable(request: FullHostEnableApiRequest) -> dict[str, Any]:
    result = PERMISSION_GATE.enable_full_host(
        enabled_by=request.enabled_by,
        typed_phrase=request.typed_phrase,
        duration_sec=request.duration_sec,
        sub_switches=AutonomySubSwitches.from_mapping(request.sub_switches),
    )
    return {**SAFETY_FLAGS, **result}


@router.post("/permission/full-host/disable")
def permission_full_host_disable(request: FullHostDisableApiRequest) -> dict[str, Any]:
    result = PERMISSION_GATE.disable_full_host(operator_id=request.operator_id, reason=request.reason)
    return {**SAFETY_FLAGS, **result}


@router.get("/permission/full-host/status")
def permission_full_host_status() -> dict[str, Any]:
    return {**SAFETY_FLAGS, **PERMISSION_GATE.status()}


@router.post("/permission/full-host/emergency-stop")
def permission_full_host_emergency_stop(request: EmergencyStopApiRequest) -> dict[str, Any]:
    result = PERMISSION_GATE.trigger_emergency_stop(operator_id=request.operator_id, reason=request.reason)
    return {**SAFETY_FLAGS, **result}


@router.post("/permission/verify-action")
def permission_verify_action(request: PermissionVerifyActionApiRequest) -> dict[str, Any]:
    try:
        result = PERMISSION_GATE.verify_action(
            PermissionScope(request.scope),
            action=request.action,
            operator_id=request.operator_id,
            signed_token=request.signed_token,
        )
    except ValueError as exc:
        return {**SAFETY_FLAGS, "allowed": False, "reason": str(exc), **PERMISSION_GATE.status()}
    return {**SAFETY_FLAGS, **result}


@router.get("/host-executor/status")
def host_executor_status() -> dict[str, Any]:
    return {**SAFETY_FLAGS, **HOST_EXECUTOR.status()}


@router.post("/host-executor/execute")
def host_executor_execute(request: HostExecutorExecuteApiRequest) -> dict[str, Any]:
    result = HOST_EXECUTOR.execute(
        HostExecutionRequest(
            action_type=request.action_type,
            path=request.path,
            content=request.content,
            max_bytes=request.max_bytes,
            max_entries=request.max_entries,
            safe_test_token=request.safe_test_token,
            operator_id=request.operator_id,
        )
    )
    return {
        **SAFETY_FLAGS,
        **result.to_dict(),
        "production_store_mutated": False,
        "local_brain_write": False,
        "candidate_promotion": False,
        "auto_commit": False,
        "auto_push": False,
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


@router.get("/web-explorer/open/status")
def open_web_explorer_status() -> dict[str, Any]:
    return {
        **SAFETY_FLAGS,
        "available": True,
        "proof_only": True,
        "fixed_allowlist_required": False,
        "live_web_default": False,
        "runs": len(OPEN_WEB_EXPLORER_RUNS),
        "default_limits": {
            "max_pages": 300,
            "max_depth": 3,
            "max_runtime_sec": 21600,
            "max_bytes_per_page": 250_000,
            "per_domain_delay_sec": 3,
            "max_pages_per_domain": 50,
            "max_candidate_drafts": 200,
            "max_skill_drafts": 50,
        },
        "denylist": ["localhost/internal IPs", "login/account/payment/upload patterns", "download-like URLs", "credentialed tokens/secrets"],
    }


@router.post("/web-explorer/open/run")
def open_web_explorer_run(request: OpenWebExplorerRunApiRequest) -> dict[str, Any]:
    config = OpenWebExplorerConfig(
        goal=request.goal,
        seed_urls=request.seed_urls,
        max_pages=max(1, min(request.max_pages, 300)),
        max_depth=max(0, min(request.max_depth, 3)),
        max_runtime_sec=max(1, min(request.max_runtime_sec, 21600)),
        max_bytes_per_page=max(1024, min(request.max_bytes_per_page, 250_000)),
        per_domain_delay_sec=max(0.0, min(request.per_domain_delay_sec, 30.0)),
        max_pages_per_domain=max(1, min(request.max_pages_per_domain, 50)),
        max_candidate_drafts=max(0, min(request.max_candidate_drafts, 200)),
        max_skill_drafts=max(0, min(request.max_skill_drafts, 50)),
        fetch_live_web=request.live_web,
    )
    fetcher = None if request.live_web else FixtureOpenWebFetcher({fixture.url: fixture.html for fixture in request.fixtures})
    result = OpenWebExplorerLoop(config, fetcher=fetcher).run().to_dict()
    OPEN_WEB_EXPLORER_RUNS[str(result["run_id"])] = result
    WEB_EXPLORER_SKILL_DRAFTS.extend(result["skill_drafts"])  # type: ignore[arg-type]
    return {**SAFETY_FLAGS, **result}


@router.get("/web-explorer/open/runs/{run_id}")
def open_web_explorer_run_status(run_id: str) -> dict[str, Any]:
    return {**SAFETY_FLAGS, "run": OPEN_WEB_EXPLORER_RUNS.get(run_id)}


@router.get("/review/status")
def review_status() -> dict[str, Any]:
    return {**SAFETY_FLAGS, **REVIEW_QUEUE.status()}


@router.get("/review/items")
def review_items(item_type: str | None = None, risk_level: str | None = None, status: str | None = None) -> dict[str, Any]:
    return {
        **SAFETY_FLAGS,
        **REVIEW_QUEUE.status(),
        "items": [item.to_dict() for item in REVIEW_QUEUE.list_items(item_type=item_type, risk_level=risk_level, status=status)],
    }


@router.get("/review/items/{item_id}")
def review_item(item_id: str) -> dict[str, Any]:
    item = REVIEW_QUEUE.get(item_id)
    return {**SAFETY_FLAGS, "item": item.to_dict() if item else None}


@router.post("/review/decide")
def review_decide(request: ReviewDecideApiRequest) -> dict[str, Any]:
    if request.item_id not in REVIEW_QUEUE.items:
        return {**SAFETY_FLAGS, "allowed": False, "reason": "review item not found", "mutation_performed": False}
    try:
        decision = REVIEW_QUEUE.decide(
            request.item_id,
            request.decision,
            request.reviewer,
            request.reason,
            request.approved_for,  # type: ignore[arg-type]
        )
    except ValueError as exc:
        return {**SAFETY_FLAGS, "allowed": False, "reason": str(exc), "mutation_performed": False}
    item = REVIEW_QUEUE.get(request.item_id)
    return {
        **SAFETY_FLAGS,
        "allowed": True,
        "decision": decision.to_dict(),
        "item": item.to_dict() if item else None,
        "mutation_performed": False,
        "production_store_mutated": False,
        "local_brain_write": False,
        "candidate_promotion": False,
        "skill_auto_promoted": False,
    }


@router.post("/review/import-web-run")
def review_import_web_run(request: ReviewImportWebRunApiRequest) -> dict[str, Any]:
    run_payload = request.run_payload
    if run_payload is None and request.run_id:
        run_payload = OPEN_WEB_EXPLORER_RUNS.get(request.run_id) or WEB_EXPLORER_RUNS.get(request.run_id)
    if not run_payload:
        return {**SAFETY_FLAGS, "allowed": False, "reason": "web run not found", "imported": 0}
    imported = REVIEW_QUEUE.import_web_run(run_payload)
    return {
        **SAFETY_FLAGS,
        **REVIEW_QUEUE.status(),
        "allowed": True,
        "imported": len(imported),
        "items": [item.to_dict() for item in imported],
        "mutation_performed": False,
        "production_store_mutated": False,
        "local_brain_write": False,
        "candidate_promotion": False,
        "skill_auto_promoted": False,
    }


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
