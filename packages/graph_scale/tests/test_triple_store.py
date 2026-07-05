"""The trillion-scale substrate: an integer-columnar triple store that ingests curated
(s,p,o) facts fast, de-dupes exactly, survives a reopen, and feeds the answer bridge —
so bulk knowledge is stored densely AND becomes usable answers."""
from __future__ import annotations

import tempfile
from pathlib import Path

from packages.graph_scale.triple_store import TripleStore, TermDict


def test_ingest_dedup_and_count():
    root = Path(tempfile.mkdtemp()) / "kg"
    ts = TripleStore(root)
    r = ts.bulk_ingest([("일본", "capital", "도쿄도"), ("캐나다", "capital", "오타와"),
                        ("일본", "capital", "도쿄도")])   # last is a duplicate
    assert r["added"] == 2 and r["duplicates"] == 1
    assert len(ts) == 2


def test_persists_across_reopen():
    root = Path(tempfile.mkdtemp()) / "kg"
    TripleStore(root).bulk_ingest([("프랑스", "capital", "파리")])
    reopened = TripleStore(root)          # fresh instance reads terms + count from disk
    assert len(reopened) == 1
    assert reopened.facts_about("프랑스") == [("프랑스", "capital", "파리")]


def test_facts_about_memmap_scan():
    root = Path(tempfile.mkdtemp()) / "kg"
    ts = TripleStore(root)
    ts.bulk_ingest([("한국", "capital", "서울"), ("한국", "language", "한국어"),
                    ("일본", "capital", "도쿄")])
    facts = ts.facts_about("한국", limit=10)
    assert ("한국", "capital", "서울") in facts and ("한국", "language", "한국어") in facts
    assert all(s == "한국" for s, _, _ in facts)


def test_dense_storage():
    """~12 bytes/triple in the columns (int32 x3) — vastly denser than JSON text rows."""
    root = Path(tempfile.mkdtemp()) / "kg"
    ts = TripleStore(root)
    ts.bulk_ingest([(f"E{i}", "rel", f"O{i}") for i in range(10000)])
    col_bytes = sum((root / f"{n}.col").stat().st_size for n in ("s", "p", "o"))
    assert col_bytes == 10000 * 3 * 4        # exactly 12 bytes/triple in the columns


def test_term_dict_stable_ids():
    d = TermDict(Path(tempfile.mkdtemp()) / "terms.txt")
    a, b = d.intern("서울"), d.intern("도쿄")
    assert d.intern("서울") == a and a != b          # stable, distinct
    assert d.term(a) == "서울"


def test_answer_bridge_reads_stored_facts(monkeypatch):
    root = Path(tempfile.mkdtemp()) / "kg"
    ts = TripleStore(root)
    ts.bulk_ingest([("일본", "capital", "도쿄도"), ("캐나다", "capital", "오타와")])
    import packages.graph_scale.answer_bridge as ab
    monkeypatch.setattr(ab, "_ROOT", root)
    ab._STORE["sig"] = None                          # force reload against the temp store
    r = ab.answer_from_triples("일본의 수도는?", "ko")
    assert r and "도쿄도" in r["answer"]
    assert r["reasoning_certificate"]["guarantees"]["fabricated_facts"] is False
    # a subject the store doesn't know -> honest None (no fabrication)
    ab._STORE["sig"] = None
    assert ab.answer_from_triples("존재하지않는나라의 수도는?", "ko") is None
