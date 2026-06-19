from fastapi.testclient import TestClient

from apps.api.app.main import app


client = TestClient(app)


def test_graph_hub_status_and_catalog():
    status = client.get("/api/graph-hub/status")
    assert status.status_code == 200
    payload = status.json()
    assert payload["product_name"] == "Graph Hub"
    assert payload["old_mirror_snapshot_used_as_live_cloud"] is False
    catalog = client.get("/api/graph-hub/catalog")
    assert catalog.status_code == 200
    rows = catalog.json()
    assert {"free", "one_time", "subscription"}.issubset({row["pricing_model"] for row in rows})
    assert "Brain Store" not in str(rows)


def test_graph_hub_export_install_attach_flow():
    exported = client.post("/api/graph-hub/export/semantic-cloud", json={
        "cartridge_id": "semantic_cloud_kubernetes_demo_api",
        "name": "Semantic Cloud Kubernetes API Demo",
        "description": "api export",
        "pricing_model": "free",
        "limit_nodes": 20,
        "limit_edges": 40,
    })
    assert exported.status_code == 200
    assert exported.json()["provenance"]["old_mirror_snapshot_used"] is False
    assert client.post("/api/graph-hub/entitlements/free/semantic_cloud_kubernetes_demo_api").status_code == 200
    installed = client.post("/api/graph-hub/install/semantic_cloud_kubernetes_demo_api")
    assert installed.status_code == 200
    assert installed.json()["local_brain_write"] is False
    attached = client.post("/api/graph-hub/attach/semantic_cloud_kubernetes_demo_api", json={"scope": "session", "read_only": True})
    assert attached.status_code == 200
    assert attached.json()["temporary"] is True
    assert attached.json()["local_brain_write"] is False


def test_graph_cartridge_mount_api_is_manifest_only_and_lazy():
    assert client.post("/api/graph-hub/entitlements/free/software_architect_demo").status_code == 200
    installed = client.post("/api/graph-hub/install/software_architect_demo")
    assert installed.status_code == 200

    mounted = client.post("/api/graph-hub/cartridges/attach/software_architect_demo")
    assert mounted.status_code == 200
    mount_payload = mounted.json()
    assert mount_payload["state"] == "mounted"
    assert mount_payload["loaded_chunks"] == 0
    assert mount_payload["materialized_nodes"] == 0
    assert mount_payload["read_only"] is True
    assert mount_payload["local_write"] is False
    assert mount_payload["cloud_merge"] is False
    assert mount_payload["full_cartridge_loaded_at_attach"] is False

    selected = client.post(
        "/api/graph-hub/cartridges/select-chunks",
        json={"query": "API testing deployment", "max_chunks": 2},
    )
    assert selected.status_code == 200
    selection = selected.json()
    assert selection["state"] == "chunks_selected"
    assert 1 <= len(selection["selected_chunks"]) <= 2
    assert selection["pair_edges_sent"] == 0
    assert selection["local_write"] is False
    assert selection["cloud_merge"] is False

    chunk_id = selection["selected_chunks"][0]["chunk_id"]
    materialized = client.post(
        "/api/graph-hub/cartridges/materialize-chunk",
        json={
            "cartridge_id": "software_architect_demo",
            "chunk_id": chunk_id,
            "max_nodes": 2,
            "max_edges": 1,
        },
    )
    assert materialized.status_code == 200
    payload = materialized.json()
    assert payload["state"] == "materialized"
    assert payload["materialized_nodes"] <= 2
    assert payload["materialized_edges"] <= 1
    assert payload["working_memory_temporary"] is True
    assert payload["local_write"] is False
    assert payload["cloud_merge"] is False
    assert payload["pair_edges_sent"] == 0
    assert payload["full_store_scan"] is False

    detached = client.post("/api/graph-hub/cartridges/detach/software_architect_demo")
    assert detached.status_code == 200
    assert detached.json()["working_memory_cleared"] is True
