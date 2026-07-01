"""Holographic associative language substrate — generalizing, coherent generation, No-LLM.

The v0 phase-context (see ``phase_context.py``) only BUNDLES emitted tokens into one state, so
it has no notion of role/order and generalizes weakly. This module adds the missing half —
BINDING — via a Fourier Holographic Reduced Representation (FHRR), the graph-native answer to the
two ceilings a count-based n-gram graph hits (no generalization to unseen combinations; no
long-range context).

How it works
------------
- Each symbol s → a unit-phasor vector φ(s) ∈ (unit ℂ)^D, phases fixed by a per-symbol hash seed
  (deterministic, reproducible, no LLM, no training).
- BIND (role⊛filler) = element-wise phasor product = phase ADDITION (the FHRR bind; unitary,
  invertible). We bind each context token to a fixed positional role, so order is preserved:
  "a b" ≠ "b a".
- BUNDLE = sum. A context window becomes one vector: Σ_j decay^j · bind(role_j, φ(token_j)).
  This single vector holds the WHOLE window at once → long-range coherence.
- For each successor token we bundle every context that preceded it into a PROTOTYPE vector.
  Prediction resonates the current context against each prototype: score(t) = Re⟨q, proto_t⟩/‖·‖.

Why it GENERALIZES (the point n-grams miss): resonance is a smooth similarity. A context never
seen verbatim still resonates with the prototypes whose stored contexts SHARE sub-structure with
it — so an unseen combination predicts a plausible next unit, and a WIDER context disambiguates
where a last-token bigram cannot. Capacity/crosstalk is bounded by D; grows gracefully with the
corpus (the density thesis, made mechanical).

Deterministic (seeded), no external model, no backprop, no gradient. A ``fabricated_facts``
guarantee holds because generation only emits units that occurred in the grounding corpus.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict

import numpy as np

_WORD = re.compile(r"[0-9A-Za-z가-힣]+")


def tokens(text: str) -> list[str]:
    return _WORD.findall(str(text or ""))


class HoloSpace:
    """Fixed unit-phasor vector per symbol (FHRR atom). Deterministic per-symbol hash seed."""

    def __init__(self, *, dim: int = 1024, seed: int = 7) -> None:
        self.dim = int(dim)
        self.seed = int(seed)
        self._v: dict[str, np.ndarray] = {}

    def vec(self, symbol: str) -> np.ndarray:
        v = self._v.get(symbol)
        if v is None:
            h = int.from_bytes(hashlib.blake2b(str(symbol).encode("utf-8"), digest_size=8).digest(), "big")
            rng = np.random.default_rng((h ^ (self.seed * 0x9E3779B97F4A7C15)) & ((1 << 64) - 1))
            v = np.exp(1j * rng.uniform(0.0, 2.0 * np.pi, self.dim))
            self._v[symbol] = v
        return v

    @staticmethod
    def bind(a: np.ndarray, b: np.ndarray) -> np.ndarray:
        return a * b  # phase addition — unitary FHRR bind

    @staticmethod
    def unbind(c: np.ndarray, a: np.ndarray) -> np.ndarray:
        return c * np.conj(a)  # phase subtraction — invert the bind


def resonance(q: np.ndarray, r: np.ndarray) -> float:
    """Normalized phase interference in [-1, 1] — the same physics as the fold core
    (Re⟨q,r⟩ = Σ re_i re_j + im_i im_j)."""
    nq = float(np.linalg.norm(q))
    nr = float(np.linalg.norm(r))
    if nq == 0.0 or nr == 0.0:
        return 0.0
    return float(np.real(np.vdot(q, r)) / (nq * nr))


class HolographicLM:
    """A holographic associative n-gram: window-context prototypes + resonance retrieval."""

    def __init__(
        self,
        *,
        dim: int = 1024,
        window: int = 3,
        decay: float = 0.7,
        seed: int = 7,
        semantic: bool = False,
        cooc_window: int = 3,
        bandwidth: float = 3.0,
    ) -> None:
        self.space = HoloSpace(dim=dim, seed=seed)
        self.window = int(window)
        self.decay = float(decay)
        self.semantic = bool(semantic)
        self.cooc_window = int(cooc_window)
        self.bandwidth = float(bandwidth)
        self._roles = [self.space.vec(f"__role_pos_{j}__") for j in range(self.window)]
        self._filler_vec: dict[str, np.ndarray] = {}  # distributional fillers (semantic mode)
        self._proto: dict[str, np.ndarray] = {}      # successor → bundled context phasor
        self._count: Counter[str] = Counter()
        self._bigram: dict[str, Counter[str]] = defaultdict(Counter)  # last-token baseline

    def _filler(self, token: str) -> np.ndarray:
        """The vector a token contributes as a bound FILLER. Random by default; in semantic
        mode it is a distributional phasor, so co-occurrence-similar tokens resonate (dog≈cat)."""
        v = self._filler_vec.get(token)
        return v if v is not None else self.space.vec(token)

    def _build_distributional_base(self, corpus: list[str] | tuple[str, ...]) -> None:
        """Random Fourier Features of the IDF-weighted co-occurrence embedding: φ(s) = exp(i·E_s·R).
        By Bochner, resonance(φ(a),φ(b)) ≈ exp(−‖E_a−E_b‖²/2) — an RBF kernel over distributional
        embeddings, so similar-context tokens have graded resonance and dissimilar ones ≈ 0.
        Deterministic (seeded), no training. Roles stay random for clean role separation."""
        cooc: dict[str, Counter[str]] = defaultdict(Counter)
        vocab: list[str] = []
        seen: set[str] = set()
        for line in corpus:
            toks = tokens(line)
            for t in toks:
                if t not in seen:
                    seen.add(t)
                    vocab.append(t)
            for i, left in enumerate(toks):
                lo = max(0, i - self.cooc_window)
                hi = min(len(toks), i + self.cooc_window + 1)
                for j in range(lo, hi):
                    if j != i:
                        cooc[left][toks[j]] += 1
        index = {t: k for k, t in enumerate(vocab)}
        v = len(vocab)
        if v == 0:
            return
        df: Counter[str] = Counter()
        for t in vocab:
            for ctx in cooc[t]:
                df[ctx] += 1
        idf = np.array([np.log((1.0 + v) / (1.0 + df.get(t, 0))) + 1.0 for t in vocab], dtype=np.float64)
        emb = np.zeros((v, v), dtype=np.float64)
        for t in vocab:
            row = emb[index[t]]
            for ctx, c in cooc[t].items():
                row[index[ctx]] = c * idf[index[ctx]]
            n = np.linalg.norm(row)
            if n > 0:
                row /= n
        rng = np.random.default_rng(self.space.seed ^ 0x5DEECE66D)
        proj = self.bandwidth * rng.standard_normal((v, self.space.dim))
        theta = emb @ proj  # (v, dim)
        phasors = np.exp(1j * theta)
        self._filler_vec = {t: phasors[index[t]] for t in vocab}

    def encode_context(self, ctx_tokens: list[str]) -> np.ndarray:
        """Bundle the recent window into one phasor: newest token bound to role 0."""
        acc = np.zeros(self.space.dim, dtype=np.complex128)
        recent = ctx_tokens[-self.window:]
        for j, tok in enumerate(reversed(recent)):  # j = 0 is the newest token
            acc = acc + (self.decay ** j) * self.space.bind(self._roles[j], self._filler(tok))
        return acc

    def fit(self, corpus: list[str] | tuple[str, ...]) -> "HolographicLM":
        if self.semantic:
            self._build_distributional_base(corpus)
        for line in corpus:
            toks = tokens(line)
            for i in range(1, len(toks)):
                nxt = toks[i]
                ctx = toks[max(0, i - self.window):i]
                cvec = self.encode_context(ctx)
                prev = self._proto.get(nxt)
                self._proto[nxt] = cvec if prev is None else prev + cvec
                self._count[nxt] += 1
                self._bigram[toks[i - 1]][nxt] += 1
        return self

    def predict(self, ctx_tokens: list[str], *, candidates: list[str] | None = None) -> dict[str, float]:
        """Resonance score per candidate successor for the given context."""
        q = self.encode_context(ctx_tokens)
        pool = candidates if candidates is not None else list(self._proto)
        return {t: resonance(q, self._proto[t]) for t in pool if t in self._proto}

    def predict_bigram(self, ctx_tokens: list[str]) -> dict[str, float]:
        """Baseline: last-token transition frequencies (what the walk uses today)."""
        if not ctx_tokens:
            return {}
        counts = self._bigram.get(ctx_tokens[-1], {})
        total = sum(counts.values()) or 1
        return {t: v / total for t, v in counts.items()}

    def top(self, ctx_tokens: list[str], *, candidates: list[str] | None = None) -> str | None:
        scores = self.predict(ctx_tokens, candidates=candidates)
        if not scores:
            return None
        best = max(scores, key=scores.get)
        return best if scores[best] > 0.0 else None

    def generate(self, seed: str | list[str], *, length: int = 8, candidates: list[str] | None = None) -> list[str]:
        out = tokens(seed if isinstance(seed, str) else " ".join(seed))
        for _ in range(max(0, length)):
            nxt = self.top(out, candidates=candidates)
            if nxt is None:
                break
            out.append(nxt)
        return out
