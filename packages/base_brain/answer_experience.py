"""Answer-policy EXPERIENCE ledger — self-correction from lived outcomes, not just a battery.

The tuner previously optimised a fixed hand-labelled battery. That is safe but cannot be
'스스로 정정': a routing mistake the battery never anticipated stays invisible (Goodhart).
This module closes the loop with real experience:

  1. RECORD: every live policy decision appends (query, feature snapshot, chosen mode).
     The snapshot is what the policy actually saw — so later labels judge the decision
     that was made, not a re-imagined one.
  2. LABEL: outcome evidence attaches an expected-mode set to a recorded decision.
     Sources are MEASURED, never guessed: the honesty eval's flagged confident-wrongs
     (expected {engage, abstain}) and its confirmed corrects (reinforce the chosen mode).
  3. TRAIN: labelled experience joins the battery in the tuner's margin objective —
     bounded to the latest N so old contexts fade — while the hand battery remains a
     hard accuracy FLOOR the tuner may never regress.

So a trigger-control mistake becomes data, data moves weights, and no human writes a new
rule. Bounded, append-only, deterministic to read."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2] / "data" / "base_brain"
LEDGER = _ROOT / "answer_experience.jsonl"
_MAX_READ = 4000          # bounded ledger scan
_MAX_EXAMPLES = 200       # latest labelled examples used for training


def _append(rec: dict[str, Any]) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def record_decision(query: str, features: dict[str, float], mode: str) -> None:
    """Log a live policy decision with its exact feature snapshot. Never raises."""
    try:
        _append({"kind": "decision", "q": (query or "")[:200],
                 "features": {k: round(float(v), 4) for k, v in (features or {}).items()},
                 "mode": mode, "ts": time.strftime("%Y-%m-%dT%H:%M:%S")})
    except Exception:
        pass


def label_outcome(query: str, expected_modes: list[str] | set[str], source: str) -> bool:
    """Attach measured outcome evidence to the LATEST decision for this query.
    Returns True if a matching decision existed. Never raises."""
    try:
        q = (query or "")[:200]
        lines = LEDGER.read_text(encoding="utf-8").splitlines()[-_MAX_READ:] if LEDGER.exists() else []
        for line in reversed(lines):
            rec = json.loads(line)
            if rec.get("kind") == "decision" and rec.get("q") == q:
                _append({"kind": "label", "q": q, "features": rec.get("features") or {},
                         "chosen": rec.get("mode"), "expected": sorted(set(expected_modes)),
                         "source": source, "ts": time.strftime("%Y-%m-%dT%H:%M:%S")})
                return True
        return False
    except Exception:
        return False


def training_examples(limit: int = _MAX_EXAMPLES) -> list[tuple[dict[str, float], set[str]]]:
    """Latest labelled experiences as (feature_snapshot, expected_mode_set). Deduped by
    query (newest label wins) so one repeated mistake doesn't dominate the objective."""
    if not LEDGER.exists():
        return []
    by_q: dict[str, tuple[dict[str, float], set[str]]] = {}
    try:
        for line in LEDGER.read_text(encoding="utf-8").splitlines()[-_MAX_READ:]:
            rec = json.loads(line)
            if rec.get("kind") == "label" and rec.get("features") and rec.get("expected"):
                by_q[rec["q"]] = ({k: float(v) for k, v in rec["features"].items()},
                                  set(rec["expected"]))
    except Exception:
        return []
    return list(by_q.values())[-limit:]
