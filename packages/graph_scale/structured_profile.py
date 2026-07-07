# -*- coding: utf-8 -*-
"""Structured profile lane (B-track) — the Copilot-style fact table, honestly.

The knowledge learner (web_knowledge_drain) gathers ATTRIBUTED PROSE evidence.
This lane adds the other half a rich answer needs: STRUCTURED ATTRIBUTES —
population, area, inception, capital — pulled from Wikidata's curated claims and
stored as typed facts with the wikidata.org entity page as provenance.

Why Wikidata, not a DBpedia bulk download: it is keyless, live, per-entity (no
multi-GB file), and every claim is community-curated with a stable QID + link.
Each stored fact is verbatim (the value + unit exactly as Wikidata states it),
so the answer layer can render a compact profile without inventing anything.

The stored predicate names are human-readable Korean ('인구', '면적', '설립') so a
profile answer reads naturally and the fact is self-describing in the store.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
STORE_ROOT = REPO / "data" / "graph_scale" / "kg_triples"
_UA = ("ATANOR-KG/2.0 (https://github.com/Cozystone/ATANOR; blueyjkim@gmail.com) "
       "structured-profile")

# Wikidata property -> (Korean predicate, kind). Only stable, high-value attributes
# that make a profile — never free-form text properties (those are the prose lane's).
_PROPS: dict[str, tuple[str, str]] = {
    "P1082": ("인구", "quantity"),
    "P2046": ("면적", "quantity"),        # km²
    "P571": ("설립", "time"),             # inception
    "P36": ("수도", "item"),
    "P17": ("국가", "item"),
    "P131": ("소재지", "item"),           # located in admin entity
    "P1376": ("수도인 지역", "item"),      # capital of
    "P610": ("최고점", "item"),
    "P2044": ("고도", "quantity"),        # elevation
    "P625": ("좌표", "globe"),
}


def _pit(claim: dict[str, Any]) -> str:
    """Point-in-time (P585) qualifier of a claim, '' when none — used to pick the
    MOST RECENT population/area statement instead of an arbitrary historical one."""
    for q in (claim.get("qualifiers") or {}).get("P585", []):
        t = ((q.get("datavalue") or {}).get("value") or {}).get("time") or ""
        if t:
            return t
    return ""


def _best_claim(claims: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Wikidata lists many statements per property (a population per census year).
    Pick honestly: 'preferred' rank wins; otherwise the latest point-in-time; a
    'deprecated' statement is never chosen. This is why France read 40M (a 1946
    figure) — first-wins grabbed a historical census."""
    usable = [c for c in claims if c.get("rank") != "deprecated"
              and (c.get("mainsnak") or {}).get("snaktype") == "value"]
    if not usable:
        return None
    preferred = [c for c in usable if c.get("rank") == "preferred"]
    pool = preferred or usable
    return max(pool, key=_pit)


def _api(url: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:  # nosec B310 - wikidata API
        return json.loads(r.read().decode("utf-8"))


def _resolve_qid(term: str) -> tuple[str, str] | None:
    """(QID, matched_label) for an EXACT Korean label/alias match only — a fuzzy hit
    would profile the wrong entity (the wrong-referent class we guard everywhere)."""
    url = ("https://www.wikidata.org/w/api.php?action=wbsearchentities&format=json"
           "&language=ko&uselang=ko&type=item&limit=5&search=" + urllib.parse.quote(term))
    try:
        data = _api(url)
    except Exception:
        return None
    tl = term.strip().lower()
    for hit in data.get("search", []):
        label = (hit.get("label") or "").strip()
        matched = str((hit.get("match") or {}).get("text") or "").strip().lower()
        if hit.get("id") and (label.lower() == tl or matched == tl):
            return hit["id"], label
    return None


def _label_for(qid: str) -> str:
    try:
        data = _api(f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json")
        ent = (data.get("entities") or {}).get(qid) or {}
        labels = ent.get("labels") or {}
        return (labels.get("ko") or labels.get("en") or {}).get("value") or qid
    except Exception:
        return qid


_MONTHS_KO = ""  # dates rendered as YYYY년 MM월 DD일 below


def _format_value(prop: str, snak: dict[str, Any]) -> str | None:
    """Verbatim value string from a Wikidata claim's mainsnak, for the given prop kind."""
    dv = (snak.get("datavalue") or {}).get("value")
    if dv is None:
        return None
    kind = _PROPS[prop][1]
    if kind == "quantity":
        amount = str(dv.get("amount") or "").lstrip("+")
        if not amount:
            return None
        try:
            n = float(amount)
            amount = f"{int(n):,}" if n.is_integer() else f"{n:,}"
        except ValueError:
            pass
        unit_q = str(dv.get("unit") or "").rsplit("/", 1)[-1]
        unit = {"Q712226": "km²", "Q828224": "km", "Q11573": "m"}.get(unit_q, "")
        return f"{amount} {unit}".strip() if amount else None
    if kind == "time":
        t = str(dv.get("time") or "")
        m = re.match(r"[+-](\d{4})-(\d{2})-(\d{2})", t)
        if not m:
            return None
        y, mo, d = m.groups()
        if mo == "00":
            return f"{int(y)}년"
        if d == "00":
            return f"{int(y)}년 {int(mo)}월"
        return f"{int(y)}년 {int(mo)}월 {int(d)}일"
    if kind == "item":
        qid = str(dv.get("id") or "")
        return _label_for(qid) if qid else None
    if kind == "globe":
        lat, lon = dv.get("latitude"), dv.get("longitude")
        if lat is None or lon is None:
            return None
        return f"{float(lat):.4f}, {float(lon):.4f}"
    return None


def fetch_profile(term: str, dry_run: bool = False, log: Any = print,
                  store: Any = None) -> dict[str, Any]:
    """Fetch + store a structured attribute profile for an entity. Returns counters
    and the (predicate, value) pairs. Nothing stored on no exact QID match."""
    out = {"term": term, "qid": None, "attributes": [], "stored": 0}
    resolved = _resolve_qid(term)
    if not resolved:
        log(f"  {term}: no exact Wikidata entity (honest skip)")
        return out
    qid, label = resolved
    out["qid"] = qid
    try:
        data = _api(f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json")
    except Exception:
        return out
    claims = ((data.get("entities") or {}).get(qid) or {}).get("claims") or {}
    url = f"https://www.wikidata.org/wiki/{qid}"
    if store is None and not dry_run:
        from .triple_store import TripleStore

        store = TripleStore(STORE_ROOT)
    sid = store.intern_source("wikidata.org", url) if store is not None else None
    for prop, (pred_ko, _kind) in _PROPS.items():
        claim = _best_claim(claims.get(prop, []))
        if claim is None:
            continue
        snak = claim.get("mainsnak") or {}
        if snak.get("snaktype") != "value":
            continue
        val = _format_value(prop, snak)
        if not val:
            continue
        if val == term or val == label:
            continue  # self-referential (국가 = 프랑스 for 프랑스) — no information
        out["attributes"].append((pred_ko, val))
        log(f"  {term}: {pred_ko} = {val}  ({url})")
        if not dry_run and store is not None:
            if store.add(term, pred_ko, val, source=sid):
                out["stored"] += 1
    if not dry_run and store is not None and out["stored"]:
        store.flush()
    return out


_PROFILE_PREDS = tuple(p for p, _ in _PROPS.values())


def profile_block(store: Any, subject: str, limit: int = 6) -> str:
    """Render stored structured attributes as a compact profile block, or '' when the
    subject has none. Used by the answer layer for adaptive rich depth."""
    try:
        rows = store.facts_with_sources(subject, limit=20, preds=_PROFILE_PREDS)
    except Exception:
        return ""
    seen: dict[str, str] = {}
    url = ""
    for (_s, p, o, _name, u) in rows:
        if p not in seen:
            seen[p] = o
            url = url or u
    if not seen:
        return ""
    order = [k for _p, (k, _kind) in _PROPS.items() if k in seen]
    lines = [f"· {k}: {seen[k]}" for k in order][:limit]
    tail = f"\n(출처: Wikidata {url})" if url else ""
    return "주요 정보:\n" + "\n".join(lines) + tail
