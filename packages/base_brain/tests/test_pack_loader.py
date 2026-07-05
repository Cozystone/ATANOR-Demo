from packages.base_brain.pack_builder import build_base_brain_pack_v0
from packages.base_brain.pack_loader import get_semantic_context, get_surface_candidates, load_base_brain_pack


def test_pack_loader_matches_kubernetes() -> None:
    build_base_brain_pack_v0()
    pack = load_base_brain_pack()
    context = get_semantic_context("쿠버네티스가 뭐야?", pack)
    assert context
    assert context[0]["concept_id"] == "kubernetes"
    candidates = get_surface_candidates("쿠버네티스가 뭐야?", context, "ko", "beginner", pack=pack)
    assert candidates
    assert all(item["language"] == "ko" for item in candidates)


def test_substring_wrong_referent_blocked():
    """Maximal-match boundary rule: a concept name INSIDE a longer word must not match.
    Measured live bug: '방탄소년단이 뭐야' confidently answered about 탄소 (carbon), and
    '삼성전자란' about 전자 (the electron) — the chronic wrong-referent class."""
    from packages.base_brain.pack_loader import _named_with_boundary, _norm

    # interior-of-word matches are rejected...
    assert not _named_with_boundary(_norm("방탄소년단이 뭐야"), _norm("탄소"))
    assert not _named_with_boundary(_norm("삼성전자란?"), _norm("전자"))
    assert not _named_with_boundary(_norm("탄소나노튜브가 뭐야"), _norm("탄소"))
    # ...while legitimate name+particle forms still match
    assert _named_with_boundary(_norm("탄소란?"), _norm("탄소"))
    assert _named_with_boundary(_norm("그럼 전자는?"), _norm("전자"))
    assert _named_with_boundary(_norm("인공지능이 뭐야"), _norm("인공지능"))
    assert _named_with_boundary(_norm("docker가 뭐야"), _norm("docker"))
