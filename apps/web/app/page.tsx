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

type DataGateState = "idle" | "running" | "completed" | "failed";

type DataGateStatus = {
  state: DataGateState;
  run_id: string | null;
  total: number;
  accepted: number;
  rejected: number;
  rejection_breakdown: Record<string, number>;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
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
  const [datagateStatus, setDatagateStatus] = useState<DataGateStatus | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const [datagateError, setDatagateError] = useState<string | null>(null);

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

  async function loadDataGateStatus() {
    try {
      const response = await fetch(`${apiBaseUrl}/api/datagate/status`, {
        cache: "no-store",
      });

      if (!response.ok) {
        throw new Error(`API returned ${response.status}`);
      }

      setDatagateStatus(await response.json());
      setDatagateError(null);
    } catch (caught) {
      setDatagateError(
        caught instanceof Error
          ? caught.message
          : "Unable to load DataGate status",
      );
    }
  }

  useEffect(() => {
    loadDataGateStatus();
  }, []);

  useEffect(() => {
    if (datagateStatus?.state !== "running") {
      return;
    }

    const timer = window.setInterval(loadDataGateStatus, 2000);
    return () => window.clearInterval(timer);
  }, [datagateStatus?.state]);

  async function runDataGate() {
    setDatagateError(null);
    try {
      const response = await fetch(`${apiBaseUrl}/api/datagate/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ input_dir: "data/raw" }),
      });

      const body = await response.json();

      if (!response.ok) {
        throw new Error(body.detail ?? body.error ?? `API returned ${response.status}`);
      }

      await loadDataGateStatus();
    } catch (caught) {
      setDatagateError(
        caught instanceof Error ? caught.message : "Unable to start DataGate",
      );
    }
  }

  const runningCount =
    status?.stages.filter((stage) => stage.state === "running").length ?? 0;
  const isDataGateRunning = datagateStatus?.state === "running";
  const acceptRate =
    datagateStatus && datagateStatus.total > 0
      ? Math.round((datagateStatus.accepted / datagateStatus.total) * 100)
      : 0;
  const rejectionEntries = Object.entries(
    datagateStatus?.rejection_breakdown ?? {},
  );

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

      <section className="datagate-panel" aria-label="DataGate controls">
        <div className="datagate-panel__header">
          <div>
            <p className="eyebrow">Ingredient Room</p>
            <h2>DataGate</h2>
          </div>
          <button
            className="run-button"
            disabled={isDataGateRunning}
            onClick={runDataGate}
            type="button"
          >
            {isDataGateRunning ? "Running..." : "Run"}
          </button>
        </div>

        <div className="datagate-status-strip">
          <span className="state-badge" data-state={datagateStatus?.state ?? "idle"}>
            {datagateStatus?.state ?? "idle"}
          </span>
          <span>{datagateStatus?.run_id ?? "No run yet"}</span>
          <span>
            Last run:{" "}
            {datagateStatus?.finished_at
              ? new Date(datagateStatus.finished_at).toLocaleString()
              : "waiting"}
          </span>
        </div>

        {datagateError ? (
          <p className="error">DataGate failed: {datagateError}</p>
        ) : null}
        {datagateStatus?.error ? (
          <p className="error">DataGate failed: {datagateStatus.error}</p>
        ) : null}

        <div className="metric-grid">
          <div className="metric-item">
            <span>Total docs</span>
            <strong>{datagateStatus?.total ?? 0}</strong>
          </div>
          <div className="metric-item">
            <span>Accepted</span>
            <strong>{datagateStatus?.accepted ?? 0}</strong>
          </div>
          <div className="metric-item">
            <span>Rejected</span>
            <strong>{datagateStatus?.rejected ?? 0}</strong>
          </div>
          <div className="metric-item">
            <span>Accept rate</span>
            <strong>{acceptRate}%</strong>
          </div>
        </div>

        <div className="breakdown">
          <h3>Rejection Breakdown</h3>
          {rejectionEntries.length > 0 ? (
            rejectionEntries.map(([name, count]) => (
              <div className="breakdown-row" key={name}>
                <span>{name}</span>
                <strong>{count}</strong>
              </div>
            ))
          ) : (
            <p>No rejected documents in the latest run.</p>
          )}
        </div>
      </section>

      <footer>
        Last update:{" "}
        {status ? new Date(status.generated_at).toLocaleString() : "waiting"}
      </footer>
    </main>
  );
}
