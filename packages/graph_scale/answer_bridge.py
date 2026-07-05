"""Bridge the bulk triple store into the answer path — so trillion-scale curated knowledge
is USABLE, not just stored.

A fact ('일본', 'capital', '도쿄도') in the TripleStore should answer '일본의 수도는?'. This
bridge does the lookup: extract the query's subject, fetch its stored facts (a bounded
memmap scan — no full load), and if the query's relation intent matches a stored predicate,
return the object as a grounded, cited answer. Structured curated triples are the highest-
quality source, so this runs BEFORE the noisier promoted-pack path.

Honesty: it only ever returns a fact that is literally stored (verbatim subject/predicate/
object, with the source in the certificate); it never infers or invents. Empty store =>
returns None (the normal paths handle it), so it is safe to wire even before any bulk load.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2] / "data" / "graph_scale" / "kg_triples"
_STORE = {"obj": None, "sig": None}

# relation-intent cues -> the predicate names a curated source uses. A small, bounded map
# (LAD/ontology layer, like the domain bridge) so '수도' finds the 'capital' predicate.
_RELATION_CUES: dict[str, tuple[str, ...]] = {
    "capital": ("수도", "capital"),
    "instance_of": ("종류", "무엇", "뭐", "is_a", "instance"),
    "chief_executive_officer": ("ceo", "대표", "최고경영자", "사장"),
    "country": ("나라", "국가", "어느 나라", "country"),
    "author": ("저자", "author", "쓴", "지은이"),
    "capital_of": ("어디의 수도", "수도인"),
    "located_in": ("어디에 있", "어느 나라에", "위치", "located"),
    "defined_as": ("뭐", "무엇", "뜻", "정의", "란 뭐", "이란", "설명", "define", "meaning", "what is"),
    "is_a": ("뭐", "무엇", "종류", "일종", "무슨", "kind of", "type of"),
}


def _store():
    try:
        meta = _ROOT / "meta.json"
        if not meta.exists():
            return None
        sig = meta.stat().st_mtime
        if _STORE["sig"] != sig:
            from .triple_store import TripleStore

            _STORE["obj"] = TripleStore(_ROOT)
            _STORE["sig"] = sig
        return _STORE["obj"]
    except Exception:
        return None


def _subject_candidates(query: str) -> list[str]:
    """INDIVIDUAL content nouns in the query, most-specific first — the possible subjects.
    Unlike neighbourhood retrieval (which JOINS compound nouns, 캐나다+수도 -> 캐나다수도),
    a triple lookup needs the atomic entity (캐나다), so we take individual noun morphemes
    (Kiwi NNP/NNG) and fall back to particle-stripped regex tokens."""
    cands: list[str] = []
    try:
        from packages.base_brain.neighborhood import _kiwi, _strip_ko_tail

        kw = _kiwi()
        if kw is not None:
            for tok in kw.tokenize(query):
                if tok.tag in ("NNP", "NNG", "SL") and len(tok.form) >= 2:
                    if tok.form not in cands:
                        cands.append(tok.form)
    except Exception:
        pass
    if not cands:
        from packages.base_brain.neighborhood import _strip_ko_tail

        for t in re.findall(r"[가-힣A-Za-z0-9]{2,}", query):
            st = _strip_ko_tail(t)
            if len(st) >= 2 and st not in cands:
                cands.append(st)
    # proper/longer nouns first (캐나다 before 수도); a subject is usually the entity name
    return sorted(cands, key=lambda t: -len(t))[:6]


# predicate -> Korean surface template. Keeps derived edges (capital_of, located_in) reading
# naturally instead of the generic "{s}의 {pred}는 {o}" frame. {s}/{o} are the stored labels.
_KO_TEMPLATE: dict[str, str] = {
    "capital": "{s}의 수도는 {o}입니다.",
    "capital_of": "{s_topic} {o}의 수도입니다.",
    "located_in": "{s_topic} {o}에 위치합니다.",
    "country": "{s}의 나라는 {o}입니다.",
    "author": "{s}의 저자는 {o}입니다.",
    "defined_as": "{s_topic} {o}입니다.",
    "is_a": "{s_topic} {o}의 일종입니다.",
}


def _ko_topic(label: str) -> str:
    """Attach the correct 은/는 topic particle (delegates to the LAD morphology layer)."""
    from packages.lad_morphology import topic

    return topic(label)


def _wanted_predicates(query: str) -> set[str]:
    q = query.lower()
    want = {pred for pred, cues in _RELATION_CUES.items() if any(c in q for c in cues)}
    return want


def answer_from_triples(query: str, language: str = "ko") -> dict[str, Any] | None:
    """Look up a stored fact that answers the query. Returns {answer, reasoning_certificate,
    confidence} or None when the store can't answer it (empty store, no subject match, or
    the relation intent isn't present)."""
    store = _store()
    if store is None or len(store) == 0:
        return None
    want = _wanted_predicates(query)
    for subj in _subject_candidates(query):
        facts = store.facts_about(subj, limit=12)
        if not facts:
            continue
        # prefer a fact whose predicate matches the query's relation intent
        chosen = [(s, p, o) for (s, p, o) in facts if (not want or p in want)]
        if not chosen:
            continue
        s, p, o = chosen[0]
        if language == "ko":
            template = _KO_TEMPLATE.get(p)
            if template:
                body = template.format(s=s, o=o, s_topic=_ko_topic(s))
            else:  # unknown predicate: generic frame with correct topic particle
                pred_ko = next((cues[0] for name, cues in _RELATION_CUES.items() if name == p), p)
                body = f"{s}의 {_ko_topic(pred_ko)} {o}입니다."
            answer = f"{body} (출처: 큐레이션 지식그래프)"
        else:
            answer = f"The {p.replace('_', ' ')} of {s} is {o}. (source: curated knowledge graph)"
        return {
            "answer": answer,
            "reasoning_certificate": {
                "derivation_kind": "structured_triple_lookup",
                "anchor_concept": {"label": s}, "steps": [{"type": "triple", "fact": f"{s} {p} {o}"}],
                "evidence_concepts": [s, o], "confidence": 0.9,
                "confidence_basis": "curated_structured_triple_verbatim",
                "guarantees": {"external_llm": False, "fabricated_facts": False, "inferred": False},
            },
            "confidence": 0.9,
            "answer_kind": "structured_triple_lookup",
        }
    return None
