from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

from .fusion import fusion_ratio_from_context
from .graph_store import graph_inventory, graph_legend, query_lazy_chunks, query_lazy_subgraph
from .synthesizer import LocalSynthesizer


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


def _normalized_query(query: str) -> str:
    return " ".join(query.strip().lower().split())


def _effective_memory_dir(cleaned_dir: str, memory_dir: str) -> str:
    if memory_dir == "data/memory" and Path(cleaned_dir) != Path("data/cleaned"):
        return str(Path(cleaned_dir).parent / "memory")
    return memory_dir


def _is_greeting_query(query: str) -> bool:
    normalized = _normalized_query(query)
    return normalized in {"hi", "hello", "hey", "yo", "\uc548\ub155", "\uc548\ub155\ud558\uc138\uc694"}


def _is_thanks_query(query: str) -> bool:
    normalized = _normalized_query(query)
    return normalized in {"thanks", "thank you", "\uace0\ub9c8\uc6cc", "\uac10\uc0ac\ud574", "\uac10\uc0ac\ud569\ub2c8\ub2e4"}


def _is_node_inventory_query(query: str) -> bool:
    normalized = _normalized_query(query)
    return ("node" in normalized or "nodes" in normalized or "\ub178\ub4dc" in normalized) and any(
        word in normalized for word in ["list", "all", "show", "inventory", "available", "\ub2e4", "\uc804\ubd80", "\ubaa8\ub450"]
    )


def _is_legend_query(query: str) -> bool:
    normalized = _normalized_query(query)
    return any(word in normalized for word in ["legend", "color", "\uc0c9", "\uc0c9\uae54"])


def _is_internal_structure_query(query: str) -> bool:
    normalized = _normalized_query(query)
    return any(word in normalized for word in ["atanor", "rag", "graphrag", "ghost", "shell", "payload", "vault", "architecture", "system", "engine", "\uad6c\uc870"])


def _conversational_result(query: str, kind: str) -> dict[str, Any]:
    if kind == "greeting":
        answer = "ATANOR online. Local Ghost Shell and Payload Vault are ready for traceable inference."
    elif kind == "thanks":
        answer = "Acknowledged. ATANOR will keep synthesis local, traceable, and air-gapped."
    else:
        answer = query.strip()
    return {
        "query": query,
        "method": "atanor-conversation-router-v1",
        "answer": answer,
        "matched_nodes": [],
        "matched_edges": [],
        "evidence_docs": [],
        "citations": [],
        "graph_paths": [],
        "follow_up_questions": [],
        "retrieval_trace": {
            "strategy": "conversational intent; retrieval skipped",
            "query_terms": _tokens(query),
            "expanded_terms": [],
            "ranked_chunk_ids": [],
            "matched_node_ids": [],
        },
        "confidence": 0.96,
        "answer_kind": "conversation",
        "answer_engine": {
            "name": "ATANOR Graph Token Predictor",
            "mode": "conversation-surface-no-retrieval-alpha",
            "external_llm": False,
            "surface_generation": "native_conversation_surface",
            "control_intent": kind,
        },
    }


def _node_type_text(node_type: str | None) -> str:
    labels = {
        "concept": "concept",
        "keyword": "keyword",
        "heading": "heading",
        "source": "source",
        "ontology": "ontology",
        "predicate": "predicate",
        "compound": "compound",
        "retrieval": "retrieval",
        "guardrail": "guardrail",
    }
    return labels.get(str(node_type or "concept"), str(node_type or "concept"))


def _inventory_result(query: str, memory_dir: str) -> dict[str, Any]:
    inventory = graph_inventory(memory_dir)
    nodes = inventory.get("nodes", [])
    edges = inventory.get("edges", [])
    preview = ", ".join(f"{node.get('label') or node.get('id')}({_node_type_text(node.get('type'))})" for node in nodes[:16])
    answer = f"ATANOR Ghost Shell currently exposes {len(nodes)} visible nodes and {len(edges)} visible edges."
    if preview:
        answer += f" Representative nodes: {preview}."
    return {
        "query": query,
        "method": "atanor-graph-inspection-v1",
        "answer": answer,
        "matched_nodes": nodes,
        "matched_edges": edges,
        "evidence_docs": [],
        "citations": [],
        "graph_paths": [],
        "follow_up_questions": [],
        "retrieval_trace": {"strategy": "graph inventory inspection", "ranked_chunk_ids": [], "matched_node_ids": [node.get("id") for node in nodes]},
        "confidence": 1.0 if nodes else 0.0,
        "answer_kind": "inspection",
        "answer_engine": {"name": "ATANOR Graph Inspector", "mode": "inspection", "external_llm": False, "surface_generation": "disabled"},
    }


def _legend_result(query: str, memory_dir: str) -> dict[str, Any]:
    legend = graph_legend(memory_dir)
    categories = legend.get("categories", []) or legend.get("node_types", []) or []
    pieces = []
    for item in categories[:12]:
        if isinstance(item, dict):
            pieces.append(f"{item.get('type') or item.get('name')}: {item.get('count', 0)}")
        else:
            pieces.append(str(item))
    answer = "ATANOR graph colors indicate Ghost Shell node classes and active signal states."
    if pieces:
        answer += " Legend: " + "; ".join(pieces) + "."
    return {
        "query": query,
        "method": "atanor-graph-legend-v1",
        "answer": answer,
        "matched_nodes": [],
        "matched_edges": [],
        "evidence_docs": [],
        "citations": [],
        "graph_paths": [],
        "follow_up_questions": [],
        "retrieval_trace": {"strategy": "graph legend inspection", "ranked_chunk_ids": [], "matched_node_ids": []},
        "confidence": 1.0,
        "answer_kind": "inspection",
        "answer_engine": {"name": "ATANOR Graph Inspector", "mode": "inspection", "external_llm": False, "surface_generation": "disabled"},
    }


def _lexical_score(query_terms: list[str], chunk: dict[str, Any]) -> float:
    token_counts = chunk.get("tokens") or Counter(_tokens(str(chunk.get("text") or "")))
    if not token_counts or not query_terms:
        return 0.0
    total = float(chunk.get("token_total") or sum(token_counts.values()) or 1)
    score = 0.0
    for term in query_terms:
        score += float(token_counts.get(term, 0)) / total
        if term in str(chunk.get("text") or "").lower():
            score += 0.08
    return score


def _rank_chunks(query: str, chunks: list[dict[str, Any]], expanded_terms: set[str], *, limit: int = 6) -> list[dict[str, Any]]:
    query_terms = _tokens(query)
    expanded = set(expanded_terms)
    ranked: list[dict[str, Any]] = []
    for chunk in chunks:
        lexical = _lexical_score(query_terms, chunk)
        graph_bonus = 0.03 * sum(1 for term in expanded if term and term in str(chunk.get("text") or "").lower())
        temporal = float(chunk.get("temporal_weight") or chunk.get("score") or 0.0)
        score = lexical + graph_bonus + temporal * 0.1
        item = dict(chunk)
        item["score"] = round(score, 6)
        item["lexical_score"] = round(lexical, 6)
        item["graph_score"] = round(graph_bonus, 6)
        ranked.append(item)
    ranked.sort(key=lambda item: (-float(item.get("score") or 0), str(item.get("chunk_id") or "")))
    return ranked[:limit]


def _citations(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "chunk_id": chunk.get("chunk_id"),
            "doc_id": chunk.get("doc_id"),
            "path": chunk.get("path"),
            "score": chunk.get("score", 0),
            "snippet": str(chunk.get("text") or "")[:260],
        }
        for chunk in chunks
    ]


def _confidence(chunks: list[dict[str, Any]], matched_nodes: list[dict[str, Any]], matched_edges: list[dict[str, Any]]) -> float:
    if not chunks:
        return 0.0
    top_score = max(float(chunk.get("score") or 0.0) for chunk in chunks)
    graph_density = min(1.0, (len(matched_nodes) + len(matched_edges)) / 24.0)
    return round(min(0.98, 0.25 + top_score + graph_density * 0.25), 3)


def query_graphrag(
    query: str,
    cleaned_dir: str = "data/cleaned",
    ontology_dir: str = "data/ontology",
    memory_dir: str = "data/memory",
) -> dict[str, Any]:
    effective_memory = _effective_memory_dir(cleaned_dir, memory_dir)
    query_terms = _tokens(query)

    if _is_greeting_query(query):
        return _conversational_result(query, "greeting")
    if _is_thanks_query(query):
        return _conversational_result(query, "thanks")
    if _is_node_inventory_query(query):
        return _inventory_result(query, effective_memory)
    if _is_legend_query(query):
        return _legend_result(query, effective_memory)

    subgraph = query_lazy_subgraph(query_terms or [query], effective_memory, max_depth=3, max_nodes=512, max_edges=2048)
    expanded_terms = set(subgraph.get("expanded_terms") or set(query_terms))
    chunks = query_lazy_chunks(query, expanded_terms, effective_memory, limit=48)
    ranked_chunks = _rank_chunks(query, chunks, expanded_terms)

    matched_nodes = list(subgraph.get("nodes") or [])
    matched_edges = list(subgraph.get("edges") or [])
    graph_paths = list(subgraph.get("graph_paths") or [])
    payload_docs = list(subgraph.get("payload_docs") or [])
    if not ranked_chunks and payload_docs:
        ranked_chunks = _rank_chunks(query, payload_docs, expanded_terms)

    has_direct_lexical_hit = any(float(chunk.get("lexical_score") or 0.0) > 0.0 for chunk in ranked_chunks)
    if (not ranked_chunks or not has_direct_lexical_hit) and not _is_internal_structure_query(query):
        utterance = LocalSynthesizer().synthesize(query, [], matched_nodes, matched_edges, graph_paths)
        fusion_ratio = fusion_ratio_from_context(
            query=query,
            matched_nodes=matched_nodes,
            matched_edges=matched_edges,
            evidence_docs=[],
            local_answer_confidence=0.0,
        )
        return {
            "query": query,
            "method": "atanor-research-no-evidence-v1",
            "answer": utterance["answer"],
            "pmv": utterance.get("pmv", {}),
            "claim_plan": utterance.get("claim_plan", []),
            "active_concepts": utterance.get("active_concepts", []),
            "matched_nodes": [],
            "matched_edges": [],
            "evidence_docs": [],
            "citations": [],
            "graph_paths": [],
            "follow_up_questions": [],
            "retrieval_trace": {
                "strategy": "no local evidence; external LLM disabled",
                "query_terms": query_terms,
                "expanded_terms": sorted(expanded_terms),
                "ranked_chunk_ids": [],
                "matched_node_ids": [],
                "fetch_sequence": subgraph.get("fetch_logs", []),
                "fusion_ratio": fusion_ratio,
            },
            "fusion_ratio": fusion_ratio,
            "confidence": 0.0,
            "answer_kind": "no_evidence",
            "answer_engine": utterance["answer_engine"],
            "ghost_shell": subgraph.get("ghost_shell", {}),
            "fetch_sequence": subgraph.get("fetch_logs", []),
        }

    synthesis_docs = ranked_chunks or [
        {
            "chunk_id": "atanor-structure#1",
            "doc_id": "atanor-structure",
            "path": "memory://atanor-structure",
            "text": "ATANOR is a local-first Ghost Shell and Payload Vault architecture for traceable graph-grounded synthesis.",
            "score": 0.35,
        }
    ]
    utterance = LocalSynthesizer().synthesize(query, synthesis_docs, matched_nodes, matched_edges, graph_paths)
    citations = _citations(ranked_chunks)
    confidence = _confidence(ranked_chunks, matched_nodes, matched_edges)
    fusion_ratio = fusion_ratio_from_context(
        query=query,
        matched_nodes=matched_nodes,
        matched_edges=matched_edges,
        evidence_docs=ranked_chunks,
        local_answer_confidence=confidence,
    )
    return {
        "query": query,
        "method": "atanor-graph-token-rag-v1",
        "answer": utterance["answer"],
        "pmv": utterance.get("pmv", {}),
        "claim_plan": utterance.get("claim_plan", []),
        "active_concepts": utterance.get("active_concepts", []),
        "matched_nodes": matched_nodes,
        "matched_edges": matched_edges,
        "evidence_docs": ranked_chunks,
        "citations": citations,
        "graph_paths": graph_paths,
        "follow_up_questions": [],
        "retrieval_trace": {
            "strategy": "lazy Ghost Shell subgraph + Payload Vault fetch + local synthesis",
            "query_terms": query_terms,
            "expanded_terms": sorted(expanded_terms),
            "ranked_chunk_ids": [chunk.get("chunk_id") for chunk in ranked_chunks],
            "matched_node_ids": [node.get("id") or node.get("node_hash") for node in matched_nodes],
            "fetch_sequence": subgraph.get("fetch_logs", []),
            "active_hashes": subgraph.get("active_hashes", []),
            "limits": subgraph.get("limits", {}),
            "fusion_ratio": fusion_ratio,
        },
        "fusion_ratio": fusion_ratio,
        "confidence": confidence,
        "answer_kind": utterance.get("answer_kind", "local_synthesis"),
        "answer_engine": utterance["answer_engine"],
        "ghost_shell": subgraph.get("ghost_shell", {}),
        "fetch_sequence": subgraph.get("fetch_logs", []),
    }
