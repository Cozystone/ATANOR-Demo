#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sweep the answer graph and materialize the connections it already ENTAILS.

The web learner adds NEW facts slowly and carefully. This is the compounding
lane: is_a / located_in / part_of are transitive (A⊂B ∧ B⊂C ⟹ A⊂C), so a
22M-edge transitive backbone entails tens of millions of edges it hasn't written
down. This script materializes them at ~3/4-million edges/sec — every edge sound
(follows from two stated edges), source-tagged `derived:*`, never fabricated.

    python scripts/derivation_accelerator.py --passes 20 --max-new 1000000
    python scripts/derivation_accelerator.py --sweep         # full graph, one wrap

Run it against the live answer store (the 25M-edge graph answers read). Bounded
per pass so peak memory stays flat; a cursor resumes across passes.
"""
from __future__ import annotations

import argparse
import glob
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for _d in sorted(glob.glob(str(ROOT / "packages" / "*"))):
    if os.path.isdir(_d):
        sys.path.append(_d)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--passes", type=int, default=10, help="bounded passes to run")
    ap.add_argument("--max-new", type=int, default=1_000_000, help="edge cap per pass")
    ap.add_argument("--edge-window", type=int, default=1_000_000, help="stated edges scanned per pass")
    ap.add_argument("--sweep", action="store_true", help="run passes until the cursor wraps the whole graph")
    args = ap.parse_args()

    from packages.graph_scale.answer_bridge import _store
    from packages.graph_scale.derivation_accelerator import accelerate

    store = _store()
    if store is None:
        raise SystemExit("answer store unavailable — run from the demo worktree")

    start_total = len(store)
    cursor = 0
    added = 0
    t0 = time.time()
    p = 0
    while True:
        p += 1
        res = accelerate(store, max_new=args.max_new, edge_window=args.edge_window, cursor=cursor)
        if res.get("error"):
            print(f"pass {p}: ERROR {res['error']}")
            break
        cursor = int(res.get("next_cursor") or 0)
        added += int(res.get("derived") or 0)
        print(f"pass {p:>3}: +{res.get('derived'):>9,} derived  "
              f"({res.get('rate_per_sec'):>8,}/s)  total={len(store):,}  cursor={cursor:,}")
        if args.sweep:
            if res.get("wrapped"):
                break
        elif p >= args.passes:
            break
    dt = time.time() - t0
    print(f"\ndone: +{added:,} new derived connections in {dt:.1f}s "
          f"({round(added / dt):,}/s), store {start_total:,} -> {len(store):,}")


if __name__ == "__main__":
    main()
