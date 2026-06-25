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
