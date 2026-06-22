from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


AutonomyLevelName = Literal[
    "LEVEL_0_OFF",
    "LEVEL_1_OBSERVE",
    "LEVEL_2_PROACTIVE_BRIEF",
    "LEVEL_3_SANDBOX_PLANNER",
    "LEVEL_4_GATED_OPERATOR",
]
TickType = Literal[
    "startup",
    "periodic_tick",
    "morning",
    "afternoon",
    "evening",
    "idle_timeout",
    "user_returned",
    "pre_sleep",
    "post_sleep",
    "manual_ping",
]
Severity = Literal["info", "notice", "warning", "blocked"]
NeedType = Literal[
    "memory_review_needed",
    "promotion_review_needed",
    "repo_hygiene_needed",
    "morning_brief_needed",
    "quality_audit_needed",
    "voice_setup_needed",
    "p2p_blocked_by_gate",
    "local_brain_write_blocked",
    "operator_confirmation_needed",
    "user_attention_needed",
    "do_nothing",
]
ActionType = Literal[
    "observe_status",
    "prepare_morning_brief",
    "prepare_evening_brief",
    "run_mirofish_deliberation",
    "prepare_memory_review",
    "prepare_promotion_review",
    "prepare_operator_confirmation_request",
    "recommend_repo_hygiene",
    "ask_user_attention",
    "do_nothing",
]
ActionStatus = Literal["proposed", "waiting_user", "approved_for_future_gate", "rejected", "deferred", "blocked"]


def _require_text(name: str, value: str) -> None:
    if not value:
        raise ValueError(f"{name} is required")


def default_safety() -> dict[str, Any]:
    return {
        "real_local_brain_write": False,
        "real_local_brain_mutated": False,
        "production_store_mutated": False,
        "candidate_store_mutated": False,
        "candidate_promotion": False,
        "actual_promotion_performed": False,
        "external_llm_used": False,
        "real_p2p_used": False,
        "real_cloud_upload": False,
        "generated_code_executed": False,
        "real_hot_swap_performed": False,
        "always_listening_enabled": False,
        "raw_voice_saved": False,
        "memory_apply_enabled": False,
        "requires_user_approval": True,
        "text_input_supported": True,
        "voice_optional": True,
    }


def assert_safe(safety: dict[str, Any]) -> None:
    unsafe_true = [
        "real_local_brain_write",
        "real_local_brain_mutated",
        "production_store_mutated",
        "candidate_store_mutated",
        "candidate_promotion",
        "actual_promotion_performed",
        "external_llm_used",
        "real_p2p_used",
        "real_cloud_upload",
        "generated_code_executed",
        "real_hot_swap_performed",
        "always_listening_enabled",
        "raw_voice_saved",
        "memory_apply_enabled",
    ]
    bad = {key: safety.get(key) for key in unsafe_true if bool(safety.get(key))}
    if bad:
        raise ValueError(f"Live Selfhood Cycle cannot mutate or use unsafe capabilities: {bad}")
    if safety.get("requires_user_approval") is not True:
        raise ValueError("requires_user_approval must remain true")
    if safety.get("text_input_supported") is not True:
        raise ValueError("text_input_supported must remain true")
    if safety.get("voice_optional") is not True:
        raise ValueError("voice_optional must remain true")


@dataclass(frozen=True)
class LifeCycleConfig:
    autonomy_level: AutonomyLevelName = "LEVEL_3_SANDBOX_PLANNER"
    max_actions_per_tick: int = 3
    voice_optional: bool = True
    text_input_supported: bool = True

    def __post_init__(self) -> None:
        if self.max_actions_per_tick < 0:
            raise ValueError("max_actions_per_tick must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LifeCycleTick:
    tick_id: str
    timestamp: str
    tick_type: TickType
    reason: str
    autonomy_level: AutonomyLevelName

    def __post_init__(self) -> None:
        _require_text("tick_id", self.tick_id)
        _require_text("timestamp", self.timestamp)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Observation:
    observation_id: str
    sensor: str
    status: str
    summary: str
    severity: Severity = "info"
    payload: dict[str, Any] = field(default_factory=dict)
    source_refs: list[str] = field(default_factory=list)
    read_only: bool = True

    def __post_init__(self) -> None:
        _require_text("observation_id", self.observation_id)
        _require_text("sensor", self.sensor)
        if self.read_only is not True:
            raise ValueError("observations must remain read_only")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Need:
    need_id: str
    need_type: NeedType
    summary: str
    severity: Severity = "info"
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Impulse:
    impulse_id: str
    need_type: NeedType
    urgency: float
    importance: float
    reversibility: float
    user_value: float
    cost: float
    safety: float
    reason: str
    proposed_next_step: str

    @property
    def score(self) -> float:
        return round(self.urgency + self.importance + self.reversibility + self.user_value + self.safety - self.cost, 6)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["score"] = self.score
        return payload


@dataclass(frozen=True)
class ScheduledAction:
    action_id: str
    action_type: ActionType
    title: str
    summary: str
    requires_user_approval: bool = True
    irreversible: bool = False
    can_apply_now: bool = False
    safety_flags: dict[str, Any] = field(default_factory=default_safety)

    def __post_init__(self) -> None:
        _require_text("action_id", self.action_id)
        if self.can_apply_now:
            raise ValueError("scheduled actions cannot apply in proof-only lifecycle")
        assert_safe(self.safety_flags)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ActionQueueItem:
    action_id: str
    action_type: ActionType
    title: str
    summary: str
    status: ActionStatus = "proposed"
    requires_user_approval: bool = True
    irreversible: bool = False
    can_apply_now: bool = False
    safety_flags: dict[str, Any] = field(default_factory=default_safety)
    created_at: str = ""

    def __post_init__(self) -> None:
        if self.can_apply_now:
            raise ValueError("action queue items cannot apply now")
        assert_safe(self.safety_flags)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DeliberationSummary:
    action_id: str
    summary: str
    objections: list[str]
    safety_notes: list[str]
    recommendation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Brief:
    brief_id: str
    brief_type: Literal["morning", "evening", "status"]
    title: str
    sections: dict[str, str]
    language: Literal["ko", "en"] = "ko"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LifeEvent:
    event_id: str
    event_type: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LifeCycleResult:
    tick: LifeCycleTick
    observations: list[Observation]
    needs: list[Need]
    impulses: list[Impulse]
    scheduled_actions: list[ScheduledAction]
    queued_actions: list[ActionQueueItem]
    deliberations: list[DeliberationSummary]
    brief: Brief | None
    events: list[LifeEvent]
    safety: dict[str, Any]
    actual_mutations: dict[str, Any]

    def __post_init__(self) -> None:
        assert_safe(self.safety)
        assert_safe({**default_safety(), **self.actual_mutations})

    def to_dict(self) -> dict[str, Any]:
        return {
            "tick": self.tick.to_dict(),
            "observations": [item.to_dict() for item in self.observations],
            "needs": [item.to_dict() for item in self.needs],
            "impulses": [item.to_dict() for item in self.impulses],
            "scheduled_actions": [item.to_dict() for item in self.scheduled_actions],
            "queued_actions": [item.to_dict() for item in self.queued_actions],
            "deliberations": [item.to_dict() for item in self.deliberations],
            "brief": self.brief.to_dict() if self.brief else None,
            "events": [item.to_dict() for item in self.events],
            "safety": dict(self.safety),
            "actual_mutations": dict(self.actual_mutations),
        }
