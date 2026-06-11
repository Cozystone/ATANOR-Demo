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


def run_ontology(input_dir: str = "data/cleaned", output_dir: str = "data/ontology") -> dict:
    node_counts: Counter[str] = Counter()
    node_types: dict[str, str] = {}
    node_docs: dict[str, set[str]] = defaultdict(set)
    edge_docs: dict[tuple[str, str, str], set[str]] = defaultdict(set)

    for path in _doc_files(input_dir):
        doc_id = path.stem
        text = path.read_text(encoding="utf-8", errors="ignore")
        for label, kind in _concepts(text):
            node_id = _slug(label)
            node_counts[label] += 1
            node_types.setdefault(label, kind)
            node_docs[label].add(doc_id)

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

    nodes = [
        Node(
            id=_slug(label),
            label=label,
            type=node_types.get(label, "concept"),
            count=count,
            confidence=round(min(0.95, 0.45 + count * 0.08 + len(node_docs[label]) * 0.08), 2),
            evidence_doc_ids=sorted(node_docs[label]),
        )
        for label, count in node_counts.most_common(80)
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
