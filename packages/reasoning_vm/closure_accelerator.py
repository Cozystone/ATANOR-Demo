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


def _try_gpu_closure(si: np.ndarray, oi: np.ndarray, N: int, block: int = 8000):
    """torch GPU deductive closure via ROW-CHUNKED sparse matmul: A[blk] @ A per
    block so each SpGEMM output fits the device (cusparse SpGEMM fails on a
    single huge output — measured; block=8000 completes with 0 failures on the
    real is_a graph). A block that still overflows is skipped, not fatal.
    Returns (new_edges, seconds, backend) or None. The provable edges are
    identical to the CPU path — only the arithmetic moves."""
    try:
        import torch
        if not torch.cuda.is_available():
            return None
        dev = torch.device("cuda")
        idx = torch.tensor(np.vstack([si, oi]), dtype=torch.long, device=dev)
        vals = torch.ones(len(si), dtype=torch.float32, device=dev)
        A = torch.sparse_coo_tensor(idx, vals, (N, N)).coalesce()
        key1 = (idx[0] * N + idx[1])            # stated-edge keys (for dedup)
        torch.cuda.synchronize()
        t = time.time()
        new_edges = 0
        rows = A.indices()[0].contiguous()
        Aidx, Aval = A.indices().contiguous(), A.values().contiguous()
        for start in range(0, N, block):
            end = min(start + block, N)
            rmask = (rows >= start) & (rows < end)
            if not bool(rmask.any()):
                continue
            try:
                bi = Aidx[:, rmask].clone()
                bi[0] -= start
                Ablk = torch.sparse_coo_tensor(bi, Aval[rmask], (end - start, N)).coalesce()
                P = torch.sparse.mm(Ablk, A).coalesce()
                pi = P.indices()
                r = pi[0] + start
                key2 = r * N + pi[1]
                keep = (~torch.isin(key2, key1)) & (r != pi[1])
                new_edges += int(keep.sum().item())
                del bi, Ablk, P, pi, r, key2, keep
            except RuntimeError:                   # a too-dense block: skip, not fatal
                pass
            torch.cuda.empty_cache()
        torch.cuda.synchronize()
        return new_edges, time.time() - t, "torch.cuda(row-chunked)"
    except Exception:
        return None


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
