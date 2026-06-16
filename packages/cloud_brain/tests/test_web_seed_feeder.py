from __future__ import annotations

import json
from pathlib import Path

from packages.cloud_brain.web_seed_feeder import (
    DEFAULT_STATE,
    feeder_status,
    is_safe_public_url,
    run_once,
    write_json,
)


def test_url_safety_rejects_private_and_local_targets() -> None:
    rejected = [
        "http://localhost:8500/api",
        "http://127.0.0.1:8500/api",
        "http://192.168.0.10/page",
        "file:///C:/secret.txt",
        "ftp://example.com/public.txt",
        "https://example.com/login",
        "C:\\Users\\private\\payload.md",
    ]
    for url in rejected:
        ok, _ = is_safe_public_url(url)
        assert ok is False

    ok, reason = is_safe_public_url("https://example.com/public-page")
    assert ok is True
    assert reason is None


def test_disabled_feeder_skips_sources(tmp_path: Path) -> None:
    root = tmp_path / "cloud_brain"
    write_json(
        root / "web_seed_sources.json",
        [
            {
                "source_id": "enabled_source",
                "name": "Enabled",
                "url": "https://example.com/public",
                "enabled": True,
                "source_type": "public_web",
                "trust_tier": "low",
                "crawl_interval_minutes": 1440,
                "last_fetched_at": None,
            }
        ],
    )
    write_json(root / "web_seed_feeder_state.json", {**DEFAULT_STATE, "enabled": False})

    result = run_once(root, fetcher=lambda url: "public text " * 20)

    assert result.status == "disabled"
    assert not list((root / "inbox").glob("*.json"))


def test_enabled_public_source_creates_candidate_fragment(tmp_path: Path) -> None:
    root = tmp_path / "cloud_brain"
    write_json(
        root / "web_seed_sources.json",
        [
            {
                "source_id": "public_seed",
                "name": "Public Seed",
                "url": "https://example.com/public",
                "enabled": True,
                "source_type": "public_web",
                "trust_tier": "medium",
                "crawl_interval_minutes": 1440,
                "last_fetched_at": None,
            }
        ],
    )
    write_json(root / "web_seed_feeder_state.json", {**DEFAULT_STATE, "enabled": True})

    result = run_once(root, fetcher=lambda url: "GraphRAG public evidence routing validates Cloud Brain fragments. " * 4)
    fragments = list((root / "inbox").glob("candidate_*.json"))

    assert result.status == "created_fragments"
    assert result.fragments_created == 1
    assert len(fragments) == 1
    fragment = json.loads(fragments[0].read_text(encoding="utf-8"))
    assert fragment["source_scope"] == "cloud"
    assert fragment["privacy_scope"] == "public"
    assert fragment["ingestion_state"] == "pending"
    assert fragment["created_by"] == "cloud_brain_web_seed_feeder"
    assert not (tmp_path / "data" / "memory").exists()


def test_duplicate_content_hash_is_skipped(tmp_path: Path) -> None:
    root = tmp_path / "cloud_brain"
    source = {
        "source_id": "public_seed",
        "name": "Public Seed",
        "url": "https://example.com/public",
        "enabled": True,
        "source_type": "public_web",
        "trust_tier": "medium",
        "crawl_interval_minutes": 0,
        "last_fetched_at": None,
    }
    write_json(root / "web_seed_sources.json", [source])
    write_json(root / "web_seed_feeder_state.json", {**DEFAULT_STATE, "enabled": True})

    text = "Cloud Brain duplicate public fragment candidate should not be written twice. " * 4
    first = run_once(root, fetcher=lambda url: text)
    write_json(root / "web_seed_sources.json", [{**source, "last_fetched_at": None}])
    second = run_once(root, fetcher=lambda url: text)

    assert first.fragments_created == 1
    assert second.fragments_created == 0
    assert second.status == "no_new_payload"
    assert len(list((root / "inbox").glob("candidate_*.json"))) == 1


def test_feeder_status_reports_public_cloud_candidate_policy(tmp_path: Path) -> None:
    root = tmp_path / "cloud_brain"
    status = feeder_status(root)

    assert status["enabled"] is False
    assert status["writes_local_brain"] is False
    assert status["privacy_scope"] == "public_cloud_candidates_only"

