from __future__ import annotations

from packages.autonomy_kernel.deficit import compute_deficit
from packages.autonomy_kernel.event_stream import utc_now
from packages.autonomy_kernel.models import SelfModelSnapshot, WorldModelSnapshot


def test_deficit_scores_bounded() -> None:
    world = WorldModelSnapshot("w", 1, 1, 1, ["q"], [{"severity": 0.8}], [{"confidence": 0.3}], utc_now())
    self_model = SelfModelSnapshot("s", 0, ["goal"], [], {"disk_free_gib": 5, "ram_free_gib": 1}, ["promotion gate missing"], [], utc_now())
    signals = compute_deficit(world, self_model)
    assert signals
    assert all(0.0 <= signal.severity <= 1.0 for signal in signals)
    assert all(0.0 <= signal.energy <= 1.0 for signal in signals)
    assert {signal.deficit_type for signal in signals} >= {"knowledge_gap", "resource_pressure", "unresolved_user_goal"}

