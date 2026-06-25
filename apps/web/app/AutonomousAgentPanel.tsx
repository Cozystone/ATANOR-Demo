"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Activity, Brain, Globe, Pause, Play, ShieldCheck, Sparkles, Square } from "lucide-react";

type Language = "en" | "ko";
type AnyRecord = Record<string, any>;

type ActivityEntry = {
  id: string;
  at: string;
  cycle: number;
  thought: string;
  actions: string[];
  candidateDrafts: number;
  splatraFrames: number;
  reviewItems: number;
  curiosity: number;
  fatigue: number;
  nextDelay: number;
  ran: boolean;
  reason: string;
};

const copy = {
  en: {
    title: "Autonomous Agent",
    sub: "ATANOR drives itself: bounded public-web reading, candidate drafting, and SPLATRA proof frames — on its own cadence. Nothing is promoted or written without your approval.",
    start: "Begin autonomous run",
    stop: "Stop",
    confirmLabel: "I authorize ATANOR to run autonomously (read-only web, candidate-only, no production write).",
    idle: "Idle — operator confirmation required before any cycle.",
    running: "Running autonomously",
    stopped: "Stopped",
    feed: "Live activity",
    empty: "No cycles yet. Authorize and begin to watch ATANOR think on its own.",
    cycle: "cycle",
    drafts: "candidate drafts",
    frames: "SPLATRA frames",
    nextIn: "next in",
    curiosity: "curiosity",
    fatigue: "fatigue",
    locks: "Safety locks",
  },
  ko: {
    title: "자율 에이전트",
    sub: "ATANOR가 스스로 구동합니다: 공개 웹 읽기·후보 초안·SPLATRA 증명 프레임을 자신의 리듬으로. 승인 없이는 무엇도 승격·기록되지 않습니다.",
    start: "자율 구동 시작",
    stop: "정지",
    confirmLabel: "ATANOR의 자율 구동을 승인합니다 (읽기 전용 웹, 후보 전용, 운영 기록 없음).",
    idle: "대기 — 모든 사이클 전 오퍼레이터 확인이 필요합니다.",
    running: "자율 구동 중",
    stopped: "정지됨",
    feed: "실시간 활동",
    empty: "아직 사이클이 없습니다. 승인 후 시작하면 ATANOR가 스스로 사고하는 과정을 볼 수 있습니다.",
    cycle: "사이클",
    drafts: "후보 초안",
    frames: "SPLATRA 프레임",
    nextIn: "다음까지",
    curiosity: "호기심",
    fatigue: "피로",
    locks: "안전 잠금",
  },
} satisfies Record<Language, Record<string, string>>;

const ACTION_LABELS: Record<string, { en: string; ko: string }> = {
  web_explorer_fixture_step: { en: "read public web evidence", ko: "공개 웹 근거 읽기" },
  review_import: { en: "imported drafts to review queue", ko: "검토 큐에 초안 등록" },
  splatra_frames: { en: "rendered SPLATRA proof frame", ko: "SPLATRA 증명 프레임 생성" },
  host_status_checks: { en: "host status check (read-only)", ko: "호스트 상태 점검 (읽기 전용)" },
  review_queue_pressure_request_review: { en: "paused to request human review", ko: "사람 검토 요청을 위해 일시정지" },
};

function labelAction(raw: string, language: Language): string {
  const key = raw.split(":")[0];
  const found = ACTION_LABELS[key];
  if (!found) return raw;
  const suffix = raw.includes(":") ? ` (${raw.split(":")[1]})` : "";
  return found[language] + suffix;
}

function num(value: unknown, fallback = 0): number {
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : fallback;
}

async function callJson(path: string, init?: RequestInit): Promise<AnyRecord | null> {
  try {
    const res = await fetch(path, { cache: "no-store", ...init });
    return (await res.json()) as AnyRecord;
  } catch {
    return null;
  }
}

const SCHED = "/api/agentic-os/policy-scheduler";
// Honor the engine's own cadence (next_delay_sec) but clamp to a live-watchable
// window so the operator can actually see each cycle.
const MIN_TICK_MS = 1800;
const MAX_TICK_MS = 6000;
const MAX_FEED = 24;

export default function AutonomousAgentPanel({ language }: { language: Language }) {
  const t = copy[language];
  const [enabled, setEnabled] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [status, setStatus] = useState<AnyRecord | null>(null);
  const [feed, setFeed] = useState<ActivityEntry[]>([]);
  const [busy, setBusy] = useState(false);

  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const enabledRef = useRef(false);

  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  // One bounded cycle, then schedule the next at the engine's own pace.
  const driveOnce = useCallback(async () => {
    if (!enabledRef.current) return;
    const payload = await callJson(`${SCHED}/tick`, { method: "POST", headers: { "content-type": "application/json" }, body: "{}" });
    if (!payload || !enabledRef.current) return;
    setStatus(payload);

    const result = (payload.last_result as AnyRecord) ?? {};
    const states = Array.isArray(result.states) ? result.states : [];
    const lastState = states.length ? (states[states.length - 1] as AnyRecord) : {};
    const actions = Array.isArray(lastState.actions_taken) ? (lastState.actions_taken as string[]) : [];
    const vector = ((payload.last_emotion as AnyRecord)?.vector as AnyRecord) ?? {};
    const policy = (payload.last_policy as AnyRecord) ?? {};
    const reasons = Array.isArray(policy.reasons) ? (policy.reasons as string[]) : [];
    const ran = Boolean(payload.ran);
    const reason = String(payload.reason ?? "");
    const nextDelay = num(payload.next_delay_sec, 5);
    const curiosity = num(vector.curiosity);
    const fatigue = num(vector.fatigue);

    const drafts = num(result.candidate_drafts);
    const frames = num(result.splatra_frames);
    const actionPhrase = actions.length
      ? actions.map((a) => labelAction(a, language)).join(", ")
      : language === "ko" ? "관찰만 수행" : "observed only";
    const driver = reasons[0] ? `${reasons[0]} · ` : "";
    const thought = ran
      ? `${driver}${language === "ko" ? `호기심 ${curiosity.toFixed(2)} — ${actionPhrase}` : `curiosity ${curiosity.toFixed(2)} — ${actionPhrase}`}`
      : `${language === "ko" ? "쉼" : "rest"}: ${reason}`;

    const entry: ActivityEntry = {
      id: `${payload.scheduler_id ?? "sched"}-${Date.now()}`,
      at: new Date().toLocaleTimeString(),
      cycle: num(payload.cycle_count),
      thought,
      actions,
      candidateDrafts: drafts,
      splatraFrames: frames,
      reviewItems: num(result.review_items),
      curiosity,
      fatigue,
      nextDelay,
      ran,
      reason,
    };
    setFeed((prev) => [entry, ...prev].slice(0, MAX_FEED));

    // The engine asked to stop / rest, or hit its bound — honor it.
    if (!payload.enabled || !ran) {
      enabledRef.current = false;
      setEnabled(false);
      clearTimer();
      return;
    }
    const delayMs = Math.max(MIN_TICK_MS, Math.min(MAX_TICK_MS, nextDelay * 1000));
    timerRef.current = setTimeout(driveOnce, delayMs);
  }, [clearTimer, language]);

  const start = useCallback(async () => {
    if (!confirmed || busy) return;
    setBusy(true);
    const payload = await callJson(`${SCHED}/start`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        operator_confirmed: true,
        max_cycles: 2000,
        max_runtime_sec: 3600,
        min_interval_sec: 2,
        max_interval_sec: 30,
        allow_web_explorer: true,
        allow_review_import: true,
        allow_splatra_generation: true,
        allow_host_executor_status_only: true,
      }),
    });
    setBusy(false);
    if (!payload || payload.allowed === false || payload.enabled === false) {
      setStatus(payload);
      return;
    }
    setStatus(payload);
    enabledRef.current = true;
    setEnabled(true);
    clearTimer();
    timerRef.current = setTimeout(driveOnce, 400);
  }, [confirmed, busy, driveOnce, clearTimer]);

  const stop = useCallback(async () => {
    enabledRef.current = false;
    setEnabled(false);
    clearTimer();
    const payload = await callJson(`${SCHED}/stop`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ reason: "operator_stop" }) });
    if (payload) setStatus(payload);
  }, [clearTimer]);

  useEffect(() => {
    callJson(`${SCHED}/status`).then((s) => { if (s) setStatus(s); });
    return () => {
      enabledRef.current = false;
      clearTimer();
    };
  }, [clearTimer]);

  const flags = (status?.safety_flags as AnyRecord) ?? {};
  const locks = [
    ["production_store_mutated", flags.production_store_mutated],
    ["local_brain_write", flags.local_brain_write],
    ["candidate_promotion", flags.candidate_promotion],
    ["human_approval_required", flags.human_approval_required],
    ["scheduler_opt_in", flags.scheduler_opt_in],
    ["no_daemon_autostart", flags.no_daemon_autostart],
  ].filter(([, v]) => v !== undefined);

  const stateLabel = enabled ? t.running : status?.stopped_reason && status.stopped_reason !== "disabled" ? `${t.stopped} · ${status.stopped_reason}` : t.idle;

  return (
    <section className="autonomous-agent" aria-label={t.title} style={{ display: "grid", gap: 16, color: "#dbe6ff" }}>
      <header style={{ display: "grid", gap: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <Brain size={20} color="#6fa8ff" />
          <h2 style={{ margin: 0, fontSize: 22, color: "#eaf1ff" }}>{t.title}</h2>
          <span style={{ marginLeft: "auto", display: "inline-flex", alignItems: "center", gap: 7, fontSize: 12.5, color: enabled ? "#7fd8a6" : "#8a93a8" }}>
            <span style={{ width: 9, height: 9, borderRadius: "50%", background: enabled ? "#48d18a" : "#56607a", boxShadow: enabled ? "0 0 10px #48d18a" : "none", animation: enabled ? "aa-pulse 1.4s ease-in-out infinite" : "none" }} />
            {stateLabel}
          </span>
        </div>
        <p style={{ margin: 0, color: "#9aa4bd", fontSize: 13, lineHeight: 1.55, maxWidth: 720 }}>{t.sub}</p>
      </header>

      <div style={{ display: "grid", gap: 12, border: "1px solid #1d2636", borderRadius: 14, padding: "14px 16px", background: "rgba(13,18,30,0.5)" }}>
        <label style={{ display: "flex", alignItems: "flex-start", gap: 9, fontSize: 12.5, color: "#b6c1da", cursor: enabled ? "default" : "pointer" }}>
          <input type="checkbox" checked={confirmed} disabled={enabled} onChange={(e) => setConfirmed(e.target.checked)} style={{ marginTop: 2 }} />
          <span>{t.confirmLabel}</span>
        </label>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          {!enabled ? (
            <button type="button" onClick={start} disabled={!confirmed || busy}
              style={{ display: "inline-flex", alignItems: "center", gap: 7, padding: "9px 16px", borderRadius: 10, border: "1px solid #2f6df0", background: confirmed && !busy ? "#2f6df0" : "#1b2740", color: confirmed && !busy ? "#fff" : "#6b7488", fontSize: 13.5, cursor: confirmed && !busy ? "pointer" : "not-allowed" }}>
              <Play size={15} /> {t.start}
            </button>
          ) : (
            <button type="button" onClick={stop}
              style={{ display: "inline-flex", alignItems: "center", gap: 7, padding: "9px 16px", borderRadius: 10, border: "1px solid #4a3a4a", background: "#2a1e2a", color: "#f0c0c8", fontSize: 13.5, cursor: "pointer" }}>
              <Square size={14} /> {t.stop}
            </button>
          )}
        </div>
        {locks.length ? (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, alignItems: "center" }}>
            <ShieldCheck size={13} color="#7fd8a6" />
            {locks.map(([name, value]) => (
              <em key={String(name)} style={{ fontStyle: "normal", fontSize: 11, color: value ? "#f5b362" : "#7fd8a6", border: `1px solid ${value ? "#4a3a23" : "#244a36"}`, borderRadius: 10, padding: "2px 8px" }}>
                {String(name)}={String(value)}
              </em>
            ))}
          </div>
        ) : null}
      </div>

      <section aria-label={t.feed} style={{ display: "grid", gap: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Activity size={16} color="#6fa8ff" />
          <strong style={{ fontSize: 14, color: "#dbe6ff" }}>{t.feed}</strong>
        </div>
        {feed.length === 0 ? (
          <p style={{ color: "#6b7488", fontSize: 12.5, margin: "4px 0 0" }}>{t.empty}</p>
        ) : (
          <ol style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 8 }}>
            {feed.map((e) => (
              <li key={e.id} style={{ border: "1px solid #1b2436", borderRadius: 12, padding: "10px 13px", background: e.ran ? "rgba(15,22,38,0.55)" : "rgba(38,28,20,0.4)", display: "grid", gap: 6 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11.5, color: "#7d869b" }}>
                  <span style={{ color: "#6fa8ff" }}>{t.cycle} {e.cycle}</span>
                  <span>· {e.at}</span>
                  <span style={{ marginLeft: "auto" }}>{t.nextIn} {e.nextDelay.toFixed(1)}s</span>
                </div>
                <p style={{ margin: 0, fontSize: 13, color: "#e2e9fb", lineHeight: 1.5 }}>
                  {e.actions.includes("web_explorer_fixture_step") ? <Globe size={12} style={{ verticalAlign: "-1px", marginRight: 5, color: "#6fa8ff" }} /> : <Sparkles size={12} style={{ verticalAlign: "-1px", marginRight: 5, color: "#c08af0" }} />}
                  {e.thought}
                </p>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6, fontSize: 10.5, color: "#9aa4bd" }}>
                  <span style={{ border: "1px solid #243049", borderRadius: 8, padding: "1px 7px" }}>{t.drafts} {e.candidateDrafts}</span>
                  <span style={{ border: "1px solid #243049", borderRadius: 8, padding: "1px 7px" }}>{t.frames} {e.splatraFrames}</span>
                  <span style={{ border: "1px solid #243049", borderRadius: 8, padding: "1px 7px" }}>{t.curiosity} {e.curiosity.toFixed(2)}</span>
                  <span style={{ border: "1px solid #243049", borderRadius: 8, padding: "1px 7px" }}>{t.fatigue} {e.fatigue.toFixed(2)}</span>
                </div>
              </li>
            ))}
          </ol>
        )}
      </section>

      <style>{`@keyframes aa-pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.35; } }`}</style>
    </section>
  );
}
