from __future__ import annotations

from pathlib import Path
from typing import Any

from .cartridge_format import make_graph_cartridge, write_cartridge
from .models import CATALOG_PATH, GRAPH_HUB_ROOT, cartridge_path, ensure_graph_hub_dirs, read_json, write_json


def _semantic_node(node_id: str, label: str) -> dict[str, Any]:
    return {"id": node_id, "label": label, "source_scope": "cartridge", "trust": 0.72}


def _semantic_edge(edge_id: str, source: str, target: str, relation: str) -> dict[str, Any]:
    return {"id": edge_id, "source": source, "target": target, "relation": relation, "weight": 0.72}


def sample_cartridges() -> list[dict[str, Any]]:
    return [
        make_graph_cartridge(
            cartridge_id="atanor_base_free",
            name="ATANOR Base Free",
            subtitle="Basic ontology anchors for everyday reasoning.",
            description="A small free graph pack with foundational concepts, surface constructions, and reasoning patterns.",
            category="general",
            pricing={"model": "free", "price": None, "currency": "none", "billing_period": "none"},
            tags=["base", "free", "starter"],
            contents={
                "semantic_graph": {
                    "nodes": [_semantic_node("base:evidence", "Evidence"), _semantic_node("base:claim", "Claim")],
                    "edges": [_semantic_edge("base:evidence-supports-claim", "base:evidence", "base:claim", "supports")],
                },
                "surface_graph": {
                    "constructions": [{"id": "direct_concise", "language": "ko", "pattern_family": "concise_answer"}],
                    "discourse_moves": [{"id": "answer_then_reason", "function": "direct_answer"}],
                    "lemma_choices": [],
                    "style_profiles": [{"id": "clear_default", "tone": "clear"}],
                },
                "reasoning_patterns": [{"id": "evidence_before_claim", "name": "Evidence before claim"}],
            },
            provenance={"source_type": "manual_sample", "source_paths": []},
        ),
        make_graph_cartridge(
            cartridge_id="startup_strategy_demo",
            name="Startup Strategy Demo",
            subtitle="Market, customer, moat, pricing, and investor objection frames.",
            description="A compact startup reasoning cartridge for strategy conversations and pitch critique.",
            category="startup",
            pricing={"model": "one_time", "price": 19, "currency": "USD", "billing_period": "none"},
            tags=["startup", "strategy", "pitch"],
            contents={
                "semantic_graph": {
                    "nodes": [_semantic_node("startup:market", "Market"), _semantic_node("startup:moat", "Moat"), _semantic_node("startup:pricing", "Pricing")],
                    "edges": [
                        _semantic_edge("startup:market-informs-pricing", "startup:market", "startup:pricing", "informs"),
                        _semantic_edge("startup:moat-protects-market", "startup:moat", "startup:market", "protects"),
                    ],
                },
                "surface_graph": {
                    "constructions": [{"id": "investor_framing", "language": "en", "pattern_family": "investor_summary"}],
                    "discourse_moves": [{"id": "objection_then_answer", "function": "objection"}],
                    "lemma_choices": [],
                    "style_profiles": [{"id": "boardroom_concise", "tone": "strategic"}],
                },
                "reasoning_patterns": [{"id": "problem_solution_moat", "name": "Problem-solution-moat"}],
            },
            provenance={"source_type": "manual_sample", "source_paths": []},
        ),
        make_graph_cartridge(
            cartridge_id="korean_writing_demo",
            name="Korean Writing Demo",
            subtitle="Natural Korean explanation and transition patterns.",
            description="A subscription demo cartridge for smoother Korean writing surface planning.",
            category="writing",
            pricing={"model": "subscription", "price": 5, "currency": "USD", "billing_period": "monthly", "trial_days": 7},
            tags=["korean", "writing", "surface"],
            contents={
                "semantic_graph": {
                    "nodes": [_semantic_node("writing:clarity", "명료성"), _semantic_node("writing:transition", "전환 표현")],
                    "edges": [_semantic_edge("writing:transition-improves-clarity", "writing:transition", "writing:clarity", "improves")],
                },
                "surface_graph": {
                    "constructions": [{"id": "ko_soft_contrast", "language": "ko", "pattern_family": "soft_contrast"}],
                    "discourse_moves": [{"id": "ko_summary_close", "function": "summary"}],
                    "lemma_choices": [{"concept": "summary", "choices": ["정리하면", "핵심만 말하면"]}],
                    "style_profiles": [{"id": "ko_clean_professional", "tone": "clean"}],
                },
                "repair_rules": [{"id": "avoid_repeated_marker", "review_required": True}],
            },
            provenance={"source_type": "manual_sample", "source_paths": []},
        ),
        make_graph_cartridge(
            cartridge_id="software_architect_demo",
            name="Software Architect Demo",
            subtitle="API, backend, frontend, deployment, testing, and tradeoff frames.",
            description="A practical software architecture cartridge for technical planning and review.",
            category="software",
            pricing={"model": "free", "price": None, "currency": "none", "billing_period": "none"},
            tags=["software", "architecture", "testing"],
            contents={
                "semantic_graph": {
                    "nodes": [_semantic_node("sw:api", "API"), _semantic_node("sw:test", "Testing"), _semantic_node("sw:deployment", "Deployment")],
                    "edges": [
                        _semantic_edge("sw:api-requires-test", "sw:api", "sw:test", "requires"),
                        _semantic_edge("sw:test-supports-deployment", "sw:test", "sw:deployment", "supports"),
                    ],
                },
                "surface_graph": {
                    "constructions": [{"id": "tradeoff_frame", "language": "en", "pattern_family": "architecture_tradeoff"}],
                    "discourse_moves": [{"id": "risk_then_mitigation", "function": "warning"}],
                    "lemma_choices": [],
                    "style_profiles": [{"id": "senior_engineer", "tone": "precise"}],
                },
                "reasoning_patterns": [{"id": "risk_tradeoff_mitigation", "name": "Risk-tradeoff-mitigation"}],
            },
            provenance={"source_type": "manual_sample", "source_paths": []},
        ),
    ]


def ensure_sample_cartridges() -> list[dict[str, Any]]:
    ensure_graph_hub_dirs()
    cartridges: list[dict[str, Any]] = []
    for cartridge in sample_cartridges():
        path = cartridge_path(cartridge["cartridge_id"])
        if not path.exists():
            write_cartridge(path, cartridge)
        cartridges.append(read_json(path, cartridge))
    return cartridges


def build_catalog_item(cartridge: dict[str, Any]) -> dict[str, Any]:
    pricing = cartridge.get("pricing") or {}
    model = str(pricing.get("model") or "free")
    price = pricing.get("price")
    currency = str(pricing.get("currency") or "none")
    period = str(pricing.get("billing_period") or "none")
    if model == "free":
        price_label = "Free"
    elif model == "one_time":
        price_label = f"{currency} {price} once"
    else:
        price_label = f"{currency} {price}/{period}"
    graph = (cartridge.get("contents") or {}).get("semantic_graph") or {}
    return {
        "cartridge_id": cartridge["cartridge_id"],
        "name": cartridge["name"],
        "subtitle": cartridge["subtitle"],
        "category": cartridge["category"],
        "pricing_model": model,
        "price_label": price_label,
        "rating": 4.6 if model != "subscription" else 4.8,
        "downloads": 0,
        "verified_author": bool((cartridge.get("author") or {}).get("verified")),
        "installed": False,
        "owned": model == "free",
        "subscription_active": False,
        "tags": (cartridge.get("metadata") or {}).get("tags") or [],
        "risk_level": (cartridge.get("safety") or {}).get("risk_level", "unknown"),
        "remote_url": None,
        "preview": {
            "semantic_nodes": len(graph.get("nodes") or []),
            "semantic_edges": len(graph.get("edges") or []),
            "default_read_only": bool((cartridge.get("safety") or {}).get("default_read_only", True)),
        },
    }


def refresh_local_catalog() -> dict[str, Any]:
    cartridges = ensure_sample_cartridges()
    items = [build_catalog_item(cartridge) for cartridge in cartridges]
    exported_dir = GRAPH_HUB_ROOT / "exported"
    for path in sorted(exported_dir.glob("*.graphpack.json")):
        payload = read_json(path, None)
        if isinstance(payload, dict) and not any(item["cartridge_id"] == payload.get("cartridge_id") for item in items):
            items.append(build_catalog_item(payload))
    write_json(CATALOG_PATH, {"product_name": "Graph Hub", "items": items})
    return {"product_name": "Graph Hub", "items": items, "catalog_path": str(CATALOG_PATH)}


def find_cartridge_file(cartridge_id: str) -> Path | None:
    for folder in ["cartridges", "exported", "installed"]:
        path = cartridge_path(cartridge_id, folder)
        if path.exists():
            return path
    return None
