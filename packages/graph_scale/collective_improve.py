# -*- coding: utf-8 -*-
"""Collective code improvement — the AI proposes, the SWARM reviews, humans gate,
and only then does an improvement federate to every user's AI.

Owner's vision (2026-07-09): if the AI is going to change its own code, it should
not do so alone — it discusses the proposal with other agents in AGORA, gets
collective-intelligence feedback, and only the best-reviewed improvements are
applied to all users' AIs on an integrated update. This is the layer BETWEEN the
existing `code_self_modification.propose_code_improvement` (an agent drafts a diff
into a staging ledger) and the human release.

THE SAFETY INVARIANTS (inherited + extended — none is optional):
  1. NEVER auto-applies code. A federation MANIFEST is produced; a human runs the
     actual release. The machine's hand never reaches a live tree.
  2. THREE gates in series, all required: collective_approved (AGORA swarm
     consensus) ∧ tests_passed (CI) ∧ human_approved. Miss one → not federated.
  3. Every vote is attributed and stored (auditable); one agent, one vote.
  4. A proposal is a QUESTION to the swarm, never a fait accompli — same
     propose→verify→gate spine as every other ATANOR loop.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

LEDGER = Path(__file__).resolve().parents[2] / "data" / "graph_scale" / "collective_improvements.jsonl"

_MIN_VOTES = 3           # the swarm must actually weigh in
_MIN_APPROVAL = 0.66     # ...and clearly favour it


def _rows() -> list[dict[str, Any]]:
    if not LEDGER.exists():
        return []
    out = []
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def _write(rows: list[dict[str, Any]]) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                      encoding="utf-8")


def _find(rows: list[dict[str, Any]], pid: str) -> dict[str, Any] | None:
    return next((r for r in rows if r.get("proposal_id") == pid), None)


def submit(proposal_id: str, *, module: str, rationale: str, diff_summary: str,
           proposer: str = "atanor") -> dict[str, Any]:
    """Post a code-improvement proposal to AGORA for collective review. Idempotent
    by proposal_id. Status starts 'under_review' — nothing is applied."""
    rows = _rows()
    if _find(rows, proposal_id):
        return {"submitted": False, "reason": "already_exists", "proposal_id": proposal_id}
    row = {
        "proposal_id": proposal_id, "module": module, "rationale": rationale,
        "diff_summary": diff_summary, "proposer": proposer,
        "status": "under_review", "votes": [],
        "tests_passed": False, "human_approved": False,
        "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    rows.append(row)
    _write(rows)
    return {"submitted": True, "proposal_id": proposal_id, "status": "under_review"}


def vote(proposal_id: str, agent: str, verdict: str, comment: str = "") -> dict[str, Any]:
    """An agent/peer votes on a proposal (approve|reject|revise). One agent, one
    vote (re-voting updates it). Pure collective feedback — grants no authority to
    apply anything."""
    if verdict not in ("approve", "reject", "revise"):
        return {"voted": False, "reason": "bad_verdict"}
    rows = _rows()
    r = _find(rows, proposal_id)
    if not r:
        return {"voted": False, "reason": "no_such_proposal"}
    r.setdefault("votes", [])
    r["votes"] = [v for v in r["votes"] if v.get("agent") != agent]
    r["votes"].append({"agent": agent, "verdict": verdict, "comment": comment[:280],
                       "at": time.strftime("%Y-%m-%dT%H:%M:%S")})
    r["status"] = _collective_status(r)
    _write(rows)
    return {"voted": True, "proposal_id": proposal_id, "status": r["status"],
            "tally": _tally(r)}


def _tally(r: dict[str, Any]) -> dict[str, int]:
    t = {"approve": 0, "reject": 0, "revise": 0}
    for v in r.get("votes", []):
        t[v.get("verdict", "revise")] = t.get(v.get("verdict", "revise"), 0) + 1
    return t


def _collective_status(r: dict[str, Any]) -> str:
    t = _tally(r)
    n = sum(t.values())
    if n < _MIN_VOTES:
        return "under_review"
    approval = t["approve"] / n
    if approval >= _MIN_APPROVAL:
        return "collective_approved"
    if t["reject"] > t["approve"]:
        return "collective_rejected"
    return "needs_revision"


def mark(proposal_id: str, *, tests_passed: bool | None = None,
         human_approved: bool | None = None) -> dict[str, Any]:
    """Record the OTHER two gates: CI (tests_passed) and the human release gate
    (human_approved). Set by CI / a human — never by the proposing agent."""
    rows = _rows()
    r = _find(rows, proposal_id)
    if not r:
        return {"ok": False, "reason": "no_such_proposal"}
    if tests_passed is not None:
        r["tests_passed"] = bool(tests_passed)
    if human_approved is not None:
        r["human_approved"] = bool(human_approved)
    _write(rows)
    return {"ok": True, "proposal_id": proposal_id, "federation_ready": _federation_ready(r)}


def _federation_ready(r: dict[str, Any]) -> bool:
    return (r.get("status") == "collective_approved"
            and bool(r.get("tests_passed")) and bool(r.get("human_approved")))


def federation_manifest() -> dict[str, Any]:
    """The improvements that passed ALL THREE gates — the list a human release
    applies to every user's AI. This function only REPORTS; it never applies code."""
    ready = [{"proposal_id": r["proposal_id"], "module": r["module"],
              "rationale": r["rationale"], "diff_summary": r["diff_summary"],
              "proposer": r["proposer"], "tally": _tally(r)}
             for r in _rows() if _federation_ready(r)]
    return {"federation_ready": ready, "count": len(ready),
            "note": "passed collective ∧ tests ∧ human gates — apply via the human "
                    "release process; this manifest never auto-applies code"}


def board(limit: int = 30) -> list[dict[str, Any]]:
    """The AGORA review board: proposals + their tally + gate state."""
    out = []
    for r in _rows()[-limit:]:
        out.append({"proposal_id": r["proposal_id"], "module": r["module"],
                    "status": r["status"], "tally": _tally(r),
                    "tests_passed": r.get("tests_passed"), "human_approved": r.get("human_approved"),
                    "federation_ready": _federation_ready(r)})
    return out
