"use client";

import type { CSSProperties } from "react";

type Language = "en" | "ko";

const observations = [
  ["Git worktree", "dirty", "Recommend review, do not clean automatically."],
  ["Candidate backlog", "attention", "Prepare promotion review packet only."],
  ["Memory review", "attention", "Prepare approval packet only."],
  ["Voice readiness", "optional", "Voice can be offered; text remains primary."],
];

const needs = [
  ["repo_hygiene_needed", "0.85", "Review dirty worktree before new long runs."],
  ["promotion_review_needed", "0.78", "Prepare human review queue."],
  ["memory_review_needed", "0.76", "Prepare memory approval queue."],
];

const actions = [
  ["recommend_repo_hygiene", "waiting_user", "No cleanup performed."],
  ["prepare_promotion_review", "waiting_user", "No candidate promotion."],
  ["prepare_memory_review", "waiting_user", "No Local Brain write."],
];

const gates = [
  ["real_local_brain_write", false],
  ["production_store_mutated", false],
  ["candidate_promotion", false],
  ["real_p2p_used", false],
  ["generated_code_executed", false],
  ["always_listening_enabled", false],
  ["raw_voice_saved", false],
  ["requires_user_approval", true],
];

const copy = {
  en: {
    eyebrow: "Proof-only autonomous lifecycle",
    title: "Live Selfhood Life Cycle",
    intro:
      "ATANOR can observe, detect needs, rank impulses, propose actions, deliberate locally, brief the user, and wait for approval.",
    level: "Autonomy Level",
    tick: "Current Tick",
    observations: "Observations",
    needs: "Needs / Impulses",
    actions: "Proposed Actions",
    brief: "Morning Brief",
    safety: "Safety Gates",
    approvals: "Pending User Approvals",
  },
  ko: {
    eyebrow: "proof-only autonomous lifecycle",
    title: "Live Selfhood Life Cycle",
    intro:
      "ATANOR가 상태를 관찰하고, 필요를 감지하고, impulse를 정렬하고, 제안을 만들고, 로컬 숙고 후 brief를 생성하며 승인을 기다리는 proof-only 패널입니다.",
    level: "Autonomy Level",
    tick: "Current Tick",
    observations: "Observations",
    needs: "Needs / Impulses",
    actions: "Proposed Actions",
    brief: "Morning Brief",
    safety: "Safety Gates",
    approvals: "Pending User Approvals",
  },
} satisfies Record<Language, Record<string, string>>;

const styles: Record<string, CSSProperties> = {
  page: { display: "grid", gridTemplateColumns: "minmax(0, 1.25fr) minmax(320px, .75fr)", gap: 16, width: "100%" },
  hero: { gridColumn: "1 / -1", border: "1px solid rgba(148, 163, 184, .26)", borderRadius: 8, padding: 20, background: "rgba(8, 13, 24, .88)" },
  panel: { border: "1px solid rgba(148, 163, 184, .22)", borderRadius: 8, padding: 16, background: "rgba(10, 15, 28, .78)", minWidth: 0 },
  grid: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))", gap: 12 },
  card: { border: "1px solid rgba(71, 85, 105, .58)", borderRadius: 8, padding: 12, background: "rgba(15, 23, 42, .74)" },
  badgeRow: { display: "flex", flexWrap: "wrap", gap: 8, marginTop: 14 },
  badge: { border: "1px solid rgba(125, 211, 252, .34)", borderRadius: 999, padding: "6px 10px", fontSize: 12, color: "#dbeafe", background: "rgba(14, 165, 233, .08)" },
  muted: { color: "#94a3b8", fontSize: 12 },
  safe: { color: "#86efac" },
  blocked: { color: "#fca5a5" },
  row: { display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center", marginTop: 8 },
};

function boolText(value: boolean) {
  return String(value).toLowerCase();
}

export default function LiveSelfhoodCyclePanel({ language }: { language: Language }) {
  const t = copy[language];
  return (
    <section style={styles.page} aria-label="Live Selfhood Life Cycle proof-only panel">
      <header style={styles.hero}>
        <span style={styles.muted}>{t.eyebrow}</span>
        <h2 style={{ margin: "6px 0 4px", fontSize: 34 }}>{t.title}</h2>
        <p style={{ maxWidth: 980, color: "#dbeafe", lineHeight: 1.58 }}>{t.intro}</p>
        <div style={styles.badgeRow}>
          {["LEVEL_3_SANDBOX_PLANNER", "self-initiated observation", "proposal only", "approval required", "not AGI/consciousness"].map((badge) => (
            <span key={badge} style={styles.badge}>{badge}</span>
          ))}
        </div>
      </header>

      <article style={styles.panel}>
        <h3>{t.level}</h3>
        <div style={styles.grid}>
          {[
            ["current", "LEVEL_3_SANDBOX_PLANNER"],
            ["can_prepare_operator_gate", "false"],
            ["can_apply", "false"],
            ["text_input_supported", "true"],
            ["voice_optional", "true"],
          ].map(([label, value]) => (
            <section key={label} style={styles.card}>
              <span style={styles.muted}>{label}</span>
              <strong style={{ display: "block", marginTop: 6 }}>{value}</strong>
            </section>
          ))}
        </div>
      </article>

      <aside style={styles.panel}>
        <h3>{t.tick}</h3>
        <p style={styles.row}><span>tick_type</span><strong>morning</strong></p>
        <p style={styles.row}><span>reason</span><strong>local lifecycle proof</strong></p>
        <p style={styles.row}><span>background_daemon</span><strong>false</strong></p>
      </aside>

      <article style={styles.panel}>
        <h3>{t.observations}</h3>
        <div style={styles.grid}>
          {observations.map(([name, status, detail]) => (
            <section key={name} style={styles.card}>
              <span style={styles.muted}>{status}</span>
              <h4>{name}</h4>
              <p>{detail}</p>
            </section>
          ))}
        </div>
      </article>

      <aside style={styles.panel}>
        <h3>{t.needs}</h3>
        {needs.map(([need, score, reason]) => (
          <p key={need} style={styles.row}>
            <span>{need}</span>
            <strong>{score}</strong>
            <span style={styles.muted}>{reason}</span>
          </p>
        ))}
      </aside>

      <article style={styles.panel}>
        <h3>{t.actions}</h3>
        <div style={styles.grid}>
          {actions.map(([action, status, detail]) => (
            <section key={action} style={styles.card}>
              <span style={styles.muted}>{status}</span>
              <h4>{action}</h4>
              <p>{detail}</p>
            </section>
          ))}
        </div>
      </article>

      <aside style={styles.panel}>
        <h3>{t.brief}</h3>
        <p><strong>What I noticed</strong><br />Dirty worktree, review backlogs, and optional voice readiness can be watched safely.</p>
        <p><strong>What I propose</strong><br />Prepare review packets and ask for approval before any irreversible action.</p>
        <p><strong>What I blocked</strong><br />Local Brain write, production mutation, candidate promotion, real P2P, generated code execution, always-on mic.</p>
      </aside>

      <article style={styles.panel}>
        <h3>{t.safety}</h3>
        <div style={styles.grid}>
          {gates.map(([label, value]) => (
            <section key={String(label)} style={styles.card}>
              <span style={styles.muted}>{label}</span>
              <strong style={value ? styles.safe : styles.blocked}>{boolText(Boolean(value))}</strong>
            </section>
          ))}
        </div>
      </article>

      <aside style={styles.panel}>
        <h3>{t.approvals}</h3>
        <p>Repository hygiene review</p>
        <p>Promotion review packet</p>
        <p>Memory approval packet</p>
      </aside>
    </section>
  );
}
