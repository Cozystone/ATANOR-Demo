"use client";

import { useEffect, useMemo, useState } from "react";

type StageState = "idle" | "running" | "warning" | "complete";
type LayoutMode = "graph" | "split" | "workbench";
type RightMode = "process" | "chat";
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

type ChatMessage = {
  role: "user" | "assistant";
  text: string;
  evidence?: AnyRecord[];
};

type MemoryNode = {
  id: string;
  label: string;
  type: string;
  confidence: number;
  x: number;
  y: number;
  color: string;
};

type MemoryEdge = {
  id: string;
  source: string;
  target: string;
  relation: string;
  confidence: number;
};

const stateLabels: Record<string, string> = {
  idle: "대기",
  running: "진행 중",
  completed: "완료",
  complete: "완료",
  failed: "실패",
  warning: "점검",
};

const memoryColors = ["#ff6b35", "#006a9f", "#8c3fa7", "#22936f", "#c5283d", "#e89d2a", "#4a8fdb"];

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

function asPercent(value?: number | null) {
  return Math.round((value ?? 0) * 100);
}

function statusText(state?: string) {
  return stateLabels[state ?? "idle"] ?? state ?? "대기";
}

function fmtClock(date = new Date()) {
  return date.toLocaleTimeString("ko-KR", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function LossChart({ losses }: { losses: Array<{ step: number; loss: number }> }) {
  if (!losses?.length) {
    return <div className="chart-empty">학습 dry-run 기록 없음</div>;
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
    <svg className="loss-chart" viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="학습 손실 곡선">
      <polyline points={points} fill="none" stroke="currentColor" strokeWidth="3" vectorEffect="non-scaling-stroke" />
      {losses.map((loss, index) => {
        const x = losses.length === 1 ? 0 : (index / (losses.length - 1)) * 100;
        const y = 92 - ((loss.loss - minLoss) / Math.max(0.001, maxLoss - minLoss)) * 76;
        return <circle key={loss.step} cx={x} cy={y} r="2.3" />;
      })}
    </svg>
  );
}

function StatusDot({ state }: { state?: string }) {
  return (
    <span className="status-indicator" data-state={state ?? "idle"}>
      <span className="status-dot" />
      {statusText(state)}
    </span>
  );
}

function makeMemoryNodes(graph: AnyRecord | null): MemoryNode[] {
  const rawNodes = graph?.nodes?.length
    ? graph.nodes
    : [
        { id: "datagate", label: "DataGate", type: "quality" },
        { id: "ontology", label: "Ontology", type: "memory" },
        { id: "rag", label: "RAG", type: "retrieval" },
        { id: "guardrail", label: "Guardrail", type: "verification" },
        { id: "oven", label: "Oven", type: "learning" },
        { id: "neuro", label: "Neuro-Efficiency", type: "efficiency" },
      ];
  const positions = [
    [52, 18],
    [78, 30],
    [82, 58],
    [60, 78],
    [32, 76],
    [16, 50],
    [25, 24],
    [48, 48],
    [70, 70],
    [36, 38],
    [18, 72],
    [86, 20],
  ];
  return rawNodes.slice(0, 12).map((node: AnyRecord, index: number) => ({
    id: node.id ?? node.label ?? `node-${index}`,
    label: node.label ?? node.name ?? node.id ?? `Node ${index + 1}`,
    type: node.type ?? node.labels?.[0] ?? "concept",
    confidence: node.confidence ?? 0.72,
    x: positions[index % positions.length][0],
    y: positions[index % positions.length][1],
    color: memoryColors[index % memoryColors.length],
  }));
}

function makeMemoryEdges(graph: AnyRecord | null, nodes: MemoryNode[]): MemoryEdge[] {
  const nodeIds = new Set(nodes.map((node) => node.id));
  const rawEdges = graph?.edges?.length
    ? graph.edges
    : [
        { source: "datagate", target: "ontology", relation: "cleans_for" },
        { source: "ontology", target: "rag", relation: "grounds" },
        { source: "rag", target: "guardrail", relation: "evidence_for" },
        { source: "oven", target: "neuro", relation: "optimizes" },
        { source: "neuro", target: "rag", relation: "routes" },
      ];
  return rawEdges
    .filter((edge: AnyRecord) => nodeIds.has(edge.source) && nodeIds.has(edge.target))
    .slice(0, 18)
    .map((edge: AnyRecord, index: number) => ({
      id: `${edge.source}-${edge.target}-${index}`,
      source: edge.source,
      target: edge.target,
      relation: edge.relation ?? edge.name ?? "relates",
      confidence: edge.confidence ?? 0.7,
    }));
}

export default function BakeBoardPage() {
  const [layoutMode, setLayoutMode] = useState<LayoutMode>("split");
  const [rightMode, setRightMode] = useState<RightMode>("process");
  const [autoChatOpened, setAutoChatOpened] = useState(false);
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
  const [selectedMemory, setSelectedMemory] = useState<AnyRecord | null>(null);
  const [chatInput, setChatInput] = useState("GraphRAG가 Evidence를 어떻게 사용해서 답변을 검증하나요?");
  const [draft, setDraft] = useState("GraphRAG는 Evidence를 사용해 답변 근거를 확인하고 Guardrail은 과장 표현을 점검합니다.");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      text: "학습 dry-run이 완료되면 이 공간은 RAG 채팅 콘솔로 전환됩니다. 질문을 보내면 온톨로지 메모리와 문서 근거를 함께 조회합니다.",
    },
  ]);
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
    refreshAll().catch((caught) => setError(caught instanceof Error ? caught.message : "BakeBoard를 불러오지 못했습니다."));
    const timer = window.setInterval(() => {
      refreshAll().catch(() => undefined);
    }, 10000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!autoChatOpened && oven?.state === "completed") {
      setRightMode("chat");
      setAutoChatOpened(true);
    }
  }, [autoChatOpened, oven?.state]);

  async function runAction(action: () => Promise<unknown>) {
    setError(null);
    try {
      await action();
      await refreshAll();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "작업 실행에 실패했습니다.");
    }
  }

  async function runTrainingDryRun() {
    setError(null);
    setRightMode("process");
    try {
      const result = await fetchJson<AnyRecord>("/api/oven/dry-run", { method: "POST" });
      setOven(result);
      setRightMode("chat");
      setAutoChatOpened(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "학습 dry-run에 실패했습니다.");
    }
  }

  async function sendChat() {
    const question = chatInput.trim();
    if (!question) return;
    setError(null);
    setChatMessages((messages) => [...messages, { role: "user", text: question }]);
    try {
      const result = await fetchJson<AnyRecord>("/api/graphrag/query", {
        method: "POST",
        body: JSON.stringify({ query: question }),
      });
      setGraphRag(result);
      const evidence = result?.result?.evidence_docs ?? [];
      const nodes = result?.result?.matched_nodes ?? [];
      const answer = result?.result?.answer;
      const nodeText = nodes.length ? nodes.map((node: AnyRecord) => node.label).join(", ") : "현재 메모리";
      setChatMessages((messages) => [
        ...messages,
        {
          role: "assistant",
          text: answer ?? `${nodeText} 중심으로 근거를 찾았습니다. 근거 문서 ${evidence.length}개를 연결했고, 신뢰도는 ${Math.round((result?.confidence ?? 0) * 100)}%입니다.`,
          evidence,
        },
      ]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "RAG 채팅에 실패했습니다.");
    }
  }

  async function checkGuard() {
    setError(null);
    try {
      const result = await fetchJson<AnyRecord>("/api/guard/check", {
        method: "POST",
        body: JSON.stringify({ draft_answer: draft, evidence_bundle: graphResult }),
      });
      setGuard(result);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "검증에 실패했습니다.");
    }
  }

  async function rebalanceNeuro() {
    setError(null);
    try {
      const plan = await fetchJson<AnyRecord>("/api/neuro/plan", {
        method: "POST",
        body: JSON.stringify({
          text: `${chatInput}\n${draft}`,
          task_type: "alpha-console",
          target_device: "low-spec-cpu-gpu",
          module_budget: 4,
        }),
      });
      setNeuro(plan);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "효율 계획 계산에 실패했습니다.");
    }
  }

  const graphResult = graphrag?.result ?? null;
  const losses = oven?.losses ?? oven?.result?.losses ?? [];
  const memoryNodes = useMemo(() => makeMemoryNodes(graph), [graph]);
  const memoryEdges = useMemo(() => makeMemoryEdges(graph, memoryNodes), [graph, memoryNodes]);
  const memoryMap = useMemo(() => new Map(memoryNodes.map((node) => [node.id, node])), [memoryNodes]);
  const energyReduction = asPercent(neuro?.energy_estimate?.reduction_ratio);
  const eventSparsity = asPercent(neuro?.event_gate?.sparsity);
  const flowHealth = useMemo(() => {
    const complete = pipeline?.stages.filter((stage) => stage.state === "complete").length ?? 0;
    return Math.round((complete / 7) * 100);
  }, [pipeline]);

  const processSteps = [
    {
      number: "01",
      title: "DataGate 정제",
      api: "POST /api/datagate/run",
      state: datagate?.state ?? "idle",
      description: "원천 문서를 통과/거절로 나누고 RAG에 들어갈 깨끗한 입력만 남깁니다.",
      metrics: [`${datagate?.accepted ?? 0}/${datagate?.total ?? 0} 통과`, `${percent(datagate?.accepted ?? 0, datagate?.total ?? 0)}% 통과율`],
      action: () => runAction(() => fetchJson("/api/datagate/run", { method: "POST", body: JSON.stringify({ input_dir: "data/raw" }) })),
      actionLabel: "정제 실행",
    },
    {
      number: "02",
      title: "온톨로지 메모리 생성",
      api: "POST /api/ontology/run",
      state: ontology?.state ?? "idle",
      description: "정제된 문서에서 개념과 관계를 추출해 왼쪽 메모리 그래프를 구성합니다.",
      metrics: [`${ontology?.node_count ?? memoryNodes.length} 노드`, `${ontology?.edge_count ?? memoryEdges.length} 엣지`],
      action: () => runAction(() => fetchJson("/api/ontology/run", { method: "POST" })),
      actionLabel: "메모리 생성",
    },
    {
      number: "03",
      title: "GraphRAG 검색",
      api: "POST /api/graphrag/query",
      state: graphrag?.state ?? "idle",
      description: "질문을 온톨로지 메모리와 문서 근거에 연결합니다. 이 단계가 실제 RAG 작업대입니다.",
      metrics: [`신뢰도 ${Math.round((graphrag?.confidence ?? 0) * 100)}%`, `${graphResult?.evidence_docs?.length ?? 0} 근거`],
      action: () => {
        setRightMode("chat");
        return sendChat();
      },
      actionLabel: "RAG 채팅 열기",
    },
    {
      number: "04",
      title: "Guardrail 검증",
      api: "POST /api/guard/check",
      state: guard?.state ?? "idle",
      description: "RAG 근거와 답변 초안을 대조해 과장 표현과 미지원 주장을 표시합니다.",
      metrics: [`${guard?.overall_guard_score ?? 0}점`, `${guard?.result?.claims?.length ?? 0} 주장`],
      action: checkGuard,
      actionLabel: "초안 검증",
    },
    {
      number: "05",
      title: "학습 dry-run",
      api: "POST /api/oven/dry-run",
      state: oven?.state ?? "idle",
      description: "학습 파이프라인을 짧게 실행하고 완료되면 오른쪽 패널을 RAG 채팅 UI로 전환합니다.",
      metrics: [`loss ${oven?.last_loss ?? "대기"}`, `${losses.length} step`],
      action: runTrainingDryRun,
      actionLabel: "학습 실행",
    },
    {
      number: "06",
      title: "저전력 효율 계획",
      api: "POST /api/neuro/plan",
      state: "completed",
      description: "이벤트 희소성, 모듈 라우팅, 압축 설정을 재계산해 저사양 실행 가능성을 봅니다.",
      metrics: [`${energyReduction}% 절감`, `${eventSparsity}% 희소성`],
      action: rebalanceNeuro,
      actionLabel: "효율 재계산",
    },
  ];

  const logs = [
    { time: fmtClock(), message: `메모리 그래프 로드: ${memoryNodes.length} nodes / ${memoryEdges.length} edges` },
    { time: fmtClock(), message: `RAG 상태: ${statusText(graphrag?.state)} / confidence ${Math.round((graphrag?.confidence ?? 0) * 100)}%` },
    { time: fmtClock(), message: `학습 상태: ${statusText(oven?.state)} / last loss ${oven?.last_loss ?? "none"}` },
    { time: fmtClock(), message: `효율 계획: estimated compute reduction ${energyReduction}%` },
  ];

  const leftStyle =
    layoutMode === "graph"
      ? { width: "100%", opacity: 1, transform: "translateX(0)" }
      : layoutMode === "workbench"
        ? { width: "0%", opacity: 0, transform: "translateX(-18px)" }
        : { width: "52%", opacity: 1, transform: "translateX(0)" };
  const rightStyle =
    layoutMode === "workbench"
      ? { width: "100%", opacity: 1, transform: "translateX(0)" }
      : layoutMode === "graph"
        ? { width: "0%", opacity: 0, transform: "translateX(18px)" }
        : { width: "48%", opacity: 1, transform: "translateX(0)" };

  return (
    <main className="console-shell">
      <header className="console-header">
        <div className="brand-block">
          <span className="back-button">←</span>
          <strong>Homage</strong>
        </div>
        <div className="layout-switcher" aria-label="레이아웃 전환">
          {[
            ["graph", "그래프"],
            ["split", "분할"],
            ["workbench", "워크벤치"],
          ].map(([mode, label]) => (
            <button key={mode} data-active={layoutMode === mode} onClick={() => setLayoutMode(mode as LayoutMode)}>
              {label}
            </button>
          ))}
        </div>
        <div className="header-status">
          <span>Step 5/6</span>
          <strong>{rightMode === "chat" ? "RAG Chat" : "Learning Process"}</strong>
          <StatusDot state={pipeline?.system_state === "mock" ? "running" : "completed"} />
        </div>
      </header>

      {error ? <p className="error-banner">작업 실패: {error}</p> : null}

      <section className="console-content">
        <aside className="panel-wrap left" style={leftStyle}>
          <section className="memory-panel">
            <div className="memory-header">
              <div>
                <h1>Ontology Memory</h1>
                <p>RAG가 참조하는 개념 기억망</p>
              </div>
              <div className="memory-tools">
                <span>{memoryNodes.length} nodes</span>
                <span>{memoryEdges.length} edges</span>
                <button onClick={() => runAction(refreshAll)}>Refresh</button>
                <button onClick={() => setLayoutMode(layoutMode === "graph" ? "split" : "graph")}>확대</button>
              </div>
            </div>
            <div className="memory-canvas">
              <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="온톨로지 메모리 그래프">
                <defs>
                  <pattern id="memory-grid" width="6" height="6" patternUnits="userSpaceOnUse">
                    <path d="M 6 0 L 0 0 0 6" fill="none" stroke="rgba(150,160,155,0.16)" strokeWidth="0.25" />
                  </pattern>
                </defs>
                <rect width="100" height="100" fill="url(#memory-grid)" />
                {memoryEdges.map((edge) => {
                  const source = memoryMap.get(edge.source);
                  const target = memoryMap.get(edge.target);
                  if (!source || !target) return null;
                  return (
                    <g key={edge.id} onClick={() => setSelectedMemory(edge)}>
                      <line x1={source.x} y1={source.y} x2={target.x} y2={target.y} className="memory-edge" />
                      <text x={(source.x + target.x) / 2} y={(source.y + target.y) / 2} className="memory-edge-label">
                        {edge.relation}
                      </text>
                    </g>
                  );
                })}
                {memoryNodes.map((node) => (
                  <g key={node.id} className="memory-node" onClick={() => setSelectedMemory(node)}>
                    <circle cx={node.x} cy={node.y} r="2.3" fill={node.color} />
                    <text x={node.x + 2.8} y={node.y + 1.1}>{node.label.slice(0, 14)}</text>
                  </g>
                ))}
              </svg>
              <div className="memory-legend">
                {memoryNodes.slice(0, 8).map((node) => (
                  <span key={node.id}><i style={{ background: node.color }} />{node.type}</span>
                ))}
              </div>
              {selectedMemory ? (
                <div className="memory-detail">
                  <button onClick={() => setSelectedMemory(null)}>×</button>
                  <span>{selectedMemory.relation ? "Relationship" : "Memory Node"}</span>
                  <strong>{selectedMemory.label ?? selectedMemory.relation}</strong>
                  <p>{selectedMemory.type ?? `${selectedMemory.source} → ${selectedMemory.target}`}</p>
                </div>
              ) : null}
            </div>
          </section>
        </aside>

        <section className="panel-wrap right" style={rightStyle}>
          <div className="right-panel">
            <div className="right-toolbar">
              <div className="mode-tabs">
                <button data-active={rightMode === "process"} onClick={() => setRightMode("process")}>학습 과정</button>
                <button data-active={rightMode === "chat"} onClick={() => setRightMode("chat")}>RAG 채팅</button>
              </div>
              <div className="mini-metrics">
                <span>Flow {flowHealth}%</span>
                <span>GPU {gpu?.utilization ?? 0}%</span>
                <span>CPU {system?.cpu_count ?? "n/a"}</span>
              </div>
            </div>

            {rightMode === "process" ? (
              <div className="process-view">
                {processSteps.map((step) => (
                  <article className="process-card" data-state={step.state} key={step.number}>
                    <div className="process-head">
                      <span className="process-num">{step.number}</span>
                      <div>
                        <h2>{step.title}</h2>
                        <small>{step.api}</small>
                      </div>
                      <span className="process-state">{statusText(step.state)}</span>
                    </div>
                    <p>{step.description}</p>
                    <div className="process-metrics">
                      {step.metrics.map((metric) => <span key={metric}>{metric}</span>)}
                    </div>
                    <button className="inline-action" onClick={step.action}>{step.actionLabel}</button>
                    {step.title.includes("학습") ? <LossChart losses={losses} /> : null}
                  </article>
                ))}
              </div>
            ) : (
              <div className="chat-view">
                <div className="chat-status-row">
                  <div><span>RAG 신뢰도</span><strong>{Math.round((graphrag?.confidence ?? 0) * 100)}%</strong></div>
                  <div><span>근거 문서</span><strong>{graphResult?.evidence_docs?.length ?? 0}</strong></div>
                  <div><span>Guard score</span><strong>{guard?.overall_guard_score ?? 0}</strong></div>
                </div>
                <div className="chat-scroll">
                  {chatMessages.map((message, index) => (
                    <article className="message" data-role={message.role} key={`${message.role}-${index}`}>
                      <span>{message.role === "user" ? "User" : "Homage RAG"}</span>
                      <p>{message.text}</p>
                      {message.evidence?.length ? (
                        <div className="message-evidence">
                          {message.evidence.slice(0, 3).map((doc) => (
                            <div key={doc.chunk_id ?? doc.doc_id}>
                              <strong>{doc.chunk_id ?? doc.doc_id}</strong>
                              <em>
                                score {doc.score ?? "-"}
                                {doc.retrieval_signals ? ` / lexical ${doc.retrieval_signals.lexical} / graph ${doc.retrieval_signals.graph_boost}` : ""}
                              </em>
                              <small>{doc.snippet}</small>
                            </div>
                          ))}
                        </div>
                      ) : null}
                    </article>
                  ))}
                </div>
                <div className="draft-checker">
                  <textarea value={draft} onChange={(event) => setDraft(event.target.value)} aria-label="검증할 답변 초안" />
                  <button onClick={checkGuard}>Guardrail 검증</button>
                </div>
                <div className="chat-composer">
                  <textarea value={chatInput} onChange={(event) => setChatInput(event.target.value)} aria-label="RAG 질문 입력" />
                  <button onClick={sendChat}>질문 보내기</button>
                </div>
              </div>
            )}
          </div>
        </section>
      </section>

      <section className="system-log">
        <div className="log-head">
          <span>SYSTEM DASHBOARD</span>
          <span>{pipeline?.generated_at ? new Date(pipeline.generated_at).toLocaleString("ko-KR") : "waiting"}</span>
        </div>
        {logs.map((log, index) => (
          <p key={`${log.message}-${index}`}><span>{log.time}</span>{log.message}</p>
        ))}
      </section>
    </main>
  );
}
