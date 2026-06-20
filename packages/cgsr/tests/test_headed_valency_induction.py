from __future__ import annotations

from cgsr.family_analysis import analyze_family_rows
from cgsr.induction import extract_headed_valency_frames, induce_headed_valency_constructions
from cgsr.storage_policy import score_family_for_storage


def test_extract_headed_valency_frame_retains_argument_head() -> None:
    frames = extract_headed_valency_frames("GraphRAG은 근거 문서를 검증한다.")

    assert any(
        predicate == "검증하다"
        and any(role == "OBJ" and head == "문서" for role, _, head in cases)
        for cases, predicate in frames
    )


def test_headed_valency_construction_adds_head_token_to_broad_core_frame() -> None:
    rows = induce_headed_valency_constructions(
        [
            "GraphRAG은 근거 문서를 검증한다.",
            "시스템은 근거 문서를 검증한다.",
            "엔진은 근거 문서를 검증한다.",
        ],
        min_frequency=2,
    )

    assert rows
    assert any("HEAD:문서" in row.canonical_form for row in rows)


def test_headed_core_frame_can_pass_strict_policy_without_adverbial() -> None:
    raw = induce_headed_valency_constructions(
        [
            "GraphRAG은 근거 문서를 검증한다.",
            "시스템은 근거 문서를 검증한다.",
            "엔진은 근거 문서를 검증한다.",
            "모듈은 근거 문서를 검증한다.",
            "그래프는 근거 문서를 검증한다.",
            "절차는 근거 문서를 검증한다.",
            "사용자는 근거 문서를 검증한다.",
            "질문은 근거 문서를 검증한다.",
            "답변은 근거 문서를 검증한다.",
            "문장은 근거 문서를 검증한다.",
        ],
        min_frequency=1,
        dedupe=False,
    )
    deduped = induce_headed_valency_constructions(
        [example for row in raw for example in row.examples],
        min_frequency=1,
        dedupe=True,
    )
    family_row = analyze_family_rows(raw, deduped)[0]
    decision = score_family_for_storage(family_row)

    assert "HEAD:" in family_row.canonical_form
    assert decision.destination == "rhfc_candidate"
