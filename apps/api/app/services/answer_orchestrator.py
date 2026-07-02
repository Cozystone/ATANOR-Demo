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
  4. creative                  — conceptual blend / assumption-break with XAI (for creative intents),
                                 grounded in real graph structure.
  5. honest abstention         — say we don't know rather than guess.

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

    # 5) honest abstention
    msg = "확인된 근거로는 답할 수 없어요. 추측하지 않을게요." if language == "ko" else "I don't have grounded evidence to answer this. I won't guess."
    return AnswerResult(msg, "abstain", certificate={"derivation_kind": "honest_abstention"})


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
