from __future__ import annotations

from cgsr.query_skeleton import (
    canonical_query_tokens,
    default_case_roles_from_flat_skeleton,
    enrich_query_skeleton,
    extract_case_roles_from_sentence,
)


def test_default_case_roles_from_flat_skeleton_are_explicit() -> None:
    roles = default_case_roles_from_flat_skeleton(
        {"concept": "GraphRAG", "object": "근거 문서", "predicate": "검증하다"}
    )

    assert roles == [
        {"role": "TOPIC", "marker": "", "head": "GraphRAG", "source": "manual_default"},
        {"role": "OBJ", "marker": "", "head": "근거 문서", "source": "manual_default"},
    ]


def test_source_sentence_case_roles_preserve_josa_roles() -> None:
    roles = extract_case_roles_from_sentence("GraphRAG는 근거 문서를 검증한다.", "검증하다")

    assert any(row["role"] == "TOPIC" for row in roles)
    assert any(row["role"] == "OBJ" for row in roles)


def test_enriched_query_tokens_match_construction_shape() -> None:
    enriched = enrich_query_skeleton(
        {"concept": "GraphRAG", "object": "근거 문서", "predicate": "검증하다"},
        source_sentence="GraphRAG는 근거 문서를 검증한다.",
    )
    tokens = canonical_query_tokens(enriched)

    assert "TOPIC" in tokens
    assert "OBJ" in tokens
    assert "HEAD:문서" in tokens
