# -*- coding: utf-8 -*-
"""Query semantic frame — one structural parse fixes the wrong-subject + misroute classes."""

from __future__ import annotations

from packages.graph_scale.query_frame import parse


def test_genitive_relation_makes_X_the_subject():
    # THE systemic fix: '물의 화학식' -> subject 물, relation 화학식 (not 화학식 as subject)
    f = parse("물의 화학식은?")
    assert f.subject == "물" and f.relation == "화학식" and f.answer_type == "relation"
    f2 = parse("일본의 수도는?")
    assert f2.subject == "일본" and f2.relation == "capital"
    f3 = parse("해리포터의 저자는?")
    assert f3.subject == "해리포터" and f3.relation == "author"


def test_procedure_is_not_a_definition():
    f = parse("피자 맛있게 만드는 법")
    assert f.answer_type == "procedure" and f.subject == "피자"


def test_opinion_and_preference_are_conversational():
    assert parse("사랑이 뭐라고 생각해?").answer_type == "opinion"
    assert parse("인생에서 가장 중요한 게 뭐야?").answer_type == "opinion"
    assert parse("파이썬 좋아해?").answer_type == "preference"


def test_definition_and_entity():
    assert parse("양자역학이 뭐야?").answer_type == "definition"
    assert parse("양자역학이 뭐야?").subject == "양자역학"
    assert parse("손흥민이 누구야?").answer_type == "entity"


def test_bound_noun_never_becomes_subject():
    # '게/것/건' (의존명사) must not be picked as the subject
    assert parse("인생에서 가장 중요한 게 뭐야?").subject not in ("게", "것", "건")


def test_single_char_subject_survives():
    f = parse("물의 화학식은?")
    assert f.subject == "물"  # 1-char subject not dropped (the old bug)
