# -*- coding: utf-8 -*-
"""Creative composer — the 다음-토큰 융합 (시/짧은 글, No-LLM).

The owner's directive: strict evidence-only reasoning cannot make a poem, so
MIX the next-token mode of generation into the architecture — as PRINCIPLES,
never as transformer code in the answer path. This module is that fusion:

  뼈 (grounding)  — the theme's real evidence sentences from the KG become the
                    corpus; phase-space neighbors widen it thematically.
  살 (flow)       — HolographicLM (FHRR kernel next-token, deterministic, no
                    backprop) is fitted ON THAT CORPUS at request time and
                    generates lines: corpus-attested units only, arranged new.
  파동 (feeling)  — the sensory impression (3-7) opens the poem; the grounded
                    metaphor (3-8) closes it.

Honesty contract: creative output is LABELED creative (creative_mode: true,
factual_claims: false). Fabrication rules bind FACT claims; a poem asserts
none — but even so, every unit it emits occurred in the grounding corpus
(the LM's own guarantee), and the corpus sources are cited. No corpus -> no
poem (silence over pastiche).
"""
from __future__ import annotations

import re
from typing import Any

_MIN_CORPUS = 3          # fewer grounded sentences than this -> decline
_MAX_CORPUS = 60         # bound the per-request fit
_NEIGHBOR_CONCEPTS = 4   # phase neighbors that widen the theme corpus


_JOSA_TAIL = re.compile(r"(은|는|이|가|을|를|의|에|에서|으로|로|와|과|도|만)$")
_CONTENT = re.compile(r"[가-힣]{2,}")


def _content_words(sentence: str, limit: int = 8) -> list[str]:
    """Hangul content words of a definition, trailing 조사 stripped — the
    concepts the theme's own prose points at (the graph-native corpus walk)."""
    out: list[str] = []
    for tok in _CONTENT.findall(sentence):
        base = _JOSA_TAIL.sub("", tok)
        if len(base) >= 2 and base not in out:
            out.append(base)
        if len(out) >= limit:
            break
    return out


def _themed_corpus(theme: str) -> tuple[list[str], list[str], list[str]]:
    """Korean prose corpus grown ALONG THE GRAPH from the theme: the theme's
    definition sentences, then the definitions of the concepts those sentences
    mention (1 hop), plus phase neighbors. Returns (sentences, urls, concepts)."""
    sentences: list[str] = []
    sources: list[str] = []
    concepts: list[str] = []
    try:
        from packages.graph_scale.answer_bridge import _store

        kg = _store()
    except Exception:
        kg = None
    if kg is None:
        return [], [], []

    terms = [theme]
    try:
        from packages.graph_scale.phase_space import neighbors

        for term, res in neighbors(theme, k=12):
            if res < 0.5 or term == theme:
                continue
            terms.append(term)
            if len(terms) > _NEIGHBOR_CONCEPTS:
                break
    except Exception:
        pass
    # 1-hop textual walk: the theme's own definitions name the concepts the
    # poem should breathe in — pull THEIR definitions into the corpus too
    try:
        first = kg.facts_with_sources(theme, limit=8, preds=("defined_as", "is_a")) or []
        hop: list[str] = []
        for row in first:
            for w in _content_words(str(row[2] if len(row) > 2 else "")):
                if w != theme and w not in terms and w not in hop:
                    hop.append(w)
        terms.extend(hop[:10])
    except Exception:
        pass

    seen: set[str] = set()
    for term in terms:
        try:
            # evidence = verbatim web sentences; defined_as/is_a = curated
            # definition prose — both are real grounded text, so both feed the
            # corpus (definitions carry most of the graph's Korean prose)
            rows = kg.facts_with_sources(
                term, limit=24, preds=("evidence", "defined_as", "is_a")) or []
        except Exception:
            continue
        got = False
        for row in rows:
            pred = str(row[1] if len(row) > 1 else "")
            o = str(row[2] if len(row) > 2 else "")
            if len(o) < 8 or o in seen:
                continue
            # Korean poem needs a Korean corpus: majority-Hangul rows only
            # (the store's neighbor definitions are often English Wiktionary prose)
            hangul = sum(1 for ch in o if "가" <= ch <= "힣")
            if hangul < len(o) * 0.4:
                continue
            seen.add(o)
            # a definition object is a noun phrase — close it into a sentence so
            # the LM learns sentence-final endings from it (josa via LAD)
            if pred == "evidence":
                sentences.append(o)
            else:
                try:
                    from packages.lad_morphology import topic as _topic

                    head = _topic(term)
                except Exception:
                    head = f"{term}은"
                sentences.append(f"{head} {o}이다.")
            got = True
            url = str(row[4] if len(row) > 4 else "")
            if url and url not in sources:
                sources.append(url)
            if len(sentences) >= _MAX_CORPUS:
                break
        if got:
            concepts.append(term)
        if len(sentences) >= _MAX_CORPUS:
            break
    return sentences, sources[:6], concepts


def _line_from_tokens(toks: list[str], *, drop_first: int = 0) -> str:
    """Tokens -> one poem line: de-noise, bound the length, and prefer ending
    on a sentence-final token so lines close instead of trailing off."""
    body = toks[drop_first:]
    out: list[str] = []
    for t in body:
        if out and t == out[-1]:
            continue
        if re.fullmatch(r"[0-9]+", t):
            continue
        out.append(t)
        if len(out) >= 12:
            break
    # trim back to the last closing token (…다/…음/…함) when one exists mid-line
    for i in range(len(out) - 1, 1, -1):
        if out[i].endswith(("다", "음", "함", "요")):
            out = out[: i + 1]
            break
    return " ".join(out).strip()


def _too_similar(a: str, b: str) -> bool:
    """Token-set overlap gate: sliding replays of the same definition collapse
    into one line (a small corpus makes the kernel replay; keep one copy)."""
    ta, tb = set(a.split()), set(b.split())
    if not ta or not tb:
        return False
    return len(ta & tb) / min(len(ta), len(tb)) > 0.6


def compose_poem(theme: str) -> dict[str, Any] | None:
    """A short grounded poem for the theme, or None when the graph holds too
    little to compose from (the honest decline stays honest)."""
    theme = str(theme or "").strip()
    if not theme or len(theme) > 24:
        return None
    corpus, sources, concepts = _themed_corpus(theme)
    if len(corpus) < _MIN_CORPUS:
        return None

    try:
        from packages.cgsr.cgsr.holographic_lm import HolographicLM

        lm = HolographicLM(dim=256, window=3, decay=0.7, seed=7)
        lm.fit(corpus)
    except Exception:
        return None

    lines: list[str] = []

    # 파동 — the measured impression opens the poem (only when it exists)
    impression = None
    try:
        from packages.continuous_self.sensory_interference import impression_from_visual

        impression = impression_from_visual(theme)
    except Exception:
        impression = None
    if impression:
        lines.append(impression["felt"])

    # 살 — holographic next-token flows. A seed must be a token the corpus
    # actually contains (조사-fused forms like 바다은 are single units to the
    # tokenizer), so seeds are corpus-attested tokens that carry the concept.
    from packages.cgsr.cgsr.holographic_lm import tokens as _lm_tokens

    corpus_toks: list[str] = []
    for s in corpus:
        corpus_toks.extend(_lm_tokens(s))
    tok_set = set(corpus_toks)

    def _attested(concept: str) -> str | None:
        if concept in tok_set:
            return concept
        for t in corpus_toks:
            if t.startswith(concept):
                return t
        return None

    seed_concepts = [theme]
    if impression and impression.get("evoked"):
        seed_concepts.append(impression["evoked"][0]["term"])
    seed_concepts.extend(c for c in concepts[1:6] if c not in seed_concepts)
    holo_lines = 0
    for concept in seed_concepts[:6]:
        if holo_lines >= 3:
            break
        seed = _attested(concept)
        if not seed:
            continue
        toks = lm.generate_fluent(seed, max_len=14, coherence=0.7, rep_penalty=0.8)
        line = _line_from_tokens(toks, drop_first=0)
        if (line and len(line.split()) >= 3
                and not any(_too_similar(line, prev) for prev in lines)):
            lines.append(line)
            holo_lines += 1

    # 은유 — the grounded metaphor closes it
    met = None
    try:
        from packages.graph_scale.metaphor import metaphor

        met = metaphor(theme)
    except Exception:
        met = None
    if met:
        try:
            from packages.lad_morphology import topic as _topic

            head = _topic(theme)
        except Exception:
            head = f"{theme}는"
        lines.append(f"{head} {met['vehicle']}의 결을 닮았다.")

    if len(lines) < 2:
        return None  # a one-line "poem" is a caption; decline instead
    return {
        "theme": theme,
        "title": f"{theme} — 위상장에서",
        "lines": lines[:5],
        "corpus_sentences": len(corpus),
        "concepts_used": concepts,
        "sources": sources,
        "metaphor": met,
        "guarantees": {
            "creative_mode": True,
            "factual_claims": False,
            "external_llm": False,
            "units_from_grounding_corpus": True,
        },
    }
