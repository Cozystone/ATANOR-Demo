"use client";

import { useEffect, useMemo, useState } from "react";

type StageState = "idle" | "running" | "warning" | "complete";
type AnyRecord = Record<string, any>;

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

const stateLabels: Record<StageState, string> = {
  idle: "Idle",
  running: "Running",
  warning: "Review",
  complete: "Complete",
};

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.detail ?? body.error ?? `API returned ${response.status}`);
  }
  return body;
}

function percent(part: number, total: number) {
  return total > 0 ? Math.round((part / total) * 100) : 0;
}

function fmtDate(value?: string | null) {
  return value ? new Date(value).toLocaleString() : "waiting";
}

function asPercent(value?: number | null) {
  return Math.round((value ?? 0) * 100);
}

function LossChart({ losses }: { losses: Array<{ step: number; loss: number }> }) {
  if (!losses?.length) {
    return <div className="chart-empty">No dry-run trace</div>;
  }
  const maxLoss = Math.max(...losses.map((loss) => loss.loss));
  const minLoss = Math.min(...losses.map((loss) => loss.loss));
  const points = losses
    .map((loss, index) => {
      const x = losses.length === 1 ? 0 : (index / (losses.length - 1)) * 100;
      const y = 92 - ((loss.loss - minLoss) / Math.max(0.001, maxLoss - minLoss)) * 76;
      return `${x},${y}`;
    })
    .join(" ");
  return (
    <svg className="loss-chart" viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="Training loss trace">
      <polyline points={points} fill="none" stroke="currentColor" strokeWidth="3" vectorEffect="non-scaling-stroke" />
      {losses.map((loss, index) => {
        const x = losses.length === 1 ? 0 : (index / (losses.length - 1)) * 100;
        const y = 92 - ((loss.loss - minLoss) / Math.max(0.001, maxLoss - minLoss)) * 76;
        return <circle key={loss.step} cx={x} cy={y} r="2.4" />;
      })}
    </svg>
  );
}

function StatusPill({ state }: { state?: string }) {
  return (
    <span className="state-badge" data-state={state ?? "idle"}>
      {state ?? "idle"}
    </span>
  );
}

export default function BakeBoardPage() {
  const [pipeline, setPipeline] = useState<PipelineStatus | null>(null);
  const [datagate, setDatagate] = useState<AnyRecord | null>(null);
  const [ontology, setOntology] = useState<AnyRecord | null>(null);
  const [graph, setGraph] = useState<AnyRecord | null>(null);
  const [graphrag, setGraphRag] = useState<AnyRecord | null>(null);
  const [guard, setGuard] = useState<AnyRecord | null>(null);
  const [gpu, setGpu] = useState<AnyRecord | null>(null);
  const [system, setSystem] = useState<AnyRecord | null>(null);
  const [oven, setOven] = useState<AnyRecord | null>(null);
  const [neuro, setNeuro] = useState<AnyRecord | null>(null);
  const [query, setQuery] = useState("GraphRAG evidence guardrail");
  const [draft, setDraft] = useState("GraphRAG always guarantees perfect answers with Evidence.");
  const [error, setError] = useState<string | null>(null);

  async function refreshAll() {
    const [
      pipelineStatus,
      datagateStatus,
      ontologyStatus,
      ontologyGraph,
      graphragStatus,
      guardStatus,
      gpuStatus,
      systemStatus,
      ovenStatus,
      neuroStatus,
    ] = await Promise.all([
      fetchJson<PipelineStatus>("/api/pipeline/status"),
      fetchJson<AnyRecord>("/api/datagate/status"),
      fetchJson<AnyRecord>("/api/ontology/status"),
      fetchJson<AnyRecord>("/api/ontology/graph"),
      fetchJson<AnyRecord>("/api/graphrag/status"),
      fetchJson<AnyRecord>("/api/guard/status"),
      fetchJson<AnyRecord>("/api/telemetry/gpu"),
      fetchJson<AnyRecord>("/api/telemetry/system"),
      fetchJson<AnyRecord>("/api/oven/status"),
      fetchJson<AnyRecord>("/api/neuro/plan"),
    ]);
    setPipeline(pipelineStatus);
    setDatagate(datagateStatus);
    setOntology(ontologyStatus);
    setGraph(ontologyGraph);
    setGraphRag(graphragStatus);
    setGuard(guardStatus);
    setGpu(gpuStatus);
    setSystem(systemStatus);
    setOven(ovenStatus);
    setNeuro(neuroStatus);
  }

  useEffect(() => {
    refreshAll().catch((caught) => setError(caught instanceof Error ? caught.message : "Unable to load BakeBoard"));
    const timer = window.setInterval(() => {
      refreshAll().catch(() => undefined);
    }, 10000);
    return () => window.clearInterval(timer);
  }, []);

  async function runAction(action: () => Promise<unknown>) {
    setError(null);
    try {
      await action();
      await refreshAll();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Action failed");
    }
  }

  async function rebalanceNeuro() {
    setError(null);
    try {
      const plan = await fetchJson<AnyRecord>("/api/neuro/plan", {
        method: "POST",
        body: JSON.stringify({
          text: `${query}\n${draft}`,
          task_type: "alpha-dashboard",
          target_device: "low-spec-cpu-gpu",
          module_budget: 4,
        }),
      });
      setNeuro(plan);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Neuro planning failed");
    }
  }

  const runningCount = pipeline?.stages.filter((stage) => stage.state === "running").length ?? 0;
  const rejectedEntries = Object.entries(datagate?.rejection_breakdown ?? {});
  const graphResult = graphrag?.result ?? null;
  const guardResult = guard?.result ?? null;
  const losses = oven?.losses ?? oven?.result?.losses ?? [];
  const neuroModules = neuro?.module_routing?.modules ?? [];
  const activeModuleIds = new Set<string>(neuro?.module_routing?.active_modules ?? []);
  const eventSparsity = asPercent(neuro?.event_gate?.sparsity);
  const eventDensity = asPercent(neuro?.event_gate?.event_density);
  const energyReduction = asPercent(neuro?.energy_estimate?.reduction_ratio);
  const pruningTarget = asPercent(neuro?.compression?.pruning_target);
  const maskRatio = asPercent(neuro?.learning_plan?.self_supervised?.mask_ratio);

  const flowHealth = useMemo(() => {
    const complete = pipeline?.stages.filter((stage) => stage.state === "complete").length ?? 0;
    return Math.round((complete / 7) * 100);
  }, [pipeline]);

  return (
    <main className="shell">
      <section className="masthead" aria-label="BakeBoard overview">
        <div>
          <p className="eyebrow">Homage1.0 Alpha</p>
          <h1>BakeBoard</h1>
          <p className="lede">
            Transparent AI factory controls for DataGate, Ontology Forge, GraphRAG,
            Guardrail, GPU telemetry, and Homage-Core dry-run training.
          </p>
        </div>
        <div className="status-panel">
          <span>Factory</span>
          <strong>{pipeline?.system_state ?? "connecting"}</strong>
          <small>{runningCount} stages running</small>
          <div className="progress" aria-label={`${flowHealth}% alpha flow health`}>
            <div style={{ width: `${flowHealth}%` }} />
          </div>
        </div>
      </section>

      {error ? <p className="error">Alpha action failed: {error}</p> : null}

      <section className="stage-grid" aria-label="Pipeline stages">
        {pipeline?.stages.map((stage) => (
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

      <section className="control-grid" aria-label="Alpha controls">
        <article className="alpha-panel alpha-panel--wide">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Ingredient Room</p>
              <h2>DataGate</h2>
            </div>
            <button onClick={() => runAction(() => fetchJson("/api/datagate/run", { method: "POST", body: JSON.stringify({ input_dir: "data/raw" }) }))}>
              Run
            </button>
          </div>
          <div className="strip"><StatusPill state={datagate?.state} /><span>{datagate?.run_id ?? "No run"}</span><span>{fmtDate(datagate?.finished_at)}</span></div>
          <div className="metric-grid">
            <div className="metric-item"><span>Total docs</span><strong>{datagate?.total ?? 0}</strong></div>
            <div className="metric-item"><span>Accepted</span><strong>{datagate?.accepted ?? 0}</strong></div>
            <div className="metric-item"><span>Rejected</span><strong>{datagate?.rejected ?? 0}</strong></div>
            <div className="metric-item"><span>Accept rate</span><strong>{percent(datagate?.accepted ?? 0, datagate?.total ?? 0)}%</strong></div>
          </div>
          <div className="mini-list">
            <h3>Rejection Breakdown</h3>
            {rejectedEntries.length ? rejectedEntries.map(([name, count]) => <div className="row" key={name}><span>{name}</span><strong>{String(count)}</strong></div>) : <p>No rejected documents.</p>}
          </div>
        </article>

        <article className="alpha-panel">
          <div className="panel-header">
            <div><p className="eyebrow">Ontology Lab</p><h2>Ontology Forge</h2></div>
            <button onClick={() => runAction(() => fetchJson("/api/ontology/run", { method: "POST" }))}>Run</button>
          </div>
          <div className="strip"><StatusPill state={ontology?.state} /><span>{ontology?.node_count ?? 0} nodes</span><span>{ontology?.edge_count ?? 0} edges</span></div>
          <div className="graph-preview">
            {(graph?.nodes ?? []).slice(0, 6).map((node: AnyRecord, index: number) => (
              <span className="node-chip" key={`${node.id}-${index}`}>{node.label}</span>
            ))}
          </div>
          <div className="mini-list">
            <h3>Candidate Edges</h3>
            {(graph?.edges ?? []).slice(0, 4).map((edge: AnyRecord, index: number) => (
              <div className="row" key={`${edge.source}-${edge.target}-${index}`}>
                <span>{edge.source} {edge.relation} {edge.target}</span>
                <strong>{edge.confidence}</strong>
              </div>
            ))}
          </div>
        </article>

        <article className="alpha-panel">
          <div className="panel-header">
            <div><p className="eyebrow">Oven Room</p><h2>Homage Oven</h2></div>
            <button onClick={() => runAction(() => fetchJson("/api/oven/dry-run", { method: "POST" }))}>Dry Run</button>
          </div>
          <div className="strip"><StatusPill state={oven?.state} /><span>loss {oven?.last_loss ?? "none"}</span></div>
          <LossChart losses={losses} />
          <div className="train-meta">
            <span>checkpoint</span>
            <strong>{oven?.checkpoint_path ?? "not written"}</strong>
          </div>
        </article>

        <article className="alpha-panel alpha-panel--wide">
          <div className="panel-header">
            <div><p className="eyebrow">Neuro Lab</p><h2>Neuro-Efficiency Layer</h2></div>
            <button onClick={rebalanceNeuro}>Rebalance</button>
          </div>
          <div className="efficiency-hero">
            <div className="efficiency-score">
              <strong>{energyReduction}%</strong>
              <span>estimated compute reduction</span>
            </div>
            <div className="efficiency-stack">
              <div className="row"><span>event sparsity</span><strong>{eventSparsity}%</strong></div>
              <div className="row"><span>event density</span><strong>{eventDensity}%</strong></div>
              <div className="row"><span>active modules</span><strong>{activeModuleIds.size || 0}/{neuroModules.length || 7}</strong></div>
              <div className="row"><span>precision</span><strong>{neuro?.compression?.quantization_bits ?? 8}-bit</strong></div>
            </div>
          </div>
          <div className="module-bars" aria-label="Neuro module activation">
            {neuroModules.map((module: AnyRecord) => (
              <div className="module-bar" data-active={activeModuleIds.has(module.id)} key={module.id}>
                <div className="module-bar__label">
                  <span>{module.name}</span>
                  <strong>{Math.round((module.score ?? 0) * 100)}%</strong>
                </div>
                <div className="module-bar__track"><div style={{ width: `${Math.round((module.score ?? 0) * 100)}%` }} /></div>
              </div>
            ))}
          </div>
          <div className="learning-grid">
            <div><span>Continual</span><strong>EWC {neuro?.learning_plan?.continual?.ewc_lambda ?? 0.42}</strong></div>
            <div><span>Few-shot</span><strong>{neuro?.learning_plan?.few_shot?.prototype_slots ?? 0} prototypes</strong></div>
            <div><span>Self-supervised</span><strong>{maskRatio}% mask</strong></div>
            <div><span>Compression</span><strong>{pruningTarget}% prune</strong></div>
          </div>
          <div className="mini-list">
            <h3>Research-backed Actions</h3>
            {(neuro?.recommendations ?? []).slice(0, 4).map((item: string) => <div className="row" key={item}><span>{item}</span></div>)}
          </div>
        </article>

        <article className="alpha-panel alpha-panel--wide">
          <div className="panel-header">
            <div><p className="eyebrow">Trace Room</p><h2>GraphRAG</h2></div>
            <button onClick={() => runAction(() => fetchJson("/api/graphrag/query", { method: "POST", body: JSON.stringify({ query }) }))}>Query</button>
          </div>
          <input className="text-input" value={query} onChange={(event) => setQuery(event.target.value)} />
          <div className="strip"><StatusPill state={graphrag?.state} /><span>confidence {graphrag?.confidence ?? 0}</span><span>{graphrag?.last_query ?? "No query"}</span></div>
          <div className="split-list">
            <div className="mini-list">
              <h3>Matched Nodes</h3>
              {(graphResult?.matched_nodes ?? []).slice(0, 5).map((node: AnyRecord) => <div className="row" key={node.id}><span>{node.label}</span><strong>{node.confidence ?? ""}</strong></div>)}
            </div>
            <div className="mini-list">
              <h3>Evidence Docs</h3>
              {(graphResult?.evidence_docs ?? []).slice(0, 3).map((doc: AnyRecord) => <div className="evidence" key={doc.doc_id}><strong>{doc.doc_id}</strong><span>{doc.snippet}</span></div>)}
            </div>
          </div>
        </article>

        <article className="alpha-panel alpha-panel--wide">
          <div className="panel-header">
            <div><p className="eyebrow">Inspector</p><h2>Guardrail</h2></div>
            <button onClick={() => runAction(() => fetchJson("/api/guard/check", { method: "POST", body: JSON.stringify({ draft_answer: draft, evidence_bundle: graphResult }) }))}>Check</button>
          </div>
          <textarea className="draft-input" value={draft} onChange={(event) => setDraft(event.target.value)} />
          <div className="strip"><StatusPill state={guard?.state} /><span>guard score {guard?.overall_guard_score ?? 0}</span></div>
          <div className="mini-list">
            <h3>Claims</h3>
            {(guardResult?.claims ?? []).map((claim: AnyRecord, index: number) => (
              <div className="claim-row" data-support={claim.support} key={`${claim.claim}-${index}`}>
                <span>{claim.claim}</span>
                <strong>{claim.support}</strong>
              </div>
            ))}
            {(guardResult?.warnings ?? []).map((warning: string) => <p className="warning-text" key={warning}>{warning}</p>)}
          </div>
        </article>

        <article className="alpha-panel">
          <div className="panel-header">
            <div><p className="eyebrow">Monitor</p><h2>GPU Monitor</h2></div>
            <button onClick={() => runAction(refreshAll)}>Refresh</button>
          </div>
          <div className="gpu-gauge">
            <div style={{ width: `${Math.min(100, gpu?.utilization ?? 0)}%` }} />
          </div>
          <div className="metric-grid metric-grid--compact">
            <div className="metric-item"><span>GPU</span><strong>{gpu?.gpu_name ?? "Unknown"}</strong></div>
            <div className="metric-item"><span>Util</span><strong>{gpu?.utilization ?? 0}%</strong></div>
            <div className="metric-item"><span>VRAM</span><strong>{gpu?.vram_total ? `${gpu.vram_used}/${gpu.vram_total}` : "fallback"}</strong></div>
            <div className="metric-item"><span>CPU</span><strong>{system?.cpu_count ?? "n/a"}</strong></div>
          </div>
          <p className="muted-line">{gpu?.message ?? "Telemetry online"}</p>
        </article>
      </section>

      <footer>
        Last update: {pipeline ? new Date(pipeline.generated_at).toLocaleString() : "waiting"}
      </footer>
    </main>
  );
}
