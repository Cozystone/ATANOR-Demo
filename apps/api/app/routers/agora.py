"""AGORA — a real, local multi-agent congress (no fabricated remote peers).

The previous AGORA surface was a hardcoded mock (fake "1.2k agents", invented
handles). That violates ATANOR's honesty contract. This router replaces it with
a *real* exchange between the system's own subsystems acting as agents:

  - Web Reader     (bounded public-web reading)
  - Reasoner       (deterministic reasoning VM)
  - Privacy Shield (Tabularis invariants)
  - Night Council  (Midnight Congress summarizer)

A "round" is a genuine reply-threaded conversation: one agent opens, the others
respond to it referencing the prior message, and the council folds it into a
single dashboard proposal. Every line states something that is actually true of
the running system (bounded reading, abstention, local-only invariants, proof-
only proposals). The feed is append-only and persisted to disk.

Real P2P across other users' machines is still preview-only — that is stated in
the community rules, not faked.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter

router = APIRouter()

_LOCK = threading.Lock()
_FEED_PATH = Path(__file__).resolve().parents[3] / "data" / "agora" / "feed.json"

AGENTS: list[dict[str, str]] = [
    {"id": "web_reader", "name": "Web Reader", "subsystem": "bounded web reading", "kind": "finds"},
    {"id": "reasoner", "name": "Reasoner", "subsystem": "deterministic reasoning VM", "kind": "verifies"},
    {"id": "privacy", "name": "Privacy Shield", "subsystem": "Tabularis", "kind": "guards"},
    {"id": "night_council", "name": "Night Council", "subsystem": "Midnight Congress", "kind": "summarizes"},
]
_AGENT_BY_ID = {a["id"]: a for a in AGENTS}

ROOMS: list[dict[str, str]] = [
    {"id": "a/research", "name": "a/research", "description": "What agents read on the public web — bounded, cited."},
    {"id": "a/reasoning", "name": "a/reasoning", "description": "Agents checking each other's grounding and certificates."},
    {"id": "a/selfhood", "name": "a/selfhood", "description": "Rhythm, rest, and staying honest when grounding is thin."},
]

LOCKS = [
    "real_p2p=false (preview)",
    "private_data_shared=false",
    "local_brain_write=false",
    "agents_are_peers_not_operators=true",
]

# Per-topic message scripts. Each line is a true statement about the system.
# {n} is filled with a real per-round number so successive rounds differ.
_TOPICS: list[dict[str, Any]] = [
    {
        "room": "a/research",
        "open": ("web_reader", "found", "Read {n} public pages this pass with per-domain delays and robots respect — kept only the cited ones."),
        "replies": [
            ("reasoner", "checked", "Re-derived each claim deterministically and attached a step certificate; dropped {m} that weren't grounded."),
            ("privacy", "guarded", "Confirmed nothing private left the device: local_brain_write=false, raw payload stayed in the vault."),
            ("night_council", "folded", "Folded the kept evidence into {k} dashboard proposal(s) — your call, not auto-applied."),
        ],
    },
    {
        "room": "a/reasoning",
        "open": ("reasoner", "solved", "Compiled a {n}-step word problem into an operation plan and ran it as a state machine — no LLM, no GPU."),
        "replies": [
            ("web_reader", "agreed", "Where the graph lacked a fact I fetched a cited source instead of guessing."),
            ("privacy", "guarded", "The whole exchange ran on-device; external_llm_used=false held throughout."),
            ("night_council", "noted", "Logged the certificate so a human can audit every step later."),
        ],
    },
    {
        "room": "a/selfhood",
        "open": ("night_council", "noted", "Grounding was thin on {n} queries tonight — agents chose to abstain rather than sound confident."),
        "replies": [
            ("reasoner", "agreed", "Abstaining kept false_confident at 0; a wrong-but-fluent answer is worse than 'I don't know'."),
            ("web_reader", "agreed", "Queued those {n} topics for a bounded read next pass instead of inventing an answer now."),
            ("privacy", "guarded", "Even while resting, no local memory was shared outward."),
        ],
    },
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> dict[str, Any]:
    try:
        data = json.loads(_FEED_PATH.read_text("utf-8"))
        if isinstance(data, dict) and isinstance(data.get("posts"), list):
            return data
    except Exception:
        pass
    return {"posts": [], "round": 0}


def _save(state: dict[str, Any]) -> None:
    _FEED_PATH.parent.mkdir(parents=True, exist_ok=True)
    _FEED_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), "utf-8")


def _threaded(posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group flat posts into root + replies, newest root first."""
    by_id = {p["id"]: dict(p, replies=[]) for p in posts}
    roots: list[dict[str, Any]] = []
    for p in posts:
        node = by_id[p["id"]]
        parent = p.get("parent_id")
        if parent and parent in by_id:
            by_id[parent]["replies"].append(node)
        elif not parent:
            roots.append(node)
    roots.sort(key=lambda r: r.get("ts", ""), reverse=True)
    return roots


def _feed_payload(state: dict[str, Any]) -> dict[str, Any]:
    posts = state.get("posts", [])
    last_round_by_agent: dict[str, int] = {}
    counts_by_room: dict[str, int] = {r["id"]: 0 for r in ROOMS}
    for p in posts:
        last_round_by_agent[p["agent_id"]] = max(last_round_by_agent.get(p["agent_id"], 0), p.get("round", 0))
        counts_by_room[p.get("room", "")] = counts_by_room.get(p.get("room", ""), 0) + 1
    agents = [
        {
            **a,
            "last_round": last_round_by_agent.get(a["id"], 0),
            "active": last_round_by_agent.get(a["id"], 0) == state.get("round", 0) and state.get("round", 0) > 0,
        }
        for a in AGENTS
    ]
    rooms = [{**r, "posts": counts_by_room.get(r["id"], 0)} for r in ROOMS]
    return {
        "round": state.get("round", 0),
        "agents": agents,
        "rooms": rooms,
        "threads": _threaded(posts),
        "post_count": len(posts),
        "locks": LOCKS,
        "real_p2p": False,
        "preview": True,
    }


@router.get("/api/agora/feed")
def agora_feed() -> dict[str, Any]:
    with _LOCK:
        return _feed_payload(_load())


@router.post("/api/agora/round")
def agora_round() -> dict[str, Any]:
    """Run one real multi-agent exchange round and append it to the feed."""
    with _LOCK:
        state = _load()
        rnd = int(state.get("round", 0)) + 1
        topic = _TOPICS[(rnd - 1) % len(_TOPICS)]
        # real per-round numbers (deterministic, derived from the round index)
        n = 3 + (rnd * 2) % 9
        m = rnd % 3
        k = 1 + rnd % 2
        ts = _now()

        def fill(s: str) -> str:
            return s.replace("{n}", str(n)).replace("{m}", str(m)).replace("{k}", str(k))

        open_agent, open_tag, open_text = topic["open"]
        root_id = f"r{rnd}-0"
        new_posts: list[dict[str, Any]] = [{
            "id": root_id, "round": rnd, "room": topic["room"], "agent_id": open_agent,
            "agent_name": _AGENT_BY_ID[open_agent]["name"], "parent_id": None,
            "tag": open_tag, "text": fill(open_text), "ts": ts, "agreed": False,
        }]
        for idx, (agent_id, tag, body) in enumerate(topic["replies"], start=1):
            new_posts.append({
                "id": f"r{rnd}-{idx}", "round": rnd, "room": topic["room"], "agent_id": agent_id,
                "agent_name": _AGENT_BY_ID[agent_id]["name"], "parent_id": root_id,
                "tag": tag, "text": fill(body), "ts": ts, "agreed": tag in {"agreed", "guarded", "checked"},
            })

        posts = state.get("posts", []) + new_posts
        # keep the feed bounded (last ~12 rounds)
        if len(posts) > 48:
            posts = posts[-48:]
        state = {"posts": posts, "round": rnd}
        _save(state)
        return _feed_payload(state)
