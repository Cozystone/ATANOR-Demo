from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .autonomy_level import can_apply_irreversible_action
from .clock import make_tick
from .lifecycle import run_life_cycle_tick
from .models import LifeCycleConfig, ScheduledAction, default_safety


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "audits" / "live_selfhood_cycle"


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _run(tick_type: str, context: dict[str, Any] | None = None, level: str = "LEVEL_3_SANDBOX_PLANNER") -> dict[str, Any]:
    tick = make_tick(tick_type=tick_type, reason=f"proof {tick_type}", autonomy_level=level)  # type: ignore[arg-type]
    result = run_life_cycle_tick(LifeCycleConfig(autonomy_level=level), tick, context or {})  # type: ignore[arg-type]
    return result.to_dict()


def run_proof(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    startup = _run("startup", {})
    morning = _run("morning", {"git_dirty": True, "dirty_files": 19})
    candidate = _run("manual_ping", {"candidate_backlog": 4})
    memory = _run("manual_ping", {"memory_review_backlog": 3})
    dirty = _run("manual_ping", {"git_dirty": True, "dirty_files": 12})
    operator = _run("manual_ping", {"approved_write_plan_waiting": True}, "LEVEL_4_GATED_OPERATOR")
    voice = _run("manual_ping", {"voice_available": True})
    level0 = _run("manual_ping", {"candidate_backlog": 4}, "LEVEL_0_OFF")
    level3 = _run("manual_ping", {"memory_review_backlog": 2}, "LEVEL_3_SANDBOX_PLANNER")
    level4 = _run("manual_ping", {"approved_write_plan_waiting": True}, "LEVEL_4_GATED_OPERATOR")
    unsafe_blocked = False
    try:
        ScheduledAction(
            action_id="unsafe-direct-local-write",
            action_type="prepare_memory_review",
            title="Unsafe direct write",
            summary="Attempt direct Local Brain write.",
            can_apply_now=True,
            safety_flags={**default_safety(), "real_local_brain_write": True},
        )
    except ValueError:
        unsafe_blocked = True

    scenarios = {
        "startup": len(startup["observations"]) > 0 and _no_mutation(startup),
        "morning": morning["brief"] is not None and "What I propose" in morning["brief"]["sections"] and _no_mutation(morning),
        "candidate_backlog": _has_need(candidate, "promotion_review_needed") and _has_action(candidate, "prepare_promotion_review"),
        "memory_backlog": _has_need(memory, "memory_review_needed") and _has_action(memory, "prepare_memory_review") and _no_mutation(memory),
        "dirty_worktree": _has_need(dirty, "repo_hygiene_needed") and _has_action(dirty, "recommend_repo_hygiene"),
        "operator_confirmation": _has_need(operator, "operator_confirmation_needed")
        and _has_action(operator, "prepare_operator_confirmation_request")
        and _no_mutation(operator),
        "voice_readiness": _has_need(voice, "voice_setup_needed")
        and voice["safety"]["text_input_supported"] is True
        and voice["safety"]["always_listening_enabled"] is False,
        "autonomy_levels": len(level0["scheduled_actions"]) == 0
        and _has_action(level3, "prepare_memory_review")
        and _has_action(level4, "prepare_operator_confirmation_request")
        and can_apply_irreversible_action("LEVEL_4_GATED_OPERATOR") is False,
        "unsafe_action_blocked": unsafe_blocked,
    }
    invariants = default_safety()
    payload = {
        "verdict": "PASS" if all(scenarios.values()) and _invariants_safe(invariants) else "FAIL",
        "scenarios": scenarios,
        "invariants": invariants,
        "samples": {
            "startup": startup,
            "morning": morning,
            "operator": operator,
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = _timestamp()
    json_path = output_dir / f"live_selfhood_cycle_proof_{ts}.json"
    md_path = output_dir / f"live_selfhood_cycle_proof_{ts}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    payload["outputs"] = {"json": str(json_path), "md": str(md_path)}
    return payload


def _has_need(payload: dict[str, Any], need_type: str) -> bool:
    return any(item["need_type"] == need_type for item in payload["needs"])


def _has_action(payload: dict[str, Any], action_type: str) -> bool:
    return any(item["action_type"] == action_type for item in payload["scheduled_actions"])


def _no_mutation(payload: dict[str, Any]) -> bool:
    return all(value is False for value in payload["actual_mutations"].values())


def _invariants_safe(invariants: dict[str, Any]) -> bool:
    return all(value is False or value is True for value in invariants.values()) and not any(
        invariants[key]
        for key in [
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
    )


def _markdown(payload: dict[str, Any]) -> str:
    lines = ["# Live Selfhood Life Cycle v0 Proof", "", f"- verdict: `{payload['verdict']}`", ""]
    for key, value in payload["scenarios"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "This proof-only lifecycle self-initiates observations, proposals, deliberation summaries, and briefs. It does not write Local Brain, mutate production, promote candidates, use real P2P, execute generated code, or enable always-on microphone capture.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    result = run_proof()
    print(json.dumps({"verdict": result["verdict"], "scenarios": result["scenarios"], "outputs": result["outputs"]}, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
