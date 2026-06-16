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
