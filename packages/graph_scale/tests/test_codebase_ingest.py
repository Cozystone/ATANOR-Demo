# -*- coding: utf-8 -*-
"""Codebase self-knowledge: AST -> structural triples, queryable, candidate-only."""


def test_ingest_extracts_structure(tmp_path):
    from packages.graph_scale.codebase_ingest import ingest_codebase, _triples_for_file
    src = tmp_path / "pkg"
    src.mkdir()
    (src / "mod.py").write_text(
        'def helper():\n    """Do a helping thing."""\n    return 1\n'
        'def main():\n    """Entry."""\n    return helper()\n', encoding="utf-8")
    t = {(a, b, c) for a, b, c in _triples_for_file(src / "mod.py", tmp_path)}
    assert ("pkg.mod", "is_a", "python_module") in t
    assert ("pkg.mod", "has_function", "main") in t
    assert ("main", "calls", "helper") in t                 # call graph captured
    assert ("helper", "documented_as", "Do a helping thing.") in t
    r = ingest_codebase(root=tmp_path, subdir="pkg", out=tmp_path / "cb.jsonl", skip_tests=False)
    assert r["written_to_production"] is False and r["functions"] >= 2


def test_about_queries_self_knowledge(tmp_path, monkeypatch):
    from packages.graph_scale import codebase_ingest as cb
    ledger = tmp_path / "cb.jsonl"
    monkeypatch.setattr(cb, "LEDGER", ledger)
    cb.ingest_codebase(root=_make(tmp_path), subdir="pkg", out=ledger, skip_tests=False)
    a = cb.about("main")
    assert a["known"] is True
    assert any(x["predicate"] == "calls" and x["object"] == "helper" for x in a["is"])


def _make(tmp_path):
    src = tmp_path / "pkg"; src.mkdir(exist_ok=True)
    (src / "mod.py").write_text(
        'def helper():\n    return 1\ndef main():\n    return helper()\n', encoding="utf-8")
    return tmp_path
