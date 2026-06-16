from packages.graph_hub.catalog import list_catalog_items, refresh_catalog


def test_catalog_loads_three_pricing_models_and_graph_hub_name():
    refreshed = refresh_catalog()
    rows = list_catalog_items()
    assert refreshed["product_name"] == "Graph Hub"
    assert {"free", "one_time", "subscription"}.issubset({row["pricing_model"] for row in rows})
    assert "Brain Store" not in str(refreshed)
