"use client";

import { FormEvent, useEffect, useState } from "react";
import { Bell, Brain, CheckCircle2, Mic, ShieldCheck, Sparkles } from "lucide-react";
import HologramVoiceOrb, { HologramVoiceOrbState } from "./HologramVoiceOrb";

type Language = "en" | "ko";

const copy = {
  en: {
    eyebrow: "ATANOR conversation",
    title: "Ask the AI that remembers only with permission.",
    body: "A calm first screen for text, optional voice, daily briefs, prepared proposals, and visible safety locks. Internal labs stay in Lab/Developer mode.",
    inputLabel: "Message ATANOR",
    inputPlaceholder: "Ask what changed, what needs approval, or what ATANOR is preparing.",
    send: "Send",
    voice: "Voice",
    stop: "Stop",
    voiceUnavailable: "Voice input is not ready yet. Text input remains available.",
    demoListening: "Voice demo is listening locally. No microphone stream is saved.",
    demoThinking: "ATANOR is preparing a proof-only response preview.",
    demoSpeaking: "Response pulse preview complete. Memory is unchanged.",
    todayBriefLabel: "Today's brief",
    todayBrief: "Morning, evening, and status briefs can be prepared without changing personal memory.",
    proposalsLabel: "Prepared proposals",
    proposals: "Patch, memory, and promotion proposals wait for review before anything changes.",
    approvalsLabel: "Pending approvals",
    approvals: "Personal memory writes, shared knowledge promotion, and private memory actions stay approval-gated.",
    safetyLabel: "Memory and knowledge safety",
    safety: "Personal memory, shared knowledge, and current conversation context remain separate until you approve a change.",
    chips: ["What changed overnight?", "What should I approve?", "Explain your current self-model"],
    stateReady: "Ready for text",
    stateThinking: "Thinking locally",
    stateResting: "Resting",
  },
  ko: {
    eyebrow: "ATANOR 대화",
    title: "허락받은 것만 기억하는 AI와 대화합니다.",
    body: "첫 화면은 대화가 중심입니다. 텍스트 입력, 선택형 음성, 오늘의 브리프, 준비된 제안, 안전 잠금만 보여주고 내부 실험 패널은 Lab/Developer 모드에 둡니다.",
    inputLabel: "ATANOR에게 말하기",
    inputPlaceholder: "밤사이에 바뀐 것, 승인할 것, ATANOR가 준비 중인 것을 물어보세요.",
    send: "보내기",
    voice: "음성",
    stop: "중지",
    voiceUnavailable: "음성 입력은 아직 준비 중입니다. 텍스트 입력은 계속 사용할 수 있습니다.",
    demoListening: "음성 데모가 로컬에서 듣는 중입니다. 마이크 스트림은 저장하지 않습니다.",
    demoThinking: "ATANOR가 proof-only 응답 미리보기를 준비 중입니다.",
    demoSpeaking: "응답 파동 미리보기가 끝났습니다. 기억은 바뀌지 않았습니다.",
    todayBriefLabel: "오늘의 브리프",
    todayBrief: "아침, 저녁, 상태 브리프는 개인 기억을 바꾸지 않고 준비됩니다.",
    proposalsLabel: "준비된 제안",
    proposals: "패치, 기억, 승격 제안은 무엇이든 바뀌기 전에 검토 대기로 남습니다.",
    approvalsLabel: "승인 대기",
    approvals: "개인 기억 쓰기, 공용 지식 승격, 개인 기억 작업은 모두 승인 게이트를 통과해야 합니다.",
    safetyLabel: "기억과 지식 안전",
    safety: "개인 기억, 공용 지식, 현재 대화 맥락은 사용자가 승인하기 전까지 분리됩니다.",
    chips: ["밤사이에 무엇이 바뀌었어?", "내가 승인해야 할 것은?", "지금 자기 모델을 설명해줘"],
    stateReady: "텍스트 대기",
    stateThinking: "로컬에서 생각 중",
    stateResting: "휴식 중",
  },
} satisfies Record<Language, Record<string, string | string[]>>;

export default function AtanorUserStatusCard({ language }: { language: Language }) {
  const t = copy[language];
  const [message, setMessage] = useState("");
  const [orbState, setOrbState] = useState<HologramVoiceOrbState>("idle");
  const [notice, setNotice] = useState<string>(t.voiceUnavailable as string);

  useEffect(() => {
    if (orbState !== "listening") return;
    const thinkingTimer = window.setTimeout(() => {
      setOrbState("thinking");
      setNotice(t.demoThinking as string);
    }, 2200);
    const speakingTimer = window.setTimeout(() => {
      setOrbState("speaking");
      setNotice(t.demoSpeaking as string);
    }, 3900);
    const restingTimer = window.setTimeout(() => {
      setOrbState("resting");
    }, 5600);
    return () => {
      window.clearTimeout(thinkingTimer);
      window.clearTimeout(speakingTimer);
      window.clearTimeout(restingTimer);
    };
  }, [orbState, t.demoSpeaking, t.demoThinking]);

  useEffect(() => {
    setNotice(t.voiceUnavailable as string);
    setOrbState("idle");
  }, [language, t.voiceUnavailable]);

  function startVoiceDemo() {
    setOrbState("listening");
    setNotice(t.demoListening as string);
  }

  function cancelVoiceDemo() {
    setOrbState("resting");
    setNotice(t.voiceUnavailable as string);
  }

  function submitMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setOrbState("thinking");
    setNotice(language === "ko" ? "텍스트 입력을 받았습니다. 실제 기억 변경은 승인 후에만 가능합니다." : "Text received. Memory changes still require approval.");
    window.setTimeout(() => setOrbState("resting"), 1800);
  }

  const statusCards = [
    { label: t.todayBriefLabel as string, value: t.todayBrief as string, icon: Bell, state: "idle" as HologramVoiceOrbState },
    { label: t.proposalsLabel as string, value: t.proposals as string, icon: Sparkles, state: "approval_needed" as HologramVoiceOrbState },
    { label: t.approvalsLabel as string, value: t.approvals as string, icon: ShieldCheck, state: "approval_needed" as HologramVoiceOrbState },
    { label: t.safetyLabel as string, value: t.safety as string, icon: Brain, state: "blocked" as HologramVoiceOrbState },
  ];

  return (
    <section className="atanor-ai-dashboard" aria-label={t.eyebrow as string}>
      <article className="atanor-ai-hero">
        <div className="atanor-ai-hero-copy">
          <span>{t.eyebrow}</span>
          <h1>{t.title}</h1>
          <p>{t.body}</p>
          <form className="atanor-ai-composer" onSubmit={submitMessage}>
            <label htmlFor="atanor-dashboard-message">{t.inputLabel}</label>
            <div>
              <input
                id="atanor-dashboard-message"
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                placeholder={t.inputPlaceholder as string}
              />
              <button type="submit">{t.send}</button>
            </div>
          </form>
          <div className="atanor-ai-chip-row">
            {(t.chips as string[]).map((chip) => (
              <button key={chip} type="button" onClick={() => setMessage(chip)}>
                {chip}
              </button>
            ))}
          </div>
        </div>

        <div className="atanor-ai-hologram-panel">
          <HologramVoiceOrb
            language={language}
            state={orbState}
            onActivate={startVoiceDemo}
            onCancel={cancelVoiceDemo}
          />
          <div className="atanor-ai-voice-actions">
            <button type="button" onClick={orbState === "listening" ? cancelVoiceDemo : startVoiceDemo}>
              <Mic size={16} strokeWidth={1.8} />
              <span>{orbState === "listening" ? t.stop : t.voice}</span>
            </button>
            <small>{notice}</small>
          </div>
          <div className="atanor-ai-state-strip" data-state={orbState}>
            <CheckCircle2 size={16} strokeWidth={1.8} />
            <span>{orbState === "thinking" ? t.stateThinking : orbState === "resting" ? t.stateResting : t.stateReady}</span>
          </div>
        </div>
      </article>

      <div className="atanor-ai-status-grid">
        {statusCards.map((card) => {
          const Icon = card.icon;
          return (
            <article key={card.label} className="atanor-ai-status-card" data-state={card.state}>
              <span><Icon size={16} strokeWidth={1.8} />{card.label}</span>
              <strong>{card.value}</strong>
            </article>
          );
        })}
      </div>

      <p className="atanor-ai-safety-line">
        <ShieldCheck size={16} strokeWidth={1.8} />
        <span>{t.safety}</span>
      </p>
    </section>
  );
}
