"use client";

import { FormEvent, useEffect, useState } from "react";
import { Mic, Send } from "lucide-react";
import HologramVoiceOrb, { HologramVoiceOrbState } from "./HologramVoiceOrb";

type Language = "en" | "ko";

type AtanorUserStatusCardProps = {
  language: Language;
  onMessageSubmit?: (message: string) => boolean;
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

export default function AtanorUserStatusCard({ language, onMessageSubmit }: AtanorUserStatusCardProps) {
  const [message, setMessage] = useState("");
  const [orbState, setOrbState] = useState<HologramVoiceOrbState>("idle");
  const placeholder = language === "ko" ? "ATANOR에게 말하기" : "Message ATANOR";

  useEffect(() => {
    if (orbState !== "listening") return;
    const thinkingTimer = window.setTimeout(() => setOrbState("thinking"), 1500);
    const speakingTimer = window.setTimeout(() => setOrbState("speaking"), 3200);
    const restingTimer = window.setTimeout(() => setOrbState("resting"), 5400);
    return () => {
      window.clearTimeout(thinkingTimer);
      window.clearTimeout(speakingTimer);
      window.clearTimeout(restingTimer);
    };
  }, [orbState]);

  function startVoiceDemo() {
    setOrbState((current) => current === "listening" ? "resting" : "listening");
  }

  function cancelVoiceDemo() {
    setOrbState("resting");
  }

  async function submitMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = message.trim();
    if (!trimmed) return;

    if (onMessageSubmit?.(trimmed)) {
      setMessage("");
      return;
    }

    setOrbState("thinking");
    try {
      const response = await fetch("/api/selfhood/thought-dry-run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: trimmed, language }),
      });
      if (!response.ok) throw new Error(`thought dry-run failed: ${response.status}`);
      const payload = await response.json();
      const nextState = String(payload?.orb_state ?? "");
      setOrbState(validOrbStates.has(nextState as HologramVoiceOrbState) ? nextState as HologramVoiceOrbState : "speaking");
      setMessage("");
      window.setTimeout(() => setOrbState("resting"), 2600);
    } catch {
      setOrbState("blocked");
      window.setTimeout(() => setOrbState("resting"), 2400);
    }
  }

  return (
    <section className="atanor-ai-dashboard" aria-label={language === "ko" ? "ATANOR 파티클 본체" : "ATANOR particle body"}>
      <div className="atanor-hologram-stage">
        <HologramVoiceOrb state={orbState} onActivate={startVoiceDemo} onCancel={cancelVoiceDemo} />
      </div>
      <form className="atanor-hologram-composer" onSubmit={submitMessage}>
        <button type="button" aria-label={language === "ko" ? "음성 상태 전환" : "Toggle voice state"} onClick={startVoiceDemo}>
          <Mic size={18} strokeWidth={1.8} />
        </button>
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
