from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


STORE_FILES = {
    "concept": "concepts.jsonl",
    "relation": "relations.jsonl",
    "evidence": "evidence.jsonl",
    "case_frame": "case_frames.jsonl",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"{path}:{line_number} is not a JSON object")
            rows.append(payload)
    return rows


def load_store_rows(store_path: Path | str) -> dict[str, list[dict[str, Any]]]:
    root = Path(store_path)
    return {kind: read_jsonl(root / filename) for kind, filename in STORE_FILES.items()}


def dedupe_key(row: dict[str, Any], fallback_fields: Iterable[str]) -> str:
    value = row.get("dedupe_key")
    if value:
        return str(value)
    for field in fallback_fields:
        if row.get(field):
            return str(row[field])
    return ""


def dedupe_keys(rows: list[dict[str, Any]], fallback_fields: Iterable[str]) -> set[str]:
    return {key for row in rows if (key := dedupe_key(row, fallback_fields))}
