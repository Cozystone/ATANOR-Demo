from __future__ import annotations

from typing import Any

from .models import AUDIT_PATH, read_jsonl, stable_id, utc_now_iso, append_jsonl


def append_graph_hub_audit_event(event_type: str, cartridge_id: str | None = None, details: dict[str, Any] | None = None, actor: str = "local_user") -> dict[str, Any]:
    event = {
        "event_id": stable_id("gha", f"{event_type}:{cartridge_id}:{utc_now_iso()}"),
        "timestamp": utc_now_iso(),
        "event_type": event_type,
        "cartridge_id": cartridge_id,
        "actor": actor,
        "details": details or {},
    }
    append_jsonl(AUDIT_PATH, event)
    return event


def list_graph_hub_audit_events(limit: int = 100) -> list[dict[str, Any]]:
    rows = read_jsonl(AUDIT_PATH)
    return rows[-limit:][::-1]
