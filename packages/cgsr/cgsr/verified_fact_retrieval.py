from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from packages.cgsr.cgsr.ingestion.verification_gate import has_mock_signal


TEXT_FIELDS = ("text", "sentence", "source_text", "claim", "content", "canonical_form")
SOURCE_FIELDS = ("source_ref", "source_id", "document_id", "url")
STORE_FILES = ("evidence.jsonl", "relations.jsonl", "case_frames.jsonl", "concepts.jsonl")
FILE_PRIORITIES = {
    "evidence.jsonl": 1.0,
    "relations.jsonl": 0.88,
    "case_frames.jsonl": 0.72,
    "concepts.jsonl": 0.58,
}
STOP_TOKENS = {
    "about",
    "explain",
    "what",
    "when",
    "where",
    "which",
    "whose",
    "how",
    "please",
    "대해",
    "설명",
    "설명해줘",
    "알려줘",
    "보여줘",
    "무엇",
    "뭐야",
    "어떻게",
    "그리고",
}
KOREAN_SUFFIXES = (
    "으로는",
    "로는",
    "으로",
    "에서",
    "에게",
    "에는",
    "이다",
    "입니다",
    "하고",
    "까지",
    "부터",
    "처럼",
    "보다",
    "이며",
    "이나",
    "거나",
    "은",
    "는",
    "이",
    "가",
    "을",
    "를",
    "의",
    "에",
    "로",
    "과",
    "와",
)


@dataclass(frozen=True)
class VerifiedFactHit:
    fact: str
    source_ref: str
    score: float


def _read_jsonl(path: Path, *, limit: int = 10000) -> list[dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            if len(rows) >= limit:
                break
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def _normalize_token(token: str) -> str:
    token = token.casefold().strip()
    for suffix in KOREAN_SUFFIXES:
        if len(token) > len(suffix) + 1 and token.endswith(suffix):
            return token[: -len(suffix)]
    return token


def _tokens(text: str) -> set[str]:
    raw = re.findall(r"[0-9A-Za-z가-힣]{2,}", str(text or ""))
    tokens = {_normalize_token(token) for token in raw if len(_normalize_token(token)) >= 2}
    return {token for token in tokens if token not in STOP_TOKENS}


def _row_text(row: dict[str, Any]) -> str:
    for field in TEXT_FIELDS:
        value = row.get(field)
        if value:
            return re.sub(r"\s+", " ", str(value).strip())
    source = row.get("source") or row.get("subject") or row.get("source_label")
    predicate = row.get("predicate") or row.get("relation") or row.get("relation_type")
    target = row.get("target") or row.get("object") or row.get("target_label")
    if source and predicate and target:
        return re.sub(r"\s+", " ", f"{source} {predicate} {target}".strip())
    return ""


def _source_ref(row: dict[str, Any], fallback: str) -> str:
    provenance = row.get("provenance") if isinstance(row.get("provenance"), dict) else {}
    for field in SOURCE_FIELDS:
        value = row.get(field) or provenance.get(field)
        if value:
            return str(value)
    source_name = provenance.get("source_name") or row.get("source_name")
    title = provenance.get("title") or row.get("title")
    if source_name or title:
        return " / ".join(str(value) for value in (source_name, title) if value)
    return fallback


def _is_verified(row: dict[str, Any]) -> bool:
    verification = row.get("verification") if isinstance(row.get("verification"), dict) else {}
    status = str(row.get("status") or row.get("verification_status") or verification.get("status") or "verified")
    return status in {"verified", "accepted"}


def retrieve_verified_facts(
    question: str,
    *,
    store_path: str | Path | None,
    limit: int = 4,
) -> list[VerifiedFactHit]:
    """Read verified-store facts relevant to a question without mutating data.

    This is extractive retrieval, not answer generation. It only returns rows
    already present in a verified JSONL store and refuses mock-template signals.
    """

    if not store_path:
        return []
    root = Path(store_path)
    if not root.exists() or not root.is_dir():
        return []
    query_tokens = _tokens(question)
    if not query_tokens:
        return []

    rows: list[tuple[str, dict[str, Any]]] = []
    for filename in STORE_FILES:
        for row in _read_jsonl(root / filename):
            rows.append((filename, row))

    hits: list[VerifiedFactHit] = []
    seen: set[str] = set()
    for filename, row in rows:
        if not _is_verified(row):
            continue
        text = _row_text(row)
        if not text or has_mock_signal(text):
            continue
        row_tokens = _tokens(text)
        if not row_tokens:
            continue
        overlap = query_tokens & row_tokens
        if not overlap:
            continue
        if len(query_tokens) >= 2 and len(overlap) < 2:
            continue
        base_score = len(overlap) / max(1, len(query_tokens))
        score = base_score * FILE_PRIORITIES.get(filename, 0.5)
        if score < 0.18:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        hits.append(VerifiedFactHit(fact=text, source_ref=_source_ref(row, filename), score=round(score, 4)))

    hits.sort(key=lambda hit: (-hit.score, len(hit.fact), hit.fact))
    return hits[:limit]
