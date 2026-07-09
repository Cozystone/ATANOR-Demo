# -*- coding: utf-8 -*-
"""Engagement cascade — structurally eliminate the DEAD-END abstention.

Owner directive (2026-07-09): when a user asks an AI expecting an answer and
gets a bare '모르겠는데요', it's a letdown. Make that structurally impossible.

The distinction that keeps this honest (BINDING — see the honesty memory): we
never fabricate a fact to fill the gap. We eliminate the DEAD-END, not the
truthfulness. Every hard-miss is instead turned into a SUBSTANTIVE, forward-
moving engagement built only from what the graph really holds:

  1. nearest VERIFIED concept (soft_resolve) — 'no direct fact, but the closest
     verified concept in the graph is X (shared type …), and X is …';
  2. RELATED facts around the best subject — offer what we DO know near it;
  3. shape-aware conversational engagement for genuinely open questions;
  4. always a forward cue (it will verify on the live web / learn this) —
     never a shrug.

So the answer is honest (grounded=False, engaged=True, fabricated_facts=False)
but never a wall. This is the omni-engage law applied to the FACTUAL-miss path,
reusing the existing soft-context and shape-engage pieces rather than new ones."""
from __future__ import annotations

import re
from typing import Any, Callable


_ADVERBS = re.compile(r"^(자세히|자세하게|정확히|간단히|쉽게|빨리|자세|간략히|대략)$")


def _best_subject(query: str) -> str:
    # 'X에 대해/에 관해/란' — the TOPIC is what precedes it, not a trailing adverb
    # ('서울특별시에 대해 자세히' -> 서울특별시, measured). Checked before the
    # frame parser, which mis-picked the adverb.
    m = re.search(r"([가-힣A-Za-z0-9]{2,})\s*(?:에 대해|에 관해|에 대하여|에 관하여|란|이란)", query)
    if m:
        return m.group(1)
    try:
        from .query_frame import parse as _parse
        s = _parse(query).subject
        if s and not _ADVERBS.match(s):
            return s
    except Exception:
        pass
    # fallback: longest Korean/alnum token, particle-stripped, no adverbs/wh-words
    toks = re.findall(r"[가-힣A-Za-z0-9]{2,}", query)
    toks = [re.sub(r"(은|는|이|가|을|를|의|란|이란|에|에서)$", "", t) for t in toks]
    toks = [t for t in toks if t and not _ADVERBS.match(t)
            and not re.match(r"^(뭐|무엇|누구|어디|언제|왜|어떻게|알려|설명|신비|힘)", t)]
    return max(toks, key=len) if toks else query.strip()


def _related_facts_line(store: Any, subject: str, language: str) -> str | None:
    """What the graph really knows AROUND the subject — never invented."""
    try:
        rows = store.facts_about(subject, limit=12) or []
    except Exception:
        return None
    seen: list[str] = []
    for s, p, o in rows:
        if p in ("alias", "sense") or not o:
            continue
        # keep human-meaningful predicates, skip raw type-batch noise
        rel = {"is_a": "종류", "defined_as": "정의", "capital": "수도",
               "located_in": "위치", "인구": "인구", "면적": "면적",
               "part_of": "구성"}.get(p, p)
        frag = f"{rel}: {o}" if language == "ko" else f"{p}: {o}"
        if frag not in seen and len(str(o)) < 60:
            seen.append(frag)
        if len(seen) >= 3:
            break
    if not seen:
        return None
    if language == "ko":
        return f"직접적인 답은 아직 없지만, ‘{subject}’에 대해 그래프가 아는 것은 — " + " · ".join(seen) + " — 입니다."
    return f"No direct fact yet, but here's what the graph holds about '{subject}': " + " · ".join(seen) + "."


def engage(query: str, language: str = "ko", *, store: Any = None) -> dict[str, Any] | None:
    """Build a substantive, honest, non-dead-end response for a hard-miss query.
    Returns an answer dict (grounded=False, engaged=True) or None only if the
    engine is truly empty. NEVER fabricates a fact."""
    subject = _best_subject(query)
    parts: list[str] = []
    used_soft = None

    if store is not None:
        # 1) related facts around the subject (highest value when present)
        rl = _related_facts_line(store, subject, language)
        if rl:
            parts.append(rl)
        # 2) nearest verified concept (soft, explicitly framed AS a neighbor)
        try:
            from .soft_resolve import soft_context_line
            sc = soft_context_line(store, subject, language)
            if sc and sc.get("text"):
                parts.append(sc["text"])
                used_soft = sc.get("neighbor")
        except Exception:
            pass

    # 3) shape-aware conversational engagement (opinion/advice/open questions)
    try:
        from packages.base_brain.zero_user_answer import _question_shape, _shape_engage
        shp = _question_shape(query)
        if shp and shp != "factual":
            se = _shape_engage(shp, language)
            if se:
                parts.append(se)
    except Exception:
        pass

    # 4) forward cue — the engine keeps going, it doesn't stop at 'I don't know'
    if language == "ko":
        cue = (f"‘{subject}’은(는) 지금 실시간 웹으로 교차 확인해 이어서 답하고, 배운 것은 그래프에 남깁니다."
               if not parts else
               "더 궁금하시면 실시간 웹 검증으로 더 깊이 파고들 수 있어요.")
    else:
        cue = (f"I'll verify '{subject}' on the live web and continue, keeping what I learn in the graph."
               if not parts else "Ask me to dig deeper and I'll verify it live on the web.")
    parts.append(cue)

    text = " ".join(parts).strip()
    if not text:
        return None
    return {
        "answer": text,
        "reasoning_certificate": {
            "derivation_kind": "engagement_no_dead_end",
            "anchor_concept": {"label": subject},
            "steps": [{"type": "engagement", "fact": p} for p in parts],
            "evidence_concepts": [subject] + ([used_soft] if used_soft else []),
            "confidence": 0.3,
            "confidence_basis": "no direct grounded fact — engaged with nearest "
                                "verified context and a live-web path; nothing fabricated",
            "guarantees": {"external_llm": False, "fabricated_facts": False,
                           "inferred": False, "engaged": True},
        },
        "confidence": 0.3,
        "answer_kind": "engagement_no_dead_end",
        "grounded": False,
        "engaged": True,
    }
