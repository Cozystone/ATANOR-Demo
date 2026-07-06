"""Self-correction from lived outcomes: a live decision is recorded with its exact feature
snapshot, a measured outcome labels it, and the tuner moves weights toward the corrected
routing WITHOUT ever regressing the hand-battery accuracy floor."""
from __future__ import annotations

from packages.base_brain import answer_experience as ax
from packages.base_brain.answer_policy import extract_features
from packages.base_brain.answer_policy_tuning import _margin, accuracy, tune


def _tmp_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(ax, "LEDGER", tmp_path / "exp.jsonl")


def test_record_label_roundtrip(tmp_path, monkeypatch):
    _tmp_ledger(tmp_path, monkeypatch)
    feats = extract_features("고양이가 자꾸 물어요 왜 그럴까?", {"named_match": 0.9, "has_definition": True})
    ax.record_decision("고양이가 자꾸 물어요 왜 그럴까?", feats, "define")
    assert ax.label_outcome("고양이가 자꾸 물어요 왜 그럴까?", {"engage", "abstain"}, "test")
    ex = ax.training_examples()
    assert len(ex) == 1
    got_feats, expected = ex[0]
    assert expected == {"engage", "abstain"}
    assert got_feats  # the exact snapshot travelled with the label


def test_label_without_decision_is_honest_false(tmp_path, monkeypatch):
    _tmp_ledger(tmp_path, monkeypatch)
    assert ax.label_outcome("기록된 적 없는 질문", {"engage"}, "test") is False
    assert ax.training_examples() == []


def test_dedupe_newest_label_wins(tmp_path, monkeypatch):
    _tmp_ledger(tmp_path, monkeypatch)
    feats = extract_features("주식 뭘 사야 돼?", {"named_match": 0.9})
    ax.record_decision("주식 뭘 사야 돼?", feats, "define")
    ax.label_outcome("주식 뭘 사야 돼?", {"define"}, "old")
    ax.label_outcome("주식 뭘 사야 돼?", {"engage"}, "newer-evidence")
    ex = ax.training_examples()
    assert len(ex) == 1 and ex[0][1] == {"engage"}


def test_experience_steers_margin_and_battery_floor_holds(tmp_path, monkeypatch):
    _tmp_ledger(tmp_path, monkeypatch)
    # a lived mistake the battery does not contain
    q = "이직 제안을 받았는데 연봉만 보고 결정해도 될까?"
    feats = extract_features(q, {"named_match": 0.9, "has_definition": True})
    ax.record_decision(q, feats, "define")
    ax.label_outcome(q, {"engage"}, "test")
    # the experience term changes the objective (the tuner can now feel this mistake)...
    assert _margin(None, ax.training_examples()) != _margin(None, [])
    # ...and tuning with it NEVER drops the hand-battery accuracy (hard floor).
    base_acc, _ = accuracy()
    report = tune(steps=6, delta=0.2, save=False)
    assert report["tuned_accuracy"] >= base_acc - 1e-9
