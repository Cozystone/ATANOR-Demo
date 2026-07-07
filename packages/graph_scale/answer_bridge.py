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
    # a definitional question is answerable by EITHER predicate: 'fruit이란?' is served
    # equally by defined_as(fruit, …) or is_a(fruit, seed-bearing structure…) — excluding
    # is_a made stored facts invisible to the very question form that asked for them
    # (measured on the sealed holdout: fruit ingested yet abstaining).
    "defined_as": ("뭐", "무엇", "뜻", "정의", "란 뭐", "이란", "설명", "define", "meaning", "what is"),
    "is_a": ("뭐", "무엇", "종류", "일종", "무슨", "뜻", "정의", "이란", "설명",
             "kind of", "type of", "define", "meaning", "what is"),
    "used_for": ("용도", "어디에 쓰", "무엇에 쓰", "뭐에 쓰", "어디에 사용", "used for"),
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
    # OOV terms leave Kiwi unsplit (비저란 stays one token) — add particle-stripped
    # variants of every candidate so the store lookup sees the bare term too.
    try:
        from packages.base_brain.neighborhood import _strip_ko_tail as _skt

        for c in list(cands):
            st = _skt(c)
            if st != c and len(st) >= 2 and st not in cands:
                cands.append(st)
    except Exception:
        pass
    for c in list(cands):  # 이란/란 definitional endings Kiwi keeps glued to OOV nouns
        for tail in ("이란", "이라는", "라는", "란"):
            if c.endswith(tail) and len(c) - len(tail) >= 2:
                st = c[: -len(tail)]
                if st not in cands:
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
    "used_for": "{s_topic} {o}에 쓰입니다.",
}


def _ko_topic(label: str) -> str:
    """Attach the correct 은/는 topic particle (delegates to the LAD morphology layer)."""
    from packages.lad_morphology import topic

    return topic(label)


def _wanted_predicates(query: str) -> set[str]:
    q = query.lower()
    want = {pred for pred, cues in _RELATION_CUES.items() if any(c in q for c in cues)}
    # the bare definitional ENDING ('에스프레소란?', 'X라는 건?') is a cue the
    # substring list can't express — without it the precision gate would block
    # legitimate definition questions along with the chatter it exists to block
    if re.search(r"[가-힣a-z0-9)\"'](?:이?란|이라는 ?건?)\s*\??\s*$", q):
        want |= {"defined_as", "is_a"}
    return want


# A static store must NEVER answer a question about the current moment — the word
# 지금 having a dictionary definition does not make "지금 몇 시야?" answerable from
# curated triples. Intent-level guard, not a knowledge table.
_REALTIME_MARKERS = ("지금", "현재", "오늘", "내일", "실시간", "최신", "요즘", "몇 시", "몇시",
                     "날씨", "주가", "시세", "가격", "얼마", "now", "today", "current", "latest")

# open-composition shapes (개방형 B1/B2) — regex-gated like the chain shapes:
# the question form itself is the cue, so these never fire on conversation.
_COMPARE_RE = re.compile(r"^(.+?)[와과]\s*(.+?)[은는의]?\s*(?:차이|다른 ?점|비교)")
_PURPOSE_RE = re.compile(r"^(.+?)(?:[은는이가의]|[으로로])?\s*(?:용도|어디에 쓰|무엇에 쓰|뭐에 쓰|어디에 사용|뭘 할 수 있)")


def _ko_grounded(subject: str, facts: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
    """Same language-appropriate grounding rule as the single-fact path: a Korean
    subject is never 'defined' by a bare foreign gloss (커피는 coffee입니다 reads
    as a wrong answer). Entity-valued relations stay."""
    if not re.search(r"[가-힣]", subject):
        return facts
    return [(s, p, o) for (s, p, o) in facts
            if re.search(r"[가-힣]", o) or p not in ("defined_as", "is_a")]


def _try_open_composition(query: str, store: Any) -> dict[str, Any] | None:
    """B1 contrast ('A와 B의 차이는?') and B2 purpose ('X는 어디에 써?') — multi-fact
    grounded composition. Every clause is a stored (or taxonomy-inherited, and then
    SAID to be inherited) fact; the composer's vocabulary is closed."""
    from packages.graph_scale.chain_reasoner import _strip_josa, common_ancestor, inherited_facts
    from packages.grounded_composer.composer import compose_comparison, compose_purpose

    q = query.strip()
    m = _COMPARE_RE.match(q)
    if m:
        a, b = _strip_josa(m.group(1)), _strip_josa(m.group(2))
        if a and b and a != b:
            fa = _ko_grounded(a, store.facts_about(a, limit=12))
            fb = _ko_grounded(b, store.facts_about(b, limit=12))
            if fa and fb:
                common = common_ancestor(a, b, store.facts_about)
                comp = compose_comparison(a, b, fa, fb, common)
                if comp is not None:
                    cert = comp.certificate()
                    cert["schema"] = "contrast"
                    return {"answer": comp.answer, "reasoning_certificate": cert,
                            "confidence": 0.85, "answer_kind": "grounded_composition"}
        return None
    m = _PURPOSE_RE.match(q)
    if m:
        lead = _strip_josa(m.group(1))
        for cand in dict.fromkeys([lead] + _subject_candidates(query)):
            if not cand:
                continue
            facts = _ko_grounded(cand, store.facts_about(cand, limit=16))
            if not facts:
                continue
            inh = inherited_facts(cand, store.facts_about)
            comp = compose_purpose(cand, facts, inh)
            if comp is not None:
                cert = comp.certificate()
                cert["schema"] = "purpose"
                return {"answer": comp.answer, "reasoning_certificate": cert,
                        "confidence": 0.85, "answer_kind": "grounded_composition"}
    return None


def _strip_generic_source(text: str) -> str:
    """Remove the placeholder '(출처: 큐레이션 지식그래프)' tail — real link
    citations replace it."""
    return re.sub(r"\s*\((?:출처|source)[^)]*\)\s*$", "", text).rstrip()


def _cite_sources(store: Any, subject: str, facts_used: list[tuple[str, str, str]],
                  language: str) -> dict[str, Any]:
    """Resolve the real provenance of the facts the answer used. Returns a citation
    suffix (with URLs when the source is a live link) and a structured source list
    for the certificate. Legacy-tier facts cite the curated corpus by name."""
    try:
        rows = store.facts_with_sources(subject, limit=20)
    except Exception:
        rows = []
    used = {(p, o) for _s, p, o in facts_used}
    seen: dict[str, str] = {}
    for (_s, p, o, name, url) in rows:
        if (p, o) in used and name not in seen:
            seen[name] = url
    friendly = "큐레이션 지식그래프" if language == "ko" else "curated knowledge graph"
    if not seen:
        tail = f" (출처: {friendly})" if language == "ko" else f" (source: {friendly})"
        return {"suffix": tail, "sources": []}
    sources = [{"name": n, "url": u} for n, u in seen.items()]
    label = "출처" if language == "ko" else "sources"
    # registry names like 'curated:legacy' are audit ids, not user-facing labels
    parts = [f"{(friendly if n.startswith('curated:') else n)}({u})" if u
             else (friendly if n.startswith("curated:") else n) for n, u in seen.items()]
    return {"suffix": f" ({label}: " + " · ".join(dict.fromkeys(parts)) + ")", "sources": sources}


def _evidence_section(store: Any, subj: str, limit: int = 3) -> tuple[str, list[dict[str, str]]]:
    """Attributed web evidence for a subject: verbatim sentences + their page links.
    The attribution IS the honesty contract — we say who said it and where. Display
    caps at 2 sentences per domain so one outlet never monopolizes the warrant,
    even when the store holds older single-domain rows."""
    try:
        rows = store.facts_with_sources(subj, limit=limit * 4, preds=("evidence",))
    except Exception:
        rows = []
    lines: list[str] = []
    sources: list[dict[str, str]] = []
    per_dom: dict[str, int] = {}
    for (_s, _p, sent, name, url) in rows:
        if len(lines) >= limit:
            break
        if per_dom.get(name, 0) >= 2:
            continue
        per_dom[name] = per_dom.get(name, 0) + 1
        lines.append(f"· {sent} — {name}({url})")
        sources.append({"name": name, "url": url, "quote": sent})
    return ("\n".join(lines), sources)


def answer_from_triples(query: str, language: str = "ko") -> dict[str, Any] | None:
    """Look up a stored fact that answers the query. Returns {answer, reasoning_certificate,
    confidence} or None when the store can't answer it (empty store, no subject match, or
    the relation intent isn't present)."""
    ql = query.lower()
    if any(m in ql for m in _REALTIME_MARKERS):
        return None  # real-time intent — the honest realtime abstain must stand
    # imperative shape = a COMMAND, not a definition question. Without this,
    # 'open atanor app' got a dictionary answer for the word 'open' (measured).
    if re.match(r"^\s*(open|launch|start|run|execute|close|kill)", ql):
        return None
    store = _store()
    if store is None or len(store) == 0:
        return None
    # P3 multi-hop chain reasoning, generalized: 결국/인가/속하나/수 있어/관계 questions
    # walk stored edges under the composition algebra (termination + no-cycle guaranteed)
    # and verbalize the actual chain. Runs BEFORE the want-gate because each chain shape
    # is regex-gated inside answer_relationship — the shape IS the relation cue, so this
    # cannot reintroduce the paste-on-chatter regression the gate exists to block.
    if language == "ko":
        try:
            from .chain_reasoner import answer_relationship, has_chain_intent

            if has_chain_intent(query):
                chained = answer_relationship(query, store.facts_about, _subject_candidates(query))
                if chained is not None:
                    return chained
        except Exception:
            pass
        # 개방형 composition (contrast/purpose) — its own regex gates, same precision rule
        try:
            composed = _try_open_composition(query, store)
            if composed is not None:
                return composed
        except Exception:
            pass
    want = _wanted_predicates(query)
    # ROLLBACK (owner-measured regression): with no explicit relation cue the
    # bridge pasted ANY stored fact about any noun in the sentence — every chat
    # message got a wikipedia-flavored definition. The bridge is a PRECISION
    # tool: it speaks only when the question explicitly asks for a definition
    # or a relation (이란/뭐/수도/저자/…), never on conversation.
    if not want:
        return None
    for subj in _subject_candidates(query):
        facts = store.facts_about(subj, limit=12)
        if language == "ko" and re.search(r"[가-힣]", subj):
            # language-appropriate grounding: a Korean word must not be "defined"
            # by a bare foreign gloss ("원래는 originally입니다" reads as a wrong
            # answer, and the honesty battery rightly flags it). Keep definitional
            # facts only when the object speaks Korean; relation facts (capital,
            # located_in, ...) are entity-valued and stay. Nothing left => the
            # honest move is abstention, and the gap feeds the ingest queue.
            facts = [(s, p, o) for (s, p, o) in facts
                     if re.search(r"[가-힣]", o) or p not in ("defined_as", "is_a")]
        if not facts:
            continue
        # prefer a fact whose predicate matches the query's relation intent
        chosen = [(s, p, o) for (s, p, o) in facts
                  if (not want or p in want) and p not in ("alias", "sense")]
        hop_from = None
        if not chosen:
            # multi-SENSE term (disambiguation asserted may-refer-to): enumerate the
            # senses dictionary-style — honest, and immune to wrong-referent answers.
            senses = list(dict.fromkeys(o for (_s, p, o) in facts if p == "sense"))
            if len(senses) >= 2 and language == "ko":
                parts = []
                for sn in senses[:3]:
                    sdef = [(s2, p2, o2) for (s2, p2, o2) in store.facts_about(sn, limit=6)
                            if p2 in ("defined_as", "is_a")]
                    if sdef:
                        parts.append(f"{sn}({sdef[0][2][:46]})")
                if len(parts) >= 2:
                    answer = f"{subj}{_ko_topic(subj)[len(subj):]} 여러 의미로 쓰입니다 — " + ", ".join(parts) + ". (출처: 큐레이션 지식그래프)"
                    return {
                        "answer": answer,
                        "reasoning_certificate": {
                            "derivation_kind": "multi_sense_enumeration",
                            "anchor_concept": {"label": subj},
                            "steps": [{"type": "sense", "fact": f"{subj} sense {sn}"} for sn in senses[:3]],
                            "evidence_concepts": [subj] + senses[:3], "confidence": 0.85,
                            "confidence_basis": "curated_structured_triple_verbatim",
                            "guarantees": {"external_llm": False, "fabricated_facts": False, "inferred": False},
                        },
                        "confidence": 0.85,
                        "answer_kind": "multi_sense_enumeration",
                    }
            # ONE visible alias hop — ONLY the redirect signature (exactly one DISTINCT
            # target): a redirect asserts equivalence; anything weaker must not
            # substitute. Distinct matters — the same equivalence asserted by two
            # sources (seed + ConceptNet Synonym) is STRONGER evidence, yet the raw
            # row list read it as ambiguity and refused the hop (기획 stayed abstained
            # with a perfectly grounded 계획 definition one hop away).
            alias_targets = list(dict.fromkeys(o for (_s, p, o) in facts if p == "alias"))
            if len(alias_targets) == 1:
                tfacts = store.facts_about(alias_targets[0], limit=12)
                tchosen = [(s2, p2, o2) for (s2, p2, o2) in tfacts
                           if (not want or p2 in want) and p2 not in ("alias", "sense")]
                if tchosen:
                    chosen = tchosen
                    hop_from = subj
        if not chosen:
            ev_text, ev_sources = _evidence_section(store, subj, limit=4)
            if ev_text and (want & {"defined_as", "is_a"}):
                head = (f"{subj}에 대해 웹에서 교차 확인된 근거입니다:" if language == "ko"
                        else f"Web-attributed evidence about {subj}:")
                return {
                    "answer": head + "\n" + ev_text,
                    "reasoning_certificate": {
                        "derivation_kind": "attributed_web_evidence",
                        "anchor_concept": {"label": subj},
                        "steps": [{"type": "quote", "fact": e["quote"][:80]} for e in ev_sources],
                        "evidence_concepts": [subj],
                        "sources": ev_sources,
                        "confidence": 0.8,
                        "confidence_basis": "verbatim_quotes_with_page_links",
                        "guarantees": {"external_llm": False, "fabricated_facts": False,
                                       "inferred": False, "attributed": True},
                    },
                    "confidence": 0.8,
                    "answer_kind": "attributed_web_evidence",
                }
            continue
        s, p, o = chosen[0]
        display_s = f"{hop_from}(={s})" if hop_from else s
        # P2 grounded composition: several stored facts -> one fluent paragraph
        # (definitional/general intents; vocabulary closed over templates+facts,
        # so composition cannot invent content). Hops and targeted relation
        # questions keep their precise single-fact paths.
        if hop_from is None and language in ("ko", "en") and (not want or (want & {"defined_as", "is_a"})):
            try:
                from packages.grounded_composer import compose_from_facts

                composed = compose_from_facts(s, facts, language=language)
            except Exception:
                composed = None
            if composed is not None:
                # 링크 근거 (owner directive): cite the ACTUAL sources of the facts
                # used, not a generic '지식그래프'. Real URLs where they exist.
                cited = _cite_sources(store, s, composed.facts_used, language)
                answer = _strip_generic_source(composed.answer) + cited["suffix"]
                cert = composed.certificate()
                cert["sources"] = cited["sources"]
                # adaptive depth: open definitional questions get the attributed
                # web-evidence section when the learner has gathered one
                ev_text, ev_sources = _evidence_section(store, s)
                if ev_text:
                    answer = answer + "\n\n관련 근거:\n" + ev_text
                    cert["evidence_sources"] = ev_sources
                return {
                    "answer": answer,
                    "reasoning_certificate": cert,
                    "confidence": 0.88,
                    "answer_kind": "grounded_composition",
                }
        if language == "ko":
            template = _KO_TEMPLATE.get(p)
            # particle follows the REAL subject's final syllable even when the display
            # label carries the alias hop ('기획(=계획)' still gets 계획's 은/는).
            particle = _ko_topic(s)[len(s):]
            if template:
                body = template.format(s=display_s, o=o, s_topic=display_s + particle)
            else:  # unknown predicate: generic frame with correct topic particle
                pred_ko = next((cues[0] for name, cues in _RELATION_CUES.items() if name == p), p)
                body = f"{display_s}의 {_ko_topic(pred_ko)} {o}입니다."
            # 링크 근거 even on the single-fact path — cite where this fact came from
            cited = _cite_sources(store, s, [(s, p, o)], language)
            answer = f"{body}{cited['suffix']}"
        else:
            # reuse the composer's clean single-fact English frames — the generic
            # 'The {p} of {s} is {o}' turned is_a into 'The is a of concerto is …'
            from packages.grounded_composer.composer import _EN_LEAD

            frame = _EN_LEAD.get(p)
            body = frame.format(s=display_s, o=o) if frame else f"{display_s}: {o}"
            cited = _cite_sources(store, s, [(s, p, o)], "en")
            answer = f"{body}{cited['suffix']}"
        # adaptive depth on the single-fact path too: a curated one-liner grows into
        # a rich profile when the learner holds attributed evidence for the subject
        ev_sources = []
        if hop_from is None and (not want or (want & {"defined_as", "is_a"})):
            ev_text, ev_sources = _evidence_section(store, s)
            if ev_text:
                label = "관련 근거" if language == "ko" else "Related evidence"
                answer = f"{answer}\n\n{label}:\n{ev_text}"
        return {
            "answer": answer,
            "reasoning_certificate": {
                "derivation_kind": "structured_triple_lookup",
                "anchor_concept": {"label": s},
                "steps": ([{"type": "alias", "fact": f"{hop_from} alias {s}"}] if hop_from else [])
                         + [{"type": "triple", "fact": f"{s} {p} {o}"}],
                "evidence_concepts": [s, o], "confidence": 0.9,
                "confidence_basis": "curated_structured_triple_verbatim",
                "sources": cited["sources"],
                **({"evidence_sources": ev_sources} if ev_sources else {}),
                "guarantees": {"external_llm": False, "fabricated_facts": False, "inferred": False},
            },
            "confidence": 0.9,
            "answer_kind": "structured_triple_lookup",
        }
    return None
