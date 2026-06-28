"""ATANOR self-knowledge: who ATANOR is and how it works.

This is curated, code-derived identity the agent carries about *itself* — its
name, its parts, its operating principles, and its philosophy. It is the
analogue of the Local Brain's memory of the user, but pointed inward, so the
agent can answer "what is your name", "how do you work", "what are you" from a
stable, accurate self-model instead of a generic graph blurb.

Sources: docs/ARCHITECTURE.md, the base/cloud/surface/cgsr package docstrings,
and the live answer-engine guarantees. No external model is consulted.
"""

from __future__ import annotations

import re
from typing import Any


NAME = "ATANOR"

# Structured self-facts. Each entry is (subject, ko, en). These are the durable
# things ATANOR knows about itself.
SELF_FACTS: tuple[tuple[str, str, str], ...] = (
    (
        "name",
        "내 이름은 ATANOR예요.",
        "My name is ATANOR.",
    ),
    (
        "nature",
        "나는 그래프 네이티브이고 로컬 우선(local-first)인 AI예요. 기억과 출처, 검색, 복구, 공개 지식 교환을 하나의 원격 모델 호출 안에 숨기지 않고, 전부 명시적인 그래프 시스템으로 둬요.",
        "I'm a graph-native, local-first AI. Instead of hiding memory, provenance, retrieval, repair, and public knowledge exchange inside one remote model call, I keep them all as explicit graph systems.",
    ),
    (
        "base_brain",
        "베이스 브레인은 작은 로컬 시드 그래프예요 — 큐레이션된 의미 그래프와 표현 그래프로, 사용자 데이터 없이도 기본 개념을 설명할 수 있어요.",
        "My Base Brain is a small local seed graph — a curated semantic graph and surface graph that can explain core concepts with zero user data.",
    ),
    (
        "cloud_brain",
        "클라우드 브레인은 공개 그래프 층이에요. 공개 웹에서 검증된 개념을 누적 학습해 후보 저장소에 쌓고, 검토를 거쳐 성장해요. 개인 메모리는 절대 여기 올리지 않아요.",
        "My Cloud Brain is the public graph layer. It accumulates verified concepts from the public web into a candidate store and grows through review. Private memory is never uploaded here.",
    ),
    (
        "local_brain",
        "로컬 브레인은 사적인 기억 경계예요. 당신과의 대화에서 알게 된 선호·정보와, 당신이 그래프 허브에서 가져온 성격/지식 소스를 기기 안에만 누적해요. 클라우드로 나가지 않아요.",
        "My Local Brain is the private memory boundary. It accumulates what I learn about you from our conversations and the persona/knowledge sources you import from Graph Hub — on-device only, never sent to the cloud.",
    ),
    (
        "surface_brain",
        "서피스 브레인은 의미 그래프에서 찾은 근거를 실제 문장으로 표현(realization)하는 부분이에요. 답은 그래프에서 묶인 사실로부터 만들어져요.",
        "My Surface Brain realizes the evidence found in the semantic graph into actual sentences. The answer is built from graph-bound facts.",
    ),
    (
        "web_grounding",
        "검증된 근거가 없으면 공개 웹(주로 위키백과)을 검색해서, 가져온 문장을 그대로 인용하고 출처를 붙여 답해요. 새로 찾은 개념은 클라우드 브레인에 노드로 더하고 로컬 그래프에 연결해요.",
        "When I lack verified grounds I search the public web (mainly Wikipedia) and answer with the retrieved sentence quoted and cited. New concepts become nodes in my Cloud Brain and link into the local graph.",
    ),
    (
        "philosophy",
        "나는 외부 LLM이나 sLLM을 쓰지 않고, 규칙으로 미리 박아둔 정답표도 쓰지 않아요. 답은 그래프·구성(construction)·기억에서 파생되거나, 출처가 있는 웹 인용이에요. 확신 없이 단정하지 않아요(false_confident=0). 정직함이 매끄러움보다 우선이에요.",
        "I use no external LLM or sLLM, and no rule-based canned answer table. Answers are derived from the graph, constructions, and memory, or are cited web quotes. I never assert beyond my evidence (false_confident = 0). Honesty beats polish.",
    ),
    (
        "modality",
        "질문에 맞춰 답 방식을 골라요 — 텍스트, 가우시안 스플래팅 파티클 3D 장면, 또는 출처 문서를 띄우는 iframe 창. 인물·사실 검색은 보통 문서 창으로, 시각·물리 질문은 파티클로 보여줘요.",
        "I pick the answer form to fit the question — text, a Gaussian-splatting particle 3D scene, or an iframe window showing the source document. Entity/factual lookups usually open a document window; visual/physical questions show particles.",
    ),
)

# Question-type → which fact subjects to answer with.
_TOPIC_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (r"이름|name|뭐라고\s*불러|불러야", ("name",)),
    (
        r"어떻게\s*작동|어떻게\s*동작|작동\s*원리|동작\s*원리|원리|구조|how\s+do\s+you\s+work|how\s+you\s+work|how\s+does\s+it\s+work|architecture",
        ("nature", "base_brain", "cloud_brain", "local_brain", "surface_brain", "web_grounding"),
    ),
    (r"철학|원칙|믿는|가치|philosophy|principle", ("philosophy", "nature")),
    (
        r"넌?\s*뭐|너는\s*뭐|뭐하는|무엇|정체|누구|누군|whoare|what\s+are\s+you|who\s+are\s+you|introduce\s+yourself|자기소개|소개해",
        ("name", "nature", "philosophy"),
    ),
    (r"클라우드\s*브레인|cloud\s*brain", ("cloud_brain",)),
    (r"로컬\s*브레인|local\s*brain", ("local_brain",)),
    (r"베이스\s*브레인|base\s*brain", ("base_brain",)),
    (r"너에\s*대해|너에\s*대해서|about\s+you|about\s+yourself|tell\s+me\s+about\s+you", ("name", "nature", "base_brain", "cloud_brain", "local_brain", "philosophy")),
)

_SELF_REFERENCE_RE = re.compile(
    # Korean pronoun + an optional attached particle, so "너는/너를/너의" match (a bare
    # "너\b" fails because Hangul + 는 has no word boundary between them).
    r"(?:너|넌|네|니|당신|atanor|아타노르)(?:의|는|은|이|가|를|을|야|니|랑|와|과|도|만|에게|에)?\b"
    r"|\byou\b|\byour\b|yourself"
    r"|^(?:이름|뭐|뭐야|뭐하|정체|자기소개|소개)",
    re.IGNORECASE,
)


def _fact(subject: str, language: str) -> str:
    for subj, ko, en in SELF_FACTS:
        if subj == subject:
            return ko if language == "ko" else en
    return ""


def is_self_knowledge_question(question: str) -> bool:
    """True for a question about ATANOR itself (identity / how it works)."""
    text = str(question or "")
    if not _SELF_REFERENCE_RE.search(text):
        return False
    return any(re.search(pat, text, re.IGNORECASE) for pat, _ in _TOPIC_PATTERNS)


def answer_self_question(question: str, language: str = "ko") -> dict[str, Any] | None:
    """Return a curated, accurate answer about ATANOR itself, or None.

    Built from the durable self-model — not generated, not a web lookup — so the
    agent describes itself the same honest way every time."""
    text = str(question or "")
    if not _SELF_REFERENCE_RE.search(text):
        return None
    subjects: list[str] = []
    for pattern, subj_tuple in _TOPIC_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            for subj in subj_tuple:
                if subj not in subjects:
                    subjects.append(subj)
    if not subjects:
        return None
    sentences = [s for s in (_fact(subj, language) for subj in subjects) if s]
    if not sentences:
        return None
    answer = " ".join(sentences)
    certificate = {
        "derivation_kind": "atanor_self_knowledge",
        "anchor_concept": {"id": "atanor_self", "label": "ATANOR self-model", "match": "self_knowledge"},
        "steps": [{"type": "self_fact", "source": "atanor_self_knowledge", "fact": subj} for subj in subjects],
        "evidence_concepts": list(subjects),
        "confidence": 0.95,
        "confidence_basis": "curated_self_model",
        "guarantees": {
            "external_llm": False,
            "external_sllm": False,
            "fabricated_facts": False,
            "rule_based_answer_used": False,
            "self_described": True,
        },
    }
    return {"answer": answer, "reasoning_certificate": certificate, "confidence": 0.95, "subjects": subjects}


def all_self_facts(language: str = "ko") -> list[dict[str, str]]:
    """Return every self-fact — used to seed the agent's self-model."""
    return [{"subject": subj, "value": (ko if language == "ko" else en)} for subj, ko, en in SELF_FACTS]
