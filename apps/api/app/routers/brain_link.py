"""Brain Link — a REAL peer-to-peer shared-compute pool.

The core Brain Link idea: instead of one machine carrying the whole learning
workload, many users' PCs pool their compute. This coordinator holds a backlog
of LEARNING WORK — batches of sentences that need concept/relation extraction
(the CPU-heavy "이해" step). Peers (other PCs / containers) REGISTER, CLAIM a
batch, run the extraction with *their own* compute, and SUBMIT the results, which
are merged into the shared brain.

Honesty: nothing is simulated. A peer's contribution only counts when it returns
real extracted concepts/relations; the shared totals grow solely from work peers
actually did. Idle peers contribute nothing. This is genuine distributed compute.
"""

from __future__ import annotations

import json
import os
import threading
import time as _time
import uuid
from collections import deque
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body

router = APIRouter(prefix="/api/brain-link", tags=["brain-link"])

_LOCK = threading.RLock()
_DATA_DIR = Path(__file__).resolve().parents[4] / "data" / "brain_link"
_CONTRIB_LOG = _DATA_DIR / "contributions.jsonl"

# In-memory pool state. Persisted contributions go to _CONTRIB_LOG.
_POOL: dict[str, Any] = {
    "queue": deque(),                 # sentences awaiting extraction
    "inflight": {},                   # batch_id -> {peer_id, sentences, claimed_at}
    "peers": {},                      # peer_id -> {label, registered_at, last_seen, claimed, completed}
    "seeded": False,
    "batches_completed": 0,
    "concepts": set(),                # unique concepts contributed across the pool
    "relations": set(),               # unique relations (a||b)
    "by_peer": {},                    # peer_id -> {concepts, relations, batches}
    "started_at": _time.time(),
}
_RECLAIM_AFTER = 120.0                 # re-queue a batch if a peer never submits

# Peers grow a DEDICATED candidate store (separate from the live loop's store so
# concurrent peer writes never race the running engine). The merge is a PERSISTENT,
# hash-SHARDED store (packages/brain_link_pool): its dedupe index is loaded ONCE
# per shard, not rebuilt per submit, and each shard's index stays ~1/K the size as
# the DB grows to millions — so throughput does NOT collapse as the brain gets big
# (the old construct-a-VerifiedStore-per-submit path paid O(n) reload EVERY submit,
# ~50ms at 20k rows, ~500ms at 200k -> a hard scaling wall). Honest: this removes
# the merge's growth-with-size wall; extraction stays parallel across peers. Going
# beyond one core's merge rate needs process-based shard workers (future).
_STORE_LOCK = threading.RLock()
_CONTRIB_STORE_ROOT_SHARDED = _DATA_DIR / "contributed_store_sharded"
_STORE_TOTALS = {"concepts_added": 0, "relations_added": 0, "ready": False}

_SHARDED_STORE: Any = None
_SHARDED_STORE_LOCK = threading.Lock()


def _get_sharded_store() -> Any:
    """Lazily build the process-lifetime sharded contributed store (singleton)."""
    global _SHARDED_STORE
    if _SHARDED_STORE is None:
        with _SHARDED_STORE_LOCK:
            if _SHARDED_STORE is None:
                from packages.brain_link_pool import ShardedContributedStore

                # DEFAULT 1 shard = EXACT de-dup (one global dedupe set) + the full
                # persistence win (index loaded once, not per submit). Measured:
                # shards>1 route whole decompositions by source, so the SAME concept
                # from different sentences lands in different shards and is counted
                # once PER shard -> up to K x concept inflation (benchmark: 8 shards
                # = 8x). Threaded shards also give ZERO speedup (GIL). So >1 is an
                # opt-in knob, only worthwhile with PROCESS workers + concept-key
                # routing (future); until then keep exact de-dup.
                try:
                    shards = max(1, int(os.getenv("ATANOR_CONTRIB_SHARDS", "1")))
                except Exception:
                    shards = 1
                _CONTRIB_STORE_ROOT_SHARDED.parent.mkdir(parents=True, exist_ok=True)
                _SHARDED_STORE = ShardedContributedStore(_CONTRIB_STORE_ROOT_SHARDED, shards=shards)
    return _SHARDED_STORE


def _accumulate_decompositions(decomps: list[dict[str, Any]]) -> tuple[int, int]:
    """Merge peer-extracted neuro-symbolic decompositions into the shared
    contributed store. The expensive decompose ran on the peers (distributed);
    this serialized append is cheap. Returns (concepts_added, relations_added)."""
    if not decomps:
        return 0, 0
    try:
        from packages.cgsr.cgsr.ingestion.decomposer import DecompositionResult
    except Exception:
        return 0, 0
    drs = []
    for d in decomps:
        try:
            drs.append(DecompositionResult(
                concepts=list(d.get("concepts") or []),
                relations=list(d.get("relations") or []),
                case_frames=list(d.get("case_frames") or []),
                evidence=d.get("evidence"),
            ))
        except Exception:
            continue
    if not drs:
        return 0, 0
    try:
        # Persistent sharded merge: no per-submit index reload, K-way shard locks
        # (not one global lock) so parallel peer submits don't all serialize.
        agg = _get_sharded_store().accumulate(drs)
    except Exception:
        return 0, 0
    c = int(agg.get("concepts_added", 0) or 0)
    r = int(agg.get("relations_added", 0) or 0)
    with _STORE_LOCK:
        _STORE_TOTALS["concepts_added"] += c
        _STORE_TOTALS["relations_added"] += r
        _STORE_TOTALS["ready"] = True
    return c, r


def _seed_queue() -> None:
    """Fill the work queue with real public sentences (same source as the
    firehose: seed corpus + any corpora dir). Lazily, on first need."""
    if _POOL["seeded"] and _POOL["queue"]:
        return
    sentences: list[str] = []
    cap = 20000
    # 1) firehose corpora (seed + plugin + ATANOR_CORPORA_DIR)
    try:
        from app.routers.cloud_brain import _firehose_corpus_files, _firehose_iter_sentences
        for f in _firehose_corpus_files():
            for s in _firehose_iter_sentences(f):
                sentences.append(s)
                if len(sentences) >= cap:
                    break
            if len(sentences) >= cap:
                break
    except Exception:
        pass
    # 2) the candidate store's real source sentences (evidence.jsonl) — thousands
    #    of genuine public-corpus sentences, so a multi-peer pool has real work.
    try:
        from app.routers.cloud_brain import _resolve_candidate_store_path
        store = _resolve_candidate_store_path()
        ev = Path(store) / "evidence.jsonl" if store else None
        if ev and ev.exists() and len(sentences) < cap:
            with ev.open("r", encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    txt = str(obj.get("text") or obj.get("sentence") or obj.get("source_sentence") or "").strip()
                    if 12 <= len(txt) <= 2000:
                        sentences.append(txt)
                        if len(sentences) >= cap:
                            break
    except Exception:
        pass
    if not sentences:
        sentences = [
            "Brain Link pools compute across peer machines.",
            "A peer claims a batch, extracts concepts, and submits results.",
            "공유 자원으로 연산력을 보강한다.",
        ]
    with _LOCK:
        for s in sentences:
            _POOL["queue"].append(s)
        _POOL["seeded"] = True


def _reclaim_stale() -> None:
    now = _time.time()
    with _LOCK:
        stale = [bid for bid, b in _POOL["inflight"].items() if now - b["claimed_at"] > _RECLAIM_AFTER]
        for bid in stale:
            b = _POOL["inflight"].pop(bid)
            for s in b["sentences"]:
                _POOL["queue"].appendleft(s)


@router.post("/peer/register")
def peer_register(body: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    peer_id = str(body.get("peer_id") or f"peer-{uuid.uuid4().hex[:8]}")
    label = str(body.get("label") or peer_id)
    now = _time.time()
    with _LOCK:
        existing = _POOL["peers"].get(peer_id, {})
        _POOL["peers"][peer_id] = {
            "label": label,
            "registered_at": existing.get("registered_at", now),
            "last_seen": now,
            "claimed": existing.get("claimed", 0),
            "completed": existing.get("completed", 0),
        }
        _POOL["by_peer"].setdefault(peer_id, {"concepts": 0, "relations": 0, "batches": 0})
    _seed_queue()
    return {"ok": True, "peer_id": peer_id, "label": label}


@router.get("/work/claim")
def work_claim(peer_id: str, n: int = 25) -> dict[str, Any]:
    _seed_queue()
    _reclaim_stale()
    n = max(1, min(200, n))
    with _LOCK:
        if peer_id not in _POOL["peers"]:
            return {"batch_id": None, "sentences": [], "reason": "register_first"}
        batch: list[str] = []
        while _POOL["queue"] and len(batch) < n:
            batch.append(_POOL["queue"].popleft())
        if not batch:
            return {"batch_id": None, "sentences": [], "reason": "no_work"}
        batch_id = uuid.uuid4().hex[:12]
        _POOL["inflight"][batch_id] = {"peer_id": peer_id, "sentences": batch, "claimed_at": _time.time()}
        _POOL["peers"][peer_id]["claimed"] += 1
        _POOL["peers"][peer_id]["last_seen"] = _time.time()
    return {"batch_id": batch_id, "sentences": batch}


@router.post("/work/submit")
def work_submit(body: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    peer_id = str(body.get("peer_id") or "")
    batch_id = str(body.get("batch_id") or "")
    decomps = body.get("decompositions") or []
    with _LOCK:
        b = _POOL["inflight"].pop(batch_id, None)
        if b is None or b["peer_id"] != peer_id:
            return {"ok": False, "reason": "unknown_or_foreign_batch"}
    # Merge the peer's neuro-symbolic decompositions into the shared store — the
    # brain actually GROWS from distributed peer compute.
    added_c, added_r = _accumulate_decompositions(decomps)
    with _LOCK:
        _POOL["batches_completed"] += 1
        p = _POOL["peers"].setdefault(peer_id, {"completed": 0, "claimed": 0})
        p["completed"] = p.get("completed", 0) + 1
        p["last_seen"] = _time.time()
        bp = _POOL["by_peer"].setdefault(peer_id, {"concepts": 0, "relations": 0, "batches": 0})
        bp["concepts"] += added_c
        bp["relations"] += added_r
        bp["batches"] += 1
    try:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        with _CONTRIB_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "at": _time.strftime("%Y-%m-%dT%H:%M:%S"), "peer_id": peer_id, "batch_id": batch_id,
                "store_concepts_added": added_c, "store_relations_added": added_r,
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return {"ok": True, "store_concepts_added": added_c, "store_relations_added": added_r,
            "store_concepts_total": _STORE_TOTALS["concepts_added"],
            "store_relations_total": _STORE_TOTALS["relations_added"]}


@router.get("/pool/status")
def pool_status() -> dict[str, Any]:
    _reclaim_stale()
    now = _time.time()
    merge: dict[str, Any] | None = None
    if _SHARDED_STORE is not None:
        try:
            merge = _SHARDED_STORE.status()
        except Exception:
            merge = None
    with _LOCK:
        peers = [{
            "peer_id": pid, "label": p.get("label", pid),
            "online": (now - p.get("last_seen", 0)) < 30,
            "claimed": p.get("claimed", 0), "completed": p.get("completed", 0),
            "concepts": _POOL["by_peer"].get(pid, {}).get("concepts", 0),
            "relations": _POOL["by_peer"].get(pid, {}).get("relations", 0),
        } for pid, p in _POOL["peers"].items()]
        return {
            "peers": peers,
            "peer_count": len(peers),
            "online_peers": sum(1 for p in peers if p["online"]),
            "queue_remaining": len(_POOL["queue"]),
            "inflight": len(_POOL["inflight"]),
            "batches_completed": _POOL["batches_completed"],
            "store_concepts_total": _STORE_TOTALS["concepts_added"],
            "store_relations_total": _STORE_TOTALS["relations_added"],
            "uptime_seconds": round(now - _POOL["started_at"], 1),
            "architecture": "p2p_shared_compute_pool",
            # The merge engine that absorbs peer output (persistent + sharded).
            "merge_engine": merge,
        }
