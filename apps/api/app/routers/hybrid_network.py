from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.hybrid_network_manager import resolve_cloud_knowledge


router = APIRouter(prefix="/api/network", tags=["hybrid-network"])


class ResolveNetworkRequest(BaseModel):
    query: str


@router.get("/status")
def hybrid_network_status() -> dict[str, Any]:
    return {
        "state": "ready",
        "architecture": "two_track_hybrid_network",
        "track_1": "supabase_metadata_signal",
        "track_2": "p2p_or_signed_fragment_payload",
        "uploads_raw_query": False,
        "uploads_private_payload": False,
    }


@router.post("/resolve")
async def hybrid_network_resolve(request: ResolveNetworkRequest) -> dict[str, Any]:
    return await resolve_cloud_knowledge(request.query)
