"""Unified reasoning→utterance orchestrator — one 'think then speak' pipeline, No-LLM, grounded.

Composes every piece built this session into ONE honestly-routed flow. Given a query it tries, in
priority order, the mechanism most likely to give an EXACT, GROUNDED answer, and abstains when none
genuinely applies (never fabricates). Each stage is deterministic and carries provenance so the
answer is explainable end-to-end.

  1. deterministic reasoning   — arithmetic VM + transitive/IS-A/causal/compound composition
                                 (exact; runs first, offline).
  2. graph-grounded answer     — the learned graph, trust-gated, with online Hebbian reinforcement
                                 (only when the graph genuinely covers the entity).
  3. multi-source synthesis    — comprehensive extractive answer across corpus sources (each cited).
  3.5 web-grounded             — broad live/search grounding (wired by the caller) so we rarely fall
                                 through; this is what makes "no answer" genuinely rare.
  4. creative                  — conceptual blend / assumption-break with XAI (for creative intents),
                                 grounded in real graph structure.
  5. best-effort grounding     — NEVER a dead "I don't know": surface real partial grounding (a
                                 corpus/graph fact that mentions the entity, hedged) or, only when
                                 there is genuinely nothing, a helpful redirect. Never fabricates.

Every dependency is imported lazily and guarded, so the orchestrator degrades gracefully when a
resource (graph store, corpus, semantic LM) is absent.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

_CREATIVE_CUE = re.compile(r"(창작|창의|시\s*를|시를|시\s*써|이야기\s*(를|만들)|아이디어|발명|새로운\s*개념|상상|지어내)")


@dataclass
class AnswerResult:
    answer: str | None
    kind: str
    grounding: list[Any] = field(default_factory=list)
    certificate: dict[str, Any] | None = None
    guarantees: dict[str, bool] = field(default_factory=lambda: {"external_llm": False, "fabricated_facts": False})

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "answer_kind": self.kind,
            "grounding": self.grounding,
            "reasoning_certificate": self.certificate,
            "guarantees": self.guarantees,
        }


def _entity(query: str) -> str:
    try:
        from packages.cgsr.cgsr.referent_resonance import query_subject_entity

        e = query_subject_entity(query)
        if 2 <= len(e) <= 40:
            return e
    except Exception:
        pass
    # fallback: longest run of Hangul/latin word chars
    words = re.findall(r"[0-9A-Za-z가-힣]+", query)
    return max(words, key=len) if words else query.strip()


def answer(
    query: str,
    *,
    language: str = "ko",
    graph_store: str | None = None,
    corpus: list[str] | None = None,
    web_answer: Any = None,  # optional Callable[[str], dict|None] — broad grounding (dual_brain wires it)
    now: datetime | None = None,
) -> AnswerResult:
    query = (query or "").strip()
    if not query:
        return AnswerResult(None, "empty")
    now = now or datetime.now(timezone.utc)

    # 1) deterministic reasoning (exact) — arithmetic + relation composition
    try:
        from app.services.reasoning_vm import solve_reasoning

        r = solve_reasoning(query, language)
        if r and r.get("answer"):
            return AnswerResult(r["answer"], "deterministic_reasoning", certificate=r.get("reasoning_certificate"))
    except Exception:  # pragma: no cover - reasoner must never break the pipeline
        pass

    creative_intent = bool(_CREATIVE_CUE.search(query))

    # 2) graph-grounded answer (trust-gated) + online Hebbian — when the learned graph covers it
    if graph_store and not creative_intent:
        try:
            from packages.cloud_brain.graph_answer import graph_answer_and_learn

            g = graph_answer_and_learn(graph_store, _entity(query), now)
            if g.get("answer"):
                return AnswerResult(
                    g["answer"], "graph_grounded", grounding=g.get("grounding", []),
                    certificate={"derivation_kind": "graph_grounded", "coverage": g.get("coverage"), "reinforced": g.get("reinforced")},
                    guarantees={"external_llm": False, "fabricated_facts": False, "learned_graph": True},
                )
        except Exception:
            pass

    # 3) multi-source synthesis (comprehensive) — each clause cited
    if corpus and not creative_intent:
        try:
            from packages.cgsr.cgsr.multisource_synth import synthesize

            s = synthesize(_entity(query), corpus)
            if s and s.text:
                return AnswerResult(
                    s.text, "multisource_synthesis", grounding=s.grounding,
                    certificate={"derivation_kind": "multisource_synthesis", "sources": len(s.grounding)},
                )
        except Exception:
            pass

    # 3.5) WEB — broad grounding so we rarely fall through (this is what makes abstention rare).
    if web_answer is not None and not creative_intent:
        try:
            w = web_answer(query)
            if w and w.get("answer"):
                return AnswerResult(
                    w["answer"], "web_grounded",
                    grounding=w.get("grounding") or w.get("sources") or [],
                    certificate=w.get("reasoning_certificate") or {"derivation_kind": "web_grounded"},
                )
        except Exception:
            pass

    # 4) creative (grounded blend / assumption-break with XAI)
    if creative_intent and corpus is not None:
        try:
            from packages.cgsr.cgsr.creative_engine import CreativeEngine

            triples = _triples_from_corpus(corpus)
            if len(triples) >= 4:
                ideas = CreativeEngine(triples).invent(top=1)
                if ideas:
                    idea = ideas[0]
                    return AnswerResult(
                        f"{idea.name_hint} — {idea.explain()}", "creative",
                        grounding=[list(t) for t in idea.grounding],
                        certificate={"derivation_kind": "creative_" + idea.operator, "creative_score": idea.creative_score},
                    )
        except Exception:
            pass

    # 5) NEVER a dead "I don't know": give the best partial grounding we have (hedged, never
    #    fabricated), or — only if there is genuinely nothing — a helpful redirect. Not abstention.
    return _best_effort(query, corpus, graph_store, language, now)


_SENT_SPLIT = re.compile(r"(?<=[.!?。])\s+")


_STOP_TOK = {"창업", "연도", "무엇", "누구", "언제", "어디", "어떻게", "회사", "사람", "정보", "관련"}


def _content_keys(query: str) -> list[str]:
    """Content tokens to probe partial grounding — head noun of the subject phrase plus long tokens."""
    ent = _entity(query)
    keys = [t for t in re.findall(r"[0-9A-Za-z가-힣]+", ent) if len(t) >= 2 and t not in _STOP_TOK]
    # strip a trailing josa off each key so '엔비디아는' also matches '엔비디아'
    out: list[str] = []
    for k in keys:
        out.append(k)
        stripped = re.sub(r"(은|는|이|가|을|를|의|에|와|과|도|만|으로|로)$", "", k)
        if stripped and stripped != k and len(stripped) >= 2:
            out.append(stripped)
    # longest first: the most specific entity token wins
    return sorted(dict.fromkeys(out), key=len, reverse=True)


def _best_effort(query: str, corpus: list[str] | None, graph_store: str | None, language: str, now: datetime) -> AnswerResult:
    keys = _content_keys(query)
    # (a) partial from corpus: a real sentence that MENTIONS the entity — surfaced, hedged.
    if corpus and keys:
        for key in keys:
            for text in corpus:
                for sent in _SENT_SPLIT.split(str(text or "")):
                    if key in sent and 10 <= len(sent) <= 240:
                        lead = "직접적인 정의는 못 찾았지만, 관련해 확인된 내용은 이래요: " if language == "ko" else "I couldn't find a direct definition, but here is related grounded context: "
                        return AnswerResult(lead + sent.strip(), "partial_grounded", grounding=[sent.strip()],
                                            certificate={"derivation_kind": "partial_grounding"})
    ent = _entity(query)
    # (b) partial from the graph (relaxed coverage) — any real facts about the entity.
    if graph_store and ent:
        try:
            from packages.cloud_brain.graph_answer import graph_answer_and_learn

            g = graph_answer_and_learn(graph_store, ent, now, min_coverage=0.0)
            if g.get("answer"):
                return AnswerResult(g["answer"], "partial_graph_grounded", grounding=g.get("grounding", []),
                                    certificate={"derivation_kind": "partial_graph", "coverage": g.get("coverage")})
        except Exception:
            pass
    # (c) genuinely nothing local + no web: a helpful redirect, NOT a dead abstention. (With web
    #     wired this almost never fires; you cannot ground the ungroundable without fabricating.)
    msg = (
        f"‘{query.strip()}’은(는) 지금 가진 근거만으로는 확정해서 답하기 어려워요. 조금만 더 구체적으로 알려주시면 바로 찾아드릴게요."
        if language == "ko"
        else f"I can't pin '{query.strip()}' down from what I have right now — give me a bit more and I'll find it."
    )
    return AnswerResult(msg, "needs_more", certificate={"derivation_kind": "insufficient_grounding_redirect"})


_ISA_SENT = re.compile(r"([가-힣A-Za-z0-9]+)(?:은|는|이|가)\s+.*?([가-힣A-Za-z0-9]+)(?:이다|입니다|이며)")


def _triples_from_corpus(corpus: list[str]) -> list[tuple[str, str, str]]:
    """Cheap IS_A triple mining from sentences for the creative engine (no ingestion pipeline)."""
    triples: list[tuple[str, str, str]] = []
    for text in corpus:
        for m in _ISA_SENT.finditer(str(text or "")):
            s, o = m.group(1), m.group(2)
            if s and o and s != o:
                triples.append((s, "IS_A", o))
    return triples
