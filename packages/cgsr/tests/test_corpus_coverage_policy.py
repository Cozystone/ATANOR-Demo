from __future__ import annotations

from cgsr.corpus_coverage_policy import (
    build_corpus_statistical_track,
    collect_corpus_predicate_stats,
    strict_predicate_inventory,
)


def test_collect_corpus_predicate_stats_uses_corpus_sentences() -> None:
    sentences = [
        "GraphRAG는 근거 문서를 검증한다.",
        "ATANOR는 후보 경로를 검증한다.",
        "시스템은 출력 문장을 검증한다.",
    ]

    stats = collect_corpus_predicate_stats(sentences)

    assert stats["predicate_counts"].get("검증하다", 0) >= 1
    assert stats["frame_counts"]


def test_corpus_statistical_track_excludes_strict_inventory_and_marks_no_eval_cases() -> None:
    sentences = [
        "GraphRAG는 근거 문서를 검증한다.",
        "ATANOR는 후보 경로를 검증한다.",
        "시스템은 출력 문장을 검증한다.",
        "아틀라스는 지역 상태를 보여준다.",
        "대시보드는 그래프 상태를 보여준다.",
    ]
    strict = [
        {
            "family_id": "strict_show",
            "row": {"canonical_form": "TOPIC OBJ HEAD:상태 PREDICATE:보여주다"},
        }
    ]

    track = build_corpus_statistical_track(
        sentences,
        strict,
        percentile=0.0,
        max_predicates=10,
    )

    assert "보여주다" in strict_predicate_inventory(strict)
    assert "검증하다" in track["predicate_list"]
    assert "보여주다" not in track["predicate_list"]
    assert track["leakage_review"]["uses_evaluation_cases"] is False
    assert track["leakage_review"]["evaluation_case_rows_parameter_exists"] is False
    assert all(item["used_evaluation_cases"] is False for item in track["candidates"])
