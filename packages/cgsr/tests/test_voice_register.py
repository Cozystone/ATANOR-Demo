"""ATANOR mirrors the user's register so its voice is consistent, not a stilted
mix of 반말 greeting + 존댓말 self-model. A polite/neutral message gets a warm
존댓말 reply; a clearly casual message keeps the casual reply. Deterministic."""
from __future__ import annotations

from packages.cgsr.cgsr.asm_v0 import _user_prefers_polite, _voice_polish, generate_surface


def test_register_detection():
    assert _user_prefers_polite("안녕하세요")
    assert _user_prefers_polite("작동 원리를 알려주세요")
    assert _user_prefers_polite("안녕")  # neutral → default polite (consistent voice)
    assert not _user_prefers_polite("네 작동 원리를 알려줘")  # clear 반말 → mirror casual


def test_polish_makes_greeting_polite():
    assert _voice_polish("안녕. 나 여기 있어.", "안녕하세요") == "안녕하세요. 나 여기 있어요."
    assert _voice_polish("응, 준비됐어.", "안녕") == "네, 준비됐어요."
    # casual user → reply left casual
    assert _voice_polish("안녕. 나 여기 있어.", "네 뭐해줘") == "안녕. 나 여기 있어."


def test_greeting_surface_is_polite_and_consistent():
    answer = generate_surface("안녕").answer or ""
    assert "안녕하세요" in answer
    assert "여기 있어" not in answer or "있어요" in answer  # not bare 반말 "있어"
