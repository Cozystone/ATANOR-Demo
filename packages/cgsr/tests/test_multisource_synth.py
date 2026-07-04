"""Multi-source grounded synthesis: comprehensive answers from several sources, no leaks, cited."""
from __future__ import annotations

import json
import pathlib

import pytest

from cgsr.multisource_synth import synthesize

CORPUS = [
    "엔비디아 코퍼레이션은 미국의 반도체 기업이다.",
    "엔비디아 드라이브는 자율주행 플랫폼이다.",
    "젠슨 황은 엔비디아의 공동 창립자이다.",          # 엔비디아 is a modifier here → excluded
    "대한민국 민법 제53조는 등기기간을 규정한 조문이다.",  # 대한민국 modifies 민법 → not about 대한민국
    "남일우는 대한민국의 축구 선수이다.",              # 대한민국 is a genitive modifier
    "2021년 대한민국에서 개봉하였다.",                 # 대한민국 is an adverbial → not the subject
]


def test_synthesizes_multiple_sources_about_the_entity():
    s = synthesize("엔비디아", CORPUS, max_facts=3)
    assert s is not None
    assert "반도체 기업" in s.text and "자율주행 플랫폼" in s.text  # two distinct facts, two sources
    assert len(s.grounding) == 2
    assert "공동 창립자" not in s.text  # 젠슨-황 sentence (엔비디아 as modifier) is excluded


def test_every_clause_is_verbatim_grounded():
    s = synthesize("엔비디아", CORPUS)
    for fact in s.facts:
        assert fact["text"] == fact["source"]   # extractive: nothing fabricated
        assert fact["source"] in CORPUS


def test_modifier_only_entity_abstains_no_leak():
    # 대한민국 only ever appears as a modifier/adverbial here → must NOT stitch unrelated facts.
    assert synthesize("대한민국", CORPUS) is None
    assert synthesize("블랙핑크", CORPUS) is None


def test_deterministic():
    a = synthesize("엔비디아", CORPUS)
    b = synthesize("엔비디아", CORPUS)
    assert a.text == b.text


_EVIDENCE = (
    pathlib.Path(__file__).resolve().parents[3]
    / "data" / "cloud_brain" / "candidate_runs" / "clean_retrain_v1" / "evidence.jsonl"
)


@pytest.mark.skipif(not _EVIDENCE.exists(), reason="real corpus not present")
def test_real_corpus_synthesizes_nvidia_multi_source():
    rows = [json.loads(l).get("text") or "" for l in _EVIDENCE.open(encoding="utf-8")]
    nvidia = synthesize("엔비디아", rows, max_facts=3)
    assert nvidia is not None and len(nvidia.grounding) >= 2  # multi-source on real data


def test_modifier_only_mentions_abstain_fixed_fixture():
    """The abstain contract on a FIXED fixture: an entity that appears only as a
    modifier ('대한민국의 축구 선수') must not get a fabricated definition. (The old
    live-data version broke the moment the growing store legitimately learned a
    real 대한민국 definition — the engine was right, the snapshot assumption wasn't.)"""
    rows = [
        "홍길동은 대한민국의 축구 선수이다.",
        "김철수는 대한민국의 가수이다.",
        "이영희는 대한민국의 과학자이다.",
    ]
    # NOTE: "대한민국 산업자원부는 …" (compound-subject) is a KNOWN separate ambiguity
    # class — structurally identical to "엔비디아 코퍼레이션은 …", undecidable without
    # entity knowledge; the consensus ledger's alias clusters are the long-term fix.
    assert synthesize("대한민국", rows) is None
