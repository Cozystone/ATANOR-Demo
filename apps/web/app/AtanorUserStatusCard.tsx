"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import type { CSSProperties } from "react";
import { Mic, Send } from "lucide-react";
import HologramVoiceOrb, { HologramVoiceOrbState } from "./HologramVoiceOrb";
import ParticleText from "./ParticleText";
import SplatraImaginationField from "./SplatraImaginationField";

type Language = "en" | "ko";

type AtanorUserStatusCardProps = {
  language: Language;
  onMessageSubmit?: (message: string) => boolean;
};

type VoiceOutput = {
  audio_available?: boolean;
  audio_url?: string | null;
  audio_mime?: string | null;
  error_reason?: string | null;
  user_message?: string | null;
  text_fallback?: boolean;
};

type VoiceWaveStyle = CSSProperties & {
  "--h": string;
  "--i": number;
};

function stripEmotionTag(text: string) {
  return text.replace(/^\[[^\]]+\]\s*/, "").trim();
}

function firstSpeechBeat(text: string) {
  const clean = stripEmotionTag(text);
  if (clean.length <= 46) return clean;
  const naturalBreak = clean.search(/[.!?]\s?/);
  if (naturalBreak > 16 && naturalBreak < 64) return clean.slice(0, naturalBreak + 1);
  const commaBreak = clean.search(/[,\u3001]\s?/);
  if (commaBreak > 16 && commaBreak < 58) return clean.slice(0, commaBreak + 1);
  return `${clean.slice(0, 44).trim()}...`;
}

function isAsmConversationPayload(payload: Record<string, any>) {
  const result = payload?.result ?? {};
  const engine = result?.answer_engine ?? {};
  const generationBasis = String(engine.generation_basis ?? "");
  const isAllowedLocalConversation =
    generationBasis === "local_corpus_construction_transition_model"
    || generationBasis === "semantic_grounded_conversation_router_v0";
  return (
    isAllowedLocalConversation
    && engine.external_llm === false
    && engine.external_sllm === false
    && engine.external_llm_used === false
    && engine.external_sllm_used === false
    && engine.rule_based_answer_used === false
    && engine.internal_trace_exposed === false
    && engine.local_brain_write === false
    && engine.production_store_mutated === false
    && engine.candidate_promotion === false
  );
}

function cleanSafeStatusLine(language: Language) {
  return language === "ko"
    ? "\uB85C\uCEEC \uB300\uD654 \uC5D4\uC9C4\uC744 \uD655\uC778\uD558\uB294 \uC911\uC785\uB2C8\uB2E4."
    : "The local conversation engine is being checked.";
}

function cleanVoiceUnavailableLine(language: Language) {
  return language === "ko"
    ? "\uC74C\uC131 \uC5D4\uC9C4\uC740 \uC544\uC9C1 \uC900\uBE44 \uC911\uC785\uB2C8\uB2E4. \uD14D\uC2A4\uD2B8 \uC751\uB2F5\uC740 \uACC4\uC18D \uC0AC\uC6A9\uD560 \uC218 \uC788\uC2B5\uB2C8\uB2E4."
    : "The voice engine is not installed yet. Text replies remain available.";
}

function cleanVoiceFailedLine(language: Language) {
  return language === "ko"
    ? "\uC74C\uC131 \uD569\uC131 \uC911 \uC624\uB958\uAC00 \uBC1C\uC0DD\uD588\uC2B5\uB2C8\uB2E4. \uD14D\uC2A4\uD2B8 \uC751\uB2F5\uC73C\uB85C \uACC4\uC18D\uD569\uB2C8\uB2E4."
    : "Voice synthesis failed. Continuing with text replies.";
}

function emitNeuralEmotionEvent(eventType: string, payloadSummary: string) {
  fetch("/api/neural-emotion/events/emit", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      source: "voice_loop",
      event_type: eventType,
      intensity: 0.45,
      payload_summary: payloadSummary,
    }),
  }).catch(() => undefined);
}

export default function AtanorUserStatusCard({ language, onMessageSubmit }: AtanorUserStatusCardProps) {
  const [message, setMessage] = useState("");
  const [orbState, setOrbState] = useState<HologramVoiceOrbState>("idle");
  const [voiceMode, setVoiceMode] = useState(false);
  const [speechLine, setSpeechLine] = useState("");
  const [voiceNotice, setVoiceNotice] = useState("");
  const [selfNarration, setSelfNarration] = useState("");
  const [audioPlaying, setAudioPlaying] = useState(false);
  const [emotionControls, setEmotionControls] = useState<Record<string, any> | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const speakingVisual = orbState === "speaking" || audioPlaying;
  const cleanPlaceholder = voiceMode
    ? language === "ko" ? "\uC74C\uC131 \uBAA8\uB4DC · \uD14D\uC2A4\uD2B8\uB3C4 \uC785\uB825\uD560 \uC218 \uC788\uC5B4\uC694" : "Voice mode · text still works"
    : language === "ko" ? "ATANOR\uC5D0\uAC8C \uB9D0\uD558\uAE30" : "Message ATANOR";
  useEffect(() => {
    if (orbState !== "listening") return;
    const thinkingTimer = window.setTimeout(() => setOrbState("thinking"), 1500);
    const speakingTimer = window.setTimeout(() => setOrbState("speaking"), 3200);
    return () => {
      window.clearTimeout(thinkingTimer);
      window.clearTimeout(speakingTimer);
    };
  }, [orbState]);

  useEffect(() => {
    if (!speechLine) return;
    const clearTimer = window.setTimeout(() => setSpeechLine(""), 5600);
    return () => window.clearTimeout(clearTimer);
  }, [speechLine]);

  useEffect(() => {
    if (!voiceNotice) return;
    const clearTimer = window.setTimeout(() => setVoiceNotice(""), 5200);
    return () => window.clearTimeout(clearTimer);
  }, [voiceNotice]);

  useEffect(() => {
    let cancelled = false;
    async function refreshEmotionControls() {
      const payload = await fetch("/api/neural-emotion/snapshot", { cache: "no-store" })
        .then((response) => response.json())
        .catch(() => null);
      if (!cancelled) {
        setEmotionControls(payload?.snapshot?.splatra_controls ?? payload?.splatra_controls ?? null);
      }
    }
    refreshEmotionControls().catch(() => undefined);
    const timer = window.setInterval(() => refreshEmotionControls().catch(() => undefined), 12000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function refreshSelfNarration() {
      const payload = await fetch("/api/inner-voice/status?workspace=product", { cache: "no-store" })
        .then((response) => response.json())
        .catch(() => null);
      const next = String(
        payload?.product_summary?.visible_self_narration
          ?? payload?.visible_self_narration
          ?? payload?.product_summary?.summary
          ?? "",
      ).trim();
      if (!cancelled && next) {
        setSelfNarration(next);
      }
    }
    refreshSelfNarration().catch(() => undefined);
    const timer = window.setInterval(() => refreshSelfNarration().catch(() => undefined), 2600);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  function stopAudio() {
    const audio = audioRef.current;
    if (audio) {
      audio.pause();
      audio.src = "";
    }
    audioRef.current = null;
    setAudioPlaying(false);
  }

  function startVoiceMode() {
    setVoiceMode(true);
    setOrbState("listening");
    setVoiceNotice("");
    setSpeechLine(language === "ko" ? "듣고 있어." : "I'm listening.");
  }

  function cancelVoiceMode() {
    stopAudio();
    setVoiceMode(false);
    setOrbState("resting");
    setSpeechLine("");
    setVoiceNotice("");
  }

  function primeVoiceAudioElement() {
    try {
      const audio = audioRef.current ?? new Audio();
      audio.muted = true;
      audio.preload = "auto";
      audio.src = "data:audio/wav;base64,UklGRigAAABXQVZFZm10IBAAAAABAAEAESsAACJWAAACABAAZGF0YQQAAAAAAA==";
      audioRef.current = audio;
      void audio.play().then(() => {
        audio.pause();
        audio.currentTime = 0;
        audio.muted = false;
      }).catch(() => undefined);
    } catch {
      audioRef.current = null;
    }
  }

  async function playVoiceOutput(voiceOutput: VoiceOutput | undefined) {
    if (!voiceOutput?.audio_available || !voiceOutput.audio_url) {
      stopAudio();
      setVoiceNotice(voiceOutput?.user_message || cleanVoiceUnavailableLine(language));
      return;
    }
    try {
      const audio = audioRef.current ?? new Audio();
      audio.pause();
      audio.muted = false;
      audio.src = voiceOutput.audio_url;
      audio.preload = "auto";
      audio.onplaying = () => {
        setAudioPlaying(true);
        setOrbState("speaking");
        emitNeuralEmotionEvent("speaking_start", "audio playback started");
      };
      audio.onended = () => {
        setAudioPlaying(false);
        setOrbState(voiceMode ? "listening" : "resting");
        emitNeuralEmotionEvent("speaking_end", "audio playback ended");
      };
      audio.onerror = () => {
        setAudioPlaying(false);
        setVoiceNotice(cleanVoiceFailedLine(language));
        setOrbState(voiceMode ? "listening" : "resting");
        emitNeuralEmotionEvent("voice_unavailable", "audio playback error");
      };
      audioRef.current = audio;
      audio.load();
      await audio.play();
    } catch {
      setAudioPlaying(false);
      setVoiceNotice(cleanVoiceFailedLine(language));
      setOrbState(voiceMode ? "listening" : "resting");
      emitNeuralEmotionEvent("voice_unavailable", "audio playback unavailable");
    }
  }

  async function submitMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = message.trim();
    if (!trimmed) return;

    if (onMessageSubmit?.(trimmed)) {
      setMessage("");
      setSpeechLine("");
      setVoiceNotice("");
      return;
    }

    setVoiceMode(true);
    setOrbState("thinking");
    setVoiceNotice("");
    setSpeechLine(language === "ko" ? "잠깐 생각할게." : "Let me think.");
    primeVoiceAudioElement();
    try {
      const response = await fetch("/api/chat/atanor", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: trimmed,
          language,
          mode: "conversation",
          brain_mode: "conversation",
          include_trace: false,
        }),
      });
      if (!response.ok) throw new Error(`conversation surface failed: ${response.status}`);
      const payload = await response.json();
      const answer = String(payload?.result?.answer ?? "");
      if (!answer || !isAsmConversationPayload(payload)) {
        throw new Error("conversation surface unavailable");
      }
      setOrbState("speaking");
      void fetch("/api/inner-voice/emit", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          source_event_id: "product_hologram_conversation",
          mode: "product_summary",
          latest_user_input: trimmed,
          latest_action_result: {
            speech_act: payload?.result?.answer_kind ?? "conversation",
            answered: true,
          },
          review_queue_pressure: 0,
          permission_tier: "OBSERVE_ONLY",
        }),
      })
        .then((response) => response.json())
        .then((innerVoicePayload) => {
          const next = String(
            innerVoicePayload?.product_summary?.visible_self_narration
              ?? innerVoicePayload?.product_summary?.summary
              ?? "",
          ).trim();
          if (next) setSelfNarration(next);
        })
        .catch(() => undefined);
      emitNeuralEmotionEvent("speaking_start", "text conversation visible speech");
      setSpeechLine(firstSpeechBeat(answer));
      setMessage("");
      await playVoiceOutput(payload?.result?.voice_output);
      if (!payload?.result?.voice_output?.audio_available) {
        window.setTimeout(() => {
          setOrbState("listening");
          emitNeuralEmotionEvent("speaking_end", "text fallback speech ended");
        }, 2900);
      }
    } catch {
      setOrbState("blocked");
      setSpeechLine(cleanSafeStatusLine(language));
      setVoiceNotice(cleanVoiceFailedLine(language));
      window.setTimeout(() => setOrbState(voiceMode ? "listening" : "resting"), 2600);
    }
  }

  return (
    <section
      className="atanor-ai-dashboard"
      aria-label={language === "ko" ? "ATANOR 입자 본체" : "ATANOR particle body"}
      data-voice-mode={voiceMode ? "true" : "false"}
      data-speaking={speakingVisual ? "true" : "false"}
    >
      <SplatraImaginationField
        state={orbState}
        mode="product"
        particleBudget={960}
        interactive={false}
        controlOverride={emotionControls ?? undefined}
        className="atanor-dashboard-imagination-field"
      />
      <div className="atanor-hologram-stage">
        <HologramVoiceOrb state={orbState} onActivate={startVoiceMode} onCancel={cancelVoiceMode} />
        {selfNarration ? (
          <ParticleText
            text={selfNarration}
            tone="self"
            className="atanor-hologram-self-narration"
            speedMs={28}
            maxLines={3}
            aria-live="polite"
          />
        ) : null}
        {speechLine ? (
          <ParticleText
            text={speechLine}
            tone="speech"
            className="atanor-hologram-speech"
            speedMs={24}
            maxLines={2}
            aria-live="polite"
          />
        ) : null}
        {voiceNotice ? (
          <p className="atanor-hologram-voice-status" aria-live="polite">
            {voiceNotice}
          </p>
        ) : null}
      </div>
      <form className="atanor-hologram-composer" data-voice-mode={voiceMode ? "true" : "false"} onSubmit={submitMessage}>
        <button type="button" aria-label={language === "ko" ? "음성 대화 모드" : "Voice conversation mode"} onClick={voiceMode ? cancelVoiceMode : startVoiceMode}>
          <Mic size={18} strokeWidth={1.8} />
        </button>
        <div className="atanor-voice-wave" aria-hidden="true">
          {Array.from({ length: 17 }, (_, index) => (
            <span key={index} style={{ "--h": `${8 + (index % 6) * 3}px`, "--i": index } as VoiceWaveStyle} />
          ))}
        </div>
        <input
          aria-label={cleanPlaceholder}
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          placeholder={cleanPlaceholder}
        />
        <button type="submit" aria-label={language === "ko" ? "보내기" : "Send"}>
          <Send size={18} strokeWidth={1.8} />
        </button>
      </form>
    </section>
  );
}
