"use client";

import { FormEvent, useEffect, useState } from "react";
import { Mic, Send } from "lucide-react";
import HologramVoiceOrb, { HologramVoiceOrbState } from "./HologramVoiceOrb";

type Language = "en" | "ko";

export default function AtanorUserStatusCard({ language }: { language: Language }) {
  const [message, setMessage] = useState("");
  const [orbState, setOrbState] = useState<HologramVoiceOrbState>("idle");
  const placeholder = language === "ko" ? "ATANOR에게 말하기" : "Message ATANOR";

  useEffect(() => {
    if (orbState !== "listening") return;
    const thinkingTimer = window.setTimeout(() => setOrbState("thinking"), 1700);
    const speakingTimer = window.setTimeout(() => setOrbState("speaking"), 3300);
    const restingTimer = window.setTimeout(() => setOrbState("resting"), 5200);
    return () => {
      window.clearTimeout(thinkingTimer);
      window.clearTimeout(speakingTimer);
      window.clearTimeout(restingTimer);
    };
  }, [orbState]);

  function startVoiceDemo() {
    setOrbState("listening");
  }

  function cancelVoiceDemo() {
    setOrbState("resting");
  }

  function submitMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setOrbState("thinking");
    window.setTimeout(() => setOrbState("resting"), 1800);
  }

  return (
    <section className="atanor-ai-dashboard" aria-label="ATANOR hologram dashboard">
      <div className="atanor-hologram-logo" aria-label="ATANOR">
        <span>ATANOR</span>
      </div>
      <div className="atanor-hologram-stage">
        <HologramVoiceOrb state={orbState} onActivate={startVoiceDemo} onCancel={cancelVoiceDemo} />
      </div>
      <form className="atanor-hologram-composer" onSubmit={submitMessage}>
        <button type="button" aria-label={language === "ko" ? "음성 데모" : "Voice demo"} onClick={startVoiceDemo}>
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
