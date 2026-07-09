# -*- coding: utf-8 -*-
"""The System 1 intuition spark: perturbation surfaces cross-domain collisions
as QUESTIONS (never facts), and a calm space (no energy) produces no false leaps.
"""
import numpy as np


class _StubStore:
    """Records any attempt to touch it. The spark must NEVER write facts."""
    def __init__(self):
        self.writes = 0
    def facts_about(self, term, limit=40):
        return []                       # no existing edges -> nothing filtered out
    def add(self, *a, **k):
        self.writes += 1                # if the spark ever writes, this trips


def _inject_space(monkeypatch, n=50, seed=1):
    from packages.graph_scale import phase_space
    rng = np.random.default_rng(seed)
    terms = [f"개념{i:02d}자" for i in range(n)]     # legible Korean, 2-8 chars
    phases = rng.uniform(0, 2 * np.pi, size=(n, 8)).astype(np.float32)
    phase_space._SPACE["phases"] = phases
    phase_space._SPACE["terms"] = terms
    phase_space._SPACE["idx"] = {t: i for i, t in enumerate(terms)}
    monkeypatch.setattr(phase_space, "_load", lambda: True)


def test_energy_zero_is_calm_no_false_leaps(tmp_path, monkeypatch):
    """With no storm the geometry is unperturbed, so a FAR pair stays far and
    nothing can satisfy (clean<0.15 AND sparked>0.55). Zero sparks — the machine
    is not manufacturing analogies out of nothing."""
    from packages.graph_scale import intuition_spark as isp
    _inject_space(monkeypatch)
    monkeypatch.setattr(isp, "LEDGER", tmp_path / "sparks.jsonl")
    out = isp.spark(store=_StubStore(), energy=0.0, seed=3)
    assert out == []


def test_perturbation_sparks_are_questions_and_immune(tmp_path, monkeypatch):
    """Loosen the thresholds so a collision is guaranteed, then assert every
    spark (a) satisfies the far-then-collided invariant, (b) is a QUESTION with
    both concepts, (c) is unverified, and (d) the store received ZERO writes —
    model-collapse immunity is structural."""
    from packages.graph_scale import intuition_spark as isp
    _inject_space(monkeypatch)
    monkeypatch.setattr(isp, "LEDGER", tmp_path / "sparks.jsonl")
    monkeypatch.setattr(isp, "_CLEAN_MAX", 0.9)      # accept almost any clean res
    monkeypatch.setattr(isp, "_LAND_MIN", -1.0)      # ...and any landing res
    store = _StubStore()
    out = isp.spark(store=store, energy=1.0, seed=7, k_terms=40)
    assert out, "loosened thresholds must yield sparks"
    for row in out:
        assert row["clean_resonance"] < isp._CLEAN_MAX
        assert row["sparked_resonance"] > isp._LAND_MIN
        assert row["status"] == "unverified" and row["kind"] == "intuition_spark"
        assert row["a"] in row["question"] and row["b"] in row["question"]
        assert row["a"] != row["b"]
    assert store.writes == 0                          # never wrote a fact
    # ledgered as questions, and re-running does not duplicate a known pair
    again = isp.spark(store=store, energy=1.0, seed=7, k_terms=40)
    seen = {(r["a"], r["b"]) for r in out}
    assert all((r["a"], r["b"]) not in seen for r in again)
