from __future__ import annotations

from packages.surface_brain.monitor import monitor_answer, repair_answer


def test_monitor_catches_repetition_and_internal_trace_leakage() -> None:
    draft = "Local Brain → Cloud Brain → Contributor Node path. answer answer repeats repeats."
    monitor = monitor_answer(draft, language="en")

    assert "internal_trace_leakage" in monitor["issues"]
    repaired = repair_answer(draft, monitor, language="en")
    repaired_monitor = monitor_answer(repaired, language="en")

    assert repaired_monitor["needs_repair"] is False
    assert "Local Brain" not in repaired
    assert "Cloud Brain" not in repaired

