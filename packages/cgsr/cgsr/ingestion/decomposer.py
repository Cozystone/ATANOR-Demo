"""Concept and case-frame decomposition for verified sentences."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import re
from typing import Any

from cgsr.morphology import analyze

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
    roles, predicate = extract_case_roles(sentence.text)
    concept_names = {role["head"] for role in roles if normalize_concept(role["head"])}
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
