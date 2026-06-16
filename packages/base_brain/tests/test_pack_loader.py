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
