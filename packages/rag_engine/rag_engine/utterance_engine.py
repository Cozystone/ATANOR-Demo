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


def _clean_topic_token(token: str) -> str:
    if re.fullmatch(r"[가-힣]{2,}(에게|에서|으로|은|는|이|가|을|를|의|와|과)", token):
        return re.sub(r"(에게|에서|으로|은|는|이|가|을|를|의|와|과)$", "", token)
    return token


def _native_no_node_generation(query: str, active_concepts: list[str], intent: str) -> str:
    """Generate a clean native answer when memory has no node hit."""

    clean_query = re.sub(r"\s+", " ", query.strip())
    tokens = [token for token in (active_concepts or _tokens(query)[:5]) if token]
    topic = _clean_topic_token(tokens[0]) if tokens else clean_query or "이 질문"
    tail = ", ".join(tokens[1:4])
    question_mark = "?" if clean_query and not clean_query.endswith(("?", "？")) else ""
    seed = sum(ord(char) for char in clean_query) % 3 if clean_query else 0

    if intent == "define" or re.search(r"(누구|무엇|뭐|who|what)", clean_query, re.IGNORECASE):
        variants = [
            f"지금 메모리 안에는 '{topic}' 설명에 필요한 근거 노드나 문서가 아직 없습니다. 그래서 누구라고 단정하지 않고, 이 이름을 새 entity 후보로 남겨 다음 수집 때 관계와 근거를 붙이겠습니다.",
            f"{topic}에 대한 확인된 온톨로지 노드는 아직 없습니다. 현재 질문은 식별 요청으로 읽혔고, 학습 파이프라인은 이 표현을 미학습 대상 후보로 보관합니다.",
            f"아직 '{topic}' 대상을 특정할 수 있는 문서 근거가 없습니다. 지금은 알 수 없다고 답하는 편이 맞고, Harvest가 관련 자료를 모으면 인물/대상 노드로 연결할 수 있습니다.",
        ]
    elif intent == "explain_process":
        variants = [
            f"{clean_query}{question_mark} 지금 메모리에는 이 절차를 뒷받침할 노드가 없어서 확정 설명은 만들지 않습니다. 대신 질문의 핵심 단서 {topic}{f', {tail}' if tail else ''}를 다음 온톨로지 후보로 남깁니다.",
            f"이 과정은 아직 학습된 경로로 이어지지 않았습니다. Homage는 질문 토큰을 후보 노드로 분리해 두고, 새 문서가 들어오면 순서 관계를 다시 계산합니다.",
            f"현재 그래프에는 이 절차를 설명할 연결이 없습니다. 수집이 진행되면 {topic} 주변의 선후 관계와 행위 관계를 먼저 만들겠습니다.",
        ]
    else:
        variants = [
            f"지금 그래프에는 '{topic}' 항목과 직접 이어지는 근거가 없습니다. 답을 꾸며내지 않고, 질문에서 감지한 단서를 미학습 노드 후보로 남겨 두겠습니다.",
            f"{clean_query}{question_mark} 현재 Homage 메모리는 이 질문을 뒷받침할 문서 조각을 찾지 못했습니다. 새 근거가 들어오면 {topic} 주변 관계부터 다시 활성화합니다.",
            f"아직 이 질문은 온톨로지의 활성 노드와 맞물리지 않습니다. 감지된 단서 {topic}{f', {tail}' if tail else ''}를 후보로 보관하고 다음 빌드에서 연결을 시도합니다.",
        ]

    return variants[seed]


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
        answer = _native_no_node_generation(query, active_concepts, intent)
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
            "mode": "native-no-node-sentence-alpha" if not evidence_docs else "native-next-thought-alpha",
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
