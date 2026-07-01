from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .models import PACK_PATH, BaseBrainPack
from .pack_builder import build_base_brain_pack_v0

BASE_PACK_CODE_VERSION = "0.1.5"
TOKEN_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "for",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
    "brain",
    "cloud",
    "local",
    "simple",
    "explain",
    "차이",
    "비교",
    "설명",
    "간단",
    "초등학생",
    "중학생",
    "전문가",
    "브레인",
}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").lower()).strip()


def _tokens(text: str) -> set[str]:
    lowered = _norm(text)
    latin = set(re.findall(r"[a-z0-9.+#-]{2,}", lowered))
    korean = set(re.findall(r"[\uac00-\ud7a3]{2,}", text or ""))
    return {token for token in (latin | korean) if token not in TOKEN_STOPWORDS}


def _needs_rebuild(payload: dict[str, Any]) -> bool:
    metadata = payload.get("metadata") or {}
    if metadata.get("base_pack_code_version") != BASE_PACK_CODE_VERSION:
        return True
    text = json.dumps(payload, ensure_ascii=False)
    return any(marker in text for marker in ("荑", "吏", "媛", "占"))


def load_base_brain_pack(pack_path: str | Path | None = None) -> BaseBrainPack:
    path = Path(pack_path) if pack_path else PACK_PATH
    if not path.exists():
        build_base_brain_pack_v0()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if _needs_rebuild(payload):
        # In-memory rebuild for THIS load only — never write, so a promoted pack on
        # disk is not clobbered back to curated-only by a version/mojibake trip.
        payload = build_base_brain_pack_v0(write=False)
    return BaseBrainPack(
        pack_id=payload["pack_id"],
        version=payload["version"],
        metadata=payload["metadata"],
        seed_graph=payload["seed_graph"],
        semantic_graph=payload["semantic_graph"],
        surface_graph=payload["surface_graph"],
        benchmark=payload["benchmark"],
    )


def _concept_score(query: str, concept: dict[str, Any]) -> float:
    query_norm = _norm(query)
    query_tokens = _tokens(query)
    names = [concept.get("concept_id", ""), concept.get("canonical_name", ""), *(concept.get("aliases") or [])]
    labels = concept.get("labels") or {}
    names.extend(str(value) for value in labels.values())
    score = 0.0
    for name in names:
        name_norm = _norm(str(name))
        if not name_norm:
            continue
        if name_norm in query_norm:
            score += 2.2
        name_tokens = _tokens(str(name))
        score += len(query_tokens & name_tokens) * 0.75
    desc_tokens = _tokens(str(concept.get("short_description", "")))
    score += min(len(query_tokens & desc_tokens) * 0.25, 1.0)
    return score


def get_semantic_context(query: str, pack: BaseBrainPack, limit: int = 12) -> list[dict[str, Any]]:
    concepts = pack.semantic_graph.get("concepts") or []
    scored = [{**concept, "match_score": _concept_score(query, concept)} for concept in concepts]
    ranked = sorted(
        scored,
        key=lambda item: (float(item.get("match_score") or 0.0), float(item.get("confidence") or 0.0)),
        reverse=True,
    )
    high_confidence = [item for item in ranked if float(item.get("match_score") or 0.0) >= 4.0]
    selected = [item for item in ranked if float(item.get("match_score") or 0.0) >= 1.0][:limit]
    if high_confidence:
        selected = [
            item
            for item in selected
            if item.get("concept_id") not in {"korean_language", "english_language"}
            or any(marker in query.lower() for marker in ["한국어", "영어로", "번역투", "language"])
        ][:limit]
    if selected:
        selected_ids = {item["concept_id"] for item in selected}
        relation_targets = {
            relation.get("target")
            for item in selected
            for relation in item.get("relations", [])
            if relation.get("target")
        }
        for item in ranked:
            if len(selected) >= limit:
                break
            if item["concept_id"] in selected_ids:
                continue
            if item["concept_id"] in relation_targets:
                selected.append(item)
                selected_ids.add(item["concept_id"])
    return selected[:limit]


def _classify_intent(query: str, seed_graph: dict[str, Any]) -> str:
    lower = _norm(query)
    if any(token in lower for token in ["compare", "versus", " vs ", "difference", "차이", "비교"]):
        return "compare"
    if any(token in lower for token in ["summarize", "요약", "정리"]):
        return "summarize"
    if any(token in lower for token in ["what is", "define", "뭐야", "무엇", "정의"]):
        return "define"
    if any(token in lower for token in ["how", "why", "explain", "설명", "왜", "어떻게"]):
        return "explain"
    return "explain" if "explain" in seed_graph.get("reasoning_primitives", []) else "clarify"


def get_surface_candidates(
    query: str,
    semantic_context: list[dict[str, Any]],
    language: str,
    audience_level: str,
    limit: int = 8,
    pack: BaseBrainPack | None = None,
) -> list[dict[str, Any]]:
    pack = pack or load_base_brain_pack()
    intent = _classify_intent(query, pack.seed_graph)
    candidates = []
    for item in pack.surface_graph.get("constructions", []):
        if item.get("language") != language:
            continue
        fit = 0.55
        if item.get("function") in {intent, "definition" if intent == "define" else intent}:
            fit += 0.28
        if item.get("audience_level") == audience_level:
            fit += 0.12
        if semantic_context:
            fit += 0.05
        candidates.append(
            {
                **item,
                "id": item.get("construction_id"),
                "pattern_family": item.get("construction_id"),
                "semantic_function": item.get("function"),
                "fit_score": min(fit, 1.0),
                "style_score": 0.78 if item.get("tone") in {"clear", "friendly", "compact"} else 0.62,
                "language_score": 1.0,
                "prior_success_weight": item.get("prior_weight", 0.5),
                "user_preference_weight": 0.72,
                "repetition_penalty": 0.0,
            }
        )
    return sorted(candidates, key=lambda item: item["fit_score"], reverse=True)[:limit]


def classify_intent(query: str, pack: BaseBrainPack | None = None) -> str:
    pack = pack or load_base_brain_pack()
    return _classify_intent(query, pack.seed_graph)
