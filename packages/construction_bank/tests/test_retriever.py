from __future__ import annotations

from dataclasses import replace

from packages.construction_bank.extractor import extract_construction_candidates
from packages.construction_bank.models import ConstructionBank
from packages.construction_bank.retriever import retrieve_constructions


def test_product_retrieval_uses_reviewed_only_and_falls_back_for_candidates() -> None:
    bank = ConstructionBank()
    candidate = extract_construction_candidates([
        {"source_type": "operator_example", "language": "ko", "route_type": "voice_status", "act": "voice_question", "text": "Fish 음성은 로컬 fallback으로 먼저 말합니다.", "source_refs": ["test"]}
    ])[0]
    bank.add(candidate)
    product = retrieve_constructions(route_type="voice_status", act="voice_question", language="ko", audience="product", bank=bank)
    assert product["retrieved_self_grown_construction"] is False
    bank.candidates[candidate.candidate_id] = replace(candidate, status="reviewed")
    product_after_review = retrieve_constructions(route_type="voice_status", act="voice_question", language="ko", audience="product", bank=bank)
    assert product_after_review["retrieved_self_grown_construction"] is True
    assert product_after_review["production_active"] is False
