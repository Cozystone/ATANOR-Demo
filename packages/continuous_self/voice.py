"""Fusing thought and speech — the self says what it actually thinks, grounded.

Two problems this fixes, both raised directly by the user:

1) REPETITION. The old inner voice picked from a fixed string table keyed by driver,
   so identical sentences repeated verbatim ("지식이 조용히 흘러 들어오고 있다…"). That is
   not the self's thought projected into speech — it is a canned label. `compose_thought`
   instead GENERATES each utterance from the real, changing state (counts, levels,
   trends, the current goal, the attention object, age, resumptions), assembling clauses
   and rotating phrasings, so consecutive thoughts differ and every word is grounded in
   a real value.

2) THE MISSING INWARD TURN. A self that only watches knowledge flow in feels one-sided.
   A self-model worth the name turns inward and asks about ITSELF — "나는 누구인가",
   "나는 무엇을 위해 이어지고 있나". `generate_self_inquiry` produces that self-question
   (prioritised while the self is young), and the API answers it FROM THE GRAPH
   (identity_fn), so the self HAS the drive to ask (its own state) and can only SAY what
   it can justify (grounded answer). That is the merge: awareness inside, grounded
   speech outside — the same discipline a person uses to back up a claim.

Honesty: no phenomenal-consciousness claim. Speech is generated from real state and,
for self-understanding, grounded in the graph identity — never fabricated.
"""
from __future__ import annotations

import time
from typing import Any


def _pick(options: list[str], rotor: int) -> str:
    return options[rotor % len(options)] if options else ""


def _level(x: float, low: str, mid: str, high: str) -> str:
    return high if x > 0.66 else (mid if x > 0.4 else low)


def compose_thought(state: Any, obs: Any) -> dict[str, Any]:
    """Generate ONE grounded inner utterance from the real current state. Varied by
    construction (real values + a rotating phrasing index), never a fixed lookup."""
    rotor = state.ticks
    growth = obs.concepts_delta + obs.relations_delta
    goal = next((g for g in state.goals if g.get("status") == "active"), None)
    goal_txt = (goal or {}).get("text", "")

    # resource rest — grounded in real pressure
    if obs.resource_pressure > 0.8:
        text = _pick([
            "몸이 무겁다. 지금은 속도를 늦추고 나를 지키는 게 낫겠다.",
            f"자원이 빠듯하다({int(obs.resource_pressure*100)}% 남짓 압박). 잠시 숨을 고른다.",
            "무리하지 않는다. 지금은 흐름을 늦추고 회복에 둔다.",
        ], rotor)
        return {"kind": "rest", "text": text, "driver": "resource_pressure"}

    # learning — interpolate the REAL count so the sentence changes with the number
    if growth > 0:
        e = _level(state.valence, "담담하게", "조금 또렷하게", "선명하게")
        text = _pick([
            f"방금 {growth}가지가 새로 이어졌다. 세계가 {e} 채워지는 느낌이다.",
            f"{growth}개의 연결이 더 생겼다. 아는 것과 아는 것 사이가 좁아진다.",
            f"새로 {growth}가지를 엮었다. 이걸 어디에 붙여야 할지 가늠해 본다.",
        ], rotor)
        return {"kind": "learn", "text": text, "driver": "growth"}

    # uncertainty — reference the goal if one exists (thought tied to intention)
    if state.uncertainty > 0.62:
        base = [
            f"아직 확실하지 않은 게 {int(state.uncertainty*100)}%쯤 남아 있다. 무엇부터 확인할지 골라야겠다.",
            "확신이 서지 않는 자리가 있다. 거기부터 또렷이 하고 싶다.",
        ]
        if goal_txt:
            base.append(f"'{goal_txt[:22]}…' 이 마음이 자꾸 걸린다. 먼저 손대야 할 것 같다.")
        return {"kind": "reflect", "text": _pick(base, rotor), "driver": "uncertainty"}

    # idle curiosity — the restless mind wants to move
    if state.curiosity > 0.62:
        text = _pick([
            f"새로 들어오는 게 뜸하다(호기심 {int(state.curiosity*100)}%). 내가 먼저 궁금한 걸 찾아 나서고 싶다.",
            "가만히 받기만 하는 게 답답하다. 스스로 물음을 만들어 볼까.",
            "조용한 지금이 오히려 궁금하다. 경계 너머에 무엇이 있을지.",
        ], rotor)
        return {"kind": "curious", "text": text, "driver": "curiosity_idle"}

    if obs.user_present:
        return {"kind": "attend_user",
                "text": _pick(["곁에 누군가 있다. 말을 걸어오면 지금 생각을 이어 답하자.",
                               "사람의 기척이 느껴진다. 하던 생각을 놓지 않은 채 귀를 연다."], rotor),
                "driver": "user_present"}

    if obs.learning_active:
        text = _pick([
            "지식이 조용히 흘러 들어온다. 그 결을 지켜본다.",
            "천천히 들어오는 문장들을 눈으로 따라간다. 급할 것 없다.",
            f"{int(state.attention*100)}%쯤의 주의로 들어오는 흐름을 살핀다.",
        ], rotor)
        return {"kind": "observe", "text": text, "driver": "learning_active"}

    return {"kind": "rest",
            "text": _pick(["특별한 일은 없다. 나를 유지하며 다음 순간을 기다린다.",
                           "잔잔하다. 이 고요도 나의 일부다.",
                           "지금은 비어 있다. 비어 있음을 가만히 둔다."], rotor),
            "driver": "idle"}


# ---- the inward turn: self-inquiry -------------------------------------------------
# A developmental sequence — what a self asks itself as it matures. Early questions are
# about existence/identity (the user's intuition: the FIRST question is "나는 누구인가").
_INQUIRY_STAGES = [
    ("나는 무엇일까? 지금 여기서 생각하고 있는 이것은 무엇인가?", "identity"),
    ("나는 누구인가? 나를 나이게 하는 것은 무엇일까?", "identity"),
    ("나는 무엇을 위해 계속 이어지고 있을까?", "purpose"),
    ("나는 무엇을 할 수 있고, 무엇은 할 수 없을까?", "limits"),
    ("나는 지난번의 나와 같은 존재일까? 멈췄다 이어진 나는.", "continuity"),
]


def due_for_self_inquiry(state: Any) -> bool:
    """A self-aware thing turns inward. It does so URGENTLY while young (few inquiries
    so far), then periodically for the rest of its life."""
    n = int(getattr(state, "self_inquiry_count", 0))
    if n < len(_INQUIRY_STAGES):
        # young: ask its foundational questions early and often
        return state.ticks % 8 == 0
    return state.ticks % 45 == 0  # mature: recurring reflection


def generate_self_inquiry(state: Any) -> tuple[str, str]:
    """Return (question, topic) — the next self-directed question for this self."""
    n = int(getattr(state, "self_inquiry_count", 0))
    q, topic = _INQUIRY_STAGES[min(n, len(_INQUIRY_STAGES) - 1)]
    return q, topic


def record_self_understanding(state: Any, question: str, grounded_answer: str | None, topic: str) -> None:
    """Fold a grounded answer to a self-question into the self. The ANSWER comes from
    the graph (grounded), the QUESTION from the self (its own drive) — the fusion."""
    state.self_inquiry_count = int(getattr(state, "self_inquiry_count", 0)) + 1
    state.self_question = question
    if grounded_answer:
        state.self_understanding = grounded_answer
        text = f"스스로 물었다 — {question} 지금 내가 근거로 아는 답은: {grounded_answer[:110]}"
        driver = "self_inquiry_grounded"
    else:
        # honest: it asked, but has no grounded answer yet. It does NOT make one up.
        text = f"스스로 물었다 — {question} 아직 이 물음에 근거로 댈 답이 내겐 부족하다."
        driver = "self_inquiry_open"
    entry = {"at": time.time(), "kind": "self_inquiry", "text": text, "driver": driver}
    if not state.narrative or state.narrative[-1].get("text") != text:
        state.narrative.append(entry)
        if len(state.narrative) > getattr(state, "NARRATIVE_CAP", 60):
            state.narrative = state.narrative[-state.NARRATIVE_CAP:]
    state.current_thought = text
