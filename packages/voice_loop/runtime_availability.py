from __future__ import annotations

from dataclasses import asdict, dataclass
import importlib.util


@dataclass(frozen=True)
class RuntimeAvailability:
    runtime_id: str
    available: bool
    checked_modules: list[str]
    missing_modules: list[str]
    optional_channel: bool = True
    text_input_supported: bool = True
    microphone_enabled: bool = False
    generated_audio_persisted: bool = False
    local_brain_write: bool = False
    cloud_brain_write: bool = False

    def __post_init__(self) -> None:
        if not self.optional_channel or not self.text_input_supported:
            raise ValueError("voice runtime must remain optional and text input must remain supported")
        if self.microphone_enabled:
            raise ValueError("availability checks must not enable the microphone")
        if self.generated_audio_persisted or self.local_brain_write or self.cloud_brain_write:
            raise ValueError("availability checks must not persist audio or write memory")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def check_modules(runtime_id: str, modules: list[str]) -> RuntimeAvailability:
    """Check optional runtime imports without loading models or calling services."""

    missing: list[str] = []
    for module in modules:
        try:
            found = importlib.util.find_spec(module) is not None
        except ModuleNotFoundError:
            found = False
        if not found:
            missing.append(module)
    return RuntimeAvailability(
        runtime_id=runtime_id,
        available=not missing,
        checked_modules=modules,
        missing_modules=missing,
    )


def check_voice_runtime_availability() -> dict[str, RuntimeAvailability]:
    """Return safe availability checks for optional ASR/TTS runtimes."""

    return {
        "nemotron_asr": check_modules("nemotron_asr", ["nemo.collections.asr"]),
        "fish_2": check_modules("fish_2", ["fish_speech"]),
        "fish_1_5": check_modules("fish_1_5", ["fish_speech"]),
    }
