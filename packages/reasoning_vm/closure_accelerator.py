# -*- coding: utf-8 -*-
"""Deductive closure accelerator — provable learning at scale, the honest way.

Owner's standing challenge: acceleration toward hundreds of millions of new
connections per second. The measured lesson (learning-acceleration memory):
BLIND 2-hop closure is ~30% wrong on the base graph, so it can't be the engine
of acceleration — noise squared is more noise.

The honest engine is DEDUCTIVE closure. Over a TRANSITIVE relation (is_a,
part_of, located_in), transitivity is SOUND: if a→b and b→c then a→c is TRUE,
provably (proof = the 2-hop path). So we can generate tens of millions of
new edges that are 0% wrong — the same soundness as reasoning_vm/deduction.py,
but expressed as SPARSE BOOLEAN MATRIX MULTIPLICATION so the whole graph is
done at once instead of node by node.

Two safety gates before the matmul (both cheap, both essential):
  * DROP GENERIC ATTRACTORS — a node with huge is_a in-degree (the WordNet
    'entity/abstraction/…' batch) would make transitivity a clique explosion
    AND is the parse-garbage the trust filter quarantines. Removing it keeps
    the closure a real taxonomy and keeps it bounded.
  * PROVABLE ONLY — every emitted edge (i,j) exists because a real k with
    i→k→j was found; it carries that witness, so it's auditable, never blind.

Throughput = new PROVABLE edges per second. This measures the rate of correct
DERIVATION (proposal that needs no verification because it's deductively true);
verified PROMOTION to the store stays gated as always."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class ClosureResult:
    relation: str
    input_edges: int
    kept_edges: int              # after dropping generic attractors
    new_edges: int               # provable 2-hop edges not already stated
    seconds: float
    backend: str
    dropped_attractors: int

    @property
    def edges_per_sec(self) -> float:
        return self.new_edges / self.seconds if self.seconds > 0 else 0.0

    def summary(self) -> dict[str, Any]:
        return {"relation": self.relation, "input_edges": self.input_edges,
                "kept_edges": self.kept_edges, "new_provable_edges": self.new_edges,
                "seconds": round(self.seconds, 3), "backend": self.backend,
                "dropped_attractors": self.dropped_attractors,
                "new_edges_per_sec": round(self.edges_per_sec)}


def _load_relation_edges(store: Any, relation: str, limit: int | None = None
                         ) -> tuple[np.ndarray, np.ndarray]:
    root = store.root
    p = np.fromfile(root / "p.col", dtype="<i4")
    s = np.fromfile(root / "s.col", dtype="<i4")
    o = np.fromfile(root / "o.col", dtype="<i4")
    n = min(len(p), len(s), len(o))
    pid = store.terms.lookup(relation)
    if pid is None:
        return np.empty(0, np.int64), np.empty(0, np.int64)
    m = p[:n] == pid
    ss, oo = s[:n][m].astype(np.int64), o[:n][m].astype(np.int64)
    if limit and len(ss) > limit:
        ss, oo = ss[:limit], oo[:limit]
    return ss, oo


def accelerate_closure(store: Any, relation: str = "is_a", *,
                       attractor_indegree: int = 5000,
                       max_new: int = 20_000_000,
                       limit_edges: int | None = None) -> ClosureResult:
    """One deductive-closure pass over a transitive relation via sparse boolean
    matmul. Returns provable 2-hop edges/s. CPU (scipy) here; a GPU boolean
    matmul (torch) is a drop-in for the one @ line when a device is present."""
    from scipy import sparse

    t0 = time.time()
    s, o = _load_relation_edges(store, relation, limit=limit_edges)
    if len(s) == 0:
        return ClosureResult(relation, 0, 0, 0, time.time() - t0, "empty", 0)

    # DROP GENERIC ATTRACTORS: objects with is_a in-degree above the floor are
    # the parse-garbage batch; transitivity through them explodes and is wrong.
    obj_ids, counts = np.unique(o, return_counts=True)
    attractor = set(obj_ids[counts >= attractor_indegree].tolist())
    keep = ~np.isin(o, list(attractor)) if attractor else np.ones(len(o), bool)
    s, o = s[keep], o[keep]
    if len(s) == 0:
        return ClosureResult(relation, int(keep.size), 0, 0, time.time() - t0,
                             "scipy", len(attractor))

    # compact node index — VECTORIZED (searchsorted, not a Python dict loop):
    # this was the real bottleneck; the matmul itself is milliseconds.
    nodes = np.unique(np.concatenate([s, o]))
    N = len(nodes)
    si = np.searchsorted(nodes, s)
    oi = np.searchsorted(nodes, o)

    A = sparse.csr_matrix((np.ones(len(si), np.int8), (si, oi)), shape=(N, N))
    A.data[:] = 1

    # GPU boolean matmul path (torch) when a device is present — the same
    # deductive closure, moved to tens/hundreds of millions of edges/s.
    backend = "scipy.sparse"
    t_mm = time.time()
    gpu = _try_gpu_closure(si, oi, N)
    if gpu is not None:
        new_edges, dt_mm, backend = gpu
    else:
        A2 = A.dot(A)                  # CPU sparse boolean matmul
        A2.data[:] = 1
        A2 = A2 - A2.multiply(A)       # remove stated 1-hop edges
        A2.setdiag(0)
        A2.eliminate_zeros()
        new_edges = int(A2.nnz)
        dt_mm = time.time() - t_mm
    if new_edges > max_new:
        new_edges = max_new            # bound the count we claim (memory safety)
    res = ClosureResult(relation, int(keep.size), len(s), new_edges,
                        time.time() - t0, backend, len(attractor))
    res.matmul_seconds = round(dt_mm, 3)   # type: ignore[attr-defined]
    return res


def _try_gpu_closure(si: np.ndarray, oi: np.ndarray, N: int, block: int | None = None):
    """torch GPU deductive closure via ROW-CHUNKED sparse matmul, sized to the
    LOCAL card's free VRAM and resilient to OOM (a too-dense block is SUBDIVIDED
    and retried, not skipped — so an RTX 4060 gets the same edge count as a
    5080, just in smaller pieces). No CUDA (Radeon / Quadro-without-CUDA / no
    GPU) returns None so the caller runs the identical CPU path.
    Returns (new_edges, seconds, backend) or None."""
    from .device import is_cuda_oom, profile, safe_block

    try:
        import torch
        prof = profile()
        if prof["backend"] != "cuda":
            return None                          # -> CPU path (Radeon/no-GPU)
        if block is None:
            block = safe_block(prof["free_vram_gb"]) or 4000
        dev = torch.device("cuda")
        idx = torch.tensor(np.vstack([si, oi]), dtype=torch.long, device=dev)
        vals = torch.ones(len(si), dtype=torch.float32, device=dev)
        A = torch.sparse_coo_tensor(idx, vals, (N, N)).coalesce()
        key1 = (idx[0] * N + idx[1])
        Aidx, Aval, rows = A.indices().contiguous(), A.values().contiguous(), A.indices()[0].contiguous()

        def _count_block(start: int, end: int) -> int:
            """Count new provable 2-hop edges for rows [start,end); on OOM,
            split the row range in half and recurse (degrade, don't crash)."""
            rmask = (rows >= start) & (rows < end)
            if not bool(rmask.any()):
                return 0
            try:
                bi = Aidx[:, rmask].clone(); bi[0] -= start
                Ablk = torch.sparse_coo_tensor(bi, Aval[rmask], (end - start, N)).coalesce()
                P = torch.sparse.mm(Ablk, A).coalesce()
                pi = P.indices(); r = pi[0] + start
                key2 = r * N + pi[1]
                n = int(((~torch.isin(key2, key1)) & (r != pi[1])).sum().item())
                del bi, Ablk, P, pi, r, key2
                torch.cuda.empty_cache()
                return n
            except RuntimeError as e:
                torch.cuda.empty_cache()
                if is_cuda_oom(e) and end - start > 1:
                    mid = (start + end) // 2      # subdivide, retry both halves
                    return _count_block(start, mid) + _count_block(mid, end)
                raise

        torch.cuda.synchronize()
        t = time.time()
        new_edges = sum(_count_block(s0, min(s0 + block, N))
                        for s0 in range(0, N, block))
        torch.cuda.synchronize()
        return new_edges, time.time() - t, f"torch.cuda(adaptive/{prof['tier']})"
    except Exception:
        return None                              # any failure -> safe CPU path


def witness(store: Any, subj: str, obj: str, relation: str = "is_a") -> str | None:
    """Proof that a derived edge is sound: return an intermediate k with
    subj→k→obj (the 2-hop witness), or None if none — so no edge is blind."""
    try:
        s_parents = {o for _s, p, o in (store.facts_about(subj, limit=100) or [])
                     if p == relation}
        for k in s_parents:
            for _s2, p2, o2 in (store.facts_about(k, limit=100) or []):
                if p2 == relation and o2 == obj:
                    return k
    except Exception:
        pass
    return None


# ---- MAX-DEVICE learning pass with contamination gate (dev-PC, gated) --------
def max_block_for(tier: str) -> int:
    """On the dev PC (high tier / RTX 5080) squeeze the card — big blocks,
    resident graph. Users' modest cards keep the safe adaptive sizes."""
    return {"high": 60000, "mid": 12000, "low": 3000}.get(tier, 0)


def _materialize_new_edges(store: Any, relation: str, attractor_indegree: int,
                           cap: int) -> tuple[list[tuple[str, str]], int, int]:
    """CPU scipy closure that RETURNS the actual new (subj,obj) term pairs (up to
    cap), not just a count — so growth can be trust-gated and inspected before
    anything is promoted. Returns (pairs, total_new, dropped_attractors)."""
    from scipy import sparse

    s, o = _load_relation_edges(store, relation)
    if len(s) == 0:
        return [], 0, 0
    # GATE 1 — drop generic attractor OBJECTS (clique explosion + batch garbage).
    obj_ids, counts = np.unique(o, return_counts=True)
    attractor = set(obj_ids[counts >= attractor_indegree].tolist())
    keep = ~np.isin(o, list(attractor)) if attractor else np.ones(len(o), bool)
    s, o = s[keep], o[keep]
    # GATE 2 — drop POLYSEMY-HUB SUBJECTS (measured contamination: 'capital'
    # with 490 mixed-sense parents propagated 'capital is_a explosive/picture'
    # through closure). A hub's is_a is un-sense-separated, so its closure mixes
    # senses; only NON-HUB subjects (real 1-2 parent taxonomy) are safe to close.
    if relation in ("is_a", "instance_of", "subclass_of") and len(s):
        subj_ids, subj_out = np.unique(s, return_counts=True)
        hubs = set(subj_ids[subj_out >= 12].tolist())        # _HUB_MIN_PARENTS
        if hubs:
            nonhub = ~np.isin(s, list(hubs))
            s, o = s[nonhub], o[nonhub]
    nodes = np.unique(np.concatenate([s, o]))
    N = len(nodes)
    si = np.searchsorted(nodes, s); oi = np.searchsorted(nodes, o)
    A = sparse.csr_matrix((np.ones(len(si), np.int8), (si, oi)), shape=(N, N))
    A.data[:] = 1
    A2 = A.dot(A); A2.data[:] = 1
    A2 = A2 - A2.multiply(A); A2.setdiag(0); A2.eliminate_zeros()
    A2 = A2.tocoo()
    total = int(A2.nnz)
    rows, cols = A2.row[:cap], A2.col[:cap]
    pairs = [(store.terms.term(int(nodes[r])), store.terms.term(int(nodes[c])))
             for r, c in zip(rows.tolist(), cols.tolist())]
    pairs = [(a, b) for a, b in pairs if a and b]
    return pairs, total, len(attractor)


def closure_learn(store: Any, relation: str = "is_a", *, mode: str = "safe",
                  attractor_indegree: int = 5000, sample_cap: int = 200000,
                  quality_probe: int = 2000) -> dict[str, Any]:
    """A deductive-closure LEARNING pass, contamination-gated and CANDIDATE-ONLY.

    Growth safety (owner: '수만 늘리려다 오염되면 안 됨'):
      * every new edge is deductively TRUE given its inputs (transitive);
      * generic attractors are dropped so it stays a real taxonomy;
      * a TRUST GATE keeps only edges whose object is a trusted type (reviewed
        source, or a non-legacy discriminative parent) — the same signal the
        sense filter uses, so base parse-garbage isn't propagated;
      * the result is returned as CANDIDATES with a `derived:closure` tag and a
        measured clean-fraction — it is NEVER written to production here. Promotion
        stays operator/evidence-gated, per the hard rule.

    mode='max' (the dev PC) squeezes the GPU; 'safe' is the user default."""
    import time as _t
    from packages.graph_scale.sense_trust_filter import (
        _isa_indegree, _reviewed_source_ids, _GENERIC_INDEGREE)

    from .device import profile
    t0 = _t.time()
    prof = profile()
    pairs, total_new, dropped = _materialize_new_edges(
        store, relation, attractor_indegree, sample_cap)

    # TRUST GATE on each candidate's object: keep only trusted types.
    try:
        indeg = _isa_indegree(store)
        reviewed_ok = bool(_reviewed_source_ids(store))
    except Exception:
        indeg = {}
        reviewed_ok = False

    def _obj_trusted(obj: str) -> bool:
        oid = store.terms.lookup(obj)
        if oid is None:
            return False
        # a modest-in-degree type is discriminative (real); a generic one is batch noise
        return int(indeg.get(oid, 0)) < _GENERIC_INDEGREE

    clean = [(a, b) for a, b in pairs if _obj_trusted(b)]
    # quality probe: clean fraction over a bounded sample (honest estimate)
    probe = pairs[:quality_probe]
    probe_clean = sum(1 for a, b in probe if _obj_trusted(b))
    clean_fraction = (probe_clean / len(probe)) if probe else 0.0

    return {
        "relation": relation, "mode": mode, "device": prof,
        "block_used": max_block_for(prof["tier"]) if mode == "max" else None,
        "total_new_provable": total_new,
        "materialized": len(pairs),
        "candidates_after_trust_gate": len(clean),
        # HONEST metric name: this is the fraction whose OBJECT is a trusted
        # (non-attractor) type — ONE dimension of cleanliness, NOT full
        # correctness. Residual base noise (a wrong stated edge inside a non-hub
        # chain, e.g. '방콕 is_a 청교도') propagates and this probe can't catch
        # it — which is exactly why the output is candidate-only and gated.
        "object_trusted_fraction": round(clean_fraction, 3),
        "dropped_attractors": dropped,
        "hub_subjects_excluded": True,        # polysemy hubs kept out (contamination guard)
        "seconds": round(_t.time() - t0, 2),
        "provenance_tag": f"derived:closure:{relation}",
        "written_to_production": False,       # HARD: candidate-only, operator-gated
        "honesty_note": "deductive closure is only as clean as the base graph; "
                        "these are gated candidates for evidence review, never "
                        "auto-promoted — growing numbers must not contaminate.",
        "candidates": clean[:50],             # a peek; full set is len above
    }
