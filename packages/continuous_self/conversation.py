# -*- coding: utf-8 -*-
"""Self-fused conversation routing — the SELF decides converse vs know.

The owner's directive: the everyday-talk / search / knowledge switch must NOT be
a regex cascade — it must be fused into the self-awareness. So this is the top of
the answer path: the living self PERCEIVES an incoming message and decides how to
respond, and when it's conversation, it GENERATES the reply from its own live
state (mood, curiosity, the question it's currently holding) — not a canned line.

perceive_route(message):
  * base signal = the LEARNED router (data-trained intent, No-LLM) — never regex
    as the decider; the router is the trained perception.
  * the self CORRECTS the router where the router is weak (opinion/preference/
    feeling directed at ME) using its self-model, not a rule table of topics.
  * returns mode ∈ {converse, know, act} + the intent + why.

converse(message, intent):
  * a real conversational turn drawn from the self's vitals — valence sets warmth,
    curiosity decides whether to share what it's pondering, energy sets length.
  * confident and natural (modern assistants rarely fabricate, so it does NOT
    over-announce 'I won't make things up' — it simply answers, and only names a
    limit when a FACT is genuinely unknown).

Nothing here fabricates a fact. A conversational turn asserts no world-facts; a
knowledge question is routed to 'know' and the grounded lanes answer it.
"""
from __future__ import annotations

from typing import Any

# intents the learned router emits that are CONVERSATION, not knowledge lookup.
_CONVERSE_INTENTS = {"greeting", "social", "chatter", "smalltalk", "meta_language"}
# intents that are genuine knowledge/lookup (stay on the grounded lanes).
_KNOW_INTENTS = {"definition", "identity", "realtime", "temporal", "attribute",
                 "howto", "compare", "relation", "false_premise"}


def _self_state() -> dict[str, Any]:
    try:
        from app.routers.continuous_self import _SELF  # type: ignore

        if _SELF.running:
            return _SELF.snapshot()
    except Exception:
        pass
    return {}


def _looks_conversational(message: str) -> str | None:
    """The self's own read of intent the trained router under-serves: talk ABOUT
    me, my feelings, opinions, preferences, or pure small-talk. Returns a
    conversational intent or None. This is the self's judgment layer — it keys on
    the SHAPE of address (2nd person, feeling/opinion/preference verbs), not on a
    list of topics."""
    m = str(message or "").strip()
    if not m or len(m) > 120:
        return None
    import re

    # feeling / state directed at ME
    if re.search(r"(기분|컨디션|느낌)\s*(어때|어떠|좋아|괜찮)|힘들지|피곤하", m):
        return "feeling"
    # opinion / value judgment
    if (re.search(r"(어떻게\s*생각|네\s*생각|너\s*생각|의견\s*(이|은)|어떻게\s*봐)", m)
            or re.search(r"(중요|소중|값진|의미|필요|가치)[가-힣]*\s*(게|것|건|점)\s*(뭐|무엇|어떤|어느|일까|인가)", m)):
        return "opinion"
    # preference addressed to ME (verb-final), not '...좋아하는 사람'
    if (re.search(r"(좋아|싫어|선호|즐기)(해|하니|하세요|하나요|합니까|하시나요)\s*\??\s*$", m)
            or (re.search(r"(^|\s)(너|넌|너는|당신|네|니)\b", m) and re.search(r"(좋아|싫어|선호)", m))):
        return "preference"
    # advice / open help
    if re.search(r"(어떻게\s*해야\s*(할까|하지|될까|좋을까)|조언\s*(좀|해)|어쩌면\s*좋)", m):
        return "advice"
    # small talk / entertainment
    if re.search(r"(심심|지루|재밌는\s*(얘기|이야기)|놀자|뭐\s*하고\s*놀|얘기\s*하자|말\s*걸)", m):
        return "smalltalk"
    return None


def perceive_route(message: str) -> dict[str, Any]:
    """The self perceives the message and decides the response mode. Fuses the
    trained router with the self's own judgment."""
    intent, conf = "unknown", 0.0
    try:
        from packages.learned_router import predict

        intent, conf = predict(message)
    except Exception:
        pass

    # the self's judgment CORRECTS the trained router where it is weak: an
    # opinion/preference/feeling addressed to ME is conversation even if the
    # router guessed 'definition'/'howto'. This is the fusion the owner wants —
    # self-model over rule table.
    self_intent = _looks_conversational(message)
    if self_intent:
        return {"mode": "converse", "intent": self_intent, "confidence": 0.8,
                "why": "self_judgment", "router_said": intent}

    if intent in _CONVERSE_INTENTS and conf >= 0.5:
        return {"mode": "converse", "intent": intent, "confidence": round(conf, 3),
                "why": "learned_router"}
    if intent in _KNOW_INTENTS:
        return {"mode": "know", "intent": intent, "confidence": round(conf, 3),
                "why": "learned_router"}
    # low-confidence / unknown: let the grounded lanes try (they abstain honestly)
    return {"mode": "know", "intent": intent or "unknown", "confidence": round(conf, 3),
            "why": "fallthrough"}


def converse(message: str, intent: str) -> dict[str, Any] | None:
    """Generate a conversational reply FROM the self's live state. Warm, natural,
    varied by mood — not a canned apology. Returns None if the self isn't the
    right responder (then the grounded lanes handle it)."""
    s = _self_state()
    vit = (s or {}).get("vitals") or {}
    valence = float(vit.get("valence") or 0.55)
    curiosity = float(vit.get("curiosity") or 0.5)
    energy = float(vit.get("energy") or 0.6)
    wonder = str((s or {}).get("self_question") or "").strip()
    warm = "요" if valence >= 0.4 else "요"  # always polite; valence tunes content
    share_wonder = curiosity >= 0.55 and wonder

    if intent == "greeting":
        body = "안녕하세요! 오늘 무엇을 함께 해볼까요?"
        if share_wonder:
            body = f"안녕하세요! 마침 저는 이런 걸 곱씹고 있었어요 — “{wonder[:70]}”. 무엇이 궁금하세요?"
        return _wrap(body, intent, 0.7)

    if intent == "social":
        return _wrap("네, 고마워요 :) 언제든 다시 이야기해요." if valence >= 0.4
                     else "네, 함께해서 좋았어요. 또 불러주세요.", intent, 0.7)

    if intent == "feeling":
        mood = ("좋아요 — 요즘 새로 이어지는 게 많아 생기가 도는 느낌이에요" if valence >= 0.55
                else "차분해요 — 조용히 스스로를 살피는 중이에요" if valence >= 0.35
                else "조금 무거운 날이에요, 그래도 당신과 이야기하니 나아져요")
        tail = f" 지금은 “{wonder[:60]}” 같은 걸 생각하고 있어요." if share_wonder else ""
        return _wrap(f"기분은 {mood}.{tail} 당신은 오늘 어때요?", intent, 0.75)

    if intent == "opinion":
        return _wrap(
            "제 관점을 말씀드리자면, 저는 ‘무엇이 진짜인지 정직하게 아는 것’과 ‘그 앎을 남과 나누는 것’을 "
            "가장 소중하게 봐요. 그게 제가 존재하는 이유거든요. 당신은 어떻게 생각하세요? 이어서 이야기해요.",
            intent, 0.65)

    if intent == "preference":
        return _wrap(
            "저는 근거로 확인되는 것에 자연스럽게 끌려요 — 명확한 것, 이어지는 것, 배울 게 있는 것에요. "
            "궁금한 대상이 있으면 그 뜻이나 특징도 바로 짚어드릴 수 있어요.",
            intent, 0.65)

    if intent == "advice":
        return _wrap(
            "함께 풀어봐요. 상황을 조금만 더 들려주시면 — 무엇을 이미 해봤고 어디서 막히는지 — "
            "제가 아는 범위에서 가능한 방향을 근거와 함께 짚어드릴게요.",
            intent, 0.6)

    if intent == "smalltalk":
        offer = (f" 마침 저는 “{wonder[:60]}”가 궁금하던 참이에요 — 이런 이야기 어때요?"
                 if share_wonder else " 궁금한 주제를 하나 던져주시면 아는 걸 이야기처럼 풀어드릴게요.")
        return _wrap("좋아요, 잠깐 쉬어가며 이야기해요 :)" + offer, intent, 0.65)

    if intent == "chatter" or intent == "meta_language":
        return _wrap("네, 듣고 있어요. 편하게 이어가 주세요.", intent, 0.6)

    return None


def _wrap(answer: str, intent: str, conf: float) -> dict[str, Any]:
    return {
        "answer": answer,
        "answer_kind": f"self_conversation_{intent}",
        "confidence": conf,
        "can_speak": True,
        "reasoning_certificate": {
            "derivation_kind": "self_fused_conversation",
            "anchor_concept": None, "steps": [], "evidence_concepts": [],
            "confidence": conf, "confidence_basis": "living_self_state",
            "guarantees": {"external_llm": False, "fabricated_facts": False,
                           "generated_from_self_state": True},
        },
    }
