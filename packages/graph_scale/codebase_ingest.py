# -*- coding: utf-8 -*-
"""Codebase self-knowledge — ATANOR learns its OWN source tree as a graph.

Owner (2026-07-09): "얘 코드베이스 학습했었니? 나중에 이것도 가르치자." Honest
answer was no — it read books and the web, but never ingested its own code. This
is the prerequisite for the collective code-improvement loop to be MEANINGFUL: an
agent can only propose a good diff to code it understands.

AST-based, No-LLM: every .py under packages/ becomes structural triples —
  module   is_a          python_module
  module   has_function  fn / has_class cls
  fn       in_module     module        / documented_as <docstring first line>
  fn       calls         other_fn       (from Call nodes in its body)
  class    has_method    method
So ATANOR can answer 'what does surgeon.py do', 'what calls trust_score', 'which
module owns _clean_edges'. Candidate-tier, local, gated — self-knowledge is not
auto-promoted, and it never rewrites code (that stays the human-gated self-mod).

Honest scope: this is STRUCTURE (who calls whom, what's documented), not deep
semantics of what the code MEANS — that needs the richer extractor, a next step.
"""
from __future__ import annotations

import ast
import json
import time
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
LEDGER = REPO / "data" / "graph_scale" / "codebase_knowledge.jsonl"


def _module_name(path: Path, root: Path) -> str:
    rel = path.relative_to(root).with_suffix("")
    return ".".join(rel.parts)


def _calls_in(node: ast.AST) -> set[str]:
    out: set[str] = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Name):
                out.add(f.id)
            elif isinstance(f, ast.Attribute):
                out.add(f.attr)
    return out


def _triples_for_file(path: Path, root: Path) -> list[tuple[str, str, str]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return []
    mod = _module_name(path, root)
    out: list[tuple[str, str, str]] = [(mod, "is_a", "python_module")]
    for node in tree.body:                      # top-level only (functions/classes)
        if isinstance(node, ast.FunctionDef):
            out.append((mod, "has_function", node.name))
            out.append((node.name, "in_module", mod))
            doc = (ast.get_docstring(node) or "").strip().split("\n")[0][:120]
            if doc:
                out.append((node.name, "documented_as", doc))
            for callee in _calls_in(node):
                if callee != node.name and 2 <= len(callee) <= 40:
                    out.append((node.name, "calls", callee))
        elif isinstance(node, ast.ClassDef):
            out.append((mod, "has_class", node.name))
            out.append((node.name, "in_module", mod))
            for m in node.body:
                if isinstance(m, ast.FunctionDef):
                    out.append((node.name, "has_method", m.name))
    return out


def ingest_codebase(root: str | Path | None = None, *, subdir: str = "packages",
                    out: str | Path | None = None, skip_tests: bool = True) -> dict[str, Any]:
    """Walk the source tree and write structural self-knowledge triples to the
    candidate ledger. Local, gated — never auto-promoted, never rewrites code."""
    base = Path(root) if root else REPO
    scan = base / subdir
    out_path = Path(out) if out else LEDGER
    out_path.parent.mkdir(parents=True, exist_ok=True)
    files = [p for p in scan.rglob("*.py")
             if "__pycache__" not in p.parts and not (skip_tests and (
                 p.name.startswith("test_") or "tests" in p.parts))]
    triples: list[tuple[str, str, str]] = []
    for p in files:
        triples.extend(_triples_for_file(p, base))
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    seen: set[tuple[str, str, str]] = set()
    n_by_pred: dict[str, int] = {}
    with out_path.open("w", encoding="utf-8") as fh:
        for s, p, o in triples:
            if (s, p, o) in seen:
                continue
            seen.add((s, p, o))
            n_by_pred[p] = n_by_pred.get(p, 0) + 1
            fh.write(json.dumps({"s": s, "p": p, "o": o, "src": "codebase:ast",
                                 "tier": "candidate", "at": now}, ensure_ascii=False) + "\n")
    return {"files": len(files), "triples": len(seen), "by_predicate": n_by_pred,
            "modules": n_by_pred.get("is_a", 0), "functions": n_by_pred.get("has_function", 0),
            "classes": n_by_pred.get("has_class", 0), "calls": n_by_pred.get("calls", 0),
            "ledger": str(out_path), "written_to_production": False,
            "note": "structural self-knowledge (AST) — candidate-tier, local; not code MEANING"}


def _rows() -> list[dict[str, Any]]:
    if not LEDGER.exists():
        return []
    out = []
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def about(name: str, limit: int = 20) -> dict[str, Any]:
    """What the self-knowledge graph holds about a module / function / class."""
    subj, obj = [], []
    for r in _rows():
        if r.get("s") == name and len(subj) < limit:
            subj.append({"predicate": r["p"], "object": r["o"]})
        elif r.get("o") == name and len(obj) < limit:
            obj.append({"subject": r["s"], "predicate": r["p"]})
    return {"name": name, "is": subj, "referenced_by": obj,
            "known": bool(subj or obj)}
