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
# contrast/commonality connectives for the comparison schema — same closed-vocabulary rule
_CONTRAST_CONNECTIVES = ("반면", "둘 다")
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
    # redundancy gate: '…위치하고 있는 도시입니다. 또한 도시의 일종입니다' reads broken —
    # drop a fact whose object already appears verbatim inside an earlier fact's object
    deduped: list[tuple[str, str, str]] = []
    for f in ordered:
        if any(f[2] and f[2] in prev[2] for prev in deduped):
            continue
        deduped.append(f)
    ordered = deduped[:max_facts]
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


def _pick_lead(facts: list[tuple[str, str, str]],
               avoid: tuple[str, str, str] | None = None) -> tuple[str, str, str] | None:
    """Highest-priority identifying fact for a subject, preferring one that DIFFERS
    from `avoid` (so a contrast never contrasts a thing with itself)."""
    by_pred: dict[str, tuple[str, str, str]] = {}
    for s, p, o in facts:
        if p not in ("alias", "sense") and p not in by_pred:
            by_pred[p] = (s, p, o)
    ordered = [by_pred[p] for p in _PRED_ORDER if p in by_pred]
    ordered += [f for p, f in by_pred.items() if p not in _PRED_ORDER]
    for f in ordered:
        if avoid is None or (f[1], f[2]) != (avoid[1], avoid[2]):
            return f
    return ordered[0] if ordered else None


def compose_comparison(a: str, b: str,
                       facts_a: list[tuple[str, str, str]],
                       facts_b: list[tuple[str, str, str]],
                       common: tuple[str, list[tuple[str, str, str]],
                                     list[tuple[str, str, str]]] | None = None,
                       language: str = "ko") -> ComposedAnswer | None:
    """Contrast schema (개방형 B1): identify A, contrast B (반면), then the grounded
    commonality (둘 다 <shared ancestor>) when the taxonomy ladders meet. Same GCG
    closure: every content span is a verbatim stored label."""
    if language != "ko":
        return None  # EN parity is a separate lane; never improvise frames
    fa0 = _pick_lead(facts_a)
    fb0 = _pick_lead(facts_b, avoid=fa0)
    if fa0 is None or fb0 is None:
        return None
    lead_a = _KO_LEAD.get(fa0[1])
    lead_b = _KO_LEAD.get(fb0[1])
    if lead_a is None or lead_b is None:
        return None

    sentences = [
        lead_a.format(s=a, o=fa0[2], s_topic=a + _ko_topic_particle(a)) + ".",
        "반면 " + lead_b.format(s=b, o=fb0[2], s_topic=b + _ko_topic_particle(b)) + ".",
    ]
    used = [fa0, fb0]
    connectives = ["반면"]
    if common is not None:
        anc, chain_a, chain_b = common
        sentences.append(f"둘 다 {anc}의 일종이라는 공통점이 있습니다.")
        connectives.append("둘 다")
        used.extend(chain_a)
        used.extend(chain_b)
    answer = " ".join(sentences) + " (출처: 큐레이션 지식그래프)"
    composed = ComposedAnswer(answer=answer, facts_used=used, connectives_used=connectives)
    return composed


# purpose/ability schema (개방형 B2): what a thing is FOR and what it CAN do —
# direct used_for/capable_of/has_part facts plus the ones the taxonomy ladder
# passes down (inherited via packages.graph_scale.chain_reasoner.inherited_facts).
_KO_PURPOSE_LEAD: dict[str, str] = {
    "used_for": "{s_topic} {o}에 쓰입니다",
    "capable_of": "{s_topic} '{o}'{i_ga} 가능합니다",
    "has_part": "{s}에는 {o}{i_ga} 있습니다",
}
_KO_PURPOSE_CONT: dict[str, str] = {
    "used_for": "{o}에도 쓰입니다",
    "capable_of": "'{o}'{i_ga} 가능합니다",
    "has_part": "{o}{i_ga} 있습니다",
}


def _ko_subject_particle(label: str) -> str:
    from packages.lad_morphology import subject

    return subject(label)[len(label):]


def compose_purpose(subject: str,
                    direct: list[tuple[str, str, str]],
                    inherited: list[tuple[list[tuple[str, str, str]], tuple[str, str, str]]] = (),
                    language: str = "ko", max_facts: int = 4) -> ComposedAnswer | None:
    """Purpose paragraph over stored used_for/capable_of/has_part facts. Direct facts
    lead; inherited ones follow WITH their taxonomy source named (X의 일종으로서) so
    the inference is visible, never smuggled."""
    if language != "ko":
        return None
    own = [(s, p, o) for s, p, o in direct if p in _KO_PURPOSE_LEAD]
    seen_po = {(p, o) for _s, p, o in own}
    inh = [(chain, edge) for chain, edge in inherited
           if chain and edge[1] in _KO_PURPOSE_LEAD and (edge[1], edge[2]) not in seen_po]
    if not own and not inh:
        return None

    sentences: list[str] = []
    connectives: list[str] = []
    used: list[tuple[str, str, str]] = []
    for s, p, o in own[:max_facts]:
        frame = _KO_PURPOSE_LEAD[p] if not sentences else _KO_PURPOSE_CONT[p]
        prefix = "" if not sentences else "또한 "
        if prefix:
            connectives.append("또한")
        sentences.append(prefix + frame.format(
            s=subject, o=o, s_topic=subject + _ko_topic_particle(subject),
            i_ga=_ko_subject_particle(o)) + ".")
        used.append((s, p, o))
    for chain, (s, p, o) in inh[: max(0, max_facts - len(sentences))]:
        kind = chain[-1][2]  # the ancestor the property actually comes from
        frame = _KO_PURPOSE_CONT[p]
        prefix = "" if not sentences else "또한 "
        if prefix:
            connectives.append("또한")
        sentences.append(
            prefix + f"{kind}의 일종으로서 " + frame.format(
                s=subject, o=o, s_topic=subject + _ko_topic_particle(subject),
                i_ga=_ko_subject_particle(o)) + ".")
        used.extend(chain)
        used.append((s, p, o))
    if not sentences:
        return None
    # a lone continuation frame has no subject — re-lead it
    if len(used) >= 1 and not own and sentences:
        first_chain, first_edge = inh[0]
        s0, p0, o0 = first_edge
        sentences[0] = f"{subject + _ko_topic_particle(subject)} {first_chain[-1][2]}의 일종으로서 " + \
            _KO_PURPOSE_CONT[p0].format(o=o0, i_ga=_ko_subject_particle(o0)) + "."
    answer = " ".join(sentences) + " (출처: 큐레이션 지식그래프)"
    return ComposedAnswer(answer=answer, facts_used=used, connectives_used=connectives)
