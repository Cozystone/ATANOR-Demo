from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

from .utterance_engine import build_native_utterance


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


def _is_greeting_query(query: str) -> bool:
    normalized = _normalized_query(query)
    return bool(re.fullmatch(r"(안녕|안녕하세요|하이|헬로|반가워|hi|hello|hey|yo)[\s!.?。！？]*", normalized, re.IGNORECASE))


def _is_thanks_query(query: str) -> bool:
    normalized = _normalized_query(query)
    return bool(re.fullmatch(r"(고마워|감사|감사합니다|땡큐|thanks|thank you)[\s!.?。！？]*", normalized, re.IGNORECASE))


def _is_node_inventory_query(query: str) -> bool:
    normalized = _normalized_query(query)
    asks_for_nodes = bool(re.search(r"(노드|node|nodes)", normalized, re.IGNORECASE))
    asks_for_inventory = bool(re.search(r"(다|전체|모두|목록|리스트|말해|알려|보여|보유|있는|list|all|show|inventory|available)", normalized, re.IGNORECASE))
    return asks_for_nodes and asks_for_inventory


def _is_legend_query(query: str) -> bool:
    normalized = _normalized_query(query)
    asks_color = bool(re.search(r"(색|색깔|색상|컬러|범례|legend|color)", normalized, re.IGNORECASE))
    asks_meaning = bool(re.search(r"(의미|뜻|뭐|설명|구분|차이|meaning|mean|label)", normalized, re.IGNORECASE))
    graph_context = bool(re.search(r"(노드|그래프|rag|온톨로지|메모리|신호|뉴런|node|graph)", normalized, re.IGNORECASE))
    return asks_color and (asks_meaning or graph_context)


def _is_internal_structure_query(query: str) -> bool:
    normalized = _normalized_query(query)
    self_or_system = bool(
        re.search(
            r"(너|네|니|너희|homage|bakeboard|rag|graphrag|온톨로지|메모리|파이프라인|엔진|시스템|아키텍처|구조|architecture|system|engine)",
            normalized,
            re.IGNORECASE,
        )
    )
    asks_structure = bool(
        re.search(
            r"(구조|설명|작동|어떻게|뭐야|무엇|누구|흐름|과정|엔진|아키텍처|structure|explain|architecture|work|flow)",
            normalized,
            re.IGNORECASE,
        )
    )
    return self_or_system and asks_structure


def _conversational_result(query: str, kind: str) -> dict[str, Any]:
    if kind == "greeting":
        answer = "안녕하세요. Homage 실험실입니다. 지금은 외부 LLM 없이 로컬 그래프 메모리와 native 생성기를 실험하는 상태예요."
    elif kind == "thanks":
        answer = "천만에요. 지금 실험 결과가 이상하면 그대로 알려주세요. 그래프, 검색, 생성 경로를 분리해서 확인하겠습니다."
    else:
        answer = query.strip()
    return {
        "query": query,
        "method": "homage-conversation-router-v1",
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
            "name": "Homage Graph Token Predictor",
            "mode": "conversation-surface-no-retrieval-alpha",
            "external_llm": False,
            "surface_generation": "native_conversation_surface",
            "control_intent": kind,
        },
    }


def _load_json(path: Path, default: Any) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _node_type_text(node_type: str | None) -> str:
    labels = {
        "concept": "개념",
        "keyword": "키워드",
        "heading": "제목",
        "source": "자료",
        "ontology": "온톨로지",
        "retrieval": "검색",
        "guardrail": "가드레일",
        "training": "학습",
        "visualization": "시각화",
        "critique": "비평",
    }
    return labels.get(node_type or "", node_type or "기억")


def _node_type_color(node_type: str | None) -> str:
    colors = {
        "source": "#ff6b35",
        "critique": "#c5283d",
        "ontology": "#1a936f",
        "retrieval": "#006a9f",
        "visualization": "#8c3fa7",
        "guardrail": "#e89d2a",
        "training": "#111715",
        "concept": "#22936f",
        "keyword": "#4a8fdb",
        "heading": "#7b8794",
        "quality": "#3f6f5f",
        "memory": "#1a936f",
        "verification": "#e89d2a",
        "learning": "#111715",
        "efficiency": "#006a9f",
    }
    return colors.get(node_type or "", "#68736d")


def _node_type_description(node_type: str | None) -> str:
    descriptions = {
        "source": "외부에서 수집된 원문 자료와 근거 청크",
        "critique": "품질 문제, 반례, 경계 조건을 표시하는 비평 신호",
        "ontology": "개념 사이의 관계를 묶는 온톨로지 메모리",
        "retrieval": "질문을 근거 문서와 그래프 경로로 연결하는 검색 노드",
        "visualization": "학습 상태를 화면에 투사하는 시각화 노드",
        "guardrail": "과장, 환각, 근거 부족을 검증하는 안전 노드",
        "training": "Homage Oven으로 넘어가는 학습/압축 신호",
        "concept": "문서에서 추출된 핵심 개념",
        "keyword": "검색과 관계 확장에 쓰이는 키워드 기억",
        "heading": "문서 구조나 섹션 제목에서 온 문맥 앵커",
        "quality": "DataGate 품질 게이트 신호",
        "memory": "장기 온톨로지 메모리 저장 영역",
        "verification": "근거 확인과 검증에 쓰이는 노드",
        "learning": "실시간 학습 과정과 연결되는 노드",
        "efficiency": "저전력/저사양 실행을 위한 효율화 노드",
    }
    return descriptions.get(node_type or "", "현재 그래프에서 관찰된 사용자 정의 기억 노드")


def _node_inventory_result(query: str, ontology_dir: Path) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = _load_json(ontology_dir / "nodes.json", [])
    edges: list[dict[str, Any]] = _load_json(ontology_dir / "edges.json", [])
    node_lines = []
    for index, node in enumerate(nodes, start=1):
        label = node.get("label") or node.get("id") or f"node-{index}"
        node_type = _node_type_text(str(node.get("type") or node.get("labels", [""])[0] or ""))
        confidence = node.get("confidence")
        confidence_text = f", 신뢰도 {round(float(confidence) * 100)}%" if isinstance(confidence, (int, float)) else ""
        node_lines.append(f"{index}. {label} ({node_type}, id: {node.get('id', label)}{confidence_text})")
    answer = (
        f"현재 온톨로지 메모리에는 {len(nodes)}개 노드와 {len(edges)}개 관계가 있습니다.\n" + "\n".join(node_lines)
        if nodes
        else "현재 온톨로지 메모리에 저장된 노드가 없습니다. DataGate와 Ontology Forge를 먼저 실행해 주세요."
    )
    return {
        "query": query,
        "method": "homage-graph-inspection-v1",
        "answer": answer,
        "matched_nodes": nodes,
        "matched_edges": edges,
        "evidence_docs": [],
        "citations": [],
        "graph_paths": [
            [str(edge.get("source", "")), str(edge.get("relation", "relates")), str(edge.get("target", ""))]
            for edge in edges[:12]
        ],
        "follow_up_questions": ["관계선도 모두 보여줄까요?", "특정 노드의 이웃만 펼쳐볼까요?"],
        "retrieval_trace": {
            "strategy": "graph inventory intent; retrieval skipped",
            "query_terms": _tokens(query),
            "expanded_terms": [],
            "ranked_chunk_ids": [],
            "matched_node_ids": [str(node.get("id", "")) for node in nodes],
        },
        "confidence": 0.99 if nodes else 0.2,
        "answer_kind": "inspection",
        "answer_engine": {
            "name": "BakeBoard Inspection Router",
            "mode": "graph-inspection-control-alpha",
            "external_llm": False,
            "surface_generation": "disabled",
        },
    }


def _graph_legend_result(query: str, ontology_dir: Path) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = _load_json(ontology_dir / "nodes.json", [])
    edges: list[dict[str, Any]] = _load_json(ontology_dir / "edges.json", [])
    type_order: list[str] = []
    type_counts: Counter[str] = Counter()
    representatives: list[dict[str, Any]] = []
    seen: set[str] = set()
    for node in nodes:
        node_type = str(node.get("type") or node.get("labels", ["concept"])[0] or "concept")
        type_counts[node_type] += 1
        if node_type not in type_order:
            type_order.append(node_type)
        if node_type not in seen:
            representatives.append(node)
            seen.add(node_type)

    lines = [
        f"- {_node_type_color(node_type)} {_node_type_text(node_type)}: {_node_type_description(node_type)}. 현재 {type_counts[node_type]}개"
        for node_type in type_order[:10]
    ]
    answer = (
        "색깔은 노드의 역할을 뜻합니다. 기본 색은 기억 타입이고, 답변 생성 중 주황색 발광은 지금 읽히는 활성 신호입니다.\n"
        + "\n".join(lines)
        if lines
        else "아직 온톨로지 노드가 없어 색상 범례를 만들 수 없습니다. DataGate와 Ontology Forge를 먼저 실행해 주세요."
    )
    representative_ids = {str(node.get("id", "")) for node in representatives}
    matched_edges = [
        edge
        for edge in edges
        if str(edge.get("source", "")) in representative_ids or str(edge.get("target", "")) in representative_ids
    ][:12]
    return {
        "query": query,
        "method": "homage-graph-legend-v1",
        "answer": answer,
        "matched_nodes": representatives,
        "matched_edges": matched_edges,
        "evidence_docs": [],
        "citations": [],
        "graph_paths": [
            [str(edge.get("source", "")), str(edge.get("relation", "relates")), str(edge.get("target", ""))]
            for edge in matched_edges
        ],
        "follow_up_questions": ["주황색 신호가 어떤 노드를 읽는지 보여줄까요?", "현재 노드 목록도 같이 펼쳐볼까요?"],
        "retrieval_trace": {
            "strategy": "graph legend intent; retrieval skipped",
            "query_terms": _tokens(query),
            "expanded_terms": type_order,
            "ranked_chunk_ids": [],
            "matched_node_ids": [str(node.get("id", "")) for node in representatives],
        },
        "confidence": 0.98 if nodes else 0.25,
        "answer_kind": "inspection",
        "answer_engine": {
            "name": "BakeBoard Inspection Router",
            "mode": "graph-legend-control-alpha",
            "external_llm": False,
            "surface_generation": "disabled",
        },
    }


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


def _internal_context_docs(query: str) -> list[dict[str, Any]]:
    """Internal architecture context used when retrieval has no direct evidence.

    These chunks are exposed as internal training samples so the graph-token
    predictor can walk architecture tokens without pretending they came from
    external retrieved evidence.
    """

    snippets = [
        (
            "Homage1.0은 Harvest, DataGate, Ontology Forge, GraphRAG, Guardrail, "
            "Homage Oven, Neuro-Efficiency, Hardware Benchmark, BakeBoard UI로 나뉜다. "
            "DataGate는 입력 품질을 거르고, Ontology Forge는 개념과 관계를 만들고, "
            "GraphRAG는 질문 시 활성 노드와 문서 chunk를 모아 context bundle을 만든다."
        ),
        (
            "Homage Graph Token Predictor는 외부 LLM을 쓰지 않고 sentence tokens, "
            "co-occurrence edges, ontology paths, active concepts를 연결해 다음 토큰열을 걷는다. "
            "연결이 약하면 답변 품질도 그대로 약하게 드러난다."
        ),
        (
            "BakeBoard의 신호 시각화는 답변 생성 중 읽힌 노드를 주황색 발광으로 보여준다. "
            "이 신호는 고정된 최단 경로가 아니라 뇌 활성처럼 관련 노드들이 켜졌다 꺼지는 상태 표시다."
        ),
    ]
    return [
        {
            "doc_id": "homage-internal-architecture",
            "chunk_id": f"homage-internal-architecture#{index}",
            "path": "internal://homage-architecture",
            "score": 0.32,
            "snippet": snippet,
            "retrieval_signals": {
                "lexical": 0,
                "coverage": 0,
                "graph_boost": 0,
                "phrase_bonus": 0,
                "internal_context": True,
            },
        }
        for index, snippet in enumerate(snippets, start=1)
        if query.strip()
    ]


def _synthesize_answer(
    query: str,
    evidence_docs: list[dict[str, Any]],
    matched_nodes: list[dict[str, Any]],
    graph_paths: list[list[str]],
    use_internal_context: bool = False,
) -> tuple[str, list[dict[str, Any]], list[str], dict[str, Any]]:
    citations = [
        {
            "doc_id": doc["chunk_id"],
            "source_doc_id": doc["doc_id"],
            "path": doc["path"],
            "score": doc["score"],
        }
        for doc in evidence_docs[:4]
    ]

    synthesis_docs = evidence_docs or (_internal_context_docs(query) if use_internal_context else [])
    synthesis_paths = graph_paths if evidence_docs else []
    utterance = build_native_utterance(query, synthesis_docs, matched_nodes, synthesis_paths)
    follow_up: list[str] = []
    return utterance["answer"], citations, follow_up, utterance


def query_graphrag(
    query: str,
    cleaned_dir: str = "data/cleaned",
    ontology_dir: str = "data/ontology",
) -> dict[str, Any]:
    if _is_greeting_query(query):
        return _conversational_result(query, "greeting")
    if _is_thanks_query(query):
        return _conversational_result(query, "thanks")
    if _is_legend_query(query):
        return _graph_legend_result(query, Path(ontology_dir))
    if _is_node_inventory_query(query):
        return _node_inventory_result(query, Path(ontology_dir))

    query_counts = Counter(_tokens(query))
    query_terms = set(query_counts)
    ontology_root = Path(ontology_dir)
    matched_nodes, matched_edges, graph_paths, expanded_terms = _match_graph(query_terms, ontology_root)

    chunks = _load_doc_chunks(Path(cleaned_dir))
    ranked_docs = _rank_chunks(query, query_counts, expanded_terms, chunks)
    evidence_docs = ranked_docs[:5]
    use_internal_context = not evidence_docs and _is_internal_structure_query(query)
    if use_internal_context:
        evidence_docs = _internal_context_docs(query)
    raw_no_node = not evidence_docs
    answer, citations, follow_up_questions, utterance = _synthesize_answer(
        query,
        evidence_docs,
        matched_nodes,
        graph_paths,
        use_internal_context,
    )
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
        "method": "homage-research-no-evidence-v1" if raw_no_node else "homage-graph-token-rag-v1",
        "answer": answer,
        "matched_nodes": matched_nodes,
        "matched_edges": matched_edges,
        "evidence_docs": evidence_docs,
        "citations": citations,
        "graph_paths": graph_paths,
        "pmv": utterance["pmv"],
        "claim_plan": utterance["claim_plan"],
        "active_concepts": utterance["active_concepts"],
        "answer_kind": utterance.get("answer_kind"),
        "answer_engine": utterance["answer_engine"],
        "follow_up_questions": follow_up_questions,
        "retrieval_trace": {
            "strategy": "no evidence; diagnostic only" if raw_no_node else "hybrid lexical ranking + ontology expansion + graph-token prediction",
            "query_terms": sorted(query_terms),
            "expanded_terms": sorted(expanded_terms)[:30],
            "ranked_chunk_ids": [doc["chunk_id"] for doc in ranked_docs[:8]],
            "matched_node_ids": [str(node.get("id", "")) for node in matched_nodes],
        },
        "confidence": confidence,
    }
