from __future__ import annotations

from typing import Any

from .action_queue import enqueue_actions
from .brief import generate_brief
from .deliberation import deliberate_actions
from .event_stream import build_events
from .impulse import rank_impulses
from .models import LifeCycleConfig, LifeCycleResult, LifeCycleTick, default_safety
from .needs import append_operator_confirmation_need, needs_from_observations
from .scheduler import LifeCycleScheduler
from .sensors import observe_all


def run_life_cycle_tick(
    config: LifeCycleConfig,
    tick: LifeCycleTick,
    context: dict[str, Any] | None = None,
) -> LifeCycleResult:
    """Run one proof-only lifecycle tick."""

    ctx = dict(context or {})
    observations = observe_all(ctx)
    needs = needs_from_observations(observations, tick)
    needs = append_operator_confirmation_need(needs, bool(ctx.get("approved_write_plan_waiting", False)))
    impulses = rank_impulses(needs)
    scheduler = LifeCycleScheduler()
    scheduled = scheduler.schedule(tick, config, impulses, list(ctx.get("recent_events", [])))
    queued = enqueue_actions(scheduled)
    deliberations = deliberate_actions(impulses, observations, scheduled)
    brief = generate_brief(tick, observations, needs, impulses, scheduled, queued)
    payload = {
        "tick": tick.to_dict(),
        "observations": [item.to_dict() for item in observations],
        "needs": [item.to_dict() for item in needs],
        "impulses": [item.to_dict() for item in impulses],
        "scheduled_actions": [item.to_dict() for item in scheduled],
        "queued_actions": [item.to_dict() for item in queued],
        "deliberations": [item.to_dict() for item in deliberations],
        "brief": brief.to_dict() if brief else None,
    }
    events = build_events(payload)
    actual_mutations = {
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
    }
    return LifeCycleResult(
        tick=tick,
        observations=observations,
        needs=needs,
        impulses=impulses,
        scheduled_actions=scheduled,
        queued_actions=queued,
        deliberations=deliberations,
        brief=brief,
        events=events,
        safety=default_safety(),
        actual_mutations=actual_mutations,
    )
