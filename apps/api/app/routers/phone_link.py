# -*- coding: utf-8 -*-
"""Phone Link API — pairing state for the shell, on/off switch.

GET  /api/phone-link/status  -> {code, enabled, last_text, last_answer, link_url}
POST /api/phone-link/enable  -> start the relay poller
POST /api/phone-link/disable
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from packages import phone_link

router = APIRouter(prefix="/api/phone-link", tags=["phone-link"])

LINK_URL = "https://atanor-liard.vercel.app/link"


@router.get("/status")
def status() -> dict[str, Any]:
    st = phone_link.get_state()
    st["code"] = phone_link.ensure_code()
    st["link_url"] = LINK_URL
    return st


@router.post("/enable")
def enable() -> dict[str, Any]:
    st = phone_link.start(True)
    st["link_url"] = LINK_URL
    return st


@router.post("/disable")
def disable() -> dict[str, Any]:
    st = phone_link.start(False)
    st["link_url"] = LINK_URL
    return st
