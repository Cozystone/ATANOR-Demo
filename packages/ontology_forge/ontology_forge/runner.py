from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path


TECH_STOPWORDS = {
    "the", "and", "for", "with", "from", "this", "that", "into", "data",
    "text", "docs", "document", "documents", "system", "using",
}

ACTION_HINTS = {
    "use",
    "uses",
    "using",
    "used",
    "build",
    "builds",
    "built",
    "create",
    "creates",
    "created",
    "extract",
    "extracts",
    "extracted",
    "retrieve",
    "retrieves",
    "retrieved",
    "traverse",
    "traverses",
    "traversed",
    "improve",
    "improves",
    "improved",
    "reduce",
    "reduces",
    "reduced",
    "require",
    "requires",
    "required",
    "contain",
    "contains",
    "contained",
    "route",
    "routes",
    "routed",
    "learn",
    "learns",
    "learned",
    "measure",
    "measures",
    "measured",
    "connect",
    "connects",
    "connected",
}

RELATION_PATTERNS = [
    (re.compile(r"\b([A-Z][A-Za-z0-9_-]{2,})\s+is\s+a\s+([A-Z][A-Za-z0-9_-]{2,})\b"), "is_a"),
    (re.compile(r"\b([A-Z][A-Za-z0-9_-]{2,})\s+uses\s+([A-Z][A-Za-z0-9_-]{2,})\b"), "uses"),
    (re.compile(r"\b([A-Z][A-Za-z0-9_-]{2,})\s+improves\s+([A-Z][A-Za-z0-9_-]{2,})\b"), "improves"),
    (re.compile(r"\b([A-Z][A-Za-z0-9_-]{2,})\s+reduces\s+([A-Z][A-Za-z0-9_-]{2,})\b"), "reduces"),
    (re.compile(r"\b([A-Z][A-Za-z0-9_-]{2,})\s+requires\s+([A-Z][A-Za-z0-9_-]{2,})\b"), "requires"),
    (re.compile(r"\b([A-Z][A-Za-z0-9_-]{2,})\s+contains\s+([A-Z][A-Za-z0-9_-]{2,})\b"), "contains"),
    (re.compile(r"([A-Za-z가-힣][A-Za-z0-9가-힣_-]{1,})\s*(?:은|는)\s*([A-Za-z가-힣][A-Za-z0-9가-힣_-]{1,})\s*(?:이다|입니다)"), "is_a"),
    (re.compile(r"([A-Za-z가-힣][A-Za-z0-9가-힣_-]{1,}).{0,8}([A-Za-z가-힣][A-Za-z0-9가-힣_-]{1,}).{0,8}사용"), "uses"),
    (re.compile(r"([A-Za-z가-힣][A-Za-z0-9가-힣_-]{1,}).{0,8}([A-Za-z가-힣][A-Za-z0-9가-힣_-]{1,}).{0,8}개선"), "improves"),
    (re.compile(r"([A-Za-z가-힣][A-Za-z0-9가-힣_-]{1,}).{0,8}([A-Za-z가-힣][A-Za-z0-9가-힣_-]{1,}).{0,8}(?:감소|줄)"), "reduces"),
    (re.compile(r"([A-Za-z가-힣][A-Za-z0-9가-힣_-]{1,}).{0,8}([A-Za-z가-힣][A-Za-z0-9가-힣_-]{1,}).{0,8}필요"), "requires"),
]


@dataclass
class Node:
    id: str
    label: str
    type: str
    count: int
    confidence: float
    evidence_doc_ids: list[str]


@dataclass
class Edge:
    source: str
    relation: str
    target: str
    confidence: float
    evidence_doc_ids: list[str]
    status: str = "candidate"


def _slug(label: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9가-힣_-]+", "-", label.strip()).strip("-").lower()
    return cleaned[:64] or "concept"


def _doc_files(input_dir: str) -> list[Path]:
    root = Path(input_dir)
    root.mkdir(parents=True, exist_ok=True)
    return sorted([*root.rglob("*.txt"), *root.rglob("*.md")])


def _concepts(text: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for heading in re.findall(r"(?m)^#{1,6}\s+(.+)$", text):
        label = heading.strip(" #`*")
        if len(label) > 2:
            found.append((label[:80], "heading"))

    for token in re.findall(r"\b[A-Z][A-Za-z0-9_-]{2,}\b|`([A-Za-z_][A-Za-z0-9_]{2,})`", text):
        label = token if isinstance(token, str) else token[0]
        if label and label.lower() not in TECH_STOPWORDS:
            found.append((label, "concept"))

    words = re.findall(r"[A-Za-z가-힣][A-Za-z0-9가-힣_-]{2,}", text)
    counts = Counter(w for w in words if w.lower() not in TECH_STOPWORDS)
    for word, count in counts.items():
        if count >= 2:
            found.append((word, "keyword"))
    return found


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?。！？])\s+|[\r\n]+", text.strip())
    return [part.strip() for part in parts if part.strip()]


def _sentence_tokens(sentence: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z가-힣][A-Za-z0-9가-힣_-]{1,}", sentence)
    return [token for token in tokens if token.lower() not in TECH_STOPWORDS][:18]


def _is_action_token(token: str) -> bool:
    lowered = token.lower().strip("-_")
    if lowered in ACTION_HINTS:
        return True
    if lowered.endswith(("ing", "ed")) and len(lowered) > 4:
        return True
    if re.search(r"(한다|했다|된다|시킨다)$", token):
        return True
    return bool(re.search(r"(사용|생성|추출|검색|검증|학습|측정|연결|확장|개선|감소|요구|라우팅)$", token))


def _add_node(
    label: str,
    kind: str,
    doc_id: str,
    node_counts: Counter[str],
    node_types: dict[str, str],
    node_docs: dict[str, set[str]],
) -> None:
    node_counts[label] += 1
    if node_types.get(label) != "concept":
        node_types.setdefault(label, kind)
    node_docs[label].add(doc_id)


def _add_sentence_structure(
    sentence: str,
    doc_id: str,
    node_counts: Counter[str],
    node_types: dict[str, str],
    node_docs: dict[str, set[str]],
    edge_docs: dict[tuple[str, str, str], set[str]],
) -> None:
    tokens = _sentence_tokens(sentence)
    if len(tokens) < 2:
        return

    for token in tokens:
        _add_node(token, "verb" if _is_action_token(token) else "keyword", doc_id, node_counts, node_types, node_docs)

    for index, token in enumerate(tokens[:-1]):
        nxt = tokens[index + 1]
        phrase = f"{token} {nxt}"
        _add_node(phrase, "phrase", doc_id, node_counts, node_types, node_docs)
        edge_docs[(_slug(token), "precedes", _slug(nxt))].add(doc_id)
        edge_docs[(_slug(token), "forms_phrase", _slug(phrase))].add(doc_id)
        edge_docs[(_slug(phrase), "contains", _slug(nxt))].add(doc_id)

    for index, token in enumerate(tokens):
        if not _is_action_token(token):
            continue
        left = next((tokens[left_index] for left_index in range(index - 1, -1, -1) if not _is_action_token(tokens[left_index])), None)
        right = next((tokens[right_index] for right_index in range(index + 1, len(tokens)) if not _is_action_token(tokens[right_index])), None)
        if left:
            edge_docs[(_slug(left), "does", _slug(token))].add(doc_id)
        if right:
            edge_docs[(_slug(token), "acts_on", _slug(right))].add(doc_id)

    for index, token in enumerate(tokens[:12]):
        for other in tokens[index + 2 : min(len(tokens), index + 5)]:
            if token != other:
                edge_docs[(_slug(token), "co_occurs", _slug(other))].add(doc_id)


def _node_type_for(label: str, node_types: dict[str, str]) -> str:
    stored_type = node_types.get(label, "concept")
    if stored_type == "phrase":
        return stored_type
    return "verb" if _is_action_token(label) else stored_type


def run_ontology(input_dir: str = "data/cleaned", output_dir: str = "data/ontology") -> dict:
    node_counts: Counter[str] = Counter()
    node_types: dict[str, str] = {}
    node_docs: dict[str, set[str]] = defaultdict(set)
    edge_docs: dict[tuple[str, str, str], set[str]] = defaultdict(set)

    for path in _doc_files(input_dir):
        doc_id = path.stem
        text = path.read_text(encoding="utf-8", errors="ignore")
        for label, kind in _concepts(text):
            _add_node(label, kind, doc_id, node_counts, node_types, node_docs)

        for pattern, relation in RELATION_PATTERNS:
            for match in pattern.finditer(text):
                source_label, target_label = match.group(1), match.group(2)
                source_id, target_id = _slug(source_label), _slug(target_label)
                node_counts[source_label] += 1
                node_counts[target_label] += 1
                node_types.setdefault(source_label, "concept")
                node_types.setdefault(target_label, "concept")
                node_docs[source_label].add(doc_id)
                node_docs[target_label].add(doc_id)
                edge_docs[(source_id, relation, target_id)].add(doc_id)

        for sentence in _sentences(text):
            _add_sentence_structure(sentence, doc_id, node_counts, node_types, node_docs, edge_docs)

    nodes = [
        Node(
            id=_slug(label),
            label=label,
            type=_node_type_for(label, node_types),
            count=count,
            confidence=round(min(0.95, 0.45 + count * 0.08 + len(node_docs[label]) * 0.08), 2),
            evidence_doc_ids=sorted(node_docs[label]),
        )
        for label, count in node_counts.most_common(160)
    ]
    node_ids = {node.id for node in nodes}
    edges = [
        Edge(
            source=source,
            relation=relation,
            target=target,
            confidence=round(min(0.9, 0.5 + len(docs) * 0.12), 2),
            evidence_doc_ids=sorted(docs),
        )
        for (source, relation, target), docs in sorted(edge_docs.items())
        if source in node_ids and target in node_ids
    ]
    report = {
        "state": "completed",
        "input_dir": input_dir,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "output_dir": output_dir,
    }

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "nodes.json").write_text(json.dumps([asdict(n) for n in nodes], ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "edges.json").write_text(json.dumps([asdict(e) for e in edges], ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "ontology_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"nodes": [asdict(n) for n in nodes], "edges": [asdict(e) for e in edges], "report": report}
