from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.main import app
from app.services.brain_sync import (
    BoundedFragmentAssembler,
    FragmentOrchestrator,
    GraphDeltaCompressor,
    resolve_conflict,
    working_memory_fragments,
)


def test_graph_patch_excludes_private_payload_text() -> None:
    compressor = GraphDeltaCompressor()
    patch = compressor.compress(
        {"nodes": [], "edges": []},
        {
            "nodes": [
                {
                    "id": "concept-alpha",
                    "label": "Private label should not leak",
                    "raw_text": "do not upload this private raw document",
                    "local_path": "C:/secret/private.md",
                }
            ],
            "edges": [
                {
                    "source": "concept-alpha",
                    "relation": "supports",
                    "target": "concept-beta",
                    "weight": 0.7,
                    "content": "secret edge payload",
                }
            ],
            "aliases_added": ["private nickname"],
        },
        privacy_level="public",
        origin_brain_id="test-brain",
    )

    serialized = json.dumps(patch, ensure_ascii=False).lower()
    assert patch["schema_version"] == "atanor.graph-patch.v1"
    assert patch["shareable"] is True
    assert "do not upload" not in serialized
    assert "c:/secret" not in serialized
    assert "private nickname" not in serialized
    assert "alias_hash" in serialized


def test_private_query_disables_cloud_fragment_request() -> None:
    decision = FragmentOrchestrator().decide(
        query="\ub0b4 \uc77c\uae30\ub97c \uc694\uc57d\ud574\uc918",
        local_confidence=0.1,
        graph_density=0.1,
        cloud_allowed=True,
    )

    assert decision.privacy_level == "private"
    assert decision.cloud_weight == 0.0
    assert decision.fragment_requested is False
    assert decision.fragment_reason == "private_query_local_only"


def test_high_local_confidence_reduces_cloud_weight() -> None:
    decision = FragmentOrchestrator().decide(
        query="Explain GraphRAG validation",
        local_confidence=0.94,
        graph_density=0.8,
        evidence_available=True,
    )

    assert decision.local_weight >= 0.92
    assert decision.cloud_weight <= 0.08
    assert decision.fragment_requested is False


def test_low_confidence_public_query_allows_bounded_fragment() -> None:
    decision = FragmentOrchestrator().decide(
        query="What is a newly published public graph paper?",
        local_confidence=0.05,
        graph_density=0.05,
        cloud_allowed=True,
    )

    assert decision.privacy_level == "public"
    assert decision.cloud_allowed is True
    assert decision.fragment_requested is True
    assert decision.cloud_weight > 0.3


def test_cloud_fragment_attaches_to_working_memory_not_permanent_store() -> None:
    fragment = BoundedFragmentAssembler().assemble(
        concept_ids=["concept-public"],
        nodes=[{"id": "concept-public", "type": "concept", "confidence": 0.8}],
        edges=[{"source": "concept-public", "relation": "supports", "target": "concept-local", "weight": 0.4}],
        evidence_summaries=[{"summary": "Public evidence only."}],
    )
    attached = working_memory_fragments.attach(fragment)

    assert attached["storage_layer"] == "working_memory"
    assert attached["permanent_local_brain_write"] is False
    assert attached["fragment_id"] == fragment["fragment_id"]


def test_local_trusted_memory_overrides_cloud_conflict() -> None:
    result = resolve_conflict(
        {"priority": "local_verified", "claim": "local fact"},
        {"priority": "cloud_unverified", "claim": "cloud claim"},
    )

    assert result["winner"] == "local"
    assert result["selected"]["claim"] == "local fact"


def test_brain_sync_status_endpoint_and_orchestration_contract() -> None:
    client = TestClient(app)

    status = client.get("/api/brain-sync/status")
    assert status.status_code == 200
    payload = status.json()
    assert payload["local_brain_primary"] is True
    assert payload["uploads_raw_private_payloads"] is False
    assert payload["external_llm_answer_generation"] is False

    decision = client.post(
        "/api/brain-sync/orchestrate",
        json={
            "query": "public ontology fragment",
            "local_confidence": 0.0,
            "graph_density": 0.0,
            "cloud_allowed": True,
        },
    )
    assert decision.status_code == 200
    assert decision.json()["fragment_requested"] is True
