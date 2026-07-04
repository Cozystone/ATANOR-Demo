"""Fused thought/speech: utterances are GENERATED from real state (varied, not a fixed
table), and the self turns inward — asking about itself and answering FROM the graph."""
from __future__ import annotations

from packages.continuous_self.self_state import Observation, SelfState, evolve
from packages.continuous_self.voice import (
    compose_thought,
    due_for_self_inquiry,
    generate_self_inquiry,
    record_self_understanding,
)


def test_learning_utterance_varies_and_carries_the_real_count():
    seen = set()
    for tick in range(6):
        s = SelfState()
        s.ticks = tick
        th = compose_thought(s, Observation(learning_active=True, concepts_delta=tick + 2))
        assert str(tick + 2) in th["text"]           # grounded in the REAL count
        seen.add(th["text"])
    assert len(seen) >= 3, "consecutive learning thoughts must not repeat verbatim"


def test_observe_utterance_is_not_a_single_fixed_string():
    outs = {compose_thought(SelfState(ticks=t), Observation(learning_active=True))["text"] for t in range(4)}
    assert len(outs := outs) >= 2, "the old single-string repetition is gone"


def test_young_self_turns_inward_early_and_often():
    s = SelfState()  # brand new, self_inquiry_count = 0
    s.ticks = 8
    assert due_for_self_inquiry(s) is True
    q, topic = generate_self_inquiry(s)
    assert "나는" in q and topic == "identity"  # the FIRST question is about itself


def test_inquiry_sequence_progresses():
    s = SelfState()
    topics = []
    for _ in range(5):
        q, topic = generate_self_inquiry(s)
        topics.append(topic)
        record_self_understanding(s, q, "나는 …로컬 지식 엔진이다.", topic)
    assert topics[0] == "identity" and "purpose" in topics  # matures through stages


def test_grounded_answer_is_folded_but_open_question_is_honest():
    s = SelfState()
    q, topic = generate_self_inquiry(s)
    # with a grounded answer → it holds an understanding
    record_self_understanding(s, q, "나는 근거에서 답을 짓는 로컬 엔진이다.", topic)
    assert s.self_understanding and "근거로 아는 답" in s.narrative[-1]["text"]
    # without one → it says so honestly, never fabricates
    s2 = SelfState()
    q2, t2 = generate_self_inquiry(s2)
    record_self_understanding(s2, q2, None, t2)
    assert "근거로 댈 답이 내겐 부족" in s2.narrative[-1]["text"]
    assert s2.self_understanding == ""


def test_evolve_uses_generated_voice_not_a_table():
    a = SelfState(); a.ticks = 1
    b = SelfState(); b.ticks = 2
    evolve(a, Observation(learning_active=True, concepts_delta=3))
    evolve(b, Observation(learning_active=True, concepts_delta=7))
    assert a.current_thought != b.current_thought  # different state → different words
