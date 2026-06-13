from __future__ import annotations

import html
import re
from collections import Counter
from typing import Any, Protocol


AUTONOMOUS_SYSTEM_INSTRUCTION = (
    "You are the ATANOR local synthesis engine. Use only the factual material inside <context>. "
    "Do not call external LLM APIs. Do not invent missing facts. Prefer the highest temporal_weight "
    "when time-series facts conflict, while preserving older facts as historical context."
)

BANNED_SURFACE_SIGNATURES = (
    "payload record says",
    "raw_no_node::",
    "CONTROL_INTENT",
)


class OnDeviceSmoothingBackend(Protocol):
    """Optional local-only smoothing hook."""

    name: str

    def smooth(self, draft: str, context: dict[str, Any]) -> str:
        ...


class DeterministicOnDeviceSmoothingBackend:
    """Dependency-free local surface cleanup.

    This is not an external model and it opens no network path. A future local
    GPU SLM can implement the same protocol.
    """

    name = "local-deterministic-on-device-smoother"

    def smooth(self, draft: str, context: dict[str, Any]) -> str:
        text = _clean(draft)
        text = re.sub(r"\s+([,.!?])", r"\1", text)
        text = re.sub(r"\s{2,}", " ", text)
        text = text.replace(" ,", ",").replace(" .", ".")
        return text.strip()


_DEFAULT_SMOOTHER = DeterministicOnDeviceSmoothingBackend()


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


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


def _infer_intent(query: str) -> str:
    normalized = query.lower()
    if re.search(r"(why|cause|reason)", normalized):
        return "explain_cause"
    if re.search(r"(how|process|flow|step)", normalized):
        return "explain_process"
    if re.search(r"(versus|vs|compare)", normalized):
        return "compare"
    if re.search(r"(who|what|define)", normalized):
        return "define"
    return "answer_grounded"


def _short_hash(value: str) -> str:
    if re.fullmatch(r"[a-fA-F0-9]{64}", value):
        return f"ghost:{value[:12]}"
    return value


def _doc_text(doc: dict[str, Any]) -> str:
    return _clean(doc.get("snippet") or doc.get("text") or doc.get("raw_text"))


def _doc_hash(doc: dict[str, Any]) -> str | None:
    value = _clean(doc.get("hash_key") or doc.get("node_hash"))
    if value:
        return value
    chunk_id = _clean(doc.get("chunk_id"))
    if "#payload" in chunk_id:
        return chunk_id.split("#payload", 1)[0]
    return None


def _doc_kind(doc: dict[str, Any]) -> str:
    metadata = doc.get("metadata")
    if isinstance(metadata, dict):
        return _clean(metadata.get("kind") or metadata.get("type") or "payload")
    return "payload"


def _temporal(doc: dict[str, Any]) -> dict[str, Any]:
    direct = doc.get("temporal")
    if isinstance(direct, dict):
        return dict(direct)
    metadata = doc.get("metadata")
    if isinstance(metadata, dict) and isinstance(metadata.get("temporal"), dict):
        return dict(metadata["temporal"])
    return {}


def _dedupe(items: list[str], *, limit: int) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        normalized = _clean(item)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
        if len(result) >= limit:
            break
    return result


def _sentence_candidates(text: str) -> list[str]:
    pieces = re.split(r"(?<=[.!?])\s+|[\n\r]+", text)
    return [_clean(piece) for piece in pieces if len(_clean(piece)) >= 8]


def _payload_facts(evidence_docs: list[dict[str, Any]], *, limit: int = 5) -> list[dict[str, Any]]:
    candidates: list[tuple[float, int, dict[str, Any]]] = []
    for index, doc in enumerate(evidence_docs):
        text = _doc_text(doc)
        if not text:
            continue
        temporal = _temporal(doc)
        temporal_weight = float(temporal.get("combined_weight") or doc.get("score") or 0.0)
        kind = _doc_kind(doc)
        priority = 3 if kind == "chunk" else 2 if kind in {"phrase", "ontology_node"} else 1
        fact = {
            "id": _clean(doc.get("chunk_id") or doc.get("id") or f"payload-{index}"),
            "kind": kind,
            "hash": _doc_hash(doc),
            "text": text[:700].strip(),
            "temporal": temporal,
            "temporal_weight": round(temporal_weight, 6),
            "temporal_rank": doc.get("temporal_rank") or temporal.get("rank"),
        }
        candidates.append((temporal_weight + priority * 0.15, len(_tokens(text)), fact))
    candidates.sort(key=lambda item: (-item[0], -item[1], item[2]["text"]))
    return [item[2] for item in candidates[:limit]]


def _compact_fact_text(payload_facts: list[dict[str, Any]], *, limit: int = 5) -> list[str]:
    candidates: list[str] = []
    for fact in payload_facts:
        text = _clean(fact.get("text"))
        candidates.extend(_sentence_candidates(text) or [text])
    return _dedupe([item[:300] for item in candidates], limit=limit)


def _xml_text(value: Any) -> str:
    return html.escape(_clean(value), quote=False)


def _node_label(node: dict[str, Any]) -> str:
    return _short_hash(_clean(node.get("label") or node.get("primary_name") or node.get("id")))


class LocalSynthesizer:
    """Local-only synthesis over Ghost Shell payloads and graph relations."""

    engine_name = "ATANOR LocalSynthesizer"

    def __init__(self, smoother: OnDeviceSmoothingBackend | None = _DEFAULT_SMOOTHER) -> None:
        self.smoother = smoother

    def synthesize(
        self,
        query: str,
        evidence_docs: list[dict[str, Any]],
        matched_nodes: list[dict[str, Any]] | None = None,
        matched_edges: list[dict[str, Any]] | None = None,
        graph_paths: list[list[str]] | None = None,
    ) -> dict[str, Any]:
        matched_nodes = matched_nodes or []
        matched_edges = matched_edges or []
        graph_paths = graph_paths or []

        active_concepts = self._active_concepts(query, evidence_docs, matched_nodes)
        relation_facts = self._relation_facts(evidence_docs, matched_nodes, matched_edges, graph_paths)
        payload_facts = _payload_facts(evidence_docs)
        context_block = self._build_context_block(query, active_concepts, relation_facts, payload_facts, graph_paths)
        intent = _infer_intent(query)

        if evidence_docs:
            answer = self._compose_answer(query, active_concepts, relation_facts, payload_facts, intent)
            answer_kind = "local_synthesis"
            mode = "local-ghost-shell-autonomous-alpha"
        else:
            answer = self._no_evidence_answer(query, active_concepts, intent)
            answer_kind = "no_evidence"
            mode = "local-no-evidence-diagnostic-alpha"

        smoothing_context = {
            "query": query,
            "system_instruction": AUTONOMOUS_SYSTEM_INSTRUCTION,
            "context_block": context_block,
            "active_concepts": active_concepts,
            "relation_facts": relation_facts,
            "payload_facts": payload_facts,
            "network_barrier": "sealed_for_generation",
        }
        if self.smoother is not None and answer_kind != "no_evidence":
            answer = self.smoother.smooth(answer, smoothing_context)

        answer = self._sanitize_surface(answer)
        temporal_collision = any(bool((fact.get("temporal") or {}).get("collision_detected")) for fact in payload_facts)
        diagnostics = {
            "intent": intent,
            "payload_count": len(evidence_docs),
            "relation_fact_count": len(relation_facts),
            "payload_fact_count": len(payload_facts),
            "active_concepts": active_concepts,
            "relation_types": sorted({fact["relation"] for fact in relation_facts})[:12],
            "temporal_priority": [
                {
                    "id": fact.get("id"),
                    "timestamp": (fact.get("temporal") or {}).get("timestamp"),
                    "combined_weight": (fact.get("temporal") or {}).get("combined_weight"),
                    "rank": fact.get("temporal_rank"),
                }
                for fact in payload_facts
            ],
            "temporal_collision_detected": temporal_collision,
            "smoother": getattr(self.smoother, "name", None),
            "outbound_http_calls": 0,
            "network_barrier": "sealed_for_generation",
            "banned_surface_signatures": [signature for signature in BANNED_SURFACE_SIGNATURES if signature in answer],
        }

        return {
            "answer": answer,
            "pmv": {
                "intent": intent,
                "topic": active_concepts[0] if active_concepts else query.strip(),
                "stance": "local_payload_grounded_experimental",
                "audience_level": "research",
                "answer_goal": "synthesize one answer from the local Ghost Shell context bundle",
                "required_evidence": True,
                "style": "autonomous_local_prose",
            },
            "claim_plan": [self._claim_line(fact) for fact in relation_facts[:8]],
            "active_concepts": active_concepts,
            "answer_kind": answer_kind,
            "answer_engine": {
                "name": self.engine_name,
                "mode": mode,
                "external_llm": False,
                "cloud_ai_provider": None,
                "network_barrier": "sealed_for_generation",
                "surface_generation": "local_autonomous_context_synthesis",
                "prediction_basis": "ghost_context_bundle_autonomous_synthesis",
                "system_instruction": AUTONOMOUS_SYSTEM_INSTRUCTION,
                "context_block": context_block,
                "on_device_slm_interface": {
                    "available": self.smoother is not None,
                    "role": "local_gpu_text_smoothing_only",
                    "allowed_runtime": "on_device_only",
                },
                "stages": [
                    "query",
                    "ghost_topology_hash_search",
                    "payload_vault_disk_fetch",
                    "temporal_decay_potentiation",
                    "context_block_assembly",
                    "local_autonomous_synthesis",
                    "optional_on_device_slm_smoothing",
                    "output",
                ],
                "diagnostics": diagnostics,
            },
        }

    def _compose_answer(
        self,
        query: str,
        active_concepts: list[str],
        relation_facts: list[dict[str, str]],
        payload_facts: list[dict[str, Any]],
        intent: str,
    ) -> str:
        topic = self._topic(query, active_concepts)
        material = _compact_fact_text(payload_facts)
        relation_lines = [self._relation_phrase(fact) for fact in relation_facts[:4]]
        temporal_collision = any(bool((fact.get("temporal") or {}).get("collision_detected")) for fact in payload_facts)
        if not material:
            return self._no_evidence_answer(query, active_concepts, intent)

        parts: list[str] = []
        if intent == "define":
            parts.append(f"{topic}: ATANOR found this concept inside the local Ghost Shell context.")
        elif intent == "explain_process":
            parts.append(f"{topic}: the local pipeline resolves ghost hashes, fetches vault payloads, then synthesizes the result.")
        elif intent == "explain_cause":
            parts.append(f"{topic}: this follows the Transparent Anomy rule: facts stay traceable, local, and air-gapped.")
        elif intent == "compare":
            parts.append(f"{topic}: ATANOR separates structural memory from the local surface generator.")
        else:
            parts.append(f"{topic}: ATANOR synthesized this from Ghost Shell hashes and Payload Vault context.")

        parts.extend(material[:3])
        if relation_lines:
            parts.append("Graph relations: " + "; ".join(relation_lines[:3]) + ".")
        if temporal_collision:
            latest = payload_facts[0].get("temporal") or {}
            stamp = latest.get("timestamp") or "the highest-weight temporal fact"
            parts.append(f"Temporal collision detected; synthesis prioritized {stamp}.")
        if len(material) > 3:
            parts.append("Additional payloads were retained as secondary context rather than overwritten.")
        return " ".join(parts)

    def _no_evidence_answer(self, query: str, active_concepts: list[str], intent: str) -> str:
        topic = self._topic(query, active_concepts)
        return (
            f"{topic}: ATANOR did not find enough directly connected local evidence in Ghost Shell. "
            "The engine does not call an external LLM to fill missing facts."
        )

    def _topic(self, query: str, active_concepts: list[str]) -> str:
        if active_concepts:
            return active_concepts[0]
        tokens = _tokens(query)
        return tokens[0] if tokens else _clean(query) or "query"

    def _active_concepts(
        self,
        query: str,
        evidence_docs: list[dict[str, Any]],
        matched_nodes: list[dict[str, Any]],
    ) -> list[str]:
        concepts: list[str] = []
        for node in matched_nodes:
            label = _node_label(node)
            if label and label not in concepts:
                concepts.append(label)
        for doc in evidence_docs:
            text = _doc_text(doc)
            if not text:
                continue
            kind = _doc_kind(doc)
            if kind in {"token", "phrase", "node", "ontology_node"}:
                label = _short_hash(text)
                if label not in concepts:
                    concepts.append(label)
        if not concepts:
            for token, _count in Counter(_tokens(query)).most_common(4):
                concepts.append(token)
        return concepts[:8]

    def _relation_facts(
        self,
        evidence_docs: list[dict[str, Any]],
        matched_nodes: list[dict[str, Any]],
        matched_edges: list[dict[str, Any]],
        graph_paths: list[list[str]],
    ) -> list[dict[str, str]]:
        label_by_id = {str(node.get("id")): _node_label(node) for node in matched_nodes if node.get("id")}
        payload_by_hash = {
            doc_hash: _short_hash(_doc_text(doc))
            for doc in evidence_docs
            if (doc_hash := _doc_hash(doc)) and _doc_text(doc)
        }

        def resolve(value: Any) -> str:
            raw = _clean(value)
            return payload_by_hash.get(raw) or label_by_id.get(raw) or _short_hash(raw)

        facts: list[dict[str, str]] = []
        seen: set[tuple[str, str, str]] = set()

        def add(source: Any, relation: Any, target: Any) -> None:
            fact = {
                "source": resolve(source),
                "relation": _clean(relation) or "ghost_edge",
                "target": resolve(target),
            }
            key = (fact["source"], fact["relation"], fact["target"])
            if not fact["source"] or not fact["target"] or key in seen:
                return
            seen.add(key)
            facts.append(fact)

        for edge in matched_edges:
            add(edge.get("source") or edge.get("source_hash"), edge.get("relation") or "ghost_edge", edge.get("target") or edge.get("target_hash"))
            if len(facts) >= 8:
                return facts

        for path in graph_paths:
            if len(path) >= 3:
                add(path[0], path[1], path[2])
            elif len(path) >= 2:
                add(path[0], "ghost_edge", path[1])
            if len(facts) >= 8:
                break
        return facts

    def _claim_line(self, fact: dict[str, str]) -> str:
        return f"{fact.get('source', '')} --{fact.get('relation', 'relates')}--> {fact.get('target', '')}"

    def _relation_phrase(self, fact: dict[str, str]) -> str:
        relation = fact.get("relation", "relates")
        source = fact.get("source", "")
        target = fact.get("target", "")
        return f"{source} --{relation}--> {target}"

    def _build_context_block(
        self,
        query: str,
        active_concepts: list[str],
        relation_facts: list[dict[str, str]],
        payload_facts: list[dict[str, Any]],
        graph_paths: list[list[str]],
    ) -> str:
        concept_lines = "\n".join(f"    <concept>{_xml_text(concept)}</concept>" for concept in active_concepts)
        payload_lines = "\n".join(
            "    "
            + f"<payload id=\"{_xml_text(fact.get('id'))}\" kind=\"{_xml_text(fact.get('kind'))}\""
            + (f" hash=\"{_xml_text(fact.get('hash'))}\"" if fact.get("hash") else "")
            + f" temporal_weight=\"{_xml_text(fact.get('temporal_weight'))}\""
            + f" temporal_rank=\"{_xml_text(fact.get('temporal_rank'))}\""
            + f" timestamp=\"{_xml_text((fact.get('temporal') or {}).get('timestamp'))}\""
            + f">{_xml_text(fact.get('text'))}</payload>"
            for fact in payload_facts
        )
        relation_lines = "\n".join(
            "    "
            + f"<edge source=\"{_xml_text(fact['source'])}\" relation=\"{_xml_text(fact['relation'])}\" target=\"{_xml_text(fact['target'])}\" />"
            for fact in relation_facts
        )
        path_lines = "\n".join(
            f"    <path>{_xml_text(' -> '.join(map(str, path)))}</path>" for path in graph_paths[:8] if path
        )
        return (
            "<context>\n"
            f"  <query>{_xml_text(query)}</query>\n"
            f"  <temporal_policy>preserve older facts; prioritize highest temporal_weight for answer synthesis</temporal_policy>\n"
            f"  <active_concepts>\n{concept_lines}\n  </active_concepts>\n"
            f"  <payloads>\n{payload_lines}\n  </payloads>\n"
            f"  <relations>\n{relation_lines}\n  </relations>\n"
            f"  <graph_paths>\n{path_lines}\n  </graph_paths>\n"
            "</context>"
        )

    def _sanitize_surface(self, answer: str) -> str:
        clean = _clean(answer)
        for signature in BANNED_SURFACE_SIGNATURES:
            clean = clean.replace(signature, "")
        clean = re.sub(r"\s{2,}", " ", clean)
        return clean.strip()
