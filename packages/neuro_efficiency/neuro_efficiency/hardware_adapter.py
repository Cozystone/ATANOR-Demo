from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Any


@dataclass(frozen=True)
class HardwareProfile:
    ram_gb: float
    vram_gb: float
    gpu_name: str
    source: str


@dataclass(frozen=True)
class ElasticRuntimeConfig:
    tier: str
    max_graph_nodes: int
    inference_mode: str
    pruning_aggressiveness: str
    lazy_subgraph_nodes: int
    lazy_subgraph_edges: int
    lazy_subgraph_depth: int
    utterance_max_tokens: int
    profile: HardwareProfile

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["profile"] = asdict(self.profile)
        return payload


def _env_float(name: str) -> float | None:
    value = os.getenv(name)
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _detect_ram_gb() -> tuple[float, str]:
    override = _env_float("HOMAGE_RAM_GB")
    if override is not None:
        return override, "env"
    try:
        import psutil  # type: ignore

        return round(psutil.virtual_memory().total / (1024 ** 3), 2), "psutil"
    except Exception:
        return 8.0, "fallback"


def _detect_torch_vram() -> tuple[float, str] | None:
    try:
        import torch  # type: ignore

        if not torch.cuda.is_available():
            return 0.0, "torch-cuda-unavailable"
        device_index = torch.cuda.current_device()
        props = torch.cuda.get_device_properties(device_index)
        return round(float(props.total_memory) / (1024 ** 3), 2), str(props.name)
    except Exception:
        return None


def _detect_nvidia_smi_vram() -> tuple[float, str] | None:
    command = shutil.which("nvidia-smi")
    if not command:
        return None
    try:
        output = subprocess.check_output(
            [
                command,
                "--query-gpu=name,memory.total",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            timeout=3,
        ).strip().splitlines()[0]
        name, memory_total = [part.strip() for part in output.split(",", 1)]
        return round(float(memory_total) / 1024, 2), name
    except Exception:
        return None


def _detect_vram_gb() -> tuple[float, str]:
    override = _env_float("HOMAGE_VRAM_GB")
    if override is not None:
        return override, "env"
    torch_result = _detect_torch_vram()
    if torch_result is not None:
        return torch_result
    smi_result = _detect_nvidia_smi_vram()
    if smi_result is not None:
        return smi_result
    return 0.0, "unavailable"


def detect_hardware_profile() -> HardwareProfile:
    ram_gb, ram_source = _detect_ram_gb()
    vram_gb, gpu_name = _detect_vram_gb()
    return HardwareProfile(
        ram_gb=ram_gb,
        vram_gb=vram_gb,
        gpu_name=gpu_name,
        source=f"ram:{ram_source};vram:{gpu_name}",
    )


def build_runtime_config(profile: HardwareProfile | dict[str, Any] | None = None) -> ElasticRuntimeConfig:
    if profile is None:
        detected = detect_hardware_profile()
    elif isinstance(profile, HardwareProfile):
        detected = profile
    else:
        detected = HardwareProfile(
            ram_gb=float(profile.get("ram_gb") or 0.0),
            vram_gb=float(profile.get("vram_gb") or 0.0),
            gpu_name=str(profile.get("gpu_name") or profile.get("gpu") or "override"),
            source="override",
        )

    if detected.vram_gb >= 12 and detected.ram_gb >= 32:
        return ElasticRuntimeConfig(
            tier="target",
            max_graph_nodes=500_000,
            inference_mode="gpu_native",
            pruning_aggressiveness="low",
            lazy_subgraph_nodes=512,
            lazy_subgraph_edges=2048,
            lazy_subgraph_depth=3,
            utterance_max_tokens=96,
            profile=detected,
        )
    if detected.ram_gb >= 16:
        return ElasticRuntimeConfig(
            tier="baseline",
            max_graph_nodes=50_000,
            inference_mode="cpu_gguf",
            pruning_aggressiveness="high",
            lazy_subgraph_nodes=256,
            lazy_subgraph_edges=1024,
            lazy_subgraph_depth=2,
            utterance_max_tokens=64,
            profile=detected,
        )
    return ElasticRuntimeConfig(
        tier="minimum",
        max_graph_nodes=10_000,
        inference_mode="cloud_fallback_api",
        pruning_aggressiveness="critical",
        lazy_subgraph_nodes=128,
        lazy_subgraph_edges=384,
        lazy_subgraph_depth=1,
        utterance_max_tokens=40,
        profile=detected,
    )


@lru_cache(maxsize=1)
def get_runtime_config() -> ElasticRuntimeConfig:
    return build_runtime_config()


def runtime_config_dict() -> dict[str, Any]:
    return get_runtime_config().as_dict()
