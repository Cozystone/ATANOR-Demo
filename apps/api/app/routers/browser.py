# -*- coding: utf-8 -*-
"""ATANOR browser API — graph-native browsing (난제 P2/P2-2).

POST /api/browser/ingest    {url, html?}  -> distill + host-voiced record
GET  /api/browser/promotable              -> multi-host, judge-cleared candidates
GET  /api/browser/stats

Fetches are safe-URL gated (public http(s), no private ranges); the verified
store is NEVER written from here — browsing observes, the promotion gate decides.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body

router = APIRouter(prefix="/api/browser", tags=["browser"])

_LEDGER = None


def _ledger():
    global _LEDGER
    if _LEDGER is None:
        from packages.atanor_browser.browser_ingest import BrowserEvidenceLedger

        _LEDGER = BrowserEvidenceLedger()
    return _LEDGER


def _fetch(url: str) -> str | None:
    """Bounded, safe-URL-gated fetch of a public page."""
    try:
        from packages.cloud_brain.web_seed_feeder import is_safe_public_url
    except Exception:
        is_safe_public_url = None
    if is_safe_public_url is not None:
        ok, _reason = is_safe_public_url(url)
        if not ok:
            return None
    try:
        import urllib.request

        req = urllib.request.Request(url, headers={"User-Agent": "ATANOR-Browser/0.1"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            if int(resp.status) != 200:
                return None
            raw = resp.read(2_000_000)  # 2MB cap
        return raw.decode("utf-8", errors="replace")
    except Exception:
        return None


@router.post("/ingest")
def browser_ingest(body: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    from packages.atanor_browser.browser_ingest import ingest_page

    url = str(body.get("url") or "")
    html = body.get("html")
    if not html:
        if not url:
            return {"ok": False, "reason": "url or html required"}
        html = _fetch(url)
        if html is None:
            return {"ok": False, "reason": "fetch blocked or failed (safe-URL gate)"}
    out = ingest_page(str(html), url=url, ledger=_ledger())
    return {"ok": True, **out}


@router.get("/promotable")
def browser_promotable() -> dict[str, Any]:
    store = None
    try:
        from packages.graph_scale.answer_bridge import _store

        store = _store()
    except Exception:
        store = None
    return {"promotable": _ledger().promotable(store=store)}


@router.get("/promote-preview")
def browser_promote_preview(auto_mode: bool = False) -> dict[str, Any]:
    """Run consensus-cleared candidates through the SAME default-deny promotion
    gate the rest of the engine uses — shows eligible vs blocked (+reasons).
    Writes nothing; the operator confirms actual promotion via the gate."""
    store = None
    try:
        from packages.graph_scale.answer_bridge import _store

        store = _store()
    except Exception:
        store = None
    return _ledger().gate_preview(store=store, auto_mode=auto_mode)


@router.post("/forget")
def browser_forget(body: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    """Right to be forgotten (threat model §4): retract every graph row that
    mentions a subject. Auditable; returns the masked subject + count only."""
    subject = str(body.get("subject") or "").strip()
    if not subject:
        return {"ok": False, "reason": "subject required"}
    try:
        from packages.graph_scale.answer_bridge import _store
        from packages.graph_scale.pii_guard import forget

        store = _store()
        if store is None:
            return {"ok": False, "reason": "store unavailable"}
        return {"ok": True, **forget(store, subject)}
    except Exception as exc:
        return {"ok": False, "reason": f"{type(exc).__name__}"}


@router.get("/stats")
def browser_stats() -> dict[str, Any]:
    return _ledger().stats()
