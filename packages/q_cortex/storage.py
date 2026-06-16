from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


DEFAULT_Q_CORTEX_ROOT = Path("data/q_cortex")


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def ensure_dirs(root: str | Path = DEFAULT_Q_CORTEX_ROOT) -> Path:
    base = Path(root)
    for name in ("runs", "proofs"):
        (base / name).mkdir(parents=True, exist_ok=True)
    return base


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: str | Path, payload: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def read_jsonl(path: str | Path, limit: int = 100) -> list[dict[str, Any]]:
    target = Path(path)
    if not target.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows[-limit:]


def record_run(result: dict[str, Any], filename: str) -> None:
    root = ensure_dirs()
    write_json(root / "runs" / f"{result['run_id']}.json", result)
    append_jsonl(root / filename, {**result, "recorded_at": now_iso()})
    append_jsonl(root / "solver_traces.jsonl", {
        "run_id": result["run_id"],
        "problem_type": result["problem_type"],
        "solver_name": result["solver_name"],
        "objective_value": result["objective_value"],
        "trace": result.get("trace", {}),
        "recorded_at": now_iso(),
    })


def list_runs(limit: int = 100) -> list[dict[str, Any]]:
    root = ensure_dirs()
    rows: list[dict[str, Any]] = []
    for path in sorted((root / "runs").glob("*.json"), key=lambda item: item.stat().st_mtime):
        try:
            rows.append(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    return rows[-limit:]


def get_run(run_id: str) -> dict[str, Any] | None:
    path = ensure_dirs() / "runs" / f"{run_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
