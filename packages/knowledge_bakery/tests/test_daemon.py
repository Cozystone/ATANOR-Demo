from __future__ import annotations

from pathlib import Path

from knowledge_bakery import daemon_checkpoint, daemon_status, stop_daemon, tick_daemon


def test_daemon_tick_persists_state_and_memory_counts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    cleaned = tmp_path / "data" / "cleaned"
    ontology = tmp_path / "data" / "ontology"
    cleaned.mkdir(parents=True)
    ontology.mkdir(parents=True)
    (cleaned / "sample.txt").write_text(
        "Graph memory learns token transitions. Local daemon keeps checkpoints after reboot.",
        encoding="utf-8",
    )
    (ontology / "nodes.json").write_text("[]", encoding="utf-8")
    (ontology / "edges.json").write_text("[]", encoding="utf-8")

    status = tick_daemon("data/memory", force=True)

    assert status["state"] == "idle"
    assert status["total_rounds"] == 1
    assert status["learned_rounds"] == 1
    assert status["latest_node_count"] > 0
    assert (tmp_path / "data" / "memory" / "daemon_state.json").exists()

    checkpoint = daemon_checkpoint("data/memory", "test")
    assert checkpoint["checkpoint_count"] == 1

    stopped = stop_daemon("data/memory", "test")
    assert stopped["state"] == "stopped"


def test_status_marks_resume_needed_when_desired_worker_is_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    memory_dir = tmp_path / "data" / "memory"
    memory_dir.mkdir(parents=True)
    (memory_dir / "daemon_state.json").write_text(
        '{"state":"running","desired_running":true,"started_at":"2026-01-01T00:00:00Z"}',
        encoding="utf-8",
    )

    status = daemon_status("data/memory")

    assert status["state"] == "resume_needed"
    assert status["resume_needed"] is True
