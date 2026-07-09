# -*- coding: utf-8 -*-
"""Collective code improvement: AI proposes -> swarm reviews -> three gates ->
federation manifest. Code is never auto-applied; all three gates are required."""


def _reset(monkeypatch, tmp_path):
    from packages.graph_scale import collective_improve as ci
    monkeypatch.setattr(ci, "LEDGER", tmp_path / "ci.jsonl")
    return ci


def test_three_gates_required_for_federation(tmp_path, monkeypatch):
    ci = _reset(monkeypatch, tmp_path)
    ci.submit("p1", module="engage.py", rationale="tighter np head",
              diff_summary="+2 -1", proposer="atanor")
    # swarm consensus (gate 1)
    for a, v in [("peer_a", "approve"), ("peer_b", "approve"), ("peer_c", "approve")]:
        ci.vote("p1", a, v)
    assert ci.board()[0]["status"] == "collective_approved"
    assert ci.federation_manifest()["count"] == 0          # tests + human still missing
    ci.mark("p1", tests_passed=True)
    assert ci.federation_manifest()["count"] == 0          # human still missing
    ci.mark("p1", human_approved=True)
    m = ci.federation_manifest()
    assert m["count"] == 1 and m["federation_ready"][0]["proposal_id"] == "p1"


def test_swarm_rejection_blocks_federation(tmp_path, monkeypatch):
    ci = _reset(monkeypatch, tmp_path)
    ci.submit("p2", module="x.py", rationale="risky", diff_summary="+50 -40")
    for a, v in [("peer_a", "reject"), ("peer_b", "reject"), ("peer_c", "approve")]:
        ci.vote("p2", a, v)
    assert ci.board()[0]["status"] == "collective_rejected"
    # even if a human/CI mistakenly marks it, collective gate still blocks
    ci.mark("p2", tests_passed=True, human_approved=True)
    assert ci.federation_manifest()["count"] == 0


def test_one_agent_one_vote(tmp_path, monkeypatch):
    ci = _reset(monkeypatch, tmp_path)
    ci.submit("p3", module="y.py", rationale="r", diff_summary="d")
    ci.vote("p3", "peer_a", "reject")
    ci.vote("p3", "peer_a", "approve")                     # re-vote replaces
    assert ci.board()[0]["tally"] == {"approve": 1, "reject": 0, "revise": 0}
