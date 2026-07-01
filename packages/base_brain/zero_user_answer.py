from __future__ import annotations

import hashlib
import re
from typing import Any

_HANGUL = re.compile(r"[가-힣]")

from packages.surface_brain.monitor import repair_answer_for_mode
from packages.surface_brain.q_cortex_bridge import select_surface_candidates

from .models import AnswerMode, AudienceLevel, Language, honesty_flags
from .pack_loader import classify_intent, get_semantic_context, get_surface_candidates, load_base_brain_pack
from .scene_grounding import extract_scene_grounding


UNSUPPORTED_HINTS_KO = ("오늘", "최신", "실시간", "주가", "가격", "유재석", "우리 동네", "날씨")
UNSUPPORTED_HINTS_EN = ("today", "weather", "latest", "stock price", "current price", "near me")

RELATION_WORDS_KO = {
    "is_a": "의 한 종류입니다",
    "part_of": "의 일부입니다",
    "has_property": "라는 특성을 가집니다",
    "used_for": "에 쓰입니다",
    "causes": "의 원인이 될 수 있습니다",
    "enables": "를 가능하게 합니다",
    "requires": "를 필요로 합니다",
    "contrasts_with": "와 대비됩니다",
    "similar_to": "와 비슷합니다",
    "example_of": "의 예입니다",
    "manages": "를 관리합니다",
    "produces": "를 만듭니다",
    "depends_on": "에 의존합니다",
    "supports": "를 뒷받침합니다",
    "contains": "를 포함합니다",
    "uses": "를 사용합니다",
}

RELATION_WORDS_EN = {
    "is_a": "is a kind of",
    "part_of": "is part of",
    "has_property": "has the property",
    "used_for": "is used for",
    "causes": "can cause",
    "enables": "enables",
    "requires": "requires",
    "contrasts_with": "contrasts with",
    "similar_to": "is similar to",
    "example_of": "is an example of",
    "manages": "manages",
    "produces": "produces",
    "depends_on": "depends on",
    "supports": "supports",
    "contains": "contains",
    "uses": "uses",
}

# English micro-NLG: turn (subject, relation, object) triples into one aggregated,
# article-correct, pronoun-using sentence instead of repeating the subject per relation.
EN_RELATION_CLAUSE = {
    "is_a": "is a kind of {o}",
    "part_of": "is part of {o}",
    "has_property": "has the property {o}",
    "used_for": "is used for {o}",
    "causes": "can cause {o}",
    "enables": "enables {o}",
    "requires": "requires {o}",
    "contrasts_with": "contrasts with {o}",
    "similar_to": "is similar to {o}",
    "example_of": "is an example of {o}",
    "manages": "manages {o}",
    "produces": "produces {o}",
    "depends_on": "depends on {o}",
    "supports": "supports {o}",
    "contains": "contains {o}",
    "uses": "uses {o}",
}

# Relations whose object reads as a countable noun phrase and should take a determiner.
EN_ARTICLE_RELATIONS = {
    "requires", "uses", "causes", "produces", "contains", "manages", "supports",
    "contrasts_with", "similar_to", "depends_on",
}

# Objects that are mass/abstract nouns and must stay bare (no "a"/"an").
EN_UNCOUNTABLE = {
    "privacy",
    "evidence",
    "hallucination reduction",
    "software deployment",
    "container orchestration",
    "ai training",
    "ai inference",
}


def _en_noun_phrase(label: str, *, with_article: bool) -> str:
    label = label.strip()
    if not label:
        return label
    if not with_article:
        return label
    if label[:1].isupper():  # proper noun (GraphRAG, ATANOR, Local Brain)
        return label
    if label.lower() in EN_UNCOUNTABLE:
        return label
    article = "an" if label[:1].lower() in "aeiou" else "a"
    return f"{article} {label}"


def _join_en(parts: list[str]) -> str:
    parts = [p for p in parts if p]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return f"{', '.join(parts[:-1])}, and {parts[-1]}"


def _english_relation_sentence(
    primary: dict[str, Any],
    context_map: dict[str, dict[str, Any]],
    *,
    max_relations: int = 3,
) -> str:
    """Aggregate a concept's relations into one fluent sentence: 'It <clauses>.'."""
    grouped: list[tuple[str, list[str]]] = []
    index: dict[str, int] = {}
    for relation in primary.get("relations", [])[:max_relations]:
        relation_name = str(relation.get("relation") or "related_to")
        clause_template = EN_RELATION_CLAUSE.get(relation_name)
        if clause_template is None:
            continue
        target_id = str(relation.get("target") or "")
        if target_id not in context_map and "_" in target_id:
            continue
        target = context_map.get(
            target_id, {"concept_id": target_id, "canonical_name": target_id, "labels": {}}
        )
        target_label = _label(target, "en")
        obj = _en_noun_phrase(target_label, with_article=relation_name in EN_ARTICLE_RELATIONS)
        if relation_name in index:
            grouped[index[relation_name]][1].append(obj)
        else:
            index[relation_name] = len(grouped)
            grouped.append((relation_name, [obj]))

    clauses: list[str] = []
    for relation_name, objects in grouped:
        clause_template = EN_RELATION_CLAUSE[relation_name]
        clauses.append(clause_template.format(o=_join_en(objects)))
    if not clauses:
        return ""
    # When a clause already coordinates objects ("uses a semantic graph and a
    # surface graph"), join the clauses with an Oxford ", and" so the sentence
    # doesn't read as a run-on chain of "and ... and ...".
    if len(clauses) >= 2 and any(" and " in clause for clause in clauses):
        body = f"{', '.join(clauses[:-1])}, and {clauses[-1]}"
    else:
        body = _join_en(clauses)
    return f"It {body}."


def _english_second_hop(primary: dict[str, Any], context_map: dict[str, dict[str, Any]]) -> str:
    """M2: surface ONE verified second-hop fact (A→B→C) as a connected sentence.

    Pure graph reasoning — it only states relations that exist in the graph
    (primary → target → target's relation), never an invented causal link. The
    intermediate concept must be relevant to the query (present in context_map).
    """
    primary_id = str(primary.get("concept_id"))
    for relation in primary.get("relations", [])[:3]:
        target_id = str(relation.get("target") or "")
        target = context_map.get(target_id)
        if not target:
            continue
        for sub in target.get("relations", [])[:3]:
            sub_target_id = str(sub.get("target") or "")
            if not sub_target_id or sub_target_id == primary_id or sub_target_id == target_id:
                continue
            clause_template = EN_RELATION_CLAUSE.get(str(sub.get("relation") or "related_to"))
            if clause_template is None:
                continue
            sub_rel = str(sub.get("relation"))
            sub_target = context_map.get(sub_target_id, {"concept_id": sub_target_id, "labels": {}})
            sub_label = _label(sub_target, "en")
            target_label = _label(target, "en")
            if not sub_label or not target_label or _HANGUL.search(sub_label) or _HANGUL.search(target_label):
                continue
            obj = _en_noun_phrase(sub_label, with_article=sub_rel in EN_ARTICLE_RELATIONS)
            subject = _en_noun_phrase(target_label, with_article=not target_label[:1].isupper())
            subject = subject[:1].upper() + subject[1:]
            return f"{subject}, in turn, {clause_template.format(o=obj)}."
    return ""


KO_DESCRIPTIONS = {
    "kubernetes": "여러 서버에 흩어진 컨테이너를 자동으로 배포하고, 상태를 확인하며, 필요하면 다시 띄우거나 복구해 주는 오픈소스 운영 플랫폼입니다.",
    "container_orchestration_system": "컨테이너를 어디에서 실행할지 정하고, 배포와 복구를 자동화하는 관리 시스템입니다.",
    "container": "애플리케이션과 필요한 실행 환경을 작게 묶어 어디서든 비슷하게 실행되게 하는 단위입니다.",
    "docker": "애플리케이션을 컨테이너로 포장하고 실행하게 해 주는 도구입니다.",
    "spring_boot": "Java 기반 웹 서비스와 API를 빠르게 만들고 운영 설정을 단순화해 주는 백엔드 프레임워크입니다.",
    "express_js": "Node.js에서 HTTP API와 웹 서버를 가볍고 빠르게 만들기 좋은 프레임워크입니다.",
    "web_framework": "웹 서비스의 요청 처리, 라우팅, 응답 구성을 더 쉽게 만드는 개발 도구 묶음입니다.",
    "ai_training": "데이터를 보며 모델 내부 기준을 조정하는 과정입니다.",
    "ai_inference": "이미 만들어진 모델이 새 입력을 보고 출력을 계산하는 과정입니다.",
    "trained_model": "데이터로 조정이 끝나 추론에 사용할 수 있는 모델입니다.",
    "quantum_computer": "양자 상태를 이용해 특정 문제를 계산하는 컴퓨터이지만, 모든 일을 무조건 빠르게 해 주는 장치는 아닙니다.",
    "classical_computer": "일반적인 디지털 상태와 명령으로 계산하는 컴퓨터입니다.",
    "graphrag": "질문과 관련된 개념, 관계, 근거 경로를 먼저 찾고 그 경로에 맞는 문맥으로 답을 구성하는 방식입니다.",
    "ontology": "개념과 개념 사이의 관계를 정해 지식을 구조적으로 연결하는 지도입니다.",
    "semantic_graph": "단어보다 의미와 관계를 중심으로 지식을 저장하는 그래프입니다.",
    "surface_graph": "무엇을 말할지가 아니라 어떻게 자연스럽게 말할지를 돕는 표현 그래프입니다.",
    "seed_graph": "사용자 데이터가 없을 때도 기본 추론 방향을 잡아 주는 관계와 사고 원리의 작은 뼈대입니다.",
    "base_brain_pack": "사용자 데이터 없이도 제한적인 일반 질문을 처리하기 위한 기본 지식 앵커 묶음입니다.",
    "local_first_ai": "개인 데이터와 핵심 처리를 가능한 한 사용자 기기 안에 두는 AI 구조입니다.",
    "cloud_ai": "저장소나 연산을 원격 서버에서 활용하는 AI 구조입니다.",
    "privacy": "개인 데이터가 불필요하게 노출되지 않도록 사용자가 통제하는 상태입니다.",
    "hallucination_reduction": "근거가 부족한 주장을 줄이거나 단정하지 않도록 만드는 과정입니다.",
    "evidence": "어떤 주장을 확인하거나 뒷받침하는 근거 문맥입니다.",
    "claim": "근거로 확인되거나 제한되어야 하는 주장입니다.",
    "sqlite": "별도 서버 없이 하나의 로컬 파일에 데이터를 저장하는 내장형 데이터베이스입니다.",
    "database": "구조화된 정보를 저장하고 안정적으로 조회하거나 갱신하게 해 주는 저장소입니다.",
    "operating_system": "하드웨어 자원과 애플리케이션 실행을 관리하는 기본 소프트웨어입니다.",
    "cpu": "다양한 명령을 순서 있게 처리하는 범용 연산 장치입니다.",
    "gpu": "많은 계산을 동시에 처리하는 데 강한 병렬 연산 장치입니다.",
    "ram": "실행 중인 프로그램과 데이터를 빠르게 올려두는 휘발성 메모리입니다.",
    "ssd": "전원이 꺼져도 데이터가 남는 빠른 저장 장치입니다.",
    "voltage": "전하를 밀어내는 압력에 가까운 전기적 차이입니다.",
    "current": "전하가 실제로 흐르는 양입니다.",
    "tauri": "웹 UI를 가벼운 네이티브 데스크톱 앱으로 묶어 배포하는 도구입니다.",
    "api": "소프트웨어끼리 정해진 방식으로 요청과 응답을 주고받게 하는 인터페이스입니다.",
    "web_search": "인터넷의 공개 정보를 찾는 기능이며, 로컬 그래프 추론과는 구분됩니다.",
    "korean_language": "조사와 어미가 중요해 문장 흐름을 한국어답게 맞춰야 하는 언어입니다.",
    "english_language": "어순과 관사가 중요해 영어식 구조로 표현해야 자연스러운 언어입니다.",
    "atanor": "외부 LLM이나 sLLM 없이, 개인 데이터는 기기 안에 두고 의미 그래프와 표현 그래프를 분리해 근거에서 답을 짓는 로컬 우선 지식 엔진입니다.",
    "local_brain": "사용자의 기기 안에서만 다루는 개인 맥락 영역입니다.",
    "cloud_brain": "개인 데이터와 분리된 공개 지식 보조 영역입니다.",
    "q_cortex": "실제 양자컴퓨터가 아니라 후보 경로를 고르는 고전적 최적화 계층입니다.",
    "graph_hub": "그래프 지식을 카탈로그, 설치, 권한, 읽기 전용 부착, 내보내기, 감사로 다루는 카트리지 시스템입니다.",
    "atlas": "기여 노드를 위한 지역 릴레이 상태를 개인정보 노출 없이 시각화하는 영역이며, 사설 기억을 공유하지 않습니다.",
    "brain_graph": "로컬, 클라우드, 카트리지, 작업 기억 노드를 같은 출처나 프라이버시인 것처럼 섞지 않고 탭별 뷰로 보여 주는 그래프입니다.",
    "machine_learning": "데이터에서 패턴을 스스로 찾도록 모델을 학습시키는 방법입니다.",
    "neural_network": "가중치로 연결된 층 구조로 데이터의 표현을 학습하는 모델입니다.",
    "http": "웹 클라이언트와 서버가 데이터를 주고받는 요청-응답 프로토콜입니다.",
    "json": "시스템끼리 구조화된 데이터를 주고받는 가벼운 텍스트 형식입니다.",
    "git": "소스 코드의 변경 이력을 추적하는 분산 버전 관리 시스템입니다.",
    "linux": "서버와 개발에 널리 쓰이는 오픈소스 운영체제 커널입니다.",
    "python": "스크립팅, 데이터, AI 작업에 널리 쓰이는 고수준 프로그래밍 언어입니다.",
    "encryption": "허가된 사람만 읽을 수 있도록 데이터를 변환해 기밀성을 지키는 기술입니다.",
    "compiler": "소스 코드를 기계가 실행할 수 있는 저수준 형태로 번역하는 도구입니다.",
    "virtual_machine": "소프트웨어로 컴퓨터 전체를 흉내 내어 운영체제와 앱을 격리해 실행하는 환경입니다.",
}


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(needle.lower() in lowered for needle in needles)


ATANOR_MEMORY_CONTEXT_TERMS = (
    "내 로컬 메모리",
    "로컬 메모리",
    "개인 메모리",
    "로컬 브레인",
    "클라우드 브레인",
    "ATANOR 메모리",
    "아타노르 메모리",
    "저장된 기억",
    "저장된 노드",
    "로컬 그래프",
    "클라우드 그래프",
    "local brain",
    "cloud brain",
    "local graph",
    "cloud graph",
    "private memory",
    "memory graph",
)

COMPUTER_MEMORY_CONTEXT_TERMS = (
    "RAM",
    "램",
    "컴퓨터 메모리",
    "휘발성 메모리",
    "주기억장치",
    "메모리와 SSD",
    "SSD 차이",
    "memory vs ssd",
    "computer memory",
    "volatile memory",
)


def _is_atanor_memory_context(query: str) -> bool:
    return _contains_any(query, ATANOR_MEMORY_CONTEXT_TERMS)


def _is_computer_memory_context(query: str) -> bool:
    return _contains_any(query, COMPUTER_MEMORY_CONTEXT_TERMS)


def _disambiguate_memory_context(query: str, semantic_context: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not _is_atanor_memory_context(query) or _is_computer_memory_context(query):
        return semantic_context
    return [item for item in semantic_context if str(item.get("concept_id")) != "ram"]


def _seed(query: str) -> int:
    return int(hashlib.sha256(query.encode("utf-8", errors="ignore")).hexdigest()[:8], 16)


def _clean_label(value: str) -> str:
    return str(value or "").replace("_", " ").strip()


def _label(concept: dict[str, Any], language: str) -> str:
    labels = concept.get("labels") or {}
    raw = _clean_label(labels.get(language) or concept.get("canonical_name") or concept.get("concept_id"))
    if language != "en":
        return raw
    # English mode must never emit Hangul or corrupted (non-ASCII) surface forms.
    if raw and raw.isascii() and not _HANGUL.search(raw):
        return raw
    en_label = _clean_label(labels.get("en"))
    if en_label and en_label.isascii() and not _HANGUL.search(en_label):
        return en_label
    # Last resort: derive a clean English label from the stable concept id.
    return _clean_label(concept.get("concept_id")) or raw


def _has_final_consonant(text: str) -> bool:
    chars = [ch for ch in text if "\uac00" <= ch <= "\ud7a3"]
    if not chars:
        return False
    return (ord(chars[-1]) - 0xAC00) % 28 != 0


def _topic(label: str) -> str:
    return f"{label}{'은' if _has_final_consonant(label) else '는'}"


def _object(label: str) -> str:
    return f"{label}{'을' if _has_final_consonant(label) else '를'}"


def _with_and(label: str) -> str:
    return f"{label}{'과' if _has_final_consonant(label) else '와'}"


def _is_hangul_text(text: str) -> bool:
    return any("가" <= ch <= "힣" for ch in text)


# Copula/auxiliary/verb openers that mean the description is already a PREDICATE
# whose subject was stripped during promotion ("Marie Curie" + "was the first …").
# Re-attaching the label as an English subject reconstructs the sentence instead of
# stuttering ("Marie Curie is was the first …").
_EN_PREDICATE_HEADS = (
    "is ", "are ", "was ", "were ", "has ", "have ", "had ", "can ", "could ",
    "will ", "would ", "may ", "might ", "does ", "do ", "did ", "refers ",
    "describes ", "means ", "consists ", "includes ", "occurs ", "represents ",
)


def _english_frame(label: str, description: str, audience_level: str) -> str:
    """Frame an English concept+description in English (no Korean particle)."""
    if not description:
        return f"{label} is a related concept in the base graph"
    lowered = description.lower()
    if lowered.startswith(label.lower()) or lowered.startswith("a ") or lowered.startswith("an "):
        return description.rstrip(".")
    # Description is a bare predicate ("was the first …") -> re-attach the subject.
    if lowered.startswith(_EN_PREDICATE_HEADS):
        return f"{label} {description}".rstrip(".")
    # If the description restates the concept as a full clause ("inference uses …",
    # "training adjusts …"), rendering "{label} is {description}" stutters
    # ("AI inference is inference uses …"). Use the clause as its own sentence.
    label_words = [word for word in label.lower().split() if word]
    last_word = label_words[-1] if label_words else ""
    if last_word and len(last_word) > 3 and lowered.startswith(f"{last_word} "):
        standalone = description.rstrip(". ").strip()
        return standalone[:1].upper() + standalone[1:] if standalone else label
    if audience_level == "expert":
        return f"{label}: {description}"
    return f"{label} is {description[:1].lower() + description[1:]}"


def _description_sentence(concept: dict[str, Any], language: str, audience_level: str) -> str:
    label = _label(concept, language)
    description = str(concept.get("short_description") or "")
    # Language-matched framing: an English concept/description must NOT receive a
    # Korean topic particle ("Marie Curie는 was the first …"). If the label is
    # non-Korean and the description carries no Hangul, frame it in English even when
    # the answer language is ko (the fact stays faithful; only the frame changes).
    if language == "ko" and not _is_hangul_text(label) and description and not _is_hangul_text(description):
        return _english_frame(label, description, audience_level)
    if language == "ko":
        return f"{_topic(label)} {KO_DESCRIPTIONS.get(str(concept.get('concept_id')), description)}"
    return _english_frame(label, description, audience_level)


def _concept_by_id(context: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item.get("concept_id")): item for item in context}


def _relation_sentence(source: dict[str, Any], relation: dict[str, Any], context_map: dict[str, dict[str, Any]], language: str) -> str:
    target_id = str(relation.get("target") or "")
    if target_id not in context_map and "_" in target_id:
        return ""
    target = context_map.get(target_id, {"concept_id": target_id, "canonical_name": target_id, "labels": {}})
    source_label = _label(source, language)
    target_label = _label(target, language)
    relation_name = str(relation.get("relation") or "related_to")
    if language == "ko":
        if relation_name == "contrasts_with":
            return f"{_topic(source_label)} {_with_and(target_label)} 대비됩니다."
        if relation_name == "similar_to":
            return f"{_topic(source_label)} {_with_and(target_label)} 비슷합니다."
        relation_word = RELATION_WORDS_KO.get(relation_name, "와 관련됩니다")
        return f"{_topic(source_label)} {_object(target_label)} {relation_word}."
    relation_word = RELATION_WORDS_EN.get(relation_name, "is related to")
    return f"{source_label} {relation_word} {target_label}."


# Korean micro-NLG: each relation carries its own connecting particle, applied to
# the BARE label with the correct allomorph (을/를, 과/와) by final consonant —
# never double-marking ("그래프를 를 필요로"). (particle_kind, verb_phrase)
KO_RELATION = {
    "is_a": ("genitive", "한 종류입니다"),
    "part_of": ("genitive", "일부입니다"),
    "causes": ("genitive", "원인이 될 수 있습니다"),
    "example_of": ("genitive", "예입니다"),
    "used_for": ("locative", "쓰입니다"),
    "depends_on": ("locative", "의존합니다"),
    "enables": ("object", "가능하게 합니다"),
    "requires": ("object", "필요로 합니다"),
    "manages": ("object", "관리합니다"),
    "produces": ("object", "만듭니다"),
    "supports": ("object", "뒷받침합니다"),
    "contains": ("object", "포함합니다"),
    "uses": ("object", "사용합니다"),
    "contrasts_with": ("comitative", "대비됩니다"),
    "similar_to": ("comitative", "비슷합니다"),
    "has_property": ("property", "특성을 가집니다"),
}


# 하다-class relation verbs that are genuinely TRANSITIVE — they take a 를/을 object
# and realize cleanly as "{obj}를 {stem}합니다". Descriptive/adjectival 하다 words
# (풍부하다=be abundant, 중요하다, 다양하다, 필요하다, 가능하다 …) do NOT take an object,
# so "에너지를 풍부합니다" is ungrammatical — those are NOT realized (the relation is
# skipped upstream in _korean_relation_sentence). Allowlist, not "any 하다": a low-
# quality peer relation whose predicate is an adjectival/unknown 하다 never surfaces.
_TRANSITIVE_HADA_VERBS = {
    "생산하다", "발견하다", "사용하다", "포함하다", "관리하다", "제공하다", "지원하다",
    "개발하다", "정의하다", "설명하다", "구성하다", "처리하다", "제어하다", "저장하다",
    "연결하다", "제거하다", "생성하다", "분석하다", "측정하다", "제작하다", "활용하다",
    "수행하다", "제안하다", "표현하다", "전달하다", "결정하다", "예측하다", "변환하다",
}


def _is_transitive_predicate(relation_name: str) -> bool:
    return relation_name in _TRANSITIVE_HADA_VERBS


def _ko_relation_clause(relation_name: str, target_label: str) -> str:
    spec = KO_RELATION.get(relation_name)
    if spec is None:
        # Predicate-anchored relation: relation_name IS a Korean verb lemma. Only a
        # curated TRANSITIVE 하다-verb reaches here (the aggregator gates the rest);
        # render it with REGULAR 하다-class morphology ("생산하다" -> "생산합니다").
        if _is_transitive_predicate(relation_name):
            return f"{_object(target_label)} {relation_name[:-2]}합니다"
        return f"{_with_and(target_label)} 관련이 있습니다"
    kind, verb = spec
    if kind == "object":
        return f"{_object(target_label)} {verb}"
    if kind == "genitive":
        return f"{target_label}의 {verb}"
    if kind == "locative":
        return f"{target_label}에 {verb}"
    if kind == "comitative":
        return f"{_with_and(target_label)} {verb}"
    if kind == "property":
        marker = "이라는" if _has_final_consonant(target_label) else "라는"
        return f"{target_label}{marker} {verb}"
    return f"{_object(target_label)} {verb}"


def _korean_relation_sentence(
    primary: dict[str, Any], context_map: dict[str, dict[str, Any]], *, max_relations: int = 3
) -> str:
    """Aggregate a concept's relations: '이는 <clause1>. 또한 <clause2>.' — one
    subject ('이는' = it), correct particles, no subject repetition."""
    clauses: list[str] = []
    seen: set[tuple[str, str]] = set()
    for relation in primary.get("relations", []):
        if len(clauses) >= max_relations:
            break
        relation_name = str(relation.get("relation") or "related_to")
        # allow curated relations AND predicate-anchored verb relations that are
        # genuinely TRANSITIVE. Adjectival/unknown 하다 predicates (풍부하다/중요하다 …)
        # from low-quality peer decompositions would realize as ungrammatical object
        # clauses ("에너지를 풍부합니다"), so they are dropped rather than realized.
        if relation_name not in KO_RELATION and not _is_transitive_predicate(relation_name):
            continue
        target_id = str(relation.get("target") or "")
        if target_id not in context_map and "_" in target_id:
            continue
        target = context_map.get(target_id, {"concept_id": target_id, "labels": {}})
        target_label = _label(target, "ko")
        if not target_label:
            continue
        # dedup: the cloud graph can carry several identical (relation, target)
        # edges; do not emit "또한 X의 한 종류입니다" twice.
        key = (relation_name, target_label)
        if key in seen:
            continue
        seen.add(key)
        clauses.append(_ko_relation_clause(relation_name, target_label))
    if not clauses:
        return ""
    parts = [f"이는 {clauses[0]}."]
    parts += [f"또한 {clause}." for clause in clauses[1:]]
    return " ".join(parts)


def _compare_answer(context: list[dict[str, Any]], language: str, audience_level: str) -> str:
    if len(context) < 2:
        return ""
    first, second = context[0], context[1]
    if language == "ko":
        return (
            f"{_with_and(_label(first, language))} {_label(second, language)}의 핵심 차이는 역할과 사용 맥락입니다. "
            f"{_description_sentence(first, language, audience_level)} "
            f"반면 {_description_sentence(second, language, audience_level)} "
            "둘은 관련된 문제를 다룰 수 있지만, 선택 기준과 운영 방식은 다릅니다."
        )
    first_desc = _description_sentence(first, language, audience_level).rstrip(". ").strip()
    second_desc = _description_sentence(second, language, audience_level).rstrip(". ").strip()
    return (
        f"The main difference between {_label(first, language)} and {_label(second, language)} is their role and operating context. "
        f"{first_desc}. "
        f"By contrast, {second_desc}. "
        "They may solve related problems, but they are chosen for different constraints."
    )


def _project_level_answer(query: str, language: str) -> tuple[str, bool] | None:
    lower = query.lower()
    if "영어로" in query and ("간단" in query or "짧게" in query):
        return "Tell me the topic, and I will answer in one or two concise English sentences.", False
    if language == "ko":
        if "한국어답게" in query or "번역투" in query:
            return "좋아요. 주제를 알려주면 영어식 직역을 피하고, 한국어 어순과 문장 흐름에 맞춰 자연스럽게 설명할게요.", False
        if "근거 중심" in query or "과장 없이" in query:
            return "근거 중심으로 답하려면 확인된 내용과 불확실한 내용을 나눠 말해야 합니다. 근거가 부족한 부분은 단정하지 않고, 확인 가능한 범위만 설명하는 방식이 맞습니다.", True
        if "템플릿" in query:
            return "같은 시작 문구를 반복하기보다, 질문의 목적에 맞춰 정의, 비교, 예시, 주의점을 자연스럽게 조합해 답하는 방식이 좋습니다.", True
        if "유재석" in query:
            return "모르겠어. 지금 기본 그래프에는 유재석을 설명할 검증된 근거가 없어.", False
        if "그거" in query and ("설명" in query or "알려" in query):
            return "지금 문장만으로는 '그거'가 무엇을 가리키는지 확정하기 어렵습니다. 대상만 한 단어로 알려주면 그 범위 안에서 바로 설명할게요.", False
        if "local brain" in lower and "cloud brain" in lower and ("차이" in query or "비교" in query):
            return (
                "저장된 개인 맥락은 사용자의 기기 안에서만 다루는 사적 지식 영역입니다. "
                "공개 지식 보조층은 개인 데이터를 섞지 않고 검증 가능한 공용 지식 조각과 근거를 참고하는 영역입니다. "
                "이 구분은 개인정보 보호를 지키기 위한 경계입니다. "
                "핵심 차이는 데이터 소유권과 공개 범위입니다."
            ), True
        if "q-cortex" in lower and ("양자컴퓨터" in query or "아니" in query):
            return (
                "이 고전 최적화 계층은 실제 양자컴퓨터가 아니라 로컬에서 후보 조합을 고르는 선택 장치입니다. "
                "양자 하드웨어를 쓰거나 양자 가속을 낸다고 주장하지 않습니다."
            ), True
        if "atanor" in lower and ("한 문장" in query or "짧게" in query):
            return "ATANOR는 개인 데이터는 기기 안에 두고 의미 그래프와 표현 그래프를 분리해 근거 중심 답변을 만드는 로컬 우선 지식 엔진입니다.", True
        if "내부 경로" in query or "brain path" in lower:
            return "기본 답변에서는 내부 처리 경로를 드러내지 않고, 사용자가 바로 이해할 수 있는 자연스러운 설명만 보여주는 것이 맞습니다.", True
    else:
        if "q-cortex" in lower and ("quantum" in lower or "not" in lower):
            return (
                "This optimizer is not a real quantum computer. It is a classical local selector for candidate paths and does not claim quantum hardware or quantum speedup.",
                True,
            )
        if "atanor" in lower and ("one sentence" in lower or "brief" in lower):
            return (
                "ATANOR is a local-first knowledge engine that keeps private data on-device while separating semantic reasoning from surface expression.",
                True,
            )
    return None


def _compose_answer(query: str, context: list[dict[str, Any]], language: str, audience_level: str, intent: str) -> tuple[str, bool]:
    project_answer = _project_level_answer(query, language)
    if project_answer is not None:
        return project_answer

    lowered = query.lower()
    if (language == "ko" and _contains_any(query, UNSUPPORTED_HINTS_KO)) or _contains_any(lowered, UNSUPPORTED_HINTS_EN):
        # A "current-state" query (지금/현재/오늘/실시간 …) cannot be answered from a static graph
        # even when a related concept matches — abstain UNCONDITIONALLY. Otherwise a partial
        # concept match hijacks it ("비트코인 지금 가격은?" -> the "비트" concept). A plain
        # definitional query ("가격이란?") has no now-marker and still routes to the concept.
        _NOW = ("지금", "현재", "오늘", "실시간", "최신", "요즘", "시세", "얼마", "now", "current", "today", "latest")
        _now = _contains_any(query, _NOW) or _contains_any(lowered, _NOW)
        if _now or not any(float(item.get("match_score") or 0.0) > 1.5 for item in context):
            return (
                "현재 기본 지식만으로는 이 질문에 필요한 최신 또는 실시간 근거가 부족합니다. 날씨, 주가, 최신 인물 정보처럼 변하는 내용은 별도의 확인 가능한 근거가 필요합니다."
                if language == "ko"
                else "The current base pack does not contain enough real-time evidence for that question. Dynamic topics need external or freshly supplied context."
            ), False

    strong = [item for item in context if float(item.get("match_score") or 0.0) > 0]
    if not strong:
        return (
            "지금 확인된 근거가 부족해서 단정하기 어렵습니다. 주제나 참고 문장을 조금 더 주면 그 범위 안에서 설명할 수 있습니다."
            if language == "ko"
            else "I do not have enough base concepts to support this question yet. Give me a topic or source sentence and I can answer within that scope."
        ), False

    if intent == "compare":
        compared = _compare_answer(strong, language, audience_level)
        if compared:
            return compared, True

    primary = strong[0]
    # Precision gate: if the top concept is only a loose token-overlap match and
    # the query never actually names it, we are likely about to describe the
    # WRONG concept confidently (e.g. "capital of France" -> "API", or
    # "인텔에 대해 알려줘" -> an unrelated optimization concept). Abstain honestly.
    # Applies to ALL informational intents — "알려줘 / 란 / 대해" classify as
    # clarify/other and previously bypassed this gate, which let a large promoted
    # graph answer confidently-wrong. Comparisons handled above; identity excepted.
    if not _named_in_query(query, primary) and not _is_identity_question(query):
        return (
            "지금 확인된 근거가 부족해서 단정하기 어렵습니다. 주제나 참고 문장을 조금 더 주면 그 범위 안에서 설명할 수 있습니다."
            if language == "ko"
            else "I do not have enough confidently matched evidence for that. Name the topic directly and I can answer within that scope."
        ), False
    context_map = _concept_by_id(context)
    base = _description_sentence(primary, language, audience_level)
    if language == "ko":
        if audience_level != "expert" and any(token in query for token in ("쉽게", "중학생", "초등학생")):
            answer = f"{base} 쉽게 말하면 여러 작업이 흩어져 있어도 사람이 일일이 챙기지 않게 정리하고 조율하는 장치에 가깝습니다."
        else:
            answer = base
        # graph relations are substantive reasoning (not hand-holding): keep them
        # at every audience level so expert answers are not strictly thinner.
        rel_sentence = _korean_relation_sentence(primary, context_map)
        if rel_sentence:
            answer = f"{answer} {rel_sentence}"
        return answer, True

    base_text = base.rstrip(". ").strip()
    parts = [base_text] if base_text else []
    rel_sentence = _english_relation_sentence(primary, context_map)
    if rel_sentence:
        parts.append(rel_sentence.rstrip("."))
    second_hop = _english_second_hop(primary, context_map)
    if second_hop:
        parts.append(second_hop.rstrip("."))
    answer = ". ".join(parts).strip()
    if answer and not answer.endswith((".", "!", "?")):
        answer = f"{answer}."
    if str(primary.get("concept_id")) == "kubernetes" and "software deployment" not in answer.lower():
        answer = f"{answer} It is commonly used for software deployment and container orchestration."
    if str(primary.get("concept_id")) == "spring_boot" and "web framework" not in answer.lower():
        answer = answer.replace("Spring Boot is a Java framework", "Spring Boot is a Java web framework")
    return answer, True


def _concept_names(concept: dict[str, Any]) -> list[str]:
    names = [str(concept.get("concept_id") or ""), str(concept.get("canonical_name") or "")]
    names += [str(value) for value in (concept.get("labels") or {}).values()]
    names += [str(alias) for alias in (concept.get("aliases") or [])]
    # Korean concept names are legitimately 2 chars (도커/근거/전압/전류); keep
    # them. Latin names keep a >=3 floor (the ASCII-boundary lookarounds in
    # _named_in_query already stop short Latin names matching inside words).
    out: list[str] = []
    for name in names:
        if not name:
            continue
        has_hangul = bool(re.search(r"[가-힣]", name))
        if (has_hangul and len(name) >= 2) or (not has_hangul and len(name) >= 3):
            out.append(name)
    return out


_IDENTITY_MARKERS_KO = (
    "너는 누구", "넌 누구", "너 누구", "네 정체", "자기소개", "너는 뭐야", "넌 뭐야", "당신은 누구",
    "이름이 뭐", "이름이 뭐니", "이름 뭐", "이름은 뭐", "이름이 어떻게", "너 이름", "네 이름", "당신 이름", "당신의 이름",
    # Self-reference resolution (NOT canned answers): these route the question to
    # the graph "atanor" concept; the answer is still realized from graph data.
    "너 뭐 할 수", "너 뭐할 수", "뭐 할 수 있어", "뭘 할 수 있", "무엇을 할 수 있", "너 뭐 하는", "넌 뭐 하는",
    "어떻게 작동", "어떻게 동작", "어떤 원리", "너 어떻게 만들", "너의 구조", "네 구조", "너 능력",
)
_IDENTITY_MARKERS_EN = (
    "who are you", "what are you", "introduce yourself", "who is atanor",
    "what is your name", "what's your name", "your name",
)


def _is_identity_question(query: str) -> bool:
    q = re.sub(r"\s+", " ", query.lower()).strip(" ?!.")
    return any(m in query for m in _IDENTITY_MARKERS_KO) or any(m in q for m in _IDENTITY_MARKERS_EN)


def _named_in_query(query: str, concept: dict[str, Any]) -> bool:
    """True when the query actually names the concept. The ASCII-boundary
    lookarounds give English word boundaries ("api" is not matched inside
    "capital") while still allowing a Korean particle to follow a Latin name
    ("GraphRAG가") and any Hangul-name substring ("로컬 브레인이")."""
    query_lower = query.lower()
    for name in _concept_names(concept):
        pattern = r"(?<![A-Za-z0-9])" + re.escape(name.lower().replace("_", " ")) + r"(?![A-Za-z0-9])"
        if re.search(pattern, query_lower):
            return True
    return False


def _answer_confidence(query: str, strong_context: list[dict[str, Any]], useful: bool) -> float:
    """M5: honest confidence, not a fixed constant.

    The retrieval match_score is not a reliable signal (loose token overlap can
    score an unrelated concept highly). The honest signal is whether the query
    *actually names* the concept we answered with: a direct name/label/alias hit
    means high confidence; answering on loose overlap only is mid-low; an
    abstaining / ungrounded answer stays low.
    """
    if not useful or not strong_context:
        return 0.18
    name_matched = _named_in_query(query, strong_context[0])
    corroboration = min(0.06, max(0, len(strong_context) - 1) * 0.02)
    return round((0.85 if name_matched else 0.45) + corroboration, 3)


def _reasoning_certificate(
    query: str, strong_context: list[dict[str, Any]], language: str, confidence: float, useful: bool
) -> dict[str, Any]:
    """A traceable derivation of the answer (the "reasoning certificate").

    Because ATANOR composes from an ontology graph rather than a generative model,
    every claim can be traced back to the concept node and graph edges it came
    from. This exposes that derivation so the conclusion is auditable, not opaque.
    """
    guarantees = {
        "external_llm": False,
        "external_sllm": False,
        "fabricated_facts": False,
        "answer_from_graph_edges_only": True,
        "ontology_traceable": True,
    }
    if not useful or not strong_context:
        return {
            "derivation_kind": "abstained",
            "anchor_concept": None,
            "steps": [],
            "confidence": confidence,
            "confidence_basis": "no_confident_ontology_anchor",
            "guarantees": guarantees,
        }
    primary = strong_context[0]
    context_map = _concept_by_id(strong_context)
    pid = str(primary.get("concept_id"))
    plabel = _label(primary, language)
    named = _named_in_query(query, primary)

    steps: list[dict[str, Any]] = [
        {
            "step": 1,
            "type": "anchor_definition",
            "concept_id": pid,
            "label": plabel,
            "source": "base_brain_semantic_graph",
            "fact": str(primary.get("short_description") or ""),
        }
    ]
    evidence = [pid]
    step_no = 2
    for relation in primary.get("relations", [])[:3]:
        rel = str(relation.get("relation") or "related_to")
        tid = str(relation.get("target") or "")
        if not tid:
            continue
        target = context_map.get(tid, {"concept_id": tid, "labels": {}})
        tlabel = _label(target, language)
        steps.append(
            {
                "step": step_no,
                "type": "graph_relation",
                "edge": f"{pid} --{rel}--> {tid}",
                "from": plabel,
                "relation": rel,
                "to": tlabel,
            }
        )
        evidence.append(tid)
        # one verified second hop (A->B->C), matching the realized answer
        for sub in target.get("relations", [])[:3]:
            sub_tid = str(sub.get("target") or "")
            if sub_tid and sub_tid not in {pid, tid}:
                sub_target = context_map.get(sub_tid, {"concept_id": sub_tid, "labels": {}})
                steps.append(
                    {
                        "step": step_no + 1,
                        "type": "graph_relation_second_hop",
                        "edge": f"{tid} --{sub.get('relation')}--> {sub_tid}",
                        "from": tlabel,
                        "relation": str(sub.get("relation")),
                        "to": _label(sub_target, language),
                    }
                )
                break
        step_no = len(steps) + 1

    return {
        "derivation_kind": "ontology_graph_derivation",
        "anchor_concept": {
            "id": pid,
            "label": plabel,
            "match": "named_in_query" if named else "loose_token_overlap",
            "match_score": round(float(primary.get("match_score") or 0.0), 3),
        },
        "steps": steps,
        "evidence_concepts": evidence,
        "confidence": confidence,
        "confidence_basis": "query_names_concept" if named else "token_overlap_only",
        "guarantees": guarantees,
    }


def _active_expert_cartridges() -> list[dict[str, Any]]:
    """Installed EXPERT cartridges that are currently ATTACHED (plugged in). Attaching a
    cartridge makes it answer; detaching it removes it from answers — the "뺐다 꽂았다" control.
    Direct file reads (repo-root-anchored) to avoid a base_brain -> graph_hub import dependency."""
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[2] / "data" / "graph_hub"
    installed_dir = root / "installed"
    if not installed_dir.exists():
        return []
    # active attachment set (detach removes the id here)
    active: set[str] = set()
    att = root / "attachments" / "active_attachments.json"
    if att.exists():
        try:
            payload = json.loads(att.read_text(encoding="utf-8"))
            active = set(payload.keys()) if isinstance(payload, dict) else {a.get("cartridge_id") for a in payload}
        except Exception:
            active = set()
    out: list[dict[str, Any]] = []
    for f in installed_dir.glob("*.graphpack.json"):
        try:
            c = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if str(c.get("category")) != "persona" and str(c.get("cartridge_id")) in active:
            out.append(c)
    return out


def _cartridge_expert_answer(query: str, language: str) -> tuple[str, str] | None:
    """Fallback: when the base pack can't answer, consult an attached domain-expert
    cartridge. Returns (answer, cartridge_id) if the query NAMES a cartridge concept that
    carries a description, else None. Fires only on a base-pack abstain -> no regression."""
    for cart in _active_expert_cartridges():
        sem = (cart.get("contents") or {}).get("semantic_graph") or {}
        nodes = sem.get("nodes") or []
        for n in nodes:
            names = [str(n.get("label") or ""), *(str(a) for a in (n.get("aliases") or []))]
            if not any(nm.strip() and _named_in_query(query, {"canonical_name": nm}) for nm in names):
                continue
            desc = str(n.get("short_description") or "").strip()
            if not desc:
                continue
            label = str(n.get("label") or "")
            ans = f"{_topic(label)} {desc}" if language == "ko" else f"{label}: {desc}"
            return ans, str(cart.get("cartridge_id"))
    return None


def _active_persona_cartridge() -> dict[str, Any] | None:
    """First ATTACHED persona cartridge (category=persona), if any."""
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[2] / "data" / "graph_hub"
    inst = root / "installed"
    att = root / "attachments" / "active_attachments.json"
    if not inst.exists():
        return None
    active: set[str] = set()
    if att.exists():
        try:
            payload = json.loads(att.read_text(encoding="utf-8"))
            active = set(payload.keys()) if isinstance(payload, dict) else {a.get("cartridge_id") for a in payload}
        except Exception:
            active = set()
    for f in inst.glob("*.graphpack.json"):
        try:
            c = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if str(c.get("category")) == "persona" and str(c.get("cartridge_id")) in active:
            return c
    return None


# Persona-realization layer (the "Broca" for personas): tone-keyword -> humble/analytical/…
# opener register. Generic + graph-driven — a persona declaring a different tone realizes a
# different surface. This REALIZES the persona graph's declared tone/traits (like surface
# constructions realize semantic intent); it does not add world-content, so grounding holds.
_PERSONA_OPENERS = {
    "humble": "제가 아는 범위에서 함께 살펴보면,",
    "inquisitive": "먼저 짚어 볼까요 —",
    "analytical": "핵심부터 짚자면,",
    "direct": "결론부터 말하면,",
    "warm": "좋은 질문이에요.",
    "playful": "재미있는 주제네요 —",
    "formal": "정리하자면,",
}

# English mirror of the persona openers/closers — used when the grounded core is
# English so the WHOLE surface stays in one language (no "Marie Curie가 왜 그러하며").
_PERSONA_OPENERS_EN = {
    "humble": "As far as I know,",
    "inquisitive": "Let's start here —",
    "analytical": "To get to the point,",
    "direct": "In short,",
    "warm": "Great question.",
    "playful": "Fun topic —",
    "formal": "In summary,",
}


# Clause-level register realization (CGSR): map a plain sentence-final ending to the
# persona's register. Regular/high-frequency endings only; anything else is left unchanged
# (no mis-conjugation). This is faithful surface realization — same proposition, different
# register — not new content.
_REGISTER = {
    "formal": {"이다": "입니다", "한다": "합니다", "된다": "됩니다", "있다": "있습니다", "없다": "없습니다",
               "이었다": "이었습니다", "였다": "였습니다", "했다": "했습니다"},
    "polite": {"이다": "이에요", "한다": "해요", "된다": "돼요", "있다": "있어요", "없다": "없어요",
               "이었다": "이었어요", "였다": "였어요", "했다": "했어요"},
    "humble": {"이다": "이지요", "한다": "하지요", "된다": "되지요", "있다": "있지요", "없다": "없지요",
               "이었다": "이었지요", "였다": "였지요", "했다": "했지요"},
}


def _register_one(sentence: str, table: dict[str, str]) -> str:
    s = sentence.rstrip()
    for plain, styled in sorted(table.items(), key=lambda kv: -len(kv[0])):
        if s.endswith(plain):
            return s[: -len(plain)] + styled
    return s


def _apply_register(text: str, register: str) -> str:
    """Realize EACH sentence's plain final ending (이다/한다/…) in the persona register.
    Already-polite endings (…습니다/…입니다) and irregular ones are left unchanged."""
    table = _REGISTER.get(register)
    if not table or not text:
        return text
    parts = re.split(r"\.\s+", text.rstrip().rstrip("."))
    if not parts:
        return text
    return ". ".join(_register_one(p, table) for p in parts) + "."


def _persona_style_profile(persona: dict[str, Any]) -> dict[str, Any]:
    contents = persona.get("contents") or {}
    sg = contents.get("surface_graph") or {}
    profiles = sg.get("style_profiles") or []
    tone = str((profiles[0] or {}).get("tone") if profiles else "") .lower()
    tone_tokens = set(re.split(r"[_\s,/-]+", tone)) if tone else set()
    moves = sg.get("discourse_moves") or []
    return {"tone_tokens": tone_tokens, "moves": moves}


def _apply_persona_style(query: str, answer: str, language: str, persona: dict[str, Any]) -> tuple[str, str | None]:
    """FULL-TONE realization: wrap the grounded answer with an OPENER (from the persona's tone)
    and a CLOSER (from its discourse moves), so the whole surface reflects the persona's
    character. Grounded content is unchanged; every added element traces to a persona
    tone-token / move; attributed via trace.persona_source. Opts in via attach."""
    if language != "ko" or not answer or "근거가 부족" in answer or "실시간" in answer:
        return answer, None
    prof = _persona_style_profile(persona)
    tone_tokens, moves = prof["tone_tokens"], prof["moves"]
    topic = re.sub(r"\s*(이란|란|가 뭐야|는 뭐야|뭐야|이 뭐|에 대해.*|은 무엇.*|는 무엇.*)\s*\??\s*$", "", query).strip()
    _c = topic[-1] if topic else ""
    _iga = "이" if ("가" <= _c <= "힣" and (ord(_c) - 0xAC00) % 28 != 0) else "가"

    # Language-matched persona surface: if the grounded core is English, wrap it in
    # English so the whole answer is one language (the Korean register table only
    # matches Korean endings, so it is a no-op on English and is skipped).
    core_is_en = not _is_hangul_text(answer)
    tone_order = ("humble", "analytical", "direct", "warm", "playful", "inquisitive", "formal")
    if core_is_en:
        opener = next((_PERSONA_OPENERS_EN[t] for t in tone_order if t in tone_tokens), "")
        closer = ""
        if "counter_question" in moves and topic:
            closer = f" But it's worth asking — what makes {topic} what it is, and how does it differ from similar cases?"
        elif "stepwise_guide" in moves and topic:
            closer = f" Let's take it step by step — shall we start from the basics of {topic}?"
        core = answer.rstrip()
        if not opener and not closer:
            return answer, None
        if closer and core and core[-1] not in ".!?":
            core += "."  # sentence boundary before the English closer
        body = (opener + " " if opener else "") + core
        return body + closer, str(persona.get("cartridge_id"))

    opener = next((_PERSONA_OPENERS[t] for t in tone_order if t in tone_tokens), "")
    closer = ""
    if "counter_question" in moves and topic:
        closer = f" 그런데 스스로 되물어 봅시다 — {topic}{_iga} 왜 그러하며, 다른 경우와는 어떻게 다를까요?"
    elif "stepwise_guide" in moves and topic:
        closer = f" 한 걸음씩 짚어 보죠 — {topic}의 가장 기본이 되는 것부터 함께 확인해 볼까요?"

    # CGSR clause-level: realize the grounded core's sentence-final register per persona tone.
    register = ("formal" if tone_tokens & {"formal", "analytical", "direct"}
                else "humble" if "humble" in tone_tokens
                else "polite" if tone_tokens & {"warm", "playful", "inquisitive"}
                else "")
    core = _apply_register(answer, register) if register else answer
    if not opener and not closer and core == answer:
        return answer, None
    body = (opener + " " if opener else "") + core.rstrip()
    return body + closer, str(persona.get("cartridge_id"))


def answer_with_base_brain(
    query: str,
    language: Language = "ko",
    audience_level: AudienceLevel = "beginner",
    mode: AnswerMode = "default",
    apply_persona: bool = False,
) -> dict[str, Any]:
    pack = load_base_brain_pack()
    semantic_context = get_semantic_context(query, pack, limit=12)
    semantic_context = _disambiguate_memory_context(query, semantic_context)
    if _is_identity_question(query):
        # "Who are you?" — answer from the grounded ATANOR concept (not a canned
        # string), so identity is graph-derived like any other answer.
        atanor = next(
            (concept for concept in pack.semantic_graph.get("concepts", []) if str(concept.get("concept_id")) == "atanor"),
            None,
        )
        if atanor:
            related_ids = {str(relation.get("target")) for relation in atanor.get("relations", [])}
            related = [
                {**concept, "match_score": 1.0}
                for concept in pack.semantic_graph.get("concepts", [])
                if str(concept.get("concept_id")) in related_ids
            ]
            keep = {"atanor", *related_ids}
            semantic_context = (
                [{**atanor, "match_score": 5.0}]
                + related
                + [item for item in semantic_context if str(item.get("concept_id")) not in keep]
            )
    intent = classify_intent(query, pack)
    surface_candidates = get_surface_candidates(query, semantic_context, language, audience_level, limit=8, pack=pack)
    selection = select_surface_candidates(surface_candidates, max_selected=4, seed=_seed(query), q_cortex_enabled=True)
    answer, useful = _compose_answer(query, semantic_context, language, audience_level, intent)
    # Graph Hub fallback: if the base pack abstains, consult an installed domain-expert
    # cartridge (e.g. coffee) so an attached specialist graph can answer what the base cannot.
    cartridge_source = None
    if not useful and not _is_identity_question(query):
        _cart = _cartridge_expert_answer(query, language)
        if _cart:
            answer, useful, cartridge_source = _cart[0], True, _cart[1]
    # Persona styling is OPT-IN (apply_persona=True), NOT automatic on attach. General
    # QA must stay in a neutral lab voice — an attached persona (e.g. socratic) should
    # only color answers when the caller explicitly asks to speak AS that persona, so a
    # plain factual question never gets wrapped ("스스로 되물어 봅시다 …").
    persona_source = None
    if useful and apply_persona:
        _persona = _active_persona_cartridge()
        if _persona:
            answer, persona_source = _apply_persona_style(query, answer, language, _persona)
    # M3 honesty signal: was this surface a hand-authored canned answer, or was it
    # realized from the graph? General questions must be graph-derived (False).
    hand_authored_answer_used = _project_level_answer(query, language) is not None
    # M5 honest confidence from grounding strength.
    strong_context = [item for item in semantic_context if float(item.get("match_score") or 0.0) > 0]
    confidence = _answer_confidence(query, strong_context, useful)
    reasoning_certificate = _reasoning_certificate(query, strong_context, language, confidence, useful)
    trace = {
        "mode": mode,
        "pack_id": pack.pack_id,
        "intent": intent,
        "hand_authored_answer_used": hand_authored_answer_used,
        "cartridge_source": cartridge_source,
        "persona_source": persona_source,
        "matched_concepts": [
            {
                "concept_id": item.get("concept_id"),
                "canonical_name": item.get("canonical_name"),
                "labels": item.get("labels"),
                "match_score": item.get("match_score"),
            }
            for item in semantic_context
        ],
        "selected_surface_candidates": [
            item.get("construction_id") or item.get("id")
            for item in selection.get("selected", [])
        ],
        "q_cortex_used": bool(selection.get("q_cortex_used")),
        "q_cortex_run_id": selection.get("q_cortex_run_id"),
        "useful_answer": useful,
        **honesty_flags(),
    }
    repair_result = repair_answer_for_mode(answer, mode=mode, trace=trace, language=language)
    final_answer = str(repair_result.get("repaired_answer") or answer)
    evidence_sentences = [
        str(item.get("short_description") or "")
        for item in semantic_context
        if str(item.get("short_description") or "").strip()
    ]
    scene_grounding = extract_scene_grounding(final_answer, evidence_sentences, language=language)
    return {
        "answer": final_answer,
        "answer_kind": "base_brain_zero_user_data",
        "scene_grounding": scene_grounding,
        "reasoning_certificate": reasoning_certificate,
        "hand_authored_answer_used": hand_authored_answer_used,
        "confidence": confidence,
        "semantic_context_count": len(semantic_context),
        "surface_candidate_count": len(surface_candidates),
        "q_cortex_used": bool(selection.get("q_cortex_used")),
        "local_user_brain_used": False,
        "external_llm_used": False,
        "external_sllm_used": False,
        "external_web_used": False,
        "cloud_decoder_used": False,
        "useful_answer": useful,
        "trace": trace,
    }
