from __future__ import annotations

from typing import Any

from .models import ConstructionBank, get_default_construction_bank
from .rhfc_adapter import rank_with_cleanup


def retrieve_constructions(
    *,
    route_type: str,
    language: str = "ko",
    act: str | None = None,
    audience: str = "product",
    grounding_context: dict[str, Any] | None = None,
    emotion_policy_bias: dict[str, Any] | None = None,
    recent_output_history: list[str] | None = None,
    bank: ConstructionBank | None = None,
    limit: int = 3,
) -> dict[str, Any]:
    del grounding_context, emotion_policy_bias
    bank = bank or get_default_construction_bank()
    reviewed_only = audience != "lab"
    candidates = bank.retrieve(route_type=route_type, act=act, language=language, reviewed_only=reviewed_only)
    openings = tuple((item or "")[:18].lower() for item in (recent_output_history or [])[-5:])
    ranked = rank_with_cleanup(candidates, route_type=route_type, recent_openings=openings)
    selected = ranked[:limit]
    top = selected[0][0] if selected else None
    return {
        "retrieved_self_grown_construction": bool(top),
        "candidate_status": top.status if top else "none",
        "construction_candidate_id": top.candidate_id if top else None,
        "production_active": False,
        "fallback_to_hand_authored": top is None,
        "hand_authored_construction_used": top is None,
        "hand_authored_construction_used_disclosed": True,
        "adapter_status": selected[0][1].adapter_status if selected else "local_cleanup_scoring",
        "top_candidates": [
            {
                **candidate.to_dict(),
                "cleanup": cleanup.to_dict(),
            }
            for candidate, cleanup in selected
        ],
    }
