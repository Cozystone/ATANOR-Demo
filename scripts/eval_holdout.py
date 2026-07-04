#!/usr/bin/env python3
"""Score the SEALED holdout battery against the live engine (:8502).

Refuses to run if the seal is broken. Reports answered / abstained / grounded
counts and appends to data/eval/holdout_history.jsonl. The number that matters
long-term is the GAP between the working battery's coverage and this one's —
a widening gap means self_improve is overfitting the working battery (Goodhart).
"""
from __future__ import annotations

import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EVAL_DIR = REPO / "data" / "eval"
BATTERY = EVAL_DIR / "holdout_v1.jsonl"
HISTORY = EVAL_DIR / "holdout_history.jsonl"
URL = "http://127.0.0.1:8502/api/base-brain/answer"
ABSTAIN = ("근거가 부족", "실시간", "확인된 근거로는", "찾아드릴게요")

sys.path.insert(0, str(REPO / "scripts"))
from build_holdout_battery import check as seal_check  # noqa: E402


def ask(question: str) -> str:
    data = json.dumps({"query": question, "language": "ko"}).encode("utf-8")
    req = urllib.request.Request(URL, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return str(json.loads(r.read().decode("utf-8")).get("answer") or "")
    except Exception as exc:  # noqa: BLE001 - live probe, report as error string
        return f"__ERR__ {exc}"


def main() -> int:
    if seal_check() != 0:
        print("[EVAL] refusing to score: seal invalid")
        return 2
    rows = [json.loads(l) for l in BATTERY.read_text(encoding="utf-8").splitlines() if l.strip()]
    answered = abstained = errors = 0
    hard: list[str] = []
    for row in rows:
        a = ask(row["question"])
        if a.startswith("__ERR__"):
            errors += 1
        elif any(m in a for m in ABSTAIN) or not a.strip():
            abstained += 1
            hard.append(row["term"])
        else:
            answered += 1
    total = len(rows)
    print(f"[HOLDOUT] answered {answered}/{total} ({answered/total:.0%}) | abstained {abstained} | errors {errors}")
    if hard:
        print(f"[HOLDOUT] abstaining terms: {hard[:15]}")
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "t": datetime.now(timezone.utc).isoformat(), "total": total,
            "answered": answered, "abstained": abstained, "errors": errors,
        }, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
