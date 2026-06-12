from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.hybrid_network_manager import (
    GraphFragmentEnvelope,
    HybridNetworkManager,
    PeerHint,
    QueryIntent,
    StaticSignalIndex,
)
from app.services.network_config import NetworkConfig


class FailingSignal:
    name = "failing_server_signal"

    async def discover_peers(self, intent: QueryIntent) -> list[PeerHint]:
        raise RuntimeError("server down")


class ReturningPayload:
    name = "fake_edge_payload"

    def __init__(self, fragment: GraphFragmentEnvelope) -> None:
        self.fragment = fragment

    def can_handle(self, hint: PeerHint) -> bool:
        return True

    async def fetch_fragment(self, hint: PeerHint) -> GraphFragmentEnvelope:
        return self.fragment


class FailingPayload:
    name = "fake_p2p_payload"

    def can_handle(self, hint: PeerHint) -> bool:
        return True

    async def fetch_fragment(self, hint: PeerHint) -> GraphFragmentEnvelope:
        raise ConnectionError("p2p unavailable")


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
    assert result["server_dependency"] is False


def test_server_signal_failure_does_not_block_edge_payload() -> None:
    fragment = GraphFragmentEnvelope.create(
        fragment_id="frag-edge",
        source_peer_id="peer-a",
        concept_ids=["concept-a"],
        nodes=[{"id": "concept-a", "label": "Local edge memory"}],
        edges=[],
    )
    manager = HybridNetworkManager(
        config=NetworkConfig(enable_server_signaling=True),
        signal_providers=[
            FailingSignal(),
            StaticSignalIndex([PeerHint(peer_id="peer-a", concept_id="concept-a", endpoint=None, source="local")]),
        ],
        payload_transports=[ReturningPayload(fragment)],
    )

    result = asyncio.run(manager.resolve_cloud_knowledge("GraphRAG edge"))

    assert result["state"] == "completed"
    assert result["fragment_count"] == 1
    assert result["signaling"]["failures"][0]["provider"] == "failing_server_signal"
    assert result["server_dependency"] is False


def test_payload_transport_falls_back_after_p2p_failure() -> None:
    fragment = GraphFragmentEnvelope.create(
        fragment_id="frag-http",
        source_peer_id="peer-b",
        concept_ids=["concept-b"],
        nodes=[{"id": "concept-b", "label": "Fallback memory"}],
        edges=[],
    )
    manager = HybridNetworkManager(
        signal_index=StaticSignalIndex([PeerHint(peer_id="peer-b", concept_id="concept-b", endpoint="http://edge.local")]),
        payload_transports=[FailingPayload(), ReturningPayload(fragment)],
    )

    result = asyncio.run(manager.resolve_cloud_knowledge("fallback path"))

    assert result["state"] == "completed"
    attempts = result["attempts"][0]["transport_attempts"]
    assert attempts[0]["state"] == "failed"
    assert attempts[1]["state"] == "completed"


def test_hybrid_network_status_endpoint() -> None:
    client = TestClient(app)

    response = client.get("/api/network/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["architecture"] == "two_track_hybrid_network"
    assert payload["evolutionary_architecture"] == "local_first_cloud_assisted_network"
    assert payload["uploads_private_payload"] is False
    assert payload["separation"]["server_dependency_for_edge_payload"] is False


def test_edge_broker_status_endpoint_is_local_first() -> None:
    client = TestClient(app)

    response = client.get("/api/network/edge/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["architecture"] == "edge_compute_broker"
    assert payload["cloud_required"] is False
    assert payload["capacity"]["peer_id"]
