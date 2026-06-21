from __future__ import annotations

from collections.abc import Iterable

from packages.voice_loop.models import VoiceOutputEvent
from packages.voice_loop.tts_adapter import TTSAdapter, TTSRuntimeUnavailable


class FishTTSAdapter(TTSAdapter):
    """Local Fish Speech adapter shell with safe fallback semantics.

    The adapter intentionally does not download weights, clone voices, or
    persist generated audio. Runtime-specific wiring can be added only after
    explicit model installation and voice-profile consent gates exist.
    """

    def __init__(self, engine: str = "fish_2", allow_voice_clone: bool = False) -> None:
        if allow_voice_clone:
            raise ValueError("voice cloning is disabled without explicit future consent")
        if engine not in {"fish_2", "fish_1_5"}:
            raise ValueError("engine must be fish_2 or fish_1_5")
        self.engine = engine
        self._loaded = False
        self._unavailable_reason: str | None = None

    def load(self) -> None:
        candidates = ["fish_speech", "fish_audio_sdk"] if self.engine == "fish_2" else ["fish_speech"]
        for module_name in candidates:
            try:
                __import__(module_name)
                self._loaded = True
                return
            except Exception as exc:  # pragma: no cover - optional runtime
                self._unavailable_reason = f"{module_name} unavailable: {exc}"
        raise TTSRuntimeUnavailable(self._unavailable_reason or "Fish runtime unavailable")

    def is_available(self) -> bool:
        if self._loaded:
            return True
        try:
            self.load()
        except TTSRuntimeUnavailable:
            return False
        return True

    def runtime_info(self) -> dict[str, object]:
        return {
            "adapter": "fish_tts",
            "engine": self.engine,
            "available": self._loaded,
            "unavailable_reason": self._unavailable_reason,
            "voice_clone_enabled": False,
            "generated_audio_persisted": False,
            "external_service": False,
        }

    def synthesize(self, text: str, language: str, style: str) -> VoiceOutputEvent:
        if not self.is_available():
            raise TTSRuntimeUnavailable(self._unavailable_reason or "Fish runtime unavailable")
        return VoiceOutputEvent(
            event_id=f"{self.engine}_event",
            text=text,
            language=language,
            tts_engine=self.engine,
            audio_path=None,
            streaming=False,
            generated_audio_persisted=False,
            requires_user_review=True,
            metadata={"style": style, "proof_mode": True},
        )

    def synthesize_stream(self, text: str, language: str, style: str) -> Iterable[VoiceOutputEvent]:
        yield self.synthesize(text, language, style)
