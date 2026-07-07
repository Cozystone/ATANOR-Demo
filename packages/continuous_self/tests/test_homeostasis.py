# -*- coding: utf-8 -*-
"""Homeostasis + digital hormones — event-raised, clock-decayed, bounded."""

from __future__ import annotations

from packages.continuous_self.homeostasis import (
    apply_homeostasis, public_report, update_hormones)
from packages.continuous_self.self_state import Observation, SelfState, evolve


def test_cortisol_rises_on_pressure_and_decays_when_calm():
    s = SelfState()
    stressed = Observation(resource_pressure=0.9)
    update_hormones(s, stressed)
    high = s.hormones["cortisol"]
    assert high > 0.3

    calm = Observation()
    for _ in range(10):
        update_hormones(s, calm)
    assert s.hormones["cortisol"] < high * 0.5  # decayed, not sticky


def test_dopamine_pulses_on_real_growth_only():
    s = SelfState()
    update_hormones(s, Observation())
    assert s.hormones["dopamine"] == 0.0  # no event, no reward
    update_hormones(s, Observation(concepts_delta=4, relations_delta=2))
    assert s.hormones["dopamine"] > 0.3


def test_noradrenaline_fires_on_arrival_transition_not_presence():
    s = SelfState()
    update_hormones(s, Observation(user_present=True))
    first = s.hormones["noradrenaline"]
    assert first > 0.3
    update_hormones(s, Observation(user_present=True))  # still present: no new pulse
    assert s.hormones["noradrenaline"] < first


def test_sustained_stress_forces_repair_floor():
    s = SelfState()
    stressed = Observation(resource_pressure=0.95, uncertainty_signal=0.9)
    targets = {"energy": 0.9, "valence": 0.6, "curiosity": 0.5, "attention": 0.5}
    for _ in range(6):
        out = apply_homeostasis(s, stressed, dict(targets))
    assert s.hormones["repair"] == 1.0
    assert out["energy"] <= 0.36  # forced-rest floor, not the 0.9 the obs wanted

    # recovery is gradual: repair holds while cortisol is still high, then lifts
    # step by step once the stress hormone has actually cleared (a hard day
    # leaves a trace instead of vanishing on the next tick)
    calm = Observation()
    for _ in range(5):  # cortisol decays 0.9/tick; drops under threshold at ~4
        apply_homeostasis(s, calm, dict(targets))
    assert 0 < s.hormones["repair"] < 1.0


def test_targets_stay_bounded_and_report_is_public():
    s = SelfState()
    out = apply_homeostasis(
        s, Observation(resource_pressure=1.0, uncertainty_signal=1.0),
        {"energy": 0.0, "valence": 0.0, "curiosity": 1.0, "attention": 1.0})
    assert all(0.0 <= v <= 1.0 for v in out.values())
    rep = public_report(s)
    assert set(rep["hormones"]) == {"cortisol", "dopamine", "noradrenaline"}
    assert "setpoint_deviation" in rep


def test_evolve_integrates_homeostasis_and_snapshot_exposes_it():
    s = SelfState()
    evolve(s, Observation(concepts_delta=3))
    snap = s.to_public()
    assert "homeostasis" in snap
    assert snap["homeostasis"]["hormones"]["dopamine"] > 0
