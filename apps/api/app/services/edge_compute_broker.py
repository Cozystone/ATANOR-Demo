from __future__ import annotations

import asyncio
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

from app.services.network_config import NetworkConfig


def _utc_seconds() -> int:
    return int(time.time())


class CapacitySignalProvider(Protocol):
    name: str

    async def broadcast_edge_availability(self, payload: dict[str, Any]) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class EdgeCapacity:
    peer_id: str
    tier: str
    idle: bool
    endpoint: str | None
    task_types: list[str]
    max_batch_nodes: int
    max_batch_edges: int
    heartbeat_ttl_seconds: int = 90
    generated_at: int = field(default_factory=_utc_seconds)

    def to_metadata(self) -> dict[str, Any]:
        """Return metadata safe to send to a signaling server.

        This does not include raw documents, graph fragments, private prompts,
        or local file paths.
        """

        return asdict(self)


class NullCapacitySignal:
    name = "local_only_capacity_signal"

    async def broadcast_edge_availability(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "state": "local_only",
            "provider": self.name,
            "broadcast": False,
            "reason": "server signaling disabled or unavailable",
            "metadata": payload,
        }


class EdgeComputeBroker:
    """Phase-2 broker for idle edge compute announcements.

    Time-critical orchestration can live in AWS/Supabase later, but heavy batch
    jobs remain edge payload work. If signaling is disabled or fails, local
    operation still continues and no raw payload leaves the machine.
    """

    def __init__(
        self,
        *,
        config: NetworkConfig | None = None,
        capacity_signal: CapacitySignalProvider | None = None,
    ) -> None:
        self.config = config or NetworkConfig.from_env()
        self.capacity_signal = capacity_signal or NullCapacitySignal()

    def current_capacity(self) -> EdgeCapacity:
        tier = self._detect_tier()
        idle = self._is_probably_idle()
        max_nodes = self.config.max_nodes if tier in {"tier_1", "tier_2"} else min(self.config.max_nodes, 512)
        max_edges = self.config.max_edges if tier in {"tier_1", "tier_2"} else min(self.config.max_edges, 2048)
        task_types = ["graph_indexing", "ontology_batch_extract", "fragment_validation"] if idle else ["fragment_validation"]
        return EdgeCapacity(
            peer_id=self.config.local_peer_id,
            tier=tier,
            idle=idle,
            endpoint=self.config.local_payload_endpoint,
            task_types=task_types,
            max_batch_nodes=max_nodes,
            max_batch_edges=max_edges,
        )

    async def advertise_if_idle(self) -> dict[str, Any]:
        capacity = self.current_capacity()
        if not capacity.idle:
            return {
                "state": "not_advertised",
                "reason": "local node is not idle enough for edge compute jobs",
                "capacity": capacity.to_metadata(),
            }
        if not self.config.enable_server_signaling:
            return await NullCapacitySignal().broadcast_edge_availability(capacity.to_metadata())
        try:
            return await asyncio.wait_for(
                self.capacity_signal.broadcast_edge_availability(capacity.to_metadata()),
                timeout=self.config.timeout_seconds,
            )
        except Exception as exc:
            return {
                "state": "signal_failed_local_continues",
                "provider": getattr(self.capacity_signal, "name", self.capacity_signal.__class__.__name__),
                "broadcast": False,
                "error": str(exc),
                "capacity": capacity.to_metadata(),
            }

    @staticmethod
    def _detect_tier() -> str:
        try:
            from neuro_efficiency.hardware_adapter import detect_hardware, resolve_hardware_config

            config = resolve_hardware_config(detect_hardware())
            if config.tier == "target":
                return "tier_1"
            if config.tier == "baseline":
                return "tier_2"
            return "tier_3"
        except Exception:
            return "unknown"

    @staticmethod
    def _is_probably_idle() -> bool:
        override = os.getenv("HOMAGE_EDGE_FORCE_IDLE")
        if override is not None:
            return override.strip().lower() in {"1", "true", "yes", "on"}
        try:
            import psutil  # type: ignore

            return psutil.cpu_percent(interval=0.1) < 35.0 and psutil.virtual_memory().percent < 82.0
        except Exception:
            return True


default_edge_compute_broker = EdgeComputeBroker()
