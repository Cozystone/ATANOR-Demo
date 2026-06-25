"""#3: inner-voice self-narration must match the conversation language.

In English mode the orange self-narration was leaking Korean ("warm 상태에서 …").
The surface is now language-aware.
"""

from __future__ import annotations

import re

from packages.inner_voice import emit_inner_voice_from_state

_HANGUL = re.compile(r"[가-힣]")


def _emit(language: str):
    return emit_inner_voice_from_state(
        source_event_id="conversation_router:test",
        mode="lab_visible",
        emotion_snapshot={"label": "warm"},
        latest_user_input="What is GraphRAG?",
        language=language,
    )


def test_english_inner_voice_has_no_hangul() -> None:
    frame = _emit("en")
    assert frame.monologue_text.strip()
    assert not _HANGUL.search(frame.monologue_text), f"Hangul leaked: {frame.monologue_text!r}"


def test_korean_inner_voice_is_unchanged() -> None:
    frame = _emit("ko")
    assert _HANGUL.search(frame.monologue_text), "Korean mode should still narrate in Korean"


def test_language_defaults_to_korean() -> None:
    # No language given -> default ko (backward compatible).
    frame = emit_inner_voice_from_state(
        source_event_id="x", emotion_snapshot={"label": "steady"}, latest_user_input="hi"
    )
    assert _HANGUL.search(frame.monologue_text)
