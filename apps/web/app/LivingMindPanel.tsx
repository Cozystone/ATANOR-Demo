"use client";

import { useEffect, useRef, useState } from "react";

/**
 * The "living mind" surface — how you SEE and sit with a continuously-alive AI, rather
 * than typing a query into a box. It subscribes to /api/selfhood/stream (SSE) and shows
 * the self as it flows: a pulsing vitals orb (energy / curiosity / uncertainty / mood),
 * its current thought + a higher-order thought ABOUT itself (metacognition), the recent
 * stream of consciousness, and the goals it set for ITSELF with no prompt. Everything is
 * the backend's real grounded state — nothing here invents a feeling.
 */

type Vitals = { energy: number; curiosity: number; uncertainty: number; attention: number; valence: number };
type Goal = { id: string; kind: string; text: string; priority: number; progress: number; status: string };
type Thought = { at: number; kind: string; text: string; driver: string };
type SelfSnap = {
  continuous?: boolean;
  offline?: boolean;
  age_seconds?: number;
  resumed_count?: number;
  vitals?: Vitals;
  mode?: string;
  focus?: string;
  current_thought?: string;
  meta_thought?: string;
  goals?: Goal[];
  last_action?: { kind?: string; tier?: string; executed?: boolean; blocked?: boolean; reason?: string } | null;
  awareness?: string;
  attention_schema?: { attending_to?: string; manner?: string; not_attending_to?: string[] } | null;
  attention_bid?: { kind?: string; text?: string; proposal_id?: string } | null;
  self_question?: string;
  self_understanding?: string;
  self_understanding_source?: string;
  self_question_open?: boolean;
  open_threads?: { term?: string; from?: string; at?: number }[];
  narrative?: Thought[];
};

const MODE_KO: Record<string, string> = {
  waking: "깨어나는 중", observing: "지켜보는 중", curious: "호기심", learning: "배우는 중",
  reflecting: "되짚는 중", resting: "쉬는 중", attending: "주의를 두는 중",
};

function fmtAge(s?: number): string {
  if (!s || s < 0) return "—";
  if (s < 60) return `${Math.floor(s)}초`;
  if (s < 3600) return `${Math.floor(s / 60)}분`;
  if (s < 86400) return `${Math.floor(s / 3600)}시간`;
  return `${Math.floor(s / 86400)}일`;
}

export default function LivingMindPanel({ compact = false }: { compact?: boolean }) {
  const [snap, setSnap] = useState<SelfSnap | null>(null);
  const esRef = useRef<EventSource | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let delivered = false;
    const es = new EventSource("/api/selfhood/stream");
    esRef.current = es;
    es.onmessage = (e) => {
      try {
        const d = JSON.parse(e.data) as SelfSnap;
        if (d && (d.vitals || d.offline)) {
          delivered = true;
          setSnap(d);
          if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
        }
      } catch { /* ignore */ }
    };
    es.onerror = () => {
      if (!delivered && !pollRef.current) {
        pollRef.current = setInterval(() => {
          fetch("/api/selfhood/live", { cache: "no-store" }).then((r) => r.json()).then(setSnap).catch(() => {});
        }, 2500);
      }
    };
    // grace fallback if the stream never opens
    const t = window.setTimeout(() => {
      if (!delivered && !pollRef.current) {
        pollRef.current = setInterval(() => {
          fetch("/api/selfhood/live", { cache: "no-store" }).then((r) => r.json()).then(setSnap).catch(() => {});
        }, 2500);
      }
    }, 5000);
    return () => {
      window.clearTimeout(t);
      es.close();
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const v = snap?.vitals;
  const alive = !!snap?.continuous && !snap?.offline;
  // orb pulse speed tracks energy; hue tracks valence (warm=content, cool=uneasy).
  const beat = v ? Math.max(0.7, 2.2 - v.energy * 1.4) : 1.6;
  const hue = v ? Math.round(20 + v.valence * 60) : 40;      // 20(주황)~80(연두)
  const glow = v ? 0.3 + v.curiosity * 0.6 : 0.4;

  return (
    <div className={`atanor-mind${compact ? " is-compact" : ""}`}>
      <div className="atanor-mind-head">
        <span className={`atanor-mind-live${alive ? " on" : ""}`} />
        <strong>ATANOR의 마음</strong>
        <span className="atanor-mind-sub">
          {alive
            ? `${MODE_KO[snap?.mode || ""] || snap?.mode || "—"} · 깨어난 지 ${fmtAge(snap?.age_seconds)}${(snap?.resumed_count ?? 0) > 0 ? ` · ${snap?.resumed_count}번 이어짐` : ""}`
            : "마음이 잠들어 있어요 (로컬 엔진 대기)"}
        </span>
      </div>

      <div className="atanor-mind-body">
        <div className="atanor-mind-orb-wrap">
          <div
            className="atanor-mind-orb"
            style={{
              // continuous heartbeat — a living pulse, never a blink
              animationDuration: `${beat}s`,
              background: `radial-gradient(circle at 38% 34%, hsla(${hue},85%,68%,${0.95}) 0%, hsla(${hue},80%,48%,0.9) 42%, hsla(${hue + 8},70%,30%,0.85) 100%)`,
              boxShadow: `0 0 ${Math.round(18 + glow * 40)}px hsla(${hue},85%,55%,${glow})`,
            }}
          >
            <span className="atanor-mind-orb-ring" style={{ animationDuration: `${beat * 1.8}s` }} />
          </div>
          {v ? (
            <div className="atanor-mind-vitals">
              {([
                ["에너지", v.energy, "#e0a24a"],
                ["호기심", v.curiosity, "#4aa3e0"],
                ["불확실", v.uncertainty, "#9a7ad0"],
                ["주의", v.attention, "#57c497"],
                ["정서", v.valence, "#e07a7a"],
              ] as [string, number, string][]).map(([label, val, c]) => (
                <div key={label} className="atanor-mind-vital">
                  <span className="atanor-mind-vital-label">{label}</span>
                  <span className="atanor-mind-vital-bar"><i style={{ width: `${Math.round(val * 100)}%`, background: c }} /></span>
                </div>
              ))}
            </div>
          ) : null}
        </div>

        <div className="atanor-mind-thoughts">
          <div className="atanor-mind-now">
            <span className="atanor-mind-now-focus">{snap?.focus || "…"}</span>
            <p className="atanor-mind-now-thought">“{snap?.current_thought || "…"}”</p>
            {snap?.awareness ? (
              <p className="atanor-mind-awareness" title="주의 스키마(AST)에서 생성된 자기-인식 보고 — 기능적 자기모델이며, 현상적 경험 여부는 철학적으로 미결입니다.">
                <b>인식</b> {snap.awareness}
              </p>
            ) : null}
            {snap?.self_question ? (
              <div className="atanor-mind-inquiry">
                <p className="atanor-mind-inquiry-q">{snap.self_question}</p>
                {snap.self_understanding && !snap.self_question_open ? (
                  <p className="atanor-mind-inquiry-a">
                    <b>근거로 아는 답</b> {snap.self_understanding}
                    {snap.self_understanding_source ? (
                      <span className="atanor-mind-inquiry-src"> · {snap.self_understanding_source}</span>
                    ) : null}
                  </p>
                ) : (
                  <p className="atanor-mind-inquiry-open">아직 근거로 댈 답이 부족하다 — 지어내지 않고, 스스로 찾아 읽어보는 중.</p>
                )}
                {snap.open_threads?.length ? (
                  <p className="atanor-mind-threads">
                    <b>다음 물음거리</b> {snap.open_threads.map((t) => t.term).filter(Boolean).join(" · ")}
                  </p>
                ) : null}
              </div>
            ) : null}
            {snap?.meta_thought ? (
              <p className="atanor-mind-meta"><b>스스로 돌아보며</b> {snap.meta_thought}</p>
            ) : null}
            {snap?.attention_bid?.text ? (
              <div className="atanor-mind-bid">
                <span className="atanor-mind-bid-dot" />
                {snap.attention_bid.text}
              </div>
            ) : null}
          </div>

          {!compact && snap?.goals?.length ? (
            <div className="atanor-mind-goals">
              <span className="atanor-mind-section">스스로 세운 목표</span>
              {snap.goals.filter((g) => g.status === "active").slice(0, 4).map((g) => (
                <div key={g.id} className="atanor-mind-goal">
                  <span className="atanor-mind-goal-text">{g.text}</span>
                  <span className="atanor-mind-goal-bar"><i style={{ width: `${Math.round(g.progress * 100)}%` }} /></span>
                </div>
              ))}
            </div>
          ) : null}

          {!compact && snap?.last_action?.kind ? (
            <div className="atanor-mind-action">
              <span className="atanor-mind-section">스스로 한 일</span>
              <p>
                <b>{snap.last_action.executed ? "직접 실행" : snap.last_action.blocked ? "승인 필요 (제안만)" : "시도"}</b>
                {" · "}{snap.last_action.reason || snap.last_action.kind}
              </p>
            </div>
          ) : null}

          {!compact && snap?.narrative?.length ? (
            <div className="atanor-mind-stream">
              <span className="atanor-mind-section">의식의 흐름</span>
              <ul>
                {snap.narrative.slice(-7).reverse().map((t, i) => (
                  <li key={`${t.at}-${i}`} data-kind={t.kind}>
                    <span className="atanor-mind-stream-dot" />
                    {t.text}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
