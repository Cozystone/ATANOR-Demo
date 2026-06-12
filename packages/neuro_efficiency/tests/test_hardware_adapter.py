from __future__ import annotations

from neuro_efficiency import build_runtime_config


def test_hardware_adapter_target_tier() -> None:
    config = build_runtime_config({"ram_gb": 32, "vram_gb": 16, "gpu_name": "RTX 5080"})

    assert config.tier == "target"
    assert config.max_graph_nodes == 500_000
    assert config.inference_mode == "gpu_native"
    assert config.pruning_aggressiveness == "low"
    assert config.lazy_subgraph_nodes == 512


def test_hardware_adapter_baseline_tier() -> None:
    config = build_runtime_config({"ram_gb": 16, "vram_gb": 0, "gpu_name": "none"})

    assert config.tier == "baseline"
    assert config.max_graph_nodes == 50_000
    assert config.inference_mode == "cpu_gguf"
    assert config.pruning_aggressiveness == "high"


def test_hardware_adapter_minimum_tier() -> None:
    config = build_runtime_config({"ram_gb": 8, "vram_gb": 0, "gpu_name": "none"})

    assert config.tier == "minimum"
    assert config.max_graph_nodes == 10_000
    assert config.inference_mode == "cloud_fallback_api"
    assert config.pruning_aggressiveness == "critical"
