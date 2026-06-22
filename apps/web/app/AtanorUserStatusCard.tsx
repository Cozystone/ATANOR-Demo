"use client";

import type { CSSProperties } from "react";

type Language = "en" | "ko";

const copy = {
  en: {
    title: "ATANOR Status",
    stateLabel: "Status",
    state: "Ready",
    suggestionLabel: "Current suggestion",
    suggestion: "Review prepared proposals before anything changes.",
    approvalsLabel: "Pending approvals",
    approvals: "Memory and promotion reviews appear here when they need you.",
    briefLabel: "Next brief",
    brief: "Morning, evening, and status briefs are prepared without changing memory.",
    safety: "No memory or knowledge is changed without your approval.",
  },
  ko: {
    title: "ATANOR Status",
    stateLabel: "상태",
    state: "준비됨",
    suggestionLabel: "현재 제안",
    suggestion: "변경 전에 준비된 제안을 먼저 검토합니다.",
    approvalsLabel: "승인 대기",
    approvals: "메모리와 승격 검토가 필요하면 여기에 표시됩니다.",
    briefLabel: "다음 브리프",
    brief: "아침, 저녁, 상태 브리프는 메모리를 변경하지 않고 준비됩니다.",
    safety: "승인 없이는 기억이나 지식이 변경되지 않습니다.",
  },
} satisfies Record<Language, Record<string, string>>;

const styles: Record<string, CSSProperties> = {
  card: {
    border: "1px solid rgba(125, 211, 252, .22)",
    borderRadius: 8,
    padding: 18,
    marginBottom: 16,
    background: "rgba(10, 15, 28, .78)",
  },
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
    gap: 10,
    marginTop: 12,
  },
  item: {
    border: "1px solid rgba(71, 85, 105, .48)",
    borderRadius: 8,
    padding: 12,
    background: "rgba(15, 23, 42, .68)",
  },
  label: {
    color: "#94a3b8",
    display: "block",
    fontSize: 12,
    marginBottom: 6,
  },
  value: {
    color: "#e5e7eb",
    display: "block",
    lineHeight: 1.45,
  },
  safety: {
    color: "#86efac",
    margin: "12px 0 0",
  },
};

export default function AtanorUserStatusCard({ language }: { language: Language }) {
  const t = copy[language];
  return (
    <section style={styles.card} aria-label="ATANOR user status">
      <h2 style={{ margin: 0 }}>{t.title}</h2>
      <div style={styles.grid}>
        <p style={styles.item}>
          <span style={styles.label}>{t.stateLabel}</span>
          <strong style={styles.value}>{t.state}</strong>
        </p>
        <p style={styles.item}>
          <span style={styles.label}>{t.suggestionLabel}</span>
          <strong style={styles.value}>{t.suggestion}</strong>
        </p>
        <p style={styles.item}>
          <span style={styles.label}>{t.approvalsLabel}</span>
          <strong style={styles.value}>{t.approvals}</strong>
        </p>
        <p style={styles.item}>
          <span style={styles.label}>{t.briefLabel}</span>
          <strong style={styles.value}>{t.brief}</strong>
        </p>
      </div>
      <p style={styles.safety}>{t.safety}</p>
    </section>
  );
}
