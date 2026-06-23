from __future__ import annotations

from datetime import datetime, timedelta, timezone

from packages.agentic_micro_os.host_authority import HostAuthority
from packages.agentic_micro_os.operator_confirm import FULL_HOST_CONFIRMATION_PHRASE
from packages.agentic_micro_os.permission_gate import (
    AutonomySubSwitches,
    AutonomyTier,
    PermissionScope,
    gate_for_test,
)


def test_default_tier_is_draft_proposal_or_safer(tmp_path) -> None:
    gate = gate_for_test(tmp_path)

    assert gate.status()["tier"] == AutonomyTier.DRAFT_PROPOSAL.value
    assert gate.verify_action(PermissionScope.REVIEW_DRAFT_WRITE)["allowed"] is True
    assert gate.verify_action(PermissionScope.SHELL)["allowed"] is False


def test_tier4_cannot_enable_without_typed_phrase(tmp_path) -> None:
    gate = gate_for_test(tmp_path)

    result = gate.enable_full_host(enabled_by="owner", typed_phrase="yes", duration_sec=600)

    assert result["allowed"] is False
    assert "phrase" in result["reason"]
    assert gate.status()["tier4_active"] is False


def test_tier4_cannot_enable_without_duration(tmp_path) -> None:
    gate = gate_for_test(tmp_path)

    result = gate.enable_full_host(
        enabled_by="owner",
        typed_phrase=FULL_HOST_CONFIRMATION_PHRASE,
        duration_sec=0,
    )

    assert result["allowed"] is False
    assert "duration" in result["reason"]


def test_expired_session_blocks_actions(tmp_path) -> None:
    gate = gate_for_test(tmp_path)
    gate.enable_full_host(
        enabled_by="owner",
        typed_phrase=FULL_HOST_CONFIRMATION_PHRASE,
        duration_sec=600,
        sub_switches=AutonomySubSwitches(shell=True),
    )
    assert gate.session is not None
    gate.session.expires_at = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()

    result = gate.verify_action(PermissionScope.SHELL, action="echo")

    assert result["allowed"] is False
    assert "expired" in result["reason"]


def test_emergency_stop_blocks_actions(tmp_path) -> None:
    gate = gate_for_test(tmp_path)
    gate.enable_full_host(
        enabled_by="owner",
        typed_phrase=FULL_HOST_CONFIRMATION_PHRASE,
        duration_sec=600,
        sub_switches=AutonomySubSwitches(shell=True),
    )

    gate.emergency_stop.trigger("stop")
    result = gate.verify_action(PermissionScope.SHELL, action="echo")

    assert result["allowed"] is False
    assert "emergency stop" in result["reason"]


def test_tier1_blocks_writes_and_shell(tmp_path) -> None:
    gate = gate_for_test(tmp_path)
    gate.set_tier(AutonomyTier.OBSERVE_ONLY)

    assert gate.verify_action(PermissionScope.READ_SUMMARY)["allowed"] is True
    assert gate.verify_action(PermissionScope.FILE_WRITE)["allowed"] is False
    assert gate.verify_action(PermissionScope.SHELL)["allowed"] is False


def test_tier2_allows_review_draft_only(tmp_path) -> None:
    gate = gate_for_test(tmp_path)

    assert gate.verify_action(PermissionScope.REVIEW_DRAFT_WRITE)["allowed"] is True
    assert gate.verify_action(PermissionScope.PATCH_PROPOSAL)["allowed"] is True
    assert gate.verify_action(PermissionScope.CLOUD_PRODUCTION_WRITE)["allowed"] is False


def test_tier3_requires_signed_scoped_token(tmp_path) -> None:
    gate = gate_for_test(tmp_path)
    gate.set_tier(AutonomyTier.SIGNED_DELEGATION)
    issued = gate.issue_signed_delegation([PermissionScope.BROWSER_CONTROL], max_runtime_sec=60)

    assert gate.verify_action(PermissionScope.BROWSER_CONTROL, signed_token=issued["token_id"])["allowed"] is True
    assert gate.verify_action(PermissionScope.MCP_TOOLS, signed_token=issued["token_id"])["allowed"] is False
    assert gate.verify_action(PermissionScope.BROWSER_CONTROL)["allowed"] is False


def test_tier4_sub_switches_control_shell_file_write_and_git(tmp_path) -> None:
    gate = gate_for_test(tmp_path)
    gate.enable_full_host(
        enabled_by="owner",
        typed_phrase=FULL_HOST_CONFIRMATION_PHRASE,
        duration_sec=600,
        sub_switches=AutonomySubSwitches(shell=True, full_file_write=True, git_push=False),
    )

    assert gate.verify_action(PermissionScope.SHELL, action="echo")["allowed"] is True
    assert gate.verify_action(PermissionScope.FILE_WRITE, action="write temp")["allowed"] is True
    assert gate.verify_action(PermissionScope.GIT_PUSH, action="git push")["allowed"] is False


def test_local_brain_and_cloud_writes_require_explicit_sub_switches(tmp_path) -> None:
    gate = gate_for_test(tmp_path)
    gate.enable_full_host(
        enabled_by="owner",
        typed_phrase=FULL_HOST_CONFIRMATION_PHRASE,
        duration_sec=600,
        sub_switches=AutonomySubSwitches(local_brain_write=True, cloud_production_write=False),
    )

    assert gate.verify_action(PermissionScope.LOCAL_BRAIN_WRITE)["allowed"] is True
    assert gate.verify_action(PermissionScope.CLOUD_PRODUCTION_WRITE)["allowed"] is False


def test_audit_log_written_for_allowed_and_denied_actions(tmp_path) -> None:
    gate = gate_for_test(tmp_path)

    gate.verify_action(PermissionScope.READ_SUMMARY, action="read")
    gate.verify_action(PermissionScope.SHELL, action="echo")

    log_lines = (tmp_path / "host_audit.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(log_lines) == 2
    assert "permission_allowed" in log_lines[0]
    assert "permission_denied" in log_lines[1]


def test_host_authority_only_runs_harmless_test_commands_and_temp_write(tmp_path) -> None:
    gate = gate_for_test(tmp_path)
    authority = HostAuthority(gate)

    assert authority.run_harmless_test_command("rm -rf /")["executed"] is False

    gate.enable_full_host(
        enabled_by="owner",
        typed_phrase=FULL_HOST_CONFIRMATION_PHRASE,
        duration_sec=600,
        sub_switches=AutonomySubSwitches(shell=True, full_file_write=True),
    )

    assert authority.run_harmless_test_command("echo")["executed"] is True
    write_result = authority.write_temp_file(tmp_path / "runtime-test" / "note.txt", "ok")
    assert write_result["written"] is True
    assert (tmp_path / "runtime-test" / "note.txt").read_text(encoding="utf-8") == "ok"
