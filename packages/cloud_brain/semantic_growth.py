from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .semantic_dedupe import resolve_or_create_concept, upsert_semantic_relation
from .semantic_projection import project_sentence_to_semantic_candidates
from .semantic_store import DEFAULT_SEMANTIC_CLOUD_ROOT, SemanticCloudStore, utc_now_iso


def _split_sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", str(text or "").strip())
    if not normalized:
        return []
    parts = re.split(r"(?<=[.!?。！？])\s+|(?<=[.!?。！？])", normalized)
    return [part.strip() for part in parts if part and part.strip()]


def _source_hash(text: str, source_id: str) -> str:
    return hashlib.sha256(f"{source_id}\n{text}".encode("utf-8")).hexdigest()


def ingest_semantic_source(
    text: str,
    source_id: str,
    language: str = "auto",
    url: str | None = None,
    title: str | None = None,
    license: str | None = None,
    usage_allowed: bool = False,
    *,
    cloud_root: str | Path = DEFAULT_SEMANTIC_CLOUD_ROOT,
) -> dict[str, Any]:
    store = SemanticCloudStore(cloud_root)
    sentences = _split_sentences(text)
    run_id = f"scg_{hashlib.sha256((source_id + text).encode('utf-8')).hexdigest()[:18]}"
    concepts_created = 0
    concepts_merged = 0
    relations_created = 0
    relations_strengthened = 0
    evidence_added = 0
    source_hash = _source_hash(text, source_id)
    now = utc_now_iso()
    evidence_row = {
        "source_hash": source_hash,
        "source_id": source_id,
        "text_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "short_snippet": text[:280] if usage_allowed and len(text) <= 1000 else None,
        "url": url,
        "title": title,
        "license": license,
        "usage_allowed": bool(usage_allowed),
        "created_at": now,
        "metadata": {"raw_text_policy": "short_snippet_only_when_allowed"},
    }
    if store.add_evidence(evidence_row):
        evidence_added = 1

    for sentence in sentences:
        projection = project_sentence_to_semantic_candidates(sentence, language=language)
        concept_by_name: dict[str, dict[str, Any]] = {}
        for candidate in projection.get("concept_candidates", []):
            concept, created = resolve_or_create_concept(candidate, store, source_hash=source_hash)
            concept_by_name[str(candidate.get("name") or candidate.get("canonical_name"))] = concept
            if created:
                concepts_created += 1
            else:
                concepts_merged += 1
        for relation in projection.get("relation_candidates", []):
            source_name = str(relation.get("source") or "")
            target_name = str(relation.get("target") or "")
            source_concept = concept_by_name.get(source_name)
            if not source_concept:
                source_concept, created = resolve_or_create_concept(
                    {"name": source_name, "confidence": relation.get("confidence", 0.55)},
                    store,
                    source_hash=source_hash,
                )
                concepts_created += 1 if created else 0
                concepts_merged += 0 if created else 1
            target_concept = concept_by_name.get(target_name)
            if not target_concept:
                target_concept, created = resolve_or_create_concept(
                    {"name": target_name, "confidence": relation.get("confidence", 0.55)},
                    store,
                    source_hash=source_hash,
                )
                concepts_created += 1 if created else 0
                concepts_merged += 0 if created else 1
            _, created_relation = upsert_semantic_relation(
                str(source_concept["concept_id"]),
                str(relation.get("relation") or "related_to"),
                str(target_concept["concept_id"]),
                source_hash,
                float(relation.get("confidence") or 0.55),
                store,
            )
            if created_relation:
                relations_created += 1
            else:
                relations_strengthened += 1

    summary = {
        "run_id": run_id,
        "sentences_processed": len(sentences),
        "concepts_created": concepts_created,
        "concepts_merged": concepts_merged,
        "relations_created": relations_created,
        "relations_strengthened": relations_strengthened,
        "evidence_added": evidence_added,
        "store_path": str(store.paths["store"]),
        "status": store.status(),
        "honesty": {
            "local_brain_write": False,
            "external_llm_used": False,
            "external_sllm_used": False,
            "global_cloud_claim": False,
            "proof_store_only": True,
        },
    }
    run_path = store.paths["growth_runs"] / f"{run_id}.json"
    run_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary
