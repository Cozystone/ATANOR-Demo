from packages.graph_hub.cartridge_exporter import export_semantic_cloud_to_cartridge


def test_semantic_cloud_export_uses_proof_store_not_mirror():
    exported = export_semantic_cloud_to_cartridge(
        "semantic_cloud_kubernetes_demo_test",
        "Semantic Cloud Kubernetes Demo Test",
        "test export",
        "free",
        limit_nodes=20,
        limit_edges=40,
    )
    assert exported["provenance"]["source_type"] == "semantic_cloud_proof_store"
    assert exported["provenance"]["old_mirror_snapshot_used"] is False
    assert exported["permissions"]["write_local_brain"] is False
    assert exported["metadata"]["checksum"]
