from __future__ import annotations

import os
import platform
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from neuro_efficiency.stability import build_sustained_run_plan


def build_hardware_benchmark(profile: dict[str, Any] | None = None) -> dict[str, Any]:
    """Measure the host enough to tune Homage Alpha workload knobs.

    This is intentionally a short startup probe, not a stress benchmark. It
    reads stable hardware facts, runs small CPU/disk probes when requested, and
    converts the result into ontology and training limits that keep the machine
    responsive during long runs.
    """

    payload = profile or {}
    run_probes = bool(payload.get("run_probes", True))
    hardware = _collect_hardware_snapshot(payload.get("hardware_profile"))
    probes = _run_quick_probes(run_probes)
    recommendation = _recommend_profile(hardware, probes)
    stability = build_sustained_run_plan(
        {
            "hardware_profile": recommendation["hardware_profile"],
            **recommendation["stability_payload"],
        }
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "local-hardware-probe",
        "can_read_local_hardware": True,
        "profile_name": recommendation["profile_name"],
        "confidence": recommendation["confidence"],
        "hardware_profile": recommendation["hardware_profile"],
        "probes": probes,
        "recommended_learning_volume": recommendation["learning_volume"],
        "recommended_stability_payload": recommendation["stability_payload"],
        "ontology_tuning": {
            "datagate_batch_docs": stability["queue_policy"]["datagate_batch_docs"],
            "ontology_delta_chunks": stability["queue_policy"]["ontology_delta_chunks"],
            "node_write_batch": stability["queue_policy"]["node_write_batch"],
            "edge_write_batch": stability["queue_policy"]["edge_write_batch"],
            "hot_window_nodes": stability["graph_policy"]["hot_window_nodes"],
            "hot_window_edges": stability["graph_policy"]["hot_window_edges"],
            "ui_render_nodes": stability["graph_policy"]["ui_render_nodes"],
            "storage_model": stability["graph_policy"]["storage_model"],
        },
        "training_tuning": {
            "precision": recommendation["precision"],
            "microbatch_tokens": recommendation["microbatch_tokens"],
            "gradient_accumulation": recommendation["gradient_accumulation"],
            "rag_query_concurrency": stability["queue_policy"]["rag_query_concurrency"],
            "checkpoint_interval_minutes": stability["checkpoint_policy"]["training_checkpoint_interval_minutes"],
            "checkpoint_keep_last": stability["checkpoint_policy"]["checkpoint_keep_last"],
        },
        "runtime_envelope": stability["runtime_envelope"],
        "backpressure_policy": stability["backpressure_policy"],
        "adjustment_policy": {
            "auto_apply_when_source": "local-hardware-probe",
            "reason": recommendation["reason"],
            "rerun_trigger": "operator request or hardware profile change",
        },
    }


def _collect_hardware_snapshot(override: Any = None) -> dict[str, Any]:
    disk = shutil.disk_usage(".")
    snapshot: dict[str, Any] = {
        "cpu": platform.processor() or platform.machine() or "Unknown CPU",
        "cpu_logical": os.cpu_count() or 1,
        "cpu_physical": None,
        "ram_gb": _read_ram_gb(),
        "gpu": "Unavailable",
        "vram_gb": 0,
        "disk_total_gb": round(disk.total / (1024**3), 1),
        "disk_free_gb": round(disk.free / (1024**3), 1),
        "platform": platform.platform(),
    }
    snapshot.update(_read_gpu_snapshot())
    if isinstance(override, dict):
        snapshot.update(override)
    if not snapshot.get("ram_gb"):
        snapshot["ram_gb"] = 16
    return snapshot


def _read_ram_gb() -> float | None:
    try:
        import psutil  # type: ignore

        return round(psutil.virtual_memory().total / (1024**3), 1)
    except Exception:
        return None


def _read_gpu_snapshot() -> dict[str, Any]:
    command = shutil.which("nvidia-smi")
    if not command:
        return {}
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
        name, mem_total = [part.strip() for part in output.split(",")]
        return {"gpu": name, "vram_gb": round(float(mem_total) / 1024, 1)}
    except Exception:
        return {}


def _run_quick_probes(run_probes: bool) -> dict[str, Any]:
    if not run_probes:
        return {
            "ran": False,
            "cpu_loop_score": None,
            "disk_write_mb_s": None,
            "duration_ms": 0,
            "notes": ["probe skipped by request"],
        }

    start = time.perf_counter()
    cpu_score = _cpu_loop_score()
    disk_score = _disk_write_score()
    duration_ms = round((time.perf_counter() - start) * 1000, 1)
    return {
        "ran": True,
        "cpu_loop_score": cpu_score,
        "disk_write_mb_s": disk_score,
        "duration_ms": duration_ms,
        "notes": ["short startup probe; not a thermal stress test"],
    }


def _cpu_loop_score() -> int:
    iterations = 360_000
    start = time.perf_counter()
    value = 0x345678
    for index in range(iterations):
        value = ((value * 1_664_525) + index + 1_013_904_223) & 0xFFFFFFFF
        value ^= value >> 13
    elapsed = max(0.001, time.perf_counter() - start)
    return int(iterations / elapsed)


def _disk_write_score() -> float | None:
    block = b"homage-benchmark\n" * 4096
    target_mb = 8
    try:
        with tempfile.NamedTemporaryFile(prefix="homage-bench-", suffix=".bin", dir=Path("."), delete=False) as handle:
            path = Path(handle.name)
            start = time.perf_counter()
            for _ in range(max(1, int((target_mb * 1024 * 1024) / len(block)))):
                handle.write(block)
            handle.flush()
            os.fsync(handle.fileno())
            elapsed = max(0.001, time.perf_counter() - start)
        path.unlink(missing_ok=True)
        return round(target_mb / elapsed, 1)
    except Exception:
        return None


def _recommend_profile(hardware: dict[str, Any], probes: dict[str, Any]) -> dict[str, Any]:
    ram_gb = _float(hardware.get("ram_gb"), 16)
    vram_gb = _float(hardware.get("vram_gb"), 0)
    cpu_logical = _int(hardware.get("cpu_logical"), 4)
    disk_free_gb = _float(hardware.get("disk_free_gb"), 0)
    cpu_score = _float(probes.get("cpu_loop_score"), 0)
    disk_score = _float(probes.get("disk_write_mb_s"), 0)

    score = 0
    score += 3 if ram_gb >= 64 else 2 if ram_gb >= 30 else 1 if ram_gb >= 16 else 0
    score += 3 if vram_gb >= 24 else 2 if vram_gb >= 15 else 1 if vram_gb >= 8 else 0
    score += 2 if cpu_logical >= 24 else 1 if cpu_logical >= 12 else 0
    score += 2 if disk_free_gb >= 300 else 1 if disk_free_gb >= 120 else 0
    score += 1 if cpu_score >= 3_000_000 else 0
    score += 1 if disk_score >= 500 else 0

    if score >= 8:
        volume = "max"
        payload = {"target_nodes": 50_000, "target_edges": 240_000, "duration_hours": 168}
        microbatch_tokens = 1024
        accumulation = 8
        profile_name = "Performance desktop"
    elif score >= 5:
        volume = "deep"
        payload = {"target_nodes": 25_000, "target_edges": 100_000, "duration_hours": 168}
        microbatch_tokens = 768
        accumulation = 8
        profile_name = "Balanced workstation"
    elif score >= 3:
        volume = "standard"
        payload = {"target_nodes": 10_000, "target_edges": 40_000, "duration_hours": 72}
        microbatch_tokens = 512
        accumulation = 4
        profile_name = "Standard desktop"
    else:
        volume = "lite"
        payload = {"target_nodes": 3_000, "target_edges": 9_000, "duration_hours": 12}
        microbatch_tokens = 256
        accumulation = 2
        profile_name = "Conservative mode"

    precision = "bf16-preferred" if vram_gb >= 12 else "int8-cpu-safe"
    confidence = "high" if hardware.get("ram_gb") and probes.get("ran") else "medium"
    reason = (
        f"score {score}: RAM {ram_gb}GB, VRAM {vram_gb}GB, "
        f"CPU threads {cpu_logical}, free disk {disk_free_gb}GB"
    )
    return {
        "profile_name": profile_name,
        "confidence": confidence,
        "learning_volume": volume,
        "stability_payload": payload,
        "hardware_profile": {
            "cpu": hardware.get("cpu") or "Unknown CPU",
            "gpu": hardware.get("gpu") or "Unavailable",
            "vram_gb": vram_gb,
            "ram_gb": ram_gb,
            "storage": hardware.get("storage") or "Local workspace disk",
            "storage_gb": _float(hardware.get("storage_gb") or hardware.get("disk_total_gb"), 1000),
            "cpu_logical": cpu_logical,
            "disk_free_gb": disk_free_gb,
            "platform": hardware.get("platform"),
        },
        "precision": precision,
        "microbatch_tokens": microbatch_tokens,
        "gradient_accumulation": accumulation,
        "reason": reason,
    }


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
