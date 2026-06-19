from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from guard import check_guard


def test_guard_detects_overclaim_and_support():
    evidence = {"evidence_docs": [{"snippet": "GraphRAG uses KnowledgeGraph and Evidence to ground answers."}]}
    ontology = {"nodes": [{"label": "GraphRAG"}, {"label": "KnowledgeGraph"}]}

    report = check_guard("GraphRAG always guarantees perfect answers.", evidence, ontology)

    assert report["claims"][0]["support"] in {"supported", "weak_support"}
    assert report["warnings"]
    assert report["overall_guard_score"] < 100
