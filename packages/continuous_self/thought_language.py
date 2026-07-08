# -*- coding: utf-8 -*-
"""Generated inner speech — the self's thoughts are REALIZED BY THE LANGUAGE
ENGINE, never picked from a hand-written snippet table (owner hard directive
2026-07-08: 절대 자의식의 생각과정을 규칙기반 스니펫으로 하지 마).

Mechanism — everything already exists and is learned, nothing is templated:
  bones = the live state (driver, current topic, open question) decides what
          the thought is ABOUT;
  flesh = HolographicLM next-token flows, fit on the language the self actually
          holds for that topic (the graph's themed utterance corpus + the
          self's own accumulated narrative), decide HOW it is worded.

The wording therefore drifts as the self learns and remembers — two moments
with different histories think in different sentences. Where the self holds no
language for a topic, this returns None and the caller falls back to the old
line MARKED generated=False, so nothing ever pretends to be generated.
"""
from __future__ import annotations

import re
from typing import Any

_NARRATIVE_WINDOW = 120


def _topic_of(driver: str, facts: dict[str, Any]) -> str:
    explicit = str((facts or {}).get("topic") or "").strip()
    if explicit:
        return explicit[:16]
    return {
        "growth": "연결", "learning_active": "지식", "uncertainty": "생각",
        "curiosity_idle": "호기심", "idle": "고요", "user_present": "사람",
        "open_self_question": "물음", "resource_pressure": "숨",
    }.get(driver, "생각")


def realize_thought(driver: str, facts: dict[str, Any] | None, state: Any = None) -> str | None:
    """One generated line of inner speech, or None when the self holds too
    little language about the topic to speak from (the honest decline)."""
    topic = _topic_of(driver, facts or {})
    corpus: list[str] = []
    try:
        from packages.grounded_composer.creative_composer import _themed_corpus

        themed, _sources, _concepts = _themed_corpus(topic)
        corpus.extend((themed or [])[:40])
    except Exception:
        pass
    # The self's own lived narrative is corpus too — and it is WEIGHTED (x3):
    # the graph corpus is definition-register ("지식은 ~이다"), the narrative is
    # first-person observation register; without the weight the LM speaks like
    # an encyclopedia instead of a mind (measured). The voice literally grows
    # out of its history, which is what makes it a voice and not a table.
    narrative_lines: list[str] = []
    if state is not None:
        for entry in (getattr(state, "narrative", []) or [])[-_NARRATIVE_WINDOW:]:
            text = str((entry or {}).get("text") or "").strip()
            if len(text) >= 8:
                narrative_lines.append(text)
    corpus.extend(narrative_lines * 3)
    if len(corpus) < 6:
        return None
    try:
        from packages.cgsr.cgsr.holographic_lm import HolographicLM
        from packages.cgsr.cgsr.holographic_lm import tokens as _lm_tokens

        # ticks vary the generation walk: the same state a moment later thinks a
        # DIFFERENT sentence from the same lived language — variation from time,
        # not from a phrasing table.
        ticks = int(getattr(state, "ticks", 0) or 0)
        lm = HolographicLM(dim=256, window=3, decay=0.7,
                           seed=((abs(hash(driver)) * 31 + ticks) & 0xFFFF) or 7)
        lm.fit(corpus)
        corpus_tokens: list[str] = []
        for sentence in corpus:
            corpus_tokens.extend(_lm_tokens(sentence))
        # Seed preference: a topic-bearing token from the self's OWN narrative
        # first (observation register: "지식이…"), the bare noun only as a last
        # resort (that seed tends to continue into a dictionary definition).
        seed = None
        seed_pool: list[str] = []
        for line in narrative_lines:
            if topic in line:
                for tok in _lm_tokens(line):
                    if tok.startswith(topic) and tok not in seed_pool:
                        seed_pool.append(tok)
        if seed_pool:
            seed = seed_pool[ticks % len(seed_pool)]
        if seed is None:
            seed = next((t for t in corpus_tokens if t.startswith(topic) and len(t) > len(topic)), None)
        if seed is None and topic in corpus_tokens:
            seed = topic
        if seed is None:
            question = str((facts or {}).get("question") or "").strip()
            if question:
                q_tokens = _lm_tokens(question)
                seed = next((t for t in corpus_tokens if q_tokens and t == q_tokens[0]), None)
        if seed is None:
            return None
        out = lm.generate_fluent(seed, max_len=13, coherence=0.7, rep_penalty=0.85)
        line = " ".join(out).strip() if isinstance(out, (list, tuple)) else str(out or "").strip()
        line = re.sub(r"\s+", " ", line)
        # quality gate: a thought must be a readable clause, not token debris
        if len(line) < 10 or len(line.split()) < 3:
            return None
        if not line.endswith(("다", ".", "요", "까", "지", "네")):
            line += " …"  # an unfinished thought reads as thinking — honest trail-off
        return line[:90]
    except Exception:
        return None
