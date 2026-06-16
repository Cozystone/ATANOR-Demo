from __future__ import annotations

import hashlib
from typing import Any

from packages.surface_brain.monitor import repair_answer_for_mode
from packages.surface_brain.q_cortex_bridge import select_surface_candidates

from .models import AnswerMode, AudienceLevel, Language, honesty_flags
from .pack_loader import classify_intent, get_semantic_context, get_surface_candidates, load_base_brain_pack


UNSUPPORTED_HINTS_KO = ["오늘", "날씨", "실시간", "최신", "주가", "가격", "내 동네"]
UNSUPPORTED_HINTS_EN = ["today", "weather", "latest", "stock price", "current price", "near me"]


def _seed(query: str) -> int:
    return int(hashlib.sha256(query.encode("utf-8", errors="ignore")).hexdigest()[:8], 16)


def _label(concept: dict[str, Any], language: str) -> str:
    labels = concept.get("labels") or {}
    return str(labels.get(language) or concept.get("canonical_name") or concept.get("concept_id"))


def _relation_words(relation: str, language: str) -> str:
    if language == "ko":
        return {
            "is_a": "의 한 종류입니다",
            "part_of": "에 속합니다",
            "has_property": "라는 성질을 가집니다",
            "used_for": "에 쓰입니다",
            "causes": "을 일으킬 수 있습니다",
            "enables": "을 가능하게 합니다",
            "requires": "을 필요로 합니다",
            "contrasts_with": "와 대비됩니다",
            "similar_to": "와 비슷합니다",
            "example_of": "의 예입니다",
            "manages": "을 관리합니다",
            "produces": "을 만들어냅니다",
            "depends_on": "에 의존합니다",
        }.get(relation, "와 연결됩니다")
    return {
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
    }.get(relation, "is related to")


def _concept_by_id(context: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item.get("concept_id")): item for item in context}


def _description_sentence(concept: dict[str, Any], language: str, audience_level: str) -> str:
    label = _label(concept, language)
    description = str(concept.get("short_description") or "")
    if language == "ko":
        ko_description = {
            "kubernetes": "여러 서버에 흩어진 컨테이너를 자동으로 배포하고, 다시 살리고, 필요한 만큼 늘리도록 돕는 운영 관리 시스템입니다.",
            "ai_training": "데이터를 보며 모델의 내부 기준을 조정하는 과정입니다.",
            "ai_inference": "이미 만들어진 모델이 새 입력을 보고 답을 계산하는 과정입니다.",
            "spring_boot": "Java 기반 서비스를 빠르게 만들고 운영 설정을 단순화해 주는 웹 프레임워크입니다.",
            "express_js": "Node.js에서 HTTP API와 웹 서비스를 가볍게 만드는 프레임워크입니다.",
            "sqlite": "서버 없이 하나의 로컬 파일 안에 데이터를 안정적으로 저장하는 내장형 데이터베이스입니다.",
            "quantum_computer": "양자 상태를 이용해 특정 문제를 다르게 계산하는 컴퓨터이지만, 모든 일을 무조건 빠르게 하는 장치는 아닙니다.",
            "graphrag": "질문과 관련된 개념 노드와 근거 경로를 먼저 찾고, 그 경로에 맞는 문맥으로 답을 구성하는 방식입니다.",
            "ontology": "개념과 관계를 정해 지식을 구조적으로 연결하는 지도입니다.",
            "semantic_graph": "단어보다 의미와 관계를 중심으로 지식을 저장하는 그래프입니다.",
            "surface_graph": "무엇을 말할지가 아니라 어떻게 자연스럽게 말할지를 다루는 표현 그래프입니다.",
            "local_first_ai": "개인 데이터와 핵심 계산을 가능한 한 사용자 기기 안에 두는 AI 구조입니다.",
            "cloud_ai": "원격 서버의 저장소나 계산 자원을 이용하는 AI 구조입니다.",
            "cpu": "다양한 명령을 순서 있게 처리하는 범용 연산 장치입니다.",
            "gpu": "많은 계산을 동시에 처리하는 병렬 연산 장치입니다.",
            "voltage": "전하를 밀어내는 전기적 압력에 가깝습니다.",
            "current": "전하가 실제로 흐르는 양입니다.",
            "tauri": "웹 UI를 가벼운 네이티브 데스크톱 앱으로 묶어 배포하는 도구입니다.",
            "api": "소프트웨어끼리 약속된 방식으로 요청과 응답을 주고받는 인터페이스입니다.",
        }.get(str(concept.get("concept_id")))
        if ko_description:
            return f"{label}는 {ko_description}"
        return f"{label}는 {description}"
    if audience_level == "beginner":
        if description.lower().startswith(label.lower()):
            return description.rstrip(".")
        return f"{label} is {description[:1].lower() + description[1:] if description else 'a related concept in the base graph'}"
    return f"{label}: {description}"


def _relation_sentence(source: dict[str, Any], relation: dict[str, Any], context_map: dict[str, dict[str, Any]], language: str) -> str:
    target_id = str(relation.get("target") or "")
    target = context_map.get(target_id, {"concept_id": target_id, "canonical_name": target_id, "labels": {}})
    source_label = _label(source, language)
    target_label = _label(target, language).replace("_", " ")
    relation_word = _relation_words(str(relation.get("relation") or "related_to"), language)
    if language == "ko":
        relation_name = str(relation.get("relation") or "related_to")
        if relation_name == "is_a":
            return f"{source_label}는 {target_label}의 한 종류입니다."
        if relation_name == "manages":
            return f"{source_label}는 {target_label} 관리를 맡습니다."
        if relation_name == "enables":
            return f"{source_label}는 {target_label}를 가능하게 합니다."
        if relation_name == "contrasts_with":
            return f"{source_label}는 {target_label}와 대비됩니다."
        return f"{source_label}는 {target_label}{relation_word}."
    return f"{source_label} {relation_word} {target_label}."


def _compare_answer(context: list[dict[str, Any]], language: str, audience_level: str) -> str:
    if len(context) < 2:
        return ""
    first, second = context[0], context[1]
    if language == "ko":
        return (
            f"{_label(first, language)}와 {_label(second, language)}의 핵심 차이는 역할과 사용 맥락입니다. "
            f"{_description_sentence(first, language, audience_level)} "
            f"반면 {_description_sentence(second, language, audience_level)} "
            "둘은 비슷한 문제를 다루더라도 선택 기준과 운영 방식이 다를 수 있습니다."
        )
    return (
        f"The main difference between {_label(first, language)} and {_label(second, language)} is their role and operating context. "
        f"{_description_sentence(first, language, audience_level)}. "
        f"By contrast, {_description_sentence(second, language, audience_level)}. "
        "They may solve related problems, but they are chosen for different constraints."
    )


def _compose_answer(query: str, context: list[dict[str, Any]], language: str, audience_level: str, intent: str) -> tuple[str, bool]:
    lowered = query.lower()
    if (language == "ko" and any(hint in query for hint in UNSUPPORTED_HINTS_KO)) or any(hint in lowered for hint in UNSUPPORTED_HINTS_EN):
        if not any(float(item.get("match_score") or 0.0) > 1.5 for item in context):
            return (
                "현재 Base Brain Pack만으로는 이 질문에 필요한 실시간 근거가 부족합니다. "
                "날씨, 최신 가격, 지역 정보처럼 변하는 정보는 외부 문맥이나 향후 확장된 그래프가 필요합니다."
                if language == "ko"
                else "The current Base Brain Pack does not contain enough real-time evidence for that question. Dynamic topics such as weather, prices, or local conditions need external context or a larger future graph."
            ), False
    strong = [item for item in context if float(item.get("match_score") or 0.0) > 0]
    if not strong:
        return (
            "현재 Base Brain Pack에는 이 질문을 충분히 뒷받침할 개념이 없습니다. 추측으로 답하지 않고, 관련 근거가 추가되면 더 정확히 설명할 수 있습니다."
            if language == "ko"
            else "The current Base Brain Pack does not contain enough supporting concepts for this question. I will not guess; a larger graph or external context is needed."
        ), False
    if intent == "compare":
        compared = _compare_answer(strong, language, audience_level)
        if compared:
            return compared, True
    primary = strong[0]
    context_map = _concept_by_id(context)
    relation_lines = [
        _relation_sentence(primary, relation, context_map, language)
        for relation in primary.get("relations", [])[:2]
    ]
    base = _description_sentence(primary, language, audience_level)
    if language == "ko":
        if relation_lines:
            return f"{base} {' '.join(relation_lines)} 정리하면, 질문의 핵심은 {_label(primary, language)}가 어떤 역할을 맡고 어떤 관계 속에서 쓰이는지를 보는 것입니다.", True
        return f"{base} 정리하면, 이 개념은 관련 시스템 안에서 맡는 역할을 기준으로 이해하면 좋습니다.", True
    if relation_lines:
        return f"{base}. {' '.join(relation_lines)} In short, the useful way to understand {_label(primary, language)} is by its role and relationships.", True
    return f"{base}. In short, it is best understood by the role it plays in the surrounding system.", True


def answer_with_base_brain(
    query: str,
    language: Language = "ko",
    audience_level: AudienceLevel = "beginner",
    mode: AnswerMode = "default",
) -> dict[str, Any]:
    pack = load_base_brain_pack()
    semantic_context = get_semantic_context(query, pack, limit=12)
    intent = classify_intent(query, pack)
    surface_candidates = get_surface_candidates(query, semantic_context, language, audience_level, limit=8, pack=pack)
    selection = select_surface_candidates(surface_candidates, max_selected=4, seed=_seed(query), q_cortex_enabled=True)
    answer, useful = _compose_answer(query, semantic_context, language, audience_level, intent)
    trace = {
        "mode": mode,
        "pack_id": pack.pack_id,
        "intent": intent,
        "matched_concepts": [
            {
                "concept_id": item.get("concept_id"),
                "canonical_name": item.get("canonical_name"),
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
    repair_result = repair_answer_for_mode(answer, mode=mode, trace=trace)
    final_answer = str(repair_result.get("repaired_answer") or answer)
    response = {
        "answer": final_answer,
        "answer_kind": "base_brain_zero_user_data",
        "semantic_context_count": len(semantic_context),
        "surface_candidate_count": len(surface_candidates),
        "q_cortex_used": bool(selection.get("q_cortex_used")),
        "local_user_brain_used": False,
        "external_llm_used": False,
        "external_sllm_used": False,
        "external_web_used": False,
        "cloud_decoder_used": False,
        "trace_hidden_by_default": mode == "default",
        "repair": {
            "applied": bool(repair_result.get("changed")),
            "applied_rules": repair_result.get("applied_rules", []),
            "moved_to_trace_count": len(repair_result.get("moved_to_trace", [])),
        },
        "trace": trace,
    }
    if mode == "default":
        response["compact_trace"] = {
            "pack_id": pack.pack_id,
            "semantic_context_count": len(semantic_context),
            "surface_candidate_count": len(surface_candidates),
            "q_cortex_used": bool(selection.get("q_cortex_used")),
            **honesty_flags(),
        }
    return response
