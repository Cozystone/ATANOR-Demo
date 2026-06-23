from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re
import shutil
import subprocess
import time
import uuid


MAX_TTS_CHARS = 480
_AUDIO_NAME_RE = re.compile(r"^atanor_voice_[a-f0-9]{32}\.wav$")


@dataclass(frozen=True)
class LocalTTSResult:
    engine: str
    audio_path: Path
    audio_url: str
    audio_mime: str = "audio/wav"
    duration_ms: int | None = None


class LocalTTSUnavailable(RuntimeError):
    pass


def local_voice_audio_dir() -> Path:
    configured = os.getenv("ATANOR_VOICE_AUDIO_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.cwd() / "runtime" / "voice_loop" / "audio").resolve()


def is_valid_voice_audio_name(filename: str) -> bool:
    return bool(_AUDIO_NAME_RE.fullmatch(filename))


def voice_audio_path(filename: str) -> Path:
    if not is_valid_voice_audio_name(filename):
        raise ValueError("invalid voice audio filename")
    return local_voice_audio_dir() / filename


def cleanup_old_voice_audio(max_age_seconds: int = 60 * 60) -> None:
    root = local_voice_audio_dir()
    if not root.exists():
        return
    cutoff = time.time() - max_age_seconds
    for path in root.glob("atanor_voice_*.wav"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
        except OSError:
            continue


def synthesize_windows_sapi(text: str, *, language: str = "ko") -> LocalTTSResult:
    """Generate a browser-playable WAV with the local Windows speech engine.

    This is a local fallback for audible product feedback. It does not call an
    external service, clone a user's voice, or persist raw microphone input.
    Fish remains the preferred engine when a concrete local Fish synthesis
    adapter is configured.
    """

    if os.name != "nt":
        raise LocalTTSUnavailable("windows_sapi_unavailable_on_non_windows")
    if os.getenv("ATANOR_ENABLE_WINDOWS_TTS_FALLBACK", "1") == "0":
        raise LocalTTSUnavailable("windows_sapi_fallback_disabled")

    executable = shutil.which("powershell") or shutil.which("pwsh")
    if not executable:
        raise LocalTTSUnavailable("powershell_not_found")

    safe_text = re.sub(r"\s+", " ", text).strip()[:MAX_TTS_CHARS]
    if not safe_text:
        raise LocalTTSUnavailable("empty_tts_text")

    root = local_voice_audio_dir()
    root.mkdir(parents=True, exist_ok=True)
    cleanup_old_voice_audio()

    stem = f"atanor_voice_{uuid.uuid4().hex}"
    text_path = root / f"{stem}.txt"
    script_path = root / f"{stem}.ps1"
    audio_path = root / f"{stem}.wav"

    script = r"""
param(
    [string]$TextPath,
    [string]$OutPath,
    [string]$Language
)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Speech
$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $text = [System.IO.File]::ReadAllText($TextPath, [System.Text.Encoding]::UTF8)
    $voices = $speaker.GetInstalledVoices() | Where-Object {
        $_.Enabled -and (
            $_.VoiceInfo.Culture.Name -like "$Language*" -or
            $_.VoiceInfo.Name -match "Korean|Heami|Zira|David"
        )
    }
    if ($voices.Count -gt 0) {
        $speaker.SelectVoice($voices[0].VoiceInfo.Name)
    }
    $speaker.Rate = 0
    $speaker.Volume = 100
    $speaker.SetOutputToWaveFile($OutPath)
    $speaker.Speak($text)
}
finally {
    $speaker.Dispose()
}
"""

    try:
        text_path.write_text(safe_text, encoding="utf-8")
        script_path.write_text(script, encoding="utf-8")
        proc = subprocess.run(
            [
                executable,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script_path),
                str(text_path),
                str(audio_path),
                "ko" if language == "ko" else "en",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "windows_sapi_failed").strip()
            raise LocalTTSUnavailable(detail[:240])
        if not audio_path.exists() or audio_path.stat().st_size <= 44:
            raise LocalTTSUnavailable("windows_sapi_empty_audio")
    finally:
        for path in (text_path, script_path):
            try:
                path.unlink()
            except OSError:
                pass

    return LocalTTSResult(
        engine="windows_sapi",
        audio_path=audio_path,
        audio_url=f"/api/voice-loop/audio/{audio_path.name}",
    )
