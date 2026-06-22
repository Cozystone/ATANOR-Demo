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
  const naturalBreak = clean.search(/[.!?。？！]\s/);
  if (naturalBreak > 16 && naturalBreak < 64) return clean.slice(0, naturalBreak + 1);
  const commaBreak = clean.search(/[,，、]\s?/);
  if (commaBreak > 16 && commaBreak < 58) return clean.slice(0, commaBreak + 1);
  return `${clean.slice(0, 44).trim()}...`;
}

export default function AtanorUserStatusCard({ language, onMessageSubmit }: AtanorUserStatusCardProps) {
  const [message, setMessage] = useState("");
  const [orbState, setOrbState] = useState<HologramVoiceOrbState>("idle");
  const [voiceMode, setVoiceMode] = useState(false);
  const [speechLine, setSpeechLine] = useState("");
  const placeholder = voiceMode
    ? language === "ko" ? "음성 모드 · 텍스트도 입력 가능" : "Voice mode · text still works"
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
      const response = await fetch("/api/selfhood/thought-dry-run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: trimmed, language }),
      });
      if (!response.ok) throw new Error(`thought dry-run failed: ${response.status}`);
      const payload = await response.json();
      const nextState = String(payload?.orb_state ?? "");
      const finalText = String(payload?.final_tagged_text ?? "");
      setOrbState(validOrbStates.has(nextState as HologramVoiceOrbState) ? nextState as HologramVoiceOrbState : "speaking");
      setSpeechLine(firstSpeechBeat(finalText));
      setMessage("");
      window.setTimeout(() => setOrbState("listening"), 2900);
    } catch {
      setOrbState("blocked");
      setSpeechLine(language === "ko" ? "지금은 응답 경계가 닫혔어요." : "The response boundary is closed right now.");
      window.setTimeout(() => setOrbState(voiceMode ? "listening" : "resting"), 2600);
    }
  }

  return (
    <section className="atanor-ai-dashboard" aria-label={language === "ko" ? "ATANOR 파티클 본체" : "ATANOR particle body"} data-voice-mode={voiceMode ? "true" : "false"}>
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
