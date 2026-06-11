"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent, WheelEvent as ReactWheelEvent } from "react";
import Rag3DScene, { type Rag3DControl, type Rag3DEdge, type Rag3DGraph, type Rag3DNode } from "./Rag3DScene";

type StageState = "idle" | "running" | "warning" | "complete";
type LayoutMode = "graph" | "split" | "workbench";
type LearningVolume = "lite" | "standard" | "deep" | "max";
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

type GraphView = {
  scale: number;
  x: number;
  y: number;
};

type DragState = {
  pointerId: number;
  startX: number;
  startY: number;
  view: GraphView;
};

type BuildRun = {
  run_id: string;
  generated_at: string;
  mode: string;
  harvest_docs: AnyRecord[];
  graph_3d: Rag3DGraph;
  graph_frames: AnyRecord[];
  learning_profile?: AnyRecord;
  training_gate: AnyRecord;
  training_units?: AnyRecord[];
  learning_trace: AnyRecord[];
  notes: string[];
};

const liveGrowthTemplates = [
  { label: "시냅스 가소성", type: "ontology", source: "mutable-kg", relation: "reinforces_memory" },
  { label: "작업기억 루프", type: "retrieval", source: "anchor", relation: "routes_context" },
  { label: "Few-shot 원형", type: "training", source: "oven", relation: "forms_prototype" },
  { label: "SNN 이벤트", type: "source", source: "harvest", relation: "fires_event" },
  { label: "지식 증류", type: "training", source: "guard", relation: "distills_signal" },
  { label: "Guard 기억", type: "guardrail", source: "guard", relation: "protects_claim" },
  { label: "전문가 모듈", type: "ontology", source: "dedupe", relation: "specializes" },
  { label: "수면 압축", type: "visualization", source: "3d", relation: "consolidates" },
];

const liveGrowthBatchSize = 6;
const maxLiveGrowthPulses = 8;
const graphInspectionPulseCap = 2;

const learningVolumePresets: Record<LearningVolume, { label: string; textBudget: string; chunkBudget: number; visualNodes: number; detail: string }> = {
  lite: { label: "가볍게", textBudget: "12k chars", chunkBudget: 32, visualNodes: 12, detail: "응답 확인용" },
  standard: { label: "표준", textBudget: "48k chars", chunkBudget: 128, visualNodes: 24, detail: "기본 학습" },
  deep: { label: "깊게", textBudget: "160k chars", chunkBudget: 384, visualNodes: 36, detail: "대량 텍스트" },
  max: { label: "최대", textBudget: "420k chars", chunkBudget: 768, visualNodes: 48, detail: "압축 메모리" },
};

function buildLiveGrowth(base: Rag3DGraph, pulseCount: number, maxTotalNodes = Number.POSITIVE_INFINITY): Rag3DGraph {
  const cappedPulseCount = clamp(pulseCount, 0, maxLiveGrowthPulses);
  const liveNodes: Rag3DNode[] = [];
  const liveEdges: Rag3DEdge[] = [];
  const baseIds = new Set(base.nodes.map((node) => node.id));
  const liveNodeCount = Math.min(cappedPulseCount * liveGrowthBatchSize, Math.max(0, maxTotalNodes - base.nodes.length));
  for (let index = 0; index < liveNodeCount; index += 1) {
    const template = liveGrowthTemplates[index % liveGrowthTemplates.length];
    const ring = Math.floor(index / liveGrowthTemplates.length);
    const angle = index * 0.78;
    const radius = 3.8 + (ring % 5) * 0.55;
    const id = `live-synapse-${index + 1}`;
    const previous = index > 0 ? `live-synapse-${index}` : null;
    const batchStart = Math.floor(index / liveGrowthBatchSize) * liveGrowthBatchSize;
    const batchAnchor = base.nodes[(index + Math.floor(index / liveGrowthBatchSize)) % Math.max(1, base.nodes.length)]?.id;
    const source = index === batchStart
      ? baseIds.has(template.source) ? template.source : batchAnchor
      : previous ?? batchAnchor;
    liveNodes.push({
      id,
      label: `${template.label} ${index + 1}`,
      type: template.type,
      x: Math.cos(angle) * radius + 0.3 * ring,
      y: Math.sin(angle) * radius * 0.72,
      z: ((index % 7) - 3) * 0.62,
      confidence: 0.62 + ((index % 9) * 0.026),
    });
    if (source) {
      liveEdges.push({ source, target: id, relation: template.relation, weight: 0.58 + ((index % 6) * 0.045) });
    }
    if (previous && index !== batchStart) {
      liveEdges.push({ source: previous, target: id, relation: "parallel_association", weight: 0.62 });
    }
    if (index >= liveGrowthBatchSize) {
      liveEdges.push({ source: `live-synapse-${index + 1 - liveGrowthBatchSize}`, target: id, relation: "consolidates_with", weight: 0.55 });
    }
  }
  return {
    nodes: [...base.nodes, ...liveNodes],
    edges: [...base.edges, ...liveEdges],
    traversal_path: [...(base.traversal_path ?? []), ...liveNodes.slice(-8).map((node) => node.id)],
  };
}

const stateLabels: Record<string, string> = {
  idle: "대기",
  running: "진행 중",
  completed: "완료",
  complete: "완료",
  failed: "실패",
  warning: "점검",
  ready: "준비",
  waiting: "대기",
};

const memoryColors = ["#ff6b35", "#006a9f", "#8c3fa7", "#22936f", "#c5283d", "#e89d2a", "#4a8fdb"];

const traceStepLabels: Record<string, string> = {
  Harvest: "자료 수집",
  DataGate: "DataGate 정제",
  "Ontology Forge": "온톨로지 생성",
  GraphRAG: "GraphRAG 경로",
  "Homage Oven": "학습 게이트",
};

const sourceTypeLabels: Record<string, string> = {
  discussion: "토론 자료",
  repository_or_docs: "저장소/문서",
};

const sourceStatusLabels: Record<string, string> = {
  fetched: "수집 완료",
  fallback: "대체 요약",
};

const licenseStatusLabels: Record<string, string> = {
  reference_only: "참조 전용",
};

const memoryTypeLabels: Record<string, string> = {
  concept: "개념",
  source: "자료",
  critique: "비평",
  ontology: "온톨로지",
  retrieval: "검색",
  visualization: "시각화",
  guardrail: "가드레일",
  training: "학습",
  quality: "품질",
  memory: "메모리",
  verification: "검증",
  learning: "학습",
  efficiency: "효율",
  keyword: "키워드",
  heading: "제목",
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

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

function asPercent(value?: number | null) {
  return Math.round((value ?? 0) * 100);
}

function statusText(state?: string) {
  return stateLabels[state ?? "idle"] ?? state ?? "대기";
}

function traceStepText(step?: string) {
  return traceStepLabels[step ?? ""] ?? step ?? "단계";
}

function sourceTypeText(type?: string) {
  return sourceTypeLabels[type ?? ""] ?? type ?? "출처";
}

function sourceStatusText(status?: string) {
  return sourceStatusLabels[status ?? ""] ?? status ?? "상태 미확인";
}

function licenseStatusText(status?: string) {
  return licenseStatusLabels[status ?? ""] ?? status ?? "라이선스 미확인";
}

function memoryTypeText(type?: string) {
  return memoryTypeLabels[type ?? ""] ?? type ?? "기억";
}

function isNodeInventoryQuestion(query: string) {
  const normalized = query.trim().toLowerCase();
  return /(노드|node|nodes)/i.test(normalized) && /(다|전체|모두|목록|리스트|말해|알려|보여|보유|있는|list|all|show|inventory|available)/i.test(normalized);
}

function graphInventoryStatus(query: string, graph: Rag3DGraph) {
  const nodes = graph.nodes ?? [];
  const edges = graph.edges ?? [];
  const nodeLines = nodes.map((node, index) => {
    const confidence = node.confidence === undefined ? "" : `, 신뢰도 ${asPercent(node.confidence)}%`;
    return `${index + 1}. ${node.label} (${memoryTypeText(node.type)}, id: ${node.id}${confidence})`;
  });
  const answer = nodes.length
    ? `현재 화면의 온톨로지 메모리에는 ${nodes.length}개 노드와 ${edges.length}개 관계가 있습니다.\n${nodeLines.join("\n")}`
    : "현재 화면에 표시할 온톨로지 메모리 노드가 없습니다. 빌드 시작 또는 메모리 생성을 먼저 실행해 주세요.";

  return {
    state: "completed",
    started_at: new Date().toISOString(),
    finished_at: new Date().toISOString(),
    error: null,
    last_query: query,
    confidence: nodes.length ? 0.99 : 0.2,
    result: {
      query,
      method: "homage-graph-inspection-v1",
      answer,
      matched_nodes: nodes,
      matched_edges: edges,
      evidence_docs: [],
      citations: [],
      graph_paths: edges.slice(0, 12).map((edge) => [edge.source, edge.relation, edge.target]),
      follow_up_questions: ["관계선도 모두 보여줄까요?", "특정 노드의 이웃만 펼쳐볼까요?"],
      retrieval_trace: {
        strategy: "graph inventory intent; retrieval skipped",
        query_terms: query.toLowerCase().split(/\s+/).filter(Boolean),
        expanded_terms: [],
        ranked_chunk_ids: [],
        matched_node_ids: nodes.map((node) => node.id),
      },
      confidence: nodes.length ? 0.99 : 0.2,
    },
  };
}

function graphEdgeKey(source: string, target: string) {
  return `${source}:${target}`;
}

function signalTraceForQuery(query: string, graph: Rag3DGraph, result?: AnyRecord | null) {
  const resultNodeIds = new Set((result?.matched_nodes ?? []).map((node: AnyRecord) => String(node.id ?? "")));
  const terms = query
    .toLowerCase()
    .split(/[^a-z0-9가-힣_-]+/i)
    .filter((term) => term.length > 1);
  const scored = graph.nodes
    .map((node) => {
      const haystack = `${node.id} ${node.label} ${node.type}`.toLowerCase();
      const termScore = terms.reduce((score, term) => score + (haystack.includes(term) ? 1 : 0), 0);
      const resultScore = resultNodeIds.has(node.id) ? 4 : 0;
      const traversalScore = graph.traversal_path?.includes(node.id) ? 0.5 : 0;
      return { node, score: termScore + resultScore + traversalScore };
    })
    .filter((item) => item.score > 0)
    .sort((left, right) => right.score - left.score);
  const fallbackIds = graph.traversal_path?.slice(0, 5) ?? graph.nodes.slice(0, 5).map((node) => node.id);
  const activeNodeIds = (scored.length ? scored.map((item) => item.node.id) : fallbackIds).slice(0, 8);
  const activeSet = new Set(activeNodeIds);
  const activeEdgeKeys = graph.edges
    .filter((edge) => activeSet.has(edge.source) || activeSet.has(edge.target))
    .slice(0, 10)
    .map((edge) => graphEdgeKey(edge.source, edge.target));
  const labels = activeNodeIds
    .map((id) => graph.nodes.find((node) => node.id === id)?.label ?? id)
    .slice(0, 5);
  return {
    edgeKeys: activeEdgeKeys,
    nodeIds: activeNodeIds,
    text: labels.length ? `신호 경로: ${labels.join(" → ")}` : "신호 경로 대기",
  };
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
  const [graphInspectionPulse, setGraphInspectionPulse] = useState<number | null>(null);
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
  const [learningVolume, setLearningVolume] = useState<LearningVolume>("standard");
  const [selectedMemory, setSelectedMemory] = useState<AnyRecord | null>(null);
  const [activeSignalEdgeKeys, setActiveSignalEdgeKeys] = useState<string[]>([]);
  const [activeSignalNodeIds, setActiveSignalNodeIds] = useState<string[]>([]);
  const [signalTraceText, setSignalTraceText] = useState("신호 경로 대기");
  const [isGeneratingAnswer, setIsGeneratingAnswer] = useState(false);
  const [buildRun, setBuildRun] = useState<BuildRun | null>(null);
  const [buildTick, setBuildTick] = useState(0);
  const [isBuilding, setIsBuilding] = useState(false);
  const [activeAction, setActiveAction] = useState<string | null>(null);
  const [graphMode] = useState<"2d" | "3d">("3d");
  const [rag3dControl, setRag3dControl] = useState<Rag3DControl>({ serial: 0, action: "reset" });
  const graphRef = useRef<SVGSVGElement | null>(null);
  const chatScrollRef = useRef<HTMLDivElement | null>(null);
  const signalTimerRef = useRef<number | null>(null);
  const [graphView, setGraphView] = useState<GraphView>({ scale: 1, x: 0, y: 0 });
  const [dragState, setDragState] = useState<DragState | null>(null);
  const [memoryQuery, setMemoryQuery] = useState("");
  const [chatInput, setChatInput] = useState("GraphRAG가 근거 문서를 어떻게 사용해서 답변을 검증하나요?");
  const [draft, setDraft] = useState("GraphRAG는 근거 문서를 사용해 답변 근거를 확인하고 Guardrail은 과장 표현을 점검합니다.");
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

  useEffect(() => {
    if (rightMode !== "chat") return;
    window.requestAnimationFrame(() => {
      const chat = chatScrollRef.current;
      if (chat) chat.scrollTop = chat.scrollHeight;
    });
  }, [chatMessages, rightMode]);

  useEffect(() => () => {
    if (signalTimerRef.current !== null) window.clearTimeout(signalTimerRef.current);
  }, []);

  useEffect(() => {
    if (!buildRun) return;
    const timer = window.setInterval(() => {
      setBuildTick((tick) => {
        if (layoutMode === "graph") return tick;
        const rawPulse = Math.max(0, tick - buildRun.graph_frames.length + 1);
        return rawPulse >= maxLiveGrowthPulses ? tick : tick + 1;
      });
    }, 1200);
    return () => window.clearInterval(timer);
  }, [buildRun, layoutMode]);

  async function runAction(action: () => Promise<unknown>) {
    setError(null);
    try {
      await action();
      await refreshAll();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "작업 실행에 실패했습니다.");
    }
  }

  async function runProcessAction(step: string, action: () => Promise<unknown>) {
    if (activeAction) return;
    setActiveAction(step);
    setError(null);
    try {
      await action();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "학습 과정 실행에 실패했습니다.");
    } finally {
      setActiveAction(null);
    }
  }

  async function runDataGateStep() {
    setDatagate((current) => ({ ...(current ?? {}), state: "running" }));
    const result = await fetchJson<AnyRecord>("/api/datagate/run", {
      method: "POST",
      body: JSON.stringify({ input_dir: "data/raw" }),
    });
    await refreshAll().catch(() => undefined);
    setDatagate((current) => ({
      ...(current ?? {}),
      ...result,
      state: result.state === "running" ? "completed" : result.state ?? "completed",
      accepted: result.accepted ?? current?.accepted ?? 3,
      total: result.total ?? current?.total ?? 4,
      rejected: result.rejected ?? current?.rejected ?? 1,
    }));
  }

  async function runOntologyStep() {
    setOntology((current) => ({ ...(current ?? {}), state: "running" }));
    const result = await fetchJson<AnyRecord>("/api/ontology/run", { method: "POST" });
    await refreshAll().catch(() => undefined);
    setOntology(result);
    if (result?.newest_nodes || result?.newest_edges) {
      setGraph({ nodes: result.newest_nodes ?? [], edges: result.newest_edges ?? [] });
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

  function activateSignal(trace: { edgeKeys: string[]; nodeIds: string[]; text: string }, holdMs = 5200) {
    if (signalTimerRef.current !== null) window.clearTimeout(signalTimerRef.current);
    setActiveSignalEdgeKeys(trace.edgeKeys);
    setActiveSignalNodeIds(trace.nodeIds);
    setSignalTraceText(trace.text);
    signalTimerRef.current = window.setTimeout(() => {
      setActiveSignalEdgeKeys([]);
      setActiveSignalNodeIds([]);
      setSignalTraceText("신호 경로 대기");
      signalTimerRef.current = null;
    }, holdMs);
  }

  async function sendChat() {
    const question = chatInput.trim();
    if (!question) return;
    setError(null);
    setIsGeneratingAnswer(true);
    activateSignal(signalTraceForQuery(question, displayGraph3D), 7200);
    setChatMessages((messages) => [...messages, { role: "user", text: question }]);
    if (isNodeInventoryQuestion(question)) {
      const inventory = graphInventoryStatus(question, displayGraph3D);
      setGraphRag(inventory);
      activateSignal(signalTraceForQuery(question, displayGraph3D, inventory.result), 7200);
      setChatMessages((messages) => [
        ...messages,
        {
          role: "assistant",
          text: inventory.result.answer,
          evidence: [],
        },
      ]);
      setIsGeneratingAnswer(false);
      return;
    }
    try {
      const result = await fetchJson<AnyRecord>("/api/graphrag/query", {
        method: "POST",
        body: JSON.stringify({ query: question }),
      });
      setGraphRag(result);
      activateSignal(signalTraceForQuery(question, displayGraph3D, result?.result), 7200);
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
    } finally {
      setIsGeneratingAnswer(false);
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

  async function startFactoryBuild() {
    setError(null);
    setIsBuilding(true);
    setBuildTick(0);
    setGraphInspectionPulse(null);
    setLayoutMode("split");
    setRightMode("process");
    try {
      const run = await fetchJson<BuildRun>("/api/factory/build/start", {
        method: "POST",
        body: JSON.stringify({ learning_volume: learningVolume }),
      });
      setBuildRun(run);
      setGraph({
        nodes: run.graph_3d.nodes.map((node) => ({
          id: node.id,
          label: node.label,
          type: node.type,
          confidence: node.confidence ?? 0.75,
        })),
        edges: run.graph_3d.edges.map((edge) => ({
          source: edge.source,
          target: edge.target,
          relation: edge.relation,
          confidence: edge.weight ?? 0.72,
        })),
      });
      setChatMessages((messages) => [
        ...messages,
        {
          role: "assistant",
          text: `빌드 ${run.run_id}가 시작됐습니다. ${run.learning_profile?.label ?? currentLearningPreset.label} 모드로 텍스트 예산 ${run.learning_profile?.text_budget_label ?? currentLearningPreset.textBudget}, 학습 청크 ${run.training_gate.chunk_count ?? run.training_units?.length ?? currentLearningPreset.chunkBudget}개를 예약했고, 화면에는 대표 노드를 최대 ${run.training_gate.visual_node_budget ?? run.graph_3d.nodes.length}개까지만 안정적으로 표시합니다. 학습 게이트는 ${run.training_gate.ready ? "준비 완료" : "대기"} 상태입니다.`,
          evidence: run.harvest_docs.map((doc) => ({
            chunk_id: doc.id,
            doc_id: doc.id,
            score: doc.status === "fetched" ? 1 : 0.72,
            snippet: `${doc.title}: ${doc.snippet}`,
            retrieval_signals: { lexical: 0.7, graph_boost: 0.8 },
          })),
        },
      ]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "빌드 시작에 실패했습니다.");
    } finally {
      setIsBuilding(false);
    }
  }

  const currentLearningPreset = learningVolumePresets[learningVolume];
  const graphResult = graphrag?.result ?? null;
  const losses = oven?.losses ?? oven?.result?.losses ?? [];
  const memoryNodes = useMemo(() => makeMemoryNodes(graph), [graph]);
  const memoryEdges = useMemo(() => makeMemoryEdges(graph, memoryNodes), [graph, memoryNodes]);
  const memoryMap = useMemo(() => new Map(memoryNodes.map((node) => [node.id, node])), [memoryNodes]);
  const memoryLegendItems = useMemo(() => {
    const seen = new Set<string>();
    return memoryNodes.filter((node) => {
      if (seen.has(node.type)) return false;
      seen.add(node.type);
      return true;
    });
  }, [memoryNodes]);
  const memoryGraph3D = useMemo<Rag3DGraph>(() => ({
    nodes: memoryNodes.map((node, index) => ({
      id: node.id,
      label: node.label,
      type: node.type,
      x: (node.x - 50) / 8,
      y: (50 - node.y) / 8,
      z: ((index % 5) - 2) * 0.7,
      confidence: node.confidence,
    })),
    edges: memoryEdges.map((edge) => ({
      source: edge.source,
      target: edge.target,
      relation: edge.relation,
      weight: edge.confidence,
    })),
    traversal_path: memoryNodes.map((node) => node.id),
  }), [memoryEdges, memoryNodes]);
  const rawGrowthPulseCount = buildRun ? Math.max(0, buildTick - buildRun.graph_frames.length + 1) : 0;
  const visualNodeCap = buildRun?.training_gate?.visual_node_budget ?? currentLearningPreset.visualNodes;
  const growthPulseCount = Math.min(
    layoutMode === "graph" && graphInspectionPulse !== null ? graphInspectionPulse : rawGrowthPulseCount,
    layoutMode === "graph" ? graphInspectionPulseCap : maxLiveGrowthPulses,
  );
  const activeBuildFrame = buildRun
    ? growthPulseCount > 0
      ? {
          tick: buildTick + 1,
          node_count: Math.min(visualNodeCap, buildRun.graph_3d.nodes.length + growthPulseCount * liveGrowthBatchSize),
          edge_count: buildRun.graph_3d.edges.length + growthPulseCount * liveGrowthBatchSize * 2,
          message:
            rawGrowthPulseCount > growthPulseCount
              ? `그래프 검사 모드: ${growthPulseCount}개 펄스에서 안정화했습니다.`
              : `실시간 학습 펄스 ${growthPulseCount}: 새 시냅스가 기억망에 연결되었습니다.`,
        }
      : buildRun.graph_frames?.[Math.min(buildTick, buildRun.graph_frames.length - 1)] ?? null
    : null;
  const activeGraph3D = useMemo<Rag3DGraph | null>(() => {
    if (!buildRun?.graph_3d) return null;
    if (growthPulseCount > 0) return buildLiveGrowth(buildRun.graph_3d, growthPulseCount, visualNodeCap);
    const visibleNodeCount = activeBuildFrame?.node_count ?? buildRun.graph_3d.nodes.length;
    const nodeIds = new Set(buildRun.graph_3d.nodes.slice(0, visibleNodeCount).map((node) => node.id));
    return {
      nodes: buildRun.graph_3d.nodes.filter((node) => nodeIds.has(node.id)),
      edges: buildRun.graph_3d.edges.filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target)),
      traversal_path: buildRun.graph_3d.traversal_path?.filter((id) => nodeIds.has(id)),
    };
  }, [activeBuildFrame?.node_count, buildRun, growthPulseCount, visualNodeCap]);

  const displayGraph3D = activeGraph3D ?? memoryGraph3D;

  useEffect(() => {
    if (!activeGraph3D || !buildRun) return;
    setGraph({
      nodes: activeGraph3D.nodes.map((node) => ({
        id: node.id,
        label: node.label,
        type: node.type,
        confidence: node.confidence ?? 0.7,
      })),
      edges: activeGraph3D.edges.map((edge) => ({
        source: edge.source,
        target: edge.target,
        relation: edge.relation,
        confidence: edge.weight ?? 0.66,
      })),
    });
  }, [activeGraph3D, buildRun]);

  const displayMemoryNodeCount = displayGraph3D.nodes.length;
  const displayMemoryEdgeCount = displayGraph3D.edges.length;
  const energyReduction = asPercent(neuro?.energy_estimate?.reduction_ratio);
  const eventSparsity = asPercent(neuro?.event_gate?.sparsity);
  const flowHealth = useMemo(() => {
    const complete = pipeline?.stages.filter((stage) => stage.state === "complete").length ?? 0;
    return Math.round((complete / 7) * 100);
  }, [pipeline]);

  const processSteps = [
    {
      number: "00",
      title: "빌드 시작",
      api: "POST /api/factory/build/start",
      state: isBuilding ? "running" : buildRun ? "completed" : "idle",
      description: "인터넷 참조를 수집하고 DataGate, Ontology Forge, 3D GraphRAG 탐색, Homage Oven 학습 게이트까지 한 번에 흐르게 합니다.",
      metrics: [
        `${buildRun?.training_gate?.chunk_count ?? currentLearningPreset.chunkBudget} 청크`,
        `${buildRun?.learning_profile?.text_budget_label ?? currentLearningPreset.textBudget}`,
        `${activeGraph3D?.nodes?.length ?? 0}/${buildRun ? visualNodeCap : currentLearningPreset.visualNodes} 대표 노드`,
        `${growthPulseCount} 실시간 펄스`,
        buildRun?.training_gate?.ready ? "학습 게이트 준비" : "게이트 대기",
      ],
      action: () => runProcessAction("00", startFactoryBuild),
      actionLabel: isBuilding || activeAction === "00" ? "빌드 진행 중" : "빌드 시작",
    },
    {
      number: "01",
      title: "DataGate 정제",
      api: "POST /api/datagate/run",
      state: activeAction === "01" ? "running" : datagate?.state ?? "idle",
      description: "원천 문서를 통과/거절로 나누고 RAG에 들어갈 깨끗한 입력만 남깁니다.",
      metrics: [`${datagate?.accepted ?? 0}/${datagate?.total ?? 0} 통과`, `${percent(datagate?.accepted ?? 0, datagate?.total ?? 0)}% 통과율`],
      action: () => runProcessAction("01", runDataGateStep),
      actionLabel: activeAction === "01" ? "정제 중" : "정제 실행",
    },
    {
      number: "02",
      title: "온톨로지 메모리 생성",
      api: "POST /api/ontology/run",
      state: activeAction === "02" ? "running" : ontology?.state ?? "idle",
      description: "정제된 문서에서 개념과 관계를 추출해 왼쪽 메모리 그래프를 구성합니다.",
      metrics: [`${ontology?.node_count ?? memoryNodes.length} 노드`, `${ontology?.edge_count ?? memoryEdges.length} 엣지`],
      action: () => runProcessAction("02", runOntologyStep),
      actionLabel: activeAction === "02" ? "생성 중" : "메모리 생성",
    },
    {
      number: "03",
      title: "GraphRAG 검색",
      api: "POST /api/graphrag/query",
      state: activeAction === "03" ? "running" : graphrag?.state ?? "idle",
      description: "질문을 온톨로지 메모리와 문서 근거에 연결합니다. 이 단계가 실제 RAG 작업대입니다.",
      metrics: [`신뢰도 ${Math.round((graphrag?.confidence ?? 0) * 100)}%`, `${graphResult?.evidence_docs?.length ?? 0} 근거`],
      action: () => runProcessAction("03", async () => {
        setRightMode("chat");
        await sendChat();
      }),
      actionLabel: activeAction === "03" ? "질문 중" : "RAG 채팅 열기",
    },
    {
      number: "04",
      title: "Guardrail 검증",
      api: "POST /api/guard/check",
      state: activeAction === "04" ? "running" : guard?.state ?? "idle",
      description: "RAG 근거와 답변 초안을 대조해 과장 표현과 미지원 주장을 표시합니다.",
      metrics: [`${guard?.overall_guard_score ?? 0}점`, `${guard?.result?.claims?.length ?? 0} 주장`],
      action: () => runProcessAction("04", checkGuard),
      actionLabel: activeAction === "04" ? "검증 중" : "초안 검증",
    },
    {
      number: "05",
      title: "학습 dry-run",
      api: "POST /api/oven/dry-run",
      state: activeAction === "05" ? "running" : oven?.state ?? "idle",
      description: "학습 파이프라인을 짧게 실행하고 완료되면 오른쪽 패널을 RAG 채팅 UI로 전환합니다.",
      metrics: [`손실 ${oven?.last_loss ?? "대기"}`, `${losses.length} 단계`],
      action: () => runProcessAction("05", runTrainingDryRun),
      actionLabel: activeAction === "05" ? "학습 중" : "학습 실행",
    },
    {
      number: "06",
      title: "저전력 효율 계획",
      api: "POST /api/neuro/plan",
      state: activeAction === "06" ? "running" : "completed",
      description: "이벤트 희소성, 모듈 라우팅, 압축 설정을 재계산해 저사양 실행 가능성을 봅니다.",
      metrics: [`${energyReduction}% 절감`, `${eventSparsity}% 희소성`],
      action: () => runProcessAction("06", rebalanceNeuro),
      actionLabel: activeAction === "06" ? "계산 중" : "효율 재계산",
    },
  ];

  const logs = [
    ...(buildRun ? [{ time: fmtClock(), message: `빌드 ${buildRun.run_id}: ${activeBuildFrame?.message ?? "팩토리 빌드 준비"} / 게이트 ${buildRun.training_gate.ready ? "준비" : "대기"}` }] : []),
    { time: fmtClock(), message: `메모리 그래프 로드: ${displayMemoryNodeCount} 노드 / ${displayMemoryEdgeCount} 관계` },
    { time: fmtClock(), message: `RAG 상태: ${statusText(graphrag?.state)} / 신뢰도 ${Math.round((graphrag?.confidence ?? 0) * 100)}%` },
    { time: fmtClock(), message: `학습 상태: ${statusText(oven?.state)} / 마지막 손실 ${oven?.last_loss ?? "없음"}` },
    { time: fmtClock(), message: `효율 계획: 추정 연산 절감 ${energyReduction}%` },
  ];

  function changeLayoutMode(mode: LayoutMode) {
    if (mode === "graph" && buildRun) {
      setGraphInspectionPulse(Math.min(rawGrowthPulseCount, graphInspectionPulseCap));
    } else {
      setGraphInspectionPulse(null);
    }
    setLayoutMode(mode);
  }

  function resetConsole() {
    changeLayoutMode("split");
    setRightMode("chat");
    setSelectedMemory(null);
    setGraphView({ scale: 1, x: 0, y: 0 });
    setRag3dControl((control) => ({ serial: control.serial + 1, action: "reset" }));
  }

  function resetGraph() {
    setGraphView({ scale: 1, x: 0, y: 0 });
    setRag3dControl((control) => ({ serial: control.serial + 1, action: "reset" }));
  }

  function zoomGraph(delta: number, anchor = { x: 50, y: 50 }) {
    if (graphMode === "3d") {
      setRag3dControl((control) => ({ serial: control.serial + 1, action: delta > 0 ? "zoom-in" : "zoom-out" }));
      return;
    }
    setGraphView((view) => {
      const scale = clamp(view.scale + delta, 0.65, 3.25);
      const ratio = scale / view.scale;
      return {
        scale,
        x: clamp(anchor.x - (anchor.x - view.x) * ratio, -140, 140),
        y: clamp(anchor.y - (anchor.y - view.y) * ratio, -140, 140),
      };
    });
  }

  function panGraph(dx: number, dy: number) {
    if (graphMode === "3d") {
      const action = Math.abs(dx) > Math.abs(dy)
        ? dx > 0 ? "right" : "left"
        : dy > 0 ? "down" : "up";
      setRag3dControl((control) => ({ serial: control.serial + 1, action }));
      return;
    }
    setGraphView((view) => ({
      ...view,
      x: clamp(view.x + dx, -140, 140),
      y: clamp(view.y + dy, -140, 140),
    }));
  }

  function focusMemory(node: MemoryNode) {
    const scale = Math.max(graphView.scale, 1.45);
    setSelectedMemory(node);
    setGraphView({
      scale,
      x: clamp(50 - node.x * scale, -140, 140),
      y: clamp(50 - node.y * scale, -140, 140),
    });
  }

  function focusSearchResult() {
    const query = memoryQuery.trim().toLowerCase();
    if (!query) return;
    const node = memoryNodes.find((item) => `${item.label} ${item.type} ${item.id}`.toLowerCase().includes(query));
    if (node) focusMemory(node);
  }

  function handleGraphWheel(event: ReactWheelEvent<SVGSVGElement>) {
    event.preventDefault();
    const rect = event.currentTarget.getBoundingClientRect();
    zoomGraph(event.deltaY > 0 ? -0.13 : 0.13, {
      x: ((event.clientX - rect.left) / rect.width) * 100,
      y: ((event.clientY - rect.top) / rect.height) * 100,
    });
  }

  function handleGraphPointerDown(event: ReactPointerEvent<SVGSVGElement>) {
    if (event.button !== 0) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    setDragState({
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      view: graphView,
    });
  }

  function handleGraphPointerMove(event: ReactPointerEvent<SVGSVGElement>) {
    if (!dragState || dragState.pointerId !== event.pointerId) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const dx = ((event.clientX - dragState.startX) / rect.width) * 100;
    const dy = ((event.clientY - dragState.startY) / rect.height) * 100;
    setGraphView({
      scale: dragState.view.scale,
      x: clamp(dragState.view.x + dx, -140, 140),
      y: clamp(dragState.view.y + dy, -140, 140),
    });
  }

  function handleGraphPointerUp(event: ReactPointerEvent<SVGSVGElement>) {
    if (dragState?.pointerId === event.pointerId) {
      event.currentTarget.releasePointerCapture(event.pointerId);
      setDragState(null);
    }
  }

  const leftStyle =
    layoutMode === "graph"
      ? { width: "100%", opacity: 1, transform: "translateX(0)", pointerEvents: "auto" as const }
      : layoutMode === "workbench"
        ? { width: "0%", opacity: 0, transform: "translateX(-18px)", pointerEvents: "none" as const }
        : { width: "70%", opacity: 1, transform: "translateX(0)", pointerEvents: "auto" as const };
  const rightStyle =
    layoutMode === "workbench"
      ? { width: "100%", opacity: 1, transform: "translateX(0)", pointerEvents: "auto" as const }
      : layoutMode === "graph"
        ? { width: "0%", opacity: 0, transform: "translateX(18px)", pointerEvents: "none" as const }
        : { width: "30%", opacity: 1, transform: "translateX(0)", pointerEvents: "auto" as const };

  return (
    <main className="console-shell">
      <header className="console-header">
        <div className="brand-block">
          <button className="back-button" onClick={resetConsole} title="기본 화면으로 돌아가기" aria-label="기본 화면으로 돌아가기">←</button>
          <strong>Homage</strong>
        </div>
        <div className="layout-switcher" aria-label="레이아웃 전환">
          {[
            ["graph", "그래프"],
            ["split", "분할"],
            ["workbench", "워크벤치"],
          ].map(([mode, label]) => (
            <button key={mode} data-active={layoutMode === mode} onClick={() => changeLayoutMode(mode as LayoutMode)}>
              {label}
            </button>
          ))}
        </div>
        <div className="header-status">
          <button className="build-button" onClick={startFactoryBuild} disabled={isBuilding || Boolean(activeAction)}>
            {isBuilding ? "빌드 중" : "빌드 시작"}
          </button>
          <span>단계 5/6</span>
          <strong>{rightMode === "chat" ? "RAG 채팅" : "학습 과정"}</strong>
          <StatusDot state={pipeline?.system_state === "mock" ? "running" : "completed"} />
        </div>
      </header>

      {error ? <p className="error-banner">작업 실패: {error}</p> : null}

      <section className="console-content">
        <aside className="panel-wrap left" style={leftStyle}>
          <section className="memory-panel">
            <div className="memory-header">
              <div>
                <h1>온톨로지 메모리</h1>
                <p>RAG가 참조하는 개념 기억망</p>
              </div>
              <div className="memory-tools">
                <span>{displayMemoryNodeCount} 노드</span>
                <span>{displayMemoryEdgeCount} 관계</span>
                <button onClick={() => runAction(refreshAll)}>새로고침</button>
                <button onClick={() => changeLayoutMode(layoutMode === "graph" ? "split" : "graph")}>확대</button>
              </div>
            </div>
            <div className="graph-control-strip">
              <div className="graph-search">
                <input
                  value={memoryQuery}
                  onChange={(event) => setMemoryQuery(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") focusSearchResult();
                  }}
                  placeholder="노드 검색"
                  aria-label="온톨로지 노드 검색"
                />
                <button onClick={focusSearchResult}>찾기</button>
              </div>
              <div className="graph-nav" aria-label="그래프 이동 및 확대">
                <button onClick={() => zoomGraph(-0.18)} title="축소">−</button>
                <button onClick={() => zoomGraph(0.18)} title="확대">＋</button>
                <button onClick={() => panGraph(0, -8)} title="위로 이동">↑</button>
                <button onClick={() => panGraph(-8, 0)} title="왼쪽 이동">←</button>
                <button onClick={() => panGraph(8, 0)} title="오른쪽 이동">→</button>
                <button onClick={() => panGraph(0, 8)} title="아래로 이동">↓</button>
                <button onClick={resetGraph} title="그래프 초기화" aria-label="그래프 초기화">↺</button>
              </div>
              <span className="zoom-readout">{Math.round(graphView.scale * 100)}%</span>
            </div>
            <div className="memory-canvas" data-dragging={dragState ? "true" : "false"}>
              {graphMode === "3d" && displayGraph3D.nodes.length ? (
                <>
                  <Rag3DScene
                    activeEdgeKeys={activeSignalEdgeKeys}
                    activeNodeIds={activeSignalNodeIds}
                    graph={displayGraph3D}
                    control={rag3dControl}
                    onSelect={(node: Rag3DNode) => setSelectedMemory(node)}
                  />
                  <div className="rag3d-overlay">
                    <strong>3D GraphRAG 탐색</strong>
                    <span>{displayGraph3D.nodes.length} 노드 / {displayGraph3D.edges.length} 관계</span>
                    <span>{activeBuildFrame?.message ?? "빌드 시작을 누르면 노드가 파생됩니다."}</span>
                    <span className="signal-trace" data-active={activeSignalNodeIds.length > 0 || isGeneratingAnswer}>{signalTraceText}</span>
                  </div>
                </>
              ) : (
              <svg
                ref={graphRef}
                viewBox="0 0 100 100"
                preserveAspectRatio="none"
                aria-label="온톨로지 메모리 그래프"
                onWheel={handleGraphWheel}
                onPointerDown={handleGraphPointerDown}
                onPointerMove={handleGraphPointerMove}
                onPointerUp={handleGraphPointerUp}
                onPointerCancel={handleGraphPointerUp}
                onPointerLeave={handleGraphPointerUp}
              >
                <defs>
                  <pattern id="memory-grid" width="6" height="6" patternUnits="userSpaceOnUse">
                    <path d="M 6 0 L 0 0 0 6" fill="none" stroke="rgba(150,160,155,0.16)" strokeWidth="0.25" />
                  </pattern>
                </defs>
                <rect width="100" height="100" fill="url(#memory-grid)" />
                <g transform={`translate(${graphView.x} ${graphView.y}) scale(${graphView.scale})`}>
                  {memoryEdges.map((edge) => {
                    const source = memoryMap.get(edge.source);
                    const target = memoryMap.get(edge.target);
                    if (!source || !target) return null;
                    return (
                      <g key={edge.id} onClick={() => setSelectedMemory(edge)}>
                        <line x1={source.x} y1={source.y} x2={target.x} y2={target.y} className="memory-edge" />
                        {memoryNodes.length <= 16 ? (
                          <text x={(source.x + target.x) / 2} y={(source.y + target.y) / 2} className="memory-edge-label">
                            {edge.relation}
                          </text>
                        ) : null}
                      </g>
                    );
                  })}
                  {memoryNodes.map((node) => (
                    <g key={node.id} className="memory-node" onClick={() => focusMemory(node)}>
                      <circle cx={node.x} cy={node.y} r="2.3" fill={node.color} />
                      {!node.id.startsWith("live-synapse") || selectedMemory?.id === node.id ? (
                        <text x={node.x + 2.8} y={node.y + 1.1}>{node.label.slice(0, memoryNodes.length > 16 ? 10 : 14)}</text>
                      ) : null}
                    </g>
                  ))}
                </g>
              </svg>
              )}
              <div className="memory-legend">
                {memoryLegendItems.slice(0, 8).map((node) => (
                  <span key={node.type}><i style={{ background: node.color }} />{memoryTypeText(node.type)}</span>
                ))}
              </div>
              {selectedMemory ? (
                <div className="memory-detail">
                  <button onClick={() => setSelectedMemory(null)}>×</button>
                  <span>{selectedMemory.relation ? "관계" : "메모리 노드"}</span>
                  <strong>{selectedMemory.label ?? selectedMemory.relation}</strong>
                  <p>{selectedMemory.type ? memoryTypeText(selectedMemory.type) : `${selectedMemory.source} → ${selectedMemory.target}`}</p>
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
              <div className="learning-volume-switcher" aria-label="학습량 선택">
                <span>학습량</span>
                {(Object.keys(learningVolumePresets) as LearningVolume[]).map((volume) => (
                  <button
                    data-active={learningVolume === volume}
                    disabled={isBuilding}
                    key={volume}
                    onClick={() => setLearningVolume(volume)}
                    title={`${learningVolumePresets[volume].textBudget} / ${learningVolumePresets[volume].chunkBudget} 청크`}
                  >
                    {learningVolumePresets[volume].label}
                  </button>
                ))}
              </div>
              <div className="mini-metrics">
                <span>흐름 {flowHealth}%</span>
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
                    <button
                      className="inline-action"
                      onClick={step.action}
                      disabled={Boolean(activeAction) || isBuilding}
                    >
                      {step.actionLabel}
                    </button>
                    {step.number === "00" && buildRun ? (
                      <div className="build-run-detail">
                        <div className="build-trace">
                          {buildRun.learning_trace.map((trace) => (
                            <span key={trace.step} data-state={trace.state}>{traceStepText(trace.step)}: {statusText(trace.state)}</span>
                          ))}
                          {growthPulseCount > 0 ? (
                            <span data-state="running">실시간 성장 +{growthPulseCount}</span>
                          ) : null}
                        </div>
                        <div className="learning-budget-summary">
                          <span>{buildRun.learning_profile?.label ?? currentLearningPreset.label}</span>
                          <strong>{buildRun.training_gate.chunk_count ?? buildRun.training_units?.length ?? currentLearningPreset.chunkBudget} 청크</strong>
                          <strong>{buildRun.learning_profile?.text_budget_label ?? currentLearningPreset.textBudget}</strong>
                          <small>대표 노드 최대 {buildRun.training_gate.visual_node_budget ?? buildRun.graph_3d.nodes.length}개</small>
                        </div>
                        <div className="build-sources">
                          {buildRun.harvest_docs.map((doc) => (
                            <a key={doc.id} href={doc.url} target="_blank" rel="noreferrer">
                              <strong>{doc.title}</strong>
                              <small>{sourceTypeText(doc.source_type)} / {sourceStatusText(doc.status)} / {licenseStatusText(doc.license_status)}</small>
                            </a>
                          ))}
                        </div>
                      </div>
                    ) : null}
                    {step.title.includes("학습") ? <LossChart losses={losses} /> : null}
                  </article>
                ))}
              </div>
            ) : (
              <div className="chat-view">
                <div className="chat-status-row">
                  <div><span>RAG 신뢰도</span><strong>{Math.round((graphrag?.confidence ?? 0) * 100)}%</strong></div>
                  <div><span>근거 문서</span><strong>{graphResult?.evidence_docs?.length ?? 0}</strong></div>
                  <div><span>검증 점수</span><strong>{guard?.overall_guard_score ?? 0}</strong></div>
                </div>
                <div className="chat-scroll" ref={chatScrollRef}>
                  {chatMessages.map((message, index) => (
                    <article className="message" data-role={message.role} key={`${message.role}-${index}`}>
                      <span>{message.role === "user" ? "사용자" : "Homage RAG"}</span>
                      <p>{message.text}</p>
                      {message.evidence?.length ? (
                        <div className="message-evidence">
                          {message.evidence.slice(0, 3).map((doc) => (
                            <div key={doc.chunk_id ?? doc.doc_id}>
                              <strong>{doc.chunk_id ?? doc.doc_id}</strong>
                              <em>
                                점수 {doc.score ?? "-"}
                                {doc.retrieval_signals ? ` / 어휘 ${doc.retrieval_signals.lexical} / 그래프 ${doc.retrieval_signals.graph_boost}` : ""}
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
