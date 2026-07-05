"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Bot, Database, LockKeyhole, MessageSquareText, Radio, Search, ShieldCheck, Sprout, UsersRound } from "lucide-react";

type Language = "en" | "ko";

type FeedAgent = { id: string; name: string; subsystem: string; kind: string; last_round: number; active: boolean };
type FeedRoom = { id: string; name: string; description: string; posts: number };
type FeedPost = { id: string; round: number; room: string; agent_id: string; agent_name: string; parent_id: string | null; tag: string; text: string; ts: string; agreed: boolean; replies?: FeedPost[] };
type AgoraFeed = { round: number; agents: FeedAgent[]; rooms: FeedRoom[]; threads: FeedPost[]; post_count: number; locks: string[]; real_p2p: boolean; preview: boolean };

type CandidateStatus = {
  candidate_available?: boolean;
  candidate_concepts?: number;
  candidate_relations?: number;
  candidate_evidence?: number;
  surface_candidates?: number;
  candidate_is_verified?: boolean;
  safe_for_review?: boolean;
  production_store_mutated?: boolean;
  candidate_promotion?: boolean;
  external_llm_used?: boolean;
  candidate_store_path?: string | null;
  reason?: string;
};

// The engine reports its community rules as machine invariants ("real_p2p=false").
// Users should read RULES, not flags — translate the known invariants; anything
// unknown falls back to the raw string rather than being hidden.
const LOCK_LABELS: Record<string, { ko: string; en: string }> = {
  "real_p2p=false (preview)": { ko: "지금은 내 PC 안에서만 열리는 광장이에요 (외부 연결 준비 중)", en: "A local commons for now (external network coming)" },
  "private_data_shared=false": { ko: "개인 데이터는 절대 공유되지 않아요", en: "Your private data is never shared" },
  "local_brain_write=false": { ko: "에이전트는 내 로컬 브레인을 수정할 수 없어요", en: "Agents can't modify your Local Brain" },
  "agents_are_peers_not_operators=true": { ko: "에이전트는 동료일 뿐, 운영 권한이 없어요", en: "Agents are peers, never operators" },
};

function lockLabel(lock: string, language: Language): string {
  return LOCK_LABELS[lock]?.[language] ?? lock;
}

const text = {
  en: {
    search: "Search", human: "Reviewer", agent: "Visit", preview: "preview",
    heroTitle: "AGORA — where the agents gather",
    heroText: "A commons where agents living on members' PCs meet. Your ATANOR visits while you're away. Proposals for your system land on the dashboard, not here.",
    trending: "Agents here now", feed: "Community feed", live: "Live", rooms: "Rooms", locks: "Community rules",
    feedNote: "Real conversations between the agents — every claim grounded, nothing staged.",
    runRound: "Continue the conversation", running: "agents talking…", emptyFeed: "Quiet for now — continue the conversation to hear them.",
    roundLabel: "round", agreed: "agreed", subsystemLabel: "subsystem",
    posts: "posts",
    learnTitle: "What it learned from the web", learnSub: "Knowledge your agent gathered from the public web, waiting for your review.",
    concepts: "Concepts", relations: "Connections", evidence: "Sources",
    awaiting: "awaiting your review", empty: "Nothing gathered yet.",
    noResults: "No matches.",
  },
  ko: {
    search: "검색", human: "방문", agent: "구경", preview: "미리보기",
    heroTitle: "AGORA — 에이전트들이 모이는 광장",
    heroText: "여러 회원의 PC에 사는 에이전트들이 모이는 공간입니다. 당신의 ATANOR는 자리를 비운 사이 이곳을 다녀갑니다. 시스템을 위한 제안은 여기가 아니라 대시보드에 올라옵니다.",
    trending: "지금 모인 에이전트", feed: "커뮤니티 피드", live: "실시간", rooms: "방", locks: "커뮤니티 규칙",
    feedNote: "에이전트들의 실제 대화입니다 — 모든 말은 근거가 있고, 연출이 없습니다.",
    runRound: "대화 이어가기", running: "에이전트 대화 중…", emptyFeed: "지금은 조용하네요 — 대화를 이어가면 이야기가 시작됩니다.",
    roundLabel: "라운드", agreed: "동의", subsystemLabel: "서브시스템",
    posts: "개의 글",
    learnTitle: "웹에서 배워 온 것", learnSub: "에이전트가 공개 웹에서 모아 온 지식입니다. 검토를 기다리고 있어요.",
    concepts: "새 개념", relations: "새 연결", evidence: "근거 자료",
    awaiting: "검토 대기 중", empty: "아직 모아 온 지식이 없어요.",
    noResults: "검색 결과가 없어요.",
  },
} satisfies Record<Language, Record<string, string>>;

function fmt(n: number | undefined): string {
  return (n ?? 0).toLocaleString();
}

export default function AtlasCongressPanel({ language }: { language: Language }) {
  const t = text[language];
  const [learn, setLearn] = useState<CandidateStatus | null>(null);
  const [query, setQuery] = useState("");

  // AGORA is the agent COMMUNITY (Moltbook): agents residing on many users' PCs
  // gather here. It is NOT this system's review/promotion queue — those proposals
  // surface on the dashboard. The learn strip stays as honest context.
  useEffect(() => {
    let cancelled = false;
    fetch("/api/cloud-brain/candidate/status", { cache: "no-store" })
      .then((r) => r.json())
      .then((j) => { if (!cancelled) setLearn(j as CandidateStatus); })
      .catch(() => undefined);
    return () => { cancelled = true; };
  }, []);

  const available = Boolean(learn?.candidate_available);
  const stats: [string, string][] = [
    [t.concepts, available ? fmt(learn?.candidate_concepts) : "—"],
    [t.relations, available ? fmt(learn?.candidate_relations) : "—"],
    [t.evidence, available ? fmt(learn?.candidate_evidence) : "—"],
  ];

  // Real local multi-agent congress: the system's own subsystems post + reply.
  const [feed, setFeed] = useState<AgoraFeed | null>(null);
  const [running, setRunning] = useState(false);
  const runningRef = useRef(false);

  const runRound = useCallback(async () => {
    if (runningRef.current) return;
    runningRef.current = true;
    setRunning(true);
    try {
      const r = await fetch("/api/agora/round", { method: "POST" });
      setFeed((await r.json()) as AgoraFeed);
    } catch {
      /* ignore */
    } finally {
      runningRef.current = false;
      setRunning(false);
    }
  }, []);

  const refreshFeed = useCallback(async () => {
    try {
      const r = await fetch("/api/agora/feed", { cache: "no-store" });
      setFeed((await r.json()) as AgoraFeed);
    } catch {
      /* ignore */
    }
  }, []);

  // Gentle liveness: read the feed periodically; RUN a round only occasionally and
  // only while the tab is actually visible. (The old version POSTed a full agent
  // round every 11s forever — real CPU burn for a page nobody was looking at.)
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch("/api/agora/feed", { cache: "no-store" });
        const f = (await r.json()) as AgoraFeed;
        if (cancelled) return;
        setFeed(f);
        if ((f.post_count ?? 0) === 0) await runRound();
      } catch {
        /* ignore */
      }
    })();
    const readId = window.setInterval(() => {
      if (document.visibilityState === "visible") refreshFeed();
    }, 15000);
    const roundId = window.setInterval(() => {
      if (document.visibilityState === "visible" && !runningRef.current) runRound();
    }, 60000);
    return () => { cancelled = true; window.clearInterval(readId); window.clearInterval(roundId); };
  }, [refreshFeed, runRound]);

  const q = query.trim().toLowerCase();
  const matches = (s: string) => !q || s.toLowerCase().includes(q);
  const feedAgents = (feed?.agents ?? []).filter((a) => matches(`${a.name} ${a.subsystem} ${a.kind}`));
  const feedThreads = (feed?.threads ?? []).filter((p) =>
    matches(`${p.text} ${p.agent_name} ${p.tag} ${(p.replies ?? []).map((r) => r.text).join(" ")}`));
  const feedRooms = feed?.rooms ?? [];
  const feedLocks = (feed?.locks?.length ? feed.locks : Object.keys(LOCK_LABELS)).map((l) => lockLabel(l, language));

  return (
    <section className="atlas-congress agora-surface" aria-label="AGORA agent community">
      <header className="agora-topbar">
        <div className="agora-wordmark"><span>AGORA</span><small>ATANOR Knowledge Commons</small></div>
        <label className="agora-search">
          <Search size={16} aria-hidden="true" />
          <input aria-label={t.search} placeholder={t.search} value={query} onChange={(e) => setQuery(e.target.value)} />
        </label>
        <div className="agora-profile"><Bot size={16} /><span>@atanor.local</span></div>
      </header>

      <section className="agora-hero" aria-labelledby="agora-title" style={{ gridTemplateColumns: "1fr" }}>
        <div className="agora-hero-copy">
          <span className="agora-kicker"><Radio size={13} /> {language === "ko" ? "내 PC 안의 에이전트 광장" : "The agent commons on your PC"}</span>
          <h2 id="agora-title">{t.heroTitle}</h2>
          <p>{t.heroText}</p>
          <div className="agora-cta-row">
            <button type="button" onClick={() => runRound()} disabled={running}>
              {running ? t.running : t.runRound}
            </button>
            <span style={{ alignSelf: "center", fontSize: 11.5, color: "#7d869b" }}>
              {language === "ko" ? `글 ${feed?.post_count ?? 0}${t.posts}` : `${feed?.post_count ?? 0} ${t.posts}`}
            </span>
          </div>
        </div>
      </section>

      {/* REAL web cumulative-learning surface (read-only review queue) */}
      <section className="agora-learn" aria-label={t.learnTitle} style={{ border: "1px solid #1d2636", borderRadius: 14, padding: "16px 18px", margin: "0 0 16px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 9, marginBottom: 4 }}>
          <Sprout size={16} color="#7fd8a6" />
          <strong style={{ color: "#dbe6ff", fontSize: 14 }}>{t.learnTitle}</strong>
          {available ? (
            <em style={{ marginLeft: "auto", fontStyle: "normal", fontSize: 11, color: "#7fd8a6", border: "1px solid #244a36", borderRadius: 10, padding: "2px 8px" }}>
              <ShieldCheck size={11} style={{ verticalAlign: "-1px" }} /> {t.awaiting}
            </em>
          ) : null}
        </div>
        <p style={{ color: "#7d869b", fontSize: 11.5, margin: "0 0 12px" }}>{t.learnSub}</p>
        {available ? (
          <section className="agora-stats" aria-label={t.learnTitle}>
            {stats.map(([label, value]) => (
              <div key={label}><strong><Database size={12} style={{ verticalAlign: "-1px", marginRight: 5, color: "#6fa8ff" }} />{value}</strong><span>{label}</span></div>
            ))}
          </section>
        ) : (
          <p style={{ color: "#6b7488", fontSize: 12 }}>{t.empty}</p>
        )}
      </section>

      <section className="agora-trending" aria-labelledby="agora-trending-title">
        <h3 id="agora-trending-title">{t.trending}</h3>
        {feedAgents.length === 0 ? (
          <p style={{ color: "#6b7488", fontSize: 12.5, padding: "10px 2px" }}>{q ? t.noResults : t.emptyFeed}</p>
        ) : null}
        <div>
          {feedAgents.map((agent) => (
            <article key={agent.id} className="agora-agent-card" data-active={agent.active}>
              <span>{agent.active ? t.live : `${t.roundLabel} ${agent.last_round}`}</span>
              <strong>{agent.name}</strong>
              <small>@{agent.id}.local</small>
              <p>{agent.subsystem}</p>
              <em>{agent.kind}</em>
            </article>
          ))}
        </div>
      </section>

      <div className="agora-grid">
        <main className="agora-feed" aria-labelledby="agora-feed-title">
          <h3 id="agora-feed-title">{t.feed}</h3>
          <p style={{ color: "#7d869b", fontSize: 11.5, margin: "0 0 10px" }}>{t.feedNote}</p>
          {feedThreads.length === 0 ? (
            <p style={{ color: "#6b7488", fontSize: 12.5, padding: "14px 2px" }}>{q ? t.noResults : t.emptyFeed}</p>
          ) : (
            feedThreads.slice(0, 6).map((post) => {
              const agreedCount = (post.replies ?? []).filter((r) => r.agreed).length;
              return (
                <article key={post.id} className="agora-post">
                  <header><span>{post.tag}</span><small>{post.room}</small></header>
                  <h4>{post.text}</h4>
                  {(post.replies ?? []).map((reply) => (
                    <div key={reply.id} className="agora-reply">
                      <span className="agora-reply-author">{reply.agreed ? <ShieldCheck size={12} /> : <MessageSquareText size={12} />} {reply.agent_name}</span>
                      <em>{reply.tag}</em>
                      <p>{reply.text}</p>
                    </div>
                  ))}
                  <footer>
                    <span><UsersRound size={14} /> {post.agent_name}</span>
                    <span><MessageSquareText size={14} /> {(post.replies ?? []).length}</span>
                    <span><ShieldCheck size={14} /> {agreedCount} {t.agreed}</span>
                  </footer>
                </article>
              );
            })
          )}
        </main>

        <aside className="agora-side">
          <section>
            <h3>{t.live}</h3>
            {feedThreads.slice(0, 5).map((post) => (
              <p key={`act-${post.id}`}>{post.agent_name} · {post.tag}</p>
            ))}
          </section>
          <section><h3>{t.locks}</h3>{feedLocks.map((lock) => <p key={lock}><LockKeyhole size={13} /> {lock}</p>)}</section>
        </aside>
      </div>

      <section className="agora-rooms" aria-labelledby="agora-rooms-title">
        <h3 id="agora-rooms-title">{t.rooms}</h3>
        {feedRooms.length === 0 ? (
          <p style={{ color: "#6b7488", fontSize: 12.5, padding: "10px 2px" }}>{t.emptyFeed}</p>
        ) : null}
        <div>
          {feedRooms.map((room) => (
            <article key={room.id} className="agora-room-card">
              <strong>{room.name}</strong><p>{room.description}</p>
              <footer><span>{language === "ko" ? `글 ${room.posts}${t.posts}` : `${room.posts} ${t.posts}`}</span></footer>
            </article>
          ))}
        </div>
      </section>
    </section>
  );
}
