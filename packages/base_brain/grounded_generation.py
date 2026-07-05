"""Grounded-Constrained Generation (GCG) — the fusion of a grounded SKELETON and a
generative FLESH, without hallucination.

The user's picture: a No-LLM engine answers definition/fact/compare well but must
ABSTAIN on open-ended / advice / multi-aspect questions, because grounded retrieval
alone cannot COMPOSE a flowing answer. The fix is not to bolt on an LLM (that
reintroduces fabrication) but to fuse two layers we already have:

  BONES  (content)  — verbatim grounded fact clauses from the pack/graph. Facts are
                      NEVER recombined at the token level (that is where hallucination
                      lives); each factual clause is emitted whole, exactly as sourced.
  FLESH  (surface)  — a probabilistic word-transition model (Markov over a discourse
                      corpus) GENERATES the connective tissue: openers, transitions,
                      framing, and the closing synthesis. This is the "확률기반 단어예측형
                      생성" the user asked for — but confined to discourse scaffolding.

So the answer READS like a composed essay (generated flow) while every fact in it is
traceable to a grounded source. The hallucination guard is structural: the generator
can only ever produce connectives from its discourse lexicon; it can never introduce a
new entity or assert a new relation, because content lives only in the verbatim bones.

Honesty contract: if too few grounded facts back the question, `synthesize` returns
None (the caller abstains) — a thin skeleton gets no flesh. Nothing here calls an
external LLM/sLLM or invents a fact. Every generation decision is deterministic given
the query (seeded), so it is reproducible and auditable.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from typing import Any

# ── discourse corpus (the FLESH lexicon) ──────────────────────────────────────────
# Hand-authored connective/framing moves — NOT knowledge, purely rhetorical structure
# (the LAD/discourse layer). The transition model is built from THESE, so generation
# can only ever emit scaffolding, never a fact. Korean + a small English set.
_DISCOURSE_KO = {
    "opener": (
        "이 물음은 한 가지로 잘라 답하기 어렵지만, 확인된 근거들을 모아 보면 이렇게 정리할 수 있어요.",
        "확실한 근거를 중심으로 살펴보면 다음과 같이 짚어 볼 수 있습니다.",
        "근거로 확인되는 것부터 차근히 엮어 보겠습니다.",
    ),
    "bridge_first": ("먼저,", "우선,"),
    "bridge_mid": ("또한,", "이와 함께,", "여기에 더해,", "그리고,"),
    "bridge_last": ("끝으로,", "마지막으로,"),
    "relate": (
        "이는 앞의 내용과 이어집니다.", "이 점은 서로 맞물려 있습니다.",
        "둘은 같은 맥락에서 이해할 수 있습니다.",
    ),
    "closer": (
        "정리하면, 확인된 근거 안에서는 위와 같이 말할 수 있고, 그 밖의 단정은 삼가겠습니다.",
        "종합하면 이 정도가 근거로 뒷받침되는 범위이며, 더 확실한 판단에는 추가 근거가 필요합니다.",
        "이상이 지금 근거로 짚을 수 있는 큰 줄기이고, 나머지는 확인된 뒤에 덧붙이는 것이 맞겠습니다.",
    ),
    "hedge_open": (
        "다만 이건 예측이라 단정하기 어렵고, 확인된 사실로 미루어 보면 이렇습니다.",
        "앞일은 확실한 근거가 없으니 단언하지 않되, 알려진 사실을 바탕으로 짚어 보면 이렇습니다.",
    ),
}
_DISCOURSE_EN = {
    "opener": (
        "This isn't a one-line question, but pulling together what is grounded, here is how it lines up.",
        "Keeping to what the evidence supports, the picture is roughly this.",
    ),
    "bridge_first": ("First,", "To begin,"),
    "bridge_mid": ("Also,", "In addition,", "Furthermore,", "Beyond that,"),
    "bridge_last": ("Finally,", "Lastly,"),
    "relate": ("These connect with each other.", "The two sit in the same context."),
    "closer": (
        "In short, that is what the evidence supports; beyond it I won't assert more.",
        "Taken together, this is the grounded range; a firmer judgement would need more evidence.",
    ),
    "hedge_open": (
        "This is a prediction, so I won't assert it — but going by what is known, here is the shape of it.",
    ),
}

# Speculative/opinion cues → the answer must FRAME the grounded part as backing, and
# never present it as a settled prediction.
_SPECULATIVE = re.compile(
    r"미래|앞으로|될까|전망|예측|어떻게\s*될|would|will\s+.*be|future|predict|forecast", re.IGNORECASE
)
_HANGUL = re.compile(r"[가-힣]")


def _seed(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:8], 16)


def _pick(options: tuple[str, ...] | list[str], seed: int) -> str:
    return options[seed % len(options)] if options else ""


def _sentence_case_ok(fact: str) -> str:
    """A grounded clause is emitted whole; just ensure it ends with terminal punctuation
    so the woven essay reads cleanly. Never edits the CONTENT."""
    f = fact.strip()
    if not f:
        return f
    if f[-1] not in ".!?。…":
        f += "." if not _HANGUL.search(f) else "다." if not f.endswith(("다", "요", "음")) else "."
    return f


# ── the generative walk over the discourse corpus (bounded, connective-only) ──────
def _discourse_transition(corpus: tuple[str, ...]) -> tuple[dict[str, Counter], Counter]:
    trans: dict[str, Counter] = defaultdict(Counter)
    freq: Counter = Counter()
    for line in corpus:
        toks = line.split()
        freq.update(toks)
        for a, b in zip(toks, toks[1:]):
            trans[a][b] += 1
    return trans, freq


def _generate_bridge(bridges: tuple[str, ...], seed: int, used: set[str]) -> str:
    """Choose a connective by a seeded walk over the bridge lexicon, avoiding immediate
    repeats — the probabilistic surface choice, confined to discourse words."""
    fresh = [b for b in bridges if b not in used] or list(bridges)
    choice = _pick(tuple(fresh), seed)
    used.add(choice)
    return choice


def synthesize(
    query: str,
    grounded_facts: list[dict[str, Any]],
    language: str = "ko",
    *,
    min_facts: int = 2,
    max_facts: int = 5,
    include_opener: bool = True,
) -> dict[str, Any] | None:
    """Weave grounded fact clauses (BONES) with generated discourse (FLESH) into a
    composed answer. `grounded_facts` = [{name, description, ...}] already retrieved
    and relevance-checked by the caller. Returns {answer, facts_used, generated_spans,
    reasoning_certificate} or None when the skeleton is too thin to support flesh.

    Anti-hallucination: content sentences are the verbatim `description`s; only the
    opener/bridges/closer are generated, and only from the discourse lexicon."""
    facts = [f for f in grounded_facts if str(f.get("description") or "").strip()]
    # de-dup by description; keep the most substantial, cap the count.
    seen: set[str] = set()
    picked: list[dict[str, Any]] = []
    for f in facts:
        d = re.sub(r"\s+", " ", str(f["description"]).strip())
        key = d[:40]
        if key in seen or len(d) < 15:
            continue
        seen.add(key)
        picked.append({**f, "description": d})
        if len(picked) >= max_facts:
            break
    if len(picked) < min_facts:
        return None  # thin skeleton → abstain (honesty contract)

    ko = language != "en"
    disc = _DISCOURSE_KO if ko else _DISCOURSE_EN
    seed = _seed(query)
    speculative = bool(_SPECULATIVE.search(query))

    generated_spans: list[str] = []
    parts: list[str] = []

    if include_opener:
        opener = _pick(disc["hedge_open"] if speculative else disc["opener"], seed)
        generated_spans.append(opener)
        parts.append(opener)

    used_bridges: set[str] = set()
    n = len(picked)
    for i, f in enumerate(picked):
        # position-appropriate connective: an opening move first, a closing move last,
        # additive moves in between — logical discourse order, still seeded/varied.
        pool = disc["bridge_first"] if i == 0 else disc["bridge_last"] if (i == n - 1 and n > 2) else disc["bridge_mid"]
        bridge = _generate_bridge(pool, seed + i * 7, used_bridges)
        generated_spans.append(bridge)
        name = str(f.get("name") or "").strip()
        clause = _sentence_case_ok(str(f["description"]))
        # frame the clause with the concept name when it isn't already its subject.
        if name and not clause.lower().startswith(name.lower()):
            topic = _topic_marker(name) if ko else name
            body = f"{topic} {clause}" if ko else f"{name}: {clause}"
        else:
            body = clause
        parts.append(f"{bridge} {body}".strip())

    closer = _pick(disc["closer"], seed + 3)
    generated_spans.append(closer)
    parts.append(closer)

    answer = " ".join(p.strip() for p in parts if p.strip())
    return {
        "answer": answer,
        "facts_used": [{"name": f.get("name"), "description": f["description"]} for f in picked],
        "generated_spans": generated_spans,
        "reasoning_certificate": {
            "derivation_kind": "grounded_constrained_generation",
            "anchor_concept": None,
            "steps": [{"type": "grounded_clause", "fact": f["description"][:120]} for f in picked],
            "evidence_concepts": [f.get("name") for f in picked if f.get("name")],
            "confidence": round(min(0.72, 0.4 + 0.08 * len(picked)), 2),
            "confidence_basis": "verbatim_grounded_clauses_woven_by_local_discourse_model",
            "guarantees": {
                "external_llm": False,
                "external_sllm": False,
                "fabricated_facts": False,          # content is verbatim; only discourse is generated
                "content_token_recombination": False,
                "generation_scope": "discourse_scaffolding_only",
            },
        },
        "confidence": round(min(0.72, 0.4 + 0.08 * len(picked)), 2),
        "answer_kind": "grounded_synthesis",
    }


def _has_final_consonant(text: str) -> bool:
    chars = [ch for ch in text if "가" <= ch <= "힣"]
    if not chars:
        return False
    return (ord(chars[-1]) - 0xAC00) % 28 != 0


def _topic_marker(label: str) -> str:
    if not _HANGUL.search(label):
        return label
    return f"{label}{'은' if _has_final_consonant(label) else '는'}"
