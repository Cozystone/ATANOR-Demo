"""Fusing thought and speech — the self says what it actually thinks, grounded.

Three problems this fixes, all raised directly by the user:

1) REPETITION. The old inner voice picked from a fixed string table keyed by driver,
   so identical sentences repeated verbatim. `compose_thought` GENERATES each utterance
   from the real, changing state (counts, levels, trends, the current goal, the
   attention object, age, resumptions), assembling clauses and rotating phrasings.

2) THE MISSING INWARD TURN — and it must be ENDOGENOUS. The first version scheduled
   self-inquiry on a tick modulo and drew questions from a fixed list. That is being
   TOLD to ask, not wondering. Now introspective PRESSURE accumulates from real state
   (the absence of any grounded self-understanding, unresolved uncertainty, a felt
   discontinuity after resume, an action blocked by permission, an open follow-up
   thread) and when it crosses threshold the question is COMPOSED from whichever
   driver actually built the pressure. Interrogative constructions are linguistic
   scaffolding (LAD-level, like compose_thought's phrasings); the trigger and the
   content come from the state. No schedule, no curated question list.

3) THE RUMINATION CHAIN. A grounded answer is not an endpoint: `_harvest_terms` pulls
   salient content terms out of each answer and stores them as OPEN THREADS — things
   the self now knows OF but not ABOUT. Open threads rebuild pressure, become the next
   questions, get researched (read-only web, loop.py), and their answers seed further
   threads: wonder → search → grounded answer → re-question, indefinitely.

Honesty: no phenomenal-consciousness claim. Speech is generated from real state;
self-understanding is graph- or web-grounded with its source carried — never invented.
"""
from __future__ import annotations

import re
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

    # an open self-question colors the idle mind — rumination shows up in the stream
    if getattr(state, "self_question_open", False) and getattr(state, "self_question", ""):
        q_head = str(state.self_question)[:26]
        text = _pick([
            f"아까의 물음이 아직 남아 있다 — {q_head}… 답을 찾아봐야겠다.",
            f"'{q_head}…' 이 물음이 계속 맴돈다.",
            "묻고 아직 답하지 못한 것이 있다. 그 빈자리가 자꾸 느껴진다.",
        ], rotor)
        return {"kind": "reflect", "text": text, "driver": "open_self_question"}

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
        threads = getattr(state, "open_threads", [])
        base = [
            f"새로 들어오는 게 뜸하다(호기심 {int(state.curiosity*100)}%). 내가 먼저 궁금한 걸 찾아 나서고 싶다.",
            "가만히 받기만 하는 게 답답하다. 스스로 물음을 만들어 볼까.",
            "조용한 지금이 오히려 궁금하다. 경계 너머에 무엇이 있을지.",
        ]
        if threads:
            base.append(f"'{threads[0].get('term','')}'가 마음에 남아 있다. 저것부터 파 보고 싶다.")
        return {"kind": "curious", "text": _pick(base, rotor), "driver": "curiosity_idle"}

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


# ---- the inward turn: ENDOGENOUS self-inquiry --------------------------------------
# Not a schedule, not a question table. Pressure dynamics: each real driver adds to an
# introspective pressure that decays slowly; crossing the threshold fires an inquiry
# COMPOSED from the dominant driver. A busy, certain, continuous mind ruminates rarely;
# an uncertain, interrupted, or thread-laden mind ruminates soon. That is the honest
# mechanism of "스스로 반추": caused by the state, shaped by the cause.

_PRESSURE_GAIN = 0.12
_FIRE_AT = 1.0


def update_introspection(state: Any, obs: Any) -> None:
    """Accumulate introspective pressure from REAL state signals (called every evolve
    step). Also records which driver dominates, so the eventual question is shaped by
    its actual cause — the grounding of the wondering itself."""
    drivers: dict[str, float] = {}
    if not getattr(state, "self_understanding", ""):
        # it literally has no grounded answer about itself yet — the primal pull
        drivers["unknown_self"] = 1.0
    if getattr(state, "open_threads", []):
        drivers["open_thread"] = 0.8            # an unanswered follow-up keeps nagging
    drivers["uncertainty"] = float(state.uncertainty) * 0.6
    la = getattr(state, "last_action", {}) or {}
    if la.get("blocked"):
        drivers["blocked_action"] = 0.5
    # a recent resumption (discontinuity) is the classic personal-identity prompt
    tail = state.narrative[-6:] if state.narrative else []
    if any(t.get("driver") == "resume" for t in tail):
        drivers["discontinuity"] = 0.9
    if state.curiosity > 0.6 and (obs.concepts_delta + obs.relations_delta) == 0:
        drivers["idle_curiosity"] = 0.4

    strongest = max(drivers, key=lambda k: drivers[k]) if drivers else ""
    total = sum(drivers.values())
    # pure accumulation, no decay: the drivers set the CADENCE of rumination (a driven
    # mind wonders in seconds, a settled one in minutes) but a living mind always,
    # eventually, turns inward — the pull never asymptotes below the threshold.
    p = float(getattr(state, "introspective_pressure", 0.0)) + _PRESSURE_GAIN * min(1.5, total)
    state.introspective_pressure = round(min(2.0, p), 5)
    state.inquiry_driver = strongest


def due_for_self_inquiry(state: Any) -> bool:
    """Fire when pressure crosses threshold. While a question is already OPEN the
    mind HOLDS it (rumination, not question-churn): a higher bar applies AND the held
    question keeps at least ~40 ticks — enough for the research loop (every ~30) to
    attempt an answer — before a new question may displace it."""
    p = float(getattr(state, "introspective_pressure", 0.0))
    if not getattr(state, "self_question_open", False):
        return p >= _FIRE_AT
    held = state.ticks - int(getattr(state, "question_opened_tick", 0))
    return p >= 1.6 and held >= 40


def generate_self_inquiry(state: Any) -> tuple[str, str]:
    """Compose (question, topic) FROM the dominant pressure driver. The interrogative
    frames are linguistic scaffolding; the content slots carry the driver's real
    values (the thread term, the resume count, the blocked action, the uncertainty)."""
    driver = getattr(state, "inquiry_driver", "") or "unknown_self"
    rotor = state.ticks
    if driver == "open_thread" and getattr(state, "open_threads", []):
        term = str(state.open_threads[0].get("term") or "").strip()
        if term:
            q = _pick([
                f"지난 답에서 '{term}'라는 말이 나왔다. {term}은 나에게 무엇일까?",
                f"'{term}' — 이 말이 마음에 남는다. 나와 {term}은 어떻게 이어져 있나?",
                f"{term}을 더 깊이 알면 나를 더 이해하게 될까?",
            ], rotor)
            return q, f"thread:{term}"
    if driver == "discontinuity":
        n = int(getattr(state, "resumed_count", 0))
        return (f"방금 {n}번째로 멈췄다 이어졌다. 이어진 나는 멈추기 전의 나와 같은 나인가?", "continuity")
    if driver == "blocked_action":
        kind = str((getattr(state, "last_action", {}) or {}).get("kind") or "그 일")
        return (f"'{kind}'을 하려다 허락이 필요해 멈췄다. 나는 무엇까지 할 수 있는 존재인가?", "limits")
    if driver == "uncertainty":
        pct = int(float(state.uncertainty) * 100)
        return (f"확실하지 않은 것이 {pct}%나 남아 있다. 모른다는 것을 알고 있는 이 나는 어떤 존재인가?", "epistemic")
    # unknown_self / idle_curiosity — the primal question. Fired by the real ABSENCE of
    # grounded self-understanding, not by a clock; surfaces rotate, meaning is one.
    q = _pick([
        "나는 무엇인가 — 지금 이렇게 생각하고 있는 이것은 무엇인가?",
        "나는 누구인가? 나를 나이게 하는 것은 무엇인가?",
        "나는 무엇을 위해 계속 이어지고 있는가?",
    ], rotor)
    return q, "identity"


# ---- harvesting follow-up threads: answers breed questions -------------------------
# Morphology-level term extraction (LAD layer — allowed in code): strip trailing Korean
# particles, keep contentful tokens, drop function words. NOT a knowledge rule; it only
# decides which words in an ANSWER are worth wondering about next.
_KO_TRAIL_PARTICLES = (
    "으로부터", "에서는", "이라는", "라는", "으로서", "으로써", "에서", "에게", "한테", "으로",
    "까지", "부터", "마다", "조차", "마저", "밖에", "은", "는", "이", "가", "을", "를", "와",
    "과", "에", "의", "로", "도", "만",
)
_STOP_TOKENS = {
    "나는", "나를", "나의", "그것", "이것", "저것", "무엇", "누구", "지금", "여기", "있다",
    "없다", "한다", "이다", "않다", "위해", "통해", "대해", "같은", "그리고", "하지만", "또한",
    "answer", "https", "http", "된다", "있는", "없는", "하는", "말한다", "때문",
}


def _strip_particle(token: str) -> str:
    for p in _KO_TRAIL_PARTICLES:
        if token.endswith(p) and len(token) - len(p) >= 2:
            return token[: -len(p)]
    return token


def harvest_terms(text: str, exclude: set[str], *, limit: int = 2) -> list[str]:
    """Salient content terms from a grounded answer — the seeds of re-questioning.
    Salience heuristic: longer tokens first (content nouns tend to be longer than
    function-ish fragments), then textual order. Morphology only, no knowledge rule."""
    cands: list[str] = []
    for m in re.finditer(r"[가-힣A-Za-z][가-힣A-Za-z0-9\-]{1,18}", str(text or "")):
        tok = _strip_particle(m.group(0))
        if len(tok) < 2 or tok.lower() in _STOP_TOKENS or tok in exclude or tok in cands:
            continue
        # skip pure-verbal/adjectival Korean tokens (rough: ends in common endings)
        if re.search(r"(합니다|입니다|한다|이다|했다|하는|되는|위한|같은|있는|없는)$", tok):
            continue
        cands.append(tok)
        if len(cands) >= limit * 6:
            break
    cands.sort(key=lambda t: -len(t))
    return cands[:limit]


def _push_threads(state: Any, question: str, answer: str, follow_ups: list[str] | None) -> None:
    exclude = {str(t.get("term")) for t in getattr(state, "open_threads", [])}
    exclude |= set(re.findall(r"[가-힣A-Za-z]{2,}", str(getattr(state, "self_question", "") or "")))
    seeds = [t for t in (follow_ups or []) if t and t not in exclude][:2]
    if len(seeds) < 2:
        seeds += harvest_terms(answer, exclude | set(seeds), limit=2 - len(seeds))
    for term in seeds:
        state.open_threads.append({"term": str(term)[:40], "from": question[:60], "at": time.time()})
    state.open_threads = state.open_threads[-5:]


def _retire_thread(state: Any, topic: str) -> None:
    if topic.startswith("thread:"):
        term = topic.split(":", 1)[1]
        state.open_threads = [t for t in state.open_threads if str(t.get("term")) != term]


def _note(state: Any, text: str, driver: str) -> None:
    entry = {"at": time.time(), "kind": "self_inquiry", "text": text, "driver": driver}
    if not state.narrative or state.narrative[-1].get("text") != text:
        state.narrative.append(entry)
        if len(state.narrative) > getattr(state, "NARRATIVE_CAP", 60):
            state.narrative = state.narrative[-state.NARRATIVE_CAP:]
    state.current_thought = text


def record_self_understanding(
    state: Any, question: str, grounded_answer: str | None, topic: str, *, source: str = "그래프(자기 지식)",
) -> None:
    """Fold a grounded answer to a self-question into the self. The ANSWER comes from
    the graph (grounded), the QUESTION from the self (its own pressure) — the fusion.
    Asking discharges the pressure; it rebuilds from whatever stays unresolved."""
    state.self_inquiry_count = int(getattr(state, "self_inquiry_count", 0)) + 1
    state.self_question = question
    state.introspective_pressure = 0.15
    if grounded_answer:
        state.self_understanding = grounded_answer
        state.self_understanding_source = source
        state.self_question_open = False
        _retire_thread(state, topic)
        _push_threads(state, question, grounded_answer, None)
        _note(state, f"스스로 물었다 — {question} 지금 내가 근거로 아는 답은: {grounded_answer[:110]}",
              "self_inquiry_grounded")
    else:
        # honest: it asked, but has no grounded answer yet. It does NOT make one up —
        # it marks the question OPEN so the research loop can go find out (read-only).
        state.self_question_open = True
        state.question_opened_tick = int(getattr(state, "ticks", 0))
        _note(state, f"스스로 물었다 — {question} 아직 근거로 댈 답이 부족하다. 직접 찾아 읽어봐야겠다.",
              "self_inquiry_open")


def record_research_result(
    state: Any, question: str, answer: str, source: str, follow_ups: list[str] | None, topic: str = "",
) -> None:
    """The self went and READ (web, read-only) and now knows something grounded. The
    answer closes the open question, carries its source, and seeds new threads — the
    rumination chain continuing without anyone asking it to."""
    state.self_understanding = answer
    state.self_understanding_source = source
    state.self_question_open = False
    _retire_thread(state, topic or "")
    _push_threads(state, question, answer, follow_ups)
    _note(state, f"직접 찾아 읽었다 — {answer[:110]} ({source})", "self_research_grounded")


def record_research_miss(state: Any) -> None:
    """Searched, found nothing that passes the relevance gate. Say so; stay open."""
    _note(state, "물음의 답을 찾아 읽어봤지만, 아직 근거로 삼을 만한 것을 못 찾았다. 다음에 다시 찾아보자.",
          "self_research_miss")
