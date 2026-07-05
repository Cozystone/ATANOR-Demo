"""Store contract: every component's WRITE path and READ path must resolve to the same
store. This class of bug has bitten repeatedly (cloud-brain sibling store, frozen promoter
source, pack-vs-graph split): the learner writes somewhere, the answerer reads somewhere
else, and 'learning doesn't accumulate' — invisibly. These assertions make the drift a CI
failure instead of a production mystery."""
from __future__ import annotations

from pathlib import Path


def test_triple_store_write_equals_read():
    """bulk ingest (writer) / answer bridge (reader) / abstain feeder (writer) — one store."""
    import scripts.bulk_ingest_kg as ingest
    import scripts.feed_abstain_queue as feeder
    from packages.graph_scale import answer_bridge

    assert Path(ingest.DEFAULT_ROOT).resolve() == Path(answer_bridge._ROOT).resolve()
    assert Path(feeder.STORE_ROOT).resolve() == Path(answer_bridge._ROOT).resolve()


def test_abstain_queue_single_path():
    """recorder (answer path) and consumer (feeder script) share the queue file."""
    from packages.graph_scale import abstain_queue

    # the consumer drains via the same module, so one constant is the contract
    assert abstain_queue.QUEUE_PATH.name == "abstain_queue.jsonl"
    assert "graph_scale" in str(abstain_queue.QUEUE_PATH)


def test_pack_promoter_writes_what_loader_reads():
    """graph->pack promoter writes PACK_PATH; the live answer loader reads PACK_PATH."""
    from packages.base_brain.models import PACK_PATH as writer_path
    from packages.base_brain.pack_loader import PACK_PATH as reader_path

    assert Path(writer_path).resolve() == Path(reader_path).resolve()
