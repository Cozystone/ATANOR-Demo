from __future__ import annotations

import sqlite3
from pathlib import Path

from knowledge_bakery import daemon_checkpoint, daemon_status, run_synaptic_decay, stop_daemon, tick_daemon


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


def test_daemon_ingests_raw_files_and_potentiates_synapses(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True)
    (raw / "first.md").write_text(
        "# GraphRAG\nGraphRAG uses KnowledgeGraph. GraphRAG uses KnowledgeGraph.",
        encoding="utf-8",
    )

    status = tick_daemon("data/memory", force=True, run_decay=False)

    assert status["last_round_action"] == "raw_ingested_and_memory_rebuilt"
    assert status["ingested_file_count"] == 1
    assert status["synaptic_edge_count"] > 0
    assert not list(raw.glob("*.md"))
    assert list((tmp_path / "data" / "cleaned").glob("*.md"))

    db_path = tmp_path / "data" / "memory" / "homage.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    first = conn.execute(
        """
        SELECT source, target, weight, count
        FROM synaptic_edges
        WHERE relation = 'uses'
        ORDER BY weight DESC
        LIMIT 1
        """
    ).fetchone()
    conn.close()

    assert first is not None
    first_weight = float(first["weight"])

    (raw / "second.md").write_text("GraphRAG uses KnowledgeGraph.", encoding="utf-8")
    status = tick_daemon("data/memory", force=True, run_decay=False)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    second = conn.execute(
        """
        SELECT weight, count
        FROM synaptic_edges
        WHERE source = ? AND relation = 'uses' AND target = ?
        """,
        (first["source"], first["target"]),
    ).fetchone()
    conn.close()

    assert status["ingested_file_count"] == 2
    assert second is not None
    assert float(second["weight"]) >= first_weight + 0.09
    assert int(second["count"]) >= 2


def test_synaptic_decay_prunes_weak_edges(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True)
    (raw / "first.md").write_text("GraphRAG uses KnowledgeGraph.", encoding="utf-8")
    tick_daemon("data/memory", force=True, run_decay=False)

    result = run_synaptic_decay("data/memory", factor=0.01, threshold=0.05)

    assert result["state"] == "completed"
    assert result["before_edges"] > 0
    assert result["pruned_edges"] > 0
    assert result["after_edges"] < result["before_edges"]
