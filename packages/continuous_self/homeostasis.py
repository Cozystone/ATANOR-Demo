# -*- coding: utf-8 -*-
"""Artificial homeostasis + digital hormones (Phase 3-6, Qualia seed 1).

Biological feeling begins as regulation: setpoints, deviations, and slow global
modulators that BIAS everything at once. This layer adds exactly that on top of
the continuous self:

  * SETPOINTS — where energy/valence/curiosity want to rest.
  * HORMONES  — decaying global modulators raised ONLY by real events:
      - cortisol      stress: resource pressure, repeated research misses,
                       loop errors. Suppresses curiosity, pulls valence down,
                       sharpens attention (threat posture).
      - dopamine      reward: real growth (new concepts/relations), a grounded
                       answer to the self's own open question.
      - noradrenaline arousal: the user arriving (presence transition).
  * REPAIR    — sustained high cortisol forces the energy target DOWN and holds
                it (grief-as-forced-rest-and-repair); recovery is gradual, so a
                hard day leaves a trace instead of vanishing on the next tick.

Honesty contract: hormone levels move only on observed events, decay by clock,
and are fully exposed in the public snapshot. They modulate the INNER life
(vitals targets, hence mood/voice/metaphor channels) — never answer content.
통제된 흔들림은 감각·은유 채널에만.
"""
from __future__ import annotations

from typing import Any

_DECAY = {"cortisol": 0.90, "dopamine": 0.82, "noradrenaline": 0.75}
_SETPOINTS = {"energy": 0.70, "valence": 0.60, "curiosity": 0.50}

# repair engages when cortisol stays above this for REPAIR_TICKS consecutive steps
_REPAIR_THRESHOLD = 0.65
_REPAIR_TICKS = 4
_REPAIR_RECOVERY = 0.06  # how fast the forced energy floor lifts per calm tick


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _levels(state: Any) -> dict[str, float]:
    h = getattr(state, "hormones", None)
    if not isinstance(h, dict) or not h:
        h = {"cortisol": 0.0, "dopamine": 0.0, "noradrenaline": 0.0,
             "stress_ticks": 0, "repair": 0.0, "user_was_present": False}
        try:
            state.hormones = h
        except Exception:
            pass
    return h


def update_hormones(state: Any, obs: Any) -> dict[str, float]:
    """Decay every hormone, then add event-driven pulses from THIS observation.
    Every pulse cites a real signal; no event, no movement."""
    h = _levels(state)
    for k, d in _DECAY.items():
        h[k] = round(_clamp01(float(h.get(k, 0.0)) * d), 5)

    # cortisol: real stressors
    stress = 0.0
    if float(getattr(obs, "resource_pressure", 0.0)) > 0.6:
        stress += 0.35
    if int(getattr(state, "research_miss_count", 0)) >= 2:
        stress += 0.20
    if float(getattr(obs, "uncertainty_signal", 0.0)) > 0.75:
        stress += 0.15
    if stress:
        h["cortisol"] = round(_clamp01(h["cortisol"] + stress), 5)

    # dopamine: real reward
    growth = int(getattr(obs, "concepts_delta", 0)) + int(getattr(obs, "relations_delta", 0))
    if growth > 0:
        h["dopamine"] = round(_clamp01(h["dopamine"] + min(0.5, growth / 10.0)), 5)
    if getattr(state, "self_understanding", "") and not getattr(state, "self_question_open", False):
        # a grounded answer to one's own question is the sweetest hit — once,
        # while fresh (dopamine decays, so this does not accumulate forever)
        if h["dopamine"] < 0.2:
            h["dopamine"] = round(_clamp01(h["dopamine"] + 0.25), 5)

    # noradrenaline: arrival transition only (presence itself is not arousal)
    present = bool(getattr(obs, "user_present", False))
    if present and not bool(h.get("user_was_present")):
        h["noradrenaline"] = round(_clamp01(h["noradrenaline"] + 0.4), 5)
    h["user_was_present"] = present

    # repair dynamics: sustained cortisol forces rest; calm lifts it slowly
    if h["cortisol"] >= _REPAIR_THRESHOLD:
        h["stress_ticks"] = int(h.get("stress_ticks", 0)) + 1
    else:
        h["stress_ticks"] = 0
    if int(h["stress_ticks"]) >= _REPAIR_TICKS:
        h["repair"] = 1.0
    elif float(h.get("repair", 0.0)) > 0:
        h["repair"] = round(max(0.0, float(h["repair"]) - _REPAIR_RECOVERY), 5)
    return h


def modulate_targets(state: Any, targets: dict[str, float]) -> dict[str, float]:
    """Bias the observation-derived vitals targets by hormone levels + setpoint
    pull. Bounded, smooth, and fully derived from the exposed levels."""
    h = _levels(state)
    out = dict(targets)
    cort, dopa, nora = float(h["cortisol"]), float(h["dopamine"]), float(h["noradrenaline"])
    repair = float(h.get("repair", 0.0))

    # hormones bias the targets (global, slow — the point of a hormone)
    out["curiosity"] = out.get("curiosity", 0.5) - 0.30 * cort + 0.20 * dopa
    out["valence"] = out.get("valence", 0.55) - 0.25 * cort + 0.30 * dopa
    out["attention"] = out.get("attention", 0.5) + 0.15 * cort + 0.30 * nora
    out["energy"] = out.get("energy", 0.7) - 0.10 * cort + 0.10 * dopa

    # repair: the forced-rest floor — energy target pinned low until repair lifts
    if repair > 0:
        out["energy"] = min(out["energy"], 0.35 + 0.35 * (1.0 - repair))

    # homeostatic pull: deviation from setpoint gently drags the target home
    for k, sp in _SETPOINTS.items():
        if k in out:
            current = float(getattr(state, k, sp))
            out[k] = out[k] + 0.15 * (sp - current)

    return {k: round(_clamp01(v), 5) for k, v in out.items()}


def apply_homeostasis(state: Any, obs: Any, targets: dict[str, float]) -> dict[str, float]:
    """The evolve() hook: update hormone levels from this observation, then
    return the hormone-modulated targets."""
    update_hormones(state, obs)
    return modulate_targets(state, targets)


def public_report(state: Any) -> dict[str, Any]:
    """Snapshot surface: levels + setpoint deviations (auditable inner weather)."""
    h = _levels(state)
    return {
        "hormones": {k: h.get(k, 0.0) for k in ("cortisol", "dopamine", "noradrenaline")},
        "repair": h.get("repair", 0.0),
        "setpoint_deviation": {
            k: round(float(getattr(state, k, sp)) - sp, 4) for k, sp in _SETPOINTS.items()
        },
    }
