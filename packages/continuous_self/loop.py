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
        initiative_every: int = 15,
    ):
        self.state_path = Path(state_path)
        self.obs_provider = obs_provider
        self.base_interval = float(base_interval)
        # A read-only probe the mind may run ITSELF to serve its goals (action.py).
        # OBSERVE-tier only, by construction; higher tiers are never autonomous.
        self.observe_fn = observe_fn
        self.initiative_every = max(1, int(initiative_every))
        self.state: SelfState = load_or_begin(self.state_path)
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._running = False

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
            # On its own cadence the mind ACTS on its highest-priority goal (unprompted,
            # OBSERVE-tier only). This closes the thought→action loop.
            if self.state.ticks % self.initiative_every == 0:
                try:
                    from .action import take_initiative

                    take_initiative(self.state, self.observe_fn)
                except Exception:
                    pass  # initiative must never break the life
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
