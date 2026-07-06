# -*- coding: utf-8 -*-
"""Grounded Composer v1 — graph-native multi-fact utterance generation (roadmap P2).

The single-fact bridge answers "X는 Y입니다." — one template, one triple. Language-model
COMPLETION means composing several stored facts into one fluent paragraph. This module
does that with the GCG 뼈+살 contract:

  뼈 (bones)  = the facts, verbatim: every content span in the output is the exact
                subject/object string of a stored triple.
  살 (flesh)  = a deterministic discourse plan (identification -> elaboration) plus a
                closed connective whitelist (또한/그리고/한편) and the LAD particle layer.

HALLUCINATION-SAFE BY CONSTRUCTION: the output vocabulary is exactly
{template constants} ∪ {connective whitelist} ∪ {verbatim fact strings}. There is no
free-text generation step that COULD invent content — the safety property is testable
as token containment, and the test suite asserts it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# identification first, then elaboration — the standard definitional discourse schema.
_PRED_ORDER = ("defined_as", "is_a", "capital", "capital_of", "located_in", "country", "author")
# closed connective whitelist (the ONLY non-template, non-fact tokens allowed)
_CONNECTIVES = ("또한", "그리고", "한편")
# subject-dropped continuation frames: Korean elaboration reads naturally without
# repeating the topic ("커피는 …입니다. 또한 …의 일종입니다.")
_KO_CONT: dict[str, str] = {
    "defined_as": "{o}이기도 합니다",
    "is_a": "{o}의 일종입니다",
    "capital": "수도는 {o}입니다",
    "capital_of": "{o}의 수도입니다",
    "located_in": "{o}에 위치합니다",
    "country": "나라는 {o}입니다",
    "author": "저자는 {o}입니다",
}
_KO_LEAD: dict[str, str] = {
    "defined_as": "{s_topic} {o}입니다",
    "is_a": "{s_topic} {o}의 일종입니다",
    "capital": "{s}의 수도는 {o}입니다",
    "capital_of": "{s_topic} {o}의 수도입니다",
    "located_in": "{s_topic} {o}에 위치합니다",
    "country": "{s}의 나라는 {o}입니다",
    "author": "{s}의 저자는 {o}입니다",
}


# English realizer — SAME GCG contract (뼈+살): every content span is a verbatim
# fact string; the only added tokens are these frames and connectives. No article
# guessing on the object (that would be invented content) — the stored label stands.
# English can't drop the subject like Korean, so continuations carry their own
# "It ..." — the connective is prepended separately.
_EN_CONNECTIVES = ("Additionally,", "Additionally,", "Additionally,")
_EN_LEAD: dict[str, str] = {
    "defined_as": "{s} is {o}",
    "is_a": "{s} is a kind of {o}",
    "capital": "The capital of {s} is {o}",
    "capital_of": "{s} is the capital of {o}",
    "located_in": "{s} is located in {o}",
    "country": "{s} is in {o}",
    "author": "{s} was written by {o}",
}
_EN_CONT: dict[str, str] = {
    "defined_as": "it is also {o}",
    "is_a": "it is a kind of {o}",
    "located_in": "it is located in {o}",
    "capital": "its capital is {o}",
    "country": "it is in {o}",
    "author": "it was written by {o}",
}


@dataclass
class ComposedAnswer:
    answer: str
    facts_used: list[tuple[str, str, str]] = field(default_factory=list)
    connectives_used: list[str] = field(default_factory=list)

    def certificate(self) -> dict[str, Any]:
        return {
            "derivation_kind": "grounded_composition",
            "anchor_concept": {"label": self.facts_used[0][0] if self.facts_used else ""},
            "steps": [{"type": "triple", "fact": f"{s} {p} {o}"} for s, p, o in self.facts_used],
            "evidence_concepts": sorted({t for s, _p, o in self.facts_used for t in (s, o)}),
            "confidence": 0.88,
            "confidence_basis": "curated_structured_triples_verbatim_composition",
            "guarantees": {"external_llm": False, "fabricated_facts": False, "inferred": False,
                           "composition_vocabulary_closed": True},
        }


def _ko_topic_particle(label: str) -> str:
    from packages.lad_morphology import topic

    return topic(label)[len(label):]


def compose_from_facts(subject: str, facts: list[tuple[str, str, str]],
                       language: str = "ko", max_facts: int = 4) -> ComposedAnswer | None:
    """Compose a fluent multi-fact answer. Returns None when fewer than TWO usable
    facts exist — single-fact answers stay on the precise single-template path."""
    if language not in ("ko", "en"):
        return None
    lead = _KO_LEAD if language == "ko" else _EN_LEAD
    cont = _KO_CONT if language == "ko" else _EN_CONT
    conns = _CONNECTIVES if language == "ko" else _EN_CONNECTIVES
    source = " (출처: 큐레이션 지식그래프)" if language == "ko" else " (source: curated knowledge graph)"
    # one fact per predicate, discourse-ordered, alias/sense excluded (they have their
    # own dedicated answer paths: substitution hop and enumeration).
    by_pred: dict[str, tuple[str, str, str]] = {}
    for s, p, o in facts:
        if p in ("alias", "sense"):
            continue
        if p not in by_pred:
            by_pred[p] = (s, p, o)
    ordered = [by_pred[p] for p in _PRED_ORDER if p in by_pred]
    ordered += [f for p, f in by_pred.items() if p not in _PRED_ORDER]
    ordered = ordered[:max_facts]
    if len(ordered) < 2:
        return None

    sentences: list[str] = []
    connectives: list[str] = []
    used: list[tuple[str, str, str]] = []
    for s, p, o in ordered:
        if not sentences:
            frame = lead.get(p)
            if frame is None:  # unknown lead predicate: never improvise a frame
                continue
            topic = s + _ko_topic_particle(s) if language == "ko" else s
            sentences.append(frame.format(s=s, o=o, s_topic=topic) + ".")
            used.append((s, p, o))
        else:
            frame = cont.get(p)
            if frame is None:  # unknown predicate: keep it out rather than improvise
                continue
            conn = conns[min(len(connectives), len(conns) - 1)]
            connectives.append(conn)
            sentences.append(f"{conn} {frame.format(o=o)}.")
            used.append((s, p, o))
    if len(sentences) < 2:
        return None
    answer = " ".join(sentences) + source
    return ComposedAnswer(answer=answer, facts_used=used, connectives_used=connectives)
