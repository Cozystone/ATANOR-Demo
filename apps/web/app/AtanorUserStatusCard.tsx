"use client";

import { Brain, CheckCircle2, MessageCircle, ShieldCheck, Sparkles } from "lucide-react";

type Language = "en" | "ko";

const copy = {
  en: {
    eyebrow: "ATANOR Status",
    title: "Talk with an AI that knows what it is allowed to remember.",
    body: "A calm conversation surface backed by memory approvals, proposal review, and proof-only self-model signals.",
    inputLabel: "Conversation preview",
    input: "Ask ATANOR what it is thinking about, what it remembers, and what needs your approval.",
    send: "Open conversation",
    stateLabel: "System state",
    state: "Ready",
    suggestionLabel: "Current suggestion",
    suggestion: "Review prepared proposals before anything changes.",
    approvalsLabel: "Pending approvals",
    approvals: "Memory and promotion reviews appear here when they need you.",
    briefLabel: "Next brief",
    brief: "Morning, evening, and status briefs are prepared without changing memory.",
    safety: "No memory, production knowledge, or Local Brain state changes without explicit approval.",
    chips: ["What changed overnight?", "What should I approve?", "Explain your current self-model"],
  },
  ko: {
    eyebrow: "ATANOR 상태",
    title: "무엇을 기억해도 되는지 아는 AI와 대화합니다.",
    body: "ATANOR의 첫 화면은 대화, 메모리 승인, 제안 검토, proof-only 자기 모델 신호를 차분하게 보여주는 공간입니다.",
    inputLabel: "대화 미리보기",
    input: "ATANOR에게 지금 무엇을 생각하는지, 무엇을 기억하는지, 어떤 승인이 필요한지 물어보세요.",
    send: "대화 열기",
    stateLabel: "시스템 상태",
    state: "준비됨",
    suggestionLabel: "현재 제안",
    suggestion: "무언가 바뀌기 전에 준비된 제안을 먼저 검토합니다.",
    approvalsLabel: "승인 대기",
    approvals: "메모리와 승격 검토가 필요하면 이곳에 표시됩니다.",
    briefLabel: "다음 브리프",
    brief: "아침, 저녁, 상태 브리프는 메모리를 바꾸지 않고 준비됩니다.",
    safety: "명시적 승인 없이는 메모리, production 지식, Local Brain 상태가 바뀌지 않습니다.",
    chips: ["밤사이 무엇이 바뀌었어?", "내가 승인해야 할 것은?", "지금 자기 모델을 설명해줘"],
  },
} satisfies Record<Language, {
  eyebrow: string;
  title: string;
  body: string;
  inputLabel: string;
  input: string;
  send: string;
  stateLabel: string;
  state: string;
  suggestionLabel: string;
  suggestion: string;
  approvalsLabel: string;
  approvals: string;
  briefLabel: string;
  brief: string;
  safety: string;
  chips: string[];
}>;

export default function AtanorUserStatusCard({ language }: { language: Language }) {
  const t = copy[language];
  const statusCards = [
    { label: t.stateLabel, value: t.state, icon: CheckCircle2 },
    { label: t.suggestionLabel, value: t.suggestion, icon: Sparkles },
    { label: t.approvalsLabel, value: t.approvals, icon: ShieldCheck },
    { label: t.briefLabel, value: t.brief, icon: Brain },
  ];

  return (
    <section className="atanor-ai-dashboard" aria-label={t.eyebrow}>
      <article className="atanor-ai-hero">
        <div className="atanor-ai-hero-copy">
          <span>{t.eyebrow}</span>
          <h1>{t.title}</h1>
          <p>{t.body}</p>
        </div>
        <div className="atanor-ai-dialogue" aria-label={t.inputLabel}>
          <div className="atanor-ai-dialogue-header">
            <MessageCircle size={18} strokeWidth={1.9} />
            <strong>{t.inputLabel}</strong>
          </div>
          <div className="atanor-ai-message" data-role="atanor">
            <span>ATANOR</span>
            <p>{t.input}</p>
          </div>
          <div className="atanor-ai-chip-row">
            {t.chips.map((chip) => (
              <button key={chip} type="button">{chip}</button>
            ))}
          </div>
          <button className="atanor-ai-primary-action" type="button">{t.send}</button>
        </div>
      </article>

      <div className="atanor-ai-status-grid">
        {statusCards.map((card) => {
          const Icon = card.icon;
          return (
            <article key={card.label} className="atanor-ai-status-card">
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
