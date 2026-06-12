from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.hybrid_network_manager import (
    GraphFragmentEnvelope,
    HybridNetworkManager,
    PeerHint,
    StaticSignalIndex,
)


def test_fragment_validation_rejects_invalid_sha256() -> None:
    fragment = GraphFragmentEnvelope.create(
        fragment_id="frag-1",
        source_peer_id="peer-a",
        concept_ids=["concept-a"],
        nodes=[{"id": "concept-a", "label": "GraphRAG"}],
        edges=[],
    )
    fragment.payload_sha256 = "0" * 64

    with pytest.raises(ValueError, match="payload_sha256"):
        fragment.validate()


def test_fragment_validation_accepts_canonical_payload() -> None:
    fragment = GraphFragmentEnvelope.create(
        fragment_id="frag-2",
        source_peer_id="peer-a",
        concept_ids=["concept-a"],
        nodes=[{"id": "concept-a", "label": "GraphRAG"}],
        edges=[{"source": "concept-a", "relation": "uses", "target": "concept-b"}],
    )

    fragment.validate()


def test_resolve_cloud_knowledge_degrades_when_peer_is_unavailable() -> None:
    manager = HybridNetworkManager(
        signal_index=StaticSignalIndex([PeerHint(peer_id="peer-a", concept_id="concept-a", endpoint=None)]),
        timeout_seconds=0.05,
    )

    result = asyncio.run(manager.resolve_cloud_knowledge("GraphRAG 구조"))

    assert result["state"] == "degraded"
    assert result["metadata_only_signal"] is True
    assert result["hint_count"] == 1
    assert result["fragment_count"] == 0
    assert result["attempts"][0]["state"] == "failed"


def test_hybrid_network_status_endpoint() -> None:
    client = TestClient(app)

    response = client.get("/api/network/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["architecture"] == "two_track_hybrid_network"
    assert payload["uploads_private_payload"] is False
