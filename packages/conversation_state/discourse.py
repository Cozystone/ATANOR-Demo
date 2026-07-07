# -*- coding: utf-8 -*-
"""Discourse state v0 — real deixis resolution instead of string concatenation.

'그럼 그 나라의 수도는?' after talking about 일본 must become '일본의 수도는?'.
The previous approach concatenated the turns and hoped the lookup found the
right subject; this module RESOLVES the referring expression:

  1. track entities across turns (most recent = most salient)
  2. a typed deixis ('그 나라') binds to the most salient entity whose stored
     is_a/defined_as facts match the type word — the GRAPH is the type system,
     no hand-written entity lists
  3. untyped deixis ('그것', '거기', '걔') binds to the most salient entity

Every binding is auditable: the resolution returns the substituted question and
the (phrase → entity, why) trace for the reasoning certificate.
"""
from __future__ import annotations

import re
from typing import Any

# deixis phrase -> type words the referent's graph facts must mention.
# () = untyped, binds to the most salient entity of any kind.
_TYPED_DEIXIS: dict[str, tuple[str, ...]] = {
    "그 나라": ("나라", "국가"),
    "그 도시": ("도시",),
    "그 사람": ("사람", "인물", "학자", "왕", "대통령"),
    "그 회사": ("회사", "기업"),
    "그 동물": ("동물", "새", "포유류"),
    "그 음식": ("음식", "요리", "음료"),
    "그 책": ("책", "소설", "저서"),
    "그곳": (), "그 곳": (), "거기": (), "그것": (), "그거": (), "이것": (),
    "걔": (), "그 애": (),
}
_STOP_ENTITIES = {"그럼", "그것", "무엇", "어디", "누구", "수도", "이름", "나라", "도시",
                  "사람", "때문", "다음", "이유", "방법", "생각", "말씀"}


def track_entities(context: list[dict[str, Any]], limit: int = 8) -> list[str]:
    """Entities across turns, USER turns first (the user's topic is what deixis
    points at — '그 나라' after '일본은 어떤 나라야?' means 일본, not the 섬나라
    the assistant's answer mentioned), then assistant turns; recent before old.
    Reuses the bridge's subject extractor so tracking and lookup agree."""
    try:
        from packages.graph_scale.answer_bridge import _subject_candidates
    except Exception:
        return []
    user_ents: list[str] = []
    other_ents: list[str] = []
    for turn in reversed(context or []):
        text = str(turn.get("content") or turn.get("text") or "")
        if not text:
            continue
        is_user = str(turn.get("role") or "").lower() == "user"
        for cand in _subject_candidates(text):
            if cand in _STOP_ENTITIES or len(cand) < 2:
                continue
            if is_user:
                if cand in other_ents:  # PROMOTE: user naming it outranks an
                    other_ents.remove(cand)  # assistant mention (일본 vs 섬나라)
                if cand not in user_ents:
                    user_ents.append(cand)
            elif cand not in user_ents and cand not in other_ents:
                other_ents.append(cand)
        if len(user_ents) + len(other_ents) >= limit * 2:
            break
    return (user_ents + other_ents)[:limit]


# predicate SIGNATURES type an entity structurally: something with a 수도 IS a
# country even when its stored definition is fragmentary ('일본 defined_as 4개의
# 섬' carries no 나라 token — measured). Ontology layer, like _RELATION_CUES.
_TYPE_SIGNATURES: dict[str, tuple[str, ...]] = {
    "나라": ("capital", "수도"), "국가": ("capital", "수도"),
    "도시": ("capital_of", "소재지", "고도"),
    "회사": ("chief_executive_officer", "최고경영자", "설립자"),
    "사람": ("author",), "인물": ("author",),
}


def _entity_matches_type(entity: str, type_words: tuple[str, ...]) -> bool:
    """The graph is the type system: 일본 matches '나라' when a stored
    is_a/defined_as fact mentions 나라 OR its predicates carry the type's
    structural signature (has 수도 => country). Bounded single lookup."""
    if not type_words:
        return True
    sig = {p for t in type_words for p in _TYPE_SIGNATURES.get(t, ())}
    try:
        from packages.graph_scale.answer_bridge import _store

        store = _store()
        if store is None:
            return False
        for (_s, p, o) in store.facts_about(entity, limit=16):
            if p in ("is_a", "defined_as") and any(t in o for t in type_words):
                return True
            if p in sig:
                return True
    except Exception:
        pass
    return False


def resolve_deixis(question: str, context: list[dict[str, Any]]) -> dict[str, Any]:
    """Resolve referring expressions in `question` against the conversation.
    Returns {resolved, bindings} — resolved == question when nothing to do.
    Bindings carry the audit trace ('그 나라' -> 일본, matched via is_a 나라)."""
    out: dict[str, Any] = {"resolved": question, "bindings": []}
    q = question or ""
    hits = [d for d in _TYPED_DEIXIS if d in q]
    if not hits or not context:
        return out
    entities = track_entities(context)
    if not entities:
        return out
    resolved = q
    for phrase in sorted(hits, key=len, reverse=True):
        type_words = _TYPED_DEIXIS[phrase]
        bound = None
        for ent in entities:  # most salient first
            if ent in q:
                continue  # already named explicitly — not what the deixis points at
            if type_words and any(ent.endswith(t) and len(ent) - len(t) <= 1
                                  for t in type_words):
                continue  # 섬나라 = modifier+나라, a KIND not a NAME; but 세종대왕
                # (a 4-char NAME ending in 왕) must stay eligible
            if _entity_matches_type(ent, type_words):
                bound = ent
                break
        if bound is None and type_words:
            continue  # typed deixis with no type-matching entity: leave unresolved
        if bound is None:
            bound = entities[0]
        resolved = resolved.replace(phrase, bound)
        out["bindings"].append({"phrase": phrase, "entity": bound,
                                "via": ("graph_type:" + "/".join(type_words)) if type_words
                                else "salience"})
    out["resolved"] = resolved
    return out
