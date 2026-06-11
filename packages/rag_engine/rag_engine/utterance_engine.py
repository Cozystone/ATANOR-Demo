from __future__ import annotations

import re
from collections import Counter
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


def _sentences(text: str) -> list[str]:
    chunks = re.split(r"(?<=[.!?。！？])\s+|\n+", text.strip())
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def _infer_intent(query: str) -> str:
    normalized = query.lower()
    if re.search(r"(왜|이유|줄이는|효과|why)", normalized):
        return "explain_cause"
    if re.search(r"(어떻게|방법|과정|흐름|how)", normalized):
        return "explain_process"
    if re.search(r"(비교|차이|versus|vs)", normalized):
        return "compare"
    if re.search(r"(뭐|무엇|정의|의미|what)", normalized):
        return "define"
    return "answer_grounded"


def _answer_goal_for(intent: str) -> str:
    return {
        "explain_cause": "explain why the concept works",
        "explain_process": "describe the process in order",
        "compare": "compare the activated concepts",
        "define": "define the activated concept",
        "answer_grounded": "answer with graph-grounded context",
    }.get(intent, "answer with graph-grounded context")


def _audience_level(query: str) -> str:
    if re.search(r"(쉽게|초보|간단|한줄|짧게)", query):
        return "intuitive"
    if re.search(r"(구조|아키텍처|엔진|구현|trace|경로)", query, re.IGNORECASE):
        return "technical but intuitive"
    return "general technical"


def _node_label(node: dict[str, Any]) -> str:
    return str(node.get("label") or node.get("id") or "").strip()


def _path_text(path: list[str]) -> str:
    if len(path) >= 3:
        return f"{path[0]} --{path[1]}--> {path[2]}"
    return " -> ".join(path)


def _rank_sentences(query: str, evidence_docs: list[dict[str, Any]], active_concepts: list[str]) -> list[dict[str, Any]]:
    query_terms = set(_tokens(query))
    concept_terms = set(_tokens(" ".join(active_concepts)))
    ranked: list[dict[str, Any]] = []
    for doc in evidence_docs:
        text = str(doc.get("snippet") or doc.get("text") or "")
        for index, sentence in enumerate(_sentences(text) or [text]):
            sentence_terms = set(_tokens(sentence))
            query_overlap = len(query_terms & sentence_terms)
            concept_overlap = len(concept_terms & sentence_terms)
            score = query_overlap * 1.2 + concept_overlap * 0.8 + float(doc.get("score") or 0)
            if sentence.strip():
                ranked.append(
                    {
                        "text": sentence.strip(),
                        "score": round(score, 4),
                        "doc_id": doc.get("chunk_id") or doc.get("doc_id") or f"evidence-{index}",
                    }
                )
    ranked.sort(key=lambda item: (-item["score"], str(item["doc_id"])))
    return ranked


def _compact_join(parts: list[str], limit: int = 900) -> str:
    text = " ".join(part.strip() for part in parts if part and part.strip())
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit].rstrip()


def build_native_utterance(
    query: str,
    evidence_docs: list[dict[str, Any]],
    matched_nodes: list[dict[str, Any]],
    graph_paths: list[list[str]],
) -> dict[str, Any]:
    """Build a PRD-style answer without using an external LLM.

    The Alpha engine follows the Homage Utterance Engine order:
    intent -> concepts -> ontology path -> claim plan -> evidence -> surface text.
    It is still lightweight, but it avoids pretending that GraphRAG retrieval text
    itself is a model response.
    """

    intent = _infer_intent(query)
    active_concepts = [_node_label(node) for node in matched_nodes if _node_label(node)]
    if not active_concepts:
        active_concepts = [term for term, _ in Counter(_tokens(query)).most_common(4)]
    active_concepts = active_concepts[:6]
    ranked_sentences = _rank_sentences(query, evidence_docs, active_concepts)
    selected_evidence = ranked_sentences[:3]
    path_lines = [_path_text(path) for path in graph_paths[:3]]

    pmv = {
        "intent": intent,
        "topic": active_concepts[0] if active_concepts else query,
        "stance": "grounded and cautious",
        "audience_level": _audience_level(query),
        "answer_goal": _answer_goal_for(intent),
        "required_evidence": True,
        "style": "clear Korean technical explanation",
    }

    claim_plan = []
    if active_concepts:
        claim_plan.append(
            {
                "claim": f"{active_concepts[0]}는 현재 질문의 중심 개념이다.",
                "support": selected_evidence[0]["doc_id"] if selected_evidence else "graph",
            }
        )
    if path_lines:
        claim_plan.append({"claim": "답변은 온톨로지 경로를 따라 좁혀진다.", "support": "graph_path"})
    for evidence in selected_evidence[:2]:
        claim_plan.append({"claim": evidence["text"], "support": evidence["doc_id"]})

    if not evidence_docs:
        topic = query.strip() or "현재 질문"
        answer = (
            f"현재 Homage 메모리에는 '{topic}'에 대해 검증된 문서 근거가 아직 없습니다. "
            "외부 LLM이나 일반 지식 데이터베이스를 쓰지 않는 Alpha 모드라서, "
            "학습되지 않은 외부 사실은 단정하지 않습니다. "
            "Build Start나 Harvest 입력으로 관련 자료를 넣으면 DataGate가 문서를 거르고, "
            "Ontology Forge가 인물/개념 노드를 만든 뒤 GraphRAG가 그 근거로 답변할 수 있습니다. "
            f"현재 활성화된 후보 개념은 {', '.join(active_concepts) if active_concepts else '없음'}입니다."
        )
    else:
        lead_by_intent = {
            "explain_cause": "핵심 이유는 지식을 모델 파라미터에만 맡기지 않고, 그래프 경로와 근거 청크로 분리해 확인하기 때문입니다.",
            "explain_process": "흐름은 질문 의도를 잡고, 관련 개념을 활성화한 뒤, 온톨로지 경로와 근거 청크를 합쳐 답변 계획을 만드는 순서입니다.",
            "compare": "비교의 기준은 어떤 개념이 검색을 맡고, 어떤 개념이 검증과 발화를 보조하는지입니다.",
            "define": "의미를 먼저 말하면, 이 노드는 Homage 메모리 안에서 특정 역할을 맡은 활성 개념입니다.",
            "answer_grounded": "현재 답변은 Homage Utterance Engine이 GraphRAG context bundle을 읽고 만든 네이티브 발화입니다.",
        }
        concept_part = f"활성 개념은 {', '.join(active_concepts[:4])}입니다." if active_concepts else ""
        signal_part = f"활성 신호는 {', '.join(active_concepts[:4])} 노드에서 켜졌습니다." if active_concepts else ""
        evidence_part = " ".join(item["text"] for item in selected_evidence)
        answer = _compact_join([lead_by_intent[intent], concept_part, signal_part, evidence_part])

    return {
        "answer": answer,
        "pmv": pmv,
        "claim_plan": claim_plan,
        "active_concepts": active_concepts,
        "answer_engine": {
            "name": "Homage Utterance Engine",
            "mode": "native-next-thought-alpha",
            "external_llm": False,
            "homage_core": "homage-core-30m-scaffold",
            "stages": [
                "intent",
                "concepts",
                "ontology_path",
                "claim_plan",
                "evidence",
                "surface_text",
                "reference_tail",
                "guard_ready",
            ],
        },
    }
