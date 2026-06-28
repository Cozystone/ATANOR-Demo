"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Live view of the infinite cumulative-learning loop. Polls
 * /api/cloud-brain/learning/continuous/metrics and shows real, measured growth —
 * a toggle switches between the CONCEPT graph and the SURFACE graph growth. No
 * fabricated numbers: these are the loop's own per-tick added counts.
 */

type Metrics = {
  running: boolean;
  uptime_seconds: number;
  ticks: number;
  sentences_fed: number;
  sentences_accepted: number;
  concepts_added: number;
  relations_added: number;
  surface_added: number;
  sentences_per_second: number;
  concepts_per_minute: number;
  accept_rate: number;
  last_titles: string[];
  last_error: string | null;
  source: string;
};

type View = "concept" | "surface";

export default function LiveLearningPanel({ apiBase = "" }: { apiBase?: string }) {
  const [m, setM] = useState<Metrics | null>(null);
  const [view, setView] = useState<View>("concept");
  const [series, setSeries] = useState<number[]>([]);
  const prevRef = useRef<number>(0);

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const res = await fetch(`${apiBase}/api/cloud-brain/learning/continuous/metrics`, { cache: "no-store" });
        const d = (await res.json()) as Metrics;
        if (!alive) return;
        setM(d);
        const total = view === "concept" ? d.concepts_added : d.surface_added;
        const delta = Math.max(0, total - prevRef.current);
        prevRef.current = total;
        setSeries((s) => [...s.slice(-59), delta]);
      } catch {
        /* keep last */
      }
    };
    prevRef.current = 0;
    setSeries([]);
    tick();
    const id = setInterval(tick, 2000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [apiBase, view]);

  const primary = m ? (view === "concept" ? m.concepts_added : m.surface_added) : 0;
  const rate = m ? (view === "concept" ? m.concepts_per_minute : Math.round((m.surface_added / Math.max(1, m.uptime_seconds)) * 60)) : 0;
  const max = Math.max(1, ...series);

  return (
    <div className="atanor-livelearn">
      <div className="atanor-livelearn-head">
        <span className={`atanor-livelearn-dot${m?.running ? " is-live" : ""}`} />
        <strong>실시간 누적학습</strong>
        <span className="atanor-livelearn-status">{m?.running ? "LEARNING" : "paused"}</span>
        <div className="atanor-livelearn-toggle">
          <button data-active={view === "concept"} onClick={() => setView("concept")}>개념 그래프</button>
          <button data-active={view === "surface"} onClick={() => setView("surface")}>Surface 그래프</button>
        </div>
      </div>

      <div className="atanor-livelearn-big">
        <span className="atanor-livelearn-num">{primary.toLocaleString()}</span>
        <span className="atanor-livelearn-unit">{view === "concept" ? "개념 추가" : "construction 추가"} · +{rate}/분</span>
      </div>

      <div className="atanor-livelearn-spark" aria-hidden="true">
        {series.map((v, i) => (
          <i key={i} style={{ height: `${Math.round((v / max) * 100)}%` }} data-fresh={i === series.length - 1 && v > 0 ? "true" : "false"} />
        ))}
      </div>

      <div className="atanor-livelearn-grid">
        <div><b>{m?.sentences_fed.toLocaleString() ?? 0}</b><span>문장 투입</span></div>
        <div><b>{m ? `${Math.round(m.accept_rate * 100)}%` : "—"}</b><span>수용률</span></div>
        <div><b>{m?.relations_added.toLocaleString() ?? 0}</b><span>관계 추가</span></div>
        <div><b>{m?.sentences_per_second ?? 0}</b><span>문장/초</span></div>
      </div>
      <div className="atanor-livelearn-foot">
        실제 공개 위키 문장 · 가짜 성장 없음{m?.last_error ? ` · ${m.last_error}` : ""}
      </div>
    </div>
  );
}
