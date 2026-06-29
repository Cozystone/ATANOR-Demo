"""Concept and case-frame decomposition for verified sentences."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import re
from typing import Any

from ..morphology import analyze

from .source_reader import SourceSentence
from .verification_gate import VerificationDecision, has_mock_signal, normalize_for_dedupe


CASE_TAG_TO_ROLE = {
    "JKS": "SUBJ",
    "JX": "TOPIC",
    "JKO": "OBJ",
    "JKB": "ADVL",
}
NOUN_TAG_PREFIXES = ("NN", "SL", "SH", "SN")
PREDICATE_TAG_PREFIXES = ("VV", "VA")
GENERIC_HEADS = {"것", "수", "등", "때", "곳"}
ENGLISH_VERB_LEMMAS = {
    "is": "be",
    "are": "be",
    "was": "be",
    "were": "be",
    "has": "have",
    "have": "have",
    "had": "have",
    "uses": "use",
    "used": "use",
    "provides": "provide",
    "supports": "support",
    "manages": "manage",
    "contains": "contain",
    "includes": "include",
    "refers": "refer",
    "describes": "describe",
    "represents": "represent",
    "enables": "enable",
    "allows": "allow",
    "requires": "require",
    "consists": "consist",
    "became": "become",
    "becomes": "become",
    "means": "mean",
    "defines": "define",
    "connects": "connect",
    "stores": "store",
    "records": "record",
    "tracks": "track",
    "verifies": "verify",
    "validates": "validate",
}
ENGLISH_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "by",
    "for",
    "from",
    "in",
    "into",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "with",
}
# Bare function/quantifier heads that are not real concepts on their own. Filtered
# at concept creation so single tokens like "other"/"such" never become nodes.
ENGLISH_GENERIC_HEADS = {
    "other",
    "others",
    "such",
    "various",
    "many",
    "more",
    "most",
    "one",
    "ones",
    "thing",
    "things",
    "kind",
    "kinds",
    "type",
    "types",
    "way",
    "ways",
    "etc",
    "some",
    "any",
    "each",
    "both",
}
# Function words that must never become concept nodes (prepositions, demonstratives,
# pronouns, conjunctions, auxiliaries, common adverbs). The small ENGLISH_STOPWORDS
# set above leaked obvious non-concepts ("this", "through", "it", "they") into the
# store; this is the broader gate applied at concept creation. Content nouns — even
# generic ones — are NOT rejected here (that needs POS); the relation entity-gate
# downstream stops generic words from forming relations.
_ENGLISH_FUNCTION_WORDS = frozenset({
    # prepositions
    "in", "on", "at", "by", "to", "of", "for", "with", "from", "into", "onto", "upon",
    "within", "without", "between", "among", "amongst", "across", "behind", "beyond",
    "during", "before", "after", "above", "below", "under", "underneath", "over",
    "through", "throughout", "toward", "towards", "about", "against", "along", "around",
    "amid", "beneath", "beside", "besides", "despite", "except", "inside", "outside",
    "near", "off", "out", "since", "till", "until", "unto", "via", "versus", "per", "as",
    # determiners / demonstratives / quantifiers
    "this", "that", "these", "those", "the", "a", "an", "each", "every", "either",
    "neither", "all", "any", "some", "no", "none", "both", "few", "fewer", "many",
    "much", "most", "more", "less", "least", "such", "other", "another", "same", "own",
    "several", "various", "enough", "certain",
    # pronouns
    "i", "me", "my", "mine", "myself", "we", "us", "our", "ours", "ourselves", "you",
    "your", "yours", "yourself", "yourselves", "he", "him", "his", "himself", "she",
    "her", "hers", "herself", "it", "its", "itself", "they", "them", "their", "theirs",
    "themselves", "who", "whom", "whose", "which", "what", "whoever", "whatever",
    "whichever", "someone", "anyone", "everyone", "nobody", "anybody", "everybody",
    "something", "anything", "everything", "nothing",
    # conjunctions / aux / common adverbs
    "and", "or", "but", "nor", "so", "yet", "because", "although", "though", "while",
    "whereas", "if", "unless", "whether", "than", "then", "thus", "hence", "therefore",
    "however", "moreover", "furthermore", "nevertheless", "nonetheless", "meanwhile",
    "not", "only", "just", "also", "too", "very", "quite", "rather", "still", "already",
    "always", "never", "often", "sometimes", "usually", "here", "there", "now", "when",
    "where", "why", "how", "again", "once", "ever", "even", "else", "perhaps", "maybe",
    "indeed", "almost", "nearly", "really", "actually", "simply", "merely",
    "is", "are", "was", "were", "be", "been", "being", "am", "do", "does", "did",
    "have", "has", "had", "having", "will", "would", "shall", "should", "can", "could",
    "may", "might", "must", "ought",
})


def _is_quality_english_concept(name: str) -> bool:
    """Reject obvious non-concepts (function words, bare tokens) at concept creation."""
    n = name.strip()
    if len(n) < 2:
        return False
    low = n.casefold()
    if low in _ENGLISH_FUNCTION_WORDS:
        return False
    if not any(ch.isalpha() for ch in n):  # pure numbers / punctuation
        return False
    return True


_ENGLISH_COPULA_RE = re.compile(r"\b(is|are|was|were)\b", re.IGNORECASE)
_ENGLISH_INTRO_PREPOSITIONS = {
    "in",
    "on",
    "at",
    "as",
    "for",
    "by",
    "with",
    "from",
    "within",
    "under",
    "during",
    "throughout",
    "through",
    "after",
    "before",
    "among",
    "across",
    "despite",
    "unlike",
    "according",
}


@dataclass
class DecompositionResult:
    """Concept-language decomposition output for one verified sentence."""

    concepts: list[dict[str, Any]] = field(default_factory=list)
    relations: list[dict[str, Any]] = field(default_factory=list)
    case_frames: list[dict[str, Any]] = field(default_factory=list)
    evidence: dict[str, Any] | None = None


def utc_now() -> str:
    """Return a UTC timestamp string."""

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def digest_id(prefix: str, value: str) -> str:
    """Return a short deterministic id."""

    return f"{prefix}_{hashlib.sha256(value.encode('utf-8')).hexdigest()[:20]}"


def normalize_concept(text: str) -> str:
    """Normalize a concept label without erasing Hangul content."""

    value = re.sub(r"[^\w가-힣]+", " ", str(text or "")).strip()
    return re.sub(r"\s+", " ", value)


def predicate_lemma_from_tokens(tokens: list[Any]) -> str:
    """Extract a conservative Korean predicate lemma from Kiwi tokens."""

    for index, token in enumerate(tokens):
        form = str(getattr(token, "form", ""))
        tag = str(getattr(token, "tag", ""))
        if tag in {"XSV", "XSA"} and index > 0:
            previous = str(getattr(tokens[index - 1], "form", ""))
            if previous:
                return previous + "하다"
        if tag.startswith(PREDICATE_TAG_PREFIXES):
            return form + "다"
    return ""


def extract_case_roles(sentence: str) -> tuple[list[dict[str, str]], str]:
    """Return case-role heads and predicate lemma from a Korean sentence."""

    tokens = analyze(sentence)
    roles: list[dict[str, str]] = []
    last_noun = ""
    for token in tokens:
        form = str(getattr(token, "form", ""))
        tag = str(getattr(token, "tag", ""))
        if tag.startswith(NOUN_TAG_PREFIXES) and form not in GENERIC_HEADS:
            last_noun = form
            continue
        if tag in CASE_TAG_TO_ROLE and last_noun:
            marker = form
            roles.append({"role": CASE_TAG_TO_ROLE[tag], "marker": marker, "head": last_noun})
            last_noun = ""
    predicate = predicate_lemma_from_tokens(tokens)
    deduped: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in roles:
        deduped[(row["role"], row["marker"], row["head"])] = row
    return list(deduped.values()), predicate


def _english_tokens(sentence: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z0-9_-]*", sentence)


def _english_head(tokens: list[str]) -> str:
    for token in reversed(tokens):
        lowered = token.casefold()
        if lowered not in ENGLISH_STOPWORDS and lowered not in ENGLISH_VERB_LEMMAS:
            return token
    return ""


def _english_definition_subject(sentence: str) -> str:
    """Return the leading subject phrase of a copula definition, e.g.
    "Marie Curie was a physicist" -> "Marie Curie", "The telephone is ..." ->
    "telephone". Keeps the real multi-word subject as one concept instead of a
    single trailing token. Returns "" when there is no clean short subject."""

    match = _ENGLISH_COPULA_RE.search(sentence)
    if not match:
        return ""
    before = sentence[: match.start()]
    parts = [part.strip() for part in before.split(",") if part.strip()]
    if not parts:
        return ""
    # "In physics, gravity is ..." opens with an introductory phrase; the real
    # subject follows it. An appositive ("A telephone, shortened to phone, is ...")
    # keeps the subject in the first segment.
    head = parts[0]
    if len(parts) > 1 and head.split()[0].casefold() in _ENGLISH_INTRO_PREPOSITIONS:
        head = parts[1]
    tokens = _english_tokens(head)
    while tokens and tokens[0].casefold() in {"a", "an", "the"}:
        tokens = tokens[1:]
    # A clean definitional subject is a short noun phrase, not a whole clause.
    if not tokens or len(tokens) > 5:
        return ""
    return " ".join(tokens)


def extract_english_case_roles(sentence: str) -> tuple[list[dict[str, str]], str]:
    """Return a conservative English SVO-style case frame.

    This deterministic helper is only for licensed corpus ingestion. It does
    not infer facts; it extracts simple subject/object heads around an explicit
    factual verb so English rows can produce review-gated candidate frames.
    """

    tokens = _english_tokens(sentence)
    if not tokens:
        return [], ""
    predicate_index = -1
    predicate = ""
    for index, token in enumerate(tokens):
        lemma = ENGLISH_VERB_LEMMAS.get(token.casefold())
        if lemma:
            predicate_index = index
            predicate = lemma
            break
    if predicate_index < 0:
        return [], ""
    roles: list[dict[str, str]] = []
    # For copula definitions ("X is/are ..."), keep the real multi-word subject
    # ("Marie Curie") rather than a single trailing token ("Curie").
    subject = ""
    if predicate == "be":
        subject = _english_definition_subject(sentence)
    if not subject:
        subject = _english_head(tokens[:predicate_index])
    obj = _english_head(tokens[predicate_index + 1 :])
    if subject:
        roles.append({"role": "SUBJ", "marker": "", "head": subject})
    if obj:
        roles.append({"role": "OBJ", "marker": "", "head": obj})
    return roles, predicate


def concept_key(name: str, language: str) -> str:
    """Return the verified store concept dedupe key."""

    normalized = normalize_for_dedupe(name)
    return digest_id("concept_key", f"{language}:{normalized}")


def frame_key(predicate: str, roles: list[dict[str, str]], language: str) -> str:
    """Return the verified store case-frame dedupe key."""

    tokens = [f"{role['role']}:{role.get('marker','')}:{normalize_for_dedupe(role['head'])}" for role in roles]
    tokens.sort()
    return digest_id("frame_key", f"{language}:{predicate}:{'|'.join(tokens)}")


def _verification_block(decision: VerificationDecision) -> dict[str, str]:
    return decision.to_verification()


def _provenance(sentence: SourceSentence, ingest_run_id: str) -> dict[str, Any]:
    row = dict(sentence.provenance)
    row["ingest_run_id"] = ingest_run_id
    return row


def _evidence(sentence: SourceSentence, decision: VerificationDecision) -> dict[str, Any]:
    return {
        "source_id": sentence.source_id,
        "source_hash": sentence.source_hash,
        "source_type": sentence.source_type,
        "title": sentence.title,
        "url": sentence.url,
        "license": sentence.license,
        "usage_allowed": sentence.usage_allowed,
        "collected_at": sentence.collected_at,
        "verification": _verification_block(decision),
        "text": sentence.text,
    }


# Bare placeholder nouns that are not real categories ('…인 것이다', '…하나이다'). These
# are pronoun-like discourse heads, not classes — excluded so IS_A stays a type signal.
# This is a tiny structural stoplist (like the concept-quality gate), not a knowledge map.
_NON_CATEGORY_HEADS = frozenset({"것", "하나", "등", "경우", "때", "점", "곳", "데", "측면", "쪽", "거", "게", "걸", "분"})


def _copula_category(text: str) -> str:
    """The category a definition assigns its subject — the noun right before the copula
    ('삼성전자는 … 기업이다' → '기업'; 'X is a company' → 'company'). A structural language
    signal (not a knowledge rule): it lets the learner emit IS_A(subject, category) so a
    type hierarchy is built in the graph FROM DATA, replacing a hand-coded type lexicon."""
    text = str(text or "")
    m = re.search(r"([가-힣]{2,})\s*(?:이다|입니다|이며|이고|이라\b)", text)
    if m and m.group(1) not in _NON_CATEGORY_HEADS:
        return m.group(1)
    m = re.search(r"\bis\s+(?:a|an|the)\s+([A-Za-z][A-Za-z ]{1,40}?)[.,;\s]", text, re.IGNORECASE)
    return m.group(1).strip() if m else ""


def decompose_sentence(
    sentence: SourceSentence,
    decision: VerificationDecision,
    *,
    ingest_run_id: str,
) -> DecompositionResult:
    """Decompose a verified sentence into concepts, relations, and case frames."""

    if decision.status != "verified":
        return DecompositionResult(evidence=_evidence(sentence, decision))
    if has_mock_signal(sentence.text, sentence.source_id, sentence.source_type):
        rejected = VerificationDecision("rejected", "mock_template_signal", decision.dedupe_key, decision.checked_at)
        return DecompositionResult(evidence=_evidence(sentence, rejected))

    created_at = utc_now()
    provenance = _provenance(sentence, ingest_run_id)
    verification = _verification_block(decision)
    if sentence.language == "en":
        roles, predicate = extract_english_case_roles(sentence.text)
    else:
        roles, predicate = extract_case_roles(sentence.text)
    concept_names = {
        role["head"]
        for role in roles
        if normalize_concept(role["head"])
        and role["head"].casefold() not in ENGLISH_GENERIC_HEADS
        and _is_quality_english_concept(role["head"])
    }
    if predicate:
        concept_names.add(predicate)
    concepts: dict[str, dict[str, Any]] = {}
    for name in sorted(concept_names):
        canonical = normalize_concept(name)
        if not canonical:
            continue
        dedupe_key = concept_key(canonical, sentence.language)
        concepts[canonical] = {
            "concept_id": digest_id("vsc", dedupe_key),
            "canonical_name": canonical,
            "language": sentence.language,
            "dedupe_key": dedupe_key,
            "provenance": provenance,
            "verification": verification,
            "created_at": created_at,
            "updated_at": created_at,
        }

    relations: list[dict[str, Any]] = []
    predicate_concept = concepts.get(predicate) if predicate else None
    for role in roles:
        source = concepts.get(role["head"])
        if not source or not predicate_concept:
            continue
        rel_name = f"{role['role']}_OF"
        dedupe_key = digest_id(
            "relation_key",
            f"{source['concept_id']}:{rel_name}:{predicate_concept['concept_id']}:{sentence.source_hash}",
        )
        relations.append(
            {
                "relation_id": digest_id("vsr", dedupe_key),
                "source_concept_id": source["concept_id"],
                "relation": rel_name,
                "target_concept_id": predicate_concept["concept_id"],
                "language": sentence.language,
                "dedupe_key": dedupe_key,
                "provenance": provenance,
                "verification": verification,
                "created_at": created_at,
                "updated_at": created_at,
                "case_role": role,
            }
        )

    # IS_A: for a copula DEFINITION ("삼성전자는 … 기업이다"), record subject is_a category.
    # The case-role extractor leaves the copula predicate empty and the subject as TOPIC,
    # so extract the category directly and ensure both ends are concepts. This builds a
    # type hierarchy in the graph FROM DATA — the basis for deriving entity types from
    # is_a later instead of a hand-coded type lexicon.
    _category = _copula_category(sentence.text)
    _subj_head = next((r["head"] for r in roles if r.get("role") in ("SUBJ", "TOPIC")), None)
    _cat_canon = normalize_concept(_category) if _category else ""
    _subj_canon = normalize_concept(_subj_head) if _subj_head else ""
    if _cat_canon and _subj_canon and _cat_canon != _subj_canon:
        for canon in (_subj_canon, _cat_canon):
            if canon not in concepts:
                dk = concept_key(canon, sentence.language)
                concepts[canon] = {
                    "concept_id": digest_id("vsc", dk),
                    "canonical_name": canon,
                    "language": sentence.language,
                    "dedupe_key": dk,
                    "provenance": provenance,
                    "verification": verification,
                    "created_at": created_at,
                    "updated_at": created_at,
                }
        src, tgt = concepts.get(_subj_canon), concepts.get(_cat_canon)
        if src and tgt:
            dedupe_key = digest_id("relation_key", f"{src['concept_id']}:IS_A:{tgt['concept_id']}:{sentence.source_hash}")
            relations.append(
                {
                    "relation_id": digest_id("vsr", dedupe_key),
                    "source_concept_id": src["concept_id"],
                    "relation": "IS_A",
                    "target_concept_id": tgt["concept_id"],
                    "language": sentence.language,
                    "dedupe_key": dedupe_key,
                    "provenance": provenance,
                    "verification": verification,
                    "created_at": created_at,
                    "updated_at": created_at,
                }
            )

    case_frames: list[dict[str, Any]] = []
    if predicate and roles:
        canonical_roles = sorted(f"{role['role']}:{role['marker']}:{role['head']}" for role in roles)
        canonical_form = " ".join([*canonical_roles, f"PREDICATE:{predicate}"])
        dedupe_key = frame_key(predicate, roles, sentence.language)
        case_frames.append(
            {
                "frame_id": digest_id("vcf", dedupe_key),
                "language": sentence.language,
                "predicate": predicate,
                "case_roles": roles,
                "canonical_form": canonical_form,
                "dedupe_key": dedupe_key,
                "source_hash": sentence.source_hash,
                "provenance": provenance,
                "verification": verification,
                "created_at": created_at,
                "updated_at": created_at,
            }
        )
    return DecompositionResult(
        concepts=list(concepts.values()),
        relations=relations,
        case_frames=case_frames,
        evidence=_evidence(sentence, decision),
    )
