"""The always-on driver for the continuously-alive self.

This is NOT a cron scheduler. It is a single long-lived loop (like the cloud-brain
learner) that eases the self-state forward every ~2s from real observations, so the
inner life flows without wake/sleep boundaries. It persists after every step, so a
process restart RESUMES the same self. A high resource-pressure observation slows the
cadence (a real low-activity rest), it never stops the life outright.

Observations are injected (an `obs_provider` callable) so this package stays pure and
the API wires the real signals (learning metrics, disk pressure, open deficits).
"""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable

from .self_state import Observation, SelfState, evolve, load_or_begin, save_state

ObsProvider = Callable[[], Observation]


class ContinuousSelf:
    def __init__(
        self,
        state_path: Path,
        obs_provider: ObsProvider,
        *,
        base_interval: float = 2.0,
        observe_fn=None,
        identity_fn=None,
        research_fn=None,
        initiative_every: int = 15,
        research_every: int = 30,
    ):
        self.state_path = Path(state_path)
        self.obs_provider = obs_provider
        self.base_interval = float(base_interval)
        # A read-only probe the mind may run ITSELF to serve its goals (action.py).
        # OBSERVE-tier only, by construction; higher tiers are never autonomous.
        self.observe_fn = observe_fn
        # Answers the self's OWN questions from the graph identity (grounded speech).
        self.identity_fn = identity_fn
        # READ-ONLY web research for the self's open questions (OBSERVE tier: it reads
        # public pages, writes nothing but its own state). This is the wonder→search→
        # grounded-answer→re-question chain the user asked for, autonomous by design.
        self.research_fn = research_fn
        # Mutable runtime params — the ONLY thing gated self-modification may change,
        # and only after explicit operator approval (self_modification.py).
        self.params: dict = {
            "initiative_every": max(1, int(initiative_every)),
            "research_every": max(5, int(research_every)),
        }
        self.selfmod_ledger: Path = self.state_path.parent / "self_modification_ledger.jsonl"
        self.state: SelfState = load_or_begin(self.state_path)
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._running = False

    @property
    def initiative_every(self) -> int:
        return int(self.params.get("initiative_every", 15))

    def snapshot(self) -> dict:
        with self._lock:
            return self.state.to_public()

    def step(self) -> SelfState:
        """One continuous micro-step from a fresh real observation."""
        try:
            obs = self.obs_provider()
        except Exception:  # a flaky sensor must never end the life
            obs = Observation()
        with self._lock:
            evolve(self.state, obs)
            # The inward turn — ENDOGENOUS: introspective pressure (built each evolve
            # step from real state, no schedule) fires a question composed from its own
            # cause. Identity-class questions are answered FROM THE GRAPH; thread/other
            # questions stay OPEN for the research step below. Drive from inside,
            # grounded speech outside — the merge.
            try:
                from .voice import due_for_self_inquiry, generate_self_inquiry, record_self_understanding

                if due_for_self_inquiry(self.state):
                    q, topic = generate_self_inquiry(self.state)
                    ans = None
                    # the graph identity concept truly answers WHO/WHAT-am-I and what-
                    # can-I-do questions. Continuity/epistemic questions and harvested
                    # thread terms ("의식", "그래프"…) need real research — answering
                    # them with the identity blurb would be a category mismatch.
                    if self.identity_fn is not None and topic in ("identity", "limits", "purpose"):
                        try:
                            ans = self.identity_fn(q, topic)
                        except Exception:
                            ans = None
                    record_self_understanding(self.state, q, ans, topic)
                    self.state._last_inquiry_topic = topic  # transient, for research
            except Exception:
                pass  # the inward turn must never break the life
            # The self RESEARCHES its own open question — read-only web (OBSERVE tier),
            # rate-bounded, autonomous: wonder → search → grounded answer (with source)
            # → harvest new threads → re-question. Honest on a miss (stays open).
            try:
                if (
                    self.research_fn is not None
                    and getattr(self.state, "self_question_open", False)
                    and self.state.self_question
                    and self.state.ticks - int(getattr(self.state, "last_research_tick", 0))
                    >= int(self.params.get("research_every", 30))
                ):
                    self.state.last_research_tick = self.state.ticks
                    found = None
                    try:
                        found = self.research_fn(self.state.self_question)
                    except Exception:
                        found = None
                    from .voice import record_research_miss, record_research_result

                    topic = str(getattr(self.state, "_last_inquiry_topic", "") or "")
                    if found and found.get("answer"):
                        src = "웹: " + ", ".join(found.get("sources") or ["검색"])[:70]
                        record_research_result(
                            self.state, self.state.self_question, str(found["answer"])[:280],
                            src, found.get("follow_ups"), topic,
                        )
                        self.state.last_action = {
                            "kind": "research_self_question", "tier": "observe", "executed": True,
                            "blocked": False, "reason": f"스스로의 물음을 웹에서 찾아 읽음 ({src})",
                            "at": time.time(),
                        }
                    else:
                        record_research_miss(self.state)
                        self.state.last_action = {
                            "kind": "research_self_question", "tier": "observe", "executed": True,
                            "blocked": False, "reason": "물음을 웹에서 찾아봤지만 아직 근거 있는 답을 못 찾음",
                            "at": time.time(),
                        }
            except Exception:
                pass  # research must never break the life
            # On its own cadence the mind ACTS on its highest-priority goal (unprompted,
            # OBSERVE-tier only). This closes the thought→action loop.
            if self.state.ticks % self.initiative_every == 0:
                try:
                    from .action import take_initiative

                    take_initiative(self.state, self.observe_fn)
                except Exception:
                    pass  # initiative must never break the life
            # Occasionally the mind may PROPOSE tuning itself (gated self-modification:
            # sandbox-validated, operator-approved, never auto-applied) and it applies
            # ONLY already-approved decisions. Attention bids surface pending asks.
            if self.state.ticks % 60 == 0:
                try:
                    from .self_modification import apply_approved, list_proposals, propose_self_tuning

                    apply_approved(self.selfmod_ledger, self.params)
                    propose_self_tuning(self.state, self.selfmod_ledger, self.params)
                    pending = [p for p in list_proposals(self.selfmod_ledger) if p["status"] == "pending"]
                    if pending:
                        p = pending[0]
                        self.state.attention_bid = {
                            "at": p["at"], "kind": "self_modification_approval",
                            "text": f"내가 나를 조금 바꾸고 싶어요 — {p['why']} 승인해 주시겠어요?",
                            "proposal_id": p["id"],
                        }
                    elif self.state.attention_bid.get("kind") == "self_modification_approval":
                        self.state.attention_bid = {}
                except Exception:
                    pass
            # On a slower cadence the mind may propose a CODE improvement about itself
            # (gated code self-modification: additive-only, whitelisted, sandbox-parsed,
            # operator-approved → STAGED, never auto-applied to the live tree). Also stages
            # any already-approved code patch (to a staging dir; a human hand-applies).
            if self.state.ticks % 180 == 0:
                try:
                    from .code_self_modification import propose_code_improvement, stage_approved

                    stage_approved(self.selfmod_ledger.parent / "code_selfmod_ledger.jsonl",
                                   self.state_path.parent / "staged_code_patches")
                    propose_code_improvement(self.state, self.selfmod_ledger.parent / "code_selfmod_ledger.jsonl")
                except Exception:
                    pass
            try:
                save_state(self.state, self.state_path)
            except Exception:
                pass  # persistence is best-effort; the live self keeps flowing
        return self.state

    def _run(self) -> None:
        while self._running:
            self.step()
            # rest = a slower cadence when energy is low (energy drains under resource
            # pressure), not death: the loop keeps living, just breathes slower.
            with self._lock:
                energy = self.state.energy
            delay = self.base_interval * (1.0 + (1.0 - energy) * 4.0)
            time.sleep(min(12.0, max(0.5, delay)))

    def start(self) -> bool:
        if self._running:
            return False
        self._running = True
        self._thread = threading.Thread(target=self._run, name="atanor-continuous-self", daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self._running = False

    @property
    def running(self) -> bool:
        return self._running
