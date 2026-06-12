"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent, WheelEvent as ReactWheelEvent } from "react";
import Rag3DScene, { type Rag3DControl, type Rag3DEdge, type Rag3DGraph, type Rag3DNode } from "./Rag3DScene";

type StageState = "idle" | "running" | "warning" | "complete";
type LayoutMode = "graph" | "split" | "workbench";
type LearningVolume = "lite" | "standard" | "deep" | "max" | "infinite";
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
  web_search?: AnyRecord;
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
  { label: "추출한다", type: "verb", source: "harvest", relation: "acts_on" },
  { label: "근거 문장", type: "phrase", source: "anchor", relation: "forms_phrase" },
  { label: "공출현 측정", type: "relation", source: "mutable-kg", relation: "co_occurs" },
];

const maxTargetNodes = 500_000;
const liveGrowthBatchSize = 24;
const minLiveGrowthPulses = 8;
const liveSummaryBatchSize = 72;

const learningVolumePresets: Record<LearningVolume, { label: string; textBudget: string; chunkBudget: number; visualNodes: number; targetNodes: number | null; edgeRatio: number; durationHours: number; detail: string }> = {
  lite: { label: "가볍게", textBudget: "12k chars", chunkBudget: 32, visualNodes: 12, targetNodes: 3_000, edgeRatio: 3, durationHours: 12, detail: "응답 확인용" },
  standard: { label: "표준", textBudget: "48k chars", chunkBudget: 128, visualNodes: 24, targetNodes: 10_000, edgeRatio: 4, durationHours: 72, detail: "기본 학습" },
  deep: { label: "깊게", textBudget: "160k chars", chunkBudget: 384, visualNodes: 36, targetNodes: 25_000, edgeRatio: 4, durationHours: 168, detail: "대량 텍스트" },
  max: { label: "최대", textBudget: "4.5m chars", chunkBudget: 4096, visualNodes: 2000, targetNodes: 500_000, edgeRatio: 4.8, durationHours: 168, detail: "압축 메모리" },
  infinite: { label: "∞", textBudget: "continuous", chunkBudget: 4096, visualNodes: 2000, targetNodes: null, edgeRatio: 6, durationHours: 720, detail: "중지 전까지 지속" },
};

function defaultTargetNodesForVolume(volume: LearningVolume) {
  return volume === "max" || volume === "infinite" ? maxTargetNodes : learningVolumePresets[volume].targetNodes ?? 10_000;
}

function buildLiveGrowth(base: Rag3DGraph, pulseCount: number, maxTotalNodes = Number.POSITIVE_INFINITY, rollingWindow = false): Rag3DGraph {
  const liveNodes: Rag3DNode[] = [];
  const liveEdges: Rag3DEdge[] = [];
  const summaryNodes: Rag3DNode[] = [];
  const summaryEdges: Rag3DEdge[] = [];
  const baseIds = new Set(base.nodes.map((node) => node.id));
  const totalLiveNodeCount = Math.max(0, Math.floor(pulseCount)) * liveGrowthBatchSize;
  const maxRenderedNodes = Number.isFinite(maxTotalNodes) ? Math.max(base.nodes.length, Math.floor(maxTotalNodes)) : Number.POSITIVE_INFINITY;
  const preliminarySlots = Math.max(0, Math.floor(maxRenderedNodes - base.nodes.length));
  const preliminaryHidden = rollingWindow ? Math.max(0, totalLiveNodeCount - preliminarySlots) : 0;
  const summaryCount = rollingWindow && preliminaryHidden > 0
    ? Math.min(12, Math.ceil(preliminaryHidden / liveSummaryBatchSize))
    : 0;
  const renderSlots = Math.max(0, Math.floor(maxRenderedNodes - base.nodes.length - summaryCount));
  const startIndex = rollingWindow ? Math.max(0, totalLiveNodeCount - renderSlots) : 0;
  const endIndex = Math.min(totalLiveNodeCount, startIndex + renderSlots);
  if (summaryCount > 0) {
    for (let summaryIndex = 0; summaryIndex < summaryCount; summaryIndex += 1) {
      const rangeStart = summaryIndex * liveSummaryBatchSize + 1;
      const rangeEnd = Math.min(startIndex, (summaryIndex + 1) * liveSummaryBatchSize);
      if (rangeEnd < rangeStart) continue;
      const angle = summaryIndex * 1.7;
      const radius = 5.2 + (summaryIndex % 4) * 0.42;
      const id = `live-summary-${summaryIndex + 1}-${rangeEnd}`;
      const anchor = base.nodes[(summaryIndex * 17) % Math.max(1, base.nodes.length)]?.id;
      summaryNodes.push({
        id,
        label: `요약 ${rangeStart}-${rangeEnd}`,
        type: "summary",
        x: Math.cos(angle) * radius,
        y: Math.sin(angle) * radius * 0.72,
        z: 2.6 + (summaryIndex % 3) * 0.5,
        confidence: 0.58,
      });
      if (anchor) summaryEdges.push({ source: anchor, target: id, relation: "summarizes_hidden_events", weight: 0.5 });
      if (summaryIndex > 0) {
        const previousRangeEnd = Math.min(startIndex, summaryIndex * liveSummaryBatchSize);
        summaryEdges.push({ source: `live-summary-${summaryIndex}-${previousRangeEnd}`, target: id, relation: "continues_history", weight: 0.42 });
      }
    }
  }
  for (let index = startIndex; index < endIndex; index += 1) {
    const template = liveGrowthTemplates[index % liveGrowthTemplates.length];
    const ring = Math.floor(index / liveGrowthTemplates.length);
    const angle = index * 0.78;
    const radius = 3.8 + (ring % 5) * 0.55;
    const id = `live-synapse-${index + 1}`;
    const previous = index > startIndex ? `live-synapse-${index}` : null;
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
    if (index - liveGrowthBatchSize >= startIndex) {
      liveEdges.push({ source: `live-synapse-${index + 1 - liveGrowthBatchSize}`, target: id, relation: "consolidates_with", weight: 0.55 });
    }
  }
  const firstVisible = liveNodes[0]?.id;
  const lastSummary = summaryNodes.at(-1)?.id;
  if (firstVisible && lastSummary) {
    summaryEdges.push({ source: lastSummary, target: firstVisible, relation: "opens_live_frontier", weight: 0.5 });
  }
  return {
    nodes: [...base.nodes, ...summaryNodes, ...liveNodes],
    edges: [...base.edges, ...summaryEdges, ...liveEdges],
    traversal_path: [...(base.traversal_path ?? []), ...summaryNodes.slice(-2).map((node) => node.id), ...liveNodes.slice(-8).map((node) => node.id)],
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

const fallbackMemoryColors = ["#ff6b35", "#006a9f", "#8c3fa7", "#22936f", "#c5283d", "#e89d2a", "#4a8fdb"];

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
  verb: "행위",
  phrase: "구",
  relation: "관계",
};

const memoryTypeColors: Record<string, string> = {
  source: "#ff6b35",
  critique: "#c5283d",
  ontology: "#1a936f",
  retrieval: "#006a9f",
  visualization: "#8c3fa7",
  guardrail: "#e89d2a",
  training: "#111715",
  concept: "#22936f",
  keyword: "#4a8fdb",
  heading: "#7b8794",
  verb: "#f97316",
  phrase: "#7c3aed",
  relation: "#0f766e",
  quality: "#3f6f5f",
  memory: "#1a936f",
  verification: "#e89d2a",
  learning: "#111715",
  efficiency: "#006a9f",
};

const memoryTypeDescriptions: Record<string, string> = {
  source: "외부에서 수집된 원문 자료와 근거 청크입니다.",
  critique: "품질 문제, 반례, 경계 조건처럼 학습을 조심시키는 신호입니다.",
  ontology: "개념 사이의 관계를 묶는 온톨로지 메모리입니다.",
  retrieval: "질문을 근거 문서와 그래프 경로로 연결하는 검색 노드입니다.",
  visualization: "현재 학습 상태를 화면에 투사하는 시각화 노드입니다.",
  guardrail: "답변의 과장, 환각, 근거 부족을 검증하는 안전 노드입니다.",
  training: "Homage Oven으로 넘어가는 학습/압축 신호입니다.",
  concept: "문서에서 추출된 핵심 개념 노드입니다.",
  keyword: "검색과 관계 확장에 쓰이는 키워드 기억입니다.",
  heading: "문서 구조나 섹션 제목에서 온 문맥 앵커입니다.",
  verb: "문장에서 추출된 행위/동작 신호입니다.",
  phrase: "인접한 단어가 함께 만든 짧은 문장 구입니다.",
  relation: "공출현, 선후, 행위 대상처럼 문장 요소 사이에서 측정된 관계 신호입니다.",
  quality: "DataGate가 판단한 품질 게이트 신호입니다.",
  memory: "장기 온톨로지 메모리의 저장 영역입니다.",
  verification: "근거 확인과 검증에 쓰이는 노드입니다.",
  learning: "실시간 학습 과정과 연결되는 노드입니다.",
  efficiency: "저전력/저사양 실행을 위한 효율화 노드입니다.",
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

function normalizeLocalBackendUrl(value: string) {
  const trimmed = value.trim().replace(/\/+$/, "");
  return trimmed || "http://127.0.0.1:8000";
}

function localBackendErrorMessage(baseUrl: string, caught: unknown) {
  const message = caught instanceof Error ? caught.message : "로컬 FastAPI 응답 실패";
  if (typeof window !== "undefined" && window.location.protocol === "https:" && normalizeLocalBackendUrl(baseUrl).startsWith("http://")) {
    return "HTTPS 배포본에서는 브라우저가 HTTP 로컬 FastAPI를 차단할 수 있습니다. 실제 PC 측정은 로컬 웹을 함께 실행하거나 HTTPS 로컬 companion을 사용하세요.";
  }
  return message;
}

async function directBackendJson<T>(baseUrl: string, path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers ?? undefined);
  const method = init?.method?.toUpperCase() ?? "GET";
  if ((init?.body || method !== "GET") && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${normalizeLocalBackendUrl(baseUrl)}${path}`, {
    ...init,
    cache: "no-store",
    headers,
  });
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.detail ?? body.error ?? `Local FastAPI returned ${response.status}`);
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

function stabilityPayloadForVolume(volume: LearningVolume, targetNodeCount?: number, hardwareProfile?: AnyRecord | null) {
  const preset = learningVolumePresets[volume];
  const targetNodes = clamp(Math.round(targetNodeCount ?? defaultTargetNodesForVolume(volume)), 100, maxTargetNodes);
  return {
    ...(hardwareProfile ? { hardware_profile: hardwareProfile } : {}),
    target_nodes: targetNodes,
    target_edges: Math.max(targetNodes + 1, Math.round(targetNodes * preset.edgeRatio)),
    duration_hours: preset.durationHours,
  };
}

function isRealTelemetrySource(system?: AnyRecord | null, benchmark?: AnyRecord | null) {
  const source = String(system?.source ?? "");
  return Boolean(benchmark?.can_read_local_hardware) || source === "local-fastapi" || source === "local-next";
}

function telemetrySourceText(system?: AnyRecord | null, benchmark?: AnyRecord | null) {
  if (benchmark?.can_read_local_hardware || system?.source === "local-fastapi") return "실제 PC 측정";
  if (system?.source === "local-next") return "로컬 Next 측정";
  if (system?.source === "deployment-sandbox") return "배포 샌드박스";
  return "측정 대기";
}

function numeric(value: unknown) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function resourcePressureReason(system?: AnyRecord | null, gpu?: AnyRecord | null, stability?: AnyRecord | null, benchmark?: AnyRecord | null) {
  if (!isRealTelemetrySource(system, benchmark)) return null;
  const ramSoft = numeric(stability?.runtime_envelope?.ram_soft_gb);
  const ramUsed = numeric(system?.ram_used_gb);
  if (ramSoft !== null && ramUsed !== null && ramUsed >= ramSoft) {
    return `RAM ${ramUsed.toFixed(1)}GB가 soft watermark ${ramSoft.toFixed(1)}GB를 넘었습니다`;
  }
  const vramSoft = numeric(stability?.runtime_envelope?.vram_soft_gb);
  const vramUsedMb = numeric(gpu?.vram_used);
  const vramUsed = vramUsedMb === null ? null : vramUsedMb / 1024;
  if (gpu?.available && vramSoft !== null && vramUsed !== null && vramUsed >= vramSoft) {
    return `VRAM ${vramUsed.toFixed(1)}GB가 soft watermark ${vramSoft.toFixed(1)}GB를 넘었습니다`;
  }
  const diskFree = numeric(system?.disk_free_gb);
  const storageReserve = numeric(stability?.runtime_envelope?.storage_reserve_gb);
  if (diskFree !== null && storageReserve !== null && diskFree <= storageReserve) {
    return `디스크 여유 ${diskFree.toFixed(1)}GB가 reserve ${storageReserve.toFixed(1)}GB 이하입니다`;
  }
  return null;
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

function memoryTypeColor(type?: string, fallbackIndex = 0) {
  return memoryTypeColors[type ?? ""] ?? fallbackMemoryColors[fallbackIndex % fallbackMemoryColors.length];
}

function memoryTypeDescription(type?: string) {
  return memoryTypeDescriptions[type ?? ""] ?? "현재 그래프에서 관찰된 사용자 정의 기억 노드입니다.";
}

function evidenceSignalText(doc: AnyRecord) {
  const signals = doc.retrieval_signals;
  if (!signals) return "";
  if (signals.web_search) return ` / 웹 ${signals.provider ?? "search"}`;
  const lexical = signals.lexical ?? "-";
  const graphBoost = signals.graph_boost ?? "-";
  return ` / 어휘 ${lexical} / 그래프 ${graphBoost}`;
}

function isNodeInventoryQuestion(query: string) {
  const normalized = query.trim().toLowerCase();
  return /(노드|node|nodes)/i.test(normalized) && /(다|전체|모두|목록|리스트|말해|알려|보여|보유|있는|list|all|show|inventory|available)/i.test(normalized);
}

function isLegendQuestion(query: string) {
  const normalized = query.trim().toLowerCase();
  const asksColor = /(색|색깔|색상|컬러|범례|legend|color)/i.test(normalized);
  const asksMeaning = /(의미|뜻|뭐|설명|구분|차이|meaning|mean|label)/i.test(normalized);
  const graphContext = /(노드|그래프|rag|온톨로지|메모리|신호|뉴런|node|graph)/i.test(normalized);
  return asksColor && (asksMeaning || graphContext);
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
      answer_kind: "inspection",
      answer_engine: {
        name: "BakeBoard Inspection Router",
        mode: "graph-inspection-control-alpha",
        external_llm: false,
        surface_generation: "disabled",
      },
      confidence: nodes.length ? 0.99 : 0.2,
    },
  };
}

function graphLegendStatus(query: string, graph: Rag3DGraph) {
  const nodes = graph.nodes ?? [];
  const edges = graph.edges ?? [];
  const typeOrder: string[] = [];
  const typeCounts = new Map<string, number>();
  const representativeNodes: Rag3DNode[] = [];
  const seenRepresentatives = new Set<string>();

  nodes.forEach((node) => {
    const type = node.type || "concept";
    typeCounts.set(type, (typeCounts.get(type) ?? 0) + 1);
    if (!typeOrder.includes(type)) typeOrder.push(type);
    if (!seenRepresentatives.has(type)) {
      representativeNodes.push(node);
      seenRepresentatives.add(type);
    }
  });

  const lines = typeOrder.slice(0, 10).map((type) => {
    const count = typeCounts.get(type) ?? 0;
    return `- ${memoryTypeColor(type)} ${memoryTypeText(type)}: ${memoryTypeDescription(type)} 현재 ${count}개`;
  });
  const answer = lines.length
    ? `색깔은 노드의 역할을 뜻합니다. 현재 3D RAG 그래프에서는 이렇게 읽으면 됩니다.\n${lines.join("\n")}\n\n답변 생성 중 주황색으로 팟팟 켜지는 노드는 “지금 질문을 처리하면서 활성화된 신호”입니다. 기본 색은 역할, 발광은 순간적인 뉴런 활성 상태라고 보면 됩니다.`
    : "아직 표시된 노드가 없어 색상 범례를 만들 수 없습니다. 빌드 시작을 누르면 수집 자료가 온톨로지 노드로 바뀌고, 노드 타입별 색상이 나타납니다.";
  const representativeIds = new Set(representativeNodes.map((node) => node.id));
  const matchedEdges = edges.filter((edge) => representativeIds.has(edge.source) || representativeIds.has(edge.target)).slice(0, 12);

  return {
    state: "completed",
    started_at: new Date().toISOString(),
    finished_at: new Date().toISOString(),
    error: null,
    last_query: query,
    confidence: nodes.length ? 0.98 : 0.25,
    result: {
      query,
      method: "homage-graph-legend-v1",
      answer,
      matched_nodes: representativeNodes,
      matched_edges: matchedEdges,
      evidence_docs: [],
      citations: [],
      graph_paths: matchedEdges.map((edge) => [edge.source, edge.relation, edge.target]),
      follow_up_questions: ["주황색 신호가 어떤 노드를 읽는지 보여줄까요?", "현재 노드 목록도 같이 펼쳐볼까요?"],
      retrieval_trace: {
        strategy: "graph legend intent; retrieval skipped",
        query_terms: query.toLowerCase().split(/\s+/).filter(Boolean),
        expanded_terms: typeOrder,
        ranked_chunk_ids: [],
        matched_node_ids: representativeNodes.map((node) => node.id),
      },
      answer_kind: "inspection",
      answer_engine: {
        name: "BakeBoard Inspection Router",
        mode: "graph-legend-control-alpha",
        external_llm: false,
        surface_generation: "disabled",
      },
      confidence: nodes.length ? 0.98 : 0.25,
    },
  };
}

function signalTraceForQuery(query: string, graph: Rag3DGraph, result?: AnyRecord | null) {
  const memoryActiveNodes = (result?.memory_activation?.active_nodes ?? []) as AnyRecord[];
  const memoryActiveEdges = (result?.memory_activation?.active_edges ?? []) as AnyRecord[];
  const memoryNodeIds = new Set(memoryActiveNodes.map((node) => String(node.id ?? "")).filter(Boolean));
  const memoryLabels = memoryActiveNodes
    .map((node) => String(node.label ?? node.id ?? "").toLowerCase())
    .filter(Boolean);
  const resultNodeIds = new Set((result?.matched_nodes ?? []).map((node: AnyRecord) => String(node.id ?? "")));
  const graphPathIds = new Set(
    (result?.graph_paths ?? [])
      .flatMap((path: AnyRecord) => Array.isArray(path) ? [path[0], path[2]] : [])
      .filter(Boolean)
      .map(String),
  );
  const terms = query
    .toLowerCase()
    .split(/[^a-z0-9가-힣_-]+/i)
    .filter((term) => term.length > 1);
  const activationTerms = [
    ...terms,
    ...memoryLabels.flatMap((label) => label.split(/[^a-z0-9가-힣-]+/i)),
  ].filter((term) => term.length > 1);
  const visibleNodeIds = new Set(graph.nodes.map((node) => node.id));
  const visibleMemoryIds = [...memoryNodeIds].filter((id) => visibleNodeIds.has(id));
  const scored = graph.nodes
    .map((node) => {
      const haystack = `${node.id} ${node.label} ${node.type}`.toLowerCase();
      const termScore = activationTerms.reduce((score, term) => score + (haystack.includes(term) ? 1 : 0), 0);
      const memoryScore = memoryNodeIds.has(node.id) ? 10 : 0;
      const labelScore = memoryLabels.some((label) => label && haystack.includes(label)) ? 7 : 0;
      const resultScore = resultNodeIds.has(node.id) ? 6 : 0;
      const pathScore = graphPathIds.has(node.id) ? 3 : 0;
      return { node, score: termScore + memoryScore + labelScore + resultScore + pathScore };
    })
    .filter((item) => item.score > 0)
    .sort((left, right) => right.score - left.score);
  let activeNodeIds = [...visibleMemoryIds, ...scored.map((item) => item.node.id)]
    .filter((id, index, all) => visibleNodeIds.has(id) && all.indexOf(id) === index)
    .slice(0, 14);
  let retargeted = Boolean(memoryNodeIds.size && !visibleMemoryIds.length && activeNodeIds.length);
  if (!activeNodeIds.length) {
    const recentLiveIds = graph.nodes
      .filter((node) => node.id.startsWith("live-synapse"))
      .slice(-10)
      .map((node) => node.id);
    const summaryIds = graph.nodes
      .filter((node) => node.id.startsWith("live-summary"))
      .slice(-4)
      .map((node) => node.id);
    const traversalIds = (graph.traversal_path ?? [])
      .filter((id) => visibleNodeIds.has(id))
      .slice(-8);
    activeNodeIds = Array.from(new Set([...recentLiveIds, ...summaryIds, ...traversalIds])).slice(0, 14);
    retargeted = Boolean(memoryNodeIds.size && activeNodeIds.length);
  }
  const activeNodeSet = new Set(activeNodeIds);
  const memoryEdgeKeys = memoryActiveEdges
    .map((edge) => `${edge.source}:${edge.target}`)
    .filter((key) => {
      const [source, target] = key.split(":");
      return activeNodeSet.has(source) && activeNodeSet.has(target);
    });
  const activeEdgeKeys = [
    ...memoryEdgeKeys,
    ...graph.edges
      .filter((edge) => activeNodeSet.has(edge.source) && activeNodeSet.has(edge.target))
      .slice(0, 18)
      .map((edge) => `${edge.source}:${edge.target}`),
  ].filter((key, index, all) => all.indexOf(key) === index).slice(0, 22);
  const labels = activeNodeIds
    .map((id) => graph.nodes.find((node) => node.id === id)?.label ?? id)
    .slice(0, 6);
  const signalText = labels.length
    ? `${retargeted ? "활성 신호(대표 노드)" : "활성 노드"}: ${labels.join(", ")}`
    : "활성 신호 대기";
  return {
    edgeKeys: activeEdgeKeys,
    nodeIds: activeNodeIds,
    text: signalText,
  };
  return {
    edgeKeys: activeEdgeKeys,
    nodeIds: activeNodeIds,
    text: labels.length ? `활성 노드: ${labels.join(", ")}` : "활성 신호 대기",
  };
}

function fmtClock(date = new Date()) {
  return date.toLocaleTimeString("ko-KR", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function formatDuration(ms: number) {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) return `${hours}시간 ${String(minutes).padStart(2, "0")}분 ${String(seconds).padStart(2, "0")}초`;
  return `${minutes}분 ${String(seconds).padStart(2, "0")}초`;
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
    color: memoryTypeColor(node.type ?? node.labels?.[0], index),
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
  const [stability, setStability] = useState<AnyRecord | null>(null);
  const [memoryStatus, setMemoryStatus] = useState<AnyRecord | null>(null);
  const [memoryDrift, setMemoryDrift] = useState<AnyRecord | null>(null);
  const [webSearchEnabled, setWebSearchEnabled] = useState(true);
  const [benchmark, setBenchmark] = useState<AnyRecord | null>(null);
  const [localBackendUrl, setLocalBackendUrl] = useState("http://127.0.0.1:8000");
  const [localBackendStatus, setLocalBackendStatus] = useState<"idle" | "checking" | "connected" | "failed">("idle");
  const [localBackendMessage, setLocalBackendMessage] = useState("배포 fallback 사용 중");
  const [learningVolume, setLearningVolume] = useState<LearningVolume>("standard");
  const [targetNodeCount, setTargetNodeCount] = useState<number>(defaultTargetNodesForVolume("standard"));
  const [selectedMemory, setSelectedMemory] = useState<AnyRecord | null>(null);
  const [activeSignalEdgeKeys, setActiveSignalEdgeKeys] = useState<string[]>([]);
  const [activeSignalNodeIds, setActiveSignalNodeIds] = useState<string[]>([]);
  const [signalTraceText, setSignalTraceText] = useState("활성 신호 대기");
  const [isGeneratingAnswer, setIsGeneratingAnswer] = useState(false);
  const [buildRun, setBuildRun] = useState<BuildRun | null>(null);
  const [buildTick, setBuildTick] = useState(0);
  const [isBuilding, setIsBuilding] = useState(false);
  const [continuousLearningActive, setContinuousLearningActive] = useState(false);
  const [learningStartedAt, setLearningStartedAt] = useState<number | null>(null);
  const [learningElapsedMs, setLearningElapsedMs] = useState(0);
  const [clockNow, setClockNow] = useState<Date | null>(null);
  const [activeAction, setActiveAction] = useState<string | null>(null);
  const [graphMode] = useState<"2d" | "3d">("3d");
  const [rag3dControl, setRag3dControl] = useState<Rag3DControl>({ serial: 0, action: "reset" });
  const graphRef = useRef<SVGSVGElement | null>(null);
  const chatScrollRef = useRef<HTMLDivElement | null>(null);
  const signalTimerRef = useRef<number | null>(null);
  const benchmarkAppliedRef = useRef(false);
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
  const localBackendConnected = localBackendStatus === "connected";

  useEffect(() => {
    const savedUrl = window.localStorage.getItem("homage.localFastApiUrl");
    if (savedUrl) {
      setLocalBackendUrl(savedUrl);
      connectLocalBackend(savedUrl).catch(() => undefined);
    }
  }, []);

  async function apiJson<T>(path: string, init?: RequestInit, options: { localOnly?: boolean; preferLocal?: boolean } = {}): Promise<T> {
    const shouldUseLocal = options.localOnly || options.preferLocal || localBackendConnected;
    if (shouldUseLocal) {
      try {
        return await directBackendJson<T>(localBackendUrl, path, init);
      } catch (caught) {
        if (localBackendConnected) {
          const message = localBackendErrorMessage(localBackendUrl, caught);
          try {
            await directBackendJson<AnyRecord>(localBackendUrl, "/health");
            setLocalBackendStatus("connected");
            setLocalBackendMessage(`로컬 FastAPI 연결됨 / 일부 API fallback: ${message}`);
          } catch {
            setLocalBackendStatus("failed");
            setLocalBackendMessage(message);
          }
        }
        if (options.localOnly) throw caught;
      }
    }
    return fetchJson<T>(path, init);
  }

  async function connectLocalBackend(candidateUrl = localBackendUrl) {
    const url = normalizeLocalBackendUrl(candidateUrl);
    setLocalBackendUrl(url);
    setLocalBackendStatus("checking");
    setLocalBackendMessage("로컬 FastAPI 확인 중");
    try {
      await directBackendJson<AnyRecord>(url, "/health");
      const [systemStatus, gpuStatus, benchmarkStatus] = await Promise.all([
        directBackendJson<AnyRecord>(url, "/api/telemetry/system"),
        directBackendJson<AnyRecord>(url, "/api/telemetry/gpu"),
        directBackendJson<AnyRecord>(url, "/api/neuro/benchmark", {
          method: "POST",
          body: JSON.stringify({ run_probes: true }),
        }),
      ]);
      setSystem(systemStatus);
      setGpu(gpuStatus);
      setBenchmark(benchmarkStatus);
      setLocalBackendStatus("connected");
      setLocalBackendMessage("로컬 FastAPI 연결됨");
      window.localStorage.setItem("homage.localFastApiUrl", url);
      const recommended = benchmarkStatus?.recommended_learning_volume as LearningVolume | undefined;
      if (benchmarkStatus?.can_read_local_hardware && recommended && learningVolumePresets[recommended]) {
        setLearningVolume(recommended);
        setTargetNodeCount(defaultTargetNodesForVolume(recommended));
      }
    } catch (caught) {
      setLocalBackendStatus("failed");
      setLocalBackendMessage(localBackendErrorMessage(url, caught));
    }
  }

  function disconnectLocalBackend() {
    setLocalBackendStatus("idle");
    setLocalBackendMessage("배포 fallback 사용 중");
    window.localStorage.removeItem("homage.localFastApiUrl");
  }

  async function refreshAll() {
    const [
      pipelineStatus,
      datagateStatus,
      ontologyStatus,
      ontologyGraph,
      memoryStatusResult,
      memoryGraphResult,
      memoryDriftResult,
      graphragStatus,
      guardStatus,
      gpuStatus,
      systemStatus,
      ovenStatus,
      neuroStatus,
      stabilityStatus,
    ] = await Promise.all([
      apiJson<PipelineStatus>("/api/pipeline/status"),
      apiJson<AnyRecord>("/api/datagate/status"),
      apiJson<AnyRecord>("/api/ontology/status"),
      apiJson<AnyRecord>("/api/ontology/graph"),
      apiJson<AnyRecord>("/api/memory/status"),
      apiJson<AnyRecord>("/api/memory/graph?limit=900"),
      apiJson<AnyRecord>("/api/memory/drift-check"),
      apiJson<AnyRecord>("/api/graphrag/status"),
      apiJson<AnyRecord>("/api/guard/status"),
      apiJson<AnyRecord>("/api/telemetry/gpu"),
      apiJson<AnyRecord>("/api/telemetry/system"),
      apiJson<AnyRecord>("/api/oven/status"),
      apiJson<AnyRecord>("/api/neuro/plan"),
      apiJson<AnyRecord>("/api/neuro/stability", {
        method: "POST",
        body: JSON.stringify(stabilityPayloadForVolume(
          learningVolume,
          targetNodeCount,
          benchmark?.can_read_local_hardware ? benchmark.hardware_profile : null,
        )),
      }),
    ]);
    setPipeline(pipelineStatus);
    setDatagate(datagateStatus);
    setOntology(ontologyStatus);
    setMemoryStatus(memoryStatusResult);
    setMemoryDrift(memoryDriftResult);
    setGraph(memoryGraphResult?.nodes?.length ? memoryGraphResult : ontologyGraph);
    setGraphRag(graphragStatus);
    setGuard(guardStatus);
    setGpu(gpuStatus);
    setSystem(systemStatus);
    setOven(ovenStatus);
    setNeuro(neuroStatus);
    setStability(stabilityStatus);
  }

  useEffect(() => {
    refreshAll().catch((caught) => setError(caught instanceof Error ? caught.message : "BakeBoard를 불러오지 못했습니다."));
    const timer = window.setInterval(() => {
      refreshAll().catch(() => undefined);
    }, 10000);
    return () => window.clearInterval(timer);
  }, [learningVolume, targetNodeCount, benchmark?.can_read_local_hardware, benchmark?.generated_at, localBackendConnected, localBackendUrl]);

  useEffect(() => {
    const updateClock = () => setClockNow(new Date());
    updateClock();
    const timer = window.setInterval(updateClock, 1000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    runHardwareBenchmark({ applyRecommendation: true }).catch((caught) => {
      setError(caught instanceof Error ? caught.message : "시스템 벤치마크에 실패했습니다.");
    });
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
        const isInfiniteRun = buildRun.learning_profile?.id === "infinite";
        const rawPulse = Math.max(0, tick - buildRun.graph_frames.length + 1);
        if (isInfiniteRun) return continuousLearningActive ? tick + 1 : tick;
        const targetNodes = Number(buildRun.training_gate?.target_nodes ?? buildRun.learning_profile?.target_nodes ?? 0);
        const baseNodes = buildRun.graph_3d?.nodes?.length ?? 0;
        const targetPulseLimit = targetNodes > baseNodes
          ? Math.ceil((targetNodes - baseNodes) / liveGrowthBatchSize)
          : minLiveGrowthPulses;
        if (rawPulse >= Math.max(minLiveGrowthPulses, targetPulseLimit)) return tick;
        return tick + 1;
      });
    }, 1200);
    return () => window.clearInterval(timer);
  }, [buildRun, continuousLearningActive, layoutMode]);

  useEffect(() => {
    if (!learningStartedAt) return;
    const updateElapsed = () => setLearningElapsedMs(Date.now() - learningStartedAt);
    updateElapsed();
    if (!continuousLearningActive) return;
    const timer = window.setInterval(updateElapsed, 1000);
    return () => window.clearInterval(timer);
  }, [continuousLearningActive, learningStartedAt]);

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
    const result = await apiJson<AnyRecord>("/api/datagate/run", {
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
    const result = await apiJson<AnyRecord>("/api/ontology/run", { method: "POST" });
    await refreshAll().catch(() => undefined);
    setOntology(result);
    if (result?.newest_nodes || result?.newest_edges) {
      setGraph({ nodes: result.newest_nodes ?? [], edges: result.newest_edges ?? [] });
    }
  }

  async function runMemoryBuildStep() {
    setMemoryStatus((current) => ({ ...(current ?? {}), state: "running" }));
    const result = await apiJson<AnyRecord>("/api/memory/build", { method: "POST" });
    const graphResult = await apiJson<AnyRecord>("/api/memory/graph?limit=900");
    const driftResult = await apiJson<AnyRecord>("/api/memory/drift-check");
    setMemoryStatus(result);
    setMemoryDrift(driftResult);
    if (graphResult?.nodes?.length) setGraph(graphResult);
  }

  async function runTrainingDryRun() {
    setError(null);
    setRightMode("process");
    try {
      const result = await apiJson<AnyRecord>("/api/oven/dry-run", { method: "POST" });
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
      setSignalTraceText("활성 신호 대기");
      signalTimerRef.current = null;
    }, holdMs);
  }

  async function sendChat() {
    const question = chatInput.trim();
    if (!question || isGeneratingAnswer) return;
    setError(null);
    setIsGeneratingAnswer(true);
    activateSignal(signalTraceForQuery(question, displayGraph3D), 15000);
    setChatMessages((messages) => [...messages, { role: "user", text: question }]);
    if (isNodeInventoryQuestion(question) || isLegendQuestion(question)) {
      const localResult = isLegendQuestion(question)
        ? graphLegendStatus(question, displayGraph3D)
        : graphInventoryStatus(question, displayGraph3D);
      setGraphRag(localResult);
      activateSignal(signalTraceForQuery(question, displayGraph3D, localResult.result), 15000);
      setChatMessages((messages) => [
        ...messages,
        {
          role: "assistant",
          text: localResult.result.answer,
          evidence: [],
        },
      ]);
      setIsGeneratingAnswer(false);
      return;
    }
    try {
      const result = await apiJson<AnyRecord>("/api/graphrag/query", {
        method: "POST",
        body: JSON.stringify({ query: question, web_search: webSearchEnabled }),
      });
      setGraphRag(result);
      activateSignal(signalTraceForQuery(question, displayGraph3D, result?.result), 15000);
      const evidence = result?.result?.evidence_docs ?? [];
      const nodes = result?.result?.matched_nodes ?? [];
      const answer = result?.result?.answer;
      const nodeText = nodes.length ? nodes.map((node: AnyRecord) => node.label).join(", ") : "현재 메모리";
      setChatMessages((messages) => [
        ...messages,
        {
          role: "assistant",
          text: answer ?? `NO_ANSWER\nnodes=${nodeText}\nevidence_docs=${evidence.length}`,
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
      const result = await apiJson<AnyRecord>("/api/guard/check", {
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
      const plan = await apiJson<AnyRecord>("/api/neuro/plan", {
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

  async function runHardwareBenchmark(options: { applyRecommendation?: boolean } = {}) {
    setError(null);
    const result = await apiJson<AnyRecord>("/api/neuro/benchmark", {
      method: "POST",
      body: JSON.stringify({ run_probes: true }),
    });
    setBenchmark(result);
    const recommended = result?.recommended_learning_volume as LearningVolume | undefined;
    let nextVolume = learningVolume;
    let nextTargetNodeCount = targetNodeCount;
    if (
      options.applyRecommendation &&
      result?.can_read_local_hardware &&
      recommended &&
      learningVolumePresets[recommended] &&
      !benchmarkAppliedRef.current
    ) {
      benchmarkAppliedRef.current = true;
      nextVolume = recommended;
      nextTargetNodeCount = defaultTargetNodesForVolume(recommended);
      setLearningVolume(recommended);
      setTargetNodeCount(nextTargetNodeCount);
    }
    const stabilityPlan = await apiJson<AnyRecord>("/api/neuro/stability", {
      method: "POST",
      body: JSON.stringify(stabilityPayloadForVolume(
        nextVolume,
        nextTargetNodeCount,
        result?.can_read_local_hardware ? result.hardware_profile : null,
      )),
    });
    setStability(stabilityPlan);
    return result;
  }

  async function refreshStabilityPlan() {
    setError(null);
    try {
      const payload = stabilityPayloadForVolume(
        learningVolume,
        targetNodeCount,
        benchmark?.can_read_local_hardware ? benchmark.hardware_profile : null,
      );
      const plan = await apiJson<AnyRecord>("/api/neuro/stability", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setStability(plan);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "지속 운전 계획 계산에 실패했습니다.");
    }
  }

  function stopContinuousLearning(reason?: string) {
    const elapsed = learningStartedAt ? Date.now() - learningStartedAt : learningElapsedMs;
    setContinuousLearningActive(false);
    setLearningElapsedMs(elapsed);
    const reasonText = reason ? ` 안전 중지 사유: ${reason}.` : "";
    setChatMessages((messages) => [
      ...messages,
      {
        role: "assistant",
        text: `∞ 지속 학습을 멈췄습니다.${reasonText} 누적 학습 시간은 ${formatDuration(elapsed)}이고, 현재 화면에는 대표 온톨로지 노드 ${displayGraph3D.nodes.length}개와 관계 ${displayGraph3D.edges.length}개가 남아 있습니다.`,
      },
    ]);
  }

  async function startFactoryBuild() {
    setError(null);
    if (learningVolume === "infinite" && resourceStopReason) {
      setError(`안전 조건 때문에 ∞ 학습을 시작하지 않았습니다: ${resourceStopReason}`);
      setChatMessages((messages) => [
        ...messages,
        { role: "assistant", text: `∞ 지속 학습 시작 전 안전 점검에서 멈췄습니다. 사유: ${resourceStopReason}.` },
      ]);
      return;
    }
    setIsBuilding(true);
    const startedAt = Date.now();
    setLearningStartedAt(startedAt);
    setLearningElapsedMs(0);
    setContinuousLearningActive(false);
    setBuildTick(0);
    setLayoutMode("split");
    setRightMode("process");
    try {
      const run = await apiJson<BuildRun>("/api/factory/build/start", {
        method: "POST",
        body: JSON.stringify(
          learningVolume === "infinite"
            ? { learning_volume: learningVolume, web_search: webSearchEnabled }
            : { learning_volume: learningVolume, target_nodes: targetNodeCount, web_search: webSearchEnabled },
        ),
      });
      const isInfiniteRun = run.learning_profile?.id === "infinite";
      setContinuousLearningActive(isInfiniteRun);
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
          text: isInfiniteRun
            ? `∞ 지속 학습이 시작됐습니다. 중지 버튼을 누르기 전까지 수집 라운드와 온톨로지 성장 이벤트를 계속 누적하고, 화면에는 최근/대표 노드를 최대 ${run.training_gate.visual_node_budget ?? run.graph_3d.nodes.length}개까지 안정적으로 표시합니다.`
            : `빌드 ${run.run_id}가 시작됐습니다. ${run.learning_profile?.label ?? currentLearningPreset.label} 모드로 텍스트 예산 ${run.learning_profile?.text_budget_label ?? currentLearningPreset.textBudget}, 학습 청크 ${run.training_gate.chunk_count ?? run.training_units?.length ?? currentLearningPreset.chunkBudget}개를 예약했고, 화면에는 대표 노드를 최대 ${run.training_gate.visual_node_budget ?? run.graph_3d.nodes.length}개까지만 안정적으로 표시합니다. 학습 게이트는 ${run.training_gate.ready ? "준비 완료" : "대기"} 상태입니다.`,
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
      setContinuousLearningActive(false);
      setError(caught instanceof Error ? caught.message : "빌드 시작에 실패했습니다.");
    } finally {
      setIsBuilding(false);
    }
  }

  const currentLearningPreset = learningVolumePresets[learningVolume];
  const benchmarkVolume = benchmark?.recommended_learning_volume as LearningVolume | undefined;
  const benchmarkVolumeLabel = benchmarkVolume && learningVolumePresets[benchmarkVolume] ? learningVolumePresets[benchmarkVolume].label : "대기";
  const benchmarkSourceLabel = benchmark?.can_read_local_hardware ? "로컬 측정" : benchmark ? "fallback" : "대기";
  const benchmarkCpuThreads = benchmark?.hardware_profile?.cpu_logical ?? system?.cpu_count ?? "n/a";
  const benchmarkRamGb = benchmark?.hardware_profile?.ram_gb ?? "n/a";
  const benchmarkDiskScore = benchmark?.probes?.disk_write_mb_s ?? null;
  const benchmarkCpuScore = benchmark?.probes?.cpu_loop_score ?? null;
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
  const buildIsInfinite = buildRun?.learning_profile?.id === "infinite";
  const selectedTargetNodeLabel = learningVolume === "infinite" ? "∞" : targetNodeCount.toLocaleString();
  const learningElapsedText = formatDuration(learningElapsedMs);
  const rawGrowthPulseCount = buildRun ? Math.max(0, buildTick - buildRun.graph_frames.length + 1) : 0;
  const visualNodeCap = buildRun?.training_gate?.visual_node_budget ?? currentLearningPreset.visualNodes;
  const buildTargetNodes = buildIsInfinite ? Number.POSITIVE_INFINITY : buildRun?.training_gate?.target_nodes ?? targetNodeCount;
  const buildTargetNodeLabel = buildIsInfinite ? "∞" : buildTargetNodes.toLocaleString();
  const representativeNodeCount = buildRun?.training_gate?.representative_node_count ?? buildRun?.graph_3d?.nodes.length ?? 0;
  const accumulatedLearningNodes = buildRun
    ? buildRun.graph_3d.nodes.length + rawGrowthPulseCount * liveGrowthBatchSize
    : 0;
  const accumulatedLearningEdges = buildRun
    ? buildRun.graph_3d.edges.length + rawGrowthPulseCount * liveGrowthBatchSize * 2
    : 0;
  const livePulseTargetLimit = buildRun
    ? Math.max(minLiveGrowthPulses, Math.ceil(Math.max(0, buildTargetNodes - representativeNodeCount) / liveGrowthBatchSize))
    : minLiveGrowthPulses;
  const growthPulseCount = Math.min(
    rawGrowthPulseCount,
    livePulseTargetLimit,
  );
  const activeBuildFrame = buildRun
    ? growthPulseCount > 0
      ? {
          tick: buildTick + 1,
          node_count: Math.min(visualNodeCap, buildRun.graph_3d.nodes.length + growthPulseCount * liveGrowthBatchSize),
          edge_count: buildRun.graph_3d.edges.length + growthPulseCount * liveGrowthBatchSize * 2,
          message:
            buildIsInfinite
              ? `${continuousLearningActive ? "∞ 지속 학습" : "∞ 학습 정지"} ${learningElapsedText}: 수집 라운드 ${growthPulseCount} / 누적 후보 ${accumulatedLearningNodes.toLocaleString()} 노드`
              : rawGrowthPulseCount > growthPulseCount
              ? `그래프 검사 모드: ${growthPulseCount}개 펄스에서 안정화했습니다.`
              : `실시간 학습 펄스 ${growthPulseCount}: 새 시냅스가 기억망에 연결되었습니다.`,
        }
      : buildRun.graph_frames?.[Math.min(buildTick, buildRun.graph_frames.length - 1)] ?? null
    : null;
  const activeGraph3D = useMemo<Rag3DGraph | null>(() => {
    if (!buildRun?.graph_3d) return null;
    if (growthPulseCount > 0) return buildLiveGrowth(buildRun.graph_3d, growthPulseCount, visualNodeCap, Boolean(buildIsInfinite || buildTargetNodes > visualNodeCap));
    const visibleNodeCount = activeBuildFrame?.node_count ?? buildRun.graph_3d.nodes.length;
    const nodeIds = new Set(buildRun.graph_3d.nodes.slice(0, visibleNodeCount).map((node) => node.id));
    return {
      nodes: buildRun.graph_3d.nodes.filter((node) => nodeIds.has(node.id)),
      edges: buildRun.graph_3d.edges.filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target)),
      traversal_path: buildRun.graph_3d.traversal_path?.filter((id) => nodeIds.has(id)),
    };
  }, [activeBuildFrame?.node_count, buildIsInfinite, buildRun, buildTargetNodes, growthPulseCount, visualNodeCap]);

  const displayGraph3D = activeGraph3D ?? memoryGraph3D;
  const totalLiveNodeCount = buildRun ? rawGrowthPulseCount * liveGrowthBatchSize : 0;
  const visibleLiveNodeCount = displayGraph3D.nodes.filter((node) => node.id.startsWith("live-synapse")).length;
  const summaryNodeCount = displayGraph3D.nodes.filter((node) => node.id.startsWith("live-summary")).length;
  const preservedAnchorNodeCount = buildRun?.graph_3d?.nodes.length ?? displayGraph3D.nodes.length;
  const hiddenLiveNodeCount = Math.max(0, totalLiveNodeCount - visibleLiveNodeCount);
  const newestLiveNodeId = totalLiveNodeCount > 0 ? `live-synapse-${totalLiveNodeCount}` : null;
  const representativeCapReached = Boolean(buildRun && displayGraph3D.nodes.length >= visualNodeCap);
  const representativeTargetPercent = buildRun && !buildIsInfinite ? percent(representativeNodeCount, buildTargetNodes) : 0;
  const renderedTargetPercent = buildRun && !buildIsInfinite ? percent(displayGraph3D.nodes.length, buildTargetNodes) : 0;

  useEffect(() => {
    if (!activeSignalNodeIds.length) return;
    const visibleNodeIds = new Set(displayGraph3D.nodes.map((node) => node.id));
    if (activeSignalNodeIds.some((id) => visibleNodeIds.has(id))) return;
    const trace = signalTraceForQuery(chatInput || String(graphResult?.query ?? ""), displayGraph3D, graphResult);
    if (!trace.nodeIds.length) return;
    setActiveSignalEdgeKeys(trace.edgeKeys);
    setActiveSignalNodeIds(trace.nodeIds);
    setSignalTraceText(trace.text);
  }, [activeSignalNodeIds, chatInput, displayGraph3D, graphResult]);

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
  const ramSoftGb = stability?.runtime_envelope?.ram_soft_gb ?? 23;
  const vramSoftGb = stability?.runtime_envelope?.vram_soft_gb ?? 12;
  const hotWindowNodes = stability?.graph_policy?.hot_window_nodes ?? 2048;
  const uiRenderNodes = stability?.graph_policy?.ui_render_nodes ?? 240;
  const telemetryLabel = telemetrySourceText(system, benchmark);
  const resourceStopReason = resourcePressureReason(system, gpu, stability, benchmark);
  const diskFreeGb = numeric(system?.disk_free_gb);
  const ramUsedGb = numeric(system?.ram_used_gb);
  const vramUsedGb = numeric(gpu?.vram_used) === null ? null : (numeric(gpu?.vram_used) ?? 0) / 1024;
  const flowHealth = useMemo(() => {
    const complete = pipeline?.stages.filter((stage) => stage.state === "complete").length ?? 0;
    return Math.round((complete / Math.max(1, pipeline?.stages.length ?? 8)) * 100);
  }, [pipeline]);

  useEffect(() => {
    if (!continuousLearningActive || !resourceStopReason) return;
    stopContinuousLearning(resourceStopReason);
  }, [continuousLearningActive, resourceStopReason]);

  const processSteps = [
    {
      number: "KB",
      title: "Knowledge Bakery",
      api: "POST /api/memory/build",
      state: activeAction === "KB" ? "running" : memoryStatus?.state ?? "idle",
      description: "정제 문서와 온톨로지에서 문장 요소, phrase 노드, 전후 토큰 확률, 3D 로컬 벡터를 SQLite 메모리로 굽습니다.",
      metrics: [
        `${memoryStatus?.node_count ?? 0} nodes`,
        `${memoryStatus?.edge_count ?? 0} edges`,
        `${memoryStatus?.transition_count ?? 0} transitions`,
        `${memoryStatus?.phrase_count ?? 0} phrases`,
        `drift ${memoryDrift?.state ?? "waiting"}`,
      ],
      action: () => runProcessAction("KB", runMemoryBuildStep),
      actionLabel: activeAction === "KB" ? "메모리 구축 중" : "메모리 구축",
    },
    {
      number: "HW",
      title: "시스템 벤치마크",
      api: "POST /api/neuro/benchmark",
      state: activeAction === "HW" ? "running" : benchmark ? "completed" : "idle",
      description: "시작 시 PC의 CPU, RAM, GPU, 디스크를 짧게 측정해 온톨로지 배치와 학습량을 자동으로 조절합니다.",
      metrics: [
        benchmark?.profile_name ?? "측정 대기",
        `추천 ${benchmarkVolumeLabel}`,
        `CPU ${benchmarkCpuThreads}`,
        `RAM ${benchmarkRamGb}GB`,
        telemetryLabel,
        resourceStopReason ? "안전중지 조건 감지" : "안전 조건 정상",
      ],
      action: () => runProcessAction("HW", () => runHardwareBenchmark({ applyRecommendation: true })),
      actionLabel: activeAction === "HW" ? "측정 중" : "벤치마크 재측정",
    },
    {
      number: "00",
      title: "빌드 시작",
      api: "POST /api/factory/build/start",
      state: isBuilding || continuousLearningActive ? "running" : buildRun ? "completed" : "idle",
      description: "인터넷 참조를 수집하고 DataGate, Ontology Forge, 3D GraphRAG 탐색, Homage Oven 학습 게이트까지 한 번에 흐르게 합니다.",
      metrics: [
        `${selectedTargetNodeLabel} 장기 목표`,
        `${buildRun?.training_gate?.chunk_count ?? currentLearningPreset.chunkBudget} 청크`,
        `${buildRun?.learning_profile?.text_budget_label ?? currentLearningPreset.textBudget}`,
        `${activeGraph3D?.nodes?.length ?? 0}/${buildRun ? visualNodeCap : currentLearningPreset.visualNodes} 대표 샘플`,
        buildRun ? `${buildRun.graph_3d.nodes.length.toLocaleString()} API 앵커` : `${currentLearningPreset.visualNodes} 초기 표시`,
        representativeCapReached ? "표시 상한 도달" : "표시 여유 있음",
        buildIsInfinite ? "무제한 지속" : buildRun?.training_gate?.target_realized ? "장기 목표 달성" : buildRun ? "장기 목표 미실현" : "대기",
        buildIsInfinite ? `누적 ${learningElapsedText}` : `${growthPulseCount} 실시간 펄스`,
        buildIsInfinite ? `${accumulatedLearningNodes.toLocaleString()} 후보 노드` : buildRun?.training_gate?.ready ? "학습 게이트 준비" : "게이트 대기",
      ],
      action: () => continuousLearningActive ? stopContinuousLearning() : runProcessAction("00", startFactoryBuild),
      actionLabel: continuousLearningActive ? "학습 중지" : isBuilding || activeAction === "00" ? "빌드 진행 중" : "빌드 시작",
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
    {
      number: "07",
      title: "지속 운전 안전장치",
      api: "POST /api/neuro/stability",
      state: activeAction === "07" ? "running" : "completed",
      description: "수천 개 노드/관계가 생겨도 큐, 체크포인트, 그래프 hot window, UI LOD로 시스템이 죽지 않게 제한합니다.",
      metrics: [`RAM soft ${ramSoftGb}GB`, `VRAM soft ${vramSoftGb}GB`, `hot ${hotWindowNodes} 노드`, `UI ${uiRenderNodes} 노드`],
      action: () => runProcessAction("07", refreshStabilityPlan),
      actionLabel: activeAction === "07" ? "계산 중" : "안정성 계산",
    },
  ];

  const logTime = clockNow ? fmtClock(clockNow) : "--:--:--";
  const logs = [
    ...(buildRun ? [{ time: logTime, message: `빌드 ${buildRun.run_id}: ${activeBuildFrame?.message ?? "팩토리 빌드 준비"} / 게이트 ${buildRun.training_gate.ready ? "준비" : "대기"}${buildIsInfinite ? ` / 누적 ${learningElapsedText}` : ""}` }] : []),
    { time: logTime, message: `벤치마크: ${benchmark?.profile_name ?? "대기"} / 추천 ${benchmarkVolumeLabel} / ${benchmarkSourceLabel}` },
    { time: logTime, message: `메모리 그래프 로드: ${displayMemoryNodeCount} 노드 / ${displayMemoryEdgeCount} 관계` },
    { time: logTime, message: `RAG 상태: ${statusText(graphrag?.state)} / 신뢰도 ${Math.round((graphrag?.confidence ?? 0) * 100)}%` },
    { time: logTime, message: `학습 상태: ${statusText(oven?.state)} / 마지막 손실 ${oven?.last_loss ?? "없음"}` },
    { time: logTime, message: `효율 계획: 추정 연산 절감 ${energyReduction}%` },
    { time: logTime, message: `지속 운전: RAM soft ${ramSoftGb}GB / VRAM soft ${vramSoftGb}GB / hot window ${hotWindowNodes} 노드` },
  ];

  function changeLayoutMode(mode: LayoutMode) {
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
          <button
            className="build-button"
            onClick={continuousLearningActive ? () => stopContinuousLearning() : startFactoryBuild}
            disabled={isBuilding || (Boolean(activeAction) && !continuousLearningActive)}
          >
            {continuousLearningActive ? "학습 중지" : isBuilding ? "빌드 중" : "빌드 시작"}
          </button>
          <span>단계 {processSteps.length}</span>
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
                    {buildRun ? (
                      <span>
                        기존 앵커 {preservedAnchorNodeCount} 유지 / 새 노드 {visibleLiveNodeCount} 표시 / 요약 {summaryNodeCount} 묶음
                      </span>
                    ) : null}
                    {newestLiveNodeId ? <span>최신 새 노드 {newestLiveNodeId} / 비표시 이력 {hiddenLiveNodeCount}</span> : null}
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
                {memoryLegendItems.slice(0, 12).map((node) => (
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
                    data-infinite={volume === "infinite"}
                    disabled={isBuilding || continuousLearningActive}
                    key={volume}
                    onClick={() => {
                      setLearningVolume(volume);
                      setTargetNodeCount(defaultTargetNodesForVolume(volume));
                    }}
                    title={`${learningVolumePresets[volume].textBudget} / ${learningVolumePresets[volume].chunkBudget} 청크`}
                  >
                    {learningVolumePresets[volume].label}
                  </button>
                ))}
                <label className="node-target-input">
                  <span>장기 목표</span>
                  {learningVolume === "infinite" ? (
                    <input
                      aria-label="장기 목표 노드 수"
                      disabled={isBuilding || continuousLearningActive}
                      readOnly
                      type="text"
                      value="∞"
                    />
                  ) : (
                    <input
                      aria-label="장기 목표 노드 수"
                      disabled={isBuilding || continuousLearningActive}
                      inputMode="numeric"
                      max={maxTargetNodes}
                      min={100}
                      step={100}
                      type="number"
                      value={targetNodeCount}
                      onChange={(event) => {
                        const nextValue = Number(event.currentTarget.value);
                        setTargetNodeCount(Number.isFinite(nextValue) ? clamp(nextValue, 100, maxTargetNodes) : defaultTargetNodesForVolume(learningVolume));
                      }}
                    />
                  )}
                </label>
                <label className="web-search-toggle">
                  <input
                    checked={webSearchEnabled}
                    type="checkbox"
                    onChange={(event) => setWebSearchEnabled(event.currentTarget.checked)}
                  />
                  <span>웹 검색</span>
                </label>
              </div>
              <div className="local-backend-control" data-state={localBackendStatus}>
                <span>로컬 FastAPI</span>
                <input
                  aria-label="로컬 FastAPI 주소"
                  disabled={localBackendStatus === "checking"}
                  value={localBackendUrl}
                  onChange={(event) => {
                    setLocalBackendUrl(event.currentTarget.value);
                    if (localBackendConnected) {
                      setLocalBackendStatus("idle");
                      setLocalBackendMessage("주소가 바뀌었습니다. 다시 연결하세요.");
                    }
                  }}
                />
                <button
                  disabled={localBackendStatus === "checking"}
                  onClick={() => connectLocalBackend()}
                >
                  {localBackendStatus === "checking" ? "확인 중" : localBackendConnected ? "재연결" : "연결"}
                </button>
                {localBackendConnected ? <button onClick={disconnectLocalBackend}>해제</button> : null}
                <small>{localBackendMessage}</small>
              </div>
              <div className="mini-metrics">
                <span>흐름 {flowHealth}%</span>
                <span>GPU {gpu?.utilization ?? 0}%</span>
                <span>RAM soft {ramSoftGb}GB</span>
                <span>{telemetryLabel}</span>
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
                      {step.metrics.map((metric, metricIndex) => <span key={`${step.number}-${metricIndex}-${metric}`}>{metric}</span>)}
                    </div>
                    <button
                      className="inline-action"
                      onClick={step.action}
                      disabled={step.number === "00" && continuousLearningActive ? false : Boolean(activeAction) || isBuilding}
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
                          {buildIsInfinite ? (
                            <span data-state={continuousLearningActive ? "running" : "complete"}>∞ 누적 {learningElapsedText}</span>
                          ) : null}
                          {buildRun ? (
                            <span data-state="complete">기존 앵커 {preservedAnchorNodeCount} 유지</span>
                          ) : null}
                          {representativeCapReached ? (
                            <span data-state="running">대표 렌더 상한 {visualNodeCap} 도달</span>
                          ) : null}
                          {buildIsInfinite ? (
                            <span data-state="running">새 노드 표시 {visibleLiveNodeCount} / 요약 {summaryNodeCount}</span>
                          ) : null}
                          {resourceStopReason ? (
                            <span data-state="running">안전중지 대기: {resourceStopReason}</span>
                          ) : null}
                        </div>
                        <div className="learning-budget-summary">
                          <span>{buildRun.learning_profile?.label ?? currentLearningPreset.label}</span>
                          <strong>웹 검색 {buildRun.web_search?.provider ?? (webSearchEnabled ? "static" : "off")}</strong>
                          <strong>{buildRun.training_gate.chunk_count ?? buildRun.training_units?.length ?? currentLearningPreset.chunkBudget} 청크</strong>
                          <strong>{buildRun.learning_profile?.text_budget_label ?? currentLearningPreset.textBudget}</strong>
                          {buildRun.web_search?.bing_query_url ? (
                            <small>검색 query: {buildRun.web_search.query} / Bing 표시 URL: {buildRun.web_search.bing_query_url}</small>
                          ) : null}
                          <small>
                            대표 노드 최대 {buildRun.training_gate.visual_node_budget ?? buildRun.graph_3d.nodes.length}개
                            {buildIsInfinite ? ` / 누적 후보 ${accumulatedLearningNodes.toLocaleString()}개 / 비표시 이력 ${hiddenLiveNodeCount.toLocaleString()}개` : ""}
                          </small>
                          <small>
                            장기 목표 {buildTargetNodeLabel}{buildIsInfinite ? "" : "개"}는 저장/학습 예산이고, API graph_3d는 대표 앵커 {buildRun.training_gate.representative_node_count ?? buildRun.graph_3d.nodes.length}개를 보냅니다.
                          </small>
                          <small>
                            현재 화면은 live 이벤트를 합쳐 {displayGraph3D.nodes.length}개를 렌더링 중이며 {buildIsInfinite ? "목표 상한 없이 계속 누적 중" : `장기 목표의 약 ${renderedTargetPercent}%`}입니다. 장기 목표는 계속 누적되고, 3D 화면은 선택한 대표 렌더 윈도우와 요약 노드로 안정화됩니다.
                          </small>
                          <small>
                            {buildIsInfinite ? "API 대표 앵커는 무제한 학습의 현재 샘플입니다." : `API 대표 앵커만 보면 장기 목표의 약 ${representativeTargetPercent}%입니다.`} 전체 목표를 실제 저장하려면 다음 단계인 append-only 온톨로지 이벤트 로그와 SQLite hot index가 필요합니다.
                          </small>
                          {buildIsInfinite ? (
                            <small>Alpha 경계: 수집 문서와 앵커 그래프는 API 결과, live-synapse는 저장 전 지속 성장 이벤트입니다.</small>
                          ) : null}
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
                    {step.number === "HW" && benchmark ? (
                      <div className="build-run-detail">
                        <div className="build-trace">
                          <span data-state={benchmark.can_read_local_hardware ? "complete" : "running"}>{benchmarkSourceLabel}</span>
                          <span data-state="complete">CPU {benchmarkCpuThreads} threads</span>
                          <span data-state="complete">Disk {benchmarkDiskScore ?? "n/a"} MB/s</span>
                          <span data-state={isRealTelemetrySource(system, benchmark) ? "complete" : "running"}>{telemetryLabel}</span>
                          {ramUsedGb !== null ? <span data-state="complete">RAM used {ramUsedGb.toFixed(1)}GB</span> : null}
                          {vramUsedGb !== null && gpu?.available ? <span data-state="complete">VRAM used {vramUsedGb.toFixed(1)}GB</span> : null}
                          {diskFreeGb !== null ? <span data-state={resourceStopReason?.includes("디스크") ? "running" : "complete"}>Disk free {diskFreeGb.toFixed(1)}GB</span> : null}
                        </div>
                        <div className="learning-budget-summary">
                          <span>{benchmark.profile_name ?? "Hardware Benchmark"}</span>
                          <strong>추천 {benchmarkVolumeLabel}</strong>
                          <strong>{benchmark.training_tuning?.microbatch_tokens ?? 0} tokens</strong>
                          <small>
                            CPU score {benchmarkCpuScore ?? "n/a"} / {benchmark?.can_read_local_hardware ? "실제 PC 기준으로 자동 적용됨" : "배포 화면의 CPU/RAM은 Vercel 샌드박스이며 실제 PC가 아닙니다"}
                          </small>
                          {resourceStopReason ? <small>안전중지: {resourceStopReason}</small> : null}
                        </div>
                      </div>
                    ) : null}
                    {step.number === "07" && stability ? (
                      <div className="build-run-detail">
                        <div className="build-trace">
                          <span data-state="running">Backpressure: {stability.backpressure_policy?.length ?? 0} 규칙</span>
                          <span data-state="complete">Checkpoint {stability.checkpoint_policy?.training_checkpoint_interval_minutes ?? 15}분</span>
                          <span data-state="complete" title={stability.graph_policy?.ui_render_strategy ?? "enabled"}>Graph LOD: frontier/anchor</span>
                          <span data-state={resourceStopReason ? "running" : "complete"}>{resourceStopReason ? "Auto-stop armed" : "Auto-stop clear"}</span>
                        </div>
                        <div className="learning-budget-summary">
                          <span>{stability.profile_name ?? "Sustained Profile"}</span>
                          <strong>{learningVolume === "infinite" ? "∞" : stability.target_workload?.target_nodes ?? 10000} 노드</strong>
                          <strong>{learningVolume === "infinite" ? "∞" : stability.target_workload?.target_edges ?? 40000} 관계</strong>
                          <small>저장 여유 {stability.runtime_envelope?.storage_reserve_gb ?? 200}GB 유지</small>
                          {diskFreeGb !== null ? <small>현재 디스크 여유 {diskFreeGb.toFixed(1)}GB / {telemetryLabel}</small> : null}
                          {resourceStopReason ? <small>현재 판단: {resourceStopReason}</small> : null}
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
                  <div><span>RAG 신뢰도</span><strong>{Math.round((graphResult?.confidence ?? graphrag?.confidence ?? 0) * 100)}%</strong></div>
                  <div><span>근거 문서</span><strong>{graphResult?.evidence_docs?.length ?? 0}</strong></div>
                  <div><span>생성 방식</span><strong>{graphResult?.answer_kind ?? graphResult?.answer_engine?.mode ?? "준비"}</strong></div>
                  <div><span>웹 검색</span><strong>{webSearchEnabled ? graphResult?.web_search?.provider ?? "on" : "off"}</strong></div>
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
                                {evidenceSignalText(doc)}
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
                  <button disabled={isGeneratingAnswer} onClick={sendChat}>{isGeneratingAnswer ? "생성 중" : "질문 보내기"}</button>
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
