# -*- coding: utf-8 -*-
"""Abstain -> ingest closed loop: the queue records, the drain processes.

The answer path already calls record_abstain when it abstains; P2 wired
abstain_feeder.drain() into the autonomous daemon so the queue is actually
drained (fetch attributed evidence + ingest), closing the loop. These tests
cover the loop's contract hermetically (no network: dry_run)."""

from __future__ import annotations

from packages.graph_scale import abstain_feeder, abstain_queue


def test_drain_returns_bounded_counters_without_raising():
    res = abstain_feeder.drain(limit=1, dry_run=True, log=lambda *a, **k: None)
    # the drain always returns a full counter dict and never raises
    assert set(res) >= {"terms", "ingested", "quarantined", "no_definition", "failed", "evidence"}
    assert all(isinstance(v, int) for v in res.values())
    assert res["terms"] <= 1  # respects the limit


def test_empty_queue_drain_is_a_noop():
    # pending() may hold real backlog; a limit-0 drain must still be safe + bounded
    res = abstain_feeder.drain(limit=0, dry_run=True, log=lambda *a, **k: None)
    assert res["terms"] == 0 and res["ingested"] == 0


def test_queue_pending_is_bounded_and_typed():
    pend = abstain_queue.pending(limit=10)
    assert isinstance(pend, list) and len(pend) <= 10
    assert all(isinstance(t, str) for t in pend)
