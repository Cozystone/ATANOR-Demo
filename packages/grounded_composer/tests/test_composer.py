# -*- coding: utf-8 -*-
"""GCG 뼈+살 contract: identification-first ordering, closed connective whitelist,
and the hallucination-safety property — output vocabulary ⊆ templates ∪ connectives
∪ verbatim fact strings, asserted as token containment."""
from __future__ import annotations

import re

from packages.grounded_composer import compose_from_facts
from packages.grounded_composer.composer import _CONNECTIVES, _KO_CONT, _KO_LEAD

FACTS = [
    ("커피", "is_a", "음료"),
    ("커피", "defined_as", "커피나무 열매의 씨앗을 볶아 우려낸 음료"),
    ("커피", "located_in", "전 세계"),
]


def test_identification_comes_first_then_elaboration():
    r = compose_from_facts("커피", FACTS)
    assert r is not None
    # defined_as leads even though is_a arrived first in the list
    assert r.answer.startswith("커피는 커피나무 열매의 씨앗을 볶아 우려낸 음료입니다.")
    assert r.facts_used[0][1] == "defined_as"
    # the connective is chosen by the LEARNED discourse model within the closed
    # whitelist — assert the elaboration content, not one pinned connective
    assert "전 세계에 위치합니다." in r.answer
    assert any(f"{c} 전 세계에 위치합니다." in r.answer for c in _CONNECTIVES)


def test_redundant_elaboration_is_dropped():
    # '…음료입니다. 또한 음료의 일종입니다' reads broken — the is_a object already
    # appears as the head of the defined_as object, so the gate drops it.
    r = compose_from_facts("커피", FACTS)
    assert r is not None
    assert "또한 음료의 일종입니다." not in r.answer
    assert all(p != "is_a" for _s, p, _o in r.facts_used)


def test_single_fact_defers_to_single_template_path():
    assert compose_from_facts("커피", [("커피", "is_a", "음료")]) is None


def test_alias_and_sense_never_enter_composition():
    facts = [("비저", "sense", "마비저"), ("비저", "alias", "마비저"),
             ("비저", "is_a", "병명"), ("비저", "defined_as", "전염병의 하나")]
    r = compose_from_facts("비저", facts)
    assert r is not None
    assert "마비저" not in r.answer


def test_hallucination_safety_vocabulary_is_closed():
    r = compose_from_facts("커피", FACTS)
    assert r is not None
    body = r.answer.replace(" (출처: 큐레이션 지식그래프)", "")
    # remove template constants FIRST (longest chunks), then fact strings longest-first —
    # removing a short subject early can shear a longer object ('커피' inside '커피나무…')
    chunks = []
    for frame in list(_KO_LEAD.values()) + list(_KO_CONT.values()):
        chunks += [c for c in re.split(r"\{[so](?:_topic)?\}", frame) if c.strip()]
    for c in sorted(set(chunks), key=len, reverse=True):
        body = body.replace(c, "")
    for term in sorted({t for s, _p, o in r.facts_used for t in (s, o)}, key=len, reverse=True):
        body = body.replace(term, "")
    for c in _CONNECTIVES:
        body = body.replace(c, "")
    # what remains may only be particles/punctuation/whitespace — no free content
    leftover = re.sub(r"[\s\.\,]", "", body)
    assert len(leftover) <= 4, f"unexpected free content: {leftover!r}"


def test_unknown_predicate_is_dropped_not_improvised():
    # located_in (not redundant with the definition) keeps two realizable facts
    # alive, so the weird predicate's exclusion is observable in a real answer.
    facts = [("커피", "defined_as", "볶은 씨앗 음료"), ("커피", "weird_pred", "이상한 값"),
             ("커피", "located_in", "전 세계")]
    r = compose_from_facts("커피", facts)
    assert r is not None
    assert "이상한 값" not in r.answer and "weird_pred" not in r.answer


def test_narrative_builds_multi_paragraph_arc():
    from packages.grounded_composer.composer import compose_narrative

    facts = [("테슬라", "defined_as", "미국의 전기자동차 제조사"),
             ("테슬라", "상위개념", "나스닥 100"),
             ("테슬라", "설립자", "마틴 에버하드"),
             ("테슬라", "설립", "2003년 7월 1일")]
    n = compose_narrative("테슬라", facts)
    assert n is not None
    paras = n.answer.split("\n\n")
    assert len(paras) >= 3                      # 기 / 승 / 결
    assert paras[-1].startswith("즉,")           # closing reuses identity verbatim
    assert "미국의 전기자동차 제조사" in paras[-1]
    assert "마틴 에버하드가 세웠습니다" in n.answer  # josa resolved


def test_narrative_abstains_below_two_groups():
    from packages.grounded_composer.composer import compose_narrative

    facts = [("커피", "defined_as", "볶은 씨앗 음료"), ("커피", "is_a", "음료")]
    assert compose_narrative("커피", facts) is None  # one group only -> no padding
