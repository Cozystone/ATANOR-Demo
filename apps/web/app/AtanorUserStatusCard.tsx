"use client";

import { useEffect, useState } from "react";
import HologramVoiceOrb, { HologramVoiceOrbState } from "./HologramVoiceOrb";

type Language = "en" | "ko";

type AtanorUserStatusCardProps = {
  language: Language;
  onMessageSubmit?: (message: string) => boolean;
};

export default function AtanorUserStatusCard({ language }: AtanorUserStatusCardProps) {
  const [orbState, setOrbState] = useState<HologramVoiceOrbState>("idle");

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

  return (
    <section className="atanor-ai-dashboard" aria-label={language === "ko" ? "ATANOR 파티클 본체" : "ATANOR particle body"}>
      <div className="atanor-hologram-stage">
        <HologramVoiceOrb state={orbState} onActivate={startVoiceDemo} onCancel={cancelVoiceDemo} />
      </div>
    </section>
  );
}
