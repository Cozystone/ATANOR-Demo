"use client";

import { FormEvent, useEffect, useState } from "react";
import type { CSSProperties } from "react";
import { Mic, Send } from "lucide-react";
import HologramVoiceOrb, { HologramVoiceOrbState } from "./HologramVoiceOrb";

type Language = "en" | "ko";

type AtanorUserStatusCardProps = {
  language: Language;
  onMessageSubmit?: (message: string) => boolean;
};

type VoiceWaveStyle = CSSProperties & {
  "--h": string;
  "--i": number;
};

const validOrbStates = new Set<HologramVoiceOrbState>([
  "idle",
  "listening",
  "thinking",
  "speaking",
  "resting",
  "approval_needed",
  "blocked",
]);

function stripEmotionTag(text: string) {
  return text.replace(/^\[[^\]]+\]\s*/, "").trim();
}

function firstSpeechBeat(text: string) {
  const clean = stripEmotionTag(text);
  if (clean.length <= 46) return clean;
  const naturalBreak = clean.search(/[.!?。！？]\s?/);
  if (naturalBreak > 16 && naturalBreak < 64) return clean.slice(0, naturalBreak + 1);
  const commaBreak = clean.search(/[,，、]\s?/);
  if (commaBreak > 16 && commaBreak < 58) return clean.slice(0, commaBreak + 1);
  return `${clean.slice(0, 44).trim()}...`;
}

function safeStatusLine(language: Language) {
  return language === "ko"
    ? "로컬 대화 엔진 연결을 확인하는 중입니다."
    : "The local conversation engine is being checked.";
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
  const placeholder = voiceMode
    ? language === "ko" ? "음성 모드 · 텍스트도 입력할 수 있어요" : "Voice mode · text still works"
    : language === "ko" ? "ATANOR에게 말하기" : "Message ATANOR";

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

  function startVoiceMode() {
    setVoiceMode(true);
    setOrbState("listening");
    setSpeechLine(language === "ko" ? "듣고 있어요." : "I'm listening.");
  }

  function cancelVoiceMode() {
    setVoiceMode(false);
    setOrbState("resting");
    setSpeechLine("");
  }

  async function submitMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = message.trim();
    if (!trimmed) return;

    if (onMessageSubmit?.(trimmed)) {
      setMessage("");
      setSpeechLine("");
      return;
    }

    setVoiceMode(true);
    setOrbState("thinking");
    setSpeechLine(language === "ko" ? "잠깐 생각할게요." : "Let me think.");
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
      window.setTimeout(() => setOrbState("listening"), 2900);
    } catch {
      setOrbState("blocked");
      setSpeechLine(safeStatusLine(language));
      window.setTimeout(() => setOrbState(voiceMode ? "listening" : "resting"), 2600);
    }
  }

  return (
    <section
      className="atanor-ai-dashboard"
      aria-label={language === "ko" ? "ATANOR 파티클 본체" : "ATANOR particle body"}
      data-voice-mode={voiceMode ? "true" : "false"}
      data-speaking={orbState === "speaking" ? "true" : "false"}
    >
      <div className="atanor-hologram-stage">
        <HologramVoiceOrb state={orbState} onActivate={startVoiceMode} onCancel={cancelVoiceMode} />
        {speechLine ? (
          <p className="atanor-hologram-speech" aria-live="polite">
            {speechLine}
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
