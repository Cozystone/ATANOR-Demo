"""Semantic-neighborhood gathering — so probabilistic synthesis can answer from the
CONSTELLATION of related grounded facts, not only an exact-match concept.

The gap that made the engine abstain far too often: retrieval is name/token based, so a
Korean query ("인공지능이 뭐야?") finds NOTHING even when the pack holds 16 facts ABOUT AI
(AI 모델 학습, 신경망, 추론 …) — different words, so no token match. An LLM answers such a
question by composing from everything it knows around the topic; it doesn't need a node
literally named 인공지능. This module gives the No-LLM engine the same reach WITHOUT
fabrication: it gathers the genuinely-related grounded facts (the neighborhood) so the
grounded-constrained generator can weave them into an honest, composed answer.

Three ways a concept enters the neighborhood (ADDITIVE, all grounded):
  1. NAME/LABEL/ALIAS match (what plain retrieval already does).
  2. DESCRIPTION-content match — a concept whose verbatim description shares the query's
     content words (finds 리더-related facts for a 리더십 query even if unnamed).
  3. DOMAIN BRIDGE — a small, bounded language-equivalence map (LAD layer, like the
     particle/외래어 rules) for high-frequency terms whose cross-lingual / synonym form
     never appears literally in any description (인공지능→AI/신경망/기계학습, 행복→
     happiness/만족 …). This is language equivalence, NOT knowledge; the KNOWLEDGE still
     comes only from the matched concepts' verbatim descriptions.

The relevance bar stays honest: a concept joins only on a real lexical/bridge overlap
with the query, and the synthesis is framed as "정확한 정의는 없지만 관련 근거로 미루어" so
it never masquerades as a definition it doesn't have.
"""
from __future__ import annotations

import re
from typing import Any

_HANGUL = re.compile(r"[가-힣]")

# LAD-layer language/synonym bridge for high-frequency query heads whose equivalent
# never appears literally in the (often English) descriptions. Bounded + honest: it
# only decides WHICH grounded concepts are topically relevant, never supplies content.
_DOMAIN_BRIDGE: dict[str, tuple[str, ...]] = {
    "인공지능": ("ai", "artificial intelligence", "기계학습", "머신러닝", "신경망", "딥러닝", "추론", "학습"),
    "ai": ("인공지능", "artificial intelligence", "신경망", "기계학습"),
    "머신러닝": ("machine learning", "기계학습", "학습", "신경망", "ai"),
    "기계학습": ("machine learning", "머신러닝", "학습", "신경망"),
    "딥러닝": ("deep learning", "신경망", "neural", "학습"),
    "컴퓨터": ("computer", "cpu", "gpu", "연산", "프로세서"),
    "인터넷": ("internet", "network", "네트워크", "웹", "http"),
    "행복": ("happiness", "만족", "즐거움", "긍정", "감정", "웰빙"),
    "리더십": ("leadership", "리더", "지도자", "이끄는", "관리", "통솔"),
    "리더": ("leader", "지도자", "이끄는", "통솔"),
    "민주주의": ("democracy", "선거", "시민", "정치", "자유"),
    "경제": ("economy", "economic", "시장", "금융", "무역"),
    "우주": ("universe", "cosmos", "은하", "행성", "항성", "천체"),
    "생명": ("life", "생물", "세포", "유기체"),
    "언어": ("language", "문법", "단어", "의미", "표현"),
    "예술": ("art", "예술가", "작품", "미술", "음악"),
    "역사": ("history", "역사적", "시대", "과거"),
    "과학": ("science", "scientific", "연구", "실험", "이론"),
    "철학": ("philosophy", "사상", "존재", "인식", "윤리"),
}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "").lower()).strip()


# Trailing Korean particles/endings to strip so a query token matches the bare concept
# (인공지능이 → 인공지능, 컴퓨터에 → 컴퓨터). Longest first so 이란/으로 beat 이/으.
_KO_TAIL = ("이란", "으로", "에서", "에게", "이라고", "라고", "은", "는", "이", "가", "을", "를",
            "에", "의", "도", "만", "과", "와", "란", "이나", "나", "로", "께", "이야", "야")


def _strip_ko_tail(token: str) -> str:
    for p in _KO_TAIL:
        if token.endswith(p) and len(token) - len(p) >= 2:
            return token[: -len(p)]
    return token


_STOP = {"무엇", "뭐야", "뭔가", "이란", "란", "인가", "대해", "설명", "알려", "어떻게", "왜",
         "무슨", "설명해", "알려줘", "되려면", "the", "what", "is", "are", "a", "an", "of",
         "about", "how", "why", "것", "게", "거"}

# Kiwi (morphological analyser) is OPTIONAL: when installed it gives robust Korean noun
# extraction (proper 조사/어미 stripping, incl. cases the regex misses like 철학이라는);
# when absent we fall back to the regex. Lazy singleton — the ~1s init happens once, and
# warm throughput is ~30k queries/sec, so it never slows the retrieval hot path. It does
# NOT replace the domain bridge: morphology can't know 인공지능 ≈ AI (that is semantics).
_KIWI = None
_KIWI_TRIED = False


def _kiwi():
    global _KIWI, _KIWI_TRIED
    if _KIWI_TRIED:
        return _KIWI
    _KIWI_TRIED = True
    try:
        from kiwipiepy import Kiwi

        _KIWI = Kiwi()
    except Exception:
        _KIWI = None
    return _KIWI


def _kiwi_noun_phrases(text: str) -> set[str]:
    """Compound-preserving noun extraction: JOIN adjacent noun morphemes so 인공+지능 ->
    인공지능 (not split), while particles/endings are dropped by the analyser. Returns an
    empty set if Kiwi is unavailable (caller falls back to the regex)."""
    kw = _kiwi()
    if kw is None:
        return set()
    out: set[str] = set()
    cur = ""
    try:
        for tok in kw.tokenize(text):
            if tok.tag in ("NNG", "NNP", "SL"):   # 일반/고유명사 + 외국어(Latin) run together
                cur += tok.form
            else:
                if len(cur) >= 2:
                    out.add(cur.lower())
                cur = ""
        if len(cur) >= 2:
            out.add(cur.lower())
    except Exception:
        return set()
    return {t for t in out if t not in _STOP}


def _content_tokens(text: str) -> set[str]:
    latin = set(re.findall(r"[a-z0-9]{2,}", _norm(text)))
    # prefer Kiwi's morphological nouns; fall back to particle-stripped regex tokens.
    korean = _kiwi_noun_phrases(str(text or ""))
    if not korean:
        korean = {_strip_ko_tail(t) for t in re.findall(r"[가-힣]{2,}", str(text or ""))}
    return {t for t in (latin | korean) if t not in _STOP and len(t) >= 2}


def _expand_query_terms(query: str) -> tuple[set[str], set[str]]:
    """Return (all_terms, primary_terms). primary = the query's OWN content tokens + their
    bridge equivalents that are specific enough (>= 2 Korean chars / >= 3 Latin) to anchor
    relevance. A concept joins the neighbourhood only if it hits a PRIMARY term, so a weak
    incidental 2-gram never drags in an off-topic concept."""
    toks = _content_tokens(query)
    primary: set[str] = set(toks)
    for t in toks:
        for bridged in _DOMAIN_BRIDGE.get(t, ()):
            b = _norm(bridged)
            if (b.isascii() and len(b) >= 3) or (not b.isascii() and len(b) >= 2):
                primary.add(b)
    return primary, primary


def _concept_text(concept: dict[str, Any]) -> str:
    labels = concept.get("labels") or {}
    return " ".join([
        str(concept.get("canonical_name") or ""),
        *[str(v) for v in labels.values()],
        *[str(a) for a in (concept.get("aliases") or [])],
        str(concept.get("short_description") or ""),
    ])


def gather_neighborhood(
    query: str, concepts: list[dict[str, Any]], *, limit: int = 6, min_overlap: int = 1
) -> list[dict[str, Any]]:
    """Return grounded concepts topically related to the query — by name/label, by
    description-content overlap, or via the domain bridge — each with a `neighbor_score`.
    Only concepts with a real description are eligible (they must carry a fact to weave)."""
    terms, primary = _expand_query_terms(query)
    if not terms:
        return []
    scored: list[tuple[float, dict[str, Any]]] = []
    for c in concepts:
        desc = str(c.get("short_description") or "").strip()
        if len(desc) < 15:
            continue
        text = _norm(_concept_text(c))
        hits = {t for t in terms if t and t in text}
        # relevance REQUIRES a primary-term hit — an incidental short 2-gram alone never
        # pulls in an off-topic concept (제주 for a 우주 query, etc.).
        if not (hits & primary):
            continue
        name_text = _norm(str(c.get("canonical_name") or "") + " " + " ".join(str(v) for v in (c.get("labels") or {}).values()))
        name_hits = sum(1 for t in hits if t in name_text)
        score = len(hits) + name_hits * 1.5
        scored.append((score, c))
    scored.sort(key=lambda it: (-it[0], len(str(it[1].get("short_description") or ""))))
    return [c for _, c in scored[:limit]]
