# ATANOR Fish 2 Audio Runtime

Status: dashboard playback contract, local runtime not bundled.

ATANOR's hologram orb can enter a visual `speaking` state before any real
audio exists. The product must keep four states separate:

1. visual speaking animation;
2. local TTS runtime availability;
3. actual audio generation;
4. successful browser playback.

## Availability States

- `unavailable_missing_package`: Fish package is not installed.
- `unavailable_missing_model`: Fish package exists, but no local model path is
  configured.
- `unavailable_no_device`: required local device/audio packaging dependency is
  unavailable.
- `available_not_loaded`: package and model path are present, but synthesis has
  not been run.
- `available_loaded`: runtime is loaded.
- `synthesis_failed`: synthesis was attempted and failed.
- `synthesis_ok`: synthesis produced browser-playable audio.
- `fallback_mock`: proof fallback only; not real Fish audio.

## `voice_output` Contract

`/api/chat/atanor` returns a `voice_output` object for dashboard conversation
turns:

- `requested`: voice output was requested for the response.
- `enabled`: voice feature is enabled as an optional channel.
- `selected_engine`: `fish_2`, `fish_1_5`, `mock`, or `none`.
- `runtime_available`: whether a local runtime is ready.
- `audio_available`: whether real audio was generated for this turn.
- `audio_url`: browser-playable URL when audio exists, otherwise `null`.
- `audio_mime`: MIME type when audio exists.
- `audio_duration_ms`: duration when known.
- `error_reason`: explicit reason when audio is unavailable.
- `text_fallback`: always true for this proof surface.

If Fish is missing, ATANOR must return `audio_available=false`,
`audio_url=null`, and keep text replies available. It must not claim Fish spoke.

## Frontend Playback

The dashboard only creates an `Audio` element when
`voice_output.audio_available=true` and `voice_output.audio_url` exists. The
submit button or orb click provides the user gesture required by browser
autoplay policy. While audio is playing, the orb remains in the speaking visual
state; when audio ends, it returns to ready/idle.

If audio is unavailable or playback fails, the UI shows a small non-blocking
message and keeps the text response visible.

## Safety Boundaries

- No external LLM or sLLM is used.
- No external TTS service is called.
- Microphone recording is disabled by default.
- Always-on listening is disabled.
- Raw voice input is not saved.
- Generated audio files are not committed.
- Local Brain is not written.
- Production Cloud Brain is not mutated.
- Candidate promotion is not performed.

## Install Notes

Fish packages and model weights are intentionally not bundled in the repository.
To enable real playback later, install a local Fish runtime outside the repo and
configure a local model path such as `ATANOR_FISH2_MODEL_DIR` or
`FISH_SPEECH_MODEL_DIR`. The concrete Fish synthesis API must then be wired to
write only temporary ignored audio and return a browser-playable URL.

## Next Steps

- Fish 2 short synthesis proof with a locally installed model.
- Fish 1.5 fallback benchmark.
- Cleanup policy for ignored temp audio.
- SPLATRA orb audio-reactive shell/ribbon mapping.
