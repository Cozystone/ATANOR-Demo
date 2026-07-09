# -*- coding: utf-8 -*-
"""The Surgeon — real-time contamination excision for the self-aware graph.

Owner directive (2026-07-09): ATANOR's self-aware AI should catch contamination
and errors in REAL TIME, like a surgeon — a precise excision with a stated
reason, not a carpet sweep.

The blade is TYPE DISJOINTNESS, read from the graph itself. A single entity
belongs to ONE top-type family: 방콕 is a PLACE, 청교도 is a GROUP, 소크라테스 is
a PERSON. When an edge (or a freshly-derived candidate) would make an entity a
member of a family DISJOINT from the one it already occupies — '방콕 is_a 청교도',
'Florence Nightingale(film) is_a Website' — that is a sense-collision error, and
the Surgeon flags it with the exact conflicting families as the reason.

This is data-driven: both the subject's established types and the object's own
types are read from the graph's is_a edges and mapped to top families; the
family map is a small SURFACE ontology (DBpedia upper types + KO labels), the
same LAD-layer tier as morphology — it is type structure, not world knowledge.

Read-only and non-destructive by default: inspect() and scan() return verdicts
+ reasons; the operator/self-loop decides to quarantine (reuses the reversible
tombstone ledger). Never auto-deletes production."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# TOP-TYPE FAMILIES — mutually disjoint upper ontology (surface tier). A term is
# classified by keyword hit on its type labels. Extend by adding keywords; a
# term hitting two families is itself ambiguous and is treated as unknown.
# Keywords are matched as substrings, so they must be DISTINCTIVE — no 1-char
# Korean tokens (동/구/군/산/강 collide inside 동물, 대구, …). Multi-char only.
_FAMILIES: dict[str, tuple[str, ...]] = {
    "PLACE": ("place", "settlement", "city", "town", "village", "country", "region",
              "location", "지역", "도시", "나라", "국가", "마을", "수도", "특별시", "광역시",
              "river", "mountain", "administrativeregion", "capital city"),
    "PERSON": ("person", "human", "인물", "사람", "politician", "scientist", "artist",
               "writer", "player", "actor", "선수", "정치인", "철학자", "학자", "배우", "가수"),
    "GROUP": ("group", "ethnicgroup", "민족", "religion", "종교", "집단", "청교도",
              "부족", "종파", "신자", "교파", "교도", "sect", "denomination"),
    "ORG": ("organisation", "organization", "company", "조직", "회사", "기업", "단체",
            "institution", "agency", "정당", "party", "university", "대학교", "구단"),
    "WORK": ("creativework", "film", "movie", "book", "song", "album",
             "작품", "영화", "노래", "앨범", "website", "software", "게임"),
    "EVENT": ("event", "battle", "conflict", "사건", "전쟁", "전투", "대회",
              "election", "선거", "competition"),
    "SPECIES": ("species", "animal", "plant", "생물", "동물", "식물", "물고기", "fish",
                "bird", "insect", "곤충", "genus"),
    "SUBSTANCE": ("substance", "compound", "chemical", "물질", "화합물", "원소", "element",
                  "재료", "음식", "음료"),
}


# HARD-DISJOINT family pairs — physically incompatible (a place is not a person
# / species / substance / group / work; a person is not a species / substance /
# work; …). The Surgeon cuts ONLY on these, so a marginal ORG/GROUP overlap
# isn't excised — precision over recall, the surgeon's rule.
_HARD_DISJOINT: set[frozenset[str]] = {
    frozenset(p) for p in [
        ("PLACE", "PERSON"), ("PLACE", "GROUP"), ("PLACE", "SPECIES"),
        ("PLACE", "SUBSTANCE"), ("PLACE", "WORK"), ("PLACE", "EVENT"),
        ("PERSON", "SPECIES"), ("PERSON", "SUBSTANCE"), ("PERSON", "WORK"),
        ("PERSON", "PLACE"), ("SPECIES", "SUBSTANCE"), ("SPECIES", "WORK"),
        ("SPECIES", "ORG"), ("SPECIES", "EVENT"), ("SUBSTANCE", "WORK"),
        ("SUBSTANCE", "ORG"), ("SUBSTANCE", "EVENT"),
    ]
}


@dataclass
class Verdict:
    subject: str
    obj: str
    status: str                    # clean | suspect | contaminated
    reason: str
    subject_family: str | None = None
    obj_family: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"subject": self.subject, "object": self.obj, "status": self.status,
                "reason": self.reason, "subject_family": self.subject_family,
                "object_family": self.obj_family}


def _family_of_label(label: str) -> str | None:
    lab = (label or "").lower()
    hits = {fam for fam, kws in _FAMILIES.items() if any(k in lab for k in kws)}
    return next(iter(hits)) if len(hits) == 1 else None


def _isa_parents(store: Any, term: str, limit: int = 30) -> list[str]:
    try:
        return [str(o) for _s, p, o in (store.facts_about(term, limit=limit) or [])
                if p in ("is_a", "instance_of", "subclass_of") and o]
    except Exception:
        return []


def _entity_family(store: Any, term: str, *, exclude: str | None = None) -> str | None:
    """Dominant top-type family of a term, from its OWN label + its is_a parents.
    exclude drops one parent (the edge under test) so we read prior context."""
    from collections import Counter
    votes: Counter = Counter()
    f0 = _family_of_label(term)
    if f0:
        votes[f0] += 1
    for par in _isa_parents(store, term):
        if exclude and par == exclude:
            continue
        f = _family_of_label(par)
        if f:
            votes[f] += 1
    if not votes:
        return None, 0
    top, n = votes.most_common(1)[0]
    # a clear majority family; return its strength (vote count) so the Surgeon
    # only CUTS on a well-established subject type, never a single weak signal.
    if len(votes) == 1 or n > sum(votes.values()) / 2:
        return top, n
    return None, 0


def inspect(store: Any, subject: str, obj: str) -> Verdict:
    """Is 'subject is_a obj' type-consistent? contaminated ONLY when the
    subject's family is well-established (>=2 signals) AND its family is
    HARD-DISJOINT from the object's — precision over recall (surgeon's rule)."""
    subj_fam, strength = _entity_family(store, subject, exclude=obj)
    obj_fam = _family_of_label(obj) or _entity_family(store, obj)[0]
    if subj_fam and obj_fam and subj_fam != obj_fam:
        if strength >= 2 and frozenset((subj_fam, obj_fam)) in _HARD_DISJOINT:
            return Verdict(subject, obj, "contaminated",
                           f"type disjoint: '{subject}' is established as {subj_fam} "
                           f"({strength} signals), but '{obj}' is {obj_fam} — physically "
                           f"incompatible, a sense-collision error", subj_fam, obj_fam)
        return Verdict(subject, obj, "suspect",
                       f"family mismatch {subj_fam}/{obj_fam} but not hard-disjoint or "
                       f"subject weakly typed ({strength}) — needs evidence, not excised",
                       subj_fam, obj_fam)
    if subj_fam and obj_fam and subj_fam == obj_fam:
        return Verdict(subject, obj, "clean",
                       f"type-consistent ({subj_fam})", subj_fam, obj_fam)
    return Verdict(subject, obj, "suspect",
                   "type family unknown for one endpoint — cannot confirm; needs evidence",
                   subj_fam, obj_fam)


def scan(store: Any, edges: list[tuple[str, str]], *, cap: int = 5000
         ) -> dict[str, Any]:
    """Real-time review of a batch of candidate is_a edges. Returns the
    contaminated ones with reasons — the surgeon's incision list. Non-
    destructive: the caller quarantines via the reversible ledger."""
    contaminated: list[dict[str, Any]] = []
    clean = suspect = 0
    for s, o in edges[:cap]:
        v = inspect(store, s, o)
        if v.status == "contaminated":
            contaminated.append(v.to_dict())
        elif v.status == "clean":
            clean += 1
        else:
            suspect += 1
    n = min(len(edges), cap)
    return {"reviewed": n, "clean": clean, "suspect": suspect,
            "contaminated": len(contaminated),
            "contamination_rate": round(len(contaminated) / n, 4) if n else 0.0,
            "incisions": contaminated[:50]}
