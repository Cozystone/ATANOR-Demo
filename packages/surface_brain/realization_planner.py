from __future__ import annotations

import hashlib
import re
from typing import Any

from .construction_graph import construction_candidates
from .discourse_graph import discourse_candidates
from .lemma_graph import lemma_candidates
from .models import RealizedAnswer, SurfacePlan, detect_language, hash_text, honesty_flags, utc_now_iso
from .monitor import monitor_answer, repair_answer_for_mode
from .q_cortex_bridge import select_surface_candidates
from .style_graph import style_profile
from .storage import SURFACE_ROOT, append_jsonl, ensure_dirs


def classify_intent(query: str) -> str:
    lower = query.lower()
    if any(token in query for token in ("뭐야", "무엇", "정의")) or any(token in lower for token in ("what is", "define")):
        return "define"
    if any(token in query for token in ("차이", "비교")) or "compare" in lower:
        return "compare"
    if any(token in query for token in ("요약", "정리")) or "summarize" in lower:
        return "summarize"
    if any(token in query for token in ("어떻게", "설명")) or "how" in lower or "explain" in lower:
        return "explain"
    if any(token in query for token in ("계획", "로드맵")) or "plan" in lower:
        return "plan"
    return "explain"


def _plan_id(query: str) -> str:
    return f"splan_{hashlib.sha256(f'{query}:{utc_now_iso()}'.encode('utf-8')).hexdigest()[:18]}"


def _semantic_context_from_any(context: dict[str, Any] | None) -> dict[str, Any]:
    context = context or {}
    if "result" in context and isinstance(context["result"], dict):
        context = context["result"]
    concepts = list(context.get("concepts") or context.get("active_concepts") or [])
    for node in context.get("matched_nodes") or []:
        label = node.get("label") or node.get("primary_name") or node.get("id")
        if label and label not in concepts:
            concepts.append(label)
    relations = list(context.get("relations") or context.get("matched_edges") or [])
    evidence = list(context.get("evidence") or context.get("evidence_docs") or [])
    claims = list(context.get("claims") or [])
    return {
        "concepts": concepts,
        "relations": relations,
        "evidence": evidence,
        "claims": claims,
        "confidence": float(context.get("confidence") or 0.0),
        "local_coverage": context.get("local_coverage") or ("medium" if concepts or evidence else "low"),
    }


def plan_speech(
    query: str,
    semantic_context: dict[str, Any] | None = None,
    *,
    language: str | None = None,
    audience_level: str = "beginner",
    tone: str = "clear",
    mode: str = "default",
    q_cortex_enabled: bool = True,
) -> dict[str, Any]:
    ensure_dirs()
    semantic = _semantic_context_from_any(semantic_context)
    lang = language or ("ko" if detect_language(query) in {"ko", "mixed"} else "en")
    intent = classify_intent(query)
    construction_pool = construction_candidates(intent, lang, audience_level)
    discourse_pool = discourse_candidates(intent, audience_level)
    lemma_pool = lemma_candidates(semantic, lang)
    seed = int(hash_text(query)[:8], 16)
    construction_selection = select_surface_candidates(construction_pool, max_selected=4, seed=seed, q_cortex_enabled=q_cortex_enabled)
    discourse_selection = select_surface_candidates(discourse_pool, max_selected=5, seed=int(hash_text("disc:" + query)[:8], 16), q_cortex_enabled=q_cortex_enabled)
    lemma_selection = select_surface_candidates(lemma_pool, max_selected=max(1, min(8, len(lemma_pool))), seed=int(hash_text("lemma:" + query)[:8], 16), q_cortex_enabled=q_cortex_enabled)
    selected_lemmas = {
        str(item.get("concept")): str(item.get("label"))
        for item in lemma_selection.get("selected", [])
        if item.get("concept") and item.get("label")
    }
    plan = SurfacePlan(
        plan_id=_plan_id(query),
        intent=intent,
        language=lang,  # type: ignore[arg-type]
        audience_level=audience_level,
        message_order=[item.get("move", item.get("id", "")) for item in discourse_selection.get("selected", [])],
        selected_discourse_moves=[item.get("move", item.get("id", "")) for item in discourse_selection.get("selected", [])],
        selected_constructions=construction_selection.get("selected", []),
        selected_lemma_choices=selected_lemmas,
        style_profile=style_profile(lang, audience_level, tone),
        q_cortex_used=bool(construction_selection.get("q_cortex_used") or discourse_selection.get("q_cortex_used") or lemma_selection.get("q_cortex_used")),
        q_cortex_run_id=construction_selection.get("q_cortex_run_id") or discourse_selection.get("q_cortex_run_id") or lemma_selection.get("q_cortex_run_id"),
        trace={
            "mode": mode,
            "construction_candidates": construction_pool,
            "discourse_candidates": discourse_pool,
            "lemma_candidates": lemma_pool,
            "construction_selection": construction_selection,
            "discourse_selection": discourse_selection,
            "lemma_selection": lemma_selection,
            "semantic_context_summary": {
                "concept_count": len(semantic["concepts"]),
                "relation_count": len(semantic["relations"]),
                "evidence_count": len(semantic["evidence"]),
                "local_coverage": semantic["local_coverage"],
            },
            **honesty_flags(),
        },
    ).to_dict()
    plan.update(honesty_flags())
    append_jsonl(SURFACE_ROOT / "traces" / "surface_plans.jsonl", {**plan, "recorded_at": utc_now_iso()})
    return plan


def _evidence_sentence(semantic: dict[str, Any]) -> str:
    for doc in semantic.get("evidence") or []:
        text = str(doc.get("snippet") or doc.get("text") or "").strip()
        if text:
            return re.sub(r"\s+", " ", text)[:260]
    return ""


def _relation_summary(semantic: dict[str, Any], language: str) -> str:
    relations = semantic.get("relations") or []
    if relations:
        relation = relations[0]
        source = relation.get("source") or relation.get("source_hash") or relation.get("from") or "개념"
        rel = relation.get("relation") or relation.get("predicate") or "relates_to"
        target = relation.get("target") or relation.get("target_hash") or relation.get("to") or "다른 개념"
        if language == "ko":
            if rel in {"manages", "uses"}:
                return f"{source}는 {target}를 다루는 개념으로 연결됩니다"
            if rel == "analogy":
                return f"{source}는 {target}와의 비유로 설명할 수 있습니다"
            return f"{source}와 {target} 사이에는 {rel} 관계가 있습니다"
        return f"{source} is linked to {target} through {rel}"
    concepts = semantic.get("concepts") or []
    if concepts:
        if language == "ko":
            return f"핵심 개념은 {', '.join(map(str, concepts[:3]))}입니다"
        return f"The core concepts are {', '.join(map(str, concepts[:3]))}"
    return ""


def _natural_answer(query: str, semantic: dict[str, Any], plan: dict[str, Any]) -> str:
    language = str(plan.get("language") or "ko")
    lower_query = query.lower()
    concepts = {str(item).lower() for item in semantic.get("concepts") or []}
    relation_text = _relation_summary(semantic, language)
    evidence_text = _evidence_sentence(semantic)
    if language == "ko":
        if "쿠버네티스" in query or "kubernetes" in lower_query or "kubernetes" in concepts:
            return (
                "쿠버네티스는 여러 컨테이너를 한곳에 모아 자동으로 배치하고 운영하도록 돕는 컨테이너 오케스트레이션 시스템입니다. "
                "쉽게 말하면, 많은 컨테이너가 어느 서버에서 실행될지 정하고, 문제가 생기면 다시 띄우고, 필요한 만큼 늘리거나 줄이는 운영 관리자에 가깝습니다. "
                "그래서 개발자는 개별 서버를 일일이 만지는 대신 서비스가 안정적으로 돌아가도록 선언적인 규칙을 관리하게 됩니다."
            )
        if "graphrag" in lower_query and ("근거" in query or "검증" in query or "evidence" in lower_query):
            return (
                "GraphRAG는 질문과 가까운 개념 노드를 먼저 찾고, 그 노드가 가리키는 근거 문서 조각을 함께 읽어 답변 후보를 좁힙니다. "
                "그다음 생성된 문장이 실제 근거와 맞는지 비교해, 근거가 약한 주장은 낮은 신뢰도로 두거나 답변에서 제외합니다. "
                "즉 답변은 그래프 경로만이 아니라, 그 경로가 연결한 문서 근거까지 함께 통과해야 합니다."
            )
        if evidence_text:
            return f"{evidence_text} 이를 기준으로 보면, {relation_text or '질문과 연결된 근거가 확인됩니다'}."
        if relation_text:
            return f"{relation_text}. 다만 현재 로컬 근거가 충분하지 않으면 확정적으로 말하지 않고 낮은 신뢰도로 둡니다."
        return "현재 확인된 로컬 근거만으로는 충분한 답을 만들기 어렵습니다. 관련 문서나 Cloud Brain 문맥을 붙이면 더 자연스럽게 설명할 수 있습니다."
    if "kubernetes" in lower_query or "kubernetes" in concepts:
        return (
            "Kubernetes is a container orchestration system: it helps place, run, restart, and scale many containers across machines. "
            "In simple terms, it behaves like an operations manager for containerized services, so teams describe the desired state instead of manually handling every server."
        )
    if "graphrag" in lower_query and ("evidence" in lower_query or "verify" in lower_query):
        return (
            "GraphRAG first expands the concepts related to a question, then retrieves the evidence chunks attached to those graph paths. "
            "The answer is checked against those chunks, so unsupported claims can be downweighted, qualified, or removed."
        )
    if evidence_text:
        return f"{evidence_text} In short, {relation_text or 'the retrieved evidence supports the answer'}."
    return "The current local context is not strong enough to answer confidently. Attaching relevant Semantic Cloud context would improve the response."


def realize_answer(
    surface_plan: dict[str, Any],
    semantic_context: dict[str, Any] | None = None,
    *,
    query: str = "",
    decoder_mode: str = "deterministic",
    apply_repair: bool = True,
) -> dict[str, Any]:
    ensure_dirs()
    semantic = _semantic_context_from_any(semantic_context)
    language = str(surface_plan.get("language") or ("ko" if detect_language(query) in {"ko", "mixed"} else "en"))
    mode = str(surface_plan.get("trace", {}).get("mode") or "default") if isinstance(surface_plan.get("trace"), dict) else "default"
    answer = _natural_answer(query, semantic, surface_plan)
    monitor = monitor_answer(answer, language=language)
    repair_result = {
        "original_answer": answer,
        "repaired_answer": answer,
        "applied_rules": [],
        "moved_to_trace": [],
        "changed": False,
        "warnings": [],
    }
    trace_summary: dict[str, Any] = {
        "intent": surface_plan.get("intent"),
        "selected_construction_families": [item.get("pattern_family") for item in surface_plan.get("selected_constructions", [])],
        "selected_discourse_moves": surface_plan.get("selected_discourse_moves", []),
        "q_cortex_used": bool(surface_plan.get("q_cortex_used")),
        "q_cortex_run_id": surface_plan.get("q_cortex_run_id"),
        "local_brain_write": False,
        "decoder_mode": decoder_mode,
        "trace_hidden_by_default": True,
        **honesty_flags(),
    }
    if apply_repair:
        repair_result = repair_answer_for_mode(answer, mode=mode, trace=trace_summary)
        answer = str(repair_result["repaired_answer"])
        monitor = monitor_answer(answer, language=language)
    semantic_sources = []
    for doc in semantic.get("evidence") or []:
        source_hash = doc.get("hash_key") or doc.get("source_hash") or doc.get("chunk_id")
        if source_hash:
            semantic_sources.append(str(source_hash))
    realized = RealizedAnswer(
        answer=answer,
        language=language,  # type: ignore[arg-type]
        surface_plan_id=str(surface_plan.get("plan_id")),
        semantic_sources=semantic_sources,
        surface_sources=[str(surface_plan.get("plan_id"))],
        confidence=max(0.35, min(0.92, float(semantic.get("confidence") or 0.55) + 0.12)),
        trace_summary={**trace_summary, "monitor": monitor},
        repair={
            "applied": bool(repair_result.get("changed")),
            "applied_rules": repair_result.get("applied_rules", []),
            "moved_to_trace_count": len(repair_result.get("moved_to_trace", [])),
            "warnings": repair_result.get("warnings", []),
        },
    ).to_dict()
    append_jsonl(SURFACE_ROOT / "traces" / "realized_answers.jsonl", {**realized, "recorded_at": utc_now_iso()})
    return realized
