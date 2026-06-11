from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any


def _tokens(text: str) -> list[str]:
    tokens: list[str] = []
    current: list[str] = []
    for char in text.lower():
        if char.isalnum() or char in {"-", "_"}:
            current.append(char)
        elif current:
            token = "".join(current).strip("-_")
            if token:
                tokens.append(token)
            current = []
    if current:
        token = "".join(current).strip("-_")
        if token:
            tokens.append(token)
    return [token for token in tokens if len(token) > 1 or token.isdigit()]


def _load_json(path: Path, default: Any) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _sentences(text: str) -> list[str]:
    chunks = re.split(r"(?<=[.!?。！？])\s+|\n+", text.strip())
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def _chunk_text(text: str, max_tokens: int = 90, overlap_sentences: int = 1) -> list[str]:
    sentences = _sentences(text)
    if not sentences:
        return []

    chunks: list[str] = []
    window: list[str] = []
    window_tokens = 0
    for sentence in sentences:
        sentence_tokens = len(_tokens(sentence))
        if window and window_tokens + sentence_tokens > max_tokens:
            chunks.append(" ".join(window))
            window = window[-overlap_sentences:] if overlap_sentences else []
            window_tokens = sum(len(_tokens(item)) for item in window)
        window.append(sentence)
        window_tokens += sentence_tokens
    if window:
        chunks.append(" ".join(window))
    return chunks


def _load_doc_chunks(root: Path) -> list[dict[str, Any]]:
    root.mkdir(parents=True, exist_ok=True)
    chunks: list[dict[str, Any]] = []
    for path in sorted([*root.rglob("*.txt"), *root.rglob("*.md")]):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for index, chunk in enumerate(_chunk_text(text) or [text[:900]]):
            token_counts = Counter(_tokens(chunk))
            if not token_counts:
                continue
            chunks.append(
                {
                    "doc_id": path.stem,
                    "chunk_id": f"{path.stem}#{index + 1}",
                    "path": str(path),
                    "text": chunk,
                    "tokens": token_counts,
                    "token_total": sum(token_counts.values()),
                }
            )
    return chunks


def _idf(chunks: list[dict[str, Any]]) -> dict[str, float]:
    doc_frequency: Counter[str] = Counter()
    for chunk in chunks:
        doc_frequency.update(chunk["tokens"].keys())
    total = max(1, len(chunks))
    return {
        token: math.log((total + 1) / (frequency + 0.5)) + 1
        for token, frequency in doc_frequency.items()
    }


def _node_score(node: dict[str, Any], query_terms: set[str]) -> float:
    node_terms = set(_tokens(f"{node.get('id', '')} {node.get('label', '')} {node.get('type', '')}"))
    if not node_terms:
        return 0
    exact = len(node_terms & query_terms)
    partial = sum(
        1
        for term in query_terms
        for node_term in node_terms
        if term in node_term or node_term in term
    )
    return exact + partial * 0.35


def _match_graph(query_terms: set[str], ontology_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[list[str]], set[str]]:
    nodes: list[dict[str, Any]] = _load_json(ontology_dir / "nodes.json", [])
    edges: list[dict[str, Any]] = _load_json(ontology_dir / "edges.json", [])

    scored_nodes = [
        (score, node)
        for node in nodes
        if (score := _node_score(node, query_terms)) > 0
    ]
    scored_nodes.sort(key=lambda item: (-item[0], item[1].get("id", "")))
    matched_nodes = [node for _, node in scored_nodes[:12]]
    matched_ids = {node.get("id") for node in matched_nodes}

    matched_edges = [
        edge
        for edge in edges
        if edge.get("source") in matched_ids or edge.get("target") in matched_ids
    ][:18]
    graph_paths = [
        [str(edge.get("source", "")), str(edge.get("relation", "relates")), str(edge.get("target", ""))]
        for edge in matched_edges[:8]
    ]

    expanded_terms = set(query_terms)
    for node in matched_nodes:
        expanded_terms.update(_tokens(f"{node.get('id', '')} {node.get('label', '')}"))
    for edge in matched_edges:
        expanded_terms.update(_tokens(f"{edge.get('source', '')} {edge.get('relation', '')} {edge.get('target', '')}"))
    return matched_nodes, matched_edges, graph_paths, expanded_terms


def _phrase_bonus(query: str, text: str, query_terms: list[str]) -> float:
    normalized_query = " ".join(query.lower().split())
    normalized_text = " ".join(text.lower().split())
    bonus = 0.0
    if normalized_query and normalized_query in normalized_text:
        bonus += 1.25
    for left, right in zip(query_terms, query_terms[1:]):
        if f"{left} {right}" in normalized_text:
            bonus += 0.2
    return bonus


def _rank_chunks(
    query: str,
    query_counts: Counter[str],
    expanded_terms: set[str],
    chunks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not chunks:
        return []

    idf = _idf(chunks)
    average_length = sum(chunk["token_total"] for chunk in chunks) / max(1, len(chunks))
    query_terms = list(query_counts)
    ranked: list[dict[str, Any]] = []
    for chunk in chunks:
        chunk_counts: Counter[str] = chunk["tokens"]
        lexical = 0.0
        for term, frequency in query_counts.items():
            if term not in chunk_counts:
                continue
            tf = chunk_counts[term]
            k1 = 1.2
            b = 0.75
            length_norm = 1 - b + b * chunk["token_total"] / max(1.0, average_length)
            lexical += idf.get(term, 1.0) * ((tf * (k1 + 1)) / (tf + k1 * length_norm)) * frequency

        matched_terms = set(query_terms) & set(chunk_counts)
        coverage = len(matched_terms) / max(1, len(set(query_terms)))
        graph_overlap = len(expanded_terms & set(chunk_counts)) / max(1, len(expanded_terms))
        phrase = _phrase_bonus(query, chunk["text"], query_terms)
        score = lexical + coverage * 0.8 + graph_overlap * 1.1 + phrase
        if score <= 0:
            continue
        ranked.append(
            {
                "doc_id": chunk["doc_id"],
                "chunk_id": chunk["chunk_id"],
                "path": chunk["path"],
                "score": round(score, 4),
                "snippet": _best_snippet(chunk["text"], matched_terms or set(query_terms)),
                "retrieval_signals": {
                    "lexical": round(lexical, 4),
                    "coverage": round(coverage, 4),
                    "graph_boost": round(graph_overlap, 4),
                    "phrase_bonus": round(phrase, 4),
                },
            }
        )
    ranked.sort(key=lambda item: (-item["score"], item["chunk_id"]))
    return ranked


def _best_snippet(text: str, terms: set[str], limit: int = 320) -> str:
    sentences = _sentences(text) or [text]
    if not terms:
        return text[:limit].strip()
    scored = []
    for sentence in sentences:
        sentence_terms = set(_tokens(sentence))
        scored.append((len(sentence_terms & terms), sentence))
    scored.sort(key=lambda item: -item[0])
    snippet = scored[0][1] if scored else text
    return snippet[:limit].strip()


def _synthesize_answer(
    query: str,
    evidence_docs: list[dict[str, Any]],
    matched_nodes: list[dict[str, Any]],
    graph_paths: list[list[str]],
) -> tuple[str, list[dict[str, Any]], list[str]]:
    citations = [
        {
            "doc_id": doc["chunk_id"],
            "source_doc_id": doc["doc_id"],
            "path": doc["path"],
            "score": doc["score"],
        }
        for doc in evidence_docs[:4]
    ]

    if not evidence_docs:
        return (
            f"'{query}'에 대한 충분한 근거 문서를 찾지 못했습니다. DataGate에 문서를 추가한 뒤 Ontology Forge와 GraphRAG를 다시 실행하세요.",
            citations,
            ["어떤 문서를 DataGate에 넣어야 하나요?", "온톨로지 노드를 먼저 확장할까요?"],
        )

    node_labels = [str(node.get("label", node.get("id", ""))) for node in matched_nodes[:4]]
    node_text = ", ".join(label for label in node_labels if label) or "현재 온톨로지 노드"
    evidence_text = " ".join(doc["snippet"] for doc in evidence_docs[:2])
    path_text = "; ".join(" -> ".join(path) for path in graph_paths[:2]) or "문서 근거 중심"
    answer = (
        f"질문 '{query}'는 {node_text} 기억과 연결됩니다. "
        f"상위 근거는 다음 흐름을 지지합니다: {path_text}. "
        f"요약하면 {evidence_text}"
    )
    follow_up = [
        "이 답변을 Guardrail로 검증할까요?",
        "관련 온톨로지 경로를 더 넓게 확장할까요?",
    ]
    return answer[:900], citations, follow_up


def query_graphrag(
    query: str,
    cleaned_dir: str = "data/cleaned",
    ontology_dir: str = "data/ontology",
) -> dict[str, Any]:
    query_counts = Counter(_tokens(query))
    query_terms = set(query_counts)
    ontology_root = Path(ontology_dir)
    matched_nodes, matched_edges, graph_paths, expanded_terms = _match_graph(query_terms, ontology_root)

    chunks = _load_doc_chunks(Path(cleaned_dir))
    ranked_docs = _rank_chunks(query, query_counts, expanded_terms, chunks)
    evidence_docs = ranked_docs[:5]
    answer, citations, follow_up_questions = _synthesize_answer(query, evidence_docs, matched_nodes, graph_paths)
    confidence = round(
        min(
            0.98,
            0.18
            + min(5, len(evidence_docs)) * 0.1
            + min(6, len(matched_nodes)) * 0.035
            + min(6, len(matched_edges)) * 0.025
            + (0.1 if citations else 0),
        ),
        2,
    )

    return {
        "query": query,
        "method": "homage-hybrid-graphrag-v1",
        "answer": answer,
        "matched_nodes": matched_nodes,
        "matched_edges": matched_edges,
        "evidence_docs": evidence_docs,
        "citations": citations,
        "graph_paths": graph_paths,
        "follow_up_questions": follow_up_questions,
        "retrieval_trace": {
            "strategy": "hybrid lexical BM25-style ranking + ontology 1-hop expansion + deterministic synthesis",
            "query_terms": sorted(query_terms),
            "expanded_terms": sorted(expanded_terms)[:30],
            "ranked_chunk_ids": [doc["chunk_id"] for doc in ranked_docs[:8]],
            "matched_node_ids": [str(node.get("id", "")) for node in matched_nodes],
        },
        "confidence": confidence,
    }
