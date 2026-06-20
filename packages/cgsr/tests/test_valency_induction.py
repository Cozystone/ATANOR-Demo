from cgsr.family_analysis import analyze_family_rows
from cgsr.induction import extract_valency_frames, induce_valency_constructions


def test_extract_valency_frame_subject_object_predicate() -> None:
    frames = extract_valency_frames("GraphRAG은 근거 문서를 검증한다.")

    assert any(
        predicate == "검증하다"
        and ("TOPIC", "은") in cases
        and ("OBJ", "를") in cases
        for cases, predicate in frames
    )


def test_induce_valency_constructions_keeps_predicate_anchor() -> None:
    rows = induce_valency_constructions(
        [
            "GraphRAG은 근거 문서를 검증한다.",
            "시스템은 근거를 검증한다.",
            "엔진은 문서를 검증한다.",
        ],
        min_frequency=2,
    )

    assert rows
    assert any("PREDICATE:검증하다" in row.canonical_form for row in rows)
    assert any("OBJ" in row.canonical_form for row in rows)


def test_family_analysis_preserves_valency_canonical_form() -> None:
    sentences = [
        "GraphRAG은 근거 문서를 검증한다.",
        "시스템은 근거를 검증한다.",
        "엔진은 문서를 검증한다.",
    ]
    raw = induce_valency_constructions(sentences, min_frequency=1, dedupe=False)
    deduped = induce_valency_constructions(sentences, min_frequency=1, dedupe=True)
    rows = analyze_family_rows(raw, deduped)

    assert rows
    assert rows[0].member_count == 3
    assert rows[0].classification != "singleton"
