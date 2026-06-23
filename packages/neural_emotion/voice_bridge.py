from __future__ import annotations

from typing import Any

from .models import EmotionVector, clamp


def voice_controls(vector: EmotionVector, *, selected_engine: str = "fallback", audio_available: bool = False) -> dict[str, Any]:
    energy = clamp(0.32 + max(0.0, vector.arousal) * 0.38 + vector.speaking_energy * 0.28 - vector.fatigue * 0.18, 0.0, 1.0)
    speed = clamp(0.92 + max(0.0, vector.arousal) * 0.14 - vector.fatigue * 0.12, 0.75, 1.18)
    pitch_shift = clamp(vector.valence * 0.08 + max(0.0, vector.arousal) * 0.04 - vector.fatigue * 0.05, -0.18, 0.18)
    caution = vector.caution
    tag = "[whispering]" if caution > 0.78 else "[sigh]" if vector.fatigue > 0.72 else "[laugh]" if vector.valence > 0.46 else ""
    return {
        "selected_engine": selected_engine,
        "audio_available": bool(audio_available),
        "planned_only": not audio_available,
        "speed": round(speed, 4),
        "pitch_shift": round(pitch_shift, 4),
        "energy": round(energy, 4),
        "temperature": round(clamp(0.52 + vector.curiosity * 0.18 - caution * 0.12, 0.25, 0.8), 4),
        "top_p": round(clamp(0.72 + vector.curiosity * 0.12 - caution * 0.14, 0.45, 0.92), 4),
        "emotion_hint": "cautious" if caution > 0.65 else "curious" if vector.curiosity > 0.68 else "warm" if vector.valence > 0.28 else "calm",
        "tts_tag": tag,
        "fish_unavailable_fallback_valid": selected_engine == "fallback" or not audio_available,
        "real_emotion_claim": False,
    }


def attach_voice_plan_metadata(payload: dict[str, Any], vector: EmotionVector) -> dict[str, Any]:
    next_payload = dict(payload)
    next_payload["neural_emotion_voice_controls"] = voice_controls(vector)
    return next_payload
