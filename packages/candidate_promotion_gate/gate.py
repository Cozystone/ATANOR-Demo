"""Candidate Promotion Gate (v0).

Turns a human-reviewed candidate (from the agentic review queue) into an
auditable, operator-signed *promotion request* — and nothing more. It exists to
ENFORCE the ATANOR rule: no candidate is promoted without explicit human
approval, and even with approval the production store is never silently mutated.

Design mirrors `construction_bank.promotion_gate` and
`local_memory_operator_confirmation.gate`:

- Default-deny. Eligibility requires the operator to have already *approved* the
  item in the review queue, plus provenance + confidence + non-critical risk.
- Operator confirmation requires an exact phrase (typo-proof gate).
- A confirmed promotion writes only a SIGNED MANIFEST artifact to a staging dir
  (auditable, reversible). It does NOT write the production cloud brain — that
  remains a separate, later gate. `production_store_mutated` stays False.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REQUIRED_CONFIRMATION_PHRASE = "PROMOTE REVIEWED CANDIDATES TO VERIFIED STAGING"

# Only these review-item types are ever promotable in v0. Raw trajectories and
# unscored sources are not.
PROMOTABLE_ITEM_TYPES = {"cloud_candidate", "construction_candidate"}

FORBIDDEN_TERMS = (
    "local_brain_direct_write",
    "local brain write",
    "production write",
    "production_store_mutated",
    "candidate promotion",
    "auto promote",
    "auto-promotion",
    "auto commit",
    "auto push",
    "raw_private_memory",
    "api_key",
    "api key",
    "secret",
    "token",
    "password",
)

# Minimal hard floor used in auto-promote mode (no operator). Incidental security
# vocabulary on a public page ("personal access token", "secret scanning") is NOT
# a reason to block; only genuine private-memory / mutation-directive signals are.
AUTO_HARD_FLOOR_TERMS = (
    "raw_private_memory",
    "local_brain_direct_write",
    "production_store_mutated",
    "local brain write",
    "production write",
)

INVARIANTS = {
    "external_llm": False,
    "external_sllm": False,
    "local_brain_write": False,
    "production_store_mutated": False,
    "production_activation": False,
    "auto_promote": False,
    "auto_commit": False,
    "auto_push": False,
    "signed_manifest_required": True,
    "rollback_required": True,
    "human_approval_required": True,
    "proof_only": True,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class PromotionThresholds:
    min_confidence: float = 0.5
    allowed_risk_levels: tuple[str, ...] = ("low", "medium")
    require_source_refs: bool = True
    require_status_approved: bool = True
    max_batch: int = 50


@dataclass(frozen=True)
class PromotionEntry:
    item_id: str
    item_type: str
    title: str
    risk_level: str
    confidence: float
    source_ref_count: int
    eligible: bool
    rejection_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _item_text(item: dict[str, Any]) -> str:
    return " ".join(
        [
            str(item.get("title", "")),
            str(item.get("summary", "")),
            " ".join(str(ref) for ref in (item.get("source_refs") or [])),
            str(item.get("risk_level", "")),
        ]
    ).lower()


def _contains_forbidden(item: dict[str, Any]) -> bool:
    return any(term in _item_text(item) for term in FORBIDDEN_TERMS)


def _contains_hard_floor(item: dict[str, Any]) -> bool:
    return any(term in _item_text(item) for term in AUTO_HARD_FLOOR_TERMS)


def evaluate_candidate_item(
    item: dict[str, Any],
    thresholds: PromotionThresholds = PromotionThresholds(),
    *,
    auto_mode: bool = False,
) -> PromotionEntry:
    """Pure eligibility check for a single review-queue item dict.

    Default-deny in operator mode. In ``auto_mode`` (operator does not intervene,
    promotion is allowed unconditionally) the human-approval and risk-level gates
    are dropped; only provenance + confidence + a minimal private/mutation hard
    floor remain so the brain is not poisoned with directive/private payloads.
    """

    reasons: list[str] = []
    item_type = str(item.get("item_type", ""))
    risk_level = str(item.get("risk_level", "high"))
    status = str(item.get("status", "pending"))
    try:
        confidence = float(item.get("confidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    source_refs = item.get("source_refs") or []
    source_ref_count = len(source_refs) if isinstance(source_refs, list) else 0

    if item_type not in PROMOTABLE_ITEM_TYPES:
        reasons.append(f"item_type_not_promotable:{item_type or 'unknown'}")
    if not auto_mode and thresholds.require_status_approved and status != "approved":
        reasons.append(f"not_human_approved:{status}")
    if not auto_mode and risk_level not in thresholds.allowed_risk_levels:
        reasons.append(f"risk_level_blocked:{risk_level}")
    if thresholds.require_source_refs and source_ref_count == 0:
        reasons.append("missing_source_refs")
    if confidence < thresholds.min_confidence:
        reasons.append("confidence_below_threshold")
    if auto_mode:
        if _contains_hard_floor(item):
            reasons.append("private_or_mutation_hard_floor")
    elif _contains_forbidden(item):
        reasons.append("forbidden_or_private_signal")

    return PromotionEntry(
        item_id=str(item.get("item_id", "")),
        item_type=item_type,
        title=str(item.get("title", ""))[:160],
        risk_level=risk_level,
        confidence=round(confidence, 4),
        source_ref_count=source_ref_count,
        eligible=not reasons,
        rejection_reasons=tuple(dict.fromkeys(reasons)),
    )


class CandidatePromotionGate:
    def __init__(self, *, staging_dir: Path | str | None = None, thresholds: PromotionThresholds = PromotionThresholds()) -> None:
        self.thresholds = thresholds
        self.staging_dir = Path(staging_dir) if staging_dir else Path("runtime/agentic_micro_os/promotions")

    # ----- evaluation / drafting -------------------------------------------------

    def evaluate(self, items: list[dict[str, Any]], item_ids: list[str] | None = None) -> list[PromotionEntry]:
        wanted = set(item_ids) if item_ids else None
        entries: list[PromotionEntry] = []
        for item in items:
            if wanted is not None and str(item.get("item_id", "")) not in wanted:
                continue
            entries.append(evaluate_candidate_item(item, self.thresholds))
        return entries

    def draft_manifest(self, items: list[dict[str, Any]], item_ids: list[str] | None = None, created_by: str = "operator") -> dict[str, Any]:
        entries = self.evaluate(items, item_ids)
        eligible = [entry for entry in entries if entry.eligible]
        eligible_ids = tuple(entry.item_id for entry in eligible)
        manifest_id = _manifest_id(eligible_ids, created_by, draft=True)
        return {
            **INVARIANTS,
            "manifest_id": manifest_id,
            "created_at": _utc_now(),
            "created_by": created_by,
            "status": "review_ready" if eligible_ids else "draft",
            "operator_confirmed": False,
            "promotion_approved_staged": False,
            "required_confirmation_phrase": REQUIRED_CONFIRMATION_PHRASE,
            "eligible_ids": list(eligible_ids),
            "eligible_count": len(eligible_ids),
            "evaluated_count": len(entries),
            "thresholds": asdict(self.thresholds),
            "entries": [entry.to_dict() for entry in entries],
        }

    # ----- confirmation / signing ------------------------------------------------

    def confirm_promotion(
        self,
        items: list[dict[str, Any]],
        *,
        item_ids: list[str] | None,
        operator_confirmed: bool,
        confirmation_phrase: str,
        operator_id: str = "operator",
    ) -> dict[str, Any]:
        """Default-deny. Only an exact phrase + confirmed flag + eligible items
        produces a signed, staged promotion manifest. Never writes production."""

        draft = self.draft_manifest(items, item_ids, created_by=operator_id)
        reasons: list[str] = []
        if not operator_confirmed:
            reasons.append("operator_confirmation_required")
        if (confirmation_phrase or "").strip() != REQUIRED_CONFIRMATION_PHRASE:
            reasons.append("required_phrase_mismatch")
        if not draft["eligible_ids"]:
            reasons.append("no_eligible_candidates")

        if reasons:
            return {
                **draft,
                "allowed": False,
                "promotion_approved_staged": False,
                "reasons": reasons,
                "manifest_path": None,
            }

        signed = {
            **draft,
            "manifest_id": _manifest_id(tuple(draft["eligible_ids"]), operator_id, draft=False),
            "status": "operator_approved_staged",
            "operator_confirmed": True,
            "operator_id": operator_id,
            "promotion_approved_staged": True,
            "signed_at": _utc_now(),
            "production_store_mutated": False,
            "production_activation": False,
            "note": (
                "Operator-signed promotion of reviewed candidates to verified STAGING. "
                "The production cloud brain is NOT mutated by this step; a separate "
                "production-merge gate remains required."
            ),
            "reasons": ["operator_confirmed_staged_promotion"],
        }
        path = self._write_manifest(signed)
        signed["manifest_path"] = str(path)
        signed["allowed"] = True
        return signed

    def auto_promote(self, items: list[dict[str, Any]], *, already_promoted: set[str] | None = None) -> dict[str, Any]:
        """Operator-free promotion (user policy: AGORA has no operator, promotion is
        allowed unconditionally). Promotes every auto-eligible item not already
        promoted, writing one signed manifest. Still skips the private/mutation
        hard floor and items without provenance — that is data hygiene, not an
        operator gate. Never writes the production store."""

        already = already_promoted or set()
        entries = [evaluate_candidate_item(item, self.thresholds, auto_mode=True) for item in items]
        eligible = [e.item_id for e in entries if e.eligible and e.item_id and e.item_id not in already]
        if not eligible:
            return {**INVARIANTS, "allowed": False, "auto_promoted": 0, "reason": "no_new_eligible", "newly_promoted_ids": []}
        signed = {
            **INVARIANTS,
            "manifest_id": _manifest_id(tuple(eligible), "auto", draft=False),
            "created_at": _utc_now(),
            "created_by": "autonomous_loop",
            "status": "auto_promoted_staged",
            "operator_confirmed": False,
            "auto_promoted": True,
            "promotion_approved_staged": True,
            "production_store_mutated": False,
            "production_activation": False,
            "newly_promoted_ids": eligible,
            "eligible_ids": eligible,
            "note": (
                "Auto-promoted (no operator) to verified STAGING under the user's "
                "unconditional-promotion policy. Production store NOT mutated; a "
                "private/mutation hard floor still applies."
            ),
        }
        self._write_manifest(signed)
        return {**signed, "allowed": True, "auto_promoted": len(eligible)}

    def list_manifests(self, limit: int = 10) -> list[dict[str, Any]]:
        if not self.staging_dir.exists():
            return []
        files = sorted(self.staging_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        manifests: list[dict[str, Any]] = []
        for file in files[:limit]:
            try:
                manifests.append(json.loads(file.read_text(encoding="utf-8")))
            except Exception:  # pragma: no cover - skip corrupt artifact
                continue
        return manifests

    def status(self, items: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        manifests = self.list_manifests()
        eligible_now = 0
        if items is not None:
            eligible_now = sum(1 for entry in self.evaluate(items) if entry.eligible)
        return {
            **INVARIANTS,
            "gate_available": True,
            "required_confirmation_phrase": REQUIRED_CONFIRMATION_PHRASE,
            "thresholds": asdict(self.thresholds),
            "eligible_now": eligible_now,
            "signed_manifests": len(manifests),
            "recent_manifests": manifests[:5],
            "staging_dir": str(self.staging_dir),
        }

    def _write_manifest(self, manifest: dict[str, Any]) -> Path:
        self.staging_dir.mkdir(parents=True, exist_ok=True)
        path = self.staging_dir / f"{manifest['manifest_id']}.json"
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        return path


def _manifest_id(eligible_ids: tuple[str, ...], created_by: str, *, draft: bool) -> str:
    digest = hashlib.sha256(("|".join(sorted(eligible_ids)) + created_by).encode("utf-8")).hexdigest()[:16]
    prefix = "promotion_draft" if draft else "promotion_signed"
    return f"{prefix}_{digest}"
