from pathlib import Path

import pytest

from packages.graph_hub.cartridge_mount import (
    attach_cartridge_namespace,
    detach_cartridge_namespace,
    materialize_cartridge_chunk,
    select_cartridge_chunks,
)
from packages.graph_hub.entitlement import grant_free_entitlement
from packages.graph_hub.installer import get_installed_cartridge, install_cartridge


def test_manifest_only_mount_does_not_load_full_cartridge(monkeypatch: pytest.MonkeyPatch) -> None:
    grant_free_entitlement("software_architect_demo")
    install_cartridge("software_architect_demo")
    installed = get_installed_cartridge("software_architect_demo")
    assert installed is not None
    installed_path = Path(str(installed["path"])).resolve()

    import packages.graph_hub.cartridge_mount as cartridge_mount

    original_read_json = cartridge_mount.read_json

    def guarded_read_json(path: Path, fallback):
        if Path(path).resolve() == installed_path:
            raise AssertionError("mount attach must not read full cartridge payload")
        return original_read_json(path, fallback)

    monkeypatch.setattr(cartridge_mount, "read_json", guarded_read_json)
    mounted = attach_cartridge_namespace("software_architect_demo")

    assert mounted["state"] == "mounted"
    assert mounted["loaded_chunks"] == 0
    assert mounted["materialized_nodes"] == 0
    assert mounted["full_cartridge_loaded_at_attach"] is False
    assert mounted["read_only"] is True
    assert mounted["local_write"] is False
    assert mounted["cloud_merge"] is False
    assert mounted["attach_ms"] < 100


def test_select_and_materialize_chunk_is_bounded_and_temporary() -> None:
    grant_free_entitlement("software_architect_demo")
    install_cartridge("software_architect_demo")
    mounted = attach_cartridge_namespace("software_architect_demo")

    selected = select_cartridge_chunks("API testing deployment", max_chunks=2)
    assert selected["state"] == "chunks_selected"
    assert 1 <= len(selected["selected_chunks"]) <= 2
    assert selected["local_write"] is False
    assert selected["cloud_merge"] is False
    assert selected["pair_edges_sent"] == 0
    assert selected["wave_budget"]["pair_edges_sent"] == 0

    chunk_id = selected["selected_chunks"][0]["chunk_id"]
    materialized = materialize_cartridge_chunk("software_architect_demo", chunk_id, max_nodes=2, max_edges=1)

    assert materialized["state"] == "materialized"
    assert materialized["materialized_nodes"] <= 2
    assert materialized["materialized_edges"] <= 1
    assert materialized["working_memory_temporary"] is True
    assert materialized["read_only"] is True
    assert materialized["local_write"] is False
    assert materialized["cloud_merge"] is False
    assert materialized["pair_edges_sent"] == 0
    assert materialized["full_store_scan"] is False
    assert materialized["wave_budget"]["nodes_materialized"] <= 2

    detached = detach_cartridge_namespace(mounted["cartridge_id"])
    assert detached["state"] == "detached"
    assert detached["working_memory_cleared"] is True
    assert detached["local_write"] is False
