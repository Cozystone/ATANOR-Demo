# -*- coding: utf-8 -*-
"""Turbo ingest — vectorized curated lane + async audit sweep (exactness restored)."""

from __future__ import annotations

from packages.graph_scale.triple_store import TripleStore
from packages.graph_scale.turbo_ingest import audit_sweep, turbo_ingest, turbo_ingest_tsv


def test_turbo_ingest_dedups_in_batch_and_is_queryable(tmp_path):
    st = TripleStore(tmp_path / "s")
    triples = [("서울", "capital_of", "한국"), ("부산", "is_a", "도시"),
               ("서울", "capital_of", "한국")]  # exact dup
    r = turbo_ingest(st, triples)
    assert r["ingested"] == 2 and r["in_batch_deduped"] == 1
    assert ("서울", "capital_of", "한국") in st.facts_about("서울", limit=5)


def test_audit_sweep_restores_cross_run_exactness(tmp_path):
    st = TripleStore(tmp_path / "s")
    turbo_ingest(st, [("서울", "capital_of", "한국")])
    turbo_ingest(st, [("서울", "capital_of", "한국"),  # cross-RUN dup (turbo skips seen-set)
                      ("부산", "is_a", "도시")])
    assert st._count == 3
    a = audit_sweep(st)
    assert a["removed"] == 1 and st._count == 2
    assert st.facts_about("서울", limit=5) == [("서울", "capital_of", "한국")]


def test_tsv_lane_end_to_end(tmp_path):
    tsv = tmp_path / "d.tsv"
    tsv.write_text("서울\tcapital_of\t한국\n부산\tis_a\t도시\n서울\tcapital_of\t한국\n",
                   encoding="utf-8")
    st = TripleStore(tmp_path / "s")
    r = turbo_ingest_tsv(st, str(tsv))
    assert r["ingested"] == 2 and r["rows_read"] == 3
    assert ("부산", "is_a", "도시") in st.facts_about("부산", limit=5)
    # meta marks the audit debt honestly
    import json
    meta = json.loads((tmp_path / "s" / "meta.json").read_text(encoding="utf-8"))
    assert meta["turbo_audit_pending"] is True
    audit_sweep(st)
    meta = json.loads((tmp_path / "s" / "meta.json").read_text(encoding="utf-8"))
    assert meta["turbo_audit_pending"] is False
