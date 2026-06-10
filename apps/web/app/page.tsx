"use client";

import { useEffect, useState } from "react";

type StageState = "idle" | "running" | "warning" | "complete";

type PipelineStage = {
  id: string;
  name: string;
  state: StageState;
  progress: number;
  summary: string;
  metric_label: string;
  metric_value: string;
};

type PipelineStatus = {
  generated_at: string;
  system_state: string;
  stages: PipelineStage[];
};

const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "";

const stateLabels: Record<StageState, string> = {
  idle: "Idle",
  running: "Running",
  warning: "Review",
  complete: "Complete",
};

export default function BakeBoardPage() {
  const [status, setStatus] = useState<PipelineStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadStatus() {
      try {
        const response = await fetch(`${apiBaseUrl}/api/pipeline/status`, {
          cache: "no-store",
        });

        if (!response.ok) {
          throw new Error(`API returned ${response.status}`);
        }

        setStatus(await response.json());
        setError(null);
      } catch (caught) {
        setError(
          caught instanceof Error
            ? caught.message
            : "Unable to load pipeline status",
        );
      }
    }

    loadStatus();
    const timer = window.setInterval(loadStatus, 10000);
    return () => window.clearInterval(timer);
  }, []);

  const runningCount =
    status?.stages.filter((stage) => stage.state === "running").length ?? 0;

  return (
    <main className="shell">
      <section className="masthead" aria-label="BakeBoard overview">
        <div>
          <p className="eyebrow">Homage1.0</p>
          <h1>BakeBoard</h1>
          <p className="lede">
            A first-pass dashboard for watching the AI factory pipeline move
            from raw ingredients to grounded answers.
          </p>
        </div>
        <div className="status-panel">
          <span>System</span>
          <strong>{status?.system_state ?? "connecting"}</strong>
          <small>{runningCount} stages running</small>
        </div>
      </section>

      {error ? <p className="error">API connection failed: {error}</p> : null}

      <section className="stage-grid" aria-label="Pipeline stages">
        {status?.stages.map((stage) => (
          <article className="stage-card" data-state={stage.state} key={stage.id}>
            <div className="stage-card__topline">
              <h2>{stage.name}</h2>
              <span>{stateLabels[stage.state]}</span>
            </div>
            <p>{stage.summary}</p>
            <div className="progress" aria-label={`${stage.progress}% complete`}>
              <div style={{ width: `${stage.progress}%` }} />
            </div>
            <div className="stage-card__footer">
              <span>{stage.metric_label}</span>
              <strong>{stage.metric_value}</strong>
            </div>
          </article>
        )) ??
          Array.from({ length: 7 }, (_, index) => (
            <article className="stage-card stage-card--loading" key={index}>
              <div />
              <div />
              <div />
            </article>
          ))}
      </section>

      <footer>
        Last update:{" "}
        {status ? new Date(status.generated_at).toLocaleString() : "waiting"}
      </footer>
    </main>
  );
}
