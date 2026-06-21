"use client";

import type { CSSProperties } from "react";

type Language = "en" | "ko";

type CongressRoom = {
  id: string;
  title: string;
  topic: string;
  status: "local_preview" | "future_p2p" | "archived";
  participantCount: number;
  tags: string[];
};

type CongressThread = {
  id: string;
  roomId: string;
  claim: string;
  evidenceCount: number;
  objectionCount: number;
  synthesis: string;
  cartridgeProposalId: string;
  status: "open" | "synthesizing" | "proposal_ready" | "blocked";
};

type CongressPeer = {
  id: string;
  label: string;
  peerType: "local_user" | "local_ai" | "atlas_peer" | "broker" | "reviewer" | "privacy_guard";
  trustScore: number;
  privacyMode: string;
  connectionStatus: "mock_local" | "future_p2p" | "offline";
};

type CartridgeProposal = {
  id: string;
  title: string;
  domain: string;
  trustScore: number;
  privacyGrade: string;
  licenseHint: string;
  status: "draft" | "review" | "blocked" | "candidate";
  writesLocalBrain: false;
  writesCloudBrain: false;
  requiresPromotionGate: true;
};

const rooms: CongressRoom[] = [
  { id: "core", title: "ATANOR Core Design", topic: "Auxiliary innovation axes and safety gates", status: "local_preview", participantCount: 6, tags: ["architecture", "safety"] },
  { id: "cgsr", title: "English CGSR Quality", topic: "Surface realization quality and held-out validation", status: "local_preview", participantCount: 4, tags: ["CGSR", "evaluation"] },
  { id: "promotion", title: "Candidate Promotion Gate", topic: "When candidate knowledge can become durable", status: "local_preview", participantCount: 5, tags: ["promotion", "review"] },
  { id: "cartridge", title: "Graph Cartridge Review", topic: "Read-only cartridge compatibility and provenance", status: "future_p2p", participantCount: 3, tags: ["Graph Hub", "cartridge"] },
  { id: "privacy", title: "Privacy & Tabularis", topic: "Private structured data boundaries", status: "local_preview", participantCount: 4, tags: ["Tabularis", "privacy"] },
];

const threads: CongressThread[] = [
  { id: "t1", roomId: "core", claim: "Autonomy proposals must remain review-only until promotion gates mature.", evidenceCount: 5, objectionCount: 1, synthesis: "Keep proof packages isolated from candidate learning and production stores.", cartridgeProposalId: "cart-autonomy-safety", status: "synthesizing" },
  { id: "t2", roomId: "promotion", claim: "Candidate learning output should not enter Cloud Brain without verified provenance.", evidenceCount: 7, objectionCount: 2, synthesis: "Require source, license, dedupe, false-confident=0, and human promotion review.", cartridgeProposalId: "cart-promotion-gate", status: "proposal_ready" },
  { id: "t3", roomId: "privacy", claim: "Private structured data must pass Tabularis before any future peer routing.", evidenceCount: 4, objectionCount: 0, synthesis: "Use redaction, generalization, synthetic aggregate output, and explicit limitations.", cartridgeProposalId: "cart-tabularis-boundary", status: "open" },
  { id: "t4", roomId: "cartridge", claim: "Graph cartridges should attach temporarily before any durable memory write.", evidenceCount: 3, objectionCount: 1, synthesis: "Atlas Router selects a safe public path; Local Brain write stays false.", cartridgeProposalId: "cart-graphhub-sandbox", status: "blocked" },
];

const peers: CongressPeer[] = [
  { id: "u", label: "Local Human Steward", peerType: "local_user", trustScore: 1.0, privacyMode: "local only", connectionStatus: "mock_local" },
  { id: "ai", label: "ATANOR Local AI", peerType: "local_ai", trustScore: 0.92, privacyMode: "no private export", connectionStatus: "mock_local" },
  { id: "peer", label: "Future Atlas Peer", peerType: "atlas_peer", trustScore: 0.74, privacyMode: "public metadata only", connectionStatus: "future_p2p" },
  { id: "broker", label: "Future Broker", peerType: "broker", trustScore: 0.68, privacyMode: "route metadata only", connectionStatus: "future_p2p" },
  { id: "reviewer", label: "Promotion Reviewer", peerType: "reviewer", trustScore: 0.88, privacyMode: "review queue only", connectionStatus: "mock_local" },
  { id: "guard", label: "Tabularis Privacy Guard", peerType: "privacy_guard", trustScore: 0.96, privacyMode: "redact before route", connectionStatus: "mock_local" },
];

const proposals: CartridgeProposal[] = [
  { id: "cart-autonomy-safety", title: "Autonomy Safety Claims", domain: "Architecture", trustScore: 0.91, privacyGrade: "public metadata", licenseHint: "internal review", status: "draft", writesLocalBrain: false, writesCloudBrain: false, requiresPromotionGate: true },
  { id: "cart-promotion-gate", title: "Promotion Gate Criteria", domain: "Cloud Candidate Review", trustScore: 0.88, privacyGrade: "public only", licenseHint: "review required", status: "review", writesLocalBrain: false, writesCloudBrain: false, requiresPromotionGate: true },
  { id: "cart-tabularis-boundary", title: "Tabularis Boundary Notes", domain: "Privacy", trustScore: 0.94, privacyGrade: "synthetic only", licenseHint: "proof-only", status: "candidate", writesLocalBrain: false, writesCloudBrain: false, requiresPromotionGate: true },
  { id: "cart-graphhub-sandbox", title: "Graph Hub Sandbox Protocol", domain: "Graph Cartridge", trustScore: 0.79, privacyGrade: "public metadata", licenseHint: "compatibility pending", status: "blocked", writesLocalBrain: false, writesCloudBrain: false, requiresPromotionGate: true },
];

const text = {
  en: {
    subtitle: "Structured P2P knowledge deliberation layer - local preview only.",
    intro: "Atlas Congress is where humans and local AI nodes will discuss public knowledge claims, evidence, objections, and cartridge proposals. In this preview, nothing is sent to peers, Cloud Brain, or Local Brain.",
    rooms: "Congress Rooms",
    threads: "Knowledge Threads",
    peers: "Peer Presence",
    cartridges: "Cartridge Proposals",
    promotion: "Promotion Queue Preview",
    localPreview: "Local preview only",
    participant: "participants",
  },
  ko: {
    subtitle: "구조화된 P2P 지식 숙의 레이어 - 로컬 프리뷰 전용.",
    intro: "Atlas Congress는 인간과 로컬 AI 노드가 공용 지식 주장, 근거, 반론, 카트리지 제안을 토론할 미래 공간입니다. 이 프리뷰에서는 어떤 내용도 피어, Cloud Brain, Local Brain으로 전송하지 않습니다.",
    rooms: "Congress Rooms",
    threads: "Knowledge Threads",
    peers: "Peer Presence",
    cartridges: "Cartridge Proposals",
    promotion: "Promotion Queue Preview",
    localPreview: "로컬 프리뷰",
    participant: "참여자",
  },
} satisfies Record<Language, Record<string, string>>;

const shell: Record<string, CSSProperties> = {
  page: { display: "grid", gridTemplateColumns: "minmax(0, 1.25fr) minmax(320px, 0.75fr)", gap: 16, width: "100%" },
  hero: { gridColumn: "1 / -1", border: "1px solid rgba(148, 163, 184, .28)", borderRadius: 8, padding: 20, background: "rgba(8, 13, 24, .86)" },
  badgeRow: { display: "flex", flexWrap: "wrap", gap: 8, marginTop: 14 },
  badge: { border: "1px solid rgba(125, 211, 252, .34)", borderRadius: 999, padding: "6px 10px", fontSize: 12, color: "#dbeafe", background: "rgba(14, 165, 233, .08)" },
  panel: { border: "1px solid rgba(148, 163, 184, .24)", borderRadius: 8, padding: 16, background: "rgba(10, 15, 28, .78)", minWidth: 0 },
  grid: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 },
  card: { border: "1px solid rgba(71, 85, 105, .55)", borderRadius: 8, padding: 12, background: "rgba(15, 23, 42, .72)" },
  muted: { color: "#94a3b8", fontSize: 12 },
  row: { display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center", marginTop: 8 },
};

export default function AtlasCongressPanel({ language }: { language: Language }) {
  const copy = text[language];
  return (
    <section style={shell.page} aria-label="Atlas Congress local preview">
      <header style={shell.hero}>
        <span style={shell.muted}>P2P Knowledge Commons</span>
        <h2 style={{ margin: "6px 0 4px", fontSize: 34 }}>Atlas Congress</h2>
        <p style={{ maxWidth: 920, color: "#cbd5e1", lineHeight: 1.55 }}>{copy.subtitle}</p>
        <p style={{ maxWidth: 980, color: "#e2e8f0", lineHeight: 1.6 }}>{copy.intro}</p>
        <div style={shell.badgeRow} aria-label="Atlas Congress safety badges">
          {["P2P: not connected", "Local Brain write: false", "Cloud Brain write: false", "Promotion required", "Tabularis required before private data leaves local", "Atlas Router required before future peer routing"].map((badge) => (
            <span key={badge} style={shell.badge}>{badge}</span>
          ))}
        </div>
      </header>

      <article style={shell.panel}>
        <h3>{copy.rooms}</h3>
        <div style={shell.grid}>
          {rooms.map((room) => (
            <section key={room.id} style={shell.card}>
              <span style={shell.muted}>{room.status === "local_preview" ? copy.localPreview : "future P2P"}</span>
              <h4>{room.title}</h4>
              <p style={shell.muted}>{room.topic}</p>
              <div style={shell.row}><span>{room.participantCount} {copy.participant}</span><strong>{room.tags.join(" / ")}</strong></div>
            </section>
          ))}
        </div>
      </article>

      <aside style={shell.panel}>
        <h3>{copy.peers}</h3>
        {peers.map((peer) => (
          <p key={peer.id} style={shell.row}>
            <span>{peer.label}<br /><small style={shell.muted}>{peer.peerType} · {peer.connectionStatus}</small></span>
            <strong>{Math.round(peer.trustScore * 100)}%</strong>
          </p>
        ))}
      </aside>

      <article style={shell.panel}>
        <h3>{copy.threads}</h3>
        <div style={shell.grid}>
          {threads.map((thread) => (
            <section key={thread.id} style={shell.card}>
              <span style={shell.muted}>{thread.status}</span>
              <h4>{thread.claim}</h4>
              <p style={shell.muted}>Evidence {thread.evidenceCount} · Objections {thread.objectionCount}</p>
              <p>{thread.synthesis}</p>
              <small style={shell.muted}>Proposed cartridge: {thread.cartridgeProposalId}</small>
            </section>
          ))}
        </div>
      </article>

      <aside style={shell.panel}>
        <h3>{copy.cartridges}</h3>
        {proposals.map((proposal) => (
          <section key={proposal.id} style={shell.card}>
            <span style={shell.muted}>{proposal.domain} · {proposal.status}</span>
            <h4>{proposal.title}</h4>
            <p style={shell.muted}>Trust {Math.round(proposal.trustScore * 100)}% · {proposal.privacyGrade} · {proposal.licenseHint}</p>
            <p style={shell.muted}>Local Brain write {String(proposal.writesLocalBrain)} · Cloud Brain write {String(proposal.writesCloudBrain)}</p>
          </section>
        ))}
      </aside>

      <article style={{ ...shell.panel, gridColumn: "1 / -1" }}>
        <h3>{copy.promotion}</h3>
        <div style={shell.grid}>
          {[
            ["Not promoted", "All Congress output remains draft or review-only."],
            ["Not written to Local Brain", "No local memory mutation occurs from this preview."],
            ["Not written to Cloud Brain", "No candidate ingestion or Cloud write is triggered."],
            ["Requires review", "Future outputs must pass Tabularis, Atlas Router, and Promotion Gate."],
          ].map(([title, summary]) => (
            <section key={title} style={shell.card}>
              <h4>{title}</h4>
              <p style={shell.muted}>{summary}</p>
            </section>
          ))}
        </div>
      </article>
    </section>
  );
}
