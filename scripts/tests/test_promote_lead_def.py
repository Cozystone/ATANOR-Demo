"""Regression test for the promotion modifier-head bug (P0).

The promotion gate builds `name -> definitional sentence` by requiring the
sentence to be ABOUT the concept as its leading subject. The OLD rule required
the sentence to start *literally* with the bare concept name, which silently
discarded almost every real-world definition because a first sentence nearly
always narrows the head noun with a modifier:

    "머신러닝 알고리즘은 …"   -> should map to 알고리즘
    "컴퓨터 바이러스는 없다."  -> should map to 바이러스 (mention, not a def — see below)

`build_lead_def_by_name` now matches the concept as the HEAD NOUN of a modified
leading subject, while still rejecting unrelated mid-sentence mentions and
mid-word substring collisions.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (str(REPO_ROOT), str(REPO_ROOT / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

from promote_graph_to_pack import build_lead_def_by_name  # noqa: E402


def _run(texts, topics_by_hash=None):
    text_by_hash = {f"h{i}": t for i, t in enumerate(texts)}
    return build_lead_def_by_name(text_by_hash, topics_by_hash or {})


def test_bare_leading_subject_still_maps():
    out = _run(["광합성은 빛 에너지를 화학 에너지로 바꾸는 과정이다."])
    assert out.get("광합성", "").startswith("광합성은")


def test_non_definitional_korean_sentences_rejected():
    # Leading subject but NOT a definition -> must not become a description.
    cases = [
        "데이터베이스는 그리 어렵지 않습니다!",          # casual negation
        "서울 살지만 첨 갔는데 다시 가고 싶지는 않아요.",   # casual opinion
        "삼성전자가 2026년 지속가능경영보고서를 발간했다.",  # news event
        "저 별들의 질량은 어디로 가는 건가요?",           # question
        "Huffyuv의 알고리즘은 무손실 JPEG-LS하고 비슷하다.",  # off-topic simile
    ]
    out = _run(cases)
    assert out == {}, f"non-definitional sentences leaked: {out}"


def test_definitional_korean_sentences_kept():
    cases = {
        "h0": "세포는 모든 생물체의 구조적, 기능적 기본 단위이다.",
        "h1": "호르몬은 내분비기관에서 생성되는 화학물질들을 통틀어 일컫는다.",
        "h2": "에너지는 물리학에서 일을 할 수 있는 능력을 뜻한다.",
        "h3": "화산은 분화의 빈도에 따라 활화산 또는 사화산이라고 한다.",
    }
    out = build_lead_def_by_name(cases, {})
    assert {"세포", "호르몬", "에너지", "화산"} <= set(out)


def test_modified_leading_subject_maps_to_head_noun():
    # THE BUG: modifier "머신러닝" in front of the head noun must not block a
    # genuine DEFINITION of the head. (Sentence is definitional: "…방법이다".)
    out = _run(
        ["머신러닝 알고리즘은 데이터로부터 규칙과 패턴을 스스로 학습하는 방법이다."]
    )
    assert "알고리즘" in out
    assert out["알고리즘"].startswith("머신러닝 알고리즘은")


def test_modified_subject_maps_and_keeps_shortest():
    out = _run(
        [
            "컴퓨터 바이러스는 스스로를 복제하여 다른 프로그램을 감염시키는 악성 코드이다.",
            "이 오래되고 특수한 기종에서 발동되는 컴퓨터 바이러스는 지금까지 하나도 없다.",
        ]
    )
    assert "바이러스" in out
    # shortest (cleanest) definitional sentence wins
    assert out["바이러스"].startswith("컴퓨터 바이러스는 스스로를")


def test_midsentence_mention_is_not_a_definition():
    # 뉴턴 appears only as a mid-sentence unit mention -> must NOT become its def.
    out = _run(["또한, 질량과는 달리 무게의 단위는 힘의 단위 (N, 뉴턴)와 동일하다."])
    assert "뉴턴" not in out


def test_substring_collision_rejected():
    # "이드" must not match inside "아이드로" — head-noun match is word-bounded,
    # and a bare startswith would also fail here, so nothing spurious maps.
    out = _run(["아이드로겐은 어떤 가상의 물질이다."])
    assert "이드" not in out
    assert out.get("아이드로겐", "").startswith("아이드로겐은")


def test_fronted_adverbial_maps_only_the_true_subject_head():
    # A fronted adverbial ("세포에 대하여") precedes the true subject ("생물학은").
    # Only the subject head 생물학 (last token of the leading NP) maps; the
    # adverbial noun 세포 must NOT be treated as the subject.
    text_by_hash = {"h0": "세포에 대하여 생물학은 생명 현상을 연구하는 자연과학의 한 분야이다."}
    out = build_lead_def_by_name(text_by_hash, {})
    assert "생물학" in out
    assert "세포" not in out


def test_korean_genitive_modifier_is_not_the_subject():
    # "엔비디아의 CUDA는 …" is about CUDA, not 엔비디아. The genitive 의 right after
    # 엔비디아 (a Hangul non-subject particle) blocks it; CUDA is the real head.
    text_by_hash = {"h0": "엔비디아의 CUDA는 병렬 컴퓨팅 플랫폼이자 프로그래밍 모델이다."}
    topics = {"h0": {"엔비디아", "cuda"}}
    out = build_lead_def_by_name(text_by_hash, topics)
    assert "엔비디아" not in out  # genitive modifier, not the subject
    assert "cuda" in out          # the actual leading subject head


def test_english_definitions_are_preserved():
    # REGRESSION GUARD: an earlier fix accidentally required a Korean subject
    # particle on the case_frame path, which silently dropped EVERY English
    # definition (English subjects have no 은/는/이/가). These must map via the
    # language-agnostic startswith path.
    texts = {
        "h0": "Algeria, officially the People's Democratic Republic of Algeria, is a country.",
        "h1": "Acianthera is a genus of orchids native to the tropical Americas.",
        "h2": "Aileen is an Irish feminine given name, a variant of Eileen.",
    }
    topics = {"h0": {"algeria"}, "h1": {"acianthera"}, "h2": {"aileen"}}
    out = build_lead_def_by_name(texts, topics)
    assert "algeria" in out
    assert "acianthera" in out
    assert "aileen" in out


def test_proper_noun_latin_tail_not_split():
    # "Spring Boot는 …" is a proper noun; its Latin tail 'boot' must NOT become a
    # concept (the decomposer mis-splits such names; head-noun rule is Hangul-only).
    out = _run(["Spring Boot는 최소한의 초기 스프링 구성으로 빠르게 실행되도록 설계되었다."])
    assert "boot" not in out
    assert "spring boot" not in out  # startswith path: sentence starts with it, but
    # the topic set is empty here, so nothing spurious maps either


def test_proper_noun_numeric_tail_not_split():
    # "맨헌트 인터내셔널 1993은 …" -> the tail '1993' is not a concept.
    out = _run(["맨헌트 인터내셔널 1993은 1993년 호주에서 처음 개최된 남자 대회이다."])
    assert "1993" not in out


def test_hangul_head_still_extracted():
    # The Hangul-only restriction must NOT drop the genuine common-noun case.
    out = _run(["컴퓨터 바이러스는 스스로를 복제하는 악성 코드이다."])
    assert "바이러스" in out


def test_korean_prefix_word_collision_rejected():
    # "미국인은 …" must NOT map to concept 미국 (미국 is only a prefix of the real
    # subject 미국인). The boundary char after 미국 is 인 (Hangul, not a subject
    # particle) -> rejected.
    text_by_hash = {"h0": "미국인은 미국에 거주하거나 미국 국적을 가진 사람이다."}
    topics = {"h0": {"미국"}}
    out = build_lead_def_by_name(text_by_hash, topics)
    assert "미국" not in out
