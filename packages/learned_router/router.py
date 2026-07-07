# -*- coding: utf-8 -*-
"""Learned intent router v0 — LEARNED understanding replacing hand-written regexes.

The macro diagnosis (2026-07-07): 7 of 8 measured chat failures were ROUTING
failures — the knowledge was in the graph, the regex lanes misread the question.
Rules generalize O(1) per fix; a learned classifier generalizes from data.

Architecture (deliberately small, inspectable, No-LLM):
  features  = hashed character 2–4-grams + word unigrams (2^15 dims, L2-normed)
  model     = multiclass logistic regression trained by SGD (pure numpy)
  training  = bootstrap synthesis from slot templates (scripts/train_router.py)
              + every real disagreement the flywheel logs becomes future gold

Precedent: this is the fastText/Watson recipe — linear models over n-grams are
within a few points of deep models for short-text intent classification, at
microsecond latency and full auditability. IBM Watson beat Jeopardy champions
with exactly this class of learned routing over retrieval — no LLM existed.

Deployment contract (soft policy, never a cliff): the regex lanes stay as
high-precision overrides; the learned router runs in SHADOW on every turn
(logged to the flywheel) and is consulted as a decider only where no regex
fires. Quality can only go up, and every disagreement is training data.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import numpy as np

REPO = Path(__file__).resolve().parents[2]
MODEL_DIR = REPO / "data" / "learned_router"
MODEL_PATH = MODEL_DIR / "router_v0.npz"
META_PATH = MODEL_DIR / "router_v0.meta.json"

DIM = 1 << 15  # hashed feature space

_MODEL: dict[str, Any] = {"W": None, "b": None, "classes": None, "mtime": 0.0}


def _hash_features(text: str) -> np.ndarray:
    """Hashed char 2-4 grams + word unigrams, L2-normalized. Deterministic
    (python hash of the SAME string differs across runs — use a stable hash)."""
    x = np.zeros(DIM, dtype=np.float32)
    t = " " + re.sub(r"\s+", " ", (text or "").strip().lower()) + " "
    feats: list[str] = []
    for n in (2, 3, 4):
        feats.extend(t[i:i + n] for i in range(len(t) - n + 1))
    feats.extend(w for w in t.split() if w)
    for f in feats:
        h = 2166136261
        for ch in f.encode("utf-8"):  # FNV-1a: stable across processes
            h = ((h ^ ch) * 16777619) & 0xFFFFFFFF
        x[h % DIM] += 1.0
    norm = float(np.linalg.norm(x))
    return x / norm if norm > 0 else x


def _load() -> bool:
    try:
        if not MODEL_PATH.exists():
            return False
        mtime = MODEL_PATH.stat().st_mtime
        if _MODEL["W"] is None or _MODEL["mtime"] != mtime:
            data = np.load(MODEL_PATH)
            _MODEL["W"], _MODEL["b"] = data["W"], data["b"]
            _MODEL["classes"] = json.loads(META_PATH.read_text(encoding="utf-8"))["classes"]
            _MODEL["mtime"] = mtime
        return True
    except Exception:
        return False


def router_available() -> bool:
    return _load()


def predict(text: str) -> tuple[str, float]:
    """(intent, confidence). ('', 0.0) when no model is trained yet — callers
    treat that as 'no opinion', never as an intent."""
    if not _load():
        return "", 0.0
    x = _hash_features(text)
    z = _MODEL["W"] @ x + _MODEL["b"]
    z = z - z.max()
    p = np.exp(z)
    p /= p.sum()
    i = int(p.argmax())
    return str(_MODEL["classes"][i]), float(p[i])


def train(rows: list[tuple[str, str]], epochs: int = 12, lr: float = 0.5,
          l2: float = 1e-5, seed: int = 7) -> dict[str, Any]:
    """SGD multiclass logistic regression. `rows` = (text, label). Saves the
    model + meta. Returns train/holdout accuracy (10% holdout, honest split)."""
    rng = np.random.default_rng(seed)
    classes = sorted({label for _t, label in rows})
    cidx = {c: i for i, c in enumerate(classes)}
    X = np.stack([_hash_features(t) for t, _l in rows])
    y = np.array([cidx[l] for _t, l in rows])
    n = len(rows)
    order = rng.permutation(n)
    cut = max(1, n // 10)
    hold, tr = order[:cut], order[cut:]
    W = np.zeros((len(classes), DIM), dtype=np.float32)
    b = np.zeros(len(classes), dtype=np.float32)
    for _ep in range(epochs):
        rng.shuffle(tr)
        for i in tr:
            z = W @ X[i] + b
            z -= z.max()
            p = np.exp(z)
            p /= p.sum()
            p[y[i]] -= 1.0  # dL/dz for cross-entropy
            W -= lr * (np.outer(p, X[i]) + l2 * W)
            b -= lr * p
    def _acc(idx: np.ndarray) -> float:
        z = X[idx] @ W.T + b
        return float((z.argmax(axis=1) == y[idx]).mean())
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(MODEL_PATH, W=W, b=b)
    META_PATH.write_text(json.dumps({"classes": classes, "n_train": int(len(tr)),
                                     "n_holdout": int(len(hold))}, ensure_ascii=False),
                         encoding="utf-8")
    _MODEL["W"] = None  # force reload
    return {"classes": len(classes), "train_acc": _acc(tr), "holdout_acc": _acc(hold),
            "n": n}
