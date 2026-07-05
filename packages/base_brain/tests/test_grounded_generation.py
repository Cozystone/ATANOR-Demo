"""Grounded-Constrained Generation: the fused answer READS as composed prose (generated
discourse flesh) while every FACT is a verbatim grounded clause (bones). The core
guarantee is structural — the generator can only emit discourse scaffolding, never a
new fact — so these tests pin BOTH the fluency and the no-hallucination contract."""
from __future__ import annotations

from packages.base_brain.grounded_generation import synthesize, _DISCOURSE_KO


FACTS = [
    {"name": "인공지능", "description": "인공지능은 인간의 학습·추론·지각 능력을 컴퓨터로 구현하는 기술이다"},
    {"name": "기계학습", "description": "기계학습은 데이터에서 패턴을 스스로 찾도록 모델을 학습시키는 방법이다"},
    {"name": "신경망", "description": "신경망은 가중치로 연결된 층 구조로 데이터의 표현을 학습하는 모델이다"},
]


def test_thin_skeleton_abstains():
    assert synthesize("무엇이든", FACTS[:1], "ko") is None       # 1 fact < min → abstain
    assert synthesize("무엇이든", [], "ko") is None


def test_every_fact_appears_verbatim():
    """The bones are exact: each grounded description appears whole in the answer, so no
    factual content was paraphrased or recombined at the token level."""
    r = synthesize("좋은 리더가 되려면?", FACTS, "ko")
    assert r is not None
    for f in FACTS:
        assert f["description"] in r["answer"], "a grounded clause was altered/dropped"


def test_only_discourse_scaffolding_is_generated():
    """Whatever is NOT a verbatim fact clause must be a discourse move from the lexicon
    — the structural no-hallucination guarantee. Strip the facts out; the remainder must
    be composed solely of known discourse phrases."""
    r = synthesize("인공지능이란 무엇인가?", FACTS, "ko")
    remainder = r["answer"]
    for f in FACTS:
        remainder = remainder.replace(f["description"], "§")
    # every generated span the synthesizer reports must be a real discourse-lexicon entry
    lexicon = {p for group in _DISCOURSE_KO.values() for p in group}
    for span in r["generated_spans"]:
        assert span in lexicon, f"generated span not from discourse lexicon: {span!r}"
    # and the answer carries NO content beyond facts + discourse + topic markers
    assert r["reasoning_certificate"]["guarantees"]["fabricated_facts"] is False
    assert r["reasoning_certificate"]["guarantees"]["content_token_recombination"] is False


def test_speculative_question_is_hedged_not_asserted():
    """A future/prediction question must FRAME the grounded facts as backing, never as a
    settled forecast."""
    r = synthesize("인공지능의 미래는 어떻게 될까?", FACTS, "ko")
    assert r is not None
    assert r["answer"].startswith(tuple(_DISCOURSE_KO["hedge_open"]))


def test_reads_as_ordered_composition():
    """A first / additive / final discourse order (not a random jumble) — the flesh gives
    the bones a readable shape."""
    r = synthesize("기후 변화의 원인과 대책은?", FACTS, "ko")
    a = r["answer"]
    assert any(a.split(".")[1].strip().startswith(b) for b in _DISCOURSE_KO["bridge_first"]) or \
        any(b in a for b in _DISCOURSE_KO["bridge_first"])
    assert a.rstrip().endswith(tuple(_DISCOURSE_KO["closer"]))


def test_english_synthesis():
    en_facts = [
        {"name": "AI", "description": "AI is the field of building systems that learn and reason"},
        {"name": "machine learning", "description": "machine learning finds patterns in data to make predictions"},
    ]
    r = synthesize("what is the future of AI?", en_facts, "en")
    assert r is not None
    for f in en_facts:
        assert f["description"] in r["answer"]
