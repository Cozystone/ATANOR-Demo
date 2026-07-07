# -*- coding: utf-8 -*-
"""OS Action Lane API — the orb's bridge to the real desktop.

POST /api/os-action/propose   {text}          -> classify+gate a natural request
POST /api/os-action/approve   {token}         -> run a held action (voice '응'/click)
POST /api/os-action/reject    {token}
GET  /api/os-action/status                    -> tier, pending, kill state
POST /api/os-action/tier      {tier}          -> raise/lower trust (0..3)
POST /api/os-action/kill      {on}            -> kill switch

Local-only: binds to the engine on 127.0.0.1; drives THIS machine's desktop. Every
action is audited to data/os_action/audit.jsonl. Starts at ASSIST (approve-every-action)
— the tier is trust the user grants, never assumed.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from packages.os_action_lane import Action, OSActionLane, TrustTier
from packages.os_action_lane.backends import LinuxDesktopBackend
from packages.os_action_lane.intent import parse_intent

router = APIRouter(prefix="/api/os-action", tags=["os-action"])

_AUDIT = Path(__file__).resolve().parents[4] / "data" / "os_action" / "audit.jsonl"
# one process-lifetime lane on the REAL desktop; ASSIST until the user raises the tier.
_LANE = OSActionLane(LinuxDesktopBackend(), tier=TrustTier(int(os.environ.get("ATANOR_TRUST_TIER", TrustTier.ASSIST))), audit_path=_AUDIT)


class ProposeIn(BaseModel):
    text: str = Field(..., max_length=1000)


class TokenIn(BaseModel):
    token: str = Field(..., max_length=64)


class TierIn(BaseModel):
    tier: int = Field(..., ge=0, le=3)


class KillIn(BaseModel):
    on: bool = True


@router.post("/propose")
def propose(body: ProposeIn) -> dict[str, Any]:
    action = parse_intent(body.text)
    if action is None:
        return {"is_os_action": False, "reason": "not an OS command — answer as a question"}
    result = _LANE.propose(action)
    out = result.to_dict()
    out["is_os_action"] = True
    # surface the approval token cleanly when the action is held
    if result.outcome != 0 and result.stdout:  # NEEDS_APPROVAL/BLOCKED carry token in stdout
        out["approval_token"] = result.stdout
    return out


@router.post("/approve")
def approve(body: TokenIn) -> dict[str, Any]:
    r = _LANE.approve(body.token)
    return {"ok": False, "detail": "no such pending action"} if r is None else r.to_dict()


@router.post("/reject")
def reject(body: TokenIn) -> dict[str, Any]:
    return {"rejected": _LANE.reject(body.token)}


@router.get("/status")
def status() -> dict[str, Any]:
    return {"tier": int(_LANE.tier), "tier_name": _LANE.tier.name,
            "pending": _LANE.pending(), "killed": _LANE._killed,  # noqa: SLF001
            "audit_path": str(_AUDIT)}


@router.get("/trust-recommendation")
def trust_recommendation() -> dict[str, Any]:
    """Phase 5: evidence-backed tier-promotion recommendation from the audit
    track record. Reports only — the grant is always the user's (POST /tier)."""
    from packages.os_action_lane.trust_record import promotion_recommendation

    return promotion_recommendation(_AUDIT, _LANE.tier)


@router.post("/tier")
def set_tier(body: TierIn) -> dict[str, Any]:
    _LANE.set_tier(TrustTier(body.tier))
    return {"tier": int(_LANE.tier), "tier_name": _LANE.tier.name}


@router.post("/kill")
def kill(body: KillIn) -> dict[str, Any]:
    if body.on:
        _LANE.kill()
    else:
        _LANE.reset_kill()
    return {"killed": _LANE._killed}  # noqa: SLF001
