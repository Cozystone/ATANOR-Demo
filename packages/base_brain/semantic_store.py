"""Disk-backed, inverted-indexed semantic concept store — the ANSWER-QUALITY half of
"성능 상향평준화". The node_store bounds the geometric fields; this bounds the SEMANTIC
payload (concept name/description/relations) that actually determines answer quality.

Two problems with the current answer path (`get_semantic_context`): for each query it
(1) SCANS every concept — O(N) — and (2) copies every concept dict, so as the brain
grows both LATENCY and RAM grow linearly (measured: 1.5k=102ms, 20k=1.4s, 100k=7s). A
big brain or a weak PC both degrade — the opposite of leveling-up.

This store fixes both with standard IR + streaming:
  - concept records live on DISK (JSONL + offset index); query reads only the CANDIDATE
    records, not all N -> resident payload RAM is bounded by the candidate set.
  - an inverted index (token -> concept ids) yields candidates in O(query tokens); only
    candidates are scored -> latency is bounded by candidates, not N.

Honest scope: the inverted index + offset map are held in RAM (O(N), but far smaller
than the records they point at, and sardable later). The big win — keeping descriptions
and scoring off the O(N) path — is real and measured. Scoring reuses pack_loader's
_concept_score so ranking matches the in-RAM path exactly.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .pack_loader import _concept_score, _norm, _tokens


def _index_tokens(concept: dict[str, Any]) -> set[str]:
    """Tokens under which a concept is findable — the same fields _concept_score
    matches names on (id, canonical_name, aliases, label values), plus the whole
    normalized name so a single-token or exact-name query still retrieves it."""
    toks: set[str] = set()
    names = [concept.get("concept_id", ""), concept.get("canonical_name", ""), *(concept.get("aliases") or [])]
    names.extend(str(v) for v in (concept.get("labels") or {}).values())
    for name in names:
        toks |= _tokens(str(name))
        nn = _norm(str(name))
        if nn:
            toks.add(nn)
    # Also index description tokens: _concept_score gives desc-token overlap a (small)
    # weight, so a concept matched only via its description must still be a candidate —
    # otherwise the store would drop secondary context the full scan finds. Descriptions
    # are one short sentence, so this keeps the inverted index modest.
    toks |= _tokens(str(concept.get("short_description", "")))
    return toks


class SemanticConceptStore:
    def __init__(self, root: Path, offsets: dict[str, tuple[int, int]], inverted: dict[str, list[str]]):
        self.root = Path(root)
        self._offsets = offsets           # concept_id -> (byte offset, length) in records.jsonl
        self._inverted = inverted         # token -> [concept_id, ...]
        self._records_path = self.root / "records.jsonl"

    @property
    def n(self) -> int:
        return len(self._offsets)

    # ---- build / open -------------------------------------------------------
    @classmethod
    def build(cls, root: str | Path, concepts: Iterable[dict[str, Any]]) -> "SemanticConceptStore":
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True)
        offsets: dict[str, tuple[int, int]] = {}
        inverted: dict[str, list[str]] = {}
        pos = 0
        with (root / "records.jsonl").open("wb") as fh:
            for c in concepts:
                cid = str(c.get("concept_id"))
                line = (json.dumps(c, ensure_ascii=False) + "\n").encode("utf-8")
                fh.write(line)
                offsets[cid] = (pos, len(line))
                pos += len(line)
                for t in _index_tokens(c):
                    inverted.setdefault(t, []).append(cid)
        (root / "index.json").write_text(
            json.dumps({"offsets": {k: list(v) for k, v in offsets.items()}, "inverted": inverted}, ensure_ascii=False),
            encoding="utf-8",
        )
        return cls(root, offsets, inverted)

    @classmethod
    def open(cls, root: str | Path) -> "SemanticConceptStore":
        root = Path(root)
        idx = json.loads((root / "index.json").read_text(encoding="utf-8"))
        offsets = {k: (int(v[0]), int(v[1])) for k, v in idx["offsets"].items()}
        return cls(root, offsets, idx["inverted"])

    # ---- bounded lookup -----------------------------------------------------
    def _read_record(self, fh, cid: str) -> dict[str, Any] | None:
        loc = self._offsets.get(cid)
        if not loc:
            return None
        off, length = loc
        fh.seek(off)
        try:
            return json.loads(fh.read(length).decode("utf-8"))
        except Exception:
            return None

    def _query_keys(self, query: str) -> set[str]:
        """Index keys to probe for candidates: the query's tokens, the whole normalized
        query, AND every contiguous substring of the normalized query. The substrings
        capture _concept_score's `name_norm in query_norm` rule (a concept whose NAME is
        a substring of the query, e.g. name '데이터' for query '데이터베이스') which token
        matching alone misses. Bounded by query length (O(len^2) tiny probes), never N."""
        keys = _tokens(query) | {_norm(query)}
        nq = _norm(query)
        m = len(nq)
        if m <= 40:  # queries are short; guard against a pathological long input
            for i in range(m):
                for j in range(i + 2, m + 1):
                    keys.add(nq[i:j])
        return keys

    def get_concept_by_id(self, cid: str) -> dict[str, Any] | None:
        """O(1) fetch of one concept record by id (offset seek) — lets the answer path
        resolve a specific concept (e.g. 'atanor' for identity) WITHOUT holding the full
        concept list in RAM, so pack-load stays bounded at trillion scale."""
        with self._records_path.open("rb") as fh:
            return self._read_record(fh, str(cid))

    def get_concepts_by_ids(self, cids: Iterable[str]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        with self._records_path.open("rb") as fh:
            for cid in cids:
                rec = self._read_record(fh, str(cid))
                if rec is not None:
                    out.append(rec)
        return out

    def _candidate_ids(self, query: str, max_candidates: int) -> list[str]:
        seen: dict[str, None] = {}
        for t in self._query_keys(query):
            for cid in self._inverted.get(t, ()):  # postings list
                if cid not in seen:
                    seen[cid] = None
                    if len(seen) >= max_candidates:
                        return list(seen)
        return list(seen)

    def lookup(self, query: str, limit: int = 12, max_candidates: int = 4000) -> list[dict[str, Any]]:
        """Top-`limit` concepts, replicating get_semantic_context's contract: score>=1.0
        threshold, korean/english_language special-case, and relation-target expansion —
        but scoring ONLY candidate records read from disk on demand. Peak RAM = candidate
        set, latency = O(candidates); both bounded regardless of total concept count N."""
        cand = self._candidate_ids(query, max_candidates)
        with self._records_path.open("rb") as fh:
            recs = {cid: r for cid in cand if (r := self._read_record(fh, cid)) is not None}
            scored = sorted(
                ({**r, "match_score": _concept_score(query, r)} for r in recs.values()),
                key=lambda it: (float(it.get("match_score") or 0.0), float(it.get("confidence") or 0.0)),
                reverse=True,
            )
            high_conf = [it for it in scored if float(it.get("match_score") or 0.0) >= 4.0]
            q_low = query.lower()
            selected = [it for it in scored if float(it.get("match_score") or 0.0) >= 1.0][:limit]
            if high_conf:
                selected = [
                    it for it in selected
                    if it.get("concept_id") not in {"korean_language", "english_language"}
                    or any(mk in q_low for mk in ["한국어", "영어로", "번역투", "language"])
                ][:limit]
            # relation-target expansion: pull selected concepts' relation targets (read
            # their records on demand) up to limit, matching the in-RAM path.
            if selected:
                sel_ids = {it["concept_id"] for it in selected}
                targets = {rel.get("target") for it in selected for rel in it.get("relations", []) if rel.get("target")}
                # Add in rank order (score desc), matching get_semantic_context which walks
                # the ranked list — so tail context ordering is identical, not just the set.
                extra = []
                for tid in targets:
                    if tid in sel_ids:
                        continue
                    rec = recs.get(tid) or self._read_record(fh, str(tid))
                    if rec is not None:
                        extra.append({**rec, "match_score": _concept_score(query, rec)})
                extra.sort(key=lambda it: (float(it.get("match_score") or 0.0), float(it.get("confidence") or 0.0)), reverse=True)
                for it in extra:
                    if len(selected) >= limit:
                        break
                    selected.append(it)
            return selected[:limit]


def build_store_from_pack(pack, root: str | Path) -> SemanticConceptStore:
    return SemanticConceptStore.build(root, pack.semantic_graph.get("concepts") or [])
