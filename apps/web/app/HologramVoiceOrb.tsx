"use client";

import { CSSProperties, useEffect, useMemo, useState } from "react";
import { Mic, MicOff } from "lucide-react";

export type HologramVoiceOrbState =
  | "idle"
  | "listening"
  | "thinking"
  | "speaking"
  | "resting"
  | "approval_needed"
  | "blocked";

type Language = "en" | "ko";

type HologramVoiceOrbProps = {
  language: Language;
  state: HologramVoiceOrbState;
  onActivate: () => void;
  onCancel: () => void;
};

const objectPresets = [
  { id: "seed", en: "seed crystal", ko: "씨앗 결정" },
  { id: "book", en: "open book", ko: "열린 책" },
  { id: "ring", en: "signal ring", ko: "신호 고리" },
  { id: "tree", en: "memory tree", ko: "기억 나무" },
  { id: "cube", en: "knowledge cube", ko: "지식 큐브" },
  { id: "comet", en: "moving comet", ko: "움직이는 혜성" },
] as const;

const stateText: Record<Language, Record<HologramVoiceOrbState, string>> = {
  en: {
    idle: "Ready",
    listening: "Listening demo",
    thinking: "Thinking",
    speaking: "Speaking",
    resting: "Resting",
    approval_needed: "Approval needed",
    blocked: "Blocked",
  },
  ko: {
    idle: "대화 준비",
    listening: "음성 입력 데모",
    thinking: "생각 중",
    speaking: "응답 중",
    resting: "휴식 중",
    approval_needed: "승인 필요",
    blocked: "차단됨",
  },
};

function particleStyle(objectId: string, index: number): CSSProperties {
  const total = 42;
  const t = index / total;
  const wave = Math.sin(t * Math.PI * 2);
  const bend = Math.cos(t * Math.PI * 4);
  let x = 50;
  let y = 50;
  let z = 0;
  let size = 5 + (index % 4);

  if (objectId === "book") {
    const side = index % 2 === 0 ? -1 : 1;
    x = 50 + side * (10 + t * 22);
    y = 42 + wave * 18 + Math.abs(side) * 4;
    z = bend * 22;
  } else if (objectId === "ring") {
    x = 50 + Math.cos(t * Math.PI * 2) * 30;
    y = 50 + Math.sin(t * Math.PI * 2) * 18;
    z = Math.sin(t * Math.PI * 4) * 36;
  } else if (objectId === "tree") {
    x = 50 + wave * (8 + t * 18);
    y = 72 - t * 48;
    z = bend * 26;
    size = t < 0.34 ? 6 : 4 + ((index + 1) % 4);
  } else if (objectId === "cube") {
    const face = index % 6;
    x = 50 + ((index % 7) - 3) * 7 + (face < 3 ? -8 : 8);
    y = 50 + ((Math.floor(index / 7) % 7) - 3) * 6;
    z = (face - 2.5) * 14;
  } else if (objectId === "comet") {
    x = 28 + t * 48;
    y = 56 - Math.sin(t * Math.PI) * 28 + bend * 3;
    z = (1 - t) * 46;
    size = 4 + Math.round((1 - t) * 7);
  } else {
    x = 50 + Math.cos(t * Math.PI * 2) * (8 + t * 22);
    y = 50 + Math.sin(t * Math.PI * 3) * (7 + t * 15);
    z = bend * 32;
  }

  return {
    "--x": `${x}%`,
    "--y": `${y}%`,
    "--z": `${z}px`,
    "--s": `${size}px`,
    "--delay": `${index * -72}ms`,
  } as CSSProperties;
}

export default function HologramVoiceOrb({ language, state, onActivate, onCancel }: HologramVoiceOrbProps) {
  const [objectIndex, setObjectIndex] = useState(0);
  const [mounted, setMounted] = useState(false);
  const object = objectPresets[objectIndex];
  const particles = useMemo(() => Array.from({ length: 42 }, (_, index) => index), []);
  const label = language === "ko"
    ? `ATANOR 홀로그램 대화 버튼, 현재 상태 ${stateText.ko[state]}`
    : `ATANOR hologram conversation button, current state ${stateText.en[state]}`;
  const visibleObjectName = language === "ko" ? object.ko : object.en;

  useEffect(() => {
    setMounted(true);
    const timer = window.setInterval(() => {
      setObjectIndex((current) => {
        const next = Math.floor(Math.random() * objectPresets.length);
        return next === current ? (current + 1) % objectPresets.length : next;
      });
    }, 4300);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <div className="hologram-voice-orb-shell" data-state={state}>
      <button
        type="button"
        className="hologram-voice-orb"
        data-state={state}
        data-object={object.id}
        aria-label={label}
        aria-pressed={state === "listening"}
        onClick={state === "listening" ? onCancel : onActivate}
      >
        <span className="hologram-voice-orb-aura" aria-hidden="true" />
        <span className="hologram-voice-orb-wave" aria-hidden="true" />
        <span className="hologram-voice-orb-core" aria-hidden="true">
          {mounted ? particles.map((particle) => (
            <span
              key={`${object.id}-${particle}`}
              className="hologram-voice-orb-splat"
              style={particleStyle(object.id, particle)}
            />
          )) : null}
        </span>
        <span className="hologram-voice-orb-icon" aria-hidden="true">
          {state === "listening" ? <MicOff size={22} strokeWidth={1.8} /> : <Mic size={22} strokeWidth={1.8} />}
        </span>
      </button>
      <div className="hologram-voice-orb-caption" aria-live="polite">
        <strong>{stateText[language][state]}</strong>
        <span>{visibleObjectName}</span>
      </div>
    </div>
  );
}
