"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import type { CSSProperties } from "react";
import { Mic, Send } from "lucide-react";
import HologramVoiceOrb, { HologramVoiceOrbState } from "./HologramVoiceOrb";

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
  const commaBreak = clean.search(/[,，]\s?/);
  if (commaBreak > 16 && commaBreak < 58) return clean.slice(0, commaBreak + 1);
  return `${clean.slice(0, 44).trim()}...`;
}

function safeStatusLine(language: Language) {
  return language === "ko"
    ? "로컬 대화 엔진을 확인하는 중입니다."
    : "The local conversation engine is being checked.";
}

function voiceUnavailableLine(language: Language) {
  return language === "ko"
    ? "음성 엔진이 아직 설치되어 있지 않습니다. 텍스트 응답은 계속 사용할 수 있습니다."
    : "The voice engine is not installed yet. Text replies remain available.";
}

function voiceFailedLine(language: Language) {
  return language === "ko"
    ? "음성 합성 중 오류가 발생했습니다. 텍스트 응답으로 계속합니다."
    : "Voice synthesis failed. Continuing with text replies.";
}

function isAsmConversationPayload(payload: Record<string, any>) {
  const result = payload?.result ?? {};
  const engine = result?.answer_engine ?? {};
  return (
    engine.generation_basis === "local_corpus_construction_transition_model"
    && engine.external_llm === false
    && engine.external_sllm === false
    && engine.rule_based_answer_used === false
    && engine.template_free_surface === true
    && engine.internal_trace_exposed === false
  );
}

export default function AtanorUserStatusCard({ language, onMessageSubmit }: AtanorUserStatusCardProps) {
  const [message, setMessage] = useState("");
  const [orbState, setOrbState] = useState<HologramVoiceOrbState>("idle");
  const [voiceMode, setVoiceMode] = useState(false);
  const [speechLine, setSpeechLine] = useState("");
  const [voiceNotice, setVoiceNotice] = useState("");
  const [audioPlaying, setAudioPlaying] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const placeholder = voiceMode
    ? language === "ko" ? "음성 모드 · 텍스트도 입력할 수 있어요" : "Voice mode · text still works"
    : language === "ko" ? "ATANOR에게 말하기" : "Message ATANOR";
  const speakingVisual = orbState === "speaking" || audioPlaying;

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

  async function playVoiceOutput(voiceOutput: VoiceOutput | undefined) {
    stopAudio();
    if (!voiceOutput?.audio_available || !voiceOutput.audio_url) {
      setVoiceNotice(voiceOutput?.user_message || voiceUnavailableLine(language));
      return;
    }
    try {
      const audio = new Audio(voiceOutput.audio_url);
      audio.preload = "auto";
      audio.onplaying = () => {
        setAudioPlaying(true);
        setOrbState("speaking");
      };
      audio.onended = () => {
        setAudioPlaying(false);
        setOrbState(voiceMode ? "listening" : "resting");
      };
      audio.onerror = () => {
        setAudioPlaying(false);
        setVoiceNotice(voiceFailedLine(language));
        setOrbState(voiceMode ? "listening" : "resting");
      };
      audioRef.current = audio;
      await audio.play();
    } catch {
      setAudioPlaying(false);
      setVoiceNotice(voiceFailedLine(language));
      setOrbState(voiceMode ? "listening" : "resting");
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
      setSpeechLine(firstSpeechBeat(answer));
      setMessage("");
      await playVoiceOutput(payload?.result?.voice_output);
      if (!payload?.result?.voice_output?.audio_available) {
        window.setTimeout(() => setOrbState("listening"), 2900);
      }
    } catch {
      setOrbState("blocked");
      setSpeechLine(safeStatusLine(language));
      setVoiceNotice(voiceFailedLine(language));
      window.setTimeout(() => setOrbState(voiceMode ? "listening" : "resting"), 2600);
    }
  }

  return (
    <section
      className="atanor-ai-dashboard"
      aria-label={language === "ko" ? "ATANOR 파티클 본체" : "ATANOR particle body"}
      data-voice-mode={voiceMode ? "true" : "false"}
      data-speaking={speakingVisual ? "true" : "false"}
    >
      <div className="atanor-hologram-stage">
        <HologramVoiceOrb state={orbState} onActivate={startVoiceMode} onCancel={cancelVoiceMode} />
        {speechLine ? (
          <p className="atanor-hologram-speech" aria-live="polite">
            {speechLine}
          </p>
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
          aria-label={placeholder}
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          placeholder={placeholder}
        />
        <button type="submit" aria-label={language === "ko" ? "보내기" : "Send"}>
          <Send size={18} strokeWidth={1.8} />
        </button>
      </form>
    </section>
  );
}
