from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol


DEFAULT_TIMEOUT_SECONDS = 2.5
DEFAULT_MAX_FRAGMENT_BYTES = 2_000_000
DEFAULT_MAX_NODES = 2_048
DEFAULT_MAX_EDGES = 8_192


def _utc_seconds() -> int:
    return int(time.time())


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def query_vector_footprint(query_vector: list[float] | tuple[float, ...], *, buckets: int = 16) -> str:
    if not query_vector:
        return sha256_hex(b"empty-vector")
    clipped = [max(-1.0, min(1.0, float(value))) for value in query_vector[:512]]
    quantized = [int(round(value * buckets)) for value in clipped]
    return sha256_hex(canonical_json_bytes({"dims": len(clipped), "q": quantized}))


def query_text_footprint(query: str) -> str:
    tokens = [token for token in query.lower().replace("_", " ").split() if token]
    return sha256_hex(canonical_json_bytes({"kind": "query-text", "tokens": tokens[:16], "length": len(query)}))


@dataclass(frozen=True)
class PeerHint:
    peer_id: str
    concept_id: str
    endpoint: str | None = None
    score: float = 0.0
    transport: str = "p2p"
    expires_at: int | None = None

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "PeerHint":
        return cls(
            peer_id=str(value.get("peer_id") or ""),
            concept_id=str(value.get("concept_id") or value.get("concept_ids") or ""),
            endpoint=str(value["endpoint"]) if value.get("endpoint") else None,
            score=float(value.get("score") or value.get("confidence") or 0.0),
            transport=str(value.get("transport") or "p2p"),
            expires_at=int(value["expires_at"]) if value.get("expires_at") else None,
        )

    def is_fresh(self) -> bool:
        return self.expires_at is None or self.expires_at > _utc_seconds()


@dataclass
class GraphFragmentEnvelope:
    fragment_id: str
    source_peer_id: str
    concept_ids: list[str]
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    payload_sha256: str
    schema_version: str = "homage.graph-fragment.v1"
    created_at: int = field(default_factory=_utc_seconds)
    expires_at: int | None = None
    signature: str | None = None
    compression: str = "none"

    @property
    def payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "fragment_id": self.fragment_id,
            "source_peer_id": self.source_peer_id,
            "concept_ids": self.concept_ids,
            "nodes": self.nodes,
            "edges": self.edges,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "compression": self.compression,
        }

    @classmethod
    def create(
        cls,
        *,
        fragment_id: str,
        source_peer_id: str,
        concept_ids: list[str],
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        signing_key: str | None = None,
        expires_at: int | None = None,
    ) -> "GraphFragmentEnvelope":
        draft = cls(
            fragment_id=fragment_id,
            source_peer_id=source_peer_id,
            concept_ids=concept_ids,
            nodes=nodes,
            edges=edges,
            payload_sha256="",
            expires_at=expires_at,
        )
        payload = canonical_json_bytes(draft.payload)
        digest = sha256_hex(payload)
        signature = sign_payload(digest, signing_key) if signing_key else None
        draft.payload_sha256 = digest
        draft.signature = signature
        return draft

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "GraphFragmentEnvelope":
        return cls(
            fragment_id=str(value.get("fragment_id") or ""),
            source_peer_id=str(value.get("source_peer_id") or value.get("peer_id") or ""),
            concept_ids=[str(item) for item in value.get("concept_ids") or []],
            nodes=list(value.get("nodes") or []),
            edges=list(value.get("edges") or []),
            payload_sha256=str(value.get("payload_sha256") or ""),
            schema_version=str(value.get("schema_version") or "homage.graph-fragment.v1"),
            created_at=int(value.get("created_at") or _utc_seconds()),
            expires_at=int(value["expires_at"]) if value.get("expires_at") else None,
            signature=str(value["signature"]) if value.get("signature") else None,
            compression=str(value.get("compression") or "none"),
        )

    def validate(
        self,
        *,
        signing_key: str | None = None,
        max_bytes: int = DEFAULT_MAX_FRAGMENT_BYTES,
        max_nodes: int = DEFAULT_MAX_NODES,
        max_edges: int = DEFAULT_MAX_EDGES,
    ) -> None:
        if self.schema_version != "homage.graph-fragment.v1":
            raise ValueError(f"unsupported fragment schema: {self.schema_version}")
        if not self.fragment_id or not self.source_peer_id:
            raise ValueError("fragment_id and source_peer_id are required")
        if self.expires_at is not None and self.expires_at <= _utc_seconds():
            raise ValueError("fragment has expired")
        if self.compression != "none":
            raise ValueError(f"unsupported compression: {self.compression}")
        if len(self.nodes) > max_nodes:
            raise ValueError(f"fragment nodes exceed limit: {len(self.nodes)} > {max_nodes}")
        if len(self.edges) > max_edges:
            raise ValueError(f"fragment edges exceed limit: {len(self.edges)} > {max_edges}")
        payload = canonical_json_bytes(self.payload)
        if len(payload) > max_bytes:
            raise ValueError(f"fragment bytes exceed limit: {len(payload)} > {max_bytes}")
        actual = sha256_hex(payload)
        if not hmac.compare_digest(actual, self.payload_sha256):
            raise ValueError("invalid fragment payload_sha256")
        if signing_key:
            expected = sign_payload(self.payload_sha256, signing_key)
            if not self.signature or not hmac.compare_digest(expected, self.signature):
                raise ValueError("invalid fragment signature")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def sign_payload(payload_sha256: str, signing_key: str | None) -> str:
    if not signing_key:
        raise ValueError("signing_key is required")
    digest = hmac.new(signing_key.encode("utf-8"), payload_sha256.encode("ascii"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


class SignalIndex(Protocol):
    async def broadcast_query_intent(self, query_vector: list[float]) -> list[PeerHint]:
        ...


class SupabaseSignalIndex:
    """Metadata-only peer discovery over Supabase.

    The raw query and heavy ontology payload never go to Supabase. Only a
    coarse vector footprint is sent so the central service acts as a lightweight
    signaling/index server.
    """

    def __init__(
        self,
        *,
        url: str | None = None,
        key: str | None = None,
        table: str = "homage_peer_index",
    ) -> None:
        self.url = url or os.getenv("SUPABASE_URL")
        self.key = key or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
        self.table = os.getenv("HOMAGE_SUPABASE_PEER_TABLE", table)
        self._client: Any | None = None

    @property
    def configured(self) -> bool:
        return bool(self.url and self.key)

    def _client_or_none(self) -> Any | None:
        if self._client is not None:
            return self._client
        if not self.configured:
            return None
        try:
            from supabase import create_client  # type: ignore

            self._client = create_client(str(self.url), str(self.key))
            return self._client
        except Exception:
            return None

    async def broadcast_query_intent(self, query_vector: list[float]) -> list[PeerHint]:
        footprint = query_vector_footprint(query_vector)
        client = self._client_or_none()
        if client is None:
            return []

        def _query() -> list[dict[str, Any]]:
            response = (
                client.table(self.table)
                .select("peer_id,concept_id,endpoint,score,transport,expires_at")
                .eq("vector_footprint", footprint)
                .order("score", desc=True)
                .limit(8)
                .execute()
            )
            return list(getattr(response, "data", None) or [])

        rows = await asyncio.to_thread(_query)
        return [hint for hint in (PeerHint.from_mapping(row) for row in rows) if hint.peer_id and hint.concept_id and hint.is_fresh()]


class P2PTransport(Protocol):
    async def fetch_p2p_subgraph(self, peer_id: str, concept_id: str) -> GraphFragmentEnvelope:
        ...


class Libp2pTransport:
    """P2P-ready transport facade.

    The Python libp2p package is optional and not stable enough to make the
    process depend on it at import time. A future Tauri/Rust sidecar can
    implement the same method over rust-libp2p without changing the resolver.
    """

    async def fetch_p2p_subgraph(self, peer_id: str, concept_id: str) -> GraphFragmentEnvelope:
        try:
            import libp2p  # type: ignore  # noqa: F401
        except Exception as exc:
            raise ConnectionError("python libp2p transport is unavailable") from exc
        raise NotImplementedError("libp2p dial/request protocol is not configured for this peer")


class HttpFallbackTransport:
    def __init__(
        self,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        signing_key: str | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.signing_key = signing_key or os.getenv("HOMAGE_FRAGMENT_SIGNING_KEY")

    async def fetch_from_endpoint(self, endpoint: str, peer_id: str, concept_id: str) -> GraphFragmentEnvelope:
        url = self._build_url(endpoint, peer_id, concept_id)

        def _fetch() -> dict[str, Any]:
            request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "Homage/0.1"})
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                data = response.read(DEFAULT_MAX_FRAGMENT_BYTES + 1)
            if len(data) > DEFAULT_MAX_FRAGMENT_BYTES:
                raise ValueError("fallback fragment response exceeded byte limit")
            return json.loads(data.decode("utf-8"))

        try:
            payload = await asyncio.wait_for(asyncio.to_thread(_fetch), timeout=self.timeout_seconds + 0.5)
        except (asyncio.TimeoutError, urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            raise ConnectionError(f"http fallback failed for peer {peer_id}") from exc
        envelope = GraphFragmentEnvelope.from_mapping(payload)
        envelope.validate(signing_key=self.signing_key)
        return envelope

    @staticmethod
    def _build_url(endpoint: str, peer_id: str, concept_id: str) -> str:
        base = endpoint.rstrip("/")
        query = urllib.parse.urlencode({"peer_id": peer_id, "concept_id": concept_id})
        return f"{base}/api/cloud-brain/fragment?{query}"


class StaticSignalIndex:
    def __init__(self, hints: list[PeerHint] | None = None) -> None:
        self.hints = hints or []

    async def broadcast_query_intent(self, query_vector: list[float]) -> list[PeerHint]:
        return [hint for hint in self.hints if hint.is_fresh()]


class HybridNetworkManager:
    def __init__(
        self,
        *,
        signal_index: SignalIndex | None = None,
        p2p_transport: P2PTransport | None = None,
        fallback_transport: HttpFallbackTransport | None = None,
        signing_key: str | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.signal_index = signal_index or SupabaseSignalIndex()
        self.p2p_transport = p2p_transport or Libp2pTransport()
        self.fallback_transport = fallback_transport or HttpFallbackTransport(signing_key=signing_key, timeout_seconds=timeout_seconds)
        self.signing_key = signing_key or os.getenv("HOMAGE_FRAGMENT_SIGNING_KEY")
        self.timeout_seconds = timeout_seconds

    async def broadcast_query_intent(self, query_vector: list[float]) -> list[PeerHint]:
        return await self.signal_index.broadcast_query_intent(query_vector)

    async def fetch_p2p_subgraph(self, peer_id: str, concept_id: str) -> GraphFragmentEnvelope:
        envelope = await asyncio.wait_for(
            self.p2p_transport.fetch_p2p_subgraph(peer_id, concept_id),
            timeout=self.timeout_seconds,
        )
        envelope.validate(signing_key=self.signing_key)
        return envelope

    async def resolve_cloud_knowledge(self, query: str) -> dict[str, Any]:
        query_vector = self._query_to_vector(query)
        hints = await self.broadcast_query_intent(query_vector)
        attempts: list[dict[str, Any]] = []
        fragments: list[dict[str, Any]] = []

        for hint in hints[:8]:
            attempt = {"peer_id": hint.peer_id, "concept_id": hint.concept_id, "transport": hint.transport, "state": "pending"}
            try:
                envelope = await self.fetch_p2p_subgraph(hint.peer_id, hint.concept_id)
                attempt["state"] = "p2p_completed"
                fragments.append(envelope.to_dict())
                attempts.append(attempt)
                continue
            except Exception as exc:
                attempt["p2p_error"] = str(exc)

            if hint.endpoint:
                try:
                    envelope = await self.fallback_transport.fetch_from_endpoint(hint.endpoint, hint.peer_id, hint.concept_id)
                    attempt["state"] = "http_fallback_completed"
                    fragments.append(envelope.to_dict())
                except Exception as exc:
                    attempt["state"] = "failed"
                    attempt["fallback_error"] = str(exc)
            else:
                attempt["state"] = "failed"
            attempts.append(attempt)

        return {
            "state": "completed" if fragments else "degraded",
            "query_footprint": query_text_footprint(query),
            "metadata_only_signal": True,
            "hint_count": len(hints),
            "fragment_count": len(fragments),
            "fragments": fragments,
            "attempts": attempts,
            "fallback_policy": "p2p_first_then_http_fragment_endpoint",
        }

    @staticmethod
    def _query_to_vector(query: str) -> list[float]:
        footprint = query_text_footprint(query)
        values: list[float] = []
        for index in range(0, min(len(footprint), 64), 2):
            byte = int(footprint[index : index + 2], 16)
            values.append((byte / 127.5) - 1.0)
        return values


default_hybrid_network_manager = HybridNetworkManager()


async def broadcast_query_intent(query_vector: list[float]) -> list[PeerHint]:
    return await default_hybrid_network_manager.broadcast_query_intent(query_vector)


async def fetch_p2p_subgraph(peer_id: str, concept_id: str) -> GraphFragmentEnvelope:
    return await default_hybrid_network_manager.fetch_p2p_subgraph(peer_id, concept_id)


async def resolve_cloud_knowledge(query: str) -> dict[str, Any]:
    return await default_hybrid_network_manager.resolve_cloud_knowledge(query)
