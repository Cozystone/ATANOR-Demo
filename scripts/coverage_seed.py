#!/usr/bin/env python3
"""Coverage seed: pull KO-Wikipedia definition sentences for common concepts and durably
ingest them, so the answer engine can define terms it currently abstains on.

The battery showed the #1 gap is coverage: common concepts (반도체/인공지능/광합성) either aren't
in the graph or have no definitional ('X는 …이다') sentence, so promotion can't describe them.
KO-Wikipedia REST summaries lead with the term, which is exactly the promotable form.

Faithful (verbatim first sentence, No-LLM), reference-only, durable (idempotent + per-source
provenance). Writes to the live local store — run with the worker STOPPED to avoid a race.
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for p in (str(REPO_ROOT), str(REPO_ROOT / "apps" / "api"), str(REPO_ROOT / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

import durable_ingest as di                                   # noqa: E402
from app.services.web_search import _wiki_rest_summary        # noqa: E402

LIVE = REPO_ROOT / "data" / "cloud_brain" / "candidate_runs" / "clean_seed_v2"
HOST = "ko.wikipedia.org"

TERMS = [
    "반도체", "인공지능", "광합성", "DNA", "세포", "중력", "아인슈타인", "엔비디아",
    "블록체인", "삼성전자", "컴퓨터", "인터넷", "세종대왕", "태양", "지구", "원자",
    "전자", "백신", "바이러스", "민주주의", "양자역학", "기계학습", "블랙홀", "단백질",
    "은하", "화산", "지진", "면역", "호르몬", "진화",
]


def _first_sentence(text: str) -> str:
    t = str(text or "")
    # Wikipedia definitions carry heavy parentheticals (한자/영문/발음: "반도체(半導體, 영어:
    # …)는") that break the Korean case-role parser so the term is never extracted as the
    # TOPIC. Strip parentheticals + bracket refs so the sentence is the clean promotable
    # form "반도체는 …이다".
    t = re.sub(r"\([^)]*\)", "", t)
    t = re.sub(r"\[[^\]]*\]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    m = re.search(r".+?다\.", t)
    s = m.group(0) if m else t[:200]
    return s.strip()


def main() -> int:
    if not LIVE.exists():
        print(f"[COVERAGE] live store missing: {LIVE}")
        return 1
    rows = []
    got = 0
    for term in TERMS:
        try:
            r = _wiki_rest_summary(term, HOST)
        except Exception:
            r = None
        if not r:
            print(f"  miss: {term}")
            continue
        sent = _first_sentence(r.get("snippet", ""))
        if 15 < len(sent) < 240:
            rows.append((sent, r.get("url") or f"https://{HOST}/wiki/{term}", "reference_only", "public_web_feed"))
            got += 1
            print(f"  ok:   {term} -> {sent[:70]}")
    print(f"\n[COVERAGE] fetched {got}/{len(TERMS)} definitions")
    if not rows:
        print("[COVERAGE] nothing fetched (rate-limited?). store untouched.")
        return 2
    print("[COVERAGE] durable ingest into live store...")
    r1 = di.ingest(LIVE, rows)
    print(f"   new={r1['new_facts']} dup={r1['dup_skipped']} rejected={r1['rejected']}")
    r2 = di.ingest(LIVE, rows)
    print(f"[COVERAGE] idempotent (run2 new==0): {r2['new_facts'] == 0}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
