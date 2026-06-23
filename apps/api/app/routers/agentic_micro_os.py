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
from packages.agentic_micro_os.policy_loop import PolicyDrivenAutonomousLoop, PolicyLoopConfig
from packages.agentic_micro_os.permission_gate import (
    AutonomySubSwitches,
    AutonomyTier,
    PermissionGate,
    PermissionScope,
)
from packages.agentic_micro_os.review_queue import ReviewQueue, ReviewStatus
from packages.agentic_micro_os.scoped_patch_executor import (
    ScopedPatchExecutor,
    ScopedPatchRequest,
    ScopedPatchRollbackRequest,
)
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
from packages.neural_emotion import emit_runtime_event
from packages.neural_emotion.event_bus import EVENT_BUS
from packages.splatra_imagination import ARCHETYPES, ImaginationGenerator, ImaginationSeed, default_safety_flags, run_imagination_proof


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
    "splatra_imagination_field": "proof_only",
    "web_explorer_loop": "proof_only",
    "cloud_gateway_mock": "available",
    "hermes_intake": "architecture_extracted",
}

WEB_EXPLORER_RUNS: dict[str, dict[str, Any]] = {}
WEB_EXPLORER_SKILL_DRAFTS: list[dict[str, Any]] = []
OPEN_WEB_EXPLORER_RUNS: dict[str, dict[str, Any]] = {}
REVIEW_QUEUE = ReviewQueue()
PERMISSION_GATE = PermissionGate()
POLICY_LOOP_RUNS: dict[str, dict[str, Any]] = {}


def _make_host_executor(base_path: Path | None = None) -> HostExecutor:
    root = base_path or PROJECT_ROOT
    return HostExecutor(
        gate=PERMISSION_GATE,
        project_root=PROJECT_ROOT,
        runtime_tmp_dir=root / "runtime" / "agentic_micro_os" / "tmp",
    )


HOST_EXECUTOR = _make_host_executor()


def _make_scoped_patch_executor(base_path: Path | None = None) -> ScopedPatchExecutor:
    root = base_path or PROJECT_ROOT
    return ScopedPatchExecutor(
        gate=PERMISSION_GATE,
        project_root=PROJECT_ROOT,
        backup_dir=root / "runtime" / "agentic_micro_os" / "scoped_patch_backups",
    )


SCOPED_PATCH_EXECUTOR = _make_scoped_patch_executor()


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


class SplatraImaginationGenerateApiRequest(BaseModel):
    seed_id: str = "api_imagination_0"
    archetype: str = "orb"
    randomness: float = 0.5
    valence: float = 0.0
    arousal: float = 0.45
    curiosity: float = 0.5
    speaking_energy: float = 0.0
    state: str = "imagining"
    particle_budget: int = 1600
    lod_target: int = 0
    include_particles: bool = True


class SplatraImaginationEvaluateApiRequest(BaseModel):
    particle_budget: int = 900


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


class PolicyLoopRunOnceApiRequest(BaseModel):
    loop_id: str = ""
    max_cycles: int = 1
    max_runtime_sec: int = 30
    base_web_pages: int = 3
    base_review_batch: int = 6
    base_splatra_frames: int = 1
    base_host_actions: int = 1
    allow_host_executor: bool = False
    review_queue_pressure: float = 0.0
    recent_failures: int = 0
    unsafe_request: bool = False
    voice_available: bool = False


class ScopedPatchApiRequest(BaseModel):
    target_path: str
    expected_old_text: str = ""
    replacement_text: str = ""
    reason: str = "operator scoped patch"
    operator_confirmation: str = ""
    tier_session_id: str = ""
    required_subswitches: list[str] = Field(default_factory=lambda: ["full_file_write"])
    dry_run: bool = True
    operator_id: str = "operator"


class ScopedPatchRollbackApiRequest(BaseModel):
    target_path: str
    backup_path: str
    operator_confirmation: str = ""
    tier_session_id: str = ""
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
    emit_runtime_event(
        source="permission_gate",
        event_type="permission_tier_changed",
        payload_summary=f"tier={request.tier}",
        intensity=0.7,
    )
    return {**SAFETY_FLAGS, **result}


@router.post("/permission/full-host/enable")
def permission_full_host_enable(request: FullHostEnableApiRequest) -> dict[str, Any]:
    result = PERMISSION_GATE.enable_full_host(
        enabled_by=request.enabled_by,
        typed_phrase=request.typed_phrase,
        duration_sec=request.duration_sec,
        sub_switches=AutonomySubSwitches.from_mapping(request.sub_switches),
    )
    emit_runtime_event(
        source="permission_gate",
        event_type="tier4_enabled" if result.get("allowed") else "host_action_denied",
        payload_summary=f"tier4 enable allowed={result.get('allowed')}",
        intensity=1.0,
    )
    return {**SAFETY_FLAGS, **result}


@router.post("/permission/full-host/disable")
def permission_full_host_disable(request: FullHostDisableApiRequest) -> dict[str, Any]:
    result = PERMISSION_GATE.disable_full_host(operator_id=request.operator_id, reason=request.reason)
    emit_runtime_event(
        source="permission_gate",
        event_type="tier4_disabled",
        payload_summary="tier4 disabled",
        intensity=0.7,
    )
    return {**SAFETY_FLAGS, **result}


@router.get("/permission/full-host/status")
def permission_full_host_status() -> dict[str, Any]:
    return {**SAFETY_FLAGS, **PERMISSION_GATE.status()}


@router.post("/permission/full-host/emergency-stop")
def permission_full_host_emergency_stop(request: EmergencyStopApiRequest) -> dict[str, Any]:
    result = PERMISSION_GATE.trigger_emergency_stop(operator_id=request.operator_id, reason=request.reason)
    emit_runtime_event(
        source="permission_gate",
        event_type="unsafe_request",
        payload_summary="emergency stop",
        intensity=1.35,
    )
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


def _make_policy_loop(config: PolicyLoopConfig | None = None) -> PolicyDrivenAutonomousLoop:
    return PolicyDrivenAutonomousLoop(
        config=config or PolicyLoopConfig(),
        event_bus=EVENT_BUS,
        review_queue=REVIEW_QUEUE,
        permission_gate=PERMISSION_GATE,
    )


@router.get("/policy-loop/status")
def policy_loop_status() -> dict[str, Any]:
    loop = _make_policy_loop()
    return {**SAFETY_FLAGS, **loop.status(), "runs": len(POLICY_LOOP_RUNS)}


@router.post("/policy-loop/run-once")
def policy_loop_run_once(request: PolicyLoopRunOnceApiRequest) -> dict[str, Any]:
    config = PolicyLoopConfig(
        loop_id=request.loop_id,
        max_cycles=request.max_cycles,
        max_runtime_sec=request.max_runtime_sec,
        base_web_pages=request.base_web_pages,
        base_review_batch=request.base_review_batch,
        base_splatra_frames=request.base_splatra_frames,
        base_host_actions=request.base_host_actions,
        allow_host_executor=request.allow_host_executor,
        review_queue_pressure=request.review_queue_pressure,
        recent_failures=request.recent_failures,
        unsafe_request=request.unsafe_request,
        voice_available=request.voice_available,
    )
    result = _make_policy_loop(config).run_once().to_dict()
    POLICY_LOOP_RUNS[result["loop_id"]] = result
    if result.get("stopped_reason") in {"review_requested", "emergency_stop", "rest_requested", "fatigue", "repeated_failure"}:
        emit_runtime_event(
            source="review_queue" if result.get("stopped_reason") == "review_requested" else "user_action",
            event_type="review_queue_pressure" if result.get("stopped_reason") == "review_requested" else "resting",
            payload_summary=f"policy loop stopped={result.get('stopped_reason')}",
            intensity=0.5,
        )
    return {
        **SAFETY_FLAGS,
        **result,
        "mutation_performed": False,
        "production_store_mutated": False,
        "local_brain_write": False,
        "candidate_promotion": False,
        "auto_commit": False,
        "auto_push": False,
    }


@router.get("/policy-loop/runs/{loop_id}")
def policy_loop_run(loop_id: str) -> dict[str, Any]:
    return {**SAFETY_FLAGS, "run": POLICY_LOOP_RUNS.get(loop_id)}


@router.get("/host-executor/patch/status")
def scoped_patch_status() -> dict[str, Any]:
    return {**SAFETY_FLAGS, **SCOPED_PATCH_EXECUTOR.status()}


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
    result_payload = result.to_dict()
    emit_runtime_event(
        source="host_executor",
        event_type="host_action_success" if result_payload.get("allowed") and result_payload.get("executed") else "host_action_denied",
        payload_summary=f"action={request.action_type}; allowed={result_payload.get('allowed')}; executed={result_payload.get('executed')}",
        intensity=0.75,
    )
    return {
        **SAFETY_FLAGS,
        **result_payload,
        "production_store_mutated": False,
        "local_brain_write": False,
        "candidate_promotion": False,
        "auto_commit": False,
        "auto_push": False,
    }


@router.post("/host-executor/patch/plan")
def scoped_patch_plan(request: ScopedPatchApiRequest) -> dict[str, Any]:
    result = SCOPED_PATCH_EXECUTOR.plan(
        ScopedPatchRequest(
            target_path=request.target_path,
            expected_old_text=request.expected_old_text,
            replacement_text=request.replacement_text,
            reason=request.reason,
            operator_confirmation=request.operator_confirmation,
            tier_session_id=request.tier_session_id,
            required_subswitches=request.required_subswitches,
            dry_run=request.dry_run,
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
        "host_executor_v1_scoped_only": True,
    }


@router.post("/host-executor/patch/apply")
def scoped_patch_apply(request: ScopedPatchApiRequest) -> dict[str, Any]:
    result = SCOPED_PATCH_EXECUTOR.apply(
        ScopedPatchRequest(
            target_path=request.target_path,
            expected_old_text=request.expected_old_text,
            replacement_text=request.replacement_text,
            reason=request.reason,
            operator_confirmation=request.operator_confirmation,
            tier_session_id=request.tier_session_id,
            required_subswitches=request.required_subswitches,
            dry_run=False,
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
        "host_executor_v1_scoped_only": True,
    }


@router.post("/host-executor/patch/rollback")
def scoped_patch_rollback(request: ScopedPatchRollbackApiRequest) -> dict[str, Any]:
    result = SCOPED_PATCH_EXECUTOR.rollback(
        ScopedPatchRollbackRequest(
            target_path=request.target_path,
            backup_path=request.backup_path,
            operator_confirmation=request.operator_confirmation,
            tier_session_id=request.tier_session_id,
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
        "host_executor_v1_scoped_only": True,
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


@router.get("/splatra/imagination/status")
def splatra_imagination_status() -> dict[str, Any]:
    return {
        **SAFETY_FLAGS,
        **default_safety_flags(),
        "available": True,
        "proof_only": True,
        "label": "imagination",
        "source": "procedural",
        "is_verified_knowledge": False,
        "archetypes": list(ARCHETYPES),
        "product_budget": 1600,
        "lab_budget": 6500,
    }


@router.post("/splatra/imagination/generate")
def splatra_imagination_generate(request: SplatraImaginationGenerateApiRequest) -> dict[str, Any]:
    if request.archetype not in ARCHETYPES:
        emit_runtime_event(
            source="splatra_imagination",
            event_type="splatra_generation_failure",
            payload_summary=f"unsupported archetype={request.archetype}",
            intensity=0.8,
        )
        return {
            **SAFETY_FLAGS,
            **default_safety_flags(),
            "allowed": False,
            "reason": "unsupported archetype",
            "archetypes": list(ARCHETYPES),
        }
    seed = ImaginationSeed(
        seed_id=request.seed_id,
        archetype=request.archetype,  # type: ignore[arg-type]
        randomness=max(0.0, min(1.0, request.randomness)),
        valence=max(-1.0, min(1.0, request.valence)),
        arousal=max(0.0, min(1.0, request.arousal)),
        curiosity=max(0.0, min(1.0, request.curiosity)),
        speaking_energy=max(0.0, min(1.0, request.speaking_energy)),
        state=request.state if request.state in {"imagining", "resting", "speaking", "thinking", "previewing", "blocked"} else "imagining",  # type: ignore[arg-type]
        particle_budget=max(16, min(request.particle_budget, 100_000)),
        lod_target=max(0, request.lod_target),
        created_at="api_procedural_seed",
    )
    frame = ImaginationGenerator(max_particle_budget=100_000).generate_frame(seed)
    emit_runtime_event(
        source="splatra_imagination",
        event_type="splatra_generation_success",
        payload_summary=f"archetype={request.archetype}; particles={request.particle_budget}",
        intensity=0.45,
    )
    return {
        **SAFETY_FLAGS,
        **default_safety_flags(),
        "allowed": True,
        "frame": frame.to_dict(include_particles=request.include_particles),
    }


@router.post("/splatra/imagination/evaluate")
def splatra_imagination_evaluate(request: SplatraImaginationEvaluateApiRequest) -> dict[str, Any]:
    proof = run_imagination_proof(particle_budget=max(16, min(request.particle_budget, 10_000)))
    return {**SAFETY_FLAGS, **default_safety_flags(), **proof}


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
    emit_runtime_event(
        source="web_explorer",
        event_type="novelty_found" if result.get("candidate_drafts_count") or result.get("skill_drafts_count") else "conversation_success",
        payload_summary=f"run={result.get('run_id')}; pages={result.get('pages_read')}; drafts={result.get('candidate_drafts_count')}",
        intensity=0.8,
    )
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
    emit_runtime_event(
        source="web_explorer",
        event_type="novelty_found" if result.get("candidate_drafts_count") or result.get("skill_drafts_count") else "conversation_success",
        payload_summary=f"open_run={result.get('run_id')}; pages={result.get('pages_read')}; drafts={result.get('candidate_drafts_count')}",
        intensity=0.8,
    )
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
    decision_value = str(request.decision)
    event_type = "review_item_approved" if decision_value == "approved" else "review_item_rejected" if decision_value == "rejected" else "review_queue_pressure"
    emit_runtime_event(
        source="review_queue",
        event_type=event_type,
        payload_summary=f"decision={decision_value}; item={request.item_id}",
        intensity=0.65,
    )
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
    status_payload = REVIEW_QUEUE.status()
    if int(status_payload.get("pending", 0) or 0) > 8 or int(status_payload.get("high_risk", 0) or 0) > 0:
        emit_runtime_event(
            source="review_queue",
            event_type="review_queue_pressure",
            payload_summary=f"pending={status_payload.get('pending')}; high_risk={status_payload.get('high_risk')}",
            intensity=0.75,
        )
    return {
        **SAFETY_FLAGS,
        **status_payload,
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
