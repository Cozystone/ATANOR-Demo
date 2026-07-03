"""Consensus-evidence ledger — the quarantine layer of the two-tier learning store.

THE keystone of the extraction-quality plan (난제 P1). Instead of trusting any single
extraction, every extracted relation first lands here as an EVIDENCE EVENT. A relation
is promoted to the verified candidate store only when it is confirmed by at least
`min_sources` INDEPENDENT pieces of evidence (distinct sentence hashes). Noise is
idiosyncratic per sentence; true facts recur — so extraction precision becomes a
counting problem that improves with data volume instead of with more hand rules
(the NELL / Knowledge Vault insight).

Two guards run before an evidence event is even counted:
  1. round-trip head check — the subject and object labels must actually occur in
     the source sentence; if extraction mangled a head, the evidence is rejected.
  2. degenerate-head check — single-char / date-unit heads are rejected (reuses the
     same class of guards as the decomposer, as defence in depth).

The ledger is append-only JSONL (events are the source of truth); aggregates are
rebuilt on load, so a crash can never corrupt counts.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

_DATE_UNIT_HEADS = {"일", "월", "년", "시", "분", "초", "세기", "요일", "주", "세", "차"}
_TOKEN = re.compile(r"[0-9A-Za-z가-힣]+")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_relation_key(source_label: str, relation: str, target_label: str) -> str:
    raw = f"{source_label.strip().lower()}|{relation.strip().lower()}|{target_label.strip().lower()}"
    return "cons_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def head_roundtrip_ok(label: str, sentence_text: str) -> bool:
    """The extracted head must be a real, non-degenerate part of the source sentence."""
    label = (label or "").strip()
    if len(label) < 2 and label not in _TOKEN.findall(sentence_text or ""):
        return False
    if label in _DATE_UNIT_HEADS:
        return False
    return bool(label) and label in (sentence_text or "")


@dataclass
class RecordResult:
    events_recorded: int = 0
    events_rejected_roundtrip: int = 0
    events_duplicate: int = 0
    relations_seen: int = 0

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


@dataclass
class PromotionResult:
    promoted: int = 0
    still_quarantined: int = 0
    promoted_keys: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"promoted": self.promoted, "still_quarantined": self.still_quarantined,
                "promoted_keys": self.promoted_keys[:20]}


class ConsensusLedger:
    """Append-only evidence ledger with consensus promotion."""

    def __init__(self, root: str | Path, *, min_sources: int = 2) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.ledger_path = self.root / "evidence_ledger.jsonl"
        self.promoted_path = self.root / "promoted_keys.jsonl"
        self.min_sources = max(1, int(min_sources))
        # aggregates: key -> {sources: set, row: representative relation row, labels}
        self._agg: dict[str, dict[str, Any]] = {}
        self._promoted: set[str] = set()
        self._load()

    # ---------- persistence ----------
    def _load(self) -> None:
        if self.ledger_path.exists():
            for line in self.ledger_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue  # torn tail write must not poison the ledger
                self._apply(ev)
        if self.promoted_path.exists():
            for line in self.promoted_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    try:
                        self._promoted.add(json.loads(line)["key"])
                    except (json.JSONDecodeError, KeyError):
                        continue

    def _apply(self, ev: dict[str, Any]) -> None:
        key = ev["key"]
        slot = self._agg.setdefault(key, {"sources": set(), "row": ev.get("row") or {},
                                          "source_label": ev.get("source_label"),
                                          "target_label": ev.get("target_label")})
        slot["sources"].add(ev["evidence_id"])
        if ev.get("row"):
            slot["row"] = ev["row"]

    def _append(self, ev: dict[str, Any]) -> None:
        with self.ledger_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(ev, ensure_ascii=False) + "\n")

    # ---------- recording ----------
    def record_decomposition(self, decomposition: Any) -> RecordResult:
        """Record all relations of one DecompositionResult as evidence events."""
        result = RecordResult()
        concepts = {c.get("concept_id"): c for c in getattr(decomposition, "concepts", [])}
        evidence = getattr(decomposition, "evidence", None) or {}
        sentence_text = str(evidence.get("text") or "")
        evidence_id = str(evidence.get("source_hash") or evidence.get("dedupe_key") or
                          hashlib.sha256(sentence_text.encode("utf-8")).hexdigest())
        for rel in getattr(decomposition, "relations", []):
            result.relations_seen += 1
            src = concepts.get(rel.get("source_concept_id"), {})
            tgt = concepts.get(rel.get("target_concept_id"), {})
            src_label = str(src.get("canonical_name") or src.get("label") or src.get("surface") or "")
            tgt_label = str(tgt.get("canonical_name") or tgt.get("label") or tgt.get("surface") or "")
            if sentence_text and not (head_roundtrip_ok(src_label, sentence_text)
                                      and head_roundtrip_ok(tgt_label, sentence_text)):
                result.events_rejected_roundtrip += 1
                continue
            key = canonical_relation_key(src_label, str(rel.get("relation") or ""), tgt_label)
            slot = self._agg.get(key)
            if slot and evidence_id in slot["sources"]:
                result.events_duplicate += 1
                continue
            ev = {"key": key, "evidence_id": evidence_id, "recorded_at": _utc_now(),
                  "source_label": src_label, "target_label": tgt_label, "row": rel}
            self._apply(ev)
            self._append(ev)
            result.events_recorded += 1
        return result

    # ---------- promotion ----------
    def promotable(self) -> list[tuple[str, dict[str, Any]]]:
        return [(k, v) for k, v in self._agg.items()
                if k not in self._promoted and len(v["sources"]) >= self.min_sources]

    def promote_into(self, store: Any) -> PromotionResult:
        """Write consensus-confirmed relations into the verified candidate store."""
        try:  # local import: avoid cycle; tolerate both path styles
            from cgsr.ingestion.accumulator import AccumulationResult
        except ImportError:
            from packages.cgsr.cgsr.ingestion.accumulator import AccumulationResult

        result = PromotionResult()
        agg = AccumulationResult()
        for key, slot in self.promotable():
            row = dict(slot["row"])
            row["evidence_count"] = len(slot["sources"])
            row["consensus_key"] = key
            row["consensus_promoted_at"] = _utc_now()
            appended = store._append_unique("relations", row, agg)  # noqa: SLF001 - store API
            self._promoted.add(key)
            with self.promoted_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"key": key, "at": row["consensus_promoted_at"],
                                     "evidence_count": row["evidence_count"]}, ensure_ascii=False) + "\n")
            if appended:
                result.promoted += 1
                result.promoted_keys.append(key)
        result.still_quarantined = sum(1 for k, v in self._agg.items()
                                       if k not in self._promoted)
        return result

    def stats(self) -> dict[str, Any]:
        counts = [len(v["sources"]) for v in self._agg.values()]
        return {
            "relations_quarantined": sum(1 for k in self._agg if k not in self._promoted),
            "relations_promoted_total": len(self._promoted),
            "min_sources": self.min_sources,
            "max_evidence_count": max(counts) if counts else 0,
            "pending_at_threshold": sum(1 for k, v in self._agg.items()
                                        if k not in self._promoted and len(v["sources"]) >= self.min_sources),
        }
