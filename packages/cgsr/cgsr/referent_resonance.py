"""Referent-type resonance: emergent selectivity for evidence, not string rules.

The whole class of "tiny" answer bugs — 빌게이츠→빌게이츠꽃등에(a fly), 일론 머스크→
X(소셜 네트워크), 너 누구야→a dictionary entry for the pronoun 너 — share ONE root
cause: the engine picked evidence by surface-token overlap, with no model of WHAT
KIND of thing the question is about. It matched strings, not referents.

Inspired by Baek/Song/Paik, *Nature Communications* 2021 ("Face detection in
untrained deep neural networks"): category selectivity emerges in a randomly
initialized network "solely from statistical variations of the feedforward
projections" — selectivity from STRUCTURE, with no training. We realize the same
principle in ATANOR's wave substrate:

- Each ontological TYPE (person / org / organism / work / place / concept / self)
  is encoded as a fixed PHASE CHORD — K oscillators whose phases are seeded
  deterministically from the type name (the "random but fixed feedforward
  projection"). No training, no per-entity rules.
- Resonance between two types = the mean two-wave interference cos(Δφ) across the
  K oscillators. SAME type → constructive (≈1). DIFFERENT type → the random phases
  average out → destructive (≈0). Crisp category separation EMERGES from the phase
  structure, exactly as selectivity emerges in the untrained network.

A "who" question expects a PERSON; evidence about a fly (ORGANISM) or a website
(ORG) destructively interferes and is suppressed — one mechanism instead of a
dozen string patches.
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import Iterable


# ---- ontological types -----------------------------------------------------

PERSON = "person"
ORG = "org"
ORGANISM = "organism"  # animal / plant / species — named-after-a-person traps live here
WORK = "work"  # film / song / novel / game
PLACE = "place"
CONCEPT = "concept"
SELF = "self"  # ATANOR itself
UNKNOWN = "unknown"

_ALL_TYPES = (PERSON, ORG, ORGANISM, WORK, PLACE, CONCEPT, SELF)

# Category words → type. These are CATEGORY nouns ("기업인", "꽃등에", "소셜 네트워크"),
# never instance names ("미국", "마이크로소프트"), so the map generalizes to any entity.
# Korean is head-final: the defining category is the noun right before the copula
# ("X는 … 기업인이다"), so inference anchors on a following copula rather than on the
# earliest mention (a movie's blurb mentions its 감독, but its HEAD category is 영화).
_TYPE_LEXICON: tuple[tuple[str, tuple[str, ...]], ...] = (
    (ORGANISM, (
        "고유종", "아종", "종", "동물", "포유류", "곤충", "꽃등에", "파리", "식물", "새", "조류",
        "물고기", "어류", "균", "박테리아", "바이러스", "나비", "딱정벌레", "갑각류", "양서류", "파충류",
        "species", "animal", "insect", "fly", "plant", "bird", "fish", "mammal", "fungus", "bacteri",
    )),
    (WORK, (
        "영화", "애니메이션", "장편", "단편", "노래", "싱글", "음반", "앨범", "소설", "드라마", "만화", "웹툰",
        "게임", "시리즈", "작품", "시집", "희곡", "뮤지컬",
        "film", "movie", "song", "single", "album", "novel", "drama", "manga", "game", "series", "poem",
    )),
    (ORG, (
        "기업", "회사", "법인", "그룹", "재단", "소셜 네트워크", "네트워크", "플랫폼", "서비스",
        "은행", "대학교", "대학", "정당", "단체", "협회", "연맹", "스튜디오", "레이블", "코퍼레이션",
        "company", "corporation", "enterprise", "social network", "platform", "service",
        "bank", "university", "organization", "agency", "studio", "label",
    )),
    (PLACE, (
        "도시", "광역시", "특별시", "국가", "나라", "지역", "지방", "마을", "산맥", "행성", "위성", "대륙",
        "강", "호수", "수도", "county", "city", "country", "nation", "region", "town", "mountain",
        "river", "planet", "continent",
    )),
    (PERSON, (
        "사람", "기업인", "사업가", "정치인", "물리학자", "과학자", "수학자", "화학자", "생물학자",
        "발명가", "발명자", "감독", "배우", "가수", "작가", "소설가", "시인", "화가", "철학자",
        "황제", "대통령", "국왕", "여왕", "왕", "장군", "엔지니어", "프로그래머", "교수", "선수",
        "ceo", "founder", "businessman", "businessperson", "magnate", "politician", "physicist",
        "scientist", "inventor", "director", "actor", "actress", "singer", "author", "novelist",
        "painter", "philosopher", "emperor", "president", "engineer", "professor", "athlete",
    )),
    (CONCEPT, (
        "개념", "이론", "법칙", "현상", "원리", "기술", "언어", "알고리즘", "방법론", "힘", "인력", "반응",
        "분야", "학문", "과정", "에너지", "단위", "물질", "원소", "질병", "force", "theory", "law",
        "phenomenon", "concept", "language", "algorithm", "method", "field", "process", "energy",
    )),
)

# A category noun counts as the HEAD category when it is immediately followed by a
# copula / case marker / clause boundary (head-final predicate or a title paren).
_COPULA = r"(?:이다|입니다|이고|이며|이라|예요|이에요|으로|로|이자|는|은|\)|\.|,|·|;|:|$)"


# ---- phase-chord encoding (the "untrained feedforward projection") ----------

_K = 8  # oscillators per type chord


def _type_phases(type_name: str) -> list[float]:
    """K fixed phases for a type, seeded from its name. This is the random-but-fixed
    projection; selectivity emerges from it without any training."""
    phases: list[float] = []
    for k in range(_K):
        digest = hashlib.md5(f"{type_name}:{k}".encode("utf-8")).hexdigest()
        frac = int(digest[:8], 16) / 0xFFFFFFFF
        phases.append(2.0 * math.pi * frac)
    return phases


_PHASE_TABLE = {t: _type_phases(t) for t in _ALL_TYPES}


def resonance(type_a: str, type_b: str) -> float:
    """Two-wave interference between two type chords: mean cos(Δφ) over K oscillators.
    Same type → ~1 (constructive); different types → ~0 (destructive)."""
    if type_a == type_b and type_a != UNKNOWN:
        return 1.0
    pa = _PHASE_TABLE.get(type_a)
    pb = _PHASE_TABLE.get(type_b)
    if not pa or not pb:
        return 0.5  # unknown on either side → neutral, don't suppress
    total = sum(math.cos(a - b) for a, b in zip(pa, pb))
    return max(0.0, total / _K)


# ---- type inference --------------------------------------------------------

def infer_evidence_type(text: str) -> str:
    """The ontological type a fact/summary DESCRIBES, from its head category noun.

    Two passes: (1) a category word anchored by a following copula/boundary is the
    head predicate ('…기업인이다' → person, '…영화이다' → work, even though the blurb
    also names a 감독); the earliest such anchored category wins. (2) Fallback to the
    earliest bare category word if nothing is copula-anchored."""
    head = (text or "")[:160].lower()
    best_type, best_pos = UNKNOWN, 10**9
    for type_name, words in _TYPE_LEXICON:
        for word in words:
            m = re.search(re.escape(word.lower()) + _COPULA, head)
            if m and m.start() < best_pos:
                best_pos, best_type = m.start(), type_name
    if best_type != UNKNOWN:
        return best_type
    # fallback: earliest bare category mention
    for type_name, words in _TYPE_LEXICON:
        for word in words:
            pos = head.find(word.lower())
            if 0 <= pos < best_pos:
                best_pos, best_type = pos, type_name
    return best_type


_WHO = ("누구", "누군", "who")
_FOUNDER = ("창립자", "창업자", "설립자", "발명자", "발명가", "감독", "저자", "작곡가", "founder", "inventor", "director", "author")
_SELF_REF = ("너", "넌", "네", "너는", "당신", "그대", "자네", "atanor", "아타노르", "yourself")


def query_expected_type(question: str) -> str:
    """The type the ANSWER to this question should be. Only the strongly-typed
    interrogatives get a gate; '뭐야/무엇' stays permissive (UNKNOWN) because the
    answer could be a concept, an org, a work, etc."""
    raw = (question or "").strip()
    low = raw.lower()
    compact = re.sub(r"\s+", "", raw)
    # self-reference identity ("너 누구야", "ATANOR가 뭐야") — handled by the identity path,
    # but tag it so grounding never answers it with a pronoun/film.
    if any(p in compact for p in ("atanor", "아타노르")) or re.match(r"^(너|넌|네|너는|당신)\b", raw) or compact[:2] in ("너누", "넌누", "너는"):
        return SELF
    if any(m in raw for m in _FOUNDER) and any(w in low for w in _WHO):
        return PERSON
    if any(w in low for w in _WHO):
        return PERSON
    if any(w in low for w in ("어디", "where")):
        return PLACE
    return UNKNOWN  # 뭐야/무엇/etc. → no type gate


def select_resonant_facts(
    question: str,
    facts: Iterable[tuple[str, str, int, int]],
    *,
    threshold: float = 0.45,
) -> tuple[list[tuple[str, str, int, int]], str]:
    """Keep only facts whose described type RESONATES with the question's expected
    type (constructive interference). Returns (kept_facts, expected_type).

    Each fact item is (clean_text, role, index, relevance) — the tuple used by the
    grounding ranker. When the expected type is UNKNOWN/SELF this is a no-op for the
    PERSON gate (SELF is routed to the identity path upstream)."""
    expected = query_expected_type(question)
    items = list(facts)
    if expected in (UNKNOWN, SELF):
        return items, expected
    kept = [item for item in items if resonance(expected, infer_evidence_type(item[0])) >= threshold]
    return kept, expected
