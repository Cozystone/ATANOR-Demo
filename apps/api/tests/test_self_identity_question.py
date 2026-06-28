"""Regression: "너는 누구야?" must return ATANOR's self-intro, not a dictionary
definition of the pronoun "너". The bug was two-fold: the identity topic pattern
lacked 누구, and the self-reference regex required a word boundary that a Korean
particle-attached pronoun ("너는") never has.
"""
from __future__ import annotations

from packages.base_brain.atanor_self_knowledge import (
    answer_self_question,
    is_self_knowledge_question,
)


def test_identity_question_variants_are_self_questions():
    for q in ["너는 누구야?", "넌 누구야", "너 누구니", "너에 대해 알려줘", "who are you?", "what are you?"]:
        lang = "ko" if any("가" <= c <= "힣" for c in q) else "en"
        assert is_self_knowledge_question(q), q
        ans = answer_self_question(q, lang)
        assert ans and "ATANOR" in str(ans.get("answer") or ""), q


def test_attribution_and_factual_are_not_self_questions():
    # these must NOT be hijacked by the self-model (they go to attribution / web)
    for q in ["엔비디아 창립자가 누구야?", "전화기를 발명한 사람은 누구야?", "광합성이 뭐야?", "모나리자를 그린 사람은 누구야?"]:
        assert not is_self_knowledge_question(q), q
        assert answer_self_question(q, "ko") is None, q
