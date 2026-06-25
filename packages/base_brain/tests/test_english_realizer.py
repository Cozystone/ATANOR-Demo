"""Golden tests for the English surface realizer (M1).

These lock the behaviour established when the English answer path was rebuilt
from a per-relation slot-filler into an aggregated, article-correct realizer:

  * English answers never leak Hangul (no Korean labels or repair injections).
  * Relations are aggregated under one pronoun subject instead of repeating the
    head concept once per relation.
  * Object noun phrases carry determiners where the relation expects one.
  * Answers end as clean sentences (single terminal period, no ``..``).
"""

from __future__ import annotations

import re

import pytest

from packages.base_brain.zero_user_answer import (
    _en_noun_phrase,
    _english_relation_sentence,
    _english_second_hop,
    _label,
    answer_with_base_brain,
)

_HANGUL = re.compile(r"[가-힣]")

EN_QUERIES = [
    "What is GraphRAG?",
    "What is ATANOR?",
    "Explain how local brain stores memory.",
    "What is an ontology graph?",
    "What is Kubernetes?",
    "What is the difference between local AI and cloud AI?",
    "Why does evidence matter for reducing hallucination?",
]


@pytest.mark.parametrize("query", EN_QUERIES)
def test_english_answer_has_no_hangul_leak(query, tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    answer = answer_with_base_brain(query, language="en", audience_level="beginner")["answer"]
    assert answer, "expected a non-empty answer"
    assert not _HANGUL.search(answer), f"Hangul leaked into English answer: {answer!r}"


@pytest.mark.parametrize("query", EN_QUERIES)
def test_english_answer_is_clean_sentence(query, tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    answer = answer_with_base_brain(query, language="en", audience_level="beginner")["answer"]
    assert ".." not in answer, f"double period in answer: {answer!r}"
    assert answer.rstrip().endswith((".", "!", "?")), f"answer not terminated: {answer!r}"


def test_relations_do_not_repeat_the_subject(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    # GraphRAG has two relations; the old realizer emitted "GraphRAG ... GraphRAG ... GraphRAG ...".
    answer = answer_with_base_brain("What is GraphRAG?", language="en", audience_level="beginner")["answer"]
    assert answer.count("GraphRAG") == 1, f"subject repeated per relation: {answer!r}"
    assert " It " in answer or answer.split(". ", 1)[-1].startswith("It "), (
        f"expected pronoun-aggregated relation clause: {answer!r}"
    )


def test_relation_sentence_aggregates_and_articles() -> None:
    primary = {
        "concept_id": "atanor",
        "labels": {"en": "ATANOR"},
        "relations": [
            {"relation": "uses", "target": "semantic_graph"},
            {"relation": "uses", "target": "surface_graph"},
            {"relation": "requires", "target": "privacy"},
        ],
    }
    context_map = {
        "semantic_graph": {"concept_id": "semantic_graph", "labels": {"en": "semantic graph"}},
        "surface_graph": {"concept_id": "surface_graph", "labels": {"en": "surface graph"}},
        "privacy": {"concept_id": "privacy", "labels": {"en": "privacy"}},
    }
    sentence = _english_relation_sentence(primary, context_map)
    assert sentence.startswith("It ")
    assert "a semantic graph" in sentence  # countable object gets a determiner
    assert "requires privacy" in sentence  # uncountable object stays bare
    assert sentence.endswith(".")


def test_compound_clause_uses_oxford_comma() -> None:
    # M1.5: avoid run-on "uses X and Y and requires Z".
    primary = {
        "concept_id": "atanor",
        "labels": {"en": "ATANOR"},
        "relations": [
            {"relation": "uses", "target": "semantic_graph"},
            {"relation": "uses", "target": "surface_graph"},
            {"relation": "requires", "target": "privacy"},
        ],
    }
    context_map = {
        "semantic_graph": {"concept_id": "semantic_graph", "labels": {"en": "semantic graph"}},
        "surface_graph": {"concept_id": "surface_graph", "labels": {"en": "surface graph"}},
        "privacy": {"concept_id": "privacy", "labels": {"en": "privacy"}},
    }
    sentence = _english_relation_sentence(primary, context_map)
    assert "a semantic graph and a surface graph, and requires privacy" in sentence
    assert " and a surface graph and requires" not in sentence  # no run-on


def test_contrasts_with_takes_a_determiner() -> None:
    # M1.5: "contrasts with surface graph" -> "contrasts with a surface graph".
    primary = {
        "concept_id": "semantic_graph",
        "labels": {"en": "semantic graph"},
        "relations": [{"relation": "contrasts_with", "target": "surface_graph"}],
    }
    context_map = {"surface_graph": {"concept_id": "surface_graph", "labels": {"en": "surface graph"}}}
    sentence = _english_relation_sentence(primary, context_map)
    assert "contrasts with a surface graph" in sentence


def test_second_hop_chains_a_verified_fact() -> None:
    # M2: A→B→C reasoning, stating only relations that exist in the graph.
    primary = {
        "concept_id": "graphrag",
        "labels": {"en": "GraphRAG"},
        "relations": [{"relation": "requires", "target": "semantic_graph"}],
    }
    context_map = {
        "semantic_graph": {
            "concept_id": "semantic_graph",
            "labels": {"en": "semantic graph"},
            "relations": [{"relation": "contrasts_with", "target": "surface_graph"}],
        },
        "surface_graph": {"concept_id": "surface_graph", "labels": {"en": "surface graph"}},
    }
    hop = _english_second_hop(primary, context_map)
    assert hop == "A semantic graph, in turn, contrasts with a surface graph."


def test_second_hop_does_not_loop_back_to_primary() -> None:
    primary = {
        "concept_id": "a",
        "labels": {"en": "A"},
        "relations": [{"relation": "requires", "target": "b"}],
    }
    context_map = {
        "b": {"concept_id": "b", "labels": {"en": "B"}, "relations": [{"relation": "requires", "target": "a"}]},
    }
    assert _english_second_hop(primary, context_map) == ""  # b→a loops back, skip


def test_second_hop_needs_relevant_intermediate() -> None:
    # If the intermediate concept was not retrieved (not in context_map), no hop.
    primary = {
        "concept_id": "graphrag",
        "labels": {"en": "GraphRAG"},
        "relations": [{"relation": "requires", "target": "semantic_graph"}],
    }
    assert _english_second_hop(primary, {}) == ""


def test_real_query_includes_second_hop_reasoning(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    answer = answer_with_base_brain("What is GraphRAG?", language="en", audience_level="beginner")["answer"]
    assert "in turn" in answer  # multi-hop reasoning surfaced


def test_precision_gate_abstains_on_loose_false_match(tmp_path, monkeypatch) -> None:
    # The pack has no "capital of France" / "Graph Hub" concept; a loose match
    # must abstain instead of confidently describing the wrong concept.
    monkeypatch.chdir(tmp_path)
    for query in ["What is the capital of France?", "What is Graph Hub?"]:
        result = answer_with_base_brain(query, language="en", audience_level="beginner")
        assert result["confidence"] <= 0.2, f"{query!r} should abstain, got {result['answer']!r}"


def test_precision_gate_keeps_directly_named_concept(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    for query in ["What is GraphRAG?", "How does a CPU work?"]:
        result = answer_with_base_brain(query, language="en", audience_level="beginner")
        assert result["confidence"] >= 0.5
        assert "enough" not in result["answer"].lower()  # not the abstain message


def test_korean_named_concept_is_confident(tmp_path, monkeypatch) -> None:
    # Korean attaches a particle to the name ("양자컴퓨터가"); name-matching must
    # still recognise it, so confidence is high (was wrongly 0.45 before).
    monkeypatch.chdir(tmp_path)
    result = answer_with_base_brain("양자컴퓨터가 뭐야?", language="ko", audience_level="beginner")
    assert result["confidence"] >= 0.5


def test_confidence_is_honest_not_a_constant(tmp_path, monkeypatch) -> None:
    # M5: confidence reflects grounding strength.
    monkeypatch.chdir(tmp_path)
    grounded = answer_with_base_brain("What is GraphRAG?", language="en", audience_level="beginner")
    ungrounded = answer_with_base_brain(
        "What is the weather today?", language="en", audience_level="beginner"
    )
    assert grounded["confidence"] > 0.5, "a directly named concept should be confident"
    assert ungrounded["confidence"] < 0.3, "an ungrounded / real-time answer should be low confidence"
    assert grounded["confidence"] != ungrounded["confidence"]  # not a fixed constant


def test_noun_phrase_determiner_rules() -> None:
    assert _en_noun_phrase("semantic graph", with_article=True) == "a semantic graph"
    assert _en_noun_phrase("ontology", with_article=True) == "an ontology"
    assert _en_noun_phrase("privacy", with_article=True) == "privacy"  # uncountable
    assert _en_noun_phrase("GraphRAG", with_article=True) == "GraphRAG"  # proper noun
    assert _en_noun_phrase("semantic graph", with_article=False) == "semantic graph"


@pytest.mark.parametrize(
    "query",
    [
        "What is GraphRAG?",
        "What is a semantic graph?",
        "What is an ontology graph?",
        "What is Kubernetes?",
        "Why does evidence matter for reducing hallucination?",
    ],
)
def test_general_english_answers_are_graph_derived_not_hand_authored(query, tmp_path, monkeypatch) -> None:
    # M3: general questions must be realized from the graph, not pulled from a
    # hand-authored canned-answer table. This is what makes ATANOR "not rule-based".
    monkeypatch.chdir(tmp_path)
    result = answer_with_base_brain(query, language="en", audience_level="beginner")
    assert result["hand_authored_answer_used"] is False, f"{query!r} used a canned answer"
    assert str(result["answer"]).strip(), f"{query!r} produced an empty answer"


def test_english_label_never_returns_hangul() -> None:
    concept = {
        "concept_id": "local_brain",
        "canonical_name": "Local Brain",
        "labels": {"ko": "저장된 개인 맥락", "en": "Local Brain"},
    }
    assert _label(concept, "en") == "Local Brain"

    # Even when the English label is missing/corrupted, EN mode must stay ASCII.
    broken = {"concept_id": "local_brain", "canonical_name": "저장된 개인 맥락", "labels": {"ko": "저장된 개인 맥락"}}
    resolved = _label(broken, "en")
    assert not _HANGUL.search(resolved), f"label leaked Hangul: {resolved!r}"
    assert resolved == "local brain"
