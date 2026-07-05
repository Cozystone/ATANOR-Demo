#!/usr/bin/env python3
"""Promotion: Cloud Brain candidate graph -> base_brain answer pack.

This is the missing link. The continuous learner writes into the cloud candidate store
(clean_seed_v2, ~7500 concepts), but answer_with_base_brain() reads a SEPARATE curated
pack (58 concepts) — so learning never reaches general answers. This batch promotion
builds an enriched pack = curated concepts (kept, high quality) + cloud-graph concepts,
each with a FAITHFUL short_description = a verbatim source sentence (linked by source_hash,
No-LLM, never paraphrased) and its IS_A/typed relations.

Re-runnable (periodic refresh). Backs nothing up itself (caller backed up the pack);
writes PACK_PATH with base_pack_code_version aligned to the loader so it is authoritative
(not rebuilt to curated-only on next load).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.base_brain.benchmark import build_zero_user_benchmark_v0          # noqa: E402
from packages.base_brain.models import PACK_PATH                                # noqa: E402
from packages.base_brain.pack_loader import BASE_PACK_CODE_VERSION              # noqa: E402
from packages.base_brain.seed_extension import build_seed_graph_v2             # noqa: E402
from packages.base_brain.semantic_pack import build_general_semantic_pack_v0   # noqa: E402
from packages.base_brain.surface_pack import build_general_surface_pack_v0     # noqa: E402
from packages.base_brain.pack_builder import _lemma_links                       # noqa: E402
from packages.base_brain.models import utc_now_iso                             # noqa: E402

STORE = REPO_ROOT / "data" / "cloud_brain" / "candidate_runs" / "clean_seed_v2"
MOJIBAKE = ("荑", "吏", "媛", "占")  # _needs_rebuild trips on these; skip such descriptions

# Non-destructive overlay: additional stores whose rows are read ALONGSIDE the
# primary STORE, so their concepts flow through the SAME quality gate (aboutness,
# IS_A, name-strip, thresholds) below. Nothing promotes unless it passes. Set via
# --extra-store (repeatable); a sharded root (contributed_store_sharded) expands to
# its shard_*/ dirs. This is the Brain Link closed loop: peer compute -> gate -> pack.
EXTRA_STORES: list[Path] = []


def _store_dirs(root: Path) -> list[Path]:
    """Concrete store dirs under a path: the path itself if it holds jsonl rows,
    plus any shard_*/ subdirs (a ShardedContributedStore root)."""
    dirs: list[Path] = []
    if (root / "concepts.jsonl").exists() or (root / "evidence.jsonl").exists():
        dirs.append(root)
    dirs.extend(sorted(root.glob("shard_*")))
    return dirs


def _read(fn: str) -> list[dict]:
    out = []
    stores = [STORE] + [d for x in EXTRA_STORES for d in _store_dirs(x)]
    for store in stores:
        p = store / fn
        if not p.exists():
            continue
        for line in p.open(encoding="utf-8"):
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def _clean_desc(text: str) -> str | None:
    t = re.sub(r"\s+", " ", str(text or "")).strip()
    if not (20 <= len(t) <= 220):
        return None
    if any(m in t for m in MOJIBAKE):
        return None
    return t


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()


# Single-token leading subject (no internal spaces): "광합성은 …", "Algeria is …".
# Language-agnostic — the token before the first Korean subject particle, or an
# English/Latin leading word, is the bare subject.
_LEAD_SUBJ = re.compile(r"^\s*([^\s()]{2,20}?)(?:은|는|이|가)\s")

# Korean MODIFIED leading subject: a multi-token noun phrase (has at least one
# internal space) ending in a subject particle — "머신러닝 알고리즘은 …". Only the
# HEAD noun (last token) is the concept; the preceding tokens are modifiers.
_LEAD_SUBJ_KO_MULTI = re.compile(r"^\s*([^()]{2,40}?)(?:은|는|이|가)\s")

# A KOREAN sentence is DEFINITIONAL only if it ends with a categorial copula
# ("…이다", "…입니다") or a defining verb ("…말한다/뜻한다/가리킨다/일컫는다",
# "…라고 한다"). This rejects the leading-subject-but-not-a-definition class that
# a subject heuristic otherwise imports as descriptions: casual ("…가고 싶지
# 않아요"), negation ("…어렵지 않습니다!"), news events ("…발간했다."), questions
# ("…건가요?"), and off-topic similes ("…JPEG-LS하고 비슷하다."). Leading-subject
# ≠ definition, and precision (never answer a "…란?" with a travel blurb) is the
# identity here. English/Latin sentences are exempt — the startswith path already
# only maps sentences that LEAD with the concept, which in this corpus are
# overwhelmingly "X is a/was a …" definitions.
_KO_DEF_ENDING = re.compile(
    r"(?:이다|입니다|이었다|이었습니다|였다|였습니다"
    r"|말한다|말합니다|뜻한다|뜻합니다|가리킨다|가리킵니다|일컫는다|일컫습니다"
    r"|이라고\s*한다|라고\s*한다|이라\s*한다"
    r"|불린다|불립니다|불리운다|불리는\s*말이다"          # "is called X"
    r"|알려져\s*있다|알려져\s*있습니다)[.\"'”’)\]]*$"       # "is known as X"
)
_HANGUL = re.compile(r"[가-힣]")

# Parenthetical / bracket noise: Korean encyclopedic first sentences wrap the
# subject with etymology / romanization / dates ("수소(水素, 영어: hydrogen)는 …",
# "이순신(李舜臣, 1545년~1598년)은 …"). That parenthetical sits BETWEEN the subject
# and its particle, so leading-subject extraction never sees "수소는"/"이순신은" and
# the real definition is lost. Strip "(…)" and "[…]" before extraction (mirrors
# coverage_seed._first_sentence) — it also makes the stored description cleaner.
_PARENS = re.compile(r"\([^()]*\)")
_BRACKETS = re.compile(r"\[[^\[\]]*\]")
# Korean wiki disambiguation / redirect header that leaks in front of the real
# sentence: "일론 머스크: 일론 리브 머스크는 …", "세종대왕급 구축함: 세종 대왕 급
# 구축함은 …". A short "제목: " prefix followed by a clause whose own subject
# particle appears soon after — strip the redundant title so the leading subject
# is the sentence's real subject. The following-particle lookahead means a
# legitimate "X: Y이다" colon definition (no early particle) is left intact.
_DISAMBIG_HEADER = re.compile(r"^[가-힣A-Za-z0-9·\s]{2,20}:\s+(?=.{1,25}?(?:은|는|이|가)\s)")


def _strip_parens(text: str) -> str:
    t = str(text or "")
    for _ in range(3):  # a few passes to unwrap simple nesting
        new = _BRACKETS.sub("", _PARENS.sub("", t))
        if new == t:
            break
        t = new
    t = re.sub(r"\s+", " ", t).strip()
    return _DISAMBIG_HEADER.sub("", t).strip()


def _is_definitional(txt: str) -> bool:
    t = str(txt or "").strip()
    if not _HANGUL.search(t):
        return True  # non-Korean: exempt (handled by startswith precision)
    return bool(_KO_DEF_ENDING.search(t))


def strip_leading_subject(name: str, desc: str) -> str:
    """Remove the description's leading subject so the answer engine's own
    "{name}은/는 …" prefix does not double it.

    Two cases:
      1. desc starts with the bare concept name — "종족은 종족은 테란이며" →
         "종족은 테란이며".
      2. desc starts with a MODIFIED subject whose HEAD is the concept —
         "파이썬 미사일은 …계열이다" (name 미사일) → "…계열이다";
         "일론 리브 머스크는 …기업인이다" (name 머스크) → "…기업인이다".
         Only when the modified subject is SHORT (a real leading NP, ≤25 chars)
         and enough predicate remains, so a mid-sentence mention is never cut.
    """
    n = re.escape(name)
    out = desc
    # Loop: strip a LEADING "{name}[ particle]" repeatedly. Ingestion sometimes
    # DUPLICATES the subject ("기록 기록 은 …" from "기록(記錄)은 …"), so one pass
    # leaves an orphaned "기록 은"; keep going while the name still leads. Bounded.
    # Longer particles FIRST in the alternation: "이란" must beat "이" (else "화석이란"
    # strips only "화석이" and leaves an orphan "란"). Same for "으로"/"으" etc.
    _PARTS = r"(?:이란|이라|으로|은|는|란|이|가|도|을|를|와|과|의)"
    for _ in range(4):
        m = re.match(n + r"\s*" + _PARTS + r"?\s*", out, re.IGNORECASE)
        if m and m.end() > 0 and (len(out) - m.end()) >= 12:
            out = out[m.end():].strip()
        else:
            break
    # An orphaned leading particle can remain when the name was doubled with a space
    # ("기록 은 …" after the name was consumed) — strip a lone leading particle.
    out = re.sub(r"^(?:이란|이라|란|은|는|이|가|을|를)\s+", "", out).strip()
    # And a leading comma/colon the English appositive leaves ("Australia, officially
    # …" -> ", officially …" -> "officially …"), so the engine's "{name} " prefix reads
    # cleanly ("Australia officially …") instead of "Australia , officially …".
    out = re.sub(r"^[,:;·]\s*", "", out).strip()
    # Only accept the stripped form if enough predicate remains; else keep original.
    if len(out) >= 12 and out != desc:
        return out
    # Fallback: name appears a little into the string ("대규모 언어 모델 은 …").
    m2 = re.match(r".{0,25}?" + n + r"\s*(?:은|는|이|가)\s+", desc, re.IGNORECASE)
    if m2 and (len(desc) - m2.end()) >= 12:
        return desc[m2.end():].strip()
    return desc


def build_lead_def_by_name(
    text_by_hash: dict[str, str], topics_by_hash: dict[str, set]
) -> dict[str, str]:
    """name -> a definitional sentence where the name is the LEADING subject.

    Decoupled from each concept's recorded source_hashes, which can be
    INCOMPLETE: a concept first created from a worse sentence may never record
    its clean definition's hash. (The coverage killer: 광합성's good "광합성은
    …과정이다" existed in evidence but wasn't in the concept's hashes, so it
    never promoted.) Search ALL evidence with the same quality gate.

    Three ADDITIVE topic sources (a concept promotes if ANY holds):
      (a) case_frame TOPIC/SUBJ head AND the sentence starts with it as a real
          subject. Language-agnostic (English "Algeria is a country…" -> algeria;
          Korean "세포는 …단위이다" -> 세포). A boundary check rejects a Korean
          genitive/prefix match ("엔비디아의 …", "미국인은 …").
      (b) the sentence's own single-token leading subject (regex), for subjects
          not recorded in any case_frame (pure-copula defs yield no frame).
      (c) NEW: the HEAD noun of a Korean MODIFIED leading subject —
          "머신러닝 알고리즘은 …" -> 알고리즘, "컴퓨터 바이러스는 …" -> 바이러스.
          The old rule required the sentence to start with the *bare* concept
          name, so any modifier in front ("머신러닝 알고리즘") silently discarded
          the definition — the systematic killer of common-noun coverage. The
          modifier tokens themselves are never treated as the subject.

    (c) is deliberately Korean-particle-gated and does NOT loosen (a)/(b): it
    only ADDS the head noun of an already-particle-terminated leading NP, so it
    cannot drop the English/clean-Korean matches (a)/(b) already produce.
    """
    out: dict[str, str] = {}

    def _offer(key: str, txt: str) -> None:
        if not key or not _is_definitional(txt):
            return
        cur = out.get(key)
        if cur is None or len(txt) < len(cur):
            out[key] = txt

    def _subject_boundary_ok(tn: str, topic: str) -> bool:
        # The sentence starts with `topic`; is `topic` the SUBJECT? Look at the
        # very next char. If it is a Korean subject/topic particle (은/는/이/가),
        # yes. If it is another Hangul syllable, `topic` is only a PREFIX — either
        # a genitive modifier ("엔비디아의 …"/"미국의 …") or a longer word
        # ("미국인은 …"), so NO. Non-Hangul (space, comma, Latin, punctuation)
        # means an English/clean boundary -> yes ("Algeria, officially …").
        rest = tn[len(topic):]
        if not rest:
            return True
        c = rest[0]
        if c in "은는이가":
            return True
        return not ("가" <= c <= "힣")

    for h, raw in text_by_hash.items():
        # Strip parentheticals so "수소(水素, 영어: hydrogen)는 …" becomes "수소는 …"
        # and the leading subject is visible. The stripped form is also what we
        # store as the (cleaner) description.
        txt = _strip_parens(raw)
        if not (12 <= len(txt) <= 220):
            continue
        tn = _norm(txt)
        # (a) case_frame topic that the sentence leads with, as a real subject.
        for topic in topics_by_hash.get(h, set()):
            if topic and tn.startswith(topic) and _subject_boundary_ok(tn, topic):
                _offer(topic, txt)
        # (b) single-token leading subject.
        m = _LEAD_SUBJ.match(txt)
        if m:
            _offer(_norm(m.group(1)), txt)
        # (c) Korean modified (multi-token) leading subject -> the FULL noun phrase is
        # the concept, NEVER the bare head. Attaching a specific entity's definition to
        # its generic head fabricates a wrong general definition — the systematic noise
        # class: "우간다 공화국은 …" must NOT define 공화국, "메탈 블레이드 레코드는 …"
        # must NOT define 레코드, "모두 플랫폼은 …" must NOT define 플랫폼. Keying by the
        # whole NP means the description only promotes a concept that IS that full NP
        # (precise + honest); a generic head with no clean bare-subject definition of
        # its own simply doesn't promote (paths (a)/(b) still cover true bare-subject
        # definitions like "세포는 …단위이다"). Genitive-modified heads ("엔비디아의
        # CUDA") are also kept as the full NP, not split to the tail.
        mk = _LEAD_SUBJ_KO_MULTI.match(txt)
        if mk:
            lead_np = _norm(mk.group(1))
            toks = lead_np.split(" ")
            if len(toks) >= 2 and len(lead_np) >= 3:  # modified NP; single-token is (b)
                _offer(lead_np, txt)
    return out


def promote(dry_run: bool = False, extra_stores: list[Path] | None = None) -> dict:
    # Optional per-call overlay (the live daemon passes the store it actually grows),
    # so learning reaches answers without a manual --extra-store argv. Overlaid rows
    # pass the SAME quality gate below. Restore on exit so callers stay isolated.
    global EXTRA_STORES
    _saved = EXTRA_STORES
    if extra_stores is not None:
        EXTRA_STORES = list(extra_stores)
    try:
        return _promote_impl(dry_run)
    finally:
        EXTRA_STORES = _saved


def _promote_impl(dry_run: bool = False) -> dict:
    # curated stays authoritative
    curated = build_general_semantic_pack_v0()
    curated_concepts = curated.get("concepts", [])
    taken_ids = {str(c["concept_id"]) for c in curated_concepts}
    taken_names = {str(c.get("canonical_name", "")).lower() for c in curated_concepts}

    # cloud graph
    evidence = _read("evidence.jsonl")
    text_by_hash = {}
    for e in evidence:
        h = e.get("source_hash")
        if h and h not in text_by_hash:
            d = _clean_desc(e.get("text"))
            if d:
                text_by_hash[h] = d

    # ABOUTNESS gate: a sentence may only describe a concept that is its TOPIC
    # (subject). Build source_hash -> set(topic heads) from case_frames, so we never
    # attach a sentence about Nvidia to the concept "델라웨어" just because it is
    # mentioned. Only definitional/subject sentences become descriptions.
    topics_by_hash: dict[str, set] = {}
    for fr in _read("case_frames.jsonl"):
        h = fr.get("source_hash")
        if not h:
            continue
        for role in fr.get("case_roles") or []:
            if str(role.get("role")) in ("TOPIC", "SUBJ", "SUBJECT"):
                topics_by_hash.setdefault(h, set()).add(_norm(role.get("head")))

    concepts = _read("concepts.jsonl")
    id_to_name = {c["concept_id"]: c.get("canonical_name", "") for c in concepts}
    rels_by_src: dict[str, list] = {}
    all_rels: list[dict] = []
    for r in _read("relations.jsonl"):
        rels_by_src.setdefault(r.get("source_concept_id"), []).append(r)
        all_rels.append(r)

    # Data-derived quality signals (NO rule list):
    #  - in_degree: how many facts REFERENCE a concept — a referenced concept is a real
    #    entity; an adverbial/filler subject (원래/오늘/지금) is never referenced (in=0).
    #  - predicate informativeness: selective verbs (결합하다) outrank light verbs (하다).
    from packages.cloud_brain.neuroplasticity import predicate_informativeness
    in_degree: dict[str, int] = {}
    for r in all_rels:
        t = r.get("target_concept_id")
        if t:
            in_degree[t] = in_degree.get(t, 0) + 1
    pred_info = predicate_informativeness(all_rels)

    lead_def_by_name = build_lead_def_by_name(text_by_hash, topics_by_hash)

    # Time-deixis / discourse words are closed-class grammar (LAD layer), not knowledge
    # entities — but casual sentences ("오늘은 …해볼게요") make them look like topics, so
    # they get promoted and then match real queries wrongly ("오늘 날씨" -> the "오늘"
    # concept). Data signals (in_degree) can't separate them (1077/1131 promoted concepts
    # have in_degree 0, incl. real entities like 방탄소년단), so exclude this small deictic
    # set explicitly — the same grammar-vs-knowledge boundary as copula handling.
    _NON_ENTITY_DEIXIS = {
        "오늘", "지금", "내일", "어제", "요즘", "최근", "방금", "오늘날", "현재", "이제",
        "원래", "본래", "당시", "그때", "이때", "여기", "거기", "저기",
    }
    # English mirror of the same grammar-vs-knowledge boundary: English source
    # sentences make sentence-leading discourse connectives / pronouns / conjunctions
    # look like subjects ("However, ..." -> topic "However"), so they promote and then
    # match queries wrongly. These are closed-class grammar (LAD layer), not entities.
    # (Surfaced by the Brain Link peer overlay: 14/18 net-new were words like However,
    # Therefore, They, Thus, Meanwhile, Indeed, I, we, s.) Matched case-insensitively.
    _NON_ENTITY_EN = {
        "however", "therefore", "thus", "hence", "meanwhile", "indeed", "moreover",
        "furthermore", "nevertheless", "nonetheless", "besides", "otherwise", "instead",
        "similarly", "consequently", "accordingly", "additionally", "conversely",
        "then", "also", "finally", "first", "firstly", "second", "secondly", "next",
        "below", "above", "here", "there", "why", "when", "where", "how", "what", "who",
        "i", "we", "you", "they", "he", "she", "it", "them", "us", "me", "him", "her",
        "this", "that", "these", "those", "everything", "everyone", "someone",
        "something", "anyone", "anything", "nobody", "nothing",
        "until", "while", "because", "although", "though", "since", "unless", "whereas",
        "and", "but", "or", "so", "yet", "nor", "if", "as", "the", "a", "an", "of",
    }

    # Korean PREDICATE names — a verb/adjective infinitive the decomposer mistook for
    # a concept ("개발하다", "활동하다", "비슷하다"). These are grammar (LAD layer), not
    # entities a user asks a definition of. The unambiguous verbal/adjectival suffixes
    # below never terminate a NOUN, so this has zero false positives on real nouns
    # (바다/포도/유다 stay). Bare monosyllabic stems (묶다/세다) are left to (a)/(b).
    _KO_PREDICATE_SUFFIX = re.compile(
        r"(하다|되다|시키다|당하다|스럽다|스레하다|롭다|답다|거리다|이다|대다|해지다|해하다)$"
    )

    # English SENTENCE-FRAGMENT names — leading-subject extraction grabbing a whole
    # clause, not an entity ("One of her major roles", "It debuted on July", "Aimed at
    # a general audience"). A real multi-word English name is a PROPER noun phrase; a
    # fragment starts with a pronoun/determiner/participle or runs sentence-long. Proper
    # names ("Princess Cecilie of Prussia", "Red Ladder Theatre Company") are kept.
    _FRAGMENT_HEAD = {
        "it", "its", "one", "both", "some", "many", "most", "this", "that", "these",
        "those", "her", "his", "their", "our", "your", "my", "he", "she", "they", "we",
        "a", "an", "the", "aimed", "named", "based", "set", "located", "according",
        "following", "known", "born", "founded", "established", "originally", "later",
        "after", "before", "during", "when", "while", "there", "here", "such", "each",
        "all", "any", "no", "another", "several", "various",
    }

    # Lowercase base-form verbs / clause markers that betray a sentence fragment even
    # without an -ed/-ing tell ("Police believe that", "Share What is").
    _CLAUSE_TOKENS = {
        "that", "what", "which", "who", "whom", "whose", "believe", "believes",
        "think", "thinks", "say", "says", "become", "becomes", "make", "makes",
        "include", "includes", "consist", "refer", "refers", "is", "are", "was", "were",
        "has", "have", "will", "would", "can", "could", "may", "do", "does",
    }

    def _is_junk_english_name(nm: str) -> bool:
        toks = nm.split()
        if len(toks) < 2:
            return False
        if toks[0].lower() in _FRAGMENT_HEAD:
            return True
        # a real entity name starts with a capital (proper noun); "potato race",
        # "counsel of" lead lowercase -> a common-noun fragment, not a name.
        if toks[0][:1].islower():
            return True
        if len(toks) >= 5:  # a 5+ word "name" is a clause, not an entity
            return True
        # a clause marker or base/finite verb among the tokens signals a sentence.
        for t in toks[1:]:
            tl = t.lower()
            if tl in _CLAUSE_TOKENS:
                return True
            if t[:1].islower() and re.search(r"(ed|ing|es|s)$", tl) and len(t) > 3 and tl not in {
                "series", "species", "games", "news", "physics", "studies", "records",
                "works", "arts", "islands", "states", "sciences", "systems",
            }:
                return True
        return False

    def _is_non_entity(nm: str) -> bool:
        low = nm.lower()
        if low in _NON_ENTITY_EN:
            return True
        # single-char / bare-inflection fragments ("s", "In") are decomposition debris
        if len(nm.strip()) <= 1:
            return True
        # Korean verb/adjective infinitive (single token, no space) — a predicate, not
        # a topic. "물 속의 바다" is fine (has space / is a real noun); "개발하다" is not.
        if " " not in nm and _HANGUL.search(nm) and _KO_PREDICATE_SUFFIX.search(nm):
            return True
        # English sentence-fragment mistaken for a concept name.
        if not _HANGUL.search(nm) and _is_junk_english_name(nm):
            return True
        return False

    # Abstract relational nouns that are almost never a meaningful IS_A PARENT — a
    # promoted "기록 is_a 관리 (이는 관리의 한 종류입니다)" / "음악 is_a 때문" is a mis-
    # extraction, not a taxonomy fact. Dropping these as is_a targets removes the junk
    # "이는 …의 한 종류입니다" tail without touching real taxonomy (오케스트레이션 시스템,
    # 프로그래밍 언어 …). Grammar/ontology-boundary list (like the deixis set), not a
    # knowledge rule.
    _ABSTRACT_NONPARENT = {
        "형태", "대상", "과정", "관리", "때문", "경우", "방법", "종류", "부분", "모습",
        "상태", "때", "것", "정도", "수준", "사건", "목록", "내용", "결과", "이유",
        "특징", "성질", "부분", "측면", "요소", "존재", "의미", "가치", "영향", "역할",
        "거주지", "영화", "오메가",
    }

    promoted = []
    for c in concepts:
        name = str(c.get("canonical_name") or "").strip()
        if not name or name.lower() in taken_names:
            continue
        if name in _NON_ENTITY_DEIXIS or _is_non_entity(name):
            continue
        # faithful AND about-this-concept: the sentence's TOPIC must be this concept
        # AND the sentence must LEAD with the concept name (it is the primary
        # subject, not a mid-sentence topic). This filters run-ons ("프레디 머큐리는
        # 〈곡〉는 ...") and mentions where the real subject is something else.
        desc = lead_def_by_name.get(_norm(name))
        if not desc:
            continue  # no definitional sentence leads with this concept -> do not promote
        # desc leads with the concept (bare or as the head of a modified NP);
        # strip that leading subject + particle so the answer engine's own
        # "{name}는" prefix does not double it ("종족은 종족은 테란이며" ->
        # "종족은 테란이며"; "파이썬 미사일은 …계열이다" -> "…계열이다").
        # Disambiguation-page stubs are not definitions ("포지션은 다음을 가리킨다",
        # "X may refer to:") — a list pointer, never an answer. Reject before strip.
        if re.search(r"다음을?\s*(가리킨다|가리킵니다|나타낸다|의미할)|다음\s*중\s*하나|"
                     r"동음이의|may\s+refer\s+to|can\s+refer\s+to|refers?\s+to\s*:", desc, re.IGNORECASE):
            continue
        desc = strip_leading_subject(name, desc)
        # A description that stripped down to almost nothing (or was always tiny) is not
        # a usable definition — abstain rather than answer with a fragment.
        if len(desc.strip()) < 15:
            continue
        # A URL in the description means a raw scrape leaked ("… available on the APDB
        # data base and on http://…") — not a clean definition.
        if re.search(r"https?://|www\.", desc):
            continue
        # A thin English predicate ("are gender-specific.", "was here.") — too few words
        # to be a definition. (Korean is gated by the copula-ending check upstream.)
        if not _HANGUL.search(desc) and len(desc.split()) < 4:
            continue
        # If the subject STILL leads after stripping, the strip bailed (remainder was too
        # short) and the answer would double the subject ("counsel은 상담을", "Maoz Israel
        # is in USA") — and such stubs aren't real definitions anyway. Reject.
        if _norm(desc).startswith(_norm(name) + " ") or _norm(desc).startswith(_norm(name) + "은") \
           or _norm(desc).startswith(_norm(name) + "는") or _norm(desc).startswith(_norm(name) + "이"):
            continue
        cid = str(c["concept_id"])
        if cid in taken_ids:
            continue
        # Quality gate: keep IS_A always; surface predicate (association) relations ONLY
        # for referenced entities (in_degree>=1), then only the most informative ones
        # with a substantive target. Parse-error/adverbial subjects (in_degree 0) fall
        # back to definition + IS_A only, instead of emitting noise
        # ("원래는 디자이너를 취직합니다").
        raw = rels_by_src.get(cid, [])
        chosen: list[dict] = []
        # Only REFERENCED entities (in_degree>=1) get relations at all; adverbial/filler
        # parse-error subjects (원래/오늘, in=0) fall back to description-only, so we never
        # assert a false "X의 한 종류" or a junk association for them.
        if in_degree.get(cid, 0) >= 1:
            chosen = [r for r in raw if str(r.get("relation")) == "IS_A"
                      and str(id_to_name.get(r.get("target_concept_id")) or "").strip() not in _ABSTRACT_NONPARENT][:2]
            cand = [r for r in raw if str(r.get("relation")) != "IS_A"
                    and pred_info.get(str(r.get("relation")), 0.0) >= 0.3
                    and len(str(id_to_name.get(r.get("target_concept_id")) or "").strip()) >= 2]
            cand.sort(key=lambda r: pred_info.get(str(r.get("relation")), 0.0), reverse=True)
            chosen += cand[:3]
        rels = []
        _seen_rel: set[tuple[str, str]] = set()
        for r in chosen:
            tgt = id_to_name.get(r.get("target_concept_id")) or r.get("target_concept_id")
            _key = (str(r.get("relation", "is_a")).lower(), str(tgt))
            if tgt and _key not in _seen_rel and str(tgt).strip().lower() != name.lower():
                _seen_rel.add(_key)
                rels.append({
                    "source": cid, "relation": str(r.get("relation", "is_a")).lower(),
                    "target": str(tgt), "confidence": round(float(c.get("confidence", 0.6)), 3),
                    "source_type": "cloud_graph_promoted",
                })
        promoted.append({
            "concept_id": cid,
            "canonical_name": name,
            "aliases": [],
            "labels": {c.get("language", "ko"): name},
            "short_description": desc,
            "relations": rels,
            "confidence": round(float(c.get("trust", 0.5)), 3),
            "source_type": "cloud_graph_promoted",
        })
        taken_ids.add(cid)
        taken_names.add(name.lower())

    merged = list(curated_concepts) + promoted
    semantic_graph = dict(curated)
    semantic_graph["concepts"] = merged
    semantic_graph["relation_count"] = sum(len(c.get("relations", [])) for c in merged)
    semantic_graph["source_type"] = "curated_plus_cloud_promoted"

    seed_graph = build_seed_graph_v2()
    surface_graph = build_general_surface_pack_v0()
    benchmark = build_zero_user_benchmark_v0()
    payload = {
        "pack_id": "atanor_base_brain_v0",
        "version": "0.1.5",
        "metadata": {
            "created_at": utc_now_iso(),
            "base_pack_code_version": BASE_PACK_CODE_VERSION,  # align => authoritative, no rebuild
            "claims": ["zero-user-data graph-native answers", "curated base + cloud-graph promoted concepts",
                       "no external LLM/sLLM", "faithful descriptions = verbatim sourced sentences"],
            "does_not_claim": ["GPT-level quality", "complete world knowledge", "trained neural decoder"],
            "promotion": {"source_store": STORE.name, "curated": len(curated_concepts),
                          "promoted_from_cloud": len(promoted), "total": len(merged)},
            "semantic_surface_links": _lemma_links(semantic_graph, surface_graph),
            "honesty": {"user_data_used": False, "external_llm_used": False,
                        "external_sllm_used": False, "external_web_used": False},
        },
        "seed_graph": seed_graph,
        "semantic_graph": semantic_graph,
        "surface_graph": surface_graph,
        "benchmark": benchmark,
    }
    if not dry_run:
        # ATOMIC write: the live answer path reads PACK_PATH on every call, and the
        # daemon may re-promote concurrently — a plain write_text could expose a
        # half-written file (JSON parse error). Write to a temp sibling then os.replace.
        _tmp = PACK_PATH.with_suffix(PACK_PATH.suffix + ".tmp")
        _tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        _tmp.replace(PACK_PATH)
        # Build the inverted-index + disk-record store next to the pack so the live
        # answer path serves lookups in O(candidates) with bounded RAM instead of an
        # O(N) scan (get_semantic_context uses it when it matches the loaded pack).
        try:
            from packages.base_brain.pack_loader import SEMANTIC_STORE_DIR
            from packages.base_brain.semantic_store import SemanticConceptStore
            SemanticConceptStore.build(SEMANTIC_STORE_DIR, merged)
        except Exception as exc:  # store is an optimization; never fail promotion on it
            print(f"[PROMOTE] semantic store build skipped: {exc}")
    return {"curated": len(curated_concepts), "promoted": len(promoted), "total": len(merged),
            "pack": str(PACK_PATH), "dry_run": dry_run,
            "promoted_names": [c.get("canonical_name") for c in promoted]}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Promote graph/contributed stores into the base answer pack.")
    ap.add_argument("--extra-store", action="append", default=[],
                    help="Additional store dir or sharded root to overlay (repeatable). "
                         "e.g. data/brain_link/contributed_store_sharded")
    ap.add_argument("--dry-run", action="store_true",
                    help="Measure what WOULD promote; do NOT write the live pack.")
    args = ap.parse_args()
    for x in args.extra_store:
        p = Path(x)
        EXTRA_STORES.append(p if p.is_absolute() else REPO_ROOT / p)
    if EXTRA_STORES:
        print(f"[PROMOTE] overlay stores: {[str(p) for p in EXTRA_STORES]}")
    r = promote(dry_run=args.dry_run)
    tag = "DRY-RUN (no write)" if r["dry_run"] else f"wrote {r['pack']} (authoritative)"
    print(f"[PROMOTE] curated={r['curated']} + cloud_promoted={r['promoted']} = total={r['total']} concepts | {tag}")
    if EXTRA_STORES:
        # Which promoted concepts are NOT in a from-scratch (no-overlay) run = the
        # net gain the overlay (e.g. Brain Link peer contributions) actually yields.
        base_names = set()
        try:
            EXTRA_SAVE = list(EXTRA_STORES)
            EXTRA_STORES.clear()
            base_names = {n for n in promote(dry_run=True)["promoted_names"]}
            EXTRA_STORES.extend(EXTRA_SAVE)
        except Exception:
            pass
        gained = [n for n in r["promoted_names"] if n not in base_names]
        print(f"[PROMOTE] net-new from overlay: {len(gained)} concepts")
        for n in gained[:25]:
            print("   +", n)
