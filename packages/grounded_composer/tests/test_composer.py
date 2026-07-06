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
    assert "또한 음료의 일종입니다." in r.answer


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
    facts = [("커피", "defined_as", "볶은 씨앗 음료"), ("커피", "weird_pred", "이상한 값"),
             ("커피", "is_a", "음료")]
    r = compose_from_facts("커피", facts)
    assert r is not None
    assert "이상한 값" not in r.answer and "weird_pred" not in r.answer
