from packages.graph_hub.entitlement import check_entitlement, expire_subscription, grant_free_entitlement, mock_purchase_one_time, mock_start_subscription


def test_entitlement_modes():
    assert grant_free_entitlement("atanor_base_free")["status"] == "free"
    assert mock_purchase_one_time("startup_strategy_demo")["status"] == "owned"
    assert mock_start_subscription("korean_writing_demo")["status"] == "active_subscription"
    assert check_entitlement("korean_writing_demo")["attach_allowed"] is True
    assert expire_subscription("korean_writing_demo")["status"] == "expired_subscription"
    assert check_entitlement("korean_writing_demo")["attach_allowed"] is False
