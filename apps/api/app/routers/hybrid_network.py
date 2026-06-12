from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.edge_compute_broker import default_edge_compute_broker
from app.services.hybrid_network_manager import default_hybrid_network_manager, resolve_cloud_knowledge


router = APIRouter(prefix="/api/network", tags=["hybrid-network"])


class ResolveNetworkRequest(BaseModel):
    query: str


@router.get("/status")
def hybrid_network_status() -> dict[str, Any]:
    return {
        "state": "ready",
        **default_hybrid_network_manager.status(),
        "track_1": "metadata_signaling_server_optional",
        "track_2": "edge_payload_p2p_or_signed_fragment",
        "uploads_raw_query": False,
        "uploads_private_payload": False,
    }


@router.post("/resolve")
async def hybrid_network_resolve(request: ResolveNetworkRequest) -> dict[str, Any]:
    return await resolve_cloud_knowledge(request.query)


@router.get("/edge/status")
def edge_compute_status() -> dict[str, Any]:
    capacity = default_edge_compute_broker.current_capacity()
    return {
        "state": "ready",
        "architecture": "edge_compute_broker",
        "cloud_required": False,
        "capacity": capacity.to_metadata(),
    }


@router.post("/edge/advertise")
async def edge_compute_advertise() -> dict[str, Any]:
    return await default_edge_compute_broker.advertise_if_idle()
