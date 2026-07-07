# -*- coding: utf-8 -*-
"""Browser ingest — distilled page candidates through the multi-source gate.

Closes the browser loop (난제 P2-2): a distilled page's candidate triples do
NOT enter the verified store. They accrue in a voice-counted ledger where the
VOICE is the page's HOST (Sybil-capped consensus: one site saying something
ten times is still one voice), and a candidate only becomes PROMOTABLE when:
  * >= min_hosts distinct hosts independently assert it (consensus), AND
  * the curated judge does not CONTRADICT it (safety).
Promotion itself is the operator/promotion-gate's call — this module only
computes what is promotable and never writes to the verified store.

This reuses the paid-for lessons: the distiller's title-anchor gate keeps
off-topic prose out; host-voice counting caps Sybil; the curated judge keeps
a lie that two blogs happen to share from promoting if the curated store knows
better. Everything is auditable in the ledger.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .page_distiller import distill_page

_DATA = Path(__file__).resolve().parents[2] / "data" / "atanor_browser"
_LEDGER = _DATA / "browser_evidence.jsonl"


def _host(url: str) -> str:
    try:
        h = urlparse(url).hostname or ""
        return h[4:] if h.startswith("www.") else h
    except Exception:
        return ""


def _key(subject: str, predicate: str, obj: str) -> str:
    return hashlib.sha256(f"{subject}\x1f{predicate}\x1f{obj}".encode()).hexdigest()[:16]


class BrowserEvidenceLedger:
    """Voice-counted candidate ledger for browsed pages. Voice = host."""

    def __init__(self, path: str | Path = _LEDGER, *, min_hosts: int = 2) -> None:
        self.path = Path(path)
        self.min_hosts = max(1, int(min_hosts))
        # key -> {subject, predicate, object, hosts:set, urls:set, first_seen}
        self._agg: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                self._apply(json.loads(line))
            except Exception:
                continue

    def _apply(self, ev: dict[str, Any]) -> None:
        k = ev["key"]
        slot = self._agg.setdefault(k, {
            "subject": ev["subject"], "predicate": ev["predicate"],
            "object": ev["object"], "hosts": set(), "urls": set(),
            "first_seen": ev.get("at")})
        if ev.get("host"):
            slot["hosts"].add(ev["host"])
        if ev.get("url"):
            slot["urls"].add(ev["url"])

    def record(self, subject: str, predicate: str, obj: str, url: str) -> None:
        host = _host(url)
        ev = {"key": _key(subject, predicate, obj), "subject": subject,
              "predicate": predicate, "object": obj, "url": url, "host": host,
              "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        self._apply(ev)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(ev, ensure_ascii=False) + "\n")

    def promotable(self, store: Any = None) -> list[dict[str, Any]]:
        """Candidates with >= min_hosts distinct host-voices that the curated
        judge does not contradict. Never writes; the promotion gate decides."""
        try:
            from packages.graph_scale.curated_judge import judge
        except Exception:
            judge = None
        out = []
        for slot in self._agg.values():
            if len(slot["hosts"]) < self.min_hosts:
                continue
            verdict = "unknown"
            if judge is not None and store is not None:
                verdict = judge(slot["subject"], slot["predicate"],
                                slot["object"], store).get("verdict", "unknown")
            if verdict in ("contradicted", "type_conflict"):
                continue  # curated store knows better — never promote
            out.append({
                "subject": slot["subject"], "predicate": slot["predicate"],
                "object": slot["object"], "hosts": sorted(slot["hosts"]),
                "host_voices": len(slot["hosts"]), "urls": sorted(slot["urls"])[:5],
                "judge": verdict})
        out.sort(key=lambda c: -c["host_voices"])
        return out

    def stats(self) -> dict[str, Any]:
        return {"candidates": len(self._agg),
                "multi_host": sum(1 for s in self._agg.values()
                                  if len(s["hosts"]) >= self.min_hosts),
                "min_hosts": self.min_hosts}


def ingest_page(html: str, url: str = "",
                ledger: BrowserEvidenceLedger | None = None) -> dict[str, Any]:
    """Distill a page and record its title-anchored candidate triples as
    host-voiced evidence. Returns what was distilled + recorded. The verified
    store is never touched here."""
    led = ledger or BrowserEvidenceLedger()
    result = distill_page(html, url=url)
    recorded = 0
    for t in result.get("triples", []):
        led.record(t["subject"], t["predicate"], t["object"], url)
        recorded += 1
    return {"anchor": result.get("anchor"), "distilled": len(result.get("triples", [])),
            "recorded": recorded, "evidence_kept": len(result.get("evidence", [])),
            "dropped": result.get("dropped", {}), "written_to_verified_store": False}
