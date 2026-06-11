from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in re.findall(r"[A-Za-z가-힣][A-Za-z0-9가-힣_-]{1,}", text)]


def _load_json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def query_graphrag(
    query: str,
    cleaned_dir: str = "data/cleaned",
    ontology_dir: str = "data/ontology",
) -> dict:
    query_tokens = Counter(_tokens(query))
    docs = []
    root = Path(cleaned_dir)
    root.mkdir(parents=True, exist_ok=True)
    for path in sorted([*root.rglob("*.txt"), *root.rglob("*.md")]):
        text = path.read_text(encoding="utf-8", errors="ignore")
        doc_tokens = Counter(_tokens(text))
        overlap = sum(min(query_tokens[t], doc_tokens[t]) for t in query_tokens)
        density = overlap / max(1, len(query_tokens))
        score = density + math.log(1 + len(doc_tokens)) / 100
        if score > 0:
            docs.append({"doc_id": path.stem, "path": str(path), "score": round(score, 4), "snippet": text[:260]})
    docs.sort(key=lambda item: (-item["score"], item["doc_id"]))

    ontology_root = Path(ontology_dir)
    nodes = _load_json(ontology_root / "nodes.json", [])
    edges = _load_json(ontology_root / "edges.json", [])
    matched_nodes = [
        node for node in nodes
        if any(token in node["label"].lower() for token in query_tokens)
    ][:12]
    matched_ids = {node["id"] for node in matched_nodes}
    matched_edges = [
        edge for edge in edges
        if edge["source"] in matched_ids or edge["target"] in matched_ids
    ][:12]
    graph_paths = [
        [edge["source"], edge["relation"], edge["target"]]
        for edge in matched_edges[:6]
    ]
    confidence = round(min(0.98, 0.25 + len(docs[:5]) * 0.1 + len(matched_nodes) * 0.04 + len(matched_edges) * 0.03), 2)
    return {
        "query": query,
        "matched_nodes": matched_nodes,
        "matched_edges": matched_edges,
        "evidence_docs": docs[:5],
        "graph_paths": graph_paths,
        "confidence": confidence,
    }
