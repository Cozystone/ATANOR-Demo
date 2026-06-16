from __future__ import annotations

from pathlib import Path

from packages.cloud_brain.cloud_node_attachment import (
    attach_bundle,
    cleanup_expired_bundles,
    create_cloud_node_bundle,
    detach_bundle,
    graph_overlay,
    retrieval_trace_for_bundle,
)
from packages.cloud_brain.contributor_node import announce_shards, contributor_status, register_local_contributor
from packages.cloud_brain.ingestion import ensure_fixture_and_ingest
from packages.cloud_brain.prove_distributed_attachment_loop import write_distributed_attachment_loop_proof
from seed_research import run_seed_iteration


def _prepare_public_shard(tmp_path: Path) -> tuple[Path, Path, Path]:
    seed_root = tmp_path / "seed_research"
    cloud_root = tmp_path / "cloud_brain"
    contributor_root = tmp_path / "contributor"
    run_seed_iteration(seed_root)
    ingest = ensure_fixture_and_ingest(seed_root=seed_root, cloud_root=cloud_root)
    assert ingest["ingestion_success"] is True
    return cloud_root, contributor_root, tmp_path / "working_memory" / "cloud_node_bundles"


def test_contributor_node_registers_and_announces_public_shard(tmp_path: Path) -> None:
    cloud_root, contributor_root, _ = _prepare_public_shard(tmp_path)

    peer = register_local_contributor(contributor_root=contributor_root, cloud_root=cloud_root)
    announce = announce_shards(contributor_root=contributor_root, cloud_root=cloud_root)
    status = contributor_status(contributor_root=contributor_root, cloud_root=cloud_root)

    assert peer["peer_kind"] == "local_workstation"
    assert peer["local_brain_private"] is True
    assert peer["raw_private_uploads_allowed"] is False
    assert announce["network_state"] == "active_single_peer"
    assert announce["cloudflare_broker_role"] == "metadata_index_only"
    assert announce["heavy_payload_storage"] == "contributor_node"
    assert status["public_shards_announced"] == 1


def test_cloud_node_bundle_attach_detach_keeps_local_brain_isolated(tmp_path: Path) -> None:
    cloud_root, contributor_root, attachment_root = _prepare_public_shard(tmp_path)
    register_local_contributor(contributor_root=contributor_root, cloud_root=cloud_root)

    bundle = create_cloud_node_bundle("GraphRAG evidence", contributor_root=contributor_root, attachment_root=attachment_root)
    attached = attach_bundle(bundle["bundle_id"], attachment_root=attachment_root)
    overlay = graph_overlay(attachment_root=attachment_root)
    trace = retrieval_trace_for_bundle(attached)
    detached = detach_bundle(bundle["bundle_id"], attachment_root=attachment_root)
    after = graph_overlay(attachment_root=attachment_root)

    assert bundle["writes_to_local_brain"] is False
    assert bundle["nodes"]
    assert bundle["nodes"][0]["visual_layer"] == "cloud_attached"
    assert attached["attached"] is True
    assert overlay["working_memory_overlay"]["cloud_attached_nodes"] == len(bundle["nodes"])
    assert trace["working_memory_overlay"]["source"] == "contributor_node"
    assert trace["working_memory_overlay"]["writes_to_local_brain"] is False
    assert detached["detached"] is True
    assert after["working_memory_overlay"]["cloud_attached_nodes"] == 0


def test_ttl_cleanup_removes_expired_cloud_bundle(tmp_path: Path) -> None:
    cloud_root, contributor_root, attachment_root = _prepare_public_shard(tmp_path)
    register_local_contributor(contributor_root=contributor_root, cloud_root=cloud_root)
    bundle = create_cloud_node_bundle("GraphRAG evidence", contributor_root=contributor_root, attachment_root=attachment_root, ttl_seconds=-1)
    attach_bundle(bundle["bundle_id"], attachment_root=attachment_root)

    cleanup = cleanup_expired_bundles(attachment_root=attachment_root)

    assert cleanup["removed_count"] == 1
    assert graph_overlay(attachment_root=attachment_root)["working_memory_overlay"]["cloud_attached_nodes"] == 0


def test_distributed_attachment_loop_proof_artifacts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    proof = write_distributed_attachment_loop_proof()

    assert proof["result"] == "PASS"
    assert proof["local_brain_state"]["local_total_nodes"] == 0
    assert proof["contributor_network"]["network_state"] == "active_single_peer"
    assert proof["attached_overlay"]["cloud_attached_nodes"] > 0
    assert proof["overlay_after_detach"]["cloud_attached_nodes"] == 0
    assert proof["external_llm_used"] is False
    assert Path("data/cloud_brain/proofs/distributed_attachment_loop_proof.json").exists()
    assert Path("data/cloud_brain/proofs/distributed_attachment_loop_proof.md").exists()
