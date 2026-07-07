"""Continuously-alive self — the always-on inner life (난제: continuity, not cron).

Starts ONE long-lived loop that eases a persistent self-state forward from real
observations (the cloud-brain learner's activity, disk pressure, open deficits). It
never wakes/sleeps on a schedule; it flows and, on restart, RESUMES the same self.
Read-only and bounded: it mutates no code, no graph, no store — it only feels and
reports its own state. Two endpoints feed the "living-mind" UI:
    GET /api/selfhood/live    → the current self snapshot
    GET /api/selfhood/stream  → SSE, pushes the self as it changes (hash-diffed)
"""
from __future__ import annotations

import asyncio
import json
import shutil
import time
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from packages.continuous_self.loop import ContinuousSelf
from packages.continuous_self.self_state import Observation

router = APIRouter(prefix="/api/selfhood", tags=["continuous-self"])

_STATE_PATH = Path(__file__).resolve().parents[4] / "runtime" / "continuous_self" / "self_state.json"

# delta tracking across observations (net-new growth is what the self "feels")
_prev = {"concepts": None, "relations": None}


def _disk_pressure() -> float:
    try:
        usage = shutil.disk_usage(str(Path(__file__).resolve().parents[4]))
        free_ratio = usage.free / max(1, usage.total)
        # pressure rises as free space falls below ~8%
        return max(0.0, min(1.0, (0.08 - free_ratio) / 0.08)) if free_ratio < 0.08 else 0.0
    except Exception:
        return 0.0


def _observe() -> Observation:
    """Gather the self's real signals THIS instant. Grounded, never fabricated."""
    learning_active = False
    c_delta = r_delta = 0
    uncertainty = 0.3
    deficits = 0
    try:
        from .cloud_brain import cloud_brain_continuous_metrics

        m = cloud_brain_continuous_metrics()
        learning_active = bool(m.get("running"))
        c = int(m.get("concepts_added") or 0)
        r = int(m.get("relations_added") or 0)
        if _prev["concepts"] is not None:
            c_delta = max(0, c - int(_prev["concepts"]))
            r_delta = max(0, r - int(_prev["relations"]))
        _prev["concepts"], _prev["relations"] = c, r
        # accept-rate below 1 means unresolved / rejected material → felt as uncertainty
        acc = float(m.get("accept_rate") or 1.0)
        uncertainty = max(0.0, min(1.0, 1.0 - acc))
    except Exception:
        pass
    try:
        hist = _STATE_PATH.parent.parent.parent / "data" / "self_improve_history.jsonl"
        if hist.exists():
            last = hist.read_text(encoding="utf-8").strip().splitlines()[-1]
            deficits = int(json.loads(last).get("hard_remaining") or 0)
    except Exception:
        pass
    # Phase 4-5 x 3-6: the camera's person-sighting IS the user's presence —
    # perception reaching the selfhood loop (arrival fires noradrenaline there)
    user_present = False
    try:
        from .perception import person_recently_seen

        user_present = person_recently_seen()
    except Exception:
        pass
    return Observation(
        learning_active=learning_active,
        concepts_delta=c_delta,
        relations_delta=r_delta,
        uncertainty_signal=uncertainty,
        resource_pressure=_disk_pressure(),
        deficit_count=deficits,
        user_present=user_present,
    )


def _self_probe(kind: str) -> dict[str, Any]:
    """A READ-ONLY probe the mind runs on ITSELF to serve a goal. OBSERVE-tier only —
    it never writes to the graph, a store, or code. It measures; it does not change."""
    if kind == "measure_coverage_gaps":
        try:
            hist = _STATE_PATH.parent.parent.parent / "data" / "self_improve_history.jsonl"
            last = json.loads(hist.read_text(encoding="utf-8").strip().splitlines()[-1])
            return {"open_gaps": int(last.get("hard_remaining") or 0),
                    "answered": int(last.get("answered_after") or 0)}
        except Exception:
            return {}
    if kind == "probe_uncertainty":
        try:
            from .cloud_brain import cloud_brain_continuous_metrics

            m = cloud_brain_continuous_metrics()
            return {"accept_rate": m.get("accept_rate"), "last_error": m.get("last_error")}
        except Exception:
            return {}
    if kind == "scan_frontier":
        # a read-only peek at what the learner is reaching toward next (no side effects).
        try:
            from .cloud_brain import cloud_brain_continuous_metrics

            titles = cloud_brain_continuous_metrics().get("last_titles") or []
            return {"frontier": titles[0]} if titles else {}
        except Exception:
            return {}
    return {"observed": True}


def _identity_answer(question: str, topic: str) -> str | None:
    """Answer the self's OWN question ABOUT itself, FROM THE GRAPH — so the self only
    SAYS what it can justify (the 'atanor' concept + honesty guarantees), never invents.
    This is the fusion: the drive to ask is the self's; the answer must be grounded."""
    try:
        from packages.base_brain.zero_user_answer import answer_with_base_brain

        res = answer_with_base_brain("너는 누구야", "ko")
        ans = str((res or {}).get("answer") or "").strip()
        cert = (res or {}).get("reasoning_certificate") or {}
        # only accept a grounded, non-abstaining identity answer.
        if ans and "근거가 부족" not in ans and cert.get("derivation_kind") != "abstained":
            return ans
    except Exception:
        pass
    return None


def _research(question: str) -> dict[str, Any] | None:
    """READ-ONLY web research for the self's own open question (OBSERVE tier — it
    reads public pages, writes nothing but the self-state). Uses the same relevance-
    gated pipeline as chat answers (referent resonance inside compose_web_answer), so
    an off-topic page is rejected rather than absorbed — the self only comes to
    'know' what actually answers its question. Returns {answer, sources, follow_ups}
    or None (an honest miss)."""
    try:
        from app.services.web_search import compose_web_answer, general_web_search

        q = str(question or "").strip()
        if not q:
            return None
        rows = general_web_search(q, count=6)
        composed = compose_web_answer(q, rows, language="ko") if rows else None
        if not composed or not str(composed.get("answer") or "").strip():
            # philosophical phrasings ("~은 나에게 무엇일까?") may not anchor a page;
            # retry on the question's own content terms (morphology-level extraction).
            from packages.continuous_self.voice import harvest_terms

            terms = harvest_terms(q, set(), limit=2)
            if terms:
                rows = general_web_search(" ".join(terms), count=6)
                composed = compose_web_answer(terms[0], rows, language="ko") if rows else None
        if composed and str(composed.get("answer") or "").strip():
            ans = str(composed["answer"]).strip()
            # junk gate: navigation/link-list text is not knowledge. A real prose
            # answer doesn't carry pipe-separated menus or long middot chains, and
            # it has enough body to say something (seen live: a 국립국어원 nav bar
            # absorbed as "self-understanding").
            if ans.count("|") >= 2 or ans.count("·") >= 6 or len(ans) < 40:
                return None
            return {
                "answer": ans,
                "sources": list(composed.get("sources") or []),
                "follow_ups": list(composed.get("follow_ups") or []),
            }
    except Exception:
        return None
    return None


_SELF = ContinuousSelf(
    _STATE_PATH, _observe, base_interval=2.0, observe_fn=_self_probe,
    identity_fn=_identity_answer, research_fn=_research, initiative_every=15,
    research_every=30,
)


def _ensure_alive() -> None:
    if not _SELF.running:
        _SELF.start()


@router.get("/live")
def selfhood_live() -> dict[str, Any]:
    _ensure_alive()
    return _SELF.snapshot()


_DEEPEN_STORE: Any = None


def _deepen_store() -> Any:
    global _DEEPEN_STORE
    if _DEEPEN_STORE is None:
        from packages.graph_scale.abstain_feeder import STORE_ROOT
        from packages.graph_scale.triple_store import TripleStore

        _DEEPEN_STORE = TripleStore(STORE_ROOT)
    return _DEEPEN_STORE


@router.post("/deepen")
def selfhood_deepen(payload: dict[str, Any]) -> dict[str, Any]:
    """Self-awareness -> answer-depth fusion, demonstrated end-to-end on LIVE
    self-state: if the query is about what the self is currently pondering, weave
    MORE of that subject's GROUNDED relations into the answer. Additive only —
    the extra clauses are literal graph facts, so hallucination-0 is preserved.
    `set_self_question` lets you steer the self's focus to see engaged-vs-not."""
    _ensure_alive()
    query = str(payload.get("query") or "").strip()
    if not query:
        return {"error": "query_required"}
    st = _SELF.state
    state = {
        "self_question": getattr(st, "self_question", "") or "",
        "self_question_open": bool(getattr(st, "self_question_open", False)),
        "last_inquiry_topic": getattr(st, "_last_inquiry_topic", "") or "",
        "curiosity": float(getattr(st, "curiosity", 0.5) or 0.5),
        "recent_insights": [],
    }
    if payload.get("set_self_question"):  # demo: steer the self's focus
        state["self_question"] = str(payload["set_self_question"])
        state["self_question_open"] = True

    from packages.continuous_self.inquiry_fusion import (
        depth_bias, engagement_note, extra_relation_budget,
    )
    from packages.graph_scale.query_frame import parse

    subject = parse(query).subject or query
    bias = depth_bias(subject, state)

    from packages.base_brain.zero_user_answer import answer_with_base_brain

    base = answer_with_base_brain(query)
    base_answer = str(base.get("answer") or "")
    deepened, added = base_answer, []
    if bias >= 0.5:
        try:
            budget = extra_relation_budget(bias) - 3  # only the EXTRA relations
            facts = _deepen_store().facts_about(subject, limit=budget + 4)
            for (s, p, o) in facts:
                if o and str(o) not in base_answer and str(o) not in query:
                    added.append(f"{s}의 {p}: {o}")
                if len(added) >= max(1, budget):
                    break
        except Exception:
            added = []
        if added:
            deepened = f"{base_answer.rstrip()} — {'; '.join(added)}. ({engagement_note(subject, bias)})"

    return {
        "query": query, "subject": subject,
        "self_question": state["self_question"],
        "self_question_open": state["self_question_open"],
        "depth_bias": bias, "self_engaged": bias >= 0.5,
        "base_answer": base_answer,
        "deepened_answer": deepened,
        "added_grounded_relations": added,
        "note": engagement_note(subject, bias),
        "hallucination_safe": True,
    }


# ---- gated self-modification: operator approval API -------------------------------
# The mind proposes; ONLY a human decides here. Nothing auto-applies anywhere.
@router.get("/self-modification/proposals")
def selfmod_proposals() -> dict[str, Any]:
    from packages.continuous_self.self_modification import list_proposals

    rows = list_proposals(_SELF.selfmod_ledger)
    return {"proposals": rows[-20:], "pending": [r for r in rows if r["status"] == "pending"],
            "current_params": dict(_SELF.params)}


@router.post("/self-modification/decide")
def selfmod_decide(payload: dict[str, Any]) -> dict[str, Any]:
    """Operator decision. Body: {proposal_id, approve: bool, confirm: "SELF_MOD",
    note?}. The confirm phrase is a deliberate friction — a human must mean it."""
    from packages.continuous_self.self_modification import apply_approved, decide

    if str(payload.get("confirm") or "") != "SELF_MOD":
        return {"ok": False, "reason": "confirm phrase 'SELF_MOD' required — operator only"}
    hit = decide(_SELF.selfmod_ledger, str(payload.get("proposal_id") or ""),
                 bool(payload.get("approve")), str(payload.get("note") or ""))
    if hit is None:
        return {"ok": False, "reason": "proposal not found or not pending"}
    applied = apply_approved(_SELF.selfmod_ledger, _SELF.params) if hit["status"] == "approved" else []
    # clear the bid once decided
    if _SELF.state.attention_bid.get("proposal_id") == hit["id"]:
        _SELF.state.attention_bid = {}
    return {"ok": True, "decision": hit["status"], "applied": [a["id"] for a in applied],
            "current_params": dict(_SELF.params)}


_CODE_LEDGER = _STATE_PATH.parent / "code_selfmod_ledger.jsonl"
_STAGED_DIR = _STATE_PATH.parent / "staged_code_patches"


@router.get("/code-modification/proposals")
def code_mod_proposals() -> dict[str, Any]:
    """Code-patch proposals the mind raised about its OWN source. Read-only view; the
    patches are additive-only and whitelisted, and NONE is applied to the live tree."""
    from packages.continuous_self.code_self_modification import _load as _load_cm

    rows = _load_cm(_CODE_LEDGER)
    return {"proposals": rows[-20:], "pending": [r for r in rows if r["status"] == "pending"],
            "note": "코드 패치는 추가(additive)만, 화이트리스트 파일만, 승인해도 라이브 코드가 아니라 스테이징에만 기록됩니다."}


@router.post("/code-modification/decide")
def code_mod_decide(payload: dict[str, Any]) -> dict[str, Any]:
    """Operator decision on a CODE patch. Body: {proposal_id, approve, confirm:
    "SELF_MOD_CODE", note?}. A DISTINCT, stronger confirm phrase than parameter changes.
    On approval the patch is STAGED to a directory only — the live source is never touched
    by the machine; a human reviews the staged .patch and applies it by hand."""
    from packages.continuous_self.code_self_modification import stage_approved
    from packages.continuous_self.self_modification import decide

    if str(payload.get("confirm") or "") != "SELF_MOD_CODE":
        return {"ok": False, "reason": "confirm phrase 'SELF_MOD_CODE' required — operator only, code changes"}
    hit = decide(_CODE_LEDGER, str(payload.get("proposal_id") or ""),
                 bool(payload.get("approve")), str(payload.get("note") or ""))
    if hit is None:
        return {"ok": False, "reason": "proposal not found or not pending"}
    staged = stage_approved(_CODE_LEDGER, _STAGED_DIR) if hit["status"] == "approved" else []
    return {"ok": True, "decision": hit["status"],
            "staged": [{"id": s["id"], "staged_path": s.get("staged_path")} for s in staged],
            "live_tree_touched": False,
            "note": "승인된 패치는 스테이징 폴더에 기록만 되었습니다. 라이브 적용은 사람이 직접 검토 후 git apply로 합니다."}


@router.get("/consciousness")
def selfhood_consciousness() -> dict[str, Any]:
    """The honest consciousness-CORRELATES report (AST / HOT / IIT Φ-proxy / GWT) for the
    current self-state — functional measures only, never a claim of phenomenal experience."""
    _ensure_alive()
    from packages.continuous_self.consciousness_correlates import consciousness_report

    return consciousness_report(_SELF.state)


@router.get("/stream")
async def selfhood_stream() -> StreamingResponse:
    _ensure_alive()

    async def _events() -> AsyncIterator[str]:
        last = ""
        last_sent = 0.0
        while True:
            snap = _SELF.snapshot()
            body = json.dumps(snap, ensure_ascii=False)
            now = time.time()
            # the clock-ish fields change every step; hash the felt content instead so
            # a quiet mind streams quietly.
            felt = json.dumps(
                {"vitals": snap["vitals"], "mode": snap["mode"], "focus": snap["focus"],
                 "current_thought": snap["current_thought"]},
                ensure_ascii=False, sort_keys=True,
            )
            if felt != last:
                last = felt
                last_sent = now
                yield f"data: {body}\n\n"
            elif now - last_sent >= 20.0:
                last_sent = now
                yield ": heartbeat\n\n"
            await asyncio.sleep(1.0)

    return StreamingResponse(
        _events(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# Begin living as soon as the API imports this router — the self should already be
# awake when the first observer looks. Guarded so an import-time hiccup can't crash
# app startup.
try:
    _SELF.start()
except Exception:
    pass
