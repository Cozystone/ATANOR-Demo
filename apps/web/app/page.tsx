"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent, WheelEvent as ReactWheelEvent } from "react";
import { Bell, Brain, Cloud, Globe2, Home, MessageCircle, Network, Package, RefreshCw, Settings, Share2, UserCircle } from "lucide-react";
import AtlasGlobe3D from "./AtlasGlobe3D";
import CloudBrainSphereScene, { type CloudBrainSphereStats } from "./CloudBrainSphereScene";
import Rag3DScene, { type Rag3DControl, type Rag3DEdge, type Rag3DGraph, type Rag3DNode, type Rag3DVisualState } from "./Rag3DScene";
import { TauriUpdatePrompt } from "./TauriUpdatePrompt";

type StageState = "idle" | "running" | "warning" | "complete";
type LayoutMode = "graph" | "split" | "workbench";
type WorkspaceMode = "daemon" | "lab";
type LearningVolume = "lite" | "standard" | "deep" | "max" | "infinite";
type RightMode = "process" | "chat";
type LabStageKey = "collect" | "learn" | "output";
type AnyRecord = Record<string, any>;
type Language = "en" | "ko";
type MainSectionId = "home" | "graph" | "local" | "cloud" | "atlas" | "graphhub" | "contribute" | "chat" | "settings";
type GraphPresentationMode = "home_unified_overview" | "local_private_memory" | "cloud_world_knowledge" | "unified_projection";

const mainNavIcon = {
  home: Home,
  graph: Network,
  local: Brain,
  cloud: Cloud,
  atlas: Globe2,
  graphhub: Package,
  contribute: Share2,
  chat: MessageCircle,
  settings: Settings,
} satisfies Record<MainSectionId, typeof Home>;

const MAIN_COPY: Record<Language, {
  nav: Array<{ id: MainSectionId; key: string; label: string }>;
  shellTitle: string;
  shellSubtitle: string;
  graphTitle: string;
  graphSubtitle: string;
  nodes: string;
  relations: string;
  sparsity: string;
  communities: string;
  systemStatus: string;
  activeTask: string;
  quickActions: string;
  recentActivity: string;
  chatTitle: string;
  chatSubtitle: string;
  send: string;
  generating: string;
  placeholder: string;
  sync: string;
  localBrain: string;
  cloudBrain: string;
  learningEngine: string;
  generationEngine: string;
  fragmentSync: string;
  running: string;
  connected: string;
  listening: string;
  ready: string;
  synced: string;
  graphSettled: string;
  localNode: string;
  cloudNode: string;
  fragmentNode: string;
  graphHint: string;
  strongRelation: string;
  weakRelation: string;
  actions: { newChat: string; graphExplore: string; memorySearch: string; learningTrigger: string; checkpoint: string };
  activity: { graphUpdate: string; patchSync: string; runtime: string; selected: string };
}> = {
  en: {
    nav: [
      { id: "home", key: "D", label: "Dashboard" },
      { id: "local", key: "L", label: "Local Brain" },
      { id: "cloud", key: "B", label: "Cloud Brain" },
      { id: "atlas", key: "A", label: "Atlas" },
      { id: "graphhub", key: "H", label: "Graph Hub" },
      { id: "contribute", key: "P", label: "Brain Link" },
      { id: "settings", key: "S", label: "Settings" },
    ],
    shellTitle: "ATANOR",
    shellSubtitle: "LOCAL-FIRST HYBRID AI ENGINE",
    graphTitle: "Unified Knowledge Graph",
    graphSubtitle: "A visual projection of Local, Seed, and Cloud layers. It does not indicate a live bridge.",
    nodes: "Nodes",
    relations: "Relations",
    sparsity: "Sparsity",
    communities: "Communities",
    systemStatus: "System Status",
    activeTask: "Active Task",
    quickActions: "Quick Actions",
    recentActivity: "Recent Activity",
    chatTitle: "ATANOR RAG",
    chatSubtitle: "Ask the local graph. Context is resolved through Ghost Shell and Payload Vault.",
    send: "Send",
    generating: "Generating",
    placeholder: "Ask ATANOR about the current memory graph...",
    sync: "Sync",
    localBrain: "Local Brain",
    cloudBrain: "Cloud Brain",
    learningEngine: "Learning Engine",
    generationEngine: "Generation Engine",
    fragmentSync: "Fragment Sync",
    running: "Running",
    connected: "Connected",
    listening: "Listening",
    ready: "Ready",
    synced: "Synced",
    graphSettled: "Graph settled",
    localNode: "Local Brain Node",
    cloudNode: "Cloud Brain Node",
    fragmentNode: "Cloud Fragment",
    graphHint: "Drag to rotate / Scroll to zoom / Click node to inspect",
    strongRelation: "Relation Strong",
    weakRelation: "Relation Weak",
    actions: {
      newChat: "New Conversation",
      graphExplore: "Graph Exploration",
      memorySearch: "Memory Search",
      learningTrigger: "Learning Trigger",
      checkpoint: "Checkpoint",
    },
    activity: {
      graphUpdate: "Graph Update",
      patchSync: "Patch Sync",
      runtime: "Runtime",
      selected: "Selected",
    },
  },
  ko: {
    nav: [
      { id: "home", key: "D", label: "대시보드" },
      { id: "local", key: "L", label: "로컬 브레인" },
      { id: "cloud", key: "B", label: "클라우드 브레인" },
      { id: "atlas", key: "A", label: "아틀라스" },
      { id: "graphhub", key: "H", label: "Graph Hub" },
      { id: "contribute", key: "P", label: "브레인 링크" },
      { id: "settings", key: "S", label: "설정" },
    ],
    shellTitle: "ATANOR",
    shellSubtitle: "로컬 우선 하이브리드 AI 엔진",
    graphTitle: "통합 지식 그래프",
    graphSubtitle: "로컬, 시드, 클라우드 레이어를 하나의 시각 투영으로 봅니다. 실제 연결 상태를 뜻하지 않습니다.",
    nodes: "노드",
    relations: "관계",
    sparsity: "희소도",
    communities: "커뮤니티",
    systemStatus: "시스템 상태",
    activeTask: "활성 작업",
    quickActions: "빠른 실행",
    recentActivity: "최근 활동",
    chatTitle: "ATANOR RAG",
    chatSubtitle: "로컬 그래프에 질문하세요. Ghost Shell과 Payload Vault 문맥을 읽어 답합니다.",
    send: "보내기",
    generating: "생성 중",
    placeholder: "현재 로컬 메모리에 대해 질문하세요...",
    sync: "동기화",
    localBrain: "로컬 브레인",
    cloudBrain: "클라우드 브레인",
    learningEngine: "학습 엔진",
    generationEngine: "생성 엔진",
    fragmentSync: "프래그먼트 동기화",
    running: "실행 중",
    connected: "연결됨",
    listening: "수신 중",
    ready: "준비됨",
    synced: "동기화됨",
    graphSettled: "그래프 안정화",
    localNode: "로컬 브레인 노드",
    cloudNode: "클라우드 브레인 노드",
    fragmentNode: "클라우드 프래그먼트",
    graphHint: "드래그 회전 / 스크롤 확대 / 노드 선택",
    strongRelation: "강한 관계",
    weakRelation: "약한 관계",
    actions: {
      newChat: "새 대화",
      graphExplore: "그래프 탐색",
      memorySearch: "메모리 검색",
      learningTrigger: "학습 시작",
      checkpoint: "체크포인트",
    },
    activity: {
      graphUpdate: "그래프 업데이트",
      patchSync: "패치 동기화",
      runtime: "누적 시간",
      selected: "선택 노드",
    },
  },
};

const INITIAL_CHAT_PROMPT: Record<Language, string> = {
  en: "How does GraphRAG verify answers with evidence documents?",
  ko: "GraphRAG가 근거 문서를 어떻게 사용해서 답변을 검증하나요?",
};

const INITIAL_ASSISTANT_MESSAGE: Record<Language, string> = {
  en: "Ask ATANOR through the local memory graph. It resolves Ghost Shell paths, fetches Payload Vault context, and answers through the local generation layer.",
  ko: "ATANOR에게 로컬 메모리를 기준으로 질문하세요. Ghost Shell 경로와 Payload Vault 문맥을 읽고 로컬 생성 계층에서 답변합니다.",
};

const EFFECTIVE_MAIN_COPY: typeof MAIN_COPY = MAIN_COPY;
const EFFECTIVE_INITIAL_CHAT_PROMPT: Record<Language, string> = INITIAL_CHAT_PROMPT;
const EFFECTIVE_INITIAL_ASSISTANT_MESSAGE: Record<Language, string> = INITIAL_ASSISTANT_MESSAGE;

const labStageOrder: LabStageKey[] = ["collect", "learn", "output"];

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

const defaultEdgeBrokerStatus: AnyRecord = {
  state: "viewer_only",
  architecture: "edge_compute_broker",
  cloud_required: false,
  capacity: {
    peer_id: "deployment-viewer",
    tier: "viewer",
    idle: false,
    endpoint: null,
    task_types: ["status_view"],
    max_batch_nodes: 0,
    max_batch_edges: 0,
  },
};

type ChatMessage = {
  role: "user" | "assistant";
  text: string;
  evidence?: AnyRecord[];
  diagnostics?: AnyRecord;
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

type AtlasDragState = {
  pointerId: number;
  startX: number;
  startRotationDeg: number;
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
const liveGrowthBatchSize = 12;
const minLiveGrowthPulses = 8;

function stableUnit(value: string, salt: number) {
  let hash = 2166136261 ^ salt;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return ((hash >>> 0) / 4294967295) * 2 - 1;
}

function stableDirection(value: string) {
  const y = stableUnit(value, 17);
  const theta = (stableUnit(value, 41) + 1) * Math.PI;
  const radial = Math.sqrt(Math.max(0.0001, 1 - y * y));
  return {
    x: Math.cos(theta) * radial,
    y,
    z: Math.sin(theta) * radial,
  };
}

const codexResearchGoalPrompt = `ATANOR1.0???κ린 ?곌뎄 紐⑺몴濡?怨꾩냽 媛쒖꽑?쒕떎.

紐⑺몴: ?몃? LLM怨?濡쒖뺄 ?묒옄??LLM ?놁씠, 濡쒖뺄 ?뚰겕?ㅽ뀒?댁뀡?먯꽌 ?μ떆媛??꾩쟻?섎뒗 ?⑦넧濡쒖?/洹몃옒??硫붾え由ъ? ?낆옄 ?앹꽦湲곕? ?곌뎄??以묓삎 LLM??媛源뚯슫 ?듬? ?덉쭏???ㅽ뿕?곸쑝濡??ъ꽦?쒕떎.

諛섎났 猷⑦봽:
1. 濡쒖뺄 FastAPI? Next BakeBoard瑜??ㅽ뻾?섍퀬 釉뚮씪?곗?濡?吏곸젒 議곗옉?쒕떎.
2. ?ㅽ뿕?ㅼ? ?섏쭛 -> ?숈뒿 -> 異쒕젰 ?쒖꽌濡쒕쭔 吏꾪뻾?쒕떎. ?섏쭛 100% ?꾩뿉???숈뒿?섏? ?딄퀬, ?숈뒿 100% ?꾩뿉??異쒕젰 ?덉쭏???됯??섏? ?딅뒗??
3. 3D 洹몃옒?꾨뒗 ?ㅼ젣 ???몃뱶/愿怨꾧? ?앷만 ?뚮쭔 ?뺤옣/?쒖꽦 ?좏샇瑜?蹂댁뿬以?? 蹂댁뿬二쇨린???꾩뒪, 媛吏?吏꾪뻾瑜? fake running ?곹깭瑜?留뚮뱾吏 ?딅뒗??
4. ?대씪?곕뱶 釉뚮젅??酉곕뒗 濡쒖뺄 FastAPI? local daemon???ㅼ젣濡??ㅽ뻾???뚮쭔 洹몃옒?꾨? 蹂댁뿬以?? ?곌껐 ?꾩씠??worker stopped ?곹깭?먯꽌??鍮?愿痢??붾㈃???좎??쒕떎.
5. Knowledge Bakery SQLite/JSONL ?대깽?? daemon ?곹깭, 泥댄겕?ъ씤?? ?몃뱶/愿怨??쒖꽦 ?좏샇瑜?吏곸젒 議고쉶??UI? ?ㅼ젣 ????곹깭媛 ?쇱튂?섎뒗吏 寃利앺븳??
6. ?앹꽦 寃곌낵媛 源⑥?硫?洹몃?濡?愿李고븯怨? 洹쒖튃 湲곕컲 ?ъ옣?쇰줈 ?④린吏 ?딅뒗??
7. 蹂묐ぉ?대굹 ?먯썝 寃쎄퀬媛 ?⑤㈃ ?ㅽ뙣 ?ㅽ뿕?쇰줈 湲곕줉?섍퀬 ?숈닠/?꾨Ц ?먮즺瑜?李얠븘 ??援ъ“?덉쓣 諛섏쁺?쒕떎.
8. 援ы쁽, ?뚯뒪?? 釉뚮씪?곗? ?ㅽ겕由곗꺑, 臾몄꽌 ?낅뜲?댄듃, 而ㅻ컠??諛섎났?쒕떎.

?쒖빟: ?듬? ?붿쭊?먮뒗 ?몃? LLM, sLLM, ?ъ쟾?숈뒿 ?앹꽦 媛以묒튂瑜??곗? ?딅뒗?? ??寃?됯낵 ?쇰Ц 議곗궗???곌뎄/?섏쭛 ?낅젰?쇰줈留??ъ슜?섍퀬, ?붿쭊???ㅼ젣濡??숈뒿?섏? ?딆? ?λ젰??媛吏?寃껋쿂???쒖떆?섏? ?딅뒗??`;

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

function buildLiveGrowth(base: Rag3DGraph, pulseCount: number, maxTotalNodes = Number.POSITIVE_INFINITY): Rag3DGraph {
  const liveNodes: Rag3DNode[] = [];
  const liveEdges: Rag3DEdge[] = [];
  const baseIds = new Set(base.nodes.map((node) => node.id));
  const baseNodeMap = new Map(base.nodes.map((node) => [node.id, node]));
  const baseCenter = base.nodes.reduce(
    (center, node) => ({
      x: center.x + (node.x ?? 0),
      y: center.y + (node.y ?? 0),
      z: center.z + (node.z ?? 0),
    }),
    { x: 0, y: 0, z: 0 },
  );
  if (base.nodes.length) {
    baseCenter.x /= base.nodes.length;
    baseCenter.y /= base.nodes.length;
    baseCenter.z /= base.nodes.length;
  }
  const baseRadius = Math.max(
    3.4,
    ...base.nodes.map((node) => {
      const dx = (node.x ?? 0) - baseCenter.x;
      const dy = (node.y ?? 0) - baseCenter.y;
      const dz = (node.z ?? 0) - baseCenter.z;
      return Math.sqrt(dx * dx + dy * dy + dz * dz);
    }),
  );
  const totalLiveNodeCount = Math.max(0, Math.floor(pulseCount)) * liveGrowthBatchSize;
  const maxRenderedNodes = Number.isFinite(maxTotalNodes) ? Math.max(base.nodes.length, Math.floor(maxTotalNodes)) : Number.POSITIVE_INFINITY;
  const renderSlots = Math.max(0, Math.floor(maxRenderedNodes - base.nodes.length));
  const startIndex = 0;
  const endIndex = Math.min(totalLiveNodeCount, renderSlots);
  for (let index = startIndex; index < endIndex; index += 1) {
    const template = liveGrowthTemplates[index % liveGrowthTemplates.length];
    const id = `live-synapse-${index + 1}`;
    const previous = index > startIndex ? `live-synapse-${index}` : null;
    const batchStart = Math.floor(index / liveGrowthBatchSize) * liveGrowthBatchSize;
    const batchIndex = Math.floor(index / liveGrowthBatchSize);
    const batchAnchor = base.nodes[(batchIndex * 3 + index) % Math.max(1, base.nodes.length)]?.id;
    const source = index === batchStart
      ? baseIds.has(template.source) ? template.source : batchAnchor
      : previous ?? batchAnchor;
    const sourceAnchor = baseIds.has(template.source) ? template.source : batchAnchor;
    const anchorNode = baseNodeMap.get(sourceAnchor ?? "") ?? base.nodes[batchIndex % Math.max(1, base.nodes.length)];
    const batchOffset = index - batchStart;
    const direction = stableDirection(id);
    const shell = baseRadius + 0.8 + Math.cbrt(index + 1) * 0.86 + Math.floor(index / liveGrowthBatchSize) * 0.055;
    const anchorBlend = Math.max(0.18, 0.42 - Math.min(0.22, batchIndex * 0.01));
    const shellPoint = {
      x: baseCenter.x + direction.x * shell,
      y: baseCenter.y + direction.y * shell * 0.9,
      z: baseCenter.z + direction.z * shell,
    };
    liveNodes.push({
      id,
      label: `${template.label} ${index + 1}`,
      type: template.type,
      x: shellPoint.x * (1 - anchorBlend) + (anchorNode?.x ?? baseCenter.x) * anchorBlend,
      y: shellPoint.y * (1 - anchorBlend) + (anchorNode?.y ?? baseCenter.y) * anchorBlend,
      z: shellPoint.z * (1 - anchorBlend) + (anchorNode?.z ?? baseCenter.z) * anchorBlend,
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
  return {
    nodes: [...base.nodes, ...liveNodes],
    edges: [...base.edges, ...liveEdges],
    traversal_path: [...(base.traversal_path ?? []), ...liveNodes.slice(-8).map((node) => node.id)],
  };
}

function buildStudioTopologyGraph(graph: Rag3DGraph): Rag3DGraph {
  if (!graph.nodes.length) return graph;
  const degree = new Map<string, number>();
  graph.nodes.forEach((node) => degree.set(node.id, 0));
  graph.edges.forEach((edge) => {
    degree.set(edge.source, (degree.get(edge.source) ?? 0) + 1);
    degree.set(edge.target, (degree.get(edge.target) ?? 0) + 1);
  });
  const sortedIds = [...graph.nodes]
    .sort((left, right) => (degree.get(right.id) ?? 0) - (degree.get(left.id) ?? 0))
    .map((node) => node.id);
  const anchorCount = Math.max(5, Math.min(18, Math.round(Math.sqrt(graph.nodes.length) / 2.1)));
  const anchors = sortedIds.slice(0, anchorCount);
  const anchorSet = new Set(anchors);
  const anchorIndex = new Map(anchors.map((id, index) => [id, index]));
  const neighborAnchors = new Map<string, string>();
  graph.edges.forEach((edge) => {
    if (anchorSet.has(edge.source) && !neighborAnchors.has(edge.target)) neighborAnchors.set(edge.target, edge.source);
    if (anchorSet.has(edge.target) && !neighborAnchors.has(edge.source)) neighborAnchors.set(edge.source, edge.target);
  });
  const anchorPosition = (id: string, index: number) => {
    if (index === 0) return { x: 0, y: 0, z: 0 };
    const side = index % 2 === 0 ? 1 : -1;
    const lane = Math.ceil(index / 2);
    const laneRatio = lane / Math.max(1, Math.ceil(anchorCount / 2));
    const arc = -0.9 + laneRatio * 1.8;
    return {
      x: side * (1.9 + laneRatio * 5.85),
      y: Math.sin(arc) * 5.35 + stableUnit(id, 501) * 0.42,
      z: Math.cos(arc) * 2.45 + stableUnit(id, 503) * 0.72,
    };
  };
  const anchorPositions = new Map<string, { x: number; y: number; z: number }>();
  anchors.forEach((id, index) => anchorPositions.set(id, anchorPosition(id, index)));
  const nodes = graph.nodes.map((node, index) => {
    const directAnchor = anchorSet.has(node.id)
      ? node.id
      : neighborAnchors.get(node.id) ?? anchors[Math.floor(((stableUnit(node.id, 601) + 1) / 2) * anchors.length) % anchors.length];
    const anchor = anchorPositions.get(directAnchor) ?? { x: 0, y: 0, z: 0 };
    const rank = anchorIndex.get(node.id);
    if (typeof rank === "number") {
      const type = anchor.x > 1.2 ? "cloud_brain" : anchor.x < -1.2 ? "local_memory" : "representative_sample";
      return {
        ...node,
        x: anchor.x,
        y: anchor.y,
        z: anchor.z,
        source_type: rank % 6 === 0 ? "cloud_fragment" : type,
      };
    }
    const degreeBoost = Math.min(1.7, 0.38 + Math.log1p(degree.get(node.id) ?? 0) * 0.2);
    const radius = degreeBoost + ((stableUnit(node.id, 607) + 1) / 2) * 1.84;
    const theta = (stableUnit(node.id, 613) + 1) * Math.PI;
    const x = anchor.x + Math.cos(theta) * radius * 0.92;
    const y = anchor.y + Math.sin(theta) * radius * 1.14 + stableUnit(`${node.id}:${index}`, 619) * 0.42;
    const z = anchor.z + stableUnit(node.id, 617) * 2.18;
    const sourceType = x > 1.7
      ? (index % 7 === 0 ? "cloud_fragment" : "cloud_brain")
      : x < -1.7
        ? "local_memory"
        : "representative_sample";
    return {
      ...node,
      x,
      y,
      z,
      source_type: sourceType,
    };
  });
  const targetVisualEdges = Math.min(graph.edges.length, Math.max(420, Math.round(Math.sqrt(graph.nodes.length) * 20)));
  const stride = Math.max(1, Math.ceil(graph.edges.length / targetVisualEdges));
  const visualEdges = graph.edges.filter((edge, index) => {
    if (anchorSet.has(edge.source) || anchorSet.has(edge.target)) return true;
    if ((degree.get(edge.source) ?? 0) > 8 && (degree.get(edge.target) ?? 0) > 8 && index % Math.max(1, Math.floor(stride / 2)) === 0) return true;
    return index % stride === 0;
  }).slice(0, targetVisualEdges);
  return { ...graph, nodes, edges: visualEdges };
}

function graphPresentationModeForSection(section: MainSectionId): GraphPresentationMode {
  if (section === "local" || section === "chat") return "local_private_memory";
  if (section === "cloud") return "cloud_world_knowledge";
  if (section === "graph") return "unified_projection";
  return "home_unified_overview";
}

function projectAtlasPoint(lat: number, lng: number) {
  const safeLat = clamp(Number.isFinite(lat) ? lat : 0, -72, 72);
  const normalizedLng = ((((Number.isFinite(lng) ? lng : 0) + 180) % 360) + 360) % 360 - 180;
  const safeLng = clamp(normalizedLng, -180, 180);
  const x = 50 + (safeLng / 180) * 38;
  const y = 50 - (safeLat / 90) * 32;
  return { x: clamp(x, 11, 89), y: clamp(y, 12, 88) };
}

function buildSphericalTopologyGraph(graph: Rag3DGraph, mode: GraphPresentationMode): Rag3DGraph {
  if (!graph.nodes.length) return graph;
  const degree = new Map<string, number>();
  graph.nodes.forEach((node) => degree.set(node.id, 0));
  graph.edges.forEach((edge) => {
    degree.set(edge.source, (degree.get(edge.source) ?? 0) + 1);
    degree.set(edge.target, (degree.get(edge.target) ?? 0) + 1);
  });
  const rankedIds = new Map(
    [...graph.nodes]
      .sort((left, right) => (degree.get(right.id) ?? 0) - (degree.get(left.id) ?? 0))
      .map((node, index) => [node.id, index]),
  );
  const nodeCount = graph.nodes.length;
  const localClusters = ["user_knowledge", "project_memory", "saved_conversations", "documents", "payload_vault", "ghost_shell", "local_evidence"];
  const cloudClusters = ["world_knowledge", "public_ontology", "source_cluster", "live_fragment", "trust_provenance", "freshness"];
  const nodes = graph.nodes.map((node, index) => {
    const rank = rankedIds.get(node.id) ?? index;
    const theta = index * 2.399963229728653 + stableUnit(node.id, 811) * 0.32;
    const scatter = 0.45 + ((stableUnit(node.id, 809) + 1) / 2);
    let x = 0;
    let y = 0;
    let z = 0;
    let sourceType = "local_memory";
    let clusterId = "local_memory";

    if (mode === "local_private_memory") {
      const cluster = localClusters[Math.abs(Math.floor((rank * 3 + index) % localClusters.length))];
      const clusterIndex = localClusters.indexOf(cluster);
      const clusterAngle = (clusterIndex / localClusters.length) * Math.PI * 2 - Math.PI / 2;
      const clusterRadius = cluster === "payload_vault" || cluster === "ghost_shell" ? 2.7 : 2.0;
      const centerX = Math.cos(clusterAngle) * clusterRadius * 0.75;
      const centerY = Math.sin(clusterAngle) * clusterRadius * 0.52;
      const centerZ = (clusterIndex - localClusters.length / 2) * 0.18;
      const nodeRadius = (rank < 28 ? 0.42 : 0.76 + scatter * 0.62) * (cluster === "payload_vault" ? 0.72 : 1);
      x = centerX + Math.cos(theta) * nodeRadius;
      y = centerY + Math.sin(theta) * nodeRadius * 0.86;
      z = centerZ + stableUnit(node.id, 821) * 1.2;
      sourceType = rank % 53 === 0 ? "cloud_fragment_disabled" : rank % 9 === 0 ? "representative_sample" : "local_memory";
      clusterId = `local:${cluster}`;
    } else if (mode === "cloud_world_knowledge") {
      if (nodeCount <= 24) {
        if (rank === 0) {
          x = 0;
          y = 0;
          z = 0.15;
        } else {
          const smallAngle = ((rank - 1) / Math.max(1, nodeCount - 1)) * Math.PI * 2 - Math.PI / 2;
          const smallRadius = 1.55 + (rank % 3) * 0.28;
          x = Math.cos(smallAngle) * smallRadius * 1.18;
          y = Math.sin(smallAngle) * smallRadius * 0.82;
          z = stableUnit(node.id, 824) * 0.88;
        }
        sourceType = rank === 0 ? "cloud_fragment" : "cloud_brain";
        clusterId = "cloud:proof_store";
        return {
          ...node,
          x,
          y,
          z,
          source_type: sourceType,
          cluster_id: clusterId,
        };
      }
      const cluster = cloudClusters[Math.abs(Math.floor((rank * 5 + index) % cloudClusters.length))];
      const clusterIndex = cloudClusters.indexOf(cluster);
      const clusterAngle = (clusterIndex / cloudClusters.length) * Math.PI * 2 + 0.38;
      const clusterRadius = 3.8 + (clusterIndex % 3) * 0.68;
      const centerX = Math.cos(clusterAngle) * clusterRadius * 1.32;
      const centerY = Math.sin(clusterAngle) * clusterRadius * 0.72;
      const centerZ = stableUnit(cluster, 829) * 2.2;
      const nodeRadius = rank < 36 ? 0.58 : 1.0 + scatter * 0.92;
      x = centerX + Math.cos(theta) * nodeRadius * 1.18;
      y = centerY + Math.sin(theta) * nodeRadius;
      z = centerZ + stableUnit(node.id, 823) * 2.5;
      sourceType = rank % 41 === 0 ? "representative_sample_edge_consumer" : rank % 5 === 0 ? "cloud_fragment" : "cloud_brain";
      clusterId = `cloud:${cluster}`;
    } else {
      const band = rank % 10;
      const isWorking = band >= 8;
      const isCloud = band >= 4 && band < 8;
      const side = isWorking ? 0 : isCloud ? 1 : -1;
      const lobeCenterX = side * 4.7;
      const lobeCenterY = isWorking ? 0 : stableUnit(`${node.id}:lobe`, 827) * 1.1;
      const lobeRadius = isWorking ? 1.25 + scatter * 0.45 : 1.55 + scatter * 0.85;
      x = lobeCenterX + Math.cos(theta) * lobeRadius * (isWorking ? 0.82 : 1.1);
      y = lobeCenterY + Math.sin(theta) * lobeRadius * 0.86;
      z = stableUnit(node.id, 831) * (isWorking ? 1.4 : 2.3);
      sourceType = isWorking ? "cloud_fragment_working_memory" : isCloud ? (rank % 6 === 0 ? "cloud_fragment" : "cloud_brain") : "local_memory";
      clusterId = isWorking ? "unified:working_memory" : isCloud ? "unified:cloud_brain" : "unified:local_brain";
    }

    return {
      ...node,
      x,
      y,
      z,
      source_type: sourceType,
      cluster_id: clusterId,
    };
  });
  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const targetVisualEdges = mode === "local_private_memory"
    ? Math.min(graph.edges.length, Math.max(260, Math.round(nodeCount * 0.78)))
    : mode === "cloud_world_knowledge"
      ? Math.min(graph.edges.length, Math.max(520, Math.round(nodeCount * 1.28)))
      : Math.min(graph.edges.length, Math.max(420, Math.round(nodeCount * 0.92)));
  const stride = Math.max(1, Math.ceil(graph.edges.length / targetVisualEdges));
  const visualEdges = graph.edges.filter((edge, index) => {
    const sourceRank = rankedIds.get(edge.source) ?? Number.MAX_SAFE_INTEGER;
    const targetRank = rankedIds.get(edge.target) ?? Number.MAX_SAFE_INTEGER;
    const sourceNode = nodeById.get(edge.source);
    const targetNode = nodeById.get(edge.target);
    const sourceCluster = String(sourceNode?.cluster_id ?? "");
    const targetCluster = String(targetNode?.cluster_id ?? "");
    if (mode === "unified_projection") {
      if (sourceCluster !== targetCluster && index % Math.max(1, Math.floor(stride / 3)) === 0) return true;
      if (sourceRank < 16 || targetRank < 16) return true;
      return index % Math.max(stride * 2, 1) === 0;
    }
    if (mode === "local_private_memory") {
      if (/disabled|cloud/i.test(String(sourceNode?.source_type ?? "")) || /disabled|cloud/i.test(String(targetNode?.source_type ?? ""))) return false;
      if (sourceRank < 14 || targetRank < 14) return true;
      if (sourceCluster !== targetCluster && index % Math.max(1, stride) === 0) return true;
      return index % Math.max(1, stride * 2) === 0;
    }
    if (sourceRank < 18 || targetRank < 18) return true;
    if (sourceCluster !== targetCluster && index % Math.max(1, Math.floor(stride / 2)) === 0) return true;
    if (sourceRank < 80 && targetRank < 80 && index % Math.max(1, Math.floor(stride / 2)) === 0) return true;
    return index % stride === 0;
  }).slice(0, targetVisualEdges);
  return { ...graph, nodes, edges: visualEdges };
}

function brainGraphLayerSourceType(node: AnyRecord) {
  const layer = String(node.layer ?? node.kind ?? "").toLowerCase();
  if (layer.includes("semantic_cloud")) return "cloud_brain";
  if (layer.includes("graph_cartridge")) return "cloud_fragment";
  if (layer.includes("cloud_attached") || layer.includes("working_memory_cloud")) return "working_memory";
  if (layer.includes("surface")) return "representative_sample";
  if (layer.includes("seed")) return "seed_schema";
  if (layer.includes("base")) return "evidence_source";
  return String(node.source_scope ?? "").toLowerCase() === "cloud" ? "cloud_brain" : "local_memory";
}

function buildBrainLayerGraph3D(rawGraph: AnyRecord | null | undefined): Rag3DGraph {
  const rawNodes = Array.isArray(rawGraph?.nodes) ? rawGraph.nodes as AnyRecord[] : [];
  const rawEdges = Array.isArray(rawGraph?.edges) ? rawGraph.edges as AnyRecord[] : [];
  if (!rawNodes.length) return { nodes: [], edges: [], traversal_path: [] };

  const idByLayerAndRawId = new Map<string, string>();
  const ids = new Set<string>();
  const nodes: Rag3DNode[] = rawNodes.map((node, index) => {
    const layer = String(node.layer ?? "graph");
    const rawId = String(node.id ?? `${layer}:${index}`);
    const id = `${layer}:${rawId}`;
    idByLayerAndRawId.set(`${layer}:${rawId}`, id);
    ids.add(id);
    const fallbackTheta = index * 2.399963229728653;
    const fallbackRadius = 1.8 + ((stableUnit(rawId, 271) + 1) / 2) * 1.4;
    const hasSourcePosition = Number.isFinite(Number(node.x)) && Number.isFinite(Number(node.y)) && Number.isFinite(Number(node.z));
    return {
      id,
      label: String(node.label ?? rawId),
      type: String(node.kind ?? node.type ?? layer),
      x: hasSourcePosition ? Number(node.x) * 2.8 : Math.cos(fallbackTheta) * fallbackRadius,
      y: hasSourcePosition ? Number(node.y) * 2.8 : Math.sin(fallbackTheta) * fallbackRadius * 0.72,
      z: hasSourcePosition ? Number(node.z) * 2.8 : stableUnit(rawId, 277) * 2.2,
      confidence: Number(node.weight ?? node.confidence ?? 0.78),
      source_type: brainGraphLayerSourceType(node),
      cluster_id: layer,
    };
  });

  const edges: Rag3DEdge[] = rawEdges.flatMap((edge) => {
    const layer = String(edge.layer ?? "graph");
    const source = idByLayerAndRawId.get(`${layer}:${String(edge.source ?? "")}`)
      ?? idByLayerAndRawId.get(`semantic_cloud:${String(edge.source ?? "")}`)
      ?? idByLayerAndRawId.get(`cloud_attached:${String(edge.source ?? "")}`)
      ?? String(edge.source ?? "");
    const target = idByLayerAndRawId.get(`${layer}:${String(edge.target ?? "")}`)
      ?? idByLayerAndRawId.get(`semantic_cloud:${String(edge.target ?? "")}`)
      ?? idByLayerAndRawId.get(`cloud_attached:${String(edge.target ?? "")}`)
      ?? String(edge.target ?? "");
    if (!ids.has(source) || !ids.has(target)) return [];
    return [{
      source,
      target,
      relation: String(edge.relation ?? "relates_to"),
      weight: Number(edge.weight ?? edge.confidence ?? 0.7),
      source_type: layer,
    }];
  });

  return {
    nodes,
    edges,
    traversal_path: nodes.slice(0, 32).map((node) => node.id),
  };
}

const stateLabels: Record<string, string> = {
  idle: "대기",
  running: "진행 중",
  completed: "완료",
  complete: "완료",
  failed: "실패",
  warning: "경고",
  ready: "준비",
  waiting: "대기",
  resume_needed: "재개 필요",
};

const fallbackMemoryColors = ["#ff6b35", "#006a9f", "#8c3fa7", "#22936f", "#c5283d", "#e89d2a", "#4a8fdb"];

const traceStepLabels: Record<string, string> = {
  Harvest: "자료 수집",
  DataGate: "DataGate 정제",
  "Ontology Forge": "온톨로지 생성",
  GraphRAG: "GraphRAG 경로",
  "ATANOR Oven": "학습 게이트",
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
  source: "웹과 문서에서 수집한 원문 자료와 근거 청크입니다.",
  critique: "품질 문제, 반례, 경계 조건처럼 학습을 조절하는 신호입니다.",
  ontology: "개념 사이의 관계를 묶는 온톨로지 메모리입니다.",
  retrieval: "질문을 근거 문서와 그래프 경로로 연결하는 검색 노드입니다.",
  visualization: "현재 학습 상태를 화면에 표시하는 시각화 노드입니다.",
  guardrail: "답변의 과장, 생략, 근거 부족을 검증하는 안전 노드입니다.",
  training: "ATANOR Oven으로 이어지는 학습 및 압축 신호입니다.",
  concept: "문서에서 추출한 핵심 개념 노드입니다.",
  keyword: "검색과 관계 확장에 쓰이는 키워드 기억입니다.",
  heading: "문서 구조와 섹션 제목에서 온 문맥 앵커입니다.",
  verb: "문장에서 추출한 행위 또는 동작 신호입니다.",
  phrase: "인접 단어가 함께 만든 짧은 문장 요소입니다.",
  relation: "공출현, 행위, 대상 사이에서 측정한 관계 신호입니다.",
  quality: "DataGate가 판단한 품질 게이트 신호입니다.",
  memory: "장기 온톨로지 메모리의 저장 영역입니다.",
  verification: "근거 확인과 검증에 쓰이는 노드입니다.",
  learning: "실시간 학습 과정과 연결되는 노드입니다.",
  efficiency: "저전력 및 저사양 실행을 위한 효율 노드입니다.",
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
  return trimmed || "http://127.0.0.1:8500";
}

function edgeStatusApiPath(baseUrl: string) {
  return `/api/network/edge/status?backend=${encodeURIComponent(normalizeLocalBackendUrl(baseUrl))}`;
}

function edgeAdvertiseApiPath(baseUrl: string) {
  return `/api/network/edge/advertise?backend=${encodeURIComponent(normalizeLocalBackendUrl(baseUrl))}`;
}

function graphStreamApiPath(baseUrl: string, limit = 5000) {
  return `/api/graph/stream?backend=${encodeURIComponent(normalizeLocalBackendUrl(baseUrl))}&limit=${encodeURIComponent(String(limit))}&include_cloud_attached=true`;
}

function readBrowserStorage(key: string) {
  try {
    if (typeof window === "undefined" || !window.localStorage) return null;
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeBrowserStorage(key: string, value: string) {
  try {
    if (typeof window !== "undefined" && window.localStorage) {
      window.localStorage.setItem(key, value);
    }
  } catch {
    // Storage can be unavailable in embedded browser sandboxes.
  }
}

function removeBrowserStorage(key: string) {
  try {
    if (typeof window !== "undefined" && window.localStorage) {
      window.localStorage.removeItem(key);
    }
  } catch {
    // Storage can be unavailable in embedded browser sandboxes.
  }
}

function localBackendErrorMessage(baseUrl: string, caught: unknown) {
  const message = caught instanceof Error ? caught.message : "로컬 FastAPI 응답 실패";
  if (typeof window !== "undefined" && window.location.protocol === "https:" && normalizeLocalBackendUrl(baseUrl).startsWith("http://")) {
    return "HTTPS 배포본에서는 브라우저가 HTTP 로컬 FastAPI를 차단할 수 있습니다. 로컬 웹과 FastAPI를 함께 실행하거나 HTTPS 로컬 companion을 사용하세요.";
  }
  return message;
}

function localBackendDisplayMessage(message: string, status: "idle" | "checking" | "connected" | "failed", language: Language) {
  if (language === "ko") return message;
  if (status === "checking") return "Syncing Local Brain";
  if (status === "connected") return "Local Brain connected";
  if (status === "idle") return "Using bundled fallback";
  if (message.includes("HTTPS") || message.includes("HTTP")) {
    return "This browser may block an HTTP Local FastAPI companion from an HTTPS deployment. Run the local web app and FastAPI together, or use an HTTPS local companion.";
  }
  return "Local FastAPI did not respond";
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
  const ramHard = numeric(stability?.runtime_envelope?.ram_hard_gb);
  const ramUsed = numeric(system?.ram_used_gb);
  const ramPercent = numeric(system?.ram_used_percent);
  if (ramHard !== null && ramUsed !== null && ramUsed >= ramHard) {
    return `RAM ${ramUsed.toFixed(1)}GB가 hard watermark ${ramHard.toFixed(1)}GB를 넘었습니다.`;
  }
  if (ramSoft !== null && ramUsed !== null && ramUsed >= ramSoft && ramPercent !== null && ramPercent >= 88) {
    return `RAM 사용률 ${ramPercent.toFixed(1)}%가 안전 한도를 넘었습니다.`;
  }
  const vramSoft = numeric(stability?.runtime_envelope?.vram_soft_gb);
  const vramHard = numeric(stability?.runtime_envelope?.vram_hard_gb);
  const vramUsedMb = numeric(gpu?.vram_used);
  const vramUsed = vramUsedMb === null ? null : vramUsedMb / 1024;
  if (gpu?.available && vramHard !== null && vramUsed !== null && vramUsed >= vramHard) {
    return `VRAM ${vramUsed.toFixed(1)}GB가 hard watermark ${vramHard.toFixed(1)}GB를 넘었습니다.`;
  }
  if (gpu?.available && vramSoft !== null && vramUsed !== null && vramUsed >= vramSoft && Number(gpu?.utilization ?? 0) >= 92) {
    return "VRAM 사용량과 GPU 부하가 안전 한도를 넘었습니다.";
  }
  const diskFree = numeric(system?.disk_free_gb);
  const storageReserve = numeric(stability?.runtime_envelope?.storage_reserve_gb);
  if (diskFree !== null && storageReserve !== null && diskFree <= storageReserve) {
    return `디스크 여유 ${diskFree.toFixed(1)}GB가 reserve ${storageReserve.toFixed(1)}GB 이하입니다.`;
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

function buildFrameMessageText(message?: string | null) {
  if (!message) return "수집 그래프를 구성하고 있습니다.";
  if (/output gate/i.test(message)) return "수집 대상 그래프 구성 완료";
  if (/harvest/i.test(message)) return "자료 수집 그래프 구성 중";
  return message;
}

function isNodeInventoryQuestion(query: string) {
  const normalized = query.trim().toLowerCase();
  return /(노드|node|nodes)/i.test(normalized) && /(전체|모두|목록|리스트|말해|알려|보여|보유|있는|list|all|show|inventory|available)/i.test(normalized);
}

function isLegendQuestion(query: string) {
  const normalized = query.trim().toLowerCase();
  const asksColor = /(색깔|색상|컬러|범례|legend|color)/i.test(normalized);
  const asksMeaning = /(의미|뜻|설명|구분|차이|meaning|mean|label)/i.test(normalized);
  const graphContext = /(노드|그래프|rag|온톨로지|메모리|신호|이론|node|graph)/i.test(normalized);
  return asksColor && (asksMeaning || graphContext);
}

function isConversationalQuestion(query: string) {
  const normalized = query.trim().toLowerCase();
  return /^(안녕|안녕하세요|하이|헬로|반가워|고마워|감사|감사합니다|hi|hello|hey|yo|thanks|thank you)[\s!.?]*$/i.test(normalized);
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
      method: "atanor-graph-inspection-v1",
      answer,
      matched_nodes: nodes,
      matched_edges: edges,
      evidence_docs: [],
      citations: [],
      graph_paths: edges.slice(0, 12).map((edge) => [edge.source, edge.relation, edge.target]),
      follow_up_questions: ["관계선을 모두 보여줄까요?", "특정 노드의 이웃만 펼쳐볼까요?"],
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
    ? `색깔은 노드의 역할을 나타냅니다. 현재 3D RAG 그래프에서는 다음처럼 읽으면 됩니다.\n${lines.join("\n")}\n\n질문 중 주황색으로 밝게 켜지는 노드는 실제로 활성화된 신호입니다. 기본 색은 역할과 메모리 상태를 구분하기 위한 시각적 표식입니다.`
    : "아직 표시된 노드가 없어 색상 범례를 만들 수 없습니다. 빌드 시작을 누르면 수집 자료가 온톨로지 노드로 바뀌고 타입별 색상이 적용됩니다.";
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
      method: "atanor-graph-legend-v1",
      answer,
      matched_nodes: representativeNodes,
      matched_edges: matchedEdges,
      evidence_docs: [],
      citations: [],
      graph_paths: matchedEdges.map((edge) => [edge.source, edge.relation, edge.target]),
      follow_up_questions: ["주황색 신호가 어떤 노드를 읽는지 보여줄까요?", "현재 노드 목록을 같이 펼쳐볼까요?"],
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

function shouldUseWebSearchForQuestion(question: string, webSearchEnabled: boolean) {
  if (!webSearchEnabled) return false;
  const normalized = question.trim().toLowerCase();
  if (!normalized) return false;
  const compact = normalized.replace(/[\s!.?,]+/g, "");
  if (["hi", "hello", "hey", "yo", "thanks", "thankyou", "안녕", "안녕하세요", "하이", "고마워", "감사", "감사합니다"].includes(compact)) {
    return false;
  }
  const tokens = normalized.match(/[a-z0-9가-힣-]+/g) ?? [];
  if (tokens.length <= 2 && tokens.some((token) => ["hi", "hello", "hey", "안녕", "안녕하세요", "하이"].includes(token))) {
    return false;
  }
  return true;
}

function signalTraceForQueryLegacy(query: string, graph: Rag3DGraph, result?: AnyRecord | null) {
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
    .split(/[^a-z0-9가-힣-]+/i)
    .filter((term) => term.length > 1);
  const activationTerms = [
    ...terms,
    ...memoryLabels.flatMap((label) => label.split(/[^a-z0-9가-힣]+/i)),
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
    .slice(0, 8);
  let retargeted = Boolean(memoryNodeIds.size && !visibleMemoryIds.length && activeNodeIds.length);
  if (!activeNodeIds.length) {
    const recentLiveIds = graph.nodes
      .filter((node) => node.id.startsWith("live-synapse"))
      .slice(-6)
      .map((node) => node.id);
    const traversalIds = (graph.traversal_path ?? [])
      .filter((id) => visibleNodeIds.has(id))
      .slice(-6);
    activeNodeIds = Array.from(new Set([...recentLiveIds, ...traversalIds])).slice(0, 8);
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
      .slice(0, 10)
      .map((edge) => `${edge.source}:${edge.target}`),
  ].filter((key, index, all) => all.indexOf(key) === index).slice(0, 12);
  const labels = activeNodeIds
    .map((id) => graph.nodes.find((node) => node.id === id)?.label ?? id)
    .slice(0, 6);
  const signalText = labels.length
    ? `${retargeted ? "활성 신호(대체 노드)" : "활성 노드"}: ${labels.join(", ")}`
    : "활성 신호 대기";
  return {
    edgeKeys: activeEdgeKeys,
    nodeIds: activeNodeIds,
    text: signalText,
  };
}

function edgeKeyFromParts(source: unknown, target: unknown) {
  if (!source || !target) return "";
  return `${String(source)}:${String(target)}`;
}

function signalTraceForQuery(query: string, graph: Rag3DGraph, result?: AnyRecord | null) {
  const visibleNodeIds = new Set(graph.nodes.map((node) => node.id));
  const visibleEdges = graph.edges;
  const memoryActiveNodes = (result?.memory_activation?.active_nodes ?? []) as AnyRecord[];
  const memoryActiveEdges = (result?.memory_activation?.active_edges ?? []) as AnyRecord[];
  const resultNodeIds = new Set<string>((result?.matched_nodes ?? []).map((node: AnyRecord) => String(node.id ?? "")).filter(Boolean));
  const graphPathIds = new Set<string>(
    (result?.graph_paths ?? [])
      .flatMap((path: AnyRecord) => Array.isArray(path) ? path : [])
      .filter(Boolean)
      .map(String),
  );
  const queryTerms = query
    .toLowerCase()
    .split(/[^a-z0-9가-힣-]+/i)
    .filter((term) => term.length > 1);
  const activeCandidates = new Set<string>();

  for (const node of memoryActiveNodes) {
    const id = String(node.id ?? "");
    if (visibleNodeIds.has(id)) activeCandidates.add(id);
  }
  for (const id of resultNodeIds) {
    if (visibleNodeIds.has(id)) activeCandidates.add(id);
  }
  for (const id of graphPathIds) {
    if (visibleNodeIds.has(id)) activeCandidates.add(id);
  }

  if (activeCandidates.size < 3 && queryTerms.length) {
    graph.nodes
      .map((node) => {
        const haystack = `${node.id} ${node.label} ${node.type}`.toLowerCase();
        const score = queryTerms.reduce((total, term) => total + (haystack.includes(term) ? 1 : 0), 0);
        return { id: node.id, score };
      })
      .filter((item) => item.score > 0)
      .sort((left, right) => right.score - left.score)
      .slice(0, 8)
      .forEach((item) => activeCandidates.add(item.id));
  }

  if (!activeCandidates.size) {
    for (const id of (graph.traversal_path ?? []).slice(-8)) {
      if (visibleNodeIds.has(id)) activeCandidates.add(id);
    }
  }

  const activeNodeIds = Array.from(activeCandidates).slice(0, 12);
  const activeNodeSet = new Set(activeNodeIds);
  const explicitMemoryEdgeKeys = memoryActiveEdges
    .map((edge) => edgeKeyFromParts(edge.source, edge.target))
    .filter((key) => {
      const [source, target] = key.split(":");
      return visibleNodeIds.has(source) && visibleNodeIds.has(target);
    });
  const visibleSignalEdges = visibleEdges
    .filter((edge) => activeNodeSet.has(edge.source) || activeNodeSet.has(edge.target))
    .slice(0, 24)
    .map((edge) => `${edge.source}:${edge.target}`);
  const activeEdgeKeys = [...explicitMemoryEdgeKeys, ...visibleSignalEdges]
    .filter((key, index, all) => key && all.indexOf(key) === index)
    .slice(0, 24);
  const labels = activeNodeIds
    .map((id) => graph.nodes.find((node) => node.id === id)?.label ?? id)
    .slice(0, 6);

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
    return <div className="chart-empty">?숈뒿 dry-run 湲곕줉 ?놁쓬</div>;
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
    <svg className="loss-chart" viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="?숈뒿 ?먯떎 怨≪꽑">
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
  return rawNodes.slice(0, 5000).map((node: AnyRecord, index: number) => ({
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
    .slice(0, 20000)
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
  const [workspaceMode, setWorkspaceMode] = useState<WorkspaceMode>("lab");
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
  const [learningDaemon, setLearningDaemon] = useState<AnyRecord | null>(null);
  const [edgeStatus, setEdgeStatus] = useState<AnyRecord | null>(defaultEdgeBrokerStatus);
  const [cloudBrainStatus, setCloudBrainStatus] = useState<AnyRecord | null>(null);
  const [cloudBrainSourceInspector, setCloudBrainSourceInspector] = useState<AnyRecord | null>(null);
  const [semanticCloudStatus, setSemanticCloudStatus] = useState<AnyRecord | null>(null);
  const [semanticGrowthRun, setSemanticGrowthRun] = useState<AnyRecord | null>(null);
  const [semanticAttachResult, setSemanticAttachResult] = useState<AnyRecord | null>(null);
  const [semanticGrowthRunning, setSemanticGrowthRunning] = useState(false);
  const [semanticGrowthError, setSemanticGrowthError] = useState<string | null>(null);
  const [graphHubStatus, setGraphHubStatus] = useState<AnyRecord | null>(null);
  const [graphHubCatalog, setGraphHubCatalog] = useState<AnyRecord[]>([]);
  const [graphHubInstalled, setGraphHubInstalled] = useState<AnyRecord[]>([]);
  const [graphHubAttachments, setGraphHubAttachments] = useState<AnyRecord[]>([]);
  const [graphHubAudit, setGraphHubAudit] = useState<AnyRecord[]>([]);
  const [graphHubExport, setGraphHubExport] = useState<AnyRecord | null>(null);
  const [graphHubProof, setGraphHubProof] = useState<AnyRecord | null>(null);
  const [graphHubPricingFilter, setGraphHubPricingFilter] = useState<string>("all");
  const [graphHubCategoryFilter, setGraphHubCategoryFilter] = useState<string>("all");
  const [graphHubTab, setGraphHubTab] = useState<"catalog" | "installed" | "attachments" | "export" | "audit">("catalog");
  const [graphHubSearch, setGraphHubSearch] = useState("");
  const [graphHubRunning, setGraphHubRunning] = useState<string | null>(null);
  const [graphHubError, setGraphHubError] = useState<string | null>(null);
  const [remoteCloudProof, setRemoteCloudProof] = useState<AnyRecord | null>(null);
  const [remoteCloudProofRunning, setRemoteCloudProofRunning] = useState(false);
  const [remoteCloudProofError, setRemoteCloudProofError] = useState<string | null>(null);
  const [cloudAttachmentStatus, setCloudAttachmentStatus] = useState<AnyRecord | null>(null);
  const [cloudAttachmentRunning, setCloudAttachmentRunning] = useState(false);
  const [cloudAttachmentError, setCloudAttachmentError] = useState<string | null>(null);
  const [brainGraphLocal, setBrainGraphLocal] = useState<AnyRecord | null>(null);
  const [brainGraphCloud, setBrainGraphCloud] = useState<AnyRecord | null>(null);
  const [brainGraphOverlayStatus, setBrainGraphOverlayStatus] = useState<AnyRecord | null>(null);
  const [brainGraphStatus, setBrainGraphStatus] = useState<AnyRecord | null>(null);
  const [localBrainGraphLayers, setLocalBrainGraphLayers] = useState<string[]>(["local_user", "working_memory_local", "local_base", "seed"]);
  const [cloudBrainGraphLayers, setCloudBrainGraphLayers] = useState<string[]>(["cloud_attached", "working_memory_cloud", "semantic_cloud"]);
  const [cloudDiagnosticsOpen, setCloudDiagnosticsOpen] = useState(false);
  const [controlledGrowthProof, setControlledGrowthProof] = useState<AnyRecord | null>(null);
  const [controlledGrowthRunning, setControlledGrowthRunning] = useState(false);
  const [controlledGrowthError, setControlledGrowthError] = useState<string | null>(null);
  const [cloudSphereStats, setCloudSphereStats] = useState<CloudBrainSphereStats | null>(null);
  const [cortexStatus, setCortexStatus] = useState<AnyRecord | null>(null);
  const [qCortexStatus, setQCortexStatus] = useState<AnyRecord | null>(null);
  const [baseBrainStatus, setBaseBrainStatus] = useState<AnyRecord | null>(null);
  const [baseBrainAnswer, setBaseBrainAnswer] = useState<AnyRecord | null>(null);
  const [baseBrainBenchmark, setBaseBrainBenchmark] = useState<AnyRecord | null>(null);
  const [baseBrainRunning, setBaseBrainRunning] = useState(false);
  const [baseBrainError, setBaseBrainError] = useState<string | null>(null);
  const [baseBrainQuery, setBaseBrainQuery] = useState("쿠버네티스가 뭐야?");
  const [answerQualityStatus, setAnswerQualityStatus] = useState<AnyRecord | null>(null);
  const [answerQualityRun, setAnswerQualityRun] = useState<AnyRecord | null>(null);
  const [answerQualityRunning, setAnswerQualityRunning] = useState(false);
  const [answerQualityError, setAnswerQualityError] = useState<string | null>(null);
  const [answerRepairComparison, setAnswerRepairComparison] = useState<AnyRecord | null>(null);
  const [answerRepairRunning, setAnswerRepairRunning] = useState(false);
  const [answerRepairError, setAnswerRepairError] = useState<string | null>(null);
  const [repairCandidates, setRepairCandidates] = useState<AnyRecord[]>([]);
  const [productionRepairRules, setProductionRepairRules] = useState<AnyRecord[]>([]);
  const [repairAuditEvents, setRepairAuditEvents] = useState<AnyRecord[]>([]);
  const [repairReviewRunning, setRepairReviewRunning] = useState(false);
  const [repairReviewError, setRepairReviewError] = useState<string | null>(null);
  const [brainSyncStatus, setBrainSyncStatus] = useState<AnyRecord | null>(null);
  const [cloudBudgetStatus, setCloudBudgetStatus] = useState<AnyRecord | null>(null);
  const [atlasStatus, setAtlasStatus] = useState<AnyRecord | null>(null);
  const [graphSourceMode, setGraphSourceMode] = useState<"build" | "memory">("memory");
  const [graphEdgeOpacity, setGraphEdgeOpacity] = useState(0.34);
  const [workbenchInfoOpen, setWorkbenchInfoOpen] = useState(false);
  const [chatInfoOpen, setChatInfoOpen] = useState(false);
  const [webSearchEnabled, setWebSearchEnabled] = useState(true);
  const [benchmark, setBenchmark] = useState<AnyRecord | null>(null);
  const [localBackendUrl, setLocalBackendUrl] = useState("http://127.0.0.1:8500");
  const [localBackendStatus, setLocalBackendStatus] = useState<"idle" | "checking" | "connected" | "failed">("idle");
  const [localBackendMessage, setLocalBackendMessage] = useState("배포 fallback 사용 중");
  const [language, setLanguage] = useState<Language>("en");
  const [mainSection, setMainSection] = useState<MainSectionId>("home");
  const [contributionEnabled, setContributionEnabled] = useState(() => readBrowserStorage("atanor.contribution.enabled") === "true");
  const [contributionPaused, setContributionPaused] = useState(false);
  const [contributionSafeMode, setContributionSafeMode] = useState(() => readBrowserStorage("atanor.contribution.safeMode") !== "false");
  const [contributionCpuLimit, setContributionCpuLimit] = useState(() => Number(readBrowserStorage("atanor.contribution.cpuLimit") ?? 20));
  const [contributionGpuLimit, setContributionGpuLimit] = useState(() => Number(readBrowserStorage("atanor.contribution.gpuLimit") ?? 0));
  const [contributionAllowPublic, setContributionAllowPublic] = useState(() => readBrowserStorage("atanor.contribution.publicFragments") !== "false");
  const [contributionChartTick, setContributionChartTick] = useState(0);
  const [contributionStatus, setContributionStatus] = useState<AnyRecord | null>(null);
  const [persistedLearningSeconds, setPersistedLearningSeconds] = useState(0);
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
  const [labStageProgress, setLabStageProgress] = useState<Record<LabStageKey, number>>({ collect: 0, learn: 0, output: 0 });
  const [activeLabStage, setActiveLabStage] = useState<LabStageKey>("collect");
  const [graphMode] = useState<"2d" | "3d">("3d");
  const [rag3dControl, setRag3dControl] = useState<Rag3DControl>({ serial: 0, action: "reset" });
  const graphRef = useRef<SVGSVGElement | null>(null);
  const chatScrollRef = useRef<HTMLDivElement | null>(null);
  const signalTimerRef = useRef<number | null>(null);
  const progressTimerRef = useRef<number | null>(null);
  const buildFrameTimerRef = useRef<number | null>(null);
  const benchmarkAppliedRef = useRef(false);
  const [graphView, setGraphView] = useState<GraphView>({ scale: 1, x: 0, y: 0 });
  const [dragState, setDragState] = useState<DragState | null>(null);
  const [atlasRotationDeg, setAtlasRotationDeg] = useState(0);
  const [atlasDragState, setAtlasDragState] = useState<AtlasDragState | null>(null);
  const [memoryQuery, setMemoryQuery] = useState("");
  const [chatInput, setChatInput] = useState(EFFECTIVE_INITIAL_CHAT_PROMPT.en);
  const [draft, setDraft] = useState("GraphRAG는 근거 문서와 지식 그래프 경로를 함께 읽어 답변 근거를 확인합니다.");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      text: EFFECTIVE_INITIAL_ASSISTANT_MESSAGE.en,
    },
  ]);
  const [error, setError] = useState<string | null>(null);
  const localBackendConnected = localBackendStatus === "connected";
  const localBackendDisplay = localBackendDisplayMessage(localBackendMessage, localBackendStatus, language);

  useEffect(() => {
    writeBrowserStorage("atanor.contribution.enabled", contributionEnabled ? "true" : "false");
    writeBrowserStorage("atanor.contribution.safeMode", contributionSafeMode ? "true" : "false");
    writeBrowserStorage("atanor.contribution.cpuLimit", String(contributionCpuLimit));
    writeBrowserStorage("atanor.contribution.gpuLimit", String(contributionGpuLimit));
    writeBrowserStorage("atanor.contribution.publicFragments", contributionAllowPublic ? "true" : "false");
  }, [contributionAllowPublic, contributionCpuLimit, contributionEnabled, contributionGpuLimit, contributionSafeMode]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.has("api") || params.has("backend")) return;
    const savedUrl = readBrowserStorage("atanor.localFastApiUrl");
    if (savedUrl) {
      setLocalBackendUrl(savedUrl);
      connectLocalBackend(savedUrl).catch(() => undefined);
    } else {
      connectLocalBackend("http://127.0.0.1:8500").catch(() => undefined);
    }
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const requestedLanguage = params.get("lang") ?? params.get("language");
    const initialLanguage = requestedLanguage === "ko" || requestedLanguage === "en"
      ? requestedLanguage
      : "en";
    setLanguage(initialLanguage);
    const requestedSection = params.get("section");
    const sectionIds: MainSectionId[] = ["home", "graph", "local", "cloud", "atlas", "graphhub", "contribute", "chat", "settings"];
    if (requestedSection && sectionIds.includes(requestedSection as MainSectionId)) {
      const nextSection = requestedSection as MainSectionId;
      setMainSection(nextSection);
      if (nextSection === "atlas") setWorkspaceMode("daemon");
      if (nextSection === "chat") setRightMode("chat");
      if (nextSection === "graph") setLayoutMode("graph");
    }
    const savedSeconds = Number(readBrowserStorage("atanor.cumulativeLearningSeconds") ?? "0");
    if (Number.isFinite(savedSeconds) && savedSeconds > 0) {
      setPersistedLearningSeconds(Math.floor(savedSeconds));
    }
  }, []);

  useEffect(() => {
    writeBrowserStorage("atanor.uiLanguage", language);
  }, [language]);

  useEffect(() => {
    setChatInput((current) => {
      if (current === EFFECTIVE_INITIAL_CHAT_PROMPT.en || current === EFFECTIVE_INITIAL_CHAT_PROMPT.ko || current === INITIAL_CHAT_PROMPT.en || current === INITIAL_CHAT_PROMPT.ko) {
        return EFFECTIVE_INITIAL_CHAT_PROMPT[language];
      }
      return current;
    });
    setChatMessages((messages) => {
      if (
        messages.length === 1
        && messages[0].role === "assistant"
        && (
          messages[0].text === EFFECTIVE_INITIAL_ASSISTANT_MESSAGE.en
          || messages[0].text === EFFECTIVE_INITIAL_ASSISTANT_MESSAGE.ko
          || messages[0].text === INITIAL_ASSISTANT_MESSAGE.en
          || messages[0].text === INITIAL_ASSISTANT_MESSAGE.ko
          || messages[0].text.includes("dry-run")
          || messages[0].text.includes("RAG 梨꾪똿 肄섏넄")
        )
      ) {
        return [{ role: "assistant", text: EFFECTIVE_INITIAL_ASSISTANT_MESSAGE[language] }];
      }
      return messages;
    });
  }, [language]);

  useEffect(() => {
    const daemonSeconds = Number(
      learningDaemon?.cumulative_learning_seconds
        ?? learningDaemon?.total_runtime_seconds
        ?? 0,
    );
    const liveSeconds = Math.floor(learningElapsedMs / 1000);
    const nextSeconds = Math.max(
      Number.isFinite(daemonSeconds) ? daemonSeconds : 0,
      Number.isFinite(liveSeconds) ? liveSeconds : 0,
    );
    if (nextSeconds <= 0) return;
    setPersistedLearningSeconds((current) => Math.max(current, Math.floor(nextSeconds)));
  }, [learningDaemon?.cumulative_learning_seconds, learningDaemon?.total_runtime_seconds, learningElapsedMs]);

  useEffect(() => {
    if (persistedLearningSeconds > 0) {
      writeBrowserStorage("atanor.cumulativeLearningSeconds", String(Math.floor(persistedLearningSeconds)));
    }
  }, [persistedLearningSeconds]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const requestedWorkspace = params.get("workspace") ?? params.get("view");
    const requestedApi = params.get("api") ?? params.get("backend");
    if (["daemon", "cumulative", "cloud", "cloud-brain", "cloudbrain"].includes(requestedWorkspace ?? "")) {
      setWorkspaceMode("daemon");
    } else if (requestedWorkspace === "lab") {
      setWorkspaceMode("lab");
    }
    if (requestedApi) {
      setLocalBackendUrl(requestedApi);
      connectLocalBackend(requestedApi).catch(() => undefined);
    }
  }, []);

  async function apiJson<T>(path: string, init?: RequestInit, options: { localOnly?: boolean; preferLocal?: boolean } = {}): Promise<T> {
    const shouldUseLocal = options.localOnly || options.preferLocal || localBackendConnected;
    if (shouldUseLocal) {
      try {
        return await directBackendJson<T>(localBackendUrl, path, init);
      } catch (caught) {
        if (options.localOnly) throw caught;
        try {
          const fallback = await fetchJson<T>(path, init);
          if (localBackendConnected) {
            setLocalBackendStatus("connected");
            setLocalBackendMessage("로컬 브레인 프록시 연결됨");
          }
          return fallback;
        } catch {
          // Continue to the existing health check so the user gets a precise status.
        }
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
      }
    }
    return fetchJson<T>(path, init);
  }

  async function syncLocalBackendState(url: string, benchmarkForStability?: AnyRecord | null) {
    const [
      memoryStatusResult,
      memoryGraphResult,
      memoryDriftResult,
      learningDaemonStatus,
      edgeBrokerStatus,
      brainSyncStatusResult,
      cloudBrainStatusResult,
      cloudBrainSourceInspectorResult,
      semanticCloudStatusResult,
      controlledGrowthProofResult,
      cloudBudgetStatusResult,
      atlasStatusResult,
      cortexStatusResult,
      qCortexStatusResult,
      baseBrainStatusResult,
      answerQualityStatusResult,
      brainGraphLocalResult,
      brainGraphCloudResult,
      brainGraphOverlayResult,
      brainGraphStatusResult,
      graphragStatus,
      guardStatus,
      ovenStatus,
      neuroStatus,
    ] = await Promise.all([
      directBackendJson<AnyRecord>(url, "/api/memory/status").catch(() => null),
      directBackendJson<AnyRecord>(url, "/api/memory/graph?limit=5000&include_cloud_attached=true").catch(() => null),
      directBackendJson<AnyRecord>(url, "/api/memory/drift-check").catch(() => null),
      directBackendJson<AnyRecord>(url, "/api/learning/daemon/status").catch(() => null),
      fetchJson<AnyRecord>(edgeStatusApiPath(url)).catch(() => null),
      directBackendJson<AnyRecord>(url, "/api/brain-sync/status").catch(() => null),
      directBackendJson<AnyRecord>(url, "/api/cloud-brain/status").catch(() => null),
      directBackendJson<AnyRecord>(url, "/api/cloud-brain/source-inspector").catch(() => null),
      directBackendJson<AnyRecord>(url, "/api/cloud-brain/semantic/status").catch(() => null),
      directBackendJson<AnyRecord>(url, "/api/cloud-brain/controlled-self-growth-proof").catch(() => null),
      directBackendJson<AnyRecord>(url, "/api/neuro/cloud-budget", {
        method: "POST",
        body: JSON.stringify({
          plan: "plus",
          contribution_active: true,
          contribution_score: 0.6,
          local_strength: 0.55,
          cloud_coverage: 0.72,
          seed_stability: 0.64,
          working_memory_capacity: 0.58,
          epistemic_confidence: 0.7,
          provider_healthy: true,
          remaining_budget_ratio: 1,
        }),
      }).catch(() => null),
      directBackendJson<AnyRecord>(url, "/api/neuro/atlas").catch(() => null),
      directBackendJson<AnyRecord>(url, "/api/cortex/status").catch(() => null),
      directBackendJson<AnyRecord>(url, "/api/q-cortex/status").catch(() => null),
      directBackendJson<AnyRecord>(url, "/api/base-brain/status").catch(() => null),
      directBackendJson<AnyRecord>(url, "/api/answer-quality/status").catch(() => null),
      directBackendJson<AnyRecord>(url, `/api/brain/graph?view=local&layers=${encodeURIComponent(localBrainGraphLayers.join(","))}&max_nodes=1000&max_edges=3000`).catch(() => null),
      directBackendJson<AnyRecord>(url, `/api/brain/graph?view=cloud&layers=${encodeURIComponent(cloudBrainGraphLayers.join(","))}&max_nodes=1000&max_edges=3000`).catch(() => null),
      directBackendJson<AnyRecord>(url, "/api/brain/overlay-status").catch(() => null),
      directBackendJson<AnyRecord>(url, "/api/brain/graph/status").catch(() => null),
      directBackendJson<AnyRecord>(url, "/api/graphrag/status").catch(() => null),
      directBackendJson<AnyRecord>(url, "/api/guard/status").catch(() => null),
      directBackendJson<AnyRecord>(url, "/api/oven/status").catch(() => null),
      directBackendJson<AnyRecord>(url, "/api/neuro/plan").catch(() => null),
    ]);
    if (memoryStatusResult) setMemoryStatus(memoryStatusResult);
    if (memoryGraphResult && ("nodes" in memoryGraphResult || "working_memory_overlay" in memoryGraphResult)) setGraph(memoryGraphResult);
    if (memoryDriftResult) setMemoryDrift(memoryDriftResult);
    if (learningDaemonStatus) setLearningDaemon(learningDaemonStatus);
    if (edgeBrokerStatus) setEdgeStatus(edgeBrokerStatus);
    if (brainSyncStatusResult) setBrainSyncStatus(brainSyncStatusResult);
    if (cloudBrainStatusResult) setCloudBrainStatus(cloudBrainStatusResult);
    if (cloudBrainSourceInspectorResult) setCloudBrainSourceInspector(cloudBrainSourceInspectorResult);
    if (semanticCloudStatusResult) setSemanticCloudStatus(semanticCloudStatusResult);
    if (controlledGrowthProofResult) setControlledGrowthProof(controlledGrowthProofResult);
    if (cloudBudgetStatusResult) setCloudBudgetStatus(cloudBudgetStatusResult);
    if (atlasStatusResult) setAtlasStatus(atlasStatusResult);
    if (cortexStatusResult) {
      setCortexStatus((current) => ({
        ...cortexStatusResult,
        last_cycle: cortexStatusResult.last_cycle ?? current?.last_cycle,
      }));
    }
    if (qCortexStatusResult) setQCortexStatus(qCortexStatusResult);
    if (baseBrainStatusResult) setBaseBrainStatus(baseBrainStatusResult);
    if (answerQualityStatusResult) setAnswerQualityStatus(answerQualityStatusResult);
    if (brainGraphLocalResult) setBrainGraphLocal(brainGraphLocalResult);
    if (brainGraphCloudResult) setBrainGraphCloud(brainGraphCloudResult);
    if (brainGraphOverlayResult) setBrainGraphOverlayStatus(brainGraphOverlayResult);
    if (brainGraphStatusResult) setBrainGraphStatus(brainGraphStatusResult);
    if (graphragStatus) setGraphRag(graphragStatus);
    if (guardStatus) setGuard(guardStatus);
    if (ovenStatus) setOven(ovenStatus);
    if (neuroStatus) setNeuro(neuroStatus);
    if (benchmarkForStability?.can_read_local_hardware) {
      const stabilityStatus = await directBackendJson<AnyRecord>(url, "/api/neuro/stability", {
        method: "POST",
        body: JSON.stringify(stabilityPayloadForVolume(
          learningVolume,
          targetNodeCount,
          benchmarkForStability.hardware_profile,
        )),
      }).catch(() => null);
      if (stabilityStatus) setStability(stabilityStatus);
    }
  }

  async function connectLocalBackend(candidateUrl = localBackendUrl) {
    const url = normalizeLocalBackendUrl(candidateUrl);
    setLocalBackendUrl(url);
    setLocalBackendStatus("checking");
    setLocalBackendMessage("로컬 브레인 동기화 중");
    try {
      try {
        await directBackendJson<AnyRecord>(url, "/health");
      } catch {
        const proxiedMemoryStatus = await fetchJson<AnyRecord>("/api/memory/status");
        setMemoryStatus(proxiedMemoryStatus);
      }
      setLocalBackendStatus("connected");
      setLocalBackendMessage("로컬 브레인 연결됨");
      writeBrowserStorage("atanor.localFastApiUrl", url);
      fetchJson<AnyRecord>(edgeStatusApiPath(url))
        .then((edgeBrokerStatus) => setEdgeStatus(edgeBrokerStatus))
        .catch(() => setEdgeStatus(defaultEdgeBrokerStatus));
      const [systemStatus, gpuStatus, benchmarkStatus] = await Promise.all([
        directBackendJson<AnyRecord>(url, "/api/telemetry/system").catch(() => null),
        directBackendJson<AnyRecord>(url, "/api/telemetry/gpu").catch(() => null),
        directBackendJson<AnyRecord>(url, "/api/neuro/benchmark", {
          method: "POST",
          body: JSON.stringify({ run_probes: true }),
        }).catch(() => null),
      ]);
      if (systemStatus) setSystem(systemStatus);
      if (gpuStatus) setGpu(gpuStatus);
      if (benchmarkStatus) setBenchmark(benchmarkStatus);
      await syncLocalBackendState(url, benchmarkStatus);
      const recommended = benchmarkStatus?.recommended_learning_volume as LearningVolume | undefined;
      let nextVolume = learningVolume;
      let nextTargetNodeCount = targetNodeCount;
      if (benchmarkStatus?.can_read_local_hardware && recommended && learningVolumePresets[recommended]) {
        nextVolume = recommended;
        nextTargetNodeCount = defaultTargetNodesForVolume(recommended);
        setLearningVolume(recommended);
        setTargetNodeCount(nextTargetNodeCount);
      }
      if (benchmarkStatus?.can_read_local_hardware) {
        const stabilityStatus = await directBackendJson<AnyRecord>(url, "/api/neuro/stability", {
          method: "POST",
          body: JSON.stringify(stabilityPayloadForVolume(
            nextVolume,
            nextTargetNodeCount,
            benchmarkStatus.hardware_profile,
          )),
        });
        setStability(stabilityStatus);
      }
    } catch (caught) {
      setLocalBackendStatus("failed");
      setLocalBackendMessage(localBackendErrorMessage(url, caught));
    }
  }

  function disconnectLocalBackend() {
    setLocalBackendStatus("idle");
    setLocalBackendMessage("배포 fallback 사용 중");
    removeBrowserStorage("atanor.localFastApiUrl");
  }

  async function refreshAll() {
    const localStrict = localBackendConnected ? { localOnly: true } : {};
    const benchmarkForRefresh = localBackendConnected
      ? await apiJson<AnyRecord>("/api/neuro/benchmark", {
        method: "POST",
        body: JSON.stringify({ run_probes: true }),
      }, { localOnly: true }).catch(() => benchmark)
      : benchmark;
    const [
      pipelineStatus,
      datagateStatus,
      ontologyStatus,
      ontologyGraph,
      memoryStatusResult,
      memoryGraphResult,
      memoryDriftResult,
      learningDaemonStatus,
      edgeBrokerStatus,
      cloudBrainStatusResult,
      cloudBrainSourceInspectorResult,
      semanticCloudStatusResult,
      controlledGrowthProofResult,
      cloudBudgetStatusResult,
      atlasStatusResult,
      cortexStatusResult,
      qCortexStatusResult,
      baseBrainStatusResult,
      answerQualityStatusResult,
      brainGraphLocalResult,
      brainGraphCloudResult,
      brainGraphOverlayResult,
      brainGraphStatusResult,
      graphragStatus,
      guardStatus,
      gpuStatus,
      systemStatus,
      ovenStatus,
      neuroStatus,
      stabilityStatus,
      contributionStatusResult,
    ] = await Promise.all([
      apiJson<PipelineStatus>("/api/pipeline/status"),
      apiJson<AnyRecord>("/api/datagate/status"),
      apiJson<AnyRecord>("/api/ontology/status"),
      apiJson<AnyRecord>("/api/ontology/graph"),
      apiJson<AnyRecord>("/api/memory/status"),
      fetchJson<AnyRecord>(graphStreamApiPath(localBackendUrl, 5000)).catch(() => apiJson<AnyRecord>("/api/memory/graph?limit=5000&include_cloud_attached=true", undefined, localStrict)),
      apiJson<AnyRecord>("/api/memory/drift-check"),
      apiJson<AnyRecord>("/api/learning/daemon/status"),
      fetchJson<AnyRecord>(edgeStatusApiPath(localBackendUrl)).catch(() => defaultEdgeBrokerStatus),
      apiJson<AnyRecord>("/api/cloud-brain/status"),
      apiJson<AnyRecord>("/api/cloud-brain/source-inspector"),
      apiJson<AnyRecord>("/api/cloud-brain/semantic/status"),
      apiJson<AnyRecord>("/api/cloud-brain/controlled-self-growth-proof"),
      apiJson<AnyRecord>("/api/neuro/cloud-budget", {
        method: "POST",
        body: JSON.stringify({
          plan: "plus",
          contribution_active: contributionEnabled && !contributionPaused,
          contribution_score: contributionEnabled && !contributionPaused ? 0.6 : 0,
          local_strength: contributionEnabled ? 0.55 : 0.78,
          cloud_coverage: contributionEnabled ? 0.72 : 0.28,
          seed_stability: 0.64,
          working_memory_capacity: 0.58,
          epistemic_confidence: contributionEnabled ? 0.7 : 0.45,
          provider_healthy: String(cloudBrainStatus?.broker_state ?? "") === "remote_connected",
          remaining_budget_ratio: 1,
        }),
      }),
      apiJson<AnyRecord>("/api/neuro/atlas"),
      localBackendConnected
        ? directBackendJson<AnyRecord>(localBackendUrl, "/api/cortex/status").catch(() => null)
        : Promise.resolve(null),
      localBackendConnected
        ? directBackendJson<AnyRecord>(localBackendUrl, "/api/q-cortex/status").catch(() => null)
        : apiJson<AnyRecord>("/api/q-cortex/status").catch(() => null),
      localBackendConnected
        ? directBackendJson<AnyRecord>(localBackendUrl, "/api/base-brain/status").catch(() => null)
        : apiJson<AnyRecord>("/api/base-brain/status").catch(() => null),
      localBackendConnected
        ? directBackendJson<AnyRecord>(localBackendUrl, "/api/answer-quality/status").catch(() => null)
        : apiJson<AnyRecord>("/api/answer-quality/status").catch(() => null),
      fetchJson<AnyRecord>(`/api/brain/graph?view=local&layers=${encodeURIComponent(localBrainGraphLayers.join(","))}&max_nodes=1000&max_edges=3000`).catch(() => null),
      fetchJson<AnyRecord>(`/api/brain/graph?view=cloud&layers=${encodeURIComponent(cloudBrainGraphLayers.join(","))}&max_nodes=1000&max_edges=3000`).catch(() => null),
      fetchJson<AnyRecord>("/api/brain/overlay-status").catch(() => null),
      fetchJson<AnyRecord>("/api/brain/graph/status").catch(() => null),
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
          benchmarkForRefresh?.can_read_local_hardware ? benchmarkForRefresh.hardware_profile : null,
        )),
      }),
      localBackendConnected
        ? directBackendJson<AnyRecord>(localBackendUrl, "/api/contribution/status").catch(() => null)
        : Promise.resolve(null),
    ]);
    setPipeline(pipelineStatus);
    setDatagate(datagateStatus);
    setOntology(ontologyStatus);
    setMemoryStatus(memoryStatusResult);
    setMemoryDrift(memoryDriftResult);
    setLearningDaemon(learningDaemonStatus);
    setEdgeStatus(edgeBrokerStatus);
    setCloudBrainStatus(cloudBrainStatusResult);
    setCloudBrainSourceInspector(cloudBrainSourceInspectorResult);
    setSemanticCloudStatus(semanticCloudStatusResult);
    setControlledGrowthProof(controlledGrowthProofResult);
    setCloudBudgetStatus(cloudBudgetStatusResult);
    setAtlasStatus(atlasStatusResult);
    setCortexStatus((current) => (
      cortexStatusResult
        ? { ...cortexStatusResult, last_cycle: cortexStatusResult.last_cycle ?? current?.last_cycle }
        : current
    ));
    setQCortexStatus((current) => qCortexStatusResult ?? current);
    setBaseBrainStatus((current) => baseBrainStatusResult ?? current);
    setAnswerQualityStatus((current) => answerQualityStatusResult ?? current);
    setBrainGraphLocal((current) => brainGraphLocalResult ?? current);
    setBrainGraphCloud((current) => brainGraphCloudResult ?? current);
    setBrainGraphOverlayStatus((current) => brainGraphOverlayResult ?? current);
    setBrainGraphStatus((current) => brainGraphStatusResult ?? current);
    setGraph(memoryGraphResult && ("nodes" in memoryGraphResult || "working_memory_overlay" in memoryGraphResult) ? memoryGraphResult : ontologyGraph);
    setGraphRag(graphragStatus);
    setGuard(guardStatus);
    setGpu(gpuStatus);
    setSystem(systemStatus);
    if (benchmarkForRefresh) setBenchmark(benchmarkForRefresh);
    setOven(ovenStatus);
    setNeuro(neuroStatus);
    setStability(stabilityStatus);
    setContributionStatus(contributionStatusResult);
  }

  async function runControlledGrowthProof() {
    setControlledGrowthRunning(true);
    setControlledGrowthError(null);
    try {
      const proof = await apiJson<AnyRecord>("/api/cloud-brain/prove-controlled-self-growth", {
        method: "POST",
      }, localBackendConnected ? { localOnly: true } : {});
      setControlledGrowthProof(proof);
      const nextCloudStatus = await apiJson<AnyRecord>("/api/cloud-brain/status", undefined, localBackendConnected ? { localOnly: true } : {});
      setCloudBrainStatus(nextCloudStatus);
    } catch (caught) {
      setControlledGrowthError(caught instanceof Error ? caught.message : "Controlled self-growth proof failed.");
    } finally {
      setControlledGrowthRunning(false);
    }
  }

  async function refreshSemanticCloud() {
    setSemanticGrowthError(null);
    const [status, cloudGraph] = await Promise.all([
      apiJson<AnyRecord>("/api/cloud-brain/semantic/status", undefined, localBackendConnected ? { localOnly: true } : {}),
      fetchJson<AnyRecord>(`/api/brain/graph?view=cloud&layers=${encodeURIComponent(cloudBrainGraphLayers.join(","))}&max_nodes=1000&max_edges=3000`).catch(() => null),
    ]);
    setSemanticCloudStatus(status);
    if (cloudGraph) setBrainGraphCloud(cloudGraph);
  }

  async function ingestSampleSemanticSource() {
    setSemanticGrowthRunning(true);
    setSemanticGrowthError(null);
    try {
      const summary = await apiJson<AnyRecord>("/api/cloud-brain/semantic/ingest", {
        method: "POST",
        body: JSON.stringify({
          text: "쿠버네티스는 컨테이너화된 애플리케이션을 자동으로 배포하고 관리하는 오픈소스 플랫폼입니다.",
          source_id: "ui-sample-kubernetes-ko",
          language: "ko",
          title: "ATANOR semantic growth sample",
          usage_allowed: false,
        }),
      }, localBackendConnected ? { localOnly: true } : {});
      setSemanticGrowthRun(summary);
      await refreshSemanticCloud();
    } catch (caught) {
      setSemanticGrowthError(caught instanceof Error ? caught.message : "Semantic Cloud ingest failed.");
    } finally {
      setSemanticGrowthRunning(false);
    }
  }

  async function attachSemanticCloudSample() {
    setSemanticGrowthRunning(true);
    setSemanticGrowthError(null);
    try {
      const attach = await apiJson<AnyRecord>("/api/cloud-brain/semantic/attach", {
        method: "POST",
        body: JSON.stringify({ query: "쿠버네티스가 뭐야?", limit: 8 }),
      }, localBackendConnected ? { localOnly: true } : {});
      setSemanticAttachResult(attach);
      const [overlay, memoryGraph, cloudGraph] = await Promise.all([
        fetchJson<AnyRecord>("/api/brain/overlay-status").catch(() => null),
        apiJson<AnyRecord>("/api/memory/graph?limit=5000&include_cloud_attached=true", undefined, localBackendConnected ? { localOnly: true } : {}).catch(() => null),
        fetchJson<AnyRecord>(`/api/brain/graph?view=cloud&layers=${encodeURIComponent(cloudBrainGraphLayers.join(","))}&max_nodes=1000&max_edges=3000`).catch(() => null),
      ]);
      if (overlay) setBrainGraphOverlayStatus(overlay);
      if (memoryGraph && ("nodes" in memoryGraph || "working_memory_overlay" in memoryGraph)) setGraph(memoryGraph);
      if (cloudGraph) setBrainGraphCloud(cloudGraph);
    } catch (caught) {
      setSemanticGrowthError(caught instanceof Error ? caught.message : "Semantic Cloud attach failed.");
    } finally {
      setSemanticGrowthRunning(false);
    }
  }

  async function refreshGraphHub() {
    setGraphHubError(null);
    const query = new URLSearchParams();
    if (graphHubPricingFilter !== "all") query.set("pricing_model", graphHubPricingFilter);
    if (graphHubSearch.trim()) query.set("query", graphHubSearch.trim());
    const suffix = query.toString() ? `?${query.toString()}` : "";
    const [status, catalog, installed, attachments, audit] = await Promise.all([
      apiJson<AnyRecord>("/api/graph-hub/status", undefined, localBackendConnected ? { localOnly: true } : {}).catch(() => null),
      apiJson<AnyRecord[]>(`/api/graph-hub/catalog${suffix}`, undefined, localBackendConnected ? { localOnly: true } : {}).catch(() => []),
      apiJson<AnyRecord[]>("/api/graph-hub/installed", undefined, localBackendConnected ? { localOnly: true } : {}).catch(() => []),
      apiJson<AnyRecord[]>("/api/graph-hub/attachments", undefined, localBackendConnected ? { localOnly: true } : {}).catch(() => []),
      apiJson<AnyRecord[]>("/api/graph-hub/audit?limit=20", undefined, localBackendConnected ? { localOnly: true } : {}).catch(() => []),
    ]);
    if (status) setGraphHubStatus(status);
    setGraphHubCatalog(Array.isArray(catalog) ? catalog : []);
    setGraphHubInstalled(Array.isArray(installed) ? installed : []);
    setGraphHubAttachments(Array.isArray(attachments) ? attachments : []);
    setGraphHubAudit(Array.isArray(audit) ? audit : []);
  }

  async function runGraphHubAction(action: string, path: string, body?: AnyRecord) {
    setGraphHubRunning(action);
    setGraphHubError(null);
    try {
      const result = await apiJson<AnyRecord>(path, {
        method: "POST",
        body: body ? JSON.stringify(body) : undefined,
      }, localBackendConnected ? { localOnly: true } : {});
      if (action === "export") setGraphHubExport(result);
      if (action === "proof") setGraphHubProof(result);
      await refreshGraphHub();
      const cloudGraph = await fetchJson<AnyRecord>(`/api/brain/graph?view=cloud&layers=${encodeURIComponent(cloudBrainGraphLayers.join(","))}&max_nodes=1000&max_edges=3000`).catch(() => null);
      if (cloudGraph) setBrainGraphCloud(cloudGraph);
    } catch (caught) {
      setGraphHubError(caught instanceof Error ? caught.message : "Graph Hub action failed.");
    } finally {
      setGraphHubRunning(null);
    }
  }

  async function runRemoteCloudBrainProof() {
    setRemoteCloudProofRunning(true);
    setRemoteCloudProofError(null);
    try {
      const result = await apiJson<AnyRecord>("/api/cloud-brain/prove-remote-cloud-brain", {
        method: "POST",
      }, localBackendConnected ? { localOnly: true } : {});
      const proof = (result.remote_proof && typeof result.remote_proof === "object" && !Array.isArray(result.remote_proof))
        ? result.remote_proof as AnyRecord
        : result;
      setRemoteCloudProof(proof);
      setCloudBrainSourceInspector(result);
      const nextCloudStatus = await apiJson<AnyRecord>("/api/cloud-brain/status", undefined, localBackendConnected ? { localOnly: true } : {});
      setCloudBrainStatus(nextCloudStatus);
    } catch (caught) {
      setRemoteCloudProofError(caught instanceof Error ? caught.message : "Remote Cloud Brain proof failed.");
    } finally {
      setRemoteCloudProofRunning(false);
    }
  }

  async function buildBaseBrainPack() {
    setBaseBrainRunning(true);
    setBaseBrainError(null);
    try {
      await fetchJson<AnyRecord>("/api/base-brain/build", {
        method: "POST",
      });
      const status = await fetchJson<AnyRecord>("/api/base-brain/status");
      setBaseBrainStatus(status);
    } catch (caught) {
      setBaseBrainError(caught instanceof Error ? caught.message : "Base Brain build failed.");
    } finally {
      setBaseBrainRunning(false);
    }
  }

  async function askBaseBrain() {
    setBaseBrainRunning(true);
    setBaseBrainError(null);
    try {
      const result = await fetchJson<AnyRecord>("/api/base-brain/answer", {
        method: "POST",
        body: JSON.stringify({
          query: baseBrainQuery,
          language,
          audience_level: "beginner",
          mode: "default",
        }),
      });
      setBaseBrainAnswer(result);
    } catch (caught) {
      setBaseBrainError(caught instanceof Error ? caught.message : "Base Brain answer failed.");
    } finally {
      setBaseBrainRunning(false);
    }
  }

  async function runBaseBrainBenchmark(limit = 10) {
    setBaseBrainRunning(true);
    setBaseBrainError(null);
    try {
      const result = await fetchJson<AnyRecord>("/api/base-brain/benchmark", {
        method: "POST",
        body: JSON.stringify({ limit }),
      });
      setBaseBrainBenchmark(result);
    } catch (caught) {
      setBaseBrainError(caught instanceof Error ? caught.message : "Base Brain benchmark failed.");
    } finally {
      setBaseBrainRunning(false);
    }
  }

  async function runAnswerQualityLab(limit = 8) {
    setAnswerQualityRunning(true);
    setAnswerQualityError(null);
    try {
      const result = await apiJson<AnyRecord>("/api/answer-quality/run", {
        method: "POST",
        body: JSON.stringify({
          benchmark_set: "core_ko_en_v1",
          limit,
        }),
      }, localBackendConnected ? { localOnly: true } : {});
      setAnswerQualityRun(result);
      setAnswerQualityStatus((current) => ({
        ...(current ?? {}),
        latest_run: result,
        state: "active",
      }));
    } catch (caught) {
      setAnswerQualityError(caught instanceof Error ? caught.message : "Answer Quality Lab failed.");
    } finally {
      setAnswerQualityRunning(false);
    }
  }

  async function runAnswerRepairComparison(limit = 8) {
    setAnswerRepairRunning(true);
    setAnswerRepairError(null);
    try {
      const result = await fetchJson<AnyRecord>("/api/answer-quality/run-repair-comparison", {
        method: "POST",
        body: JSON.stringify({
          benchmark_set: "core_ko_en_v1",
          limit,
        }),
      });
      setAnswerRepairComparison(result);
      writeBrowserStorage("atanor.latestAnswerRepairComparison", JSON.stringify(result));
    } catch (caught) {
      setAnswerRepairError(caught instanceof Error ? caught.message : "Repair comparison failed.");
    } finally {
      setAnswerRepairRunning(false);
    }
  }

  async function refreshRepairReviewQueue() {
    const [candidateResult, rulesResult, auditResult] = await Promise.all([
      fetchJson<AnyRecord>("/api/surface-brain/repair-candidates"),
      fetchJson<AnyRecord>("/api/surface-brain/production-rules"),
      fetchJson<AnyRecord>("/api/surface-brain/repair-audit?limit=8"),
    ]);
    setRepairCandidates(Array.isArray(candidateResult.candidates) ? candidateResult.candidates : []);
    setProductionRepairRules(Array.isArray(rulesResult.production_rules) ? rulesResult.production_rules : []);
    setRepairAuditEvents(Array.isArray(auditResult.events) ? auditResult.events : []);
  }

  async function generateRepairCandidatesFromFeedback() {
    if (!answerQualityFeedback.length) {
      setRepairReviewError(language === "ko" ? "먼저 Answer Quality Lab을 실행해 피드백을 생성하세요." : "Run Answer Quality Lab first to create feedback.");
      return;
    }
    setRepairReviewRunning(true);
    setRepairReviewError(null);
    try {
      await fetchJson<AnyRecord>("/api/surface-brain/feedback-to-repair-candidates", {
        method: "POST",
        body: JSON.stringify({
          run_id: String(latestAnswerQualityRun?.run_id ?? "ui-answer-quality-run"),
          feedback_items: answerQualityFeedback,
        }),
      });
      await refreshRepairReviewQueue();
    } catch (caught) {
      setRepairReviewError(caught instanceof Error ? caught.message : "Repair candidate generation failed.");
    } finally {
      setRepairReviewRunning(false);
    }
  }

  async function reviewCandidateAction(candidateId: string, action: "approve" | "reject") {
    setRepairReviewRunning(true);
    setRepairReviewError(null);
    try {
      await fetchJson<AnyRecord>(`/api/surface-brain/repair-candidates/${encodeURIComponent(candidateId)}/${action}`, {
        method: "POST",
        body: JSON.stringify({
          reviewer: "local_operator",
          comment: action === "approve" ? "Approved from ATANOR lab UI." : "Rejected from ATANOR lab UI.",
        }),
      });
      await refreshRepairReviewQueue();
    } catch (caught) {
      setRepairReviewError(caught instanceof Error ? caught.message : `Repair candidate ${action} failed.`);
    } finally {
      setRepairReviewRunning(false);
    }
  }

  async function rollbackProductionRepairRule(ruleId: string) {
    setRepairReviewRunning(true);
    setRepairReviewError(null);
    try {
      await fetchJson<AnyRecord>(`/api/surface-brain/production-rules/${encodeURIComponent(ruleId)}/rollback`, { method: "POST" });
      await refreshRepairReviewQueue();
    } catch (caught) {
      setRepairReviewError(caught instanceof Error ? caught.message : "Production rule rollback failed.");
    } finally {
      setRepairReviewRunning(false);
    }
  }

  useEffect(() => {
    if (workspaceMode !== "lab" || mainSection !== "cloud" || answerRepairComparison || answerRepairRunning) return;
    let cancelled = false;
    const saved = readBrowserStorage("atanor.latestAnswerRepairComparison");
    if (saved) {
      try {
        const parsed = JSON.parse(saved) as AnyRecord;
        if (parsed && parsed.run_id) {
          setAnswerRepairComparison(parsed);
          return () => {
            cancelled = true;
          };
        }
      } catch {
        writeBrowserStorage("atanor.latestAnswerRepairComparison", "");
      }
    }
    fetchJson<AnyRecord>("/api/answer-quality/repair-comparisons?limit=1")
      .then((result) => {
        if (cancelled) return;
        const rows = Array.isArray(result.repair_comparisons) ? result.repair_comparisons : [];
        if (rows[0]) {
          setAnswerRepairComparison(rows[0]);
          writeBrowserStorage("atanor.latestAnswerRepairComparison", JSON.stringify(rows[0]));
        }
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [answerRepairComparison, answerRepairRunning, mainSection, workspaceMode]);

  useEffect(() => {
    if (workspaceMode !== "lab" || mainSection !== "cloud") return;
    refreshRepairReviewQueue().catch(() => undefined);
  }, [mainSection, workspaceMode]);

  async function refreshBrainGraphPanels() {
    const [localResult, cloudResult, overlayResult, statusResult] = await Promise.all([
      fetchJson<AnyRecord>(`/api/brain/graph?view=local&layers=${encodeURIComponent(localBrainGraphLayers.join(","))}&max_nodes=1000&max_edges=3000`).catch(() => null),
      fetchJson<AnyRecord>(`/api/brain/graph?view=cloud&layers=${encodeURIComponent(cloudBrainGraphLayers.join(","))}&max_nodes=1000&max_edges=3000`).catch(() => null),
      fetchJson<AnyRecord>("/api/brain/overlay-status").catch(() => null),
      fetchJson<AnyRecord>("/api/brain/graph/status").catch(() => null),
    ]);
    if (localResult) setBrainGraphLocal(localResult);
    if (cloudResult) setBrainGraphCloud(cloudResult);
    if (overlayResult) setBrainGraphOverlayStatus(overlayResult);
    if (statusResult) setBrainGraphStatus(statusResult);
  }

  useEffect(() => {
    if (mainSection !== "local" && mainSection !== "cloud") return;
    refreshBrainGraphPanels().catch(() => undefined);
  }, [mainSection, localBrainGraphLayers, cloudBrainGraphLayers]);

  function toggleBrainGraphLayer(view: "local" | "cloud", layer: string) {
    const setter = view === "local" ? setLocalBrainGraphLayers : setCloudBrainGraphLayers;
    setter((current) => (
      current.includes(layer)
        ? current.filter((item) => item !== layer)
        : [...current, layer]
    ));
  }

  async function refreshGraphWithCloudOverlay() {
    const localStrict = localBackendConnected ? { localOnly: true } : {};
    const attachmentResult = await apiJson<AnyRecord>("/api/working-memory/cloud-attachments", undefined, localStrict).catch(() => null);
    if (attachmentResult) setCloudAttachmentStatus(attachmentResult);
    const graphResult = await fetchJson<AnyRecord>(graphStreamApiPath(localBackendUrl, 5000))
      .catch(() => apiJson<AnyRecord>("/api/memory/graph?limit=5000&include_cloud_attached=true", undefined, localStrict));
    if (graphResult && ("nodes" in graphResult || "working_memory_overlay" in graphResult)) setGraph(graphResult);
    return graphResult;
  }

  async function attachCloudContext() {
    setCloudAttachmentRunning(true);
    setCloudAttachmentError(null);
    try {
      const localStrict = localBackendConnected ? { localOnly: true } : {};
      const created = await apiJson<AnyRecord>("/api/working-memory/cloud-attachments/create", {
        method: "POST",
        body: JSON.stringify({ query: chatInput.trim() || memoryQuery.trim() || "GraphRAG evidence" }),
      }, localStrict);
      const bundleId = String((created.bundle as AnyRecord | undefined)?.bundle_id ?? "");
      if (!bundleId) throw new Error(String(created.reason ?? "No Cloud Node Bundle was created."));
      const attached = await apiJson<AnyRecord>("/api/working-memory/cloud-attachments/attach", {
        method: "POST",
        body: JSON.stringify({ bundle_id: bundleId }),
      }, localStrict);
      setCloudAttachmentStatus(attached);
      if (attached.cortex_g2 && typeof attached.cortex_g2 === "object" && !Array.isArray(attached.cortex_g2)) {
        setCortexStatus((current) => ({
          ...(current ?? {}),
          state: "active",
          last_cycle: attached.cortex_g2 as AnyRecord,
        }));
      }
      await refreshGraphWithCloudOverlay();
    } catch (caught) {
      setCloudAttachmentError(caught instanceof Error ? caught.message : "Cloud context attachment failed.");
    } finally {
      setCloudAttachmentRunning(false);
    }
  }

  async function detachCloudContext() {
    setCloudAttachmentRunning(true);
    setCloudAttachmentError(null);
    try {
      const localStrict = localBackendConnected ? { localOnly: true } : {};
      const activeIds = ((cloudAttachmentStatus?.working_memory_overlay as AnyRecord | undefined)?.bundle_ids as string[] | undefined)
        ?? (cloudAttachmentStatus?.active_bundle_ids as string[] | undefined)
        ?? ((graph?.working_memory_overlay as AnyRecord | undefined)?.bundle_ids as string[] | undefined)
        ?? [];
      for (const bundleId of activeIds) {
        await apiJson<AnyRecord>("/api/working-memory/cloud-attachments/detach", {
          method: "POST",
          body: JSON.stringify({ bundle_id: bundleId }),
        }, localStrict);
      }
      const listed = await apiJson<AnyRecord>("/api/working-memory/cloud-attachments", undefined, localStrict);
      setCloudAttachmentStatus(listed);
      await refreshGraphWithCloudOverlay();
      if (Number(listed.cloud_attached_nodes ?? 0) === 0) {
        setGraph((current) => ({
          ...(current ?? {}),
          nodes: [],
          edges: [],
          counts: {
            local_nodes: 0,
            local_edges: 0,
            seed_anchor_nodes: 0,
            cloud_attached_nodes: 0,
            cloud_attached_edges: 0,
          },
          working_memory_overlay: {
            active: false,
            bundle_ids: [],
            cloud_attached_nodes: 0,
            cloud_attached_edges: 0,
            seed_anchor_nodes: 0,
            writes_to_local_brain: false,
            detachable: true,
          },
          local_brain_empty: true,
          cloud_mirror_excluded_from_local_brain: true,
        }));
      }
    } catch (caught) {
      setCloudAttachmentError(caught instanceof Error ? caught.message : "Cloud context detach failed.");
    } finally {
      setCloudAttachmentRunning(false);
    }
  }

  async function clearCloudOverlay() {
    setCloudAttachmentRunning(true);
    setCloudAttachmentError(null);
    try {
      const localStrict = localBackendConnected ? { localOnly: true } : {};
      const cleared = await apiJson<AnyRecord>("/api/working-memory/cloud-attachments/clear", { method: "POST" }, localStrict);
      setCloudAttachmentStatus(cleared);
      await refreshGraphWithCloudOverlay();
      setGraph((current) => ({
        ...(current ?? {}),
        nodes: [],
        edges: [],
        counts: {
          local_nodes: 0,
          local_edges: 0,
          seed_anchor_nodes: 0,
          cloud_attached_nodes: 0,
          cloud_attached_edges: 0,
        },
        working_memory_overlay: {
          active: false,
          bundle_ids: [],
          cloud_attached_nodes: 0,
          cloud_attached_edges: 0,
          seed_anchor_nodes: 0,
          writes_to_local_brain: false,
          detachable: true,
        },
        local_brain_empty: true,
        cloud_mirror_excluded_from_local_brain: true,
      }));
    } catch (caught) {
      setCloudAttachmentError(caught instanceof Error ? caught.message : "Cloud overlay clear failed.");
    } finally {
      setCloudAttachmentRunning(false);
    }
  }

  useEffect(() => {
    refreshAll().catch((caught) => setError(caught instanceof Error ? caught.message : "BakeBoard瑜?遺덈윭?ㅼ? 紐삵뻽?듬땲??"));
    const timer = window.setInterval(() => {
      refreshAll().catch(() => undefined);
    }, 10000);
    return () => window.clearInterval(timer);
  }, [learningVolume, targetNodeCount, benchmark?.can_read_local_hardware, benchmark?.generated_at, localBackendConnected, localBackendUrl]);

  useEffect(() => {
    if (mainSection !== "local") return;
    refreshGraphWithCloudOverlay().catch(() => undefined);
  }, [mainSection, localBackendConnected, localBackendUrl]);

  useEffect(() => {
    if (mainSection !== "graphhub") return;
    refreshGraphHub().catch((caught) => setGraphHubError(caught instanceof Error ? caught.message : "Graph Hub refresh failed."));
  }, [mainSection, graphHubPricingFilter, localBackendConnected, localBackendUrl]);

  useEffect(() => {
    const updateClock = () => setClockNow(new Date());
    updateClock();
    const timer = window.setInterval(updateClock, 1000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    runHardwareBenchmark({ applyRecommendation: true }).catch((caught) => {
      setError(caught instanceof Error ? caught.message : "?쒖뒪??踰ㅼ튂留덊겕???ㅽ뙣?덉뒿?덈떎.");
    });
  }, []);

  useEffect(() => {
    if (rightMode !== "chat") return;
    window.requestAnimationFrame(() => {
      const chat = chatScrollRef.current;
      if (chat) chat.scrollTop = chat.scrollHeight;
    });
  }, [chatMessages, rightMode]);

  useEffect(() => () => {
    if (signalTimerRef.current !== null) window.clearTimeout(signalTimerRef.current);
    if (buildFrameTimerRef.current !== null) window.clearInterval(buildFrameTimerRef.current);
  }, []);

  useEffect(() => {
    if (!buildRun || !continuousLearningActive || layoutMode === "workbench") return;
    const timer = window.setInterval(() => {
      setBuildTick((tick) => {
        const isInfiniteRun = buildRun.learning_profile?.id === "infinite";
        return isInfiniteRun ? tick + 1 : tick;
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

  useEffect(() => () => {
    if (progressTimerRef.current !== null) window.clearInterval(progressTimerRef.current);
  }, []);

  async function runAction(action: () => Promise<unknown>) {
    setError(null);
    try {
      await action();
      await refreshAll();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "?묒뾽 ?ㅽ뻾???ㅽ뙣?덉뒿?덈떎.");
    }
  }

  function isLabStageKey(step: string): step is LabStageKey {
    return step === "collect" || step === "learn" || step === "output";
  }

  function setStageProgress(step: LabStageKey, progress: number) {
    setLabStageProgress((current) => ({ ...current, [step]: clamp(Math.round(progress), 0, 100) }));
  }

  async function runProcessAction(step: string, action: () => Promise<unknown>) {
    if (activeAction) return;
    const labStep = isLabStageKey(step) ? step : null;
    if (progressTimerRef.current !== null) {
      window.clearInterval(progressTimerRef.current);
      progressTimerRef.current = null;
    }
    if (labStep) {
      setStageProgress(labStep, 6);
      progressTimerRef.current = window.setInterval(() => {
        setLabStageProgress((current) => ({
          ...current,
          [labStep]: Math.min(92, current[labStep] + 7),
        }));
      }, 260);
    }
    setActiveAction(step);
    setError(null);
    try {
      await action();
      if (labStep) {
        setStageProgress(labStep, 100);
        if (labStep === "collect") setActiveLabStage("learn");
        if (labStep === "learn") setActiveLabStage("output");
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "?숈뒿 怨쇱젙 ?ㅽ뻾???ㅽ뙣?덉뒿?덈떎.");
    } finally {
      if (progressTimerRef.current !== null) {
        window.clearInterval(progressTimerRef.current);
        progressTimerRef.current = null;
      }
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
    const localStrict = localBackendConnected ? { localOnly: true } : {};
    const buildGraphCandidate = buildRun?.graph_3d?.nodes?.length
      ? {
        nodes: buildRun.graph_3d.nodes.map((node) => ({
          id: node.id,
          label: node.label,
          type: node.type,
          confidence: node.confidence ?? 0.75,
        })),
        edges: buildRun.graph_3d.edges.map((edge) => ({
          source: edge.source,
          target: edge.target,
          relation: edge.relation,
          confidence: edge.weight ?? 0.72,
        })),
      }
      : null;
    const previousEdgeKeys = new Set(
      ((graph?.edges ?? []) as AnyRecord[])
        .map((edge) => edgeKeyFromParts(edge.source, edge.target))
        .filter(Boolean),
    );
    const previousEdgeCount = Number(memoryStatus?.edge_count ?? graph?.edges?.length ?? 0);
    setMemoryStatus((current) => ({ ...(current ?? {}), state: "running" }));
    const result = await apiJson<AnyRecord>("/api/memory/build", { method: "POST" }, localStrict);
    const graphResult = await fetchJson<AnyRecord>(graphStreamApiPath(localBackendUrl, 5000)).catch(() => apiJson<AnyRecord>("/api/memory/graph?limit=5000&include_cloud_attached=true", undefined, localStrict));
    const driftResult = await apiJson<AnyRecord>("/api/memory/drift-check", undefined, localStrict);
    setMemoryStatus(result);
    setMemoryDrift(driftResult);
    if (graphResult?.nodes?.length) {
      const shouldKeepBuildGraph = Boolean(
        buildGraphCandidate && buildGraphCandidate.nodes.length >= graphResult.nodes.length,
      );
      const learnedGraph = shouldKeepBuildGraph ? buildGraphCandidate! : graphResult;
      setGraph(learnedGraph);
      setGraphSourceMode(shouldKeepBuildGraph ? "build" : "memory");
      const freshEdges = ((learnedGraph.edges ?? []) as AnyRecord[])
        .filter((edge) => {
          const key = edgeKeyFromParts(edge.source, edge.target);
          return key && !previousEdgeKeys.has(key);
        });
      const learnedEdges = shouldKeepBuildGraph && freshEdges.length === 0
        ? ((learnedGraph.edges ?? []) as AnyRecord[])
          .filter((edge) => Number(edge.confidence ?? 0) >= 0.68)
          .slice(0, 18)
        : freshEdges.slice(0, 18);
      const nextEdgeCount = Number(result?.edge_count ?? graphResult.edges?.length ?? 0);
      if ((nextEdgeCount > previousEdgeCount || shouldKeepBuildGraph) && learnedEdges.length > 0) {
        const learnedTrace = {
          edgeKeys: learnedEdges.map((edge) => edgeKeyFromParts(edge.source, edge.target)).filter(Boolean),
          nodeIds: Array.from(new Set(learnedEdges.flatMap((edge) => [String(edge.source), String(edge.target)]))).slice(0, 16),
          text: shouldKeepBuildGraph
            ? `?숈뒿 愿怨??뺤씤: ???洹몃옒??愿怨?${learnedEdges.length}媛쒕? ?쒖꽦?뷀뻽?듬땲??`
            : `?숈뒿 愿怨??뺤젙: ??愿怨?${learnedEdges.length}媛쒓? 硫붾え由ъ뿉 ??λ릱?듬땲??`,
        };
        window.setTimeout(() => activateSignal(learnedTrace, 12000), 80);
      } else {
        setSignalTraceText("?숈뒿 ?꾨즺: ???곌껐 蹂???놁쓬");
      }
    }
  }

  async function runLearningStage() {
    setLabStageProgress((current) => ({ ...current, output: 0 }));
    await runOntologyStep();
    await runMemoryBuildStep();
    await refreshStabilityPlan();
  }

  async function startLearningDaemon() {
    const result = await apiJson<AnyRecord>("/api/learning/daemon/start", {
      method: "POST",
      body: JSON.stringify({ interval_seconds: 30, resume: true }),
    });
    setLearningDaemon(result);
    await refreshAll().catch(() => undefined);
  }

  async function resumeLearningDaemon() {
    const result = await apiJson<AnyRecord>("/api/learning/daemon/resume", {
      method: "POST",
      body: JSON.stringify({ interval_seconds: 30, resume: true }),
    });
    setLearningDaemon(result);
    await refreshAll().catch(() => undefined);
  }

  async function stopLearningDaemon() {
    const result = await apiJson<AnyRecord>("/api/learning/daemon/stop", {
      method: "POST",
      body: JSON.stringify({ reason: "user_request" }),
    });
    setLearningDaemon(result);
    await refreshAll().catch(() => undefined);
  }

  async function checkpointLearningDaemon() {
    const result = await apiJson<AnyRecord>("/api/learning/daemon/checkpoint", {
      method: "POST",
      body: JSON.stringify({ reason: "user_request" }),
    });
    setLearningDaemon(result);
    await refreshAll().catch(() => undefined);
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

  function clearActiveSignal() {
    if (signalTimerRef.current !== null) {
      window.clearTimeout(signalTimerRef.current);
      signalTimerRef.current = null;
    }
    setActiveSignalEdgeKeys([]);
    setActiveSignalNodeIds([]);
    setSignalTraceText("활성 신호 대기");
  }

  function replayBuildFrames(run: BuildRun) {
    if (buildFrameTimerRef.current !== null) {
      window.clearInterval(buildFrameTimerRef.current);
      buildFrameTimerRef.current = null;
    }
    const frameCount = Math.max(1, run.graph_frames?.length ?? 1);
    setBuildTick(0);
    if (frameCount <= 1) return;
    let frameIndex = 0;
    buildFrameTimerRef.current = window.setInterval(() => {
      frameIndex += 1;
      setBuildTick(Math.min(frameIndex, frameCount - 1));
      if (frameIndex >= frameCount - 1 && buildFrameTimerRef.current !== null) {
        window.clearInterval(buildFrameTimerRef.current);
        buildFrameTimerRef.current = null;
      }
    }, 620);
  }

  async function sendChat() {
    const question = chatInput.trim();
    if (!question || isGeneratingAnswer) return;
    setError(null);
    setIsGeneratingAnswer(true);
    if (learnComplete) setStageProgress("output", Math.max(8, labStageProgress.output));
    activateSignal(signalTraceForQuery(question, displayGraph3D), 15000);
    setChatMessages((messages) => [...messages, { role: "user", text: question }]);
    try {
      const shouldUseWebSearch = shouldUseWebSearchForQuestion(question, webSearchEnabled);
      const result = await apiJson<AnyRecord>("/api/chat/atanor", {
        method: "POST",
        body: JSON.stringify({
          question,
          web_search: shouldUseWebSearch,
          brain_mode: mainSection === "local" ? "local" : mainSection === "cloud" ? "cloud" : "unified",
          language,
          audience_level: "beginner",
          tone: "clear",
          mode: "default",
          include_trace: true,
        }),
      });
      setGraphRag(result);
      const apiResult = result?.result;
      const answerKind = String(apiResult?.answer_kind ?? "");
      const isConversationResult =
        apiResult?.method === "atanor-conversation-router-v1" || ["greeting", "thanks", "conversation"].includes(answerKind);
      if (isConversationResult) {
        clearActiveSignal();
      } else {
        activateSignal(signalTraceForQuery(question, displayGraph3D, apiResult), 15000);
      }
      const evidence = result?.result?.evidence_docs ?? [];
      const nodes = result?.result?.matched_nodes ?? [];
      const answer = result?.result?.answer;
      const nodeText = nodes.length ? nodes.map((node: AnyRecord) => node.label).join(", ") : "현재 메모리";
      if (answer) {
        setDraft(answer);
        try {
          const guardResult = await apiJson<AnyRecord>("/api/guard/check", {
            method: "POST",
            body: JSON.stringify({ draft_answer: answer, evidence_bundle: result?.result ?? null }),
          });
          setGuard(guardResult);
        } catch {
          // Guardrail is an automatic output check; answer generation should not fail if the check is unavailable.
        }
      }
      setChatMessages((messages) => [
        ...messages,
        {
          role: "assistant",
          text: answer ?? `NO_ANSWER\nnodes=${nodeText}\nevidence_docs=${evidence.length}`,
          evidence,
          diagnostics: {
            compact_trace: apiResult?.compact_trace,
            surface_plan: apiResult?.surface_plan,
            answer_engine: apiResult?.answer_engine,
            native_generation_failed_quality_check: apiResult?.native_generation_failed_quality_check ?? apiResult?.answer_engine?.diagnostics?.native_generation_failed_quality_check,
            degeneration: apiResult?.degeneration ?? apiResult?.answer_engine?.diagnostics?.degeneration,
            native_stop_reason: apiResult?.native_stop_reason ?? apiResult?.answer_engine?.diagnostics?.native_stop_reason,
            training_feedback_recorded: apiResult?.training_feedback_recorded ?? apiResult?.answer_engine?.diagnostics?.training_feedback_recorded,
          },
        },
      ]);
      if (learnComplete) setStageProgress("output", 100);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "RAG 梨꾪똿???ㅽ뙣?덉뒿?덈떎.");
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
      setError(caught instanceof Error ? caught.message : "寃利앹뿉 ?ㅽ뙣?덉뒿?덈떎.");
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
      setError(caught instanceof Error ? caught.message : "?⑥쑉 怨꾪쉷 怨꾩궛???ㅽ뙣?덉뒿?덈떎.");
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
      setError(caught instanceof Error ? caught.message : "吏???댁쟾 怨꾪쉷 怨꾩궛???ㅽ뙣?덉뒿?덈떎.");
    }
  }

  function stopContinuousLearning(reason?: string) {
    const elapsed = learningStartedAt ? Date.now() - learningStartedAt : learningElapsedMs;
    setContinuousLearningActive(false);
    setLearningElapsedMs(elapsed);
    const reasonText = reason ? ` ?덉쟾 以묒? ?ъ쑀: ${reason}.` : "";
    setChatMessages((messages) => [
      ...messages,
      {
        role: "assistant",
        text: `??吏???숈뒿??硫덉톬?듬땲??${reasonText} ?꾩쟻 ?숈뒿 ?쒓컙? ${formatDuration(elapsed)}?닿퀬, ?꾩옱 ?붾㈃?먮뒗 ????⑦넧濡쒖? ?몃뱶 ${displayGraph3D.nodes.length}媛쒖? 愿怨?${displayGraph3D.edges.length}媛쒓? ?⑥븘 ?덉뒿?덈떎.`,
      },
    ]);
  }

  async function startFactoryBuild() {
    setError(null);
    if (learningVolume === "infinite" && resourceStopReason) {
      setError(`?덉쟾 議곌굔 ?뚮Ц?????숈뒿???쒖옉?섏? ?딆븯?듬땲?? ${resourceStopReason}`);
      setChatMessages((messages) => [
        ...messages,
        { role: "assistant", text: `??吏???숈뒿 ?쒖옉 ???덉쟾 ?먭??먯꽌 硫덉톬?듬땲?? ?ъ쑀: ${resourceStopReason}.` },
      ]);
      return;
    }
    setIsBuilding(true);
    const startedAt = Date.now();
    setLearningStartedAt(startedAt);
    setLearningElapsedMs(0);
    setContinuousLearningActive(false);
    setBuildTick(0);
    setLabStageProgress((current) => ({ ...current, collect: Math.max(current.collect, 6), learn: 0, output: 0 }));
    setActiveLabStage("collect");
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
      replayBuildFrames(run);
      setGraphSourceMode("build");
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
      if (isInfiniteRun) {
        setChatMessages((messages) => [
          ...messages,
          {
            role: "assistant",
            text: `지속 학습을 시작했습니다. 중지 버튼을 누르기 전까지 수집 라운드와 온톨로지 성장 이벤트를 계속 누적하고, 화면에는 최근/대표 노드를 최대 ${run.training_gate.visual_node_budget ?? run.graph_3d.nodes.length}개까지 안정적으로 표시합니다.`,
          },
        ]);
      }
    } catch (caught) {
      setContinuousLearningActive(false);
      setError(caught instanceof Error ? caught.message : "鍮뚮뱶 ?쒖옉???ㅽ뙣?덉뒿?덈떎.");
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
  const fusionRatio = graphResult?.fusion_ratio ?? graphResult?.retrieval_trace?.fusion_ratio ?? null;
  const localWeightPct = Math.round(Number(fusionRatio?.local_weight ?? fusionRatio?.local ?? 1) * 100);
  const cloudWeightPct = Math.round(Number(fusionRatio?.cloud_weight ?? fusionRatio?.cloud ?? 0) * 100);
  const fusionDisplayText = fusionRatio
    ? `Local ${localWeightPct}% / Cloud ${cloudWeightPct}%`
    : "Local 100% / Cloud 0%";
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
          node_count: buildRun.graph_3d.nodes.length + growthPulseCount * liveGrowthBatchSize,
          edge_count: buildRun.graph_3d.edges.length + growthPulseCount * liveGrowthBatchSize * 2,
          message:
            buildIsInfinite
              ? `${continuousLearningActive ? "??吏???숈뒿" : "???숈뒿 ?뺤?"} ${learningElapsedText}: ?섏쭛 ?쇱슫??${growthPulseCount} / ?꾩쟻 ?꾨낫 ${accumulatedLearningNodes.toLocaleString()} ?몃뱶`
              : rawGrowthPulseCount > growthPulseCount
              ? `洹몃옒??寃??紐⑤뱶: ${growthPulseCount}媛??꾩뒪?먯꽌 ?덉젙?뷀뻽?듬땲??`
              : `?ㅼ떆媛??숈뒿 ?꾩뒪 ${growthPulseCount}: ???쒕깄?ㅺ? 湲곗뼲留앹뿉 ?곌껐?섏뿀?듬땲??`,
        }
      : buildRun.graph_frames?.[Math.min(buildTick, buildRun.graph_frames.length - 1)] ?? null
    : null;
  const activeGraph3D = useMemo<Rag3DGraph | null>(() => {
    if (!buildRun?.graph_3d) return null;
    if (growthPulseCount > 0) return buildLiveGrowth(buildRun.graph_3d, growthPulseCount, Number.POSITIVE_INFINITY);
    const visibleNodeCount = activeBuildFrame?.node_count ?? buildRun.graph_3d.nodes.length;
    const nodeIds = new Set(buildRun.graph_3d.nodes.slice(0, visibleNodeCount).map((node) => node.id));
    return {
      nodes: buildRun.graph_3d.nodes.filter((node) => nodeIds.has(node.id)),
      edges: buildRun.graph_3d.edges.filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target)),
      traversal_path: buildRun.graph_3d.traversal_path?.filter((id) => nodeIds.has(id)),
    };
  }, [activeBuildFrame?.node_count, buildIsInfinite, buildRun, buildTargetNodes, growthPulseCount, visualNodeCap]);

  const graphPresentationMode = graphPresentationModeForSection(mainSection);
  const localGraphState = (cloudBrainStatus?.local_graph_state && typeof cloudBrainStatus.local_graph_state === "object" && !Array.isArray(cloudBrainStatus.local_graph_state))
    ? cloudBrainStatus.local_graph_state as AnyRecord
    : null;
  const localBrainInitialized = Boolean(localGraphState?.local_brain_initialized);
  const emptyLocalBrainGraph3D = useMemo<Rag3DGraph>(() => ({ nodes: [], edges: [], traversal_path: [] }), []);
  const earlyWorkingMemoryOverlay = (graph?.working_memory_overlay && typeof graph.working_memory_overlay === "object" && !Array.isArray(graph.working_memory_overlay))
    ? graph.working_memory_overlay as AnyRecord
    : {};
  const earlyCloudAttachmentOverlay = (cloudAttachmentStatus?.working_memory_overlay && typeof cloudAttachmentStatus.working_memory_overlay === "object" && !Array.isArray(cloudAttachmentStatus.working_memory_overlay))
    ? cloudAttachmentStatus.working_memory_overlay as AnyRecord
    : {};
  const localWorkingMemoryOverlayActive = Boolean(earlyWorkingMemoryOverlay.active)
    || Number(earlyWorkingMemoryOverlay.cloud_attached_nodes ?? 0) > 0
    || Number(earlyWorkingMemoryOverlay.seed_anchor_nodes ?? 0) > 0
    || Boolean(earlyCloudAttachmentOverlay.active)
    || Number(earlyCloudAttachmentOverlay.cloud_attached_nodes ?? (cloudAttachmentStatus?.cloud_attached_nodes ?? 0)) > 0
    || Number(earlyCloudAttachmentOverlay.seed_anchor_nodes ?? 0) > 0;
  const activeTabBrainGraphRaw = mainSection === "cloud"
    ? brainGraphCloud
    : mainSection === "local"
      ? brainGraphLocal
      : null;
  const tabBrainGraphPending = (mainSection === "local" || mainSection === "cloud") && !activeTabBrainGraphRaw;
  const tabBrainGraph3D = useMemo(() => buildBrainLayerGraph3D(activeTabBrainGraphRaw), [activeTabBrainGraphRaw]);
  const sectionMemoryGraph3D = mainSection === "cloud"
    ? tabBrainGraph3D
    : mainSection === "local"
      ? (graphPresentationMode === "local_private_memory" && !localBrainInitialized && !localWorkingMemoryOverlayActive && tabBrainGraph3D.nodes.length === 0
          ? emptyLocalBrainGraph3D
          : tabBrainGraph3D)
      : memoryGraph3D;
  const displayGraph3D = graphSourceMode === "memory" ? sectionMemoryGraph3D : activeGraph3D ?? sectionMemoryGraph3D;
  const collectionDisplayNodeCount = buildRun ? activeGraph3D?.nodes.length ?? buildRun.graph_3d.nodes.length : displayGraph3D.nodes.length;
  const totalLiveNodeCount = buildRun ? rawGrowthPulseCount * liveGrowthBatchSize : 0;
  const visibleLiveNodeCount = displayGraph3D.nodes.filter((node) => node.id.startsWith("live-synapse")).length;
  const preservedAnchorNodeCount = buildRun?.graph_3d?.nodes.length ?? displayGraph3D.nodes.length;
  const newestLiveNodeId = totalLiveNodeCount > 0 ? `live-synapse-${totalLiveNodeCount}` : null;
  const representativeCapReached = Boolean(buildRun && displayGraph3D.nodes.length >= visualNodeCap);
  const representativeTargetPercent = buildRun && !buildIsInfinite ? percent(representativeNodeCount, buildTargetNodes) : 0;
  const renderedTargetPercent = buildRun && !buildIsInfinite ? percent(displayGraph3D.nodes.length, buildTargetNodes) : 0;
  const graphOverlayMessage = graphSourceMode === "build"
    ? buildFrameMessageText(activeBuildFrame?.message)
    : buildRun
      ? "?숈뒿 ?④퀎媛 ???洹몃옒?꾩쓽 愿怨꾨? ?뺤씤?덉뒿?덈떎."
      : "鍮뚮뱶 ?쒖옉???꾨Ⅴ硫??몃뱶媛 ?뚯깮?⑸땲??";
  const daemonCanOperate = learningDaemon?.mode === "local-daemon";
  const daemonGraphReady = workspaceMode !== "daemon" || (localBackendConnected && daemonCanOperate && Boolean(learningDaemon?.worker_alive));
  const graphSyncPending = workspaceMode === "lab"
    && graphSourceMode === "memory"
    && !localBackendConnected
    && localBackendStatus !== "failed"
    && !buildRun;
  const graphLooksLikeTinyFallback = workspaceMode === "lab"
    && graphSourceMode === "memory"
    && mainSection !== "cloud"
    && mainSection !== "local"
    && localBackendStatus !== "failed"
    && !buildRun
    && !localWorkingMemoryOverlayActive
    && displayGraph3D.nodes.length > 0
    && displayGraph3D.nodes.length <= 12;
  const visibleGraph3D = daemonGraphReady && !graphSyncPending && !graphLooksLikeTinyFallback ? displayGraph3D : { nodes: [], edges: [], traversal_path: [] };
  const ragVisualState: Rag3DVisualState = !visibleGraph3D.nodes.length
    ? "idle"
    : isBuilding || continuousLearningActive || activeAction === "collect" || activeAction === "learn"
      ? "learning"
      : isGeneratingAnswer || activeSignalNodeIds.length || activeSignalEdgeKeys.length
        ? "activating"
        : graphSourceMode === "build" && buildRun
          ? "completed"
          : "idle";

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
    if (graphSourceMode === "memory") return;
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
  }, [activeGraph3D, buildRun, graphSourceMode]);

  const displayMemoryNodeCount = visibleGraph3D.nodes.length;
  const displayMemoryEdgeCount = visibleGraph3D.edges.length;
  const graphHeaderNodeCount = displayMemoryNodeCount;
  const graphHeaderEdgeCount = displayMemoryEdgeCount;
  const graphHeaderNodeText = tabBrainGraphPending ? "..." : graphHeaderNodeCount.toLocaleString();
  const graphHeaderEdgeText = tabBrainGraphPending ? "..." : graphHeaderEdgeCount.toLocaleString();
  const graphEmptyTitle = tabBrainGraphPending
    ? (language === "ko" ? "그래프 동기화 중" : "Syncing graph")
    : localBackendDisplay;
  const graphEmptySubtitle = tabBrainGraphPending
    ? (mainSection === "local"
      ? (language === "ko" ? "Seed Graph와 Base Brain 레이어를 불러오고 있습니다" : "Loading Seed Graph and Base Brain layers")
      : (language === "ko" ? "Semantic Cloud proof store를 확인하고 있습니다" : "Checking Semantic Cloud proof store"))
    : localBackendStatus === "checking"
      ? (language === "ko" ? "Ghost Shell 주소록을 깨우고 있습니다" : "Waking Ghost Shell topology")
      : (language === "ko" ? "로컬 Companion 응답 대기" : "Waiting for local Companion");
  const studioGraph3D = useMemo(() => buildStudioTopologyGraph(visibleGraph3D), [visibleGraph3D]);
  const sphereGraph3D = useMemo(() => buildSphericalTopologyGraph(visibleGraph3D, graphPresentationMode), [visibleGraph3D, graphPresentationMode]);
  const usesStudioGraph = mainSection === "home";
  const usesSphereGraph = mainSection === "graph" || mainSection === "local" || mainSection === "cloud" || mainSection === "chat";
  const userSceneGraph3D = usesStudioGraph ? studioGraph3D : usesSphereGraph ? sphereGraph3D : studioGraph3D;
  const energyReduction = asPercent(neuro?.energy_estimate?.reduction_ratio);
  const eventSparsity = asPercent(neuro?.event_gate?.sparsity);
  const ramSoftGb = stability?.runtime_envelope?.ram_soft_gb ?? 23;
  const vramSoftGb = stability?.runtime_envelope?.vram_soft_gb ?? 12;
  const hotWindowNodes = stability?.graph_policy?.hot_window_nodes ?? 2048;
  const uiRenderNodes = stability?.graph_policy?.ui_render_nodes ?? 240;
  const telemetryLabel = telemetrySourceText(system, benchmark);
  const edgeTierLabel = String(edgeStatus?.capacity?.tier ?? "unknown").replace(/^tier_/, "T").replace(/_/g, "-").toUpperCase();
  const edgeBrokerState = edgeStatus?.capacity?.idle
    ? "idle"
    : edgeStatus?.state === "viewer_only"
      ? "viewer"
      : edgeStatus?.state ?? "waiting";
  const edgeBrokerLabel = `Edge ${edgeTierLabel} 쨌 Broker ${edgeBrokerState}`;
  const cloudRemoteConfig = (cloudBrainStatus?.remote_config && typeof cloudBrainStatus.remote_config === "object" && !Array.isArray(cloudBrainStatus.remote_config))
    ? cloudBrainStatus.remote_config as AnyRecord
    : null;
  const cloudRemoteStatus = (cloudBrainStatus?.remote_status && typeof cloudBrainStatus.remote_status === "object" && !Array.isArray(cloudBrainStatus.remote_status))
    ? cloudBrainStatus.remote_status as AnyRecord
    : null;
  const cloudProviderName = String(cloudBrainStatus?.cloud_provider ?? cloudRemoteStatus?.provider ?? "local");
  const cloudBrokerState = String(cloudBrainStatus?.broker_state ?? "local_broker_mode");
  const cloudEndpointLabel = String(cloudRemoteConfig?.endpoint ?? "").includes("workers.dev")
    ? "Cloudflare Workers"
    : cloudRemoteConfig?.endpoint ? "Remote endpoint" : "Local broker";
  const cloudBudget = (cloudBudgetStatus?.cloud_budget && typeof cloudBudgetStatus.cloud_budget === "object" && !Array.isArray(cloudBudgetStatus.cloud_budget))
    ? cloudBudgetStatus.cloud_budget as AnyRecord
    : null;
  const cloudBalance = (cloudBudgetStatus?.actual_context_balance && typeof cloudBudgetStatus.actual_context_balance === "object" && !Array.isArray(cloudBudgetStatus.actual_context_balance))
    ? cloudBudgetStatus.actual_context_balance as AnyRecord
    : (cloudBudgetStatus?.planned_balance && typeof cloudBudgetStatus.planned_balance === "object" && !Array.isArray(cloudBudgetStatus.planned_balance))
      ? cloudBudgetStatus.planned_balance as AnyRecord
      : null;
  const cloudBudgetPlan = String(cloudBudgetStatus?.plan ?? cloudBudget?.plan ?? "free");
  const cloudBudgetRequests = Number(cloudBudget?.effective_fragment_requests_per_day ?? cloudBudget?.cloud_fragment_requests_per_day ?? 0);
  const syncLocalWeight = typeof brainSyncStatus?.local_weight === "number" ? brainSyncStatus.local_weight : null;
  const syncCloudWeight = typeof brainSyncStatus?.cloud_weight === "number" ? brainSyncStatus.cloud_weight : null;
  const budgetLocalPct = Math.round(Number(syncLocalWeight ?? cloudBalance?.local ?? 1) * 100);
  const budgetCloudPct = Math.round(Number(syncCloudWeight ?? cloudBalance?.cloud ?? 0) * 100);
  const resourceStopReason = resourcePressureReason(system, gpu, stability, benchmark);
  const diskFreeGb = numeric(system?.disk_free_gb);
  const ramUsedGb = numeric(system?.ram_used_gb);
  const vramUsedGb = numeric(gpu?.vram_used) === null ? null : (numeric(gpu?.vram_used) ?? 0) / 1024;
  const daemonViewerOnly = !daemonCanOperate;
  const daemonCumulativeSeconds = Math.max(
    persistedLearningSeconds,
    Math.floor(Number(learningDaemon?.cumulative_learning_seconds ?? learningDaemon?.total_runtime_seconds ?? 0)),
    Math.floor(learningElapsedMs / 1000),
  );
  const contributionBackendState = String(contributionStatus?.contributor_state ?? "local_only");
  const contributionBrokerState = String(contributionStatus?.broker_state ?? (localBackendConnected ? "local_broker_mode" : "viewer_only"));
  const contributionCurrentTask = contributionStatus?.current_task as AnyRecord | null | undefined;
  const contributionCompletedTasks = Number(contributionStatus?.total_tasks_completed ?? 0);
  const contributionPendingCredit = numeric(contributionStatus?.pending_credits) ?? 0;
  const contributionConfirmedCredit = numeric(contributionStatus?.confirmed_credits) ?? 0;
  const contributionPreviewDisclaimer = String(
    contributionStatus?.preview_disclaimer
      ?? (language === "ko"
        ? "브레인 링크 노드는 원격 브로커와 안전한 공개 fragment 작업만 교환합니다. 개인 Payload Vault와 로컬 브레인 데이터는 공유하지 않습니다."
        : "Brain Link Node is running in Local Broker Mode. Private Payload Vault and Local Brain data are never shared."),
  );
  const contributionCpuUsage = Math.round(numeric(system?.cpu_percent ?? system?.cpu_usage_percent ?? system?.cpu?.usage_percent) ?? 8);
  const contributionRamGb = numeric(system?.ram_used_gb ?? system?.memory_used_gb ?? edgeStatus?.capacity?.ram_used_gb) ?? 1.2;
  const contributionGpuAvailable = Boolean(gpu?.available);
  const contributionGpuUsage = Math.round(numeric(gpu?.utilization) ?? 0);
  const contributionGpuLimitEffective = contributionGpuAvailable ? contributionGpuLimit : 0;
  const contributionCreditMultiplier = Number((1 + Math.min(0.35, Math.max(0, contributionCpuLimit - 20) / 60 * 0.35) + (contributionGpuLimitEffective / 95 * 1.65)).toFixed(2));
  const contributionEstimatedTaskCredit = Number(((numeric(contributionCurrentTask?.credit_estimate) ?? 1) * contributionCreditMultiplier).toFixed(2));
  const contributionNetworkLabel = localBackendConnected
    ? (language === "ko" ? "정상" : "Normal")
    : (language === "ko" ? "낮음" : "Low");
  const contributionThermalLabel = resourceStopReason
    ? (language === "ko" ? "보류" : "Hold")
    : (language === "ko" ? "정상" : "Normal");
  const contributionBlockedBySafety = Boolean(resourceStopReason);
  const contributionIsBackendActive = [
    "contributor_active",
    "contributor_registered",
    "task_polling",
    "task_running",
    "task_submitted",
    "verification_pending",
    "credit_confirmed",
  ].includes(contributionBackendState);
  const contributionIsActive = contributionEnabled && contributionIsBackendActive && !contributionPaused && !contributionBlockedBySafety;
  const contributionStatusText = !localBackendConnected
    ? (language === "ko" ? "연결 확인" : "Checking link")
    : contributionBlockedBySafety
      ? (language === "ko" ? "보호 모드" : "Protected")
      : contributionBackendState === "verification_pending"
        ? (language === "ko" ? "검증 준비" : "Verification ready")
        : contributionBackendState === "task_running"
          ? (language === "ko" ? "동기화 중" : "Syncing")
          : contributionPaused || contributionBackendState === "paused"
            ? (language === "ko" ? "일시정지" : "Paused")
            : contributionIsActive
              ? (language === "ko" ? "연결됨" : "Linked")
              : (language === "ko" ? "대기 안정" : "Stable idle");
  const contributionTodayCredit = contributionPendingCredit;
  const contributionTotalCredit = contributionConfirmedCredit + contributionPendingCredit;
  const contributionWaitingCredit = contributionPendingCredit;
  const contributionCreditTrend = useMemo(() => {
    const base = Math.max(0.2, contributionTotalCredit || contributionEstimatedTaskCredit || 0.8);
    const activityBoost = contributionIsActive ? 0.34 : 0.08;
    const gpuBoost = contributionGpuAvailable ? contributionGpuLimitEffective / 140 : 0.04;
    const cpuBoost = contributionCpuUsage / 260;
    const phase = contributionChartTick / 1.7;
    const samples = [0.72, 0.78, 0.74, 0.86, 0.91, 0.88, 1.02, 0.98, 1.1, 1.16, 1.12, 1.24];
    const values = samples.map((sample, index) => {
      const liveBias = (index / Math.max(1, samples.length - 1)) * (activityBoost + gpuBoost + cpuBoost);
      const wave = Math.sin(phase + index * 0.82) * 0.11 + Math.cos(phase * 1.7 + index * 0.44) * 0.05;
      return Number(Math.max(0, base * (sample + wave) + liveBias).toFixed(2));
    });
    const max = Math.max(...values, 1);
    const min = Math.min(...values, 0);
    const range = Math.max(0.1, max - min);
    return values.map((value, index) => ({
      value,
      x: Number(((index / Math.max(1, values.length - 1)) * 100).toFixed(2)),
      y: Number((80 - ((value - min) / range) * 62).toFixed(2)),
    }));
  }, [contributionChartTick, contributionCpuUsage, contributionEstimatedTaskCredit, contributionGpuAvailable, contributionGpuLimitEffective, contributionIsActive, contributionTotalCredit]);
  const contributionCreditPolyline = contributionCreditTrend.map((point) => `${point.x},${point.y}`).join(" ");
  const contributionCreditArea = contributionCreditTrend.length
    ? `0,96 ${contributionCreditPolyline} 100,96`
    : "";
  const contributionCreditLatest = contributionCreditTrend[contributionCreditTrend.length - 1]?.value ?? contributionTotalCredit;
  const contributionSharedRatio = contributionAllowPublic && contributionIsActive ? 100 : 0;
  const contributionLocalShareRatio = 0;
  const contributionSafeSummary = contributionBlockedBySafety
    ? resourceStopReason
    : contributionGpuLimitEffective > 0
      ? (language === "ko" ? `GPU ${contributionGpuLimitEffective}% 보호 한도` : `GPU protected cap ${contributionGpuLimitEffective}%`)
      : (language === "ko" ? "CPU 경량 모드" : "CPU light mode");
  const daemonRuntimeText = formatDuration(daemonCumulativeSeconds * 1000);
  const daemonStateText = learningDaemon?.state === "resume_needed" ? "재개 필요" : learningDaemon?.state === "demo" ? "실험실 뷰어" : statusText(learningDaemon?.state);
  const daemonModeText = daemonCanOperate ? "로컬 클라우드 브레인 워커" : "배포 클라우드 브레인 뷰어";
  const daemonCheckpointText = learningDaemon?.last_checkpoint_at
    ? new Date(learningDaemon.last_checkpoint_at).toLocaleString("ko-KR")
    : "아직 없음";
  const daemonStatusState = daemonCanOperate
    ? learningDaemon?.worker_alive ? "running" : learningDaemon?.state === "failed" ? "failed" : learningDaemon?.state === "resume_needed" ? "warning" : "idle"
    : "completed";
  const labStatusState = error
    ? "failed"
    : isBuilding || continuousLearningActive || Boolean(activeAction) || isGeneratingAnswer
      ? "running"
      : "ready";
  const headerStatusState = workspaceMode === "daemon"
    ? daemonStatusState
    : labStatusState;
  const guardScore = guard?.overall_guard_score ?? guard?.result?.overall_guard_score ?? null;
  const guardClaimCount = guard?.result?.claims?.length ?? 0;
  const compactInfoSummary = [
    `${currentLearningPreset.label}${learningVolume === "infinite" ? "" : ` ${targetNodeCount.toLocaleString()}`}`,
    localBackendConnected ? "로컬 연결" : "fallback",
    edgeBrokerLabel,
    `GPU ${gpu?.utilization ?? 0}%`,
    `RAM ${ramSoftGb}GB`,
  ].join(" · ");
  const chatSummaryText = [
    `RAG ${Math.round((graphResult?.confidence ?? graphrag?.confidence ?? 0) * 100)}%`,
    fusionDisplayText,
    `근거 ${graphResult?.evidence_docs?.length ?? 0}`,
    guardScore === null ? "Guard 자동" : `Guard ${guardScore}`,
  ].join(" · ");
  const flowHealth = useMemo(() => {
    const complete = pipeline?.stages.filter((stage) => stage.state === "complete").length ?? 0;
    return Math.round((complete / Math.max(1, pipeline?.stages.length ?? 8)) * 100);
  }, [pipeline]);
  const collectComplete = labStageProgress.collect >= 100;
  const learnComplete = labStageProgress.learn >= 100;
  const outputComplete = labStageProgress.output >= 100;

  useEffect(() => {
    if (!continuousLearningActive || !resourceStopReason) return;
    stopContinuousLearning(resourceStopReason);
  }, [continuousLearningActive, resourceStopReason]);

  useEffect(() => {
    if (mainSection !== "contribute") return;
    const timer = window.setInterval(() => setContributionChartTick((tick) => tick + 1), 1000);
    return () => window.clearInterval(timer);
  }, [mainSection]);

  const advancedProcessSteps: never[] = []; /*
    {
      number: "KB",
      title: "Knowledge Bakery",
      api: "POST /api/memory/build",
      state: activeAction === "KB" ? "running" : memoryStatus?.state ?? "idle",
      description: "?뺤젣 臾몄꽌? ?⑦넧濡쒖??먯꽌 臾몄옣 ?붿냼, phrase ?몃뱶, ?꾪썑 ?좏겙 ?뺣쪧, 3D 濡쒖뺄 踰≫꽣瑜?SQLite 硫붾え由щ줈 援쎌뒿?덈떎.",
      metrics: [
        `${memoryStatus?.node_count ?? 0} nodes`,
        `${memoryStatus?.edge_count ?? 0} edges`,
        `${memoryStatus?.transition_count ?? 0} transitions`,
        `${memoryStatus?.phrase_count ?? 0} phrases`,
        `drift ${memoryDrift?.state ?? "waiting"}`,
      ],
      action: () => runProcessAction("KB", runMemoryBuildStep),
      actionLabel: activeAction === "KB" ? "硫붾え由?援ъ텞 以? : "硫붾え由?援ъ텞",
    },
    {
      number: "HW",
      title: "?쒖뒪??踰ㅼ튂留덊겕",
      api: "POST /api/neuro/benchmark",
      state: activeAction === "HW" ? "running" : benchmark ? "completed" : "idle",
      description: "?쒖옉 ??PC??CPU, RAM, GPU, ?붿뒪?щ? 吏㏐쾶 痢≪젙???⑦넧濡쒖? 諛곗튂? ?숈뒿?됱쓣 ?먮룞?쇰줈 議곗젅?⑸땲??",
      metrics: [
        benchmark?.profile_name ?? "痢≪젙 ?湲?,
        `異붿쿇 ${benchmarkVolumeLabel}`,
        `CPU ${benchmarkCpuThreads}`,
        `RAM ${benchmarkRamGb}GB`,
        telemetryLabel,
        resourceStopReason ? "?덉쟾以묒? 議곌굔 媛먯?" : "?덉쟾 議곌굔 ?뺤긽",
      ],
      action: () => runProcessAction("HW", () => runHardwareBenchmark({ applyRecommendation: true })),
      actionLabel: activeAction === "HW" ? "痢≪젙 以? : "踰ㅼ튂留덊겕 ?ъ륫??,
    },
    {
      number: "00",
      title: "鍮뚮뱶 ?쒖옉",
      api: "POST /api/factory/build/start",
      state: isBuilding || continuousLearningActive ? "running" : buildRun ? "completed" : "idle",
      description: "?명꽣??李몄“瑜??섏쭛?섍퀬 DataGate, Ontology Forge, 3D GraphRAG ?먯깋, ATANOR Oven ?숈뒿 寃뚯씠?멸퉴吏 ??踰덉뿉 ?먮Ⅴ寃??⑸땲??",
      metrics: [
        `${selectedTargetNodeLabel} ?κ린 紐⑺몴`,
        `${buildRun?.training_gate?.chunk_count ?? currentLearningPreset.chunkBudget} 泥?겕`,
        `${buildRun?.learning_profile?.text_budget_label ?? currentLearningPreset.textBudget}`,
        `${activeGraph3D?.nodes?.length ?? 0}/${buildRun ? visualNodeCap : currentLearningPreset.visualNodes} ????섑뵆`,
        buildRun ? `${buildRun.graph_3d.nodes.length.toLocaleString()} API ?듭빱` : `${currentLearningPreset.visualNodes} 珥덇린 ?쒖떆`,
        representativeCapReached ? "?쒖떆 ?곹븳 ?꾨떖" : "?쒖떆 ?ъ쑀 ?덉쓬",
        buildIsInfinite ? "臾댁젣??吏?? : buildRun?.training_gate?.target_realized ? "?κ린 紐⑺몴 ?ъ꽦" : buildRun ? "?κ린 紐⑺몴 誘몄떎?? : "?湲?,
        buildIsInfinite ? `?꾩쟻 ${learningElapsedText}` : `${growthPulseCount} ?ㅼ떆媛??꾩뒪`,
        buildIsInfinite ? `${accumulatedLearningNodes.toLocaleString()} ?꾨낫 ?몃뱶` : buildRun?.training_gate?.ready ? "?숈뒿 寃뚯씠??以鍮? : "寃뚯씠???湲?,
      ],
      action: () => continuousLearningActive ? stopContinuousLearning() : runProcessAction("00", startFactoryBuild),
      actionLabel: continuousLearningActive ? "?숈뒿 以묒?" : isBuilding || activeAction === "00" ? "鍮뚮뱶 吏꾪뻾 以? : "鍮뚮뱶 ?쒖옉",
    },
    {
      number: "01",
      title: "DataGate ?뺤젣",
      api: "POST /api/datagate/run",
      state: activeAction === "01" ? "running" : datagate?.state ?? "idle",
      description: "?먯쿇 臾몄꽌瑜??듦낵/嫄곗젅濡??섎늻怨?RAG???ㅼ뼱媛?源⑤걮???낅젰留??④퉩?덈떎.",
      metrics: [`${datagate?.accepted ?? 0}/${datagate?.total ?? 0} ?듦낵`, `${percent(datagate?.accepted ?? 0, datagate?.total ?? 0)}% ?듦낵??],
      action: () => runProcessAction("01", runDataGateStep),
      actionLabel: activeAction === "01" ? "?뺤젣 以? : "?뺤젣 ?ㅽ뻾",
    },
    {
      number: "02",
      title: "?⑦넧濡쒖? 硫붾え由??앹꽦",
      api: "POST /api/ontology/run",
      state: activeAction === "02" ? "running" : ontology?.state ?? "idle",
      description: "?뺤젣??臾몄꽌?먯꽌 媛쒕뀗怨?愿怨꾨? 異붿텧???쇱そ 硫붾え由?洹몃옒?꾨? 援ъ꽦?⑸땲??",
      metrics: [`${ontology?.node_count ?? memoryNodes.length} ?몃뱶`, `${ontology?.edge_count ?? memoryEdges.length} ?ｌ?`],
      action: () => runProcessAction("02", runOntologyStep),
      actionLabel: activeAction === "02" ? "?앹꽦 以? : "硫붾え由??앹꽦",
    },
    {
      number: "03",
      title: "GraphRAG 寃??,
      api: "POST /api/graphrag/query",
      state: activeAction === "03" ? "running" : graphrag?.state ?? "idle",
      description: "吏덈Ц???⑦넧濡쒖? 硫붾え由ъ? 臾몄꽌 洹쇨굅???곌껐?⑸땲?? ???④퀎媛 ?ㅼ젣 RAG ?묒뾽??낅땲??",
      metrics: [`?좊ː??${Math.round((graphrag?.confidence ?? 0) * 100)}%`, `${graphResult?.evidence_docs?.length ?? 0} 洹쇨굅`],
      action: () => runProcessAction("03", async () => {
        setRightMode("chat");
        await sendChat();
      }),
      actionLabel: activeAction === "03" ? "吏덈Ц 以? : "RAG 梨꾪똿 ?닿린",
    },
    {
      number: "04",
      title: "Guardrail 寃利?,
      api: "POST /api/guard/check",
      state: activeAction === "04" ? "running" : guard?.state ?? "idle",
      description: "RAG 洹쇨굅? ?듬? 珥덉븞???議고빐 怨쇱옣 ?쒗쁽怨?誘몄???二쇱옣???쒖떆?⑸땲??",
      metrics: [`${guard?.overall_guard_score ?? 0}??, `${guard?.result?.claims?.length ?? 0} 二쇱옣`],
      action: () => runProcessAction("04", checkGuard),
      actionLabel: activeAction === "04" ? "寃利?以? : "珥덉븞 寃利?,
    },
    {
      number: "05",
      title: "?숈뒿 dry-run",
      api: "POST /api/oven/dry-run",
      state: activeAction === "05" ? "running" : oven?.state ?? "idle",
      description: "?숈뒿 ?뚯씠?꾨씪?몄쓣 吏㏐쾶 ?ㅽ뻾?섍퀬 ?꾨즺?섎㈃ ?ㅻⅨ履??⑤꼸??RAG 梨꾪똿 UI濡??꾪솚?⑸땲??",
      metrics: [`?먯떎 ${oven?.last_loss ?? "?湲?}`, `${losses.length} ?④퀎`],
      action: () => runProcessAction("05", runTrainingDryRun),
      actionLabel: activeAction === "05" ? "?숈뒿 以? : "?숈뒿 ?ㅽ뻾",
    },
    {
      number: "06",
      title: "??꾨젰 ?⑥쑉 怨꾪쉷",
      api: "POST /api/neuro/plan",
      state: activeAction === "06" ? "running" : "completed",
      description: "?대깽???ъ냼?? 紐⑤뱢 ?쇱슦?? ?뺤텞 ?ㅼ젙???ш퀎?고빐 ??ъ뼇 ?ㅽ뻾 媛?μ꽦??遊낅땲??",
      metrics: [`${energyReduction}% ?덇컧`, `${eventSparsity}% ?ъ냼??],
      action: () => runProcessAction("06", rebalanceNeuro),
      actionLabel: activeAction === "06" ? "怨꾩궛 以? : "?⑥쑉 ?ш퀎??,
    },
    {
      number: "07",
      title: "吏???댁쟾 ?덉쟾?μ튂",
      api: "POST /api/neuro/stability",
      state: activeAction === "07" ? "running" : "completed",
      description: "?섏쿇 媛??몃뱶/愿怨꾧? ?앷꺼???? 泥댄겕?ъ씤?? 洹몃옒??hot window, UI LOD濡??쒖뒪?쒖씠 二쎌? ?딄쾶 ?쒗븳?⑸땲??",
      metrics: [`RAM soft ${ramSoftGb}GB`, `VRAM soft ${vramSoftGb}GB`, `hot ${hotWindowNodes} ?몃뱶`, `UI ${uiRenderNodes} ?몃뱶`],
      action: () => runProcessAction("07", refreshStabilityPlan),
      actionLabel: activeAction === "07" ? "怨꾩궛 以? : "?덉젙??怨꾩궛",
    },
  ];

  const processSteps = [
    {
      key: "collect" as LabStageKey,
      number: "01",
      title: "?섏쭛",
      api: "POST /api/factory/build/start + DataGate",
      state: isBuilding || continuousLearningActive || activeAction === "collect" ? "running" : collectComplete ? "completed" : "idle",
      description: "??臾몄꽌 ?낅젰??媛?몄? 臾몄옣 ?⑥쐞濡?履쇨컻怨? GraphRAG媛 ?쎌쓣 ???덈뒗 ?꾨낫 泥?겕? 珥덇린 ?듭빱 洹몃옒?꾨? 留뚮벊?덈떎.",
      progress: labStageProgress.collect,
      available: true,
      metrics: [
        `${buildRun?.harvest_docs?.length ?? datagate?.total ?? 0} ?먮즺`,
        `${buildRun?.training_gate?.chunk_count ?? currentLearningPreset.chunkBudget} 泥?겕`,
        `${collectionDisplayNodeCount.toLocaleString()} ?쒖떆 ?몃뱶`,
        buildIsInfinite ? `??${learningElapsedText}` : `${selectedTargetNodeLabel} 紐⑺몴`,
      ],
      action: () => continuousLearningActive ? stopContinuousLearning() : runProcessAction("collect", startFactoryBuild),
      actionLabel: continuousLearningActive ? "?섏쭛 以묒?" : isBuilding || activeAction === "collect" ? "?섏쭛 以? : "?섏쭛 ?쒖옉",
      blockedText: "",
    },
    {
      key: "learn" as LabStageKey,
      number: "02",
      title: "?숈뒿",
      api: "POST /api/ontology/run + /api/memory/build",
      state: activeAction === "learn" ? "running" : learnComplete ? "completed" : collectComplete ? "ready" : "idle",
      description: "遺꾪빐??臾몄옣 ?붿냼瑜??⑦넧濡쒖? ?몃뱶濡??꾩쟻?섍퀬, 怨듭텧???꾪썑/?됱쐞 愿怨꾨? 怨꾩궛??洹몃옒??硫붾え由щ줈 援쎌뒿?덈떎.",
      progress: labStageProgress.learn,
      available: collectComplete,
      metrics: buildRun
        ? [
          `${displayGraph3D.nodes.length.toLocaleString()} ????몃뱶`,
          `${displayGraph3D.edges.length.toLocaleString()} ???愿怨?,
          `${memoryStatus?.node_count ?? 0} ????몃뱶`,
          `${memoryStatus?.edge_count ?? 0} ???愿怨?,
        ]
        : [
          `${memoryStatus?.node_count ?? ontology?.node_count ?? displayGraph3D.nodes.length} ?몃뱶`,
          `${memoryStatus?.edge_count ?? ontology?.edge_count ?? displayGraph3D.edges.length} 愿怨?,
          `${memoryStatus?.transition_count ?? 0} ?꾩씠`,
          `drift ${memoryDrift?.state ?? "waiting"}`,
        ],
      action: () => runProcessAction("learn", runLearningStage),
      actionLabel: activeAction === "learn" ? "?숈뒿 以? : "愿怨?怨꾩궛",
      blockedText: "?섏쭛 100% ?꾨즺 ???숈뒿?????덉뒿?덈떎.",
    },
    {
      key: "output" as LabStageKey,
      number: "03",
      title: "異쒕젰",
      api: "POST /api/graphrag/query + /api/guard/check",
      state: activeAction === "output" || isGeneratingAnswer ? "running" : outputComplete ? "completed" : learnComplete ? "ready" : "idle",
      description: "吏덈Ц???먯뿰?대줈 ?ｌ쑝硫??쒖꽦 ?몃뱶? 洹몃옒???꾩씠瑜??쎌뼱 ?듬???留뚮뱾怨? 媛숈? 洹쇨굅 臾띠쓬?쇰줈 Guardrail???먮룞 寃利앺빀?덈떎.",
      progress: labStageProgress.output,
      available: learnComplete,
      metrics: [
        `?좊ː??${Math.round((graphResult?.confidence ?? graphrag?.confidence ?? 0) * 100)}%`,
        `${graphResult?.evidence_docs?.length ?? 0} 洹쇨굅`,
        guardScore === null ? "Guard ?먮룞 ?湲? : `Guard ${guardScore}??,
        `??${webSearchEnabled ? graphResult?.web_search?.provider ?? "on" : "off"}`,
      ],
      action: () => runProcessAction("output", async () => {
        setRightMode("chat");
        await sendChat();
      }),
      actionLabel: activeAction === "output" || isGeneratingAnswer ? "?앹꽦 以? : "吏덈Ц 蹂대궡湲?,
      blockedText: "?숈뒿 100% ?꾨즺 ??異쒕젰 ?④퀎濡??섏뼱媛묐땲??",
    },
  ];

  */
  const processSteps = [
    {
      key: "collect" as LabStageKey,
      number: "01",
      title: language === "ko" ? "수집" : "Collect",
      api: "POST /api/factory/build/start + DataGate",
      state: isBuilding || continuousLearningActive || activeAction === "collect" ? "running" : collectComplete ? "completed" : "idle",
      description: language === "ko"
        ? "원문과 웹 참조를 문장 단위로 분해하고 GraphRAG가 읽을 후보 chunk와 초기 앵커 그래프를 만듭니다."
        : "Collects raw text and web references, splits them into sentence chunks, and prepares initial GraphRAG anchors.",
      progress: labStageProgress.collect,
      available: true,
      metrics: [
        `${buildRun?.harvest_docs?.length ?? datagate?.total ?? 0} docs`,
        `${buildRun?.training_gate?.chunk_count ?? currentLearningPreset.chunkBudget} chunks`,
        `${collectionDisplayNodeCount.toLocaleString()} visible nodes`,
        buildIsInfinite ? `∞ ${learningElapsedText}` : `${selectedTargetNodeLabel} target`,
      ],
      action: () => continuousLearningActive ? stopContinuousLearning() : runProcessAction("collect", startFactoryBuild),
      actionLabel: continuousLearningActive
        ? (language === "ko" ? "수집 중지" : "Stop collect")
        : isBuilding || activeAction === "collect"
          ? (language === "ko" ? "수집 중" : "Collecting")
          : (language === "ko" ? "수집 시작" : "Start collect"),
      blockedText: "",
    },
    {
      key: "learn" as LabStageKey,
      number: "02",
      title: language === "ko" ? "학습" : "Learn",
      api: "POST /api/ontology/run + /api/memory/build",
      state: activeAction === "learn" ? "running" : learnComplete ? "completed" : collectComplete ? "ready" : "idle",
      description: language === "ko"
        ? "분해된 문장 요소를 온톨로지 노드로 누적하고, 공출현과 전후 관계를 계산해 그래프 메모리로 굽습니다."
        : "Accumulates extracted sentence elements as ontology nodes and computes relation weights into graph memory.",
      progress: labStageProgress.learn,
      available: collectComplete,
      metrics: buildRun
        ? [
          `${displayGraph3D.nodes.length.toLocaleString()} representative nodes`,
          `${displayGraph3D.edges.length.toLocaleString()} representative edges`,
          `${memoryStatus?.node_count ?? 0} stored nodes`,
          `${memoryStatus?.edge_count ?? 0} stored edges`,
        ]
        : [
          `${memoryStatus?.node_count ?? ontology?.node_count ?? displayGraph3D.nodes.length} nodes`,
          `${memoryStatus?.edge_count ?? ontology?.edge_count ?? displayGraph3D.edges.length} edges`,
          `${memoryStatus?.transition_count ?? 0} transitions`,
          `drift ${memoryDrift?.state ?? "waiting"}`,
        ],
      action: () => runProcessAction("learn", runLearningStage),
      actionLabel: activeAction === "learn" ? (language === "ko" ? "학습 중" : "Learning") : (language === "ko" ? "관계 계산" : "Compute relations"),
      blockedText: language === "ko" ? "수집이 완료된 뒤 학습할 수 있습니다." : "Collect must complete before learning.",
    },
    {
      key: "output" as LabStageKey,
      number: "03",
      title: language === "ko" ? "출력" : "Output",
      api: "POST /api/graphrag/query + /api/guard/check",
      state: activeAction === "output" || isGeneratingAnswer ? "running" : outputComplete ? "completed" : learnComplete ? "ready" : "idle",
      description: language === "ko"
        ? "질문을 자연어로 입력하면 활성 노드와 그래프 경로를 읽고, 같은 근거 묶음으로 자동 검증합니다."
        : "Reads active nodes and graph paths for a question, then checks the answer against the same evidence bundle.",
      progress: labStageProgress.output,
      available: learnComplete,
      metrics: [
        `RAG ${Math.round((graphResult?.confidence ?? graphrag?.confidence ?? 0) * 100)}%`,
        `${graphResult?.evidence_docs?.length ?? 0} evidence`,
        guardScore === null ? "Guard waiting" : `Guard ${guardScore}`,
        `Web ${webSearchEnabled ? graphResult?.web_search?.provider ?? "on" : "off"}`,
      ],
      action: () => runProcessAction("output", async () => {
        setRightMode("chat");
        await sendChat();
      }),
      actionLabel: activeAction === "output" || isGeneratingAnswer ? (language === "ko" ? "생성 중" : "Generating") : (language === "ko" ? "질문 보내기" : "Send question"),
      blockedText: language === "ko" ? "학습이 완료된 뒤 출력 단계로 넘어갑니다." : "Learning must complete before output.",
    },
  ];

  void advancedProcessSteps;

  const activeLabStageIndex = Math.max(0, labStageOrder.indexOf(activeLabStage));
  const activeProcessStep = processSteps.find((step) => step.key === activeLabStage) ?? processSteps[0];
  const previousProcessKey = activeLabStageIndex > 0 ? labStageOrder[activeLabStageIndex - 1] : null;
  const nextProcessKey = activeLabStageIndex < labStageOrder.length - 1 ? labStageOrder[activeLabStageIndex + 1] : null;

  function canOpenProcessStep(step: LabStageKey) {
    if (step === "collect") return true;
    if (step === "learn") return collectComplete;
    return learnComplete;
  }

  function openProcessStep(step: LabStageKey) {
    if (!canOpenProcessStep(step)) return;
    setRightMode("process");
    setActiveLabStage(step);
  }

  const logTime = clockNow ? fmtClock(clockNow) : "--:--:--";
  const logs = [
    ...(buildRun ? [{ time: logTime, message: `Build ${buildRun.run_id}: ${activeBuildFrame?.message ?? "factory build ready"} / gate ${buildRun.training_gate.ready ? "ready" : "waiting"}${buildIsInfinite ? ` / accumulated ${learningElapsedText}` : ""}` }] : []),
    { time: logTime, message: `Cloud Brain: ${daemonModeText} / state ${daemonStateText} / runtime ${daemonRuntimeText}` },
    { time: logTime, message: `Benchmark: ${benchmark?.profile_name ?? "waiting"} / recommended ${benchmarkVolumeLabel} / ${benchmarkSourceLabel}` },
    { time: logTime, message: `Memory graph loaded: ${displayMemoryNodeCount} nodes / ${displayMemoryEdgeCount} edges` },
    { time: logTime, message: `Provider: ${cloudProviderName} / broker ${cloudBrokerState} / budget ${cloudBudgetPlan} ${cloudBudgetRequests || 0}/day` },
    { time: logTime, message: `Brain Balance: Local ${budgetLocalPct}% / Cloud ${budgetCloudPct}%` },
    { time: logTime, message: `RAG state: ${statusText(graphrag?.state)} / confidence ${Math.round((graphrag?.confidence ?? 0) * 100)}%` },
    { time: logTime, message: `Learning state: ${statusText(oven?.state)} / last loss ${oven?.last_loss ?? "none"}` },
    { time: logTime, message: `Efficiency plan: estimated compute reduction ${energyReduction}%` },
    { time: logTime, message: `Stability: RAM soft ${ramSoftGb}GB / VRAM soft ${vramSoftGb}GB / hot window ${hotWindowNodes} nodes` },
  ];

  const headerBuildLabel = continuousLearningActive
    ? (language === "ko" ? "학습 중지" : "Stop learning")
    : isBuilding || activeAction === "collect"
      ? (language === "ko" ? "수집 중" : "Collecting")
      : activeAction === "learn"
        ? (language === "ko" ? "학습 중" : "Learning")
        : activeAction === "output" || isGeneratingAnswer
          ? (language === "ko" ? "출력 중" : "Generating")
          : !collectComplete
            ? (language === "ko" ? "빌드 시작" : "Start build")
            : !learnComplete
              ? (language === "ko" ? "다음: 학습" : "Next: learn")
              : (language === "ko" ? "RAG 채팅" : "RAG chat");

  async function runNextLabStage() {
    if (continuousLearningActive) {
      stopContinuousLearning();
      return;
    }
    if (!collectComplete) {
      await runProcessAction("collect", startFactoryBuild);
      return;
    }
    if (!learnComplete) {
      await runProcessAction("learn", runLearningStage);
      return;
    }
    setRightMode("chat");
    setLabStageProgress((current) => ({ ...current, output: Math.max(current.output, 6) }));
  }

  function changeLayoutMode(mode: LayoutMode) {
    setLayoutMode(mode);
  }

  function changeWorkspaceMode(mode: WorkspaceMode) {
    setWorkspaceMode(mode);
    const url = new URL(window.location.href);
    url.searchParams.set("workspace", mode);
    window.history.replaceState(null, "", url);
  }

  function resetConsole() {
    changeLayoutMode("split");
    changeWorkspaceMode("lab");
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

  function handleAtlasPointerDown(event: ReactPointerEvent<HTMLDivElement>) {
    if (event.button !== 0) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    setAtlasDragState({
      pointerId: event.pointerId,
      startX: event.clientX,
      startRotationDeg: atlasRotationDeg,
    });
  }

  function handleAtlasPointerMove(event: ReactPointerEvent<HTMLDivElement>) {
    if (!atlasDragState || atlasDragState.pointerId !== event.pointerId) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const deltaRatio = rect.width > 0 ? (event.clientX - atlasDragState.startX) / rect.width : 0;
    const nextRotation = atlasDragState.startRotationDeg + deltaRatio * 180;
    setAtlasRotationDeg((((nextRotation % 360) + 360) % 360));
  }

  function handleAtlasPointerUp(event: ReactPointerEvent<HTMLDivElement>) {
    if (atlasDragState?.pointerId === event.pointerId) {
      event.currentTarget.releasePointerCapture(event.pointerId);
      setAtlasDragState(null);
    }
  }

  const copy = EFFECTIVE_MAIN_COPY[language];
  const graphSparsity = displayMemoryNodeCount > 1
    ? ((displayMemoryEdgeCount / Math.max(1, displayMemoryNodeCount * (displayMemoryNodeCount - 1))) * 100).toFixed(2)
    : "0.00";
  const graphCommunities = Math.max(1, Math.round(Math.sqrt(Math.max(1, displayMemoryNodeCount)) / 2));
  const rawCloudAssistRatio =
    graphResult?.fusion?.cloud_ratio
    ?? graphResult?.fusion_ratio?.cloud_weight
    ?? graphResult?.retrieval_trace?.fusion_ratio?.cloud_weight
    ?? graphResult?.cloud_ratio;
  const generationLowConfidence = Boolean(
    graphResult?.native_generation_failed_quality_check
    || graphResult?.answer_engine?.diagnostics?.quality_guarded_surface
  );
  const cloudAssistRatio = graphPresentationMode === "local_private_memory"
    ? 0
    : graphPresentationMode === "cloud_world_knowledge"
      ? 100
      : rawCloudAssistRatio === undefined || rawCloudAssistRatio === null
        ? 50
        : Math.max(generationLowConfidence ? 35 : 0, Math.round(Number(rawCloudAssistRatio) * 100));
  const localAssistRatio = Math.max(0, 100 - cloudAssistRatio);
  const presentationCopy = (() => {
    if (graphPresentationMode === "local_private_memory") {
      return {
        graphTitle: language === "ko" ? "로컬 브레인 지식 그래프" : "Local Brain Knowledge Graph",
        graphSubtitle: language === "ko"
          ? "개인 Ghost Shell과 Payload Vault 안에서만 탐색하고 답합니다."
          : "Searches and answers only inside the private Ghost Shell and Payload Vault.",
        localLabel: language === "ko" ? "로컬 브레인" : "Local Brain",
        localDetail: language === "ko" ? "개인 메모리 / 프로젝트 문맥" : "Private Memory / Project Context",
        cloudLabel: language === "ko" ? "클라우드 비활성" : "Cloud Disabled",
        cloudDetail: language === "ko" ? "명시적으로 켜기 전까지 사용하지 않음" : "Not used unless explicitly enabled",
        centerLabel: "Local Anchor",
        localNode: language === "ko" ? "개인 메모리" : "Private Memory",
        cloudNode: language === "ko" ? "비활성 Cloud" : "Disabled Cloud",
        fragmentNode: "Payload Vault",
      };
    }
    if (graphPresentationMode === "cloud_world_knowledge") {
      return {
        graphTitle: language === "ko" ? "클라우드 브레인 지식 그래프" : "Cloud Brain Knowledge Graph",
        graphSubtitle: language === "ko"
          ? "공용 온톨로지 후보와 public fragment 흐름을 읽기 전용으로 관찰합니다."
          : "Observes public ontology candidates and public fragment flow in read-only mode.",
        localLabel: language === "ko" ? "엣지 미러" : "Edge Mirror",
        localDetail: language === "ko" ? "읽기 전용 소비자" : "Read-only consumer",
        cloudLabel: language === "ko" ? "클라우드 브레인" : "Cloud Brain",
        cloudDetail: "Public Ontology / World Knowledge",
        centerLabel: "Public Anchor",
        localNode: language === "ko" ? "엣지 미러" : "Edge Mirror",
        cloudNode: language === "ko" ? "공용 지식 노드" : "Public Knowledge",
        fragmentNode: language === "ko" ? "실시간 Fragment" : "Live Fragment",
      };
    }
    return {
      graphTitle: mainSection === "home" ? copy.graphTitle : (language === "ko" ? "통합 지식 그래프" : "Unified Knowledge Graph"),
      graphSubtitle: mainSection === "home"
        ? copy.graphSubtitle
        : (language === "ko"
          ? "로컬, 시드, 클라우드 레이어를 하나의 시각 투영으로만 표시합니다. 실제 브리지 연결을 뜻하지 않습니다."
          : "Local, Seed, and Cloud layers are shown as a visual projection only, not a live bridge."),
      localLabel: copy.localBrain,
      localDetail: "Private Boundary",
      cloudLabel: copy.cloudBrain,
      cloudDetail: "Public Fragment",
      centerLabel: "Working Memory",
      localNode: copy.localNode,
      cloudNode: copy.cloudNode,
      fragmentNode: copy.fragmentNode,
    };
  })(); /*
    ? {
      graphTitle: language === "ko" ? "濡쒖뺄 釉뚮젅??媛쒖씤 硫붾え由? : "Local Brain Private Memory",
      graphSubtitle: language === "ko"
        ? "媛쒖씤 湲곗뼲, ?꾨줈?앺듃 臾몄꽌, ?????? Payload Vault瑜??곗꽑?⑸땲?? Cloud Brain? 湲곕낯?곸쑝濡??ъ슜?섏? ?딆뒿?덈떎."
        : "Prioritizes private memory, project documents, saved conversations, and Payload Vault. Cloud Brain stays minimal by default.",
      localLabel: language === "ko" ? "濡쒖뺄 釉뚮젅?? : "Local Brain",
      localDetail: language === "ko" ? "媛쒖씤 湲곗뼲 / ?꾨줈?앺듃 臾몃㎘" : "Private Memory / Project Context",
      cloudLabel: language === "ko" ? "Cloud 鍮꾪솢?? : "Cloud Disabled",
      cloudDetail: language === "ko" ? "?먭꺽 吏?앹? 理쒖냼?? : "Remote knowledge minimized",
      centerLabel: language === "ko" ? "Local Anchor" : "Local Anchor",
      localNode: language === "ko" ? "媛쒖씤 硫붾え由? : "Private Memory",
      cloudNode: language === "ko" ? "鍮꾪솢??Cloud" : "Disabled Cloud",
      fragmentNode: "Payload Vault",
    }
    : graphPresentationMode === "cloud_world_knowledge"
      ? {
        graphTitle: language === "ko" ? "?대씪?곕뱶 釉뚮젅??怨듭슜 ?⑦넧濡쒖?" : "Cloud Brain Public Ontology",
        graphSubtitle: language === "ko"
          ? "?멸퀎 怨듦컻 吏?? 怨듭슜 source cluster, ?ㅼ떆媛?fragment, ?좊ː?꾩? 理쒖떊?깆쓣 愿李고빀?덈떎."
          : "Observes world knowledge, public source clusters, live fragments, trust, provenance, and freshness.",
        localLabel: language === "ko" ? "?ｌ? 誘몃윭" : "Edge Mirror",
        localDetail: language === "ko" ? "?쎄린 ?꾩슜 ?뚮퉬?? : "Read-only consumer",
        cloudLabel: language === "ko" ? "?대씪?곕뱶 釉뚮젅?? : "Cloud Brain",
        cloudDetail: language === "ko" ? "Public Ontology / World Knowledge" : "Public Ontology / World Knowledge",
        centerLabel: language === "ko" ? "Public Anchor" : "Public Anchor",
        localNode: language === "ko" ? "?ｌ? 誘몃윭" : "Edge Mirror",
        cloudNode: language === "ko" ? "怨듭슜 吏???몃뱶" : "Public Knowledge",
        fragmentNode: language === "ko" ? "?ㅼ떆媛?Fragment" : "Live Fragment",
      }
      : {
        graphTitle: mainSection === "home" ? copy.graphTitle : (language === "ko" ? "통합 지식 그래프" : "Unified Knowledge Graph"),
        graphSubtitle: mainSection === "home" ? copy.graphSubtitle : (language === "ko"
          ? "로컬 기억, 공용 Cloud Fragment, Seed Schema가 하나의 통합 graph projection으로 표시됩니다."
          : "Local memory, public Cloud fragments, and Seed Schema are shown as one unified graph projection."),
        localLabel: copy.localBrain,
        localDetail: language === "ko" ? "Private Boundary" : "Private Boundary",
        cloudLabel: copy.cloudBrain,
        cloudDetail: language === "ko" ? "Public Fragment" : "Public Fragment",
        centerLabel: language === "ko" ? "Working Memory" : "Working Memory",
        localNode: copy.localNode,
        cloudNode: copy.cloudNode,
        fragmentNode: copy.fragmentNode,
      };
  if (language === "ko") {
    presentationCopy = graphPresentationMode === "local_private_memory"
      ? {
        graphTitle: "濡쒖뺄 釉뚮젅??吏??洹몃옒??,
        graphSubtitle: "媛쒖씤 Ghost Shell怨?Payload Vault ?덉뿉?쒕쭔 ?먯깋?섍퀬 ?듬??⑸땲??",
        localLabel: "濡쒖뺄 釉뚮젅??,
        localDetail: "媛쒖씤 硫붾え由?/ ?꾨줈?앺듃 臾몃㎘",
        cloudLabel: "?대씪?곕뱶 鍮꾪솢??,
        cloudDetail: "紐낆떆?곸쑝濡?耳쒓린 ?꾧퉴吏 ?ъ슜?섏? ?딆쓬",
        centerLabel: "Local Anchor",
        localNode: "媛쒖씤 硫붾え由?,
        cloudNode: "鍮꾪솢??Cloud",
        fragmentNode: "Payload Vault",
      }
      : graphPresentationMode === "cloud_world_knowledge"
        ? {
          graphTitle: "?대씪?곕뱶 釉뚮젅??吏??洹몃옒??,
          graphSubtitle: "怨듭슜 ?⑦넧濡쒖? ?꾨낫? public fragment ?먮쫫???쎄린 ?꾩슜?쇰줈 愿李고빀?덈떎.",
          localLabel: "?ｌ? 誘몃윭",
          localDetail: "?쎄린 ?꾩슜 ?뚮퉬??,
          cloudLabel: "?대씪?곕뱶 釉뚮젅??,
          cloudDetail: "Public Ontology / World Knowledge",
          centerLabel: "Public Anchor",
          localNode: "?ｌ? 誘몃윭",
          cloudNode: "怨듭슜 吏???몃뱶",
          fragmentNode: "?ㅼ떆媛?Fragment",
        }
        : {
          graphTitle: mainSection === "home" ? copy.graphTitle : "???釉뚮젅???듯빀 洹몃옒??,
          graphSubtitle: mainSection === "home"
            ? copy.graphSubtitle
            : "Local Brain怨?Cloud Brain??Working Memory?먯꽌 留뚮굹??愿怨?寃쎈줈瑜?蹂댁뿬以띾땲??",
          localLabel: "濡쒖뺄 釉뚮젅??,
          localDetail: "Private Boundary",
          cloudLabel: "?대씪?곕뱶 釉뚮젅??,
          cloudDetail: "Public Fragment",
          centerLabel: "Working Memory",
          localNode: "濡쒖뺄 釉뚮젅???몃뱶",
          cloudNode: "?대씪?곕뱶 釉뚮젅???몃뱶",
          fragmentNode: "?대씪?곕뱶 ?꾨옒洹몃㉫??,
        };
  }
  */
  const activeTaskLabel = continuousLearningActive || learningDaemon?.worker_alive
    ? copy.learningEngine
    : isGeneratingAnswer
      ? copy.generationEngine
      : activeAction
        ? String(activeAction).toUpperCase()
        : "Adaptive Local-Cloud Ratio";
  const activeTaskRouteText = graphPresentationMode === "local_private_memory"
    ? (language === "ko" ? "Local private memory only" : "Local private memory only")
    : graphPresentationMode === "cloud_world_knowledge"
      ? (language === "ko" ? "클라우드 브레인 뷰어 / 읽기 전용 proof store" : "Cloud Brain viewer / read-only proof store")
      : graphPresentationMode === "home_unified_overview" || graphPresentationMode === "unified_projection"
        ? (language === "ko" ? "시각 투영 전용" : "Visual projection only")
        : `${localAssistRatio}% local / ${cloudAssistRatio}% cloud`;
  const graphFitScale = usesStudioGraph
    ? 1.18
    : graphPresentationMode === "local_private_memory"
      ? 1.58
      : graphPresentationMode === "cloud_world_knowledge"
        ? 1.2
        : 1.34;
  const activeTaskProgress = continuousLearningActive || learningDaemon?.worker_alive
    ? 100
    : isGeneratingAnswer
      ? 62
      : Math.max(4, cloudAssistRatio);
  const statusRows = graphPresentationMode === "local_private_memory"
    ? [
      { label: language === "ko" ? "로컬 브레인" : "Local Brain", value: localBrainInitialized ? copy.running : (language === "ko" ? "학습 전" : "Not trained"), tone: localBrainInitialized ? "green" : "orange" },
      { label: language === "ko" ? "저장 메모리" : "Stored Memories", value: displayMemoryNodeCount.toLocaleString(), tone: "white" },
      { label: "Payload Vault", value: language === "ko" ? "봉인됨" : "Sealed", tone: "white" },
      { label: "Ghost Shell", value: localBrainInitialized ? (language === "ko" ? "활성" : "Active") : (language === "ko" ? "비어 있음" : "Empty"), tone: "cyan" },
      { label: "Cloud Access", value: language === "ko" ? "최소화" : "Minimal", tone: "blue" },
    ]
    : graphPresentationMode === "cloud_world_knowledge"
      ? [
        { label: language === "ko" ? "클라우드 커버리지" : "Cloud Coverage", value: "100%", tone: "blue" },
        { label: language === "ko" ? "공용 Fragment" : "Public Fragments", value: displayMemoryNodeCount.toLocaleString(), tone: "cyan" },
        { label: language === "ko" ? "최신성" : "Freshness", value: learningDaemon?.worker_alive ? copy.listening : copy.ready, tone: "cyan" },
        { label: language === "ko" ? "Source Trust" : "Source Trust", value: "Tracked", tone: "white" },
        { label: language === "ko" ? "Edge Mirrors" : "Edge Mirrors", value: language === "ko" ? "읽기 전용" : "Read-only", tone: "green" },
      ]
      : [
        { label: copy.localBrain, value: graphPresentationMode === "home_unified_overview" || graphPresentationMode === "unified_projection" ? (language === "ko" ? "시각 레이어" : "Visual layer") : `${localAssistRatio}%`, tone: "green" },
        { label: copy.cloudBrain, value: graphPresentationMode === "home_unified_overview" || graphPresentationMode === "unified_projection" ? (language === "ko" ? "시각 레이어" : "Visual layer") : `${cloudAssistRatio}%`, tone: "blue" },
        { label: copy.learningEngine, value: learningDaemon?.worker_alive ? copy.listening : copy.ready, tone: "white" },
        { label: copy.generationEngine, value: isGeneratingAnswer ? copy.running : copy.ready, tone: "white" },
        { label: copy.fragmentSync, value: graphPresentationMode === "home_unified_overview" || graphPresentationMode === "unified_projection" ? (language === "ko" ? "연출" : "Staged") : copy.synced, tone: "cyan" },
      ];
  const providerStatusRows = [
    { label: "Cloud Provider", value: `${cloudProviderName} / ${cloudEndpointLabel}`, tone: cloudBrokerState === "remote_connected" ? "blue" : "white" },
    { label: "Broker State", value: cloudBrokerState, tone: cloudBrokerState === "remote_connected" ? "green" : "white" },
    { label: "Cloud Budget", value: `${cloudBudgetPlan.toUpperCase()} ${cloudBudgetRequests || 0}/day`, tone: "cyan" },
    { label: "Brain Balance", value: `${budgetLocalPct}% local / ${budgetCloudPct}% cloud`, tone: "blue" },
  ];
  const displayStatusRows = [...statusRows, ...providerStatusRows];
  const recentCards = [
    { title: copy.activity.graphUpdate, value: `${displayMemoryNodeCount.toLocaleString()} nodes / ${displayMemoryEdgeCount.toLocaleString()} relations`, time: logTime },
    { title: copy.activity.patchSync, value: signalTraceText, time: logTime },
    { title: copy.activity.runtime, value: daemonRuntimeText, time: logTime },
    { title: copy.activity.selected, value: selectedMemory?.label ?? "none", time: logTime },
  ];
  const sectionFallbackLabel: Record<MainSectionId, string> = {
    home: language === "ko" ? "대시보드" : "Dashboard",
    graph: language === "ko" ? "통합 지식 그래프" : "Unified Knowledge Graph",
    local: copy.localBrain,
    cloud: copy.cloudBrain,
    atlas: language === "ko" ? "아틀라스" : "Atlas",
    graphhub: "Graph Hub",
    contribute: language === "ko" ? "브레인 링크" : "Brain Link",
    chat: language === "ko" ? "채팅" : "Chat",
    settings: language === "ko" ? "설정" : "Settings",
  };
  const activeSectionLabel = copy.nav.find((item) => item.id === mainSection)?.label ?? sectionFallbackLabel[mainSection] ?? copy.nav[0].label;
  const isCloudViewerSection = mainSection === "cloud";
  const isLocalChatSection = mainSection === "local" || mainSection === "chat";
  const isOntologyChatSection = mainSection === "graph";
  const showInlineChatPanel = isOntologyChatSection || isLocalChatSection;
  const showRightRail = !isLocalChatSection;
  const showLowerSection = false;
  let lowerPanelTitle = isCloudViewerSection
    ? (language === "ko" ? "클라우드 브레인 뷰어" : "Cloud Brain Viewer")
    : isOntologyChatSection
      ? (language === "ko" ? "온톨로지 그래프 채팅" : "Ontology Graph Chat")
      : isLocalChatSection
      ? (language === "ko" ? "로컬 브레인 채팅" : "Local Brain Chat")
      : copy.chatTitle;
  let lowerPanelSubtitle = isCloudViewerSection
    ? (language === "ko"
      ? "공용 온톨로지 후보를 읽기 전용으로 관찰합니다. 질문 생성은 로컬 브레인에서만 실행됩니다."
      : "Read-only view of shared ontology candidates. Generative chat stays inside the Local Brain.")
    : isOntologyChatSection
      ? (language === "ko"
        ? "로컬/클라우드/작업 메모리의 관계를 함께 보며 질문합니다."
        : "Ask while inspecting Local, Cloud, and Working Memory relationships.")
      : isLocalChatSection
      ? (language === "ko"
        ? "로컬 Ghost Shell과 Payload Vault만 사용해 답변합니다."
        : "Chat against the local Ghost Shell and Payload Vault only.")
      : copy.chatSubtitle;
  if (language === "ko") {
    lowerPanelTitle = isCloudViewerSection
      ? "클라우드 브레인 뷰어"
      : isOntologyChatSection
        ? "온톨로지 그래프 채팅"
        : isLocalChatSection
          ? "로컬 브레인 채팅"
          : copy.chatTitle;
    lowerPanelSubtitle = isCloudViewerSection
      ? "공용 온톨로지 후보를 읽기 전용으로 관찰합니다. 질문 생성은 로컬 브레인에서만 실행됩니다."
      : isOntologyChatSection
        ? "그래프를 보면서 활성 노드와 Payload Vault 문맥을 기준으로 질문합니다."
        : isLocalChatSection
          ? "로컬 Ghost Shell과 Payload Vault만 사용해 답변합니다."
          : copy.chatSubtitle;
  }
  const ontologyPromptChips = language === "ko"
    ? ["브레인 라우팅 설명", "관련 메모리 보기", "앵커는 어떻게 선택해?"]
    : ["Explain unified-brain routing", "Show related memories", "How are anchors selected?"];
  const localPromptChips = language === "ko"
    ? ["내 로컬 메모리 구조 설명", "Payload Vault에는 뭐가 저장돼?", "최근 학습한 개념 보여줘"]
    : ["Explain my local memory", "What is stored in Payload Vault?", "Show recently learned concepts"];
  const activePromptChips = isLocalChatSection ? localPromptChips : ontologyPromptChips;
  const cloudViewerRows = [
    {
      label: language === "ko" ? "표시 노드" : "Visible nodes",
      value: displayMemoryNodeCount.toLocaleString(),
    },
    {
      label: language === "ko" ? "표시 관계" : "Visible relations",
      value: displayMemoryEdgeCount.toLocaleString(),
    },
    {
      label: language === "ko" ? "클라우드 보조" : "Cloud assist",
      value: `${cloudAssistRatio}%`,
    },
    {
      label: language === "ko" ? "조작 권한" : "Interaction",
      value: language === "ko" ? "읽기 전용" : "Viewer only",
    },
  ];
  const localBrainLayerCatalog = [
    { id: "local_user", label: language === "ko" ? "개인 로컬" : "Local User" },
    { id: "working_memory_local", label: language === "ko" ? "작업 메모리" : "Working Memory" },
    { id: "local_base", label: language === "ko" ? "기본 지식" : "Base Brain" },
    { id: "seed", label: language === "ko" ? "시드 앵커" : "Seed" },
    { id: "local_memory_candidate", label: language === "ko" ? "승격 후보" : "Candidates" },
  ];
  const cloudBrainLayerCatalog = [
    { id: "semantic_cloud", label: language === "ko" ? "의미 클라우드" : "Semantic Cloud" },
    { id: "graph_cartridge", label: language === "ko" ? "그래프 카트리지" : "Graph Cartridge" },
    { id: "cloud_attached", label: language === "ko" ? "임시 부착" : "Cloud Attached" },
    { id: "contributor", label: language === "ko" ? "기여 노드" : "Contributor" },
    { id: "working_memory_cloud", label: language === "ko" ? "클라우드 작업 메모리" : "Cloud WM" },
    { id: "surface_trace_summary", label: language === "ko" ? "표현 요약" : "Surface Summary" },
  ];
  const activeBrainGraph = activeTabBrainGraphRaw;
  const activeBrainLayerCatalog = mainSection === "cloud" ? cloudBrainLayerCatalog : localBrainLayerCatalog;
  const activeBrainLayerSelection = mainSection === "cloud" ? cloudBrainGraphLayers : localBrainGraphLayers;
  const activeBrainView = mainSection === "cloud" ? "cloud" : "local";
  const activeBrainLayerCounts = (activeBrainGraph?.stats as AnyRecord | undefined)?.layer_counts as AnyRecord | undefined;
  const activeBrainMissing = Array.isArray(activeBrainGraph?.layers_missing) ? activeBrainGraph.layers_missing as AnyRecord[] : [];
  const activeBrainRenderedNodes = Number((activeBrainGraph?.stats as AnyRecord | undefined)?.rendered_nodes ?? 0);
  const activeBrainRenderedEdges = Number((activeBrainGraph?.stats as AnyRecord | undefined)?.rendered_edges ?? 0);
  const activeBrainOverlay = brainGraphOverlayStatus ?? ((activeBrainGraph?.stats as AnyRecord | undefined)?.overlay as AnyRecord | undefined) ?? {};
  const activeBrainGraphRows = activeBrainLayerCatalog.map((item) => {
    const count = Number(activeBrainLayerCounts?.[item.id] ?? 0);
    const missing = activeBrainMissing.find((entry) => entry.layer === item.id);
    return {
      ...item,
      enabled: activeBrainLayerSelection.includes(item.id),
      count,
      missingReason: missing ? String(missing.reason ?? "unavailable") : "",
    };
  });
  const sourceInspector = (cloudBrainSourceInspector && typeof cloudBrainSourceInspector === "object" && !Array.isArray(cloudBrainSourceInspector))
    ? cloudBrainSourceInspector as AnyRecord
    : {};
  const remoteBrokerInspector = (sourceInspector.remote_cloudflare_broker && typeof sourceInspector.remote_cloudflare_broker === "object" && !Array.isArray(sourceInspector.remote_cloudflare_broker))
    ? sourceInspector.remote_cloudflare_broker as AnyRecord
    : {};
  const localProofInspector = (sourceInspector.local_proof_store && typeof sourceInspector.local_proof_store === "object" && !Array.isArray(sourceInspector.local_proof_store))
    ? sourceInspector.local_proof_store as AnyRecord
    : {};
  const mirrorInspector = (sourceInspector.cloud_mirror_snapshot && typeof sourceInspector.cloud_mirror_snapshot === "object" && !Array.isArray(sourceInspector.cloud_mirror_snapshot))
    ? sourceInspector.cloud_mirror_snapshot as AnyRecord
    : {};
  const activeCloudSourceMode = String(sourceInspector.active_source_mode ?? "local_broker_mode");
  const verifiedRemoteCloudBrain = activeCloudSourceMode === "remote_cloudflare_broker";
  const remoteProofStatus = String(remoteCloudProof?.result ?? (remoteBrokerInspector.remote_persistence ? "PASS" : "UNVERIFIED"));
  const sourceInspectorRows = [
    { label: language === "ko" ? "활성 소스" : "Active source", value: activeCloudSourceMode },
    { label: language === "ko" ? "Local proof" : "Local proof", value: `${Number(localProofInspector.fragments ?? 0)} / ${Number(localProofInspector.nodes ?? 0)}n` },
    { label: language === "ko" ? "Mirror snapshot" : "Mirror snapshot", value: `${Number(mirrorInspector.nodes ?? 0).toLocaleString()} / ${Number(mirrorInspector.edges ?? 0).toLocaleString()}` },
    { label: language === "ko" ? "Remote broker" : "Remote broker", value: remoteBrokerInspector.reachable ? String(remoteBrokerInspector.broker_state ?? "reachable") : "not verified" },
    { label: language === "ko" ? "Storage" : "Storage", value: String(remoteBrokerInspector.storage_backend ?? "unknown") },
    { label: language === "ko" ? "Read-back" : "Read-back", value: remoteBrokerInspector.fragment_readback_success ? "ok" : "not proven" },
  ];
  const sourceInspectorWarning = verifiedRemoteCloudBrain
    ? (language === "ko" ? "검증된 원격 Cloud Brain 브로커를 보고 있습니다." : "You are viewing a verified remote Cloud Brain broker.")
    : (language === "ko" ? "현재 화면은 실시간 원격 Cloud Brain이 아닙니다. 로컬 proof, 로컬 브로커 또는 미러 스냅샷입니다." : "You are not viewing the live remote Cloud Brain. This view is local proof, local broker, or mirror snapshot.");
  const semanticCloudRows = [
    { label: language === "ko" ? "개념" : "Concepts", value: String(semanticCloudStatus?.concepts ?? 0) },
    { label: language === "ko" ? "관계" : "Relations", value: String(semanticCloudStatus?.relations ?? 0) },
    { label: language === "ko" ? "근거" : "Evidence", value: String(semanticCloudStatus?.evidence ?? 0) },
    { label: language === "ko" ? "저장소" : "Store", value: semanticCloudStatus?.proof_store_only === false ? "external" : "proof only" },
  ];
  const semanticGrowthRows = [
    { label: language === "ko" ? "생성 개념" : "Concepts created", value: String(semanticGrowthRun?.concepts_created ?? 0) },
    { label: language === "ko" ? "병합 개념" : "Concepts merged", value: String(semanticGrowthRun?.concepts_merged ?? 0) },
    { label: language === "ko" ? "생성 관계" : "Relations created", value: String(semanticGrowthRun?.relations_created ?? 0) },
    { label: language === "ko" ? "강화 관계" : "Relations strengthened", value: String(semanticGrowthRun?.relations_strengthened ?? 0) },
    { label: language === "ko" ? "Local 기록" : "Local write", value: semanticGrowthRun?.honesty?.local_brain_write ? "true" : "false" },
    { label: language === "ko" ? "외부 LLM" : "External LLM", value: semanticGrowthRun?.honesty?.external_llm_used ? "true" : "false" },
  ];
  const semanticAttachRows = [
    { label: language === "ko" ? "임시 노드" : "Attached nodes", value: String((semanticAttachResult?.attached_nodes as AnyRecord[] | undefined)?.length ?? 0) },
    { label: language === "ko" ? "임시 관계" : "Attached edges", value: String((semanticAttachResult?.attached_edges as AnyRecord[] | undefined)?.length ?? 0) },
    { label: language === "ko" ? "임시성" : "Temporary", value: semanticAttachResult?.temporary ? "true" : "-" },
    { label: language === "ko" ? "Local 기록" : "Local write", value: semanticAttachResult?.local_brain_write ? "true" : "false" },
  ];
  const graphOverlay = (graph?.working_memory_overlay && typeof graph.working_memory_overlay === "object" && !Array.isArray(graph.working_memory_overlay))
    ? graph.working_memory_overlay as AnyRecord
    : ((cloudAttachmentStatus?.working_memory_overlay && typeof cloudAttachmentStatus.working_memory_overlay === "object" && !Array.isArray(cloudAttachmentStatus.working_memory_overlay))
      ? cloudAttachmentStatus.working_memory_overlay as AnyRecord
      : {});
  const cloudAttachedNodeCount = Number(graphOverlay.cloud_attached_nodes ?? (cloudAttachmentStatus?.cloud_attached_nodes ?? 0));
  const cloudAttachedEdgeCount = Number(graphOverlay.cloud_attached_edges ?? (cloudAttachmentStatus?.cloud_attached_edges ?? 0));
  const overlayBundleIds = Array.isArray(graphOverlay.bundle_ids) ? graphOverlay.bundle_ids as string[] : [];
  const webFeederState = (cloudBrainStatus?.web_feeder_state && typeof cloudBrainStatus.web_feeder_state === "object" && !Array.isArray(cloudBrainStatus.web_feeder_state))
    ? cloudBrainStatus.web_feeder_state as AnyRecord
    : {};
  const webFeederEnabled = Boolean(webFeederState.enabled);
  const webFeederStatus = String(webFeederState.status ?? webFeederState.last_status ?? "idle");
  const webFeederLastRun = String(webFeederState.last_run_at ?? "-");
  const webFeederCreated = Number(webFeederState.fragments_created ?? 0);
  const webFeederRejected = Number(webFeederState.fragments_rejected ?? 0);
  const webFeederRows = [
    { label: language === "ko" ? "상태" : "State", value: webFeederEnabled ? (language === "ko" ? "활성" : "Enabled") : (language === "ko" ? "비활성" : "Disabled") },
    { label: language === "ko" ? "최근 실행" : "Last run", value: webFeederLastRun },
    { label: language === "ko" ? "확인 소스" : "Sources checked", value: String(webFeederState.sources_checked ?? 0) },
    { label: language === "ko" ? "후보 생성" : "Candidates", value: String(webFeederCreated) },
    { label: language === "ko" ? "거절" : "Rejected", value: String(webFeederRejected) },
    { label: language === "ko" ? "마지막 상태" : "Last status", value: webFeederStatus },
  ];
  const webFeederMessage = !webFeederEnabled
    ? (language === "ko" ? "Web Seed Feeder는 비활성 상태입니다." : "Web Seed Feeder is disabled.")
    : webFeederCreated > 0
      ? (language === "ko" ? "새 공개 후보 fragment가 생성되었습니다. 검증/수집 대기 중입니다." : "New public candidate fragments were created. Waiting for verification/ingestion.")
      : webFeederStatus === "no_new_payload" || webFeederStatus === "listening"
        ? (language === "ko" ? "새 공개 seed payload를 대기 중입니다." : "Listening for new public seed payloads.")
        : (language === "ko" ? "Cloud Brain 카운트는 수집과 검증 이후에만 갱신됩니다." : "Cloud Brain counts update only after ingestion and verification.");
  const controlledGrowthState = (cloudBrainStatus?.controlled_self_growth_state && typeof cloudBrainStatus.controlled_self_growth_state === "object" && !Array.isArray(cloudBrainStatus.controlled_self_growth_state))
    ? cloudBrainStatus.controlled_self_growth_state as AnyRecord
    : {};
  const autonomousSelfGrowthActive = Boolean(
    webFeederEnabled
    && webFeederCreated > 0
    && controlledGrowthState.last_ingestion_success
    && String(controlledGrowthState.provenance_type ?? "").toLowerCase() === "autonomous_growth"
  );
  const semanticCloudConcepts = Number(semanticCloudStatus?.concepts ?? 0);
  const semanticCloudRelations = Number(semanticCloudStatus?.relations ?? 0);
  const semanticCloudEvidence = Number(semanticCloudStatus?.evidence ?? 0);
  const cloudTruthRows = [
    { label: language === "ko" ? "Store" : "Store", value: semanticCloudStatus?.proof_store_only === false ? "external" : "proof only" },
    { label: language === "ko" ? "Concepts" : "Concepts", value: String(semanticCloudConcepts) },
    { label: language === "ko" ? "Relations" : "Relations", value: String(semanticCloudRelations) },
    { label: language === "ko" ? "Evidence" : "Evidence", value: String(semanticCloudEvidence) },
    { label: language === "ko" ? "Self-growth" : "Self-growth", value: autonomousSelfGrowthActive ? (language === "ko" ? "활성" : "active") : (language === "ko" ? "비활성" : "inactive") },
    { label: language === "ko" ? "Web feeder" : "Web feeder", value: webFeederEnabled ? webFeederStatus : (language === "ko" ? "비활성" : "inactive") },
    { label: language === "ko" ? "Source" : "Source", value: semanticCloudConcepts > 0 ? (language === "ko" ? "sample / proof" : "sample / proof") : "empty" },
    { label: language === "ko" ? "Local write" : "Local write", value: "false" },
  ];
  const cloudSourceCompactRows = [
    { label: language === "ko" ? "Active source" : "Active source", value: activeCloudSourceMode },
    { label: language === "ko" ? "Remote broker" : "Remote broker", value: remoteBrokerInspector.reachable ? String(remoteBrokerInspector.broker_state ?? "reachable") : "not verified" },
    { label: language === "ko" ? "Mirror snapshot" : "Mirror snapshot", value: mirrorInspector.source_is_remote ? "remote" : "not live cloud" },
    { label: language === "ko" ? "Local Brain" : "Local Brain", value: `${Number(sourceInspector.local_brain_state?.local_total_nodes ?? 0)} / ${Number(sourceInspector.local_brain_state?.local_total_edges ?? 0)}` },
  ];
  const cloudAttachmentCompactRows = [
    { label: language === "ko" ? "Cloud attached" : "Cloud attached", value: `${cloudAttachedNodeCount} / ${cloudAttachedEdgeCount}` },
    { label: language === "ko" ? "Working Memory" : "Working Memory", value: cloudAttachedNodeCount > 0 ? "temporary" : "idle" },
    { label: language === "ko" ? "Bundles" : "Bundles", value: String(overlayBundleIds.length) },
    { label: language === "ko" ? "Local write" : "Local write", value: "false" },
  ];
  const cloudProofGraphState = (cloudBrainStatus?.cloud_graph_state && typeof cloudBrainStatus.cloud_graph_state === "object" && !Array.isArray(cloudBrainStatus.cloud_graph_state))
    ? cloudBrainStatus.cloud_graph_state as AnyRecord
    : {};
  const controlledGrowthRows = [
    { label: language === "ko" ? "검증 방식" : "Proof mode", value: String(controlledGrowthProof?.mode ?? controlledGrowthState.mode ?? "controlled_fixture_only") },
    { label: language === "ko" ? "후보 fragment" : "Candidate fragment", value: String(controlledGrowthProof?.fragment_id ?? controlledGrowthState.last_ingested_fragment_id ?? "-") },
    { label: language === "ko" ? "정렬" : "Alignment", value: controlledGrowthProof?.alignment_success ? (language === "ko" ? "seed 정렬" : "seed aligned") : (language === "ko" ? "대기" : "waiting") },
    { label: language === "ko" ? "수집 상태" : "Ingestion", value: controlledGrowthProof?.ingestion_success || controlledGrowthState.last_ingestion_success ? "ingested" : "pending" },
    { label: language === "ko" ? "신뢰 상태" : "Trust", value: controlledGrowthProof?.trust_state ? String(controlledGrowthProof.trust_state) : (controlledGrowthProof?.ingestion_success ? "seed_aligned" : "unverified") },
    { label: language === "ko" ? "읽기 검증" : "Read-back", value: controlledGrowthProof?.query_readback_success ? "ok" : "-" },
    { label: language === "ko" ? "추가 노드" : "Nodes added", value: String(controlledGrowthProof?.nodes_added ?? 0) },
    { label: language === "ko" ? "추가 관계" : "Edges added", value: String(controlledGrowthProof?.edges_added ?? 0) },
    { label: language === "ko" ? "Cloud 노드" : "Cloud nodes", value: String(controlledGrowthProof?.new_cloud_nodes ?? cloudProofGraphState.proof_store_nodes ?? 0) },
    { label: language === "ko" ? "Cloud 관계" : "Cloud edges", value: String(controlledGrowthProof?.new_cloud_edges ?? cloudProofGraphState.proof_store_edges ?? 0) },
    { label: language === "ko" ? "Local 기록" : "Local write", value: "0 / 0" },
    { label: language === "ko" ? "광역 크롤링" : "Broad crawl", value: "false" },
  ];
  const controlledGrowthMessage = controlledGrowthProof?.controlled_self_growth
    ? (language === "ko"
      ? "공개 fixture fragment가 Seed Graph에 정렬된 뒤 Cloud Brain proof store에만 수집되고, fragment query로 다시 읽혔습니다."
      : "The public fixture fragment aligned to the Seed Graph, entered only the Cloud Brain proof store, and was read back through fragment query.")
    : (language === "ko"
      ? "아직 controlled self-growth proof를 실행하지 않았습니다. 이 검증은 제한된 fixture만 사용하며 광역 크롤링을 주장하지 않습니다."
      : "Controlled self-growth proof has not run yet. This uses a bounded fixture only and does not claim broad crawling.");
  const cloudSphereRows = [
    { label: language === "ko" ? "Logical nodes" : "Logical nodes", value: cloudSphereStats?.logicalNodes ?? "0" },
    { label: language === "ko" ? "Actual materialized" : "Actual materialized", value: String(cloudSphereStats?.actualMaterializedNodes ?? 0) },
    { label: language === "ko" ? "Rendered nodes" : "Rendered nodes", value: String(cloudSphereStats?.renderedNodes ?? 0) },
    { label: language === "ko" ? "Active tiles" : "Active tiles", value: String(cloudSphereStats?.activeTiles ?? 0) },
    { label: language === "ko" ? "Zoom level" : "Zoom level", value: String(cloudSphereStats?.zoomLevel ?? 0) },
    { label: language === "ko" ? "Render budget" : "Render budget", value: `${cloudSphereStats?.renderBudgetNodes ?? 5000} / ${cloudSphereStats?.renderBudgetEdges ?? 10000}` },
    { label: language === "ko" ? "Compression" : "Compression", value: String(Boolean(cloudSphereStats?.compressionUsed)) },
    { label: language === "ko" ? "Aggregate nodes" : "Aggregate nodes", value: String(Boolean(cloudSphereStats?.semanticAggregateNodesUsed)) },
    { label: language === "ko" ? "Shell mode" : "Shell mode", value: String(Boolean(cloudSphereStats?.shellMode)) },
    { label: language === "ko" ? "Actual-node mode" : "Actual-node mode", value: String(Boolean(cloudSphereStats?.actualNodeMode)) },
  ];
  const cortexLastCycle = (cortexStatus?.last_cycle && typeof cortexStatus.last_cycle === "object" && !Array.isArray(cortexStatus.last_cycle))
    ? cortexStatus.last_cycle as AnyRecord
    : {};
  const cortexRows = [
    { label: language === "ko" ? "활성 노드" : "Active nodes", value: String(cortexLastCycle.activated_nodes ?? 0) },
    { label: language === "ko" ? "억제 노드" : "Inhibited nodes", value: String(cortexLastCycle.inhibited_nodes ?? 0) },
    { label: language === "ko" ? "작업공간" : "Workspace", value: String(cortexLastCycle.salience_nodes ?? 0) },
    { label: language === "ko" ? "예측 경로" : "Prediction paths", value: String(cortexLastCycle.prediction_paths ?? 0) },
    { label: language === "ko" ? "오차" : "Error", value: `${Math.round(Number(cortexLastCycle.prediction_error ?? 0) * 100)}%` },
    { label: language === "ko" ? "Crystal 후보" : "Crystal candidate", value: cortexLastCycle.knowledge_crystal_candidate ? "true" : "false" },
    { label: language === "ko" ? "Dream 질문" : "Dream questions", value: String(cortexStatus?.dream_questions ?? 0) },
    { label: language === "ko" ? "Local 기록" : "Local write", value: cortexLastCycle.local_brain_write ? "true" : "false" },
  ];
  const cortexPanelState = cortexLastCycle.enabled
    ? (language === "ko" ? "활성 trace" : "TRACE ACTIVE")
    : (language === "ko" ? "대기" : "READY");
  const qCortexLastRun = (qCortexStatus?.last_run && typeof qCortexStatus.last_run === "object" && !Array.isArray(qCortexStatus.last_run))
    ? qCortexStatus.last_run as AnyRecord
    : {};
  const qCortexTrace = (qCortexLastRun.trace && typeof qCortexLastRun.trace === "object" && !Array.isArray(qCortexLastRun.trace))
    ? qCortexLastRun.trace as AnyRecord
    : {};
  const qCortexRows = [
    { label: language === "ko" ? "문제 유형" : "Problem", value: String(qCortexLastRun.problem_type ?? "idle") },
    { label: language === "ko" ? "Solver" : "Solver", value: String(qCortexLastRun.solver_name ?? "local") },
    { label: language === "ko" ? "입력" : "Inputs", value: String(qCortexLastRun.input_count ?? 0) },
    { label: language === "ko" ? "선택" : "Selected", value: String(qCortexLastRun.selected_count ?? 0) },
    { label: language === "ko" ? "목적값" : "Objective", value: Number.isFinite(Number(qCortexLastRun.objective_value)) ? Number(qCortexLastRun.objective_value).toFixed(2) : "0.00" },
    { label: language === "ko" ? "Baseline Δ" : "Baseline delta", value: Number.isFinite(Number(qCortexTrace.baseline_delta)) ? Number(qCortexTrace.baseline_delta).toFixed(2) : "0.00" },
    { label: language === "ko" ? "양자 HW" : "Quantum HW", value: qCortexStatus?.real_quantum_hardware_used ? "true" : "false" },
    { label: language === "ko" ? "Local 기록" : "Local write", value: qCortexStatus?.local_brain_write ? "true" : "false" },
  ];
  const qCortexPanelState = qCortexStatus?.state === "active"
    ? (language === "ko" ? "고전 최적화" : "CLASSICAL OPTIMIZER")
    : (language === "ko" ? "대기" : "READY");
  const baseBrainPct = (value: unknown) => Number.isFinite(Number(value)) ? `${Math.round(Number(value) * 100)}%` : "-";
  const baseBrainRows = [
    { label: language === "ko" ? "팩" : "Pack", value: baseBrainStatus?.pack_exists ? "true" : "false" },
    { label: language === "ko" ? "Seed 관계" : "Seed relations", value: String(baseBrainStatus?.seed_relation_primitive_count ?? 0) },
    { label: language === "ko" ? "Semantic" : "Semantic", value: String(baseBrainStatus?.semantic_node_count ?? 0) },
    { label: language === "ko" ? "Relations" : "Relations", value: String(baseBrainStatus?.semantic_relation_count ?? 0) },
    { label: language === "ko" ? "Surface" : "Surface", value: String(baseBrainStatus?.surface_construction_count ?? 0) },
    { label: language === "ko" ? "Bench" : "Bench", value: String(baseBrainStatus?.benchmark_prompt_count ?? 0) },
    { label: "LLM", value: baseBrainStatus?.external_llm_used ? "true" : "false" },
    { label: "sLLM", value: baseBrainStatus?.external_sllm_used ? "true" : "false" },
  ];
  const baseBrainBenchmarkRows = [
    { label: language === "ko" ? "실행" : "Run", value: String(baseBrainBenchmark?.total_prompts ?? 0) },
    { label: language === "ko" ? "유용 답변" : "Useful", value: String(baseBrainBenchmark?.useful_answer_count ?? 0) },
    { label: language === "ko" ? "Trace hygiene" : "Trace hygiene", value: baseBrainPct(baseBrainBenchmark?.trace_hygiene_rate) },
    { label: language === "ko" ? "평균 품질" : "Avg quality", value: baseBrainPct(baseBrainBenchmark?.average_answer_quality) },
  ];
  const baseBrainPanelState = baseBrainRunning
    ? (language === "ko" ? "실행 중" : "RUNNING")
    : baseBrainStatus?.pack_exists
      ? (language === "ko" ? "팩 준비됨" : "PACK READY")
      : (language === "ko" ? "팩 대기" : "READY");
  const latestAnswerQualityRun = answerQualityRun ?? (
    answerQualityStatus?.latest_run && typeof answerQualityStatus.latest_run === "object" && !Array.isArray(answerQualityStatus.latest_run)
      ? answerQualityStatus.latest_run as AnyRecord
      : null
  );
  const answerQualityScores = (latestAnswerQualityRun?.average_scores && typeof latestAnswerQualityRun.average_scores === "object" && !Array.isArray(latestAnswerQualityRun.average_scores))
    ? latestAnswerQualityRun.average_scores as AnyRecord
    : {};
  const answerQualityCategories = (latestAnswerQualityRun?.category_scores && typeof latestAnswerQualityRun.category_scores === "object" && !Array.isArray(latestAnswerQualityRun.category_scores))
    ? latestAnswerQualityRun.category_scores as AnyRecord
    : {};
  const answerQualityFeedback = Array.isArray(latestAnswerQualityRun?.surface_feedback)
    ? latestAnswerQualityRun.surface_feedback as AnyRecord[]
    : [];
  const answerQualityWorstCases = Array.isArray(latestAnswerQualityRun?.worst_cases)
    ? latestAnswerQualityRun.worst_cases as AnyRecord[]
    : [];
  const answerQualityPct = (value: unknown) => Number.isFinite(Number(value)) ? `${Math.round(Number(value) * 100)}%` : "-";
  const answerQualityRows = [
    { label: language === "ko" ? "Overall" : "Overall", value: answerQualityPct(answerQualityScores.overall) },
    { label: language === "ko" ? "한국어 자연도" : "Korean naturalness", value: answerQualityPct((answerQualityCategories.korean_natural as AnyRecord | undefined)?.naturalness ?? answerQualityScores.naturalness) },
    { label: language === "ko" ? "영어 자연도" : "English naturalness", value: answerQualityPct((answerQualityCategories.english_answer as AnyRecord | undefined)?.naturalness ?? answerQualityScores.naturalness) },
    { label: language === "ko" ? "Trace hygiene" : "Trace hygiene", value: answerQualityPct(answerQualityScores.trace_hygiene) },
    { label: language === "ko" ? "Template score" : "Template score", value: answerQualityPct(answerQualityScores.template_smell) },
    { label: language === "ko" ? "Grounding" : "Grounding", value: answerQualityPct(answerQualityScores.grounding) },
    { label: language === "ko" ? "피드백" : "Feedback", value: String(answerQualityFeedback.length) },
    { label: language === "ko" ? "프롬프트" : "Prompts", value: String(latestAnswerQualityRun?.total_prompts ?? answerQualityStatus?.benchmark_prompts ?? 0) },
  ];
  const answerRepairRows = [
    { label: language === "ko" ? "Trace before" : "Trace before", value: answerQualityPct(answerRepairComparison?.trace_hygiene_before) },
    { label: language === "ko" ? "Trace after" : "Trace after", value: answerQualityPct(answerRepairComparison?.trace_hygiene_after) },
    { label: language === "ko" ? "Trace delta" : "Trace delta", value: Number.isFinite(Number(answerRepairComparison?.trace_hygiene_delta)) ? `${Math.round(Number(answerRepairComparison?.trace_hygiene_delta) * 100)}pt` : "-" },
    { label: language === "ko" ? "Overall delta" : "Overall delta", value: Number.isFinite(Number(answerRepairComparison?.overall_delta)) ? `${Math.round(Number(answerRepairComparison?.overall_delta) * 100)}pt` : "-" },
    { label: language === "ko" ? "수리 적용" : "Repairs", value: String(answerRepairComparison?.repairs_applied ?? 0) },
    { label: language === "ko" ? "남은 누출" : "Remaining leaks", value: String(Array.isArray(answerRepairComparison?.remaining_leakages) ? answerRepairComparison.remaining_leakages.length : 0) },
  ];
  const pendingRepairCandidates = repairCandidates.filter((item) => item.status === "pending");
  const approvedRepairCandidates = repairCandidates.filter((item) => item.status === "approved");
  const rejectedRepairCandidates = repairCandidates.filter((item) => item.status === "rejected");
  const enabledProductionRepairRules = productionRepairRules.filter((item) => item.enabled);
  const disabledProductionRepairRules = productionRepairRules.filter((item) => !item.enabled);
  const reviewQueueRows = [
    { label: language === "ko" ? "대기 후보" : "Pending", value: String(pendingRepairCandidates.length) },
    { label: language === "ko" ? "승인 후보" : "Approved", value: String(approvedRepairCandidates.length) },
    { label: language === "ko" ? "거절 후보" : "Rejected", value: String(rejectedRepairCandidates.length) },
    { label: language === "ko" ? "활성 규칙" : "Enabled rules", value: String(enabledProductionRepairRules.length) },
    { label: language === "ko" ? "비활성 규칙" : "Disabled rules", value: String(disabledProductionRepairRules.length) },
    { label: language === "ko" ? "감사 이벤트" : "Audit events", value: String(repairAuditEvents.length) },
  ];
  const answerQualityPanelState = answerQualityRunning
    ? (language === "ko" ? "측정 중" : "RUNNING")
    : answerRepairRunning
      ? (language === "ko" ? "수리 비교 중" : "REPAIR CHECK")
    : latestAnswerQualityRun
      ? (language === "ko" ? "최근 측정" : "LATEST RUN")
      : (language === "ko" ? "대기" : "READY");
  const atlasHub = (atlasStatus?.hub && typeof atlasStatus.hub === "object" && !Array.isArray(atlasStatus.hub))
    ? atlasStatus.hub as AnyRecord
    : { label: "Seoul Hub", lat: 37.5665, lng: 126.978 };
  const atlasNodes = Array.isArray(atlasStatus?.nodes) ? atlasStatus.nodes as AnyRecord[] : [];
  const atlasStats = (atlasStatus?.stats && typeof atlasStatus.stats === "object" && !Array.isArray(atlasStatus.stats))
    ? atlasStatus.stats as AnyRecord
    : {};
  const atlasRelay = (atlasStatus?.relay && typeof atlasStatus.relay === "object" && !Array.isArray(atlasStatus.relay))
    ? atlasStatus.relay as AnyRecord
    : { active_region: "East Asia", sequence: ["East Asia", "Europe", "North America", "Pacific"], status: "local_preview" };
  const atlasMyNode = (atlasStatus?.my_node && typeof atlasStatus.my_node === "object" && !Array.isArray(atlasStatus.my_node))
    ? atlasStatus.my_node as AnyRecord
    : {};
  const atlasPrivacy = (atlasStatus?.privacy && typeof atlasStatus.privacy === "object" && !Array.isArray(atlasStatus.privacy))
    ? atlasStatus.privacy as AnyRecord
    : {};
  const atlasMode = String(atlasStatus?.mode ?? "preview");
  const atlasProvider = String(atlasStatus?.provider ?? cloudProviderName ?? "local");
  const atlasBrokerState = String(atlasStatus?.broker_state ?? cloudBrokerState ?? "local_broker_mode");
  const atlasRemoteConnected = atlasBrokerState === "remote_connected";
  const atlasStatusCopy = atlasRemoteConnected
    ? (language === "ko" ? "Cloud Brain 원격 브로커에 연결되었습니다. 표시된 해외 릴레이 점은 실제 사용자 위치가 아니라 프리뷰 지역 신호입니다." : "Connected to the Cloud Brain remote broker. Overseas relay points are preview regional signals, not verified user locations.")
    : (language === "ko" ? "현재는 로컬/프리뷰 모드입니다. 글로벌 브레인 링크 네트워크는 아직 완전 활성화되지 않았습니다." : "Local/preview mode. The global Brain Link Network is not fully live yet.");
  const atlasRelaySequence = Array.isArray(atlasRelay.sequence) && atlasRelay.sequence.length
    ? atlasRelay.sequence.map((item) => String(item))
    : ["East Asia", "Europe", "North America", "Pacific"];
  const atlasUtcHour = clockNow ? clockNow.getUTCHours() : new Date().getUTCHours();
  const atlasComputedRelayRegion = atlasUtcHour <= 5
    ? "East Asia"
    : atlasUtcHour <= 11
      ? "Europe"
      : atlasUtcHour <= 18
        ? "North America"
        : "Pacific";
  const atlasActiveRelayRegion = String(atlasRelay.active_region ?? atlasComputedRelayRegion);
  const atlasRelayRegionLabel = (region: string) => {
    if (language !== "ko") return region;
    const labels: Record<string, string> = {
      "East Asia": "동아시아",
      Europe: "유럽",
      "North America": "북미",
      Pacific: "태평양",
    };
    return labels[region] ?? region;
  };
  const atlasDayNightAngle = Math.round((atlasUtcHour / 24) * 360 - 90);
  const atlasFragmentStore = String(
    cloudRemoteStatus?.storage && typeof cloudRemoteStatus.storage === "object" && !Array.isArray(cloudRemoteStatus.storage)
      ? (cloudRemoteStatus.storage as AnyRecord).fragment_store ?? "unknown"
      : atlasStatus?.fragment_store ?? "unknown",
  );
  const atlasHubPoint = projectAtlasPoint(
    Number(atlasHub.lat ?? 37.5665),
    Number(atlasHub.lng ?? 126.978) + atlasRotationDeg,
  );
  const atlasNodePoints = atlasNodes.map((node, index) => {
    const projected = projectAtlasPoint(Number(node.approximate_lat ?? 0), Number(node.approximate_lng ?? 0) + atlasRotationDeg);
    return {
      ...node,
      x: projected.x,
      y: projected.y,
      activity: Math.max(0.12, Math.min(1, Number(node.activity_level ?? 0.3))),
      state: String(node.state ?? "idle"),
      source: String(node.source ?? "preview"),
      key: String(node.display_id ?? `atlas-node-${index}`),
    };
  });
  const atlasGlobeNodes = useMemo(
    () => atlasNodes.map((node, index) => ({
      key: String(node.display_id ?? `atlas-node-${index}`),
      lat: Number(node.approximate_lat ?? 0),
      lng: Number(node.approximate_lng ?? 0),
                    activity: Math.max(0.12, Math.min(1, Number(node.activity_level ?? 0.3))),
                    state: String(node.state ?? "idle"),
                    source: String(node.source ?? "preview"),
                    role: String(node.role ?? ""),
                  })),
    [atlasNodes],
  );
  const atlasStatusCards = [
    { label: "Provider", value: atlasProvider },
    { label: "Broker", value: atlasBrokerState },
    { label: language === "ko" ? "Fragment Store" : "Fragment Store", value: atlasFragmentStore },
    { label: language === "ko" ? "활성 브레인 링크 노드" : "Active Brain Link Nodes", value: String(atlasStats.active_contributor_nodes ?? 0) },
    { label: language === "ko" ? "검증된 원격 노드" : "Verified Remote Nodes", value: String(atlasStats.verified_remote_contributor_nodes ?? 0) },
    { label: language === "ko" ? "공용 작업 / 분" : "Public Tasks / min", value: String(atlasStats.public_tasks_per_min ?? 0) },
  ];
  const atlasPrivacyRows = [
    { label: language === "ko" ? "Raw IP 저장" : "Raw IP stored", value: atlasPrivacy.raw_ip_stored ? "YES" : "NO" },
    { label: language === "ko" ? "정확 위치 표시" : "Exact location shown", value: atlasPrivacy.exact_location_shown ? "YES" : "NO" },
    { label: language === "ko" ? "개인 데이터 공유" : "Private data shared", value: atlasPrivacy.private_data_shared ? "YES" : "NO" },
    { label: language === "ko" ? "표시 정밀도" : "Display precision", value: String(atlasPrivacy.display_precision ?? "coarse_region_jittered") },
  ];
  const selectedMemoryTitle = selectedMemory
    ? String(selectedMemory.label ?? selectedMemory.id ?? "Selected Memory")
    : (language === "ko" ? "선택 대기" : "No node selected");
  const selectedMemoryDetail = selectedMemory
    ? String(selectedMemory.type ? memoryTypeText(String(selectedMemory.type)) : selectedMemory.id ?? "Graph node")
    : "";
  const epistemicRows = language === "ko"
    ? [
      { label: "Anchor", value: "Stable", tone: "green" },
      { label: "Evidence", value: cloudAssistRatio > 8 ? "Mixed" : "Partial", tone: "orange" },
      { label: "Noise Rejected", value: String(Math.max(1, Math.round(displayMemoryEdgeCount / Math.max(2200, displayMemoryNodeCount * 5)))), tone: "white" },
    ]
    : [
      { label: "Anchor", value: "Stable", tone: "green" },
      { label: "Evidence", value: cloudAssistRatio > 8 ? "Mixed" : "Partial", tone: "orange" },
      { label: "Noise Rejected", value: String(Math.max(1, Math.round(displayMemoryEdgeCount / Math.max(2200, displayMemoryNodeCount * 5)))), tone: "white" },
    ];
  const ontologyGuideTitle = language === "ko"
    ? "ATANOR에 오신 것을 환영합니다.\n당신의 통합 온톨로지 파트너."
    : "Welcome to ATANOR.\nYour unified ontology partner.";
  const ontologyGuideBody = language === "ko"
    ? "로컬 지식의 정확성과 Cloud Brain의 확장성을 함께 읽고, 연결하고, 검증합니다."
    : "It combines private precision with public breadth to reason, connect, and generate with confidence.";
  const activeSectionDetail: Record<MainSectionId, string> = {
    home: language === "ko" ? "그래프, 런타임, 생성 상태를 한 화면에서 봅니다." : "Overview of graph, runtime, and generation state.",
    graph: language === "ko" ? "통합 온톨로지 그래프를 탐색합니다." : "3D ontology graph exploration mode.",
    local: language === "ko" ? "로컬 기억과 Payload Vault를 기준으로 대화합니다." : "Prioritizing local memory and Payload Vault.",
    cloud: language === "ko" ? "공용 Cloud Fragment와 브로커 상태를 읽기 전용으로 봅니다." : "Viewing Cloud Brain bridge status.",
    atlas: language === "ko" ? "익명 지역 단위로 Cloud Brain 브레인 링크 신호를 시각화합니다." : "Visualizing anonymous regional Cloud Brain Link signals.",
    graphhub: language === "ko" ? "Graph Cartridge를 설치하고 읽기 전용으로 연결합니다." : "Install and attach Graph Cartridges read-only.",
    contribute: language === "ko" ? "유휴 자원을 안전하게 Cloud Brain 검증에 연결합니다." : "Link safe idle compute to the Cloud Brain.",
    chat: language === "ko" ? "로컬 브레인과 대화합니다." : "Chat with the Local Brain.",
    settings: language === "ko" ? "언어와 로컬 Companion 동기화 상태를 조정합니다." : "Language and local companion sync controls.",
  };

  function setMainLanguage(nextLanguage: Language) {
    setLanguage(nextLanguage);
    writeBrowserStorage("atanor.uiLanguage", nextLanguage);
    const url = new URL(window.location.href);
    url.searchParams.set("lang", nextLanguage);
    window.history.replaceState(null, "", url);
  }

  function openMainSection(id: MainSectionId) {
    setMainSection(id);
    setSelectedMemory(null);
    if (id === "home") {
      changeWorkspaceMode("lab");
      changeLayoutMode("split");
      setRightMode("process");
      resetGraph();
      return;
    }
    if (id === "graph") {
      changeWorkspaceMode("lab");
      changeLayoutMode("graph");
      setRightMode("process");
      resetGraph();
      return;
    }
    if (id === "local") {
      changeWorkspaceMode("lab");
      changeLayoutMode("split");
      setRightMode("process");
      setGraphSourceMode("memory");
      resetGraph();
      return;
    }
    if (id === "cloud") {
      changeWorkspaceMode("lab");
      changeLayoutMode("split");
      setRightMode("process");
      setGraphSourceMode("memory");
      resetGraph();
      return;
    }
    if (id === "atlas") {
      changeWorkspaceMode("daemon");
      changeLayoutMode("split");
      setRightMode("process");
      return;
    }
    if (id === "contribute") {
      changeWorkspaceMode("lab");
      changeLayoutMode("split");
      setRightMode("process");
      return;
    }
    if (id === "chat") {
      changeWorkspaceMode("lab");
      changeLayoutMode("split");
      setRightMode("chat");
      return;
    }
    changeLayoutMode("workbench");
    setRightMode("process");
  }

  async function enableContribution() {
    setContributionEnabled(true);
    setContributionPaused(false);
    if (!localBackendConnected) {
      setError(language === "ko" ? "로컬 Companion 연결 후 브레인 링크 노드를 시작할 수 있습니다." : "Connect the local companion before starting Brain Link Node.");
      return;
    }
    await directBackendJson<AnyRecord>(localBackendUrl, "/api/contribution/settings", {
      method: "POST",
      body: JSON.stringify({
        cpu_limit_percent: contributionCpuLimit,
        gpu_enabled: contributionGpuLimit > 0,
        gpu_limit_percent: contributionGpuLimit,
        ram_limit_gb: 2,
        battery_pause: true,
        thermal_pause: true,
      }),
    });
    await directBackendJson<AnyRecord>(localBackendUrl, "/api/contribution/register", { method: "POST" });
    const response = await directBackendJson<AnyRecord>(localBackendUrl, "/api/contribution/run-once", { method: "POST" });
    setContributionStatus(response);
    await refreshAll();
  }

  async function pauseContribution() {
    setContributionPaused(true);
    if (localBackendConnected) {
      const response = await directBackendJson<AnyRecord>(localBackendUrl, "/api/contribution/pause", { method: "POST" }).catch(() => null);
      if (response) setContributionStatus(response);
    }
  }

  async function resumeContribution() {
    setContributionEnabled(true);
    setContributionPaused(false);
    if (localBackendConnected) {
      const response = await directBackendJson<AnyRecord>(localBackendUrl, "/api/contribution/resume", { method: "POST" }).catch(() => null);
      if (response) setContributionStatus(response);
    }
  }

  async function handleGraphHubPrimary(item: AnyRecord) {
    const cartridgeId = String(item.cartridge_id);
    const pricingModel = String(item.pricing_model ?? "free");
    const entitlementStatus = String(item.entitlement_status ?? "locked");
    const installed = Boolean(item.installed);
    const attached = graphHubAttachments.some((row) => row.cartridge_id === cartridgeId && row.status === "attached");
    setGraphHubRunning(cartridgeId);
    setGraphHubError(null);
    try {
      if (attached) {
        await apiJson<AnyRecord>(`/api/graph-hub/detach/${encodeURIComponent(cartridgeId)}`, { method: "POST" }, localBackendConnected ? { localOnly: true } : {});
      } else if (pricingModel === "free" && entitlementStatus === "locked") {
        await apiJson<AnyRecord>(`/api/graph-hub/entitlements/free/${encodeURIComponent(cartridgeId)}`, { method: "POST" }, localBackendConnected ? { localOnly: true } : {});
        await apiJson<AnyRecord>(`/api/graph-hub/install/${encodeURIComponent(cartridgeId)}`, { method: "POST" }, localBackendConnected ? { localOnly: true } : {});
      } else if (pricingModel === "one_time" && entitlementStatus !== "owned") {
        await apiJson<AnyRecord>(`/api/graph-hub/entitlements/mock-purchase/${encodeURIComponent(cartridgeId)}`, { method: "POST" }, localBackendConnected ? { localOnly: true } : {});
      } else if (pricingModel === "subscription" && entitlementStatus !== "active_subscription") {
        await apiJson<AnyRecord>(`/api/graph-hub/entitlements/mock-subscribe/${encodeURIComponent(cartridgeId)}`, { method: "POST" }, localBackendConnected ? { localOnly: true } : {});
      } else if (!installed) {
        await apiJson<AnyRecord>(`/api/graph-hub/install/${encodeURIComponent(cartridgeId)}`, { method: "POST" }, localBackendConnected ? { localOnly: true } : {});
      } else {
        await apiJson<AnyRecord>(`/api/graph-hub/attach/${encodeURIComponent(cartridgeId)}`, {
          method: "POST",
          body: JSON.stringify({ scope: "session", read_only: true }),
        }, localBackendConnected ? { localOnly: true } : {});
      }
      await refreshGraphHub();
      const cloudGraph = await fetchJson<AnyRecord>(`/api/brain/graph?view=cloud&layers=${encodeURIComponent(cloudBrainGraphLayers.join(","))}&max_nodes=1000&max_edges=3000`).catch(() => null);
      if (cloudGraph) setBrainGraphCloud(cloudGraph);
    } catch (caught) {
      setGraphHubError(caught instanceof Error ? caught.message : "Graph Hub action failed.");
    } finally {
      setGraphHubRunning(null);
    }
  }

  function graphHubPrimaryLabel(item: AnyRecord) {
    const pricingModel = String(item.pricing_model ?? "free");
    const entitlementStatus = String(item.entitlement_status ?? "locked");
    const installed = Boolean(item.installed);
    const attached = graphHubAttachments.some((row) => row.cartridge_id === item.cartridge_id && row.status === "attached");
    if (attached) return language === "ko" ? "분리" : "Detach";
    if (pricingModel === "free" && entitlementStatus === "locked") return language === "ko" ? "무료 설치" : "Install Free";
    if (pricingModel === "one_time" && entitlementStatus !== "owned") return language === "ko" ? "한 번 구매" : "Buy once";
    if (pricingModel === "subscription" && entitlementStatus !== "active_subscription") return entitlementStatus === "expired_subscription" ? (language === "ko" ? "구독 갱신" : "Renew subscription") : (language === "ko" ? "구독 시작" : "Start subscription");
    if (!installed) return language === "ko" ? "설치" : "Install";
    return language === "ko" ? "읽기 전용 연결" : "Attach read-only";
  }

  function isMainSectionActive(id: MainSectionId) {
    return mainSection === id;
  }

  function startNewConversation() {
    setMainSection("local");
    changeWorkspaceMode("lab");
    changeLayoutMode("split");
    setRightMode("chat");
    setChatInput("");
    setChatMessages([{ role: "assistant", text: EFFECTIVE_INITIAL_ASSISTANT_MESSAGE[language] }]);
  }

  const quickActions = [
    { label: copy.actions.newChat, action: startNewConversation },
    { label: copy.actions.graphExplore, action: () => openMainSection("graph") },
    { label: copy.actions.memorySearch, action: () => {
      openMainSection("local");
      setMemoryQuery("GraphRAG");
      activateSignal(signalTraceForQuery("GraphRAG", visibleGraph3D), 6000);
      focusSearchResult();
    } },
    { label: copy.actions.learningTrigger, action: () => runAction(startLearningDaemon) },
    { label: copy.actions.checkpoint, action: () => runAction(checkpointLearningDaemon) },
  ];

  const graphHubCategories = useMemo(() => {
    const categories = graphHubCatalog
      .map((item) => String(item.category ?? "general").trim())
      .filter(Boolean);
    return ["all", ...Array.from(new Set(categories))];
  }, [graphHubCatalog]);

  const visibleGraphHubCatalog = useMemo(() => {
    const query = graphHubSearch.trim().toLowerCase();
    return graphHubCatalog.filter((item) => {
      const category = String(item.category ?? "general");
      const haystack = [
        item.name,
        item.subtitle,
        item.description,
        item.category,
        ...(Array.isArray(item.tags) ? item.tags : []),
      ].join(" ").toLowerCase();
      return (graphHubCategoryFilter === "all" || category === graphHubCategoryFilter)
        && (!query || haystack.includes(query));
    });
  }, [graphHubCatalog, graphHubCategoryFilter, graphHubSearch]);

  return (
    <main className="atanor-user-shell" data-language={language} data-section={mainSection}>
      <aside className="atanor-user-sidebar">
        <div className="atanor-user-brand">
          <img
            src="/atanor-logo-header-white.png"
            alt="ATANOR"
            onError={(event) => {
              event.currentTarget.style.display = "none";
            }}
          />
          <span>0.1.2</span>
        </div>
        <nav className="atanor-user-nav" aria-label="ATANOR sections">
          {copy.nav.map((item) => {
            const Icon = mainNavIcon[item.id];
            return (
              <button key={item.id} data-active={isMainSectionActive(item.id)} onClick={() => openMainSection(item.id)}>
                <span aria-hidden="true"><Icon size={17} strokeWidth={1.8} /></span>
                <strong>{item.label}</strong>
              </button>
            );
          })}
        </nav>
        <div className="atanor-user-connection">
          <span><i data-tone="green" />{copy.localBrain}</span>
          <strong>{localBackendConnected ? copy.connected : language === "ko" ? "대기" : "Fallback"}</strong>
          <span><i data-tone="blue" />{copy.cloudBrain}</span>
          <strong>{workspaceMode === "daemon" ? copy.connected : language === "ko" ? "뷰어" : "Viewer"}</strong>
        </div>
      </aside>

      <section className="atanor-user-main">
        <header className="atanor-user-topbar">
          <div className="atanor-user-topbar-spacer" aria-hidden="true" />
          <div className="atanor-user-top-actions">
            <span className="atanor-user-clock">{clockNow ? clockNow.toLocaleTimeString(language === "ko" ? "ko-KR" : "en-US") : "--:--:--"}</span>
            <div className="atanor-user-language" aria-label="Language">
              <button data-active={language === "en"} onClick={() => setMainLanguage("en")}>EN</button>
              <button data-active={language === "ko"} onClick={() => setMainLanguage("ko")}>KO</button>
            </div>
            <span className="atanor-user-settled-badge"><i />{copy.graphSettled}</span>
            <button
              className="atanor-user-icon-button"
              onClick={() => runAction(refreshAll)}
              aria-label={language === "ko" ? "상태 새로고침" : "Refresh status alerts"}
              title={language === "ko" ? "상태 새로고침" : "Refresh status alerts"}
            >
              <Bell size={16} strokeWidth={1.8} />
            </button>
            <button
              className="atanor-user-icon-button"
              data-active={mainSection === "settings"}
              onClick={() => openMainSection("settings")}
              aria-label={language === "ko" ? "설정 열기" : "Open settings"}
              title={language === "ko" ? "설정 열기" : "Open settings"}
            >
              <UserCircle size={18} strokeWidth={1.8} />
            </button>
            <button className="atanor-user-sync-button" onClick={() => runAction(refreshAll)} aria-label={copy.sync}>
              <RefreshCw size={14} strokeWidth={1.8} />
              <span>{copy.sync}</span>
            </button>
          </div>
        </header>

        {error ? (
          <p className="atanor-user-error" title={error}>
            {language === "ko" ? "로컬 엔진 동기화 대기" : "Local engine sync pending"}
          </p>
        ) : null}

        {mainSection === "atlas" ? (
          <section className="atanor-atlas-grid">
            <article className="atanor-atlas-hero">
              <header>
                <div>
                  <span>{language === "ko" ? "Cloud Brain Relay Preview" : "Cloud Brain Relay Preview"}</span>
                  <h2>ATANOR Atlas</h2>
                  <p>
                    {language === "ko"
                      ? "원격 브로커 연결 상태와 익명 지역 릴레이 프리뷰를 개인정보 없이 시각화합니다."
                      : "Privacy-safe visualization of remote broker state and anonymous regional relay preview."}
                  </p>
                </div>
                <strong data-remote={atlasRemoteConnected}>
                  <i />
                  {atlasRemoteConnected ? "REMOTE CONNECTED" : atlasMode.toUpperCase()}
                </strong>
              </header>
              <div
                className="atanor-atlas-stage"
                aria-label={language === "ko" ? "익명 지역 단위 Cloud Brain 동기화 지도" : "Anonymous regional Cloud Brain sync map"}
              >
                <AtlasGlobe3D
                  hub={{
                    lat: Number(atlasHub.lat ?? 37.5665),
                    lng: Number(atlasHub.lng ?? 126.978),
                  }}
                  language={language}
                  remoteConnected={atlasRemoteConnected}
                  nodes={atlasGlobeNodes}
                />
                <div className="atanor-atlas-caption">
                  <strong>{language === "ko" ? "서울 허브 릴레이" : "Seoul Hub Relay"}</strong>
                  <span>
                    {language === "ko"
                      ? "실제 WebGL 지구 · 공용 Fragment 검증 신호는 프리뷰 지역 점으로 표시됩니다. Raw IP, 정확 위치, 기기명, 개인 데이터는 표시하지 않습니다."
                      : "Real WebGL Earth · Public fragment verification signals are shown as preview regional points. No raw IP, exact location, device name, or private data is displayed."}
                  </span>
                </div>
              </div>
            </article>

            <aside className="atanor-atlas-side">
              <section className="atanor-atlas-panel">
                <h2>{language === "ko" ? "아틀라스 상태" : "Atlas Status"}</h2>
                <p className="atanor-atlas-state-copy">{atlasStatusCopy}</p>
                <div className="atanor-atlas-stat-grid">
                  {atlasStatusCards.map((card) => (
                    <span key={card.label}>
                      <small>{card.label}</small>
                      <strong>{card.value}</strong>
                    </span>
                  ))}
                </div>
              </section>

              <section className="atanor-atlas-panel">
                <h2>{language === "ko" ? "내 노드" : "My Node"}</h2>
                <p><span>{language === "ko" ? "상태" : "State"}</span><strong>{String(atlasMyNode.state ?? "Idle")}</strong></p>
                <p><span>{language === "ko" ? "모드" : "Mode"}</span><strong>{String(atlasMyNode.mode ?? "Brain Link Preview")}</strong></p>
                <p><span>CPU</span><strong>{String(atlasMyNode.cpu_limit_percent ?? 20)}%</strong></p>
                <p><span>RAM</span><strong>{String(atlasMyNode.ram_limit_gb ?? 2)}GB</strong></p>
                <p><span>{language === "ko" ? "개인 데이터" : "Private Data"}</span><strong>{String(atlasMyNode.private_data ?? "Not Shared")}</strong></p>
              </section>

              <section className="atanor-atlas-panel">
                <h2>Time-Zone Relay</h2>
                <p><span>{language === "ko" ? "태양 경계" : "Solar Terminator"}</span><strong>{language === "ko" ? "실시간" : "Live"}</strong></p>
                <p><span>{language === "ko" ? "시각 레이어" : "Visual Layer"}</span><strong>{language === "ko" ? "낮/밤 지구" : "Day/Night Earth"}</strong></p>
                <p><span>{language === "ko" ? "노드 신호" : "Node Signal"}</span><strong>{atlasStats.verified_remote_contributor_nodes ? "Mixed" : "Preview"}</strong></p>
                <p><span>{language === "ko" ? "원격 브로커" : "Remote Broker"}</span><strong>{atlasRemoteConnected ? "Connected" : atlasBrokerState}</strong></p>
                <p className="atanor-atlas-state-copy">
                  {language === "ko"
                    ? "지구의 낮과 밤 경계가 움직이면 깨어 있는 지역의 유휴 연산 노드가 Cloud Brain 작업을 이어받는 구조를 시각화합니다."
                    : "As Earth's day-night boundary moves, idle compute from awake regions can relay Cloud Brain work."}
                </p>
              </section>

              <section className="atanor-atlas-panel">
                <h2>{language === "ko" ? "개인정보 경계" : "Privacy Boundary"}</h2>
                {atlasPrivacyRows.map((row) => (
                  <p key={row.label}>
                    <span>{row.label}</span>
                    <strong>{row.value}</strong>
                  </p>
                ))}
              </section>
            </aside>
          </section>
        ) : mainSection === "graphhub" ? (
          <section className="atanor-graph-hub">
            <header className="atanor-graph-hub-hero">
              <div>
                <h2>Graph Hub</h2>
                <p>{language === "ko" ? "그래프 지식과 사고 회로를 탐색하고 설치하세요." : "Browse and install graph knowledge and reasoning circuits."}</p>
              </div>
              <button className="atanor-graph-hub-refresh" type="button" onClick={() => refreshGraphHub().catch(() => undefined)}>
                {language === "ko" ? "새로고침" : "Refresh"}
              </button>
            </header>

            <nav className="atanor-graph-hub-tabs" aria-label="Graph Hub views">
              {[
                ["catalog", language === "ko" ? "Catalog" : "Catalog"],
                ["installed", language === "ko" ? "Installed" : "Installed"],
                ["attachments", language === "ko" ? "Active Attachments" : "Active Attachments"],
                ["export", "Export"],
                ["audit", language === "ko" ? "Audit Log" : "Audit Log"],
              ].map(([id, label]) => (
                <button key={id} type="button" data-active={graphHubTab === id} onClick={() => setGraphHubTab(id as typeof graphHubTab)}>
                  <span>{label}</span>
                </button>
              ))}
            </nav>

            {graphHubTab === "catalog" ? (
              <article className="atanor-graph-hub-toolbar">
                <input
                  value={graphHubSearch}
                  onChange={(event) => setGraphHubSearch(event.currentTarget.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") refreshGraphHub().catch(() => undefined);
                  }}
                  placeholder={language === "ko" ? "카트리지 검색" : "Search cartridges"}
                />
                <div className="atanor-graph-hub-filters">
                  {graphHubCategories.map((filter) => (
                    <button key={filter} data-active={graphHubCategoryFilter === filter} onClick={() => setGraphHubCategoryFilter(filter)}>
                      {filter === "all" ? "All" : filter}
                    </button>
                  ))}
                </div>
                <div className="atanor-graph-hub-filters">
                  {["all", "free", "one_time", "subscription"].map((filter) => (
                    <button key={filter} data-active={graphHubPricingFilter === filter} onClick={() => setGraphHubPricingFilter(filter)}>
                      {filter === "all" ? "All" : filter === "one_time" ? (language === "ko" ? "Buy once" : "Buy once") : filter === "subscription" ? (language === "ko" ? "Subscription" : "Subscription") : "Free"}
                    </button>
                  ))}
                </div>
              </article>
            ) : null}

            {graphHubError ? <p className="atanor-user-error">{graphHubError}</p> : null}

            {graphHubTab === "catalog" ? (
              <section className="atanor-graph-hub-grid">
              {visibleGraphHubCatalog.map((item) => {
                const attached = graphHubAttachments.some((row) => row.cartridge_id === item.cartridge_id && row.status === "attached");
                const title = String(item.name ?? "Graph Cartridge");
                const initial = title.trim().slice(0, 1).toUpperCase();
                return (
                  <article className="atanor-graph-hub-card" key={String(item.cartridge_id)} data-attached={attached}>
                    <div className="atanor-graph-hub-cover" data-tone={String(item.category ?? "general")}>
                      <span>{initial}</span>
                      <i />
                    </div>
                    <header>
                      <span>{String(item.category ?? "general")}</span>
                      <strong>{item.verified_author ? (language === "ko" ? "Verified" : "Verified") : (language === "ko" ? "Local" : "Local")}</strong>
                    </header>
                    <h3>{title}</h3>
                    <p>{String(item.subtitle ?? "")}</p>
                    <div className="atanor-graph-hub-badges">
                      <span>{String(item.price_label ?? "Free")}</span>
                      {item.installed ? <span>{language === "ko" ? "Installed" : "Installed"}</span> : null}
                    </div>
                    <div className="atanor-graph-hub-card-actions">
                      <button disabled={graphHubRunning === item.cartridge_id} onClick={() => handleGraphHubPrimary(item)}>
                        <span>{graphHubRunning === item.cartridge_id ? (language === "ko" ? "처리 중" : "Working") : graphHubPrimaryLabel(item)}</span>
                      </button>
                      {item.installed ? (
                        <button
                          type="button"
                          onClick={() => runGraphHubAction(`uninstall-${String(item.cartridge_id)}`, `/api/graph-hub/uninstall/${encodeURIComponent(String(item.cartridge_id))}`)}
                        >
                          <span>{language === "ko" ? "설치 해제" : "Uninstall"}</span>
                        </button>
                      ) : null}
                      {item.pricing_model === "subscription" && item.entitlement_status === "active_subscription" ? (
                        <button
                          type="button"
                          onClick={() => runGraphHubAction(`expire-${String(item.cartridge_id)}`, `/api/graph-hub/entitlements/expire/${encodeURIComponent(String(item.cartridge_id))}`)}
                        >
                          <span>{language === "ko" ? "구독 관리" : "Manage"}</span>
                        </button>
                      ) : null}
                    </div>
                  </article>
                );
              })}
              {!visibleGraphHubCatalog.length ? (
                <article className="atanor-graph-hub-card">
                  <div className="atanor-graph-hub-cover">
                    <span>G</span>
                    <i />
                  </div>
                  <header>
                    <span>EMPTY</span>
                    <strong>Graph Hub</strong>
                  </header>
                  <h3>{language === "ko" ? "검색 결과가 없습니다" : "No cartridges found"}</h3>
                  <p>{language === "ko" ? "검색어나 필터를 조정해보세요." : "Try adjusting your search or filters."}</p>
                </article>
              ) : null}
              </section>
            ) : null}

            {graphHubTab !== "catalog" ? (
              <section className="atanor-graph-hub-lower">
              {graphHubTab === "installed" ? (
              <article>
                <h2>{language === "ko" ? "Installed Graphs" : "Installed Graphs"}</h2>
                {graphHubInstalled.length ? graphHubInstalled.map((item) => (
                  <p key={String(item.cartridge_id)}>
                    <span>{String(item.cartridge_id)}</span>
                    <strong>{String(item.entitlement_status ?? "unknown")}</strong>
                  </p>
                )) : <p>{language === "ko" ? "설치된 Graph Cartridge가 없습니다." : "No installed Graph Cartridges."}</p>}
              </article>
              ) : null}
              {graphHubTab === "attachments" ? (
              <article>
                <h2>{language === "ko" ? "Active Graph Attachments" : "Active Graph Attachments"}</h2>
                {graphHubAttachments.length ? graphHubAttachments.map((item, index) => (
                  <p key={`${String(item.attachment_id ?? item.cartridge_id)}-${index}`}>
                    <span>{String(item.cartridge_id)}</span>
                    <strong>{String(item.status)} · {String(item.working_memory_nodes ?? 0)}n</strong>
                  </p>
                )) : <p>{language === "ko" ? "활성 연결이 없습니다." : "No active attachments."}</p>}
              </article>
              ) : null}
              {graphHubTab === "export" ? (
              <article>
                <h2>Export</h2>
                <button
                  className="atanor-graph-hub-panel-action"
                  type="button"
                  disabled={graphHubRunning === "export"}
                  onClick={() => runGraphHubAction("export", "/api/graph-hub/export/semantic-cloud", {
                    cartridge_id: "semantic_cloud_kubernetes_demo",
                    name: "Semantic Cloud Kubernetes Demo",
                    description: "A small real proof-store export from the Semantic Cloud Growth Loop.",
                    pricing_model: "free",
                    limit_nodes: 100,
                    limit_edges: 300,
                  })}
                >
                  {language === "ko" ? "Semantic Cloud Demo 내보내기" : "Export Semantic Cloud Demo"}
                </button>
                <button
                  className="atanor-graph-hub-panel-action"
                  type="button"
                  disabled={graphHubRunning === "proof"}
                  onClick={() => runGraphHubAction("proof", "/api/graph-hub/proof")}
                >
                  {language === "ko" ? "Graph Hub 증명" : "Run Proof"}
                </button>
                {graphHubExport ? <p><span>{language === "ko" ? "최근 내보내기" : "Latest export"}</span><strong>{String(graphHubExport.exported_nodes ?? 0)} / {String(graphHubExport.exported_edges ?? 0)}</strong></p> : null}
                {graphHubProof ? <p><span>{language === "ko" ? "Proof" : "Proof"}</span><strong>{graphHubProof.passed ? "PASS" : "FAIL"}</strong></p> : null}
              </article>
              ) : null}
              {graphHubTab === "audit" ? (
              <article>
                <h2>{language === "ko" ? "Audit Log" : "Audit Log"}</h2>
                {graphHubAudit.slice(0, 5).map((event, index) => (
                  <p key={`${String(event.event_id)}-${index}`}>
                    <span>{String(event.event_type)}</span>
                    <strong>{String(event.cartridge_id ?? "Graph Hub")}</strong>
                  </p>
                ))}
              </article>
              ) : null}
              </section>
            ) : null}
          </section>
        ) : mainSection === "settings" ? (
          <section className="atanor-settings-grid">
            <article className="atanor-settings-hero">
              <div>
                <span>SYSTEM SETTINGS</span>
                <h2>{language === "ko" ? "ATANOR 실행 환경" : "ATANOR Runtime Control"}</h2>
                <p>
                  {language === "ko"
                    ? "ATANOR 앱의 언어, 로컬 Companion, 안전 모드, 브레인 라우팅 상태를 한 곳에서 관리합니다."
                    : "Manage language, local Companion, safety mode, and brain routing for the user-facing ATANOR app."}
                </p>
              </div>
              <div className="atanor-settings-metrics">
                <span><small>{language === "ko" ? "로컬 Companion" : "Local Companion"}</small><strong>{localBackendConnected ? copy.connected : language === "ko" ? "대기" : "Fallback"}</strong></span>
                <span><small>{language === "ko" ? "하드웨어 티어" : "Hardware Tier"}</small><strong>{edgeTierLabel}</strong></span>
                <span><small>{language === "ko" ? "학습 런타임" : "Learning Runtime"}</small><strong>{daemonRuntimeText}</strong></span>
                <span><small>{language === "ko" ? "라우팅" : "Routing"}</small><strong>{localAssistRatio}% / {cloudAssistRatio}%</strong></span>
              </div>
            </article>

            <article className="atanor-settings-panel">
              <header>
                <h2>{language === "ko" ? "언어와 표시" : "Language and Display"}</h2>
                <p>{language === "ko" ? "기본 UI 언어를 전환합니다. URL에 lang 파라미터가 있으면 그 값을 우선합니다." : "Switch the UI language. A lang URL parameter takes priority when present."}</p>
              </header>
              <div className="atanor-settings-segment" aria-label="Language">
                <button data-active={language === "en"} onClick={() => setMainLanguage("en")}>English</button>
                <button data-active={language === "ko"} onClick={() => setMainLanguage("ko")}>한국어</button>
              </div>
              <label className="atanor-settings-toggle">
                <span>{language === "ko" ? "웹 검색 보조" : "Web search assist"}</span>
                <input type="checkbox" checked={webSearchEnabled} onChange={(event) => setWebSearchEnabled(event.target.checked)} />
              </label>
            </article>

            <article className="atanor-settings-panel">
              <header>
                <h2>{language === "ko" ? "로컬 Companion" : "Local Companion"}</h2>
                <p>{language === "ko" ? "FastAPI Companion 주소를 지정하고 로컬 그래프와 동기화합니다." : "Point the app to the FastAPI Companion and sync the local graph."}</p>
              </header>
              <label className="atanor-settings-field">
                <span>{language === "ko" ? "API 주소" : "API URL"}</span>
                <input
                  value={localBackendUrl}
                  onChange={(event) => setLocalBackendUrl(event.currentTarget.value)}
                  spellCheck={false}
                />
              </label>
              <div className="atanor-settings-actions">
                <button onClick={() => runAction(() => connectLocalBackend(localBackendUrl))}>{language === "ko" ? "재연결" : "Reconnect"}</button>
                <button onClick={() => {
                  const defaultUrl = "http://127.0.0.1:8500";
                  setLocalBackendUrl(defaultUrl);
                  void runAction(() => connectLocalBackend(defaultUrl));
                }}>{language === "ko" ? "기본값" : "Default"}</button>
                <button onClick={disconnectLocalBackend}>{language === "ko" ? "해제" : "Disconnect"}</button>
              </div>
              <small>{localBackendDisplay}</small>
            </article>

            <article className="atanor-settings-panel">
              <header>
                <h2>{language === "ko" ? "브레인 링크 안전장치" : "Brain Link Safety"}</h2>
                <p>{language === "ko" ? "공용 fragment 작업은 허용하되 개인 Payload Vault와 로컬 데이터는 기본적으로 보호합니다." : "Allow public fragment jobs while keeping private Payload Vault and local data protected by default."}</p>
              </header>
              <label className="atanor-settings-toggle">
                <span>{language === "ko" ? "안전 모드" : "Safe mode"}</span>
                <input type="checkbox" checked={contributionSafeMode} onChange={(event) => setContributionSafeMode(event.target.checked)} />
              </label>
              <label className="atanor-settings-toggle">
                <span>{language === "ko" ? "공용 fragment 작업 허용" : "Allow public fragment jobs"}</span>
                <input type="checkbox" checked={contributionAllowPublic} onChange={(event) => setContributionAllowPublic(event.target.checked)} />
              </label>
              <label className="atanor-settings-toggle">
                <span>{language === "ko" ? "로컬 데이터 공유 금지" : "Local data sharing blocked"}</span>
                <input type="checkbox" checked readOnly disabled />
              </label>
              <label className="atanor-settings-slider">
                <span>CPU {language === "ko" ? "한도" : "limit"} {contributionCpuLimit}%</span>
                <input type="range" min={5} max={80} value={contributionCpuLimit} onChange={(event) => setContributionCpuLimit(Number(event.target.value))} />
              </label>
            </article>

            <article className="atanor-settings-panel atanor-settings-wide">
              <header>
                <h2>{language === "ko" ? "진단과 유지관리" : "Diagnostics and Maintenance"}</h2>
                <p>{language === "ko" ? "현재 세션의 그래프, 학습 데몬, Payload Vault 체크포인트를 수동으로 정리합니다." : "Manually refresh graph state, learning daemon state, and Payload Vault checkpoints."}</p>
              </header>
              <div className="atanor-settings-actions">
                <button onClick={() => runAction(refreshAll)}>{copy.sync}</button>
                <button onClick={() => runAction(startLearningDaemon)}>{copy.actions.learningTrigger}</button>
                <button onClick={() => runAction(checkpointLearningDaemon)}>{copy.actions.checkpoint}</button>
              </div>
              <div className="atanor-settings-status-list">
                <p><span>{language === "ko" ? "브레인 작업" : "Brain task"}</span><strong>{activeTaskLabel}</strong></p>
                <p><span>{language === "ko" ? "데몬 상태" : "Daemon"}</span><strong>{daemonStateText}</strong></p>
                <p><span>{language === "ko" ? "엣지 브로커" : "Edge broker"}</span><strong>{edgeBrokerLabel}</strong></p>
                <p><span>{language === "ko" ? "메모리" : "Memory"}</span><strong>{displayMemoryNodeCount.toLocaleString()} / {displayMemoryEdgeCount.toLocaleString()}</strong></p>
              </div>
            </article>
          </section>
        ) : mainSection === "contribute" ? (
          <section className="atanor-contribution-grid">
            <header className="atanor-brain-link-header">
              <div>
                <h2>Brain Link</h2>
                <p>{language === "ko" ? "설치된 그래프와 공용 Fragment 작업을 현재 브레인 흐름에 안전하게 연결합니다." : "Safely link installed graphs and public fragment work into the current brain flow."}</p>
              </div>
              <div className="atanor-brain-link-status">
                <span><small>{language === "ko" ? "활성 링크" : "Active links"}</small><strong>{graphHubAttachments.length + (contributionIsActive ? 1 : 0)}</strong></span>
                <span><small>{language === "ko" ? "부착 노드" : "Attached nodes"}</small><strong>{graphHubAttachments.reduce((total, item) => total + Number(item.working_memory_nodes ?? 0), 0)}</strong></span>
                <span><small>{language === "ko" ? "읽기 전용" : "Read-only"}</small><strong>ON</strong></span>
                <span><small>Local write</small><strong>false</strong></span>
              </div>
            </header>
            <article className="atanor-contribution-hero">
              <div className="atanor-contribution-ring" data-active={contributionIsActive}>
                <svg viewBox="0 0 120 120" aria-hidden="true">
                  <circle cx="60" cy="60" r="48" />
                  <circle cx="60" cy="60" r="48" style={{ strokeDasharray: `${contributionIsActive ? 286 : 72} 302` }} />
                </svg>
                <strong>{contributionStatusText}</strong>
                <span>{contributionIsActive ? (language === "ko" ? "활성" : "Active") : contributionPaused ? (language === "ko" ? "정지" : "Paused") : (language === "ko" ? "안정" : "Stable")}</span>
              </div>
              <div className="atanor-contribution-copy">
                <span>{language === "ko" ? "보호된 링크" : "Protected Link"}</span>
                <h2>{language === "ko" ? "공용 검증 채널이 안정적으로 대기 중입니다." : "Public verification channel is standing by."}</h2>
                <p>{language === "ko" ? "개인 데이터는 장치 안에 남기고, 공개 후보 조각의 신뢰 신호만 확인합니다." : "Private data stays on device; only public candidate trust signals are checked."}</p>
                <div className="atanor-contribution-badges">
                  <span>{language === "ko" ? "개인 금고 보존" : "Private vault sealed"}</span>
                  <span>{language === "ko" ? "공개 범위" : "Public scope"}</span>
                  <span>{language === "ko" ? `크레딧 x${contributionCreditMultiplier}` : `Credit x${contributionCreditMultiplier}`}</span>
                </div>
                <div className="atanor-contribution-actions">
                  <button onClick={() => runAction(enableContribution)}>
                    {contributionEnabled && !contributionPaused ? (language === "ko" ? "브레인 링크 갱신" : "Refresh Brain Link") : (language === "ko" ? "브레인 링크 연결" : "Connect Brain Link")}
                  </button>
                  <button onClick={contributionBlockedBySafety ? () => runAction(refreshAll) : contributionIsActive ? pauseContribution : resumeContribution}>
                    {contributionIsActive
                      ? (language === "ko" ? "일시정지" : "Pause")
                      : contributionBlockedBySafety
                        ? (language === "ko" ? "상태 재확인" : "Recheck")
                        : (language === "ko" ? "재개" : "Resume")}
                  </button>
                </div>
                {resourceStopReason ? <small className="atanor-contribution-hold">{resourceStopReason}</small> : null}
              </div>
              <div className="atanor-contribution-credit-summary">
                <span>{language === "ko" ? "브레인 링크 크레딧" : "Brain Link Credits"}</span>
                <strong>{contributionTotalCredit.toFixed(1)}</strong>
                <small>{language === "ko" ? `오늘 +${contributionTodayCredit.toFixed(1)} · 작업당 ${contributionEstimatedTaskCredit.toFixed(1)}` : `Today +${contributionTodayCredit.toFixed(1)} · ${contributionEstimatedTaskCredit.toFixed(1)} per task`}</small>
                <em>x{contributionCreditMultiplier}</em>
              </div>
              <div className="atanor-contribution-metrics">
                <span><small>CPU</small><strong>{contributionCpuUsage}%</strong></span>
                <span><small>GPU</small><strong>{contributionGpuAvailable ? `${contributionGpuUsage}%` : (language === "ko" ? "미감지" : "n/a")}</strong></span>
                <span><small>RAM</small><strong>{contributionRamGb.toFixed(1)}GB</strong></span>
                <span><small>{language === "ko" ? "네트워크" : "Network"}</small><strong>{contributionNetworkLabel}</strong></span>
              </div>
            </article>

            <aside className="atanor-contribution-side">
              <section>
                <h2>{language === "ko" ? "링크 라우팅" : "Link Routing"}</h2>
                <div className="atanor-routing-donut" style={{ ["--local-share" as string]: `${contributionSharedRatio}%` }}>
                  <strong>{contributionSharedRatio}%</strong>
                  <span>{language === "ko" ? "공용 작업" : "Public jobs"}</span>
                </div>
                <p><span>{language === "ko" ? "로컬 데이터 공유" : "Local data share"}</span><strong>{contributionLocalShareRatio}%</strong></p>
                <p><span>{language === "ko" ? "브로커" : "Broker"}</span><strong>{contributionBrokerState.replace(/_/g, " ")}</strong></p>
                <p><span>{language === "ko" ? "상태" : "State"}</span><strong>{contributionSafeSummary}</strong></p>
              </section>
              <section>
                <h2>{language === "ko" ? "현재 공용 작업" : "Current Public Task"}</h2>
                <div className="atanor-task-orb" />
                <strong>{String(contributionCurrentTask?.task_type ?? "public_fragment_validation").replace(/_/g, " ")}</strong>
                <p>{language === "ko" ? "공개 후보 조각의 중복과 신뢰 신호만 확인합니다." : "Checks only duplicate and trust signals for public candidates."}</p>
                <small>{contributionCurrentTask?.task_id ?? "local-broker"} · {contributionBackendState}</small>
              </section>
            </aside>

            <article className="atanor-contribution-card">
              <header className="atanor-credit-trend-header">
                <div>
                  <h2>{language === "ko" ? "크레딧 플로우" : "Credit Flow"}</h2>
                  <p>{language === "ko" ? "공용 Fragment 작업 보상 추세" : "Public fragment reward trend"}</p>
                </div>
                <strong>{contributionCreditLatest.toFixed(1)}</strong>
              </header>
              <div className="atanor-credit-chart" data-active={contributionIsActive}>
                <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
                  <polygon points={contributionCreditArea} />
                  <polyline points={contributionCreditPolyline} />
                  {contributionCreditTrend.map((point, index) => (
                    <circle key={`${point.x}-${index}`} cx={point.x} cy={point.y} r={index === contributionCreditTrend.length - 1 ? 2.4 : 1.2} />
                  ))}
                </svg>
                <div className="atanor-credit-chart-axis">
                  <span>{language === "ko" ? "대기" : "Standby"}</span>
                  <span>{language === "ko" ? "실시간" : "Live"}</span>
                </div>
              </div>
              <small className="atanor-credit-trend-meta">
                {language === "ko"
                  ? `${edgeTierLabel} · 완료 ${contributionCompletedTasks} · 대기 ${contributionWaitingCredit.toFixed(1)} credit`
                  : `${edgeTierLabel} · ${contributionCompletedTasks} tasks · ${contributionWaitingCredit.toFixed(1)} credit pending`}
              </small>
            </article>

            <article className="atanor-contribution-card">
              <h2>{language === "ko" ? "안전 및 개인정보" : "Safety and Privacy"}</h2>
              <div className="atanor-safety-list">
                <label><span>{language === "ko" ? "개인 데이터 공유 안 함" : "Do not share private data"}</span><input type="checkbox" checked readOnly /></label>
                <label><span>{language === "ko" ? "로컬 브레인 데이터 공유 금지" : "Local Brain sharing blocked"}</span><input type="checkbox" checked readOnly disabled /></label>
                <label><span>{language === "ko" ? "공용 fragment 작업 허용" : "Allow public fragment jobs"}</span><input type="checkbox" checked={contributionAllowPublic} onChange={(event) => setContributionAllowPublic(event.target.checked)} /></label>
                <label><span>{language === "ko" ? "안전 모드" : "Safe mode"}</span><input type="checkbox" checked={contributionSafeMode} onChange={(event) => setContributionSafeMode(event.target.checked)} /></label>
              </div>
            </article>

            <article className="atanor-contribution-wide">
              <details>
                <summary>{language === "ko" ? "자원 설정" : "Resource settings"}</summary>
                <div className="atanor-resource-slider">
                  <span>CPU {language === "ko" ? "한도" : "limit"} {contributionCpuLimit}%</span>
                  <input type="range" min={5} max={80} value={contributionCpuLimit} onChange={(event) => setContributionCpuLimit(Number(event.target.value))} />
                </div>
                <div className="atanor-resource-slider">
                  <span>GPU {language === "ko" ? "한도" : "limit"} {contributionGpuLimitEffective}% · {language === "ko" ? `크레딧 x${contributionCreditMultiplier}` : `credit x${contributionCreditMultiplier}`}</span>
                  <input type="range" min={0} max={95} value={contributionGpuLimit} disabled={!contributionGpuAvailable} onChange={(event) => setContributionGpuLimit(Number(event.target.value))} />
                  {!contributionGpuAvailable ? <small>{language === "ko" ? "GPU 텔레메트리가 연결되면 활성화됩니다." : "Enabled when GPU telemetry is available."}</small> : null}
                </div>
              </details>
              <details>
                <summary>{language === "ko" ? "브레인 링크 작업" : "Brain Link tasks"}</summary>
                <p>Public Fragment verification · Ghost hash dedupe · Source noise check · Public alias review</p>
              </details>
              <details>
                <summary>{language === "ko" ? "실시간 작동 로그" : "Live operation log"}</summary>
                <p>{edgeStatus?.ghost_shell?.logs?.slice?.(-2)?.join(" / ") ?? edgeBrokerLabel}</p>
              </details>
              <details>
                <summary>{language === "ko" ? "크레딧 정책" : "Credit policy"}</summary>
                <p>{language === "ko" ? "현재 제품은 내부 크레딧만 기록합니다. 암호화폐, 전송 가능한 토큰, 금융형 보상은 구현하지 않았습니다." : "This product build records internal credits only. Cryptocurrency, transferable tokens, and financial rewards are not implemented."}</p>
              </details>
            </article>
          </section>
        ) : (
        <>
        <section className="atanor-user-grid">
          {showInlineChatPanel ? (
            <article className={`atanor-user-chat-card atanor-user-ontology-chat-card ${isLocalChatSection ? "atanor-user-local-chat-card" : ""}`}>
              <header>
                <div>
                  <h2>{lowerPanelTitle}</h2>
                </div>
                <button data-active={webSearchEnabled} onClick={() => setWebSearchEnabled((enabled) => !enabled)}>
                  {language === "ko" ? `웹 ${webSearchEnabled ? "켜짐" : "꺼짐"}` : `Web ${webSearchEnabled ? "On" : "Off"}`}
                </button>
              </header>
              {isOntologyChatSection ? (
                <div className="atanor-ontology-guide">
                  <h3>{ontologyGuideTitle.split("\n").map((line) => <span key={line}>{line}</span>)}</h3>
                  <p>{ontologyGuideBody}</p>
                </div>
              ) : (
                <div className="atanor-local-chat-scope">
                  <span>{language === "ko" ? "로컬 전용" : "LOCAL ONLY"}</span>
                  <strong>{language === "ko" ? "개인 Ghost Shell과 Payload Vault 안에서만 답변합니다." : "Answers only from private Ghost Shell and Payload Vault."}</strong>
                </div>
              )}
              <div className="atanor-user-chat-scroll" ref={chatScrollRef}>
                {chatMessages.slice(-5).map((message, index) => (
                  <article key={`${message.role}-${index}`} data-role={message.role}>
                    <span>{message.role === "user" ? "User" : "ATANOR"}</span>
                    <p>{message.text}</p>
                    {message.evidence?.length ? (
                      <details className="atanor-trace-details">
                        <summary>{language === "ko" ? "근거 / Brain path" : "Evidence / Brain path"}</summary>
                        <small>{message.evidence.slice(0, 2).map((doc) => doc.chunk_id ?? doc.doc_id ?? "evidence").join(" · ")}</small>
                      </details>
                    ) : null}
                  </article>
                ))}
              </div>
              <div className="atanor-user-prompt-chips">
                {activePromptChips.map((chip) => (
                  <button key={chip} onClick={() => setChatInput(chip)}>{chip}</button>
                ))}
              </div>
              <div className="atanor-user-composer">
                <textarea
                  value={chatInput}
                  onChange={(event) => setChatInput(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      sendChat();
                    }
                  }}
                  placeholder={copy.placeholder}
                  aria-label={copy.placeholder}
                />
                <button disabled={isGeneratingAnswer} onClick={sendChat}>
                  {isGeneratingAnswer ? copy.generating : copy.send}
                </button>
              </div>
            </article>
          ) : null}

          <article className="atanor-user-graph-card" data-presentation={graphPresentationMode}>
            <div className="atanor-user-graph-meta">
              <div>
                <h2>{presentationCopy.graphTitle}</h2>
              </div>
              <div className="atanor-user-stat-stack">
                <span>{copy.nodes}<strong>{graphHeaderNodeText}</strong></span>
                <span>{copy.relations}<strong>{graphHeaderEdgeText}</strong></span>
                <span>{copy.sparsity}<strong>{graphSparsity}%</strong></span>
                <span>{copy.communities}<strong>{graphCommunities}</strong></span>
              </div>
            </div>
            <div className="atanor-user-graph-stage" data-presentation={graphPresentationMode}>
              {isCloudViewerSection && !visibleGraph3D.nodes.length ? (
                <CloudBrainSphereScene
                  edgeOpacity={graphEdgeOpacity}
                  highEnd={Boolean(benchmark?.hardware_tier === "Tier 1-M" || benchmark?.tier === "Tier 1-M")}
                  onStats={setCloudSphereStats}
                />
              ) : visibleGraph3D.nodes.length ? (
                <Rag3DScene
                  key={usesStudioGraph ? "atanor-home-studio-graph" : `atanor-${mainSection}-${graphPresentationMode}-sphere-graph`}
                  activeEdgeKeys={activeSignalEdgeKeys}
                  activeNodeIds={activeSignalNodeIds}
                  graph={userSceneGraph3D}
                  control={rag3dControl}
                  preserveSourceCoordinates={usesStudioGraph || usesSphereGraph}
                  theme="dark"
                  visualState={ragVisualState}
                  fitScale={graphFitScale}
                  showLabels={mainSection !== "local"}
                  edgeOpacity={graphEdgeOpacity}
                  onSelect={(node: Rag3DNode) => setSelectedMemory(node)}
                />
              ) : (
                <div className="atanor-user-empty-graph" data-status={localBackendStatus}>
                  <div className="atanor-empty-loader" aria-hidden="true">
                    <span />
                    <span />
                    <span />
                    <i />
                  </div>
                  <strong>{graphEmptyTitle}</strong>
                  <small>{graphEmptySubtitle}</small>
                </div>
              )}
              {mainSection !== "local" && mainSection !== "cloud" ? (
                <>
                  <div className="atanor-user-graph-label local">{presentationCopy.localLabel}<span>{presentationCopy.localDetail}</span></div>
                  <div className="atanor-user-graph-label cloud">{presentationCopy.cloudLabel}<span>{presentationCopy.cloudDetail}</span></div>
                </>
              ) : null}
              {mainSection !== "local" && mainSection !== "cloud" ? (
                <div className="atanor-user-graph-mini-legend" aria-label="Graph legend">
                  <span><i data-kind="local" />{presentationCopy.localNode}</span>
                  <span><i data-kind="cloud" />{presentationCopy.cloudNode}</span>
                  <span><i data-kind="fragment" />{presentationCopy.fragmentNode}</span>
                  <span><i data-kind="line" />{copy.strongRelation}</span>
                </div>
              ) : null}
              {mainSection !== "local" && mainSection !== "cloud" ? (
                <div className="atanor-user-graph-hint">{copy.graphHint}</div>
              ) : null}
              <div className="atanor-user-graph-tools">
                {mainSection === "local" || mainSection === "cloud" ? (
                  <label className="atanor-edge-opacity-control">
                    <span>{language === "ko" ? "연결선" : "Lines"}</span>
                    <input
                      aria-label={language === "ko" ? "연결선 선명도" : "Line clarity"}
                      max="0.86"
                      min="0.04"
                      step="0.02"
                      type="range"
                      value={graphEdgeOpacity}
                      onChange={(event) => setGraphEdgeOpacity(Number(event.target.value))}
                    />
                    <strong>{Math.round(graphEdgeOpacity * 100)}%</strong>
                  </label>
                ) : null}
                {mainSection === "local" ? (
                  <button
                    type="button"
                    onClick={attachCloudContext}
                    disabled={cloudAttachmentRunning}
                    aria-label={language === "ko" ? "Cloud Context 부착" : "Attach Cloud Context"}
                  >
                    {cloudAttachmentRunning
                      ? (language === "ko" ? "부착 중" : "Attaching")
                      : (language === "ko" ? "Cloud 부착" : "Attach Cloud")}
                  </button>
                ) : null}
                <button onClick={() => zoomGraph(-0.18)} aria-label="Zoom out">-</button>
                <button onClick={() => zoomGraph(0.18)} aria-label="Zoom in">+</button>
                <button onClick={resetGraph} aria-label={language === "ko" ? "그래프 초기화" : "Reset graph"}>
                  {language === "ko" ? "초기화" : "Reset"}
                </button>
              </div>
              {mainSection === "local" && (cloudAttachedNodeCount > 0 || Number(graphOverlay.seed_anchor_nodes ?? 0) > 0) ? (
                <div className="atanor-local-overlay-badge">
                  <span>{language === "ko" ? "Working Memory Overlay Active" : "Working Memory Overlay Active"}</span>
                  <strong>{`Cloud attached nodes: ${cloudAttachedNodeCount}`}</strong>
                  <small>{`Seed anchors: ${Number(graphOverlay.seed_anchor_nodes ?? 0)}`}</small>
                  <small>{`Local write: ${String(Boolean(graphOverlay.writes_to_local_brain)).toLowerCase()}`}</small>
                  <small>{language === "ko" ? "임시 부착 · Local Brain 저장 안 함" : "Temporary attachment · not saved to Local Brain"}</small>
                  {cortexLastCycle.enabled ? (
                    <small>CORTEX-G2 · {language === "ko" ? "활성" : "active"} {String(cortexLastCycle.activated_nodes ?? 0)} · error {Math.round(Number(cortexLastCycle.prediction_error ?? 0) * 100)}%</small>
                  ) : null}
                  <button type="button" onClick={detachCloudContext} disabled={cloudAttachmentRunning || cloudAttachedNodeCount === 0}>
                    Detach
                  </button>
                </div>
              ) : null}
              <small className="atanor-user-graph-state">{ragVisualState === "completed" ? copy.graphSettled : signalTraceText}</small>
            </div>
            <div className="atanor-user-legend">
              <span><i data-kind="local" />{presentationCopy.localNode}</span>
              <span><i data-kind="cloud" />{presentationCopy.cloudNode}</span>
              <span><i data-kind="fragment" />{presentationCopy.fragmentNode}</span>
              <span><i data-kind="line" />{copy.strongRelation}</span>
              <span><i data-kind="line-weak" />{copy.weakRelation}</span>
            </div>
            {mainSection === "local" || mainSection === "cloud" ? (
              <section className="atanor-brain-layer-panel" data-compact={mainSection === "cloud"}>
                <header>
                  <div>
                    <span>{mainSection === "local" ? "LOCAL VIEW" : "CLOUD VIEW"}</span>
                    <h3>{mainSection === "local" ? (language === "ko" ? "로컬 브레인 레이어" : "Local Brain Layers") : (language === "ko" ? "클라우드 브레인 레이어" : "Cloud Brain Layers")}</h3>
                  </div>
                  <button type="button" onClick={refreshBrainGraphPanels}>
                    {language === "ko" ? "레이어 갱신" : "Refresh layers"}
                  </button>
                </header>
                <div className="atanor-brain-layer-summary">
                  <span><small>{language === "ko" ? "표시 노드" : "Rendered nodes"}</small><strong>{tabBrainGraphPending ? "..." : activeBrainRenderedNodes.toLocaleString()}</strong></span>
                  <span><small>{language === "ko" ? "표시 관계" : "Rendered edges"}</small><strong>{tabBrainGraphPending ? "..." : activeBrainRenderedEdges.toLocaleString()}</strong></span>
                  <span><small>Overlay</small><strong>{activeBrainOverlay?.working_memory_active ? "active" : "idle"}</strong></span>
                  <span><small>Local write</small><strong>{String(Boolean(activeBrainOverlay?.local_brain_write)).toLowerCase()}</strong></span>
                </div>
                {mainSection === "cloud" ? (
                  <div className="atanor-brain-layer-strip" aria-label="Cloud Brain layer summary">
                    {activeBrainGraphRows.filter((row) => row.enabled && row.count > 0).slice(0, 4).map((row) => (
                      <span key={row.id}>{row.label}<strong>{row.count.toLocaleString()}</strong></span>
                    ))}
                  </div>
                ) : (
                  <>
                    <div className="atanor-brain-layer-list">
                      {activeBrainGraphRows.map((row) => (
                        <button
                          key={row.id}
                          type="button"
                          data-enabled={row.enabled}
                          data-missing={Boolean(row.missingReason)}
                          onClick={() => toggleBrainGraphLayer(activeBrainView, row.id)}
                        >
                          <span>{row.label}</span>
                          <strong>{row.enabled ? (tabBrainGraphPending ? "..." : row.count.toLocaleString()) : "off"}</strong>
                          {row.missingReason ? <small>{row.missingReason}</small> : null}
                        </button>
                      ))}
                    </div>
                    <p>{language === "ko" ? "Cloud attached 노드는 로컬 브레인 카운트에 포함하지 않습니다." : "Cloud-attached nodes are not counted as Local Brain memory."}</p>
                  </>
                )}
              </section>
            ) : null}
          </article>

          {showRightRail ? (
          <aside className="atanor-user-right-rail" data-variant={isOntologyChatSection ? "ontology" : isCloudViewerSection ? "cloud" : "default"}>
            {isOntologyChatSection ? (
              <>
                <section className="atanor-user-panel atanor-brain-routing-panel">
                  <h2>{language === "ko" ? "브레인 라우팅" : "Brain Routing"}</h2>
                  <div className="atanor-brain-routing-core" style={{ ["--cloud-share" as string]: `${cloudAssistRatio}%` }}>
                    <strong>{localAssistRatio}%</strong>
                    <span>Local</span>
                    <em>{cloudAssistRatio}% Cloud</em>
                  </div>
                  <p><span>{language === "ko" ? "Working Memory" : "Working Memory"}</span><strong>{continuousLearningActive ? "Active" : "Ready"}</strong></p>
                </section>
                <section className="atanor-user-panel atanor-epistemic-panel">
                  <h2>{language === "ko" ? "인식 상태" : "Epistemic State"}</h2>
                  {epistemicRows.map((row) => (
                    <p key={row.label}>
                      <span>{row.label}</span>
                      <strong data-tone={row.tone}>{row.value}</strong>
                    </p>
                  ))}
                </section>
                <section className="atanor-user-panel atanor-selected-memory-panel">
                  <h2>{language === "ko" ? "선택 메모리" : "Selected Memory"}</h2>
                  <div className="atanor-selected-memory-card">
                    <Network className="atanor-selected-memory-icon" size={22} strokeWidth={1.7} />
                    <div>
                      <strong>{selectedMemoryTitle}</strong>
                      <small>{selectedMemory ? memoryTypeText(String(selectedMemory.type ?? "concept")) : (language === "ko" ? "노드를 선택하세요" : "Select a node")}</small>
                    </div>
                  </div>
                  {selectedMemory ? (
                    <>
                      <p>{selectedMemoryDetail}</p>
                      <small>Type <strong>{String(selectedMemory.type ?? "Concept")}</strong></small>
                    </>
                  ) : null}
                </section>
              </>
            ) : isCloudViewerSection ? (
              <>
                <section className="atanor-user-panel atanor-cloud-viewer-panel">
                  <h2>{language === "ko" ? "Cloud Brain" : "Cloud Brain"}</h2>
                  <span className="atanor-user-readonly-badge">{language === "ko" ? "PROOF STORE" : "PROOF STORE"}</span>
                  <div className="atanor-user-viewer-grid">
                    {cloudTruthRows.map((row) => (
                      <span key={row.label}>
                        <small>{row.label}</small>
                        <strong>{row.value}</strong>
                      </span>
                    ))}
                  </div>
                  <p>
                    {language === "ko"
                      ? "현재 화면은 live global Cloud Brain이 아니라 로컬 semantic proof store와 임시 Cloud attached 상태를 읽기 전용으로 보여줍니다."
                      : "This view is a read-only local semantic proof store and temporary Cloud-attached state, not a live global Cloud Brain."}
                  </p>
                </section>
                <section className="atanor-user-panel atanor-cloud-viewer-panel">
                  <h2>{language === "ko" ? "Source Inspector" : "Source Inspector"}</h2>
                  <span className="atanor-user-readonly-badge">{verifiedRemoteCloudBrain ? "REMOTE VERIFIED" : "LOCAL / MIRROR"}</span>
                  <div className="atanor-user-viewer-grid">
                    {cloudSourceCompactRows.map((row) => (
                      <span key={row.label}>
                        <small>{row.label}</small>
                        <strong>{row.value}</strong>
                      </span>
                    ))}
                  </div>
                  <p>{sourceInspectorWarning}</p>
                  {remoteCloudProofError ? <p>{remoteCloudProofError}</p> : null}
                  {remoteCloudProof ? (
                    <p>{language === "ko" ? "마지막 검증" : "Last proof"}: {remoteProofStatus}</p>
                  ) : null}
                </section>
                <section className="atanor-user-panel atanor-cloud-viewer-panel">
                  <h2>{language === "ko" ? "Semantic Cloud Store" : "Semantic Cloud Store"}</h2>
                  <span className="atanor-user-readonly-badge">{language === "ko" ? "SAMPLE / PROOF" : "SAMPLE / PROOF"}</span>
                  <div className="atanor-user-viewer-grid">
                    {semanticCloudRows.map((row) => (
                      <span key={row.label}>
                        <small>{row.label}</small>
                        <strong>{row.value}</strong>
                      </span>
                    ))}
                  </div>
                  <p>
                    {language === "ko"
                      ? "표시 중인 semantic cloud는 proof/sample ingest 기반입니다. 자율 성장 또는 원격 공용 그래프로 과장하지 않습니다."
                      : "The visible semantic cloud is proof/sample-ingest based. It is not presented as autonomous growth or a verified remote public graph."}
                  </p>
                  {semanticGrowthError ? <p>{semanticGrowthError}</p> : null}
                </section>
                <section className="atanor-user-panel atanor-cloud-viewer-panel">
                  <h2>{language === "ko" ? "Cloud Attached" : "Cloud Attached"}</h2>
                  <span className="atanor-user-readonly-badge">{cloudAttachedNodeCount > 0 ? "TEMPORARY" : "IDLE"}</span>
                  <div className="atanor-user-viewer-grid">
                    {cloudAttachmentCompactRows.map((row) => (
                      <span key={row.label}>
                        <small>{row.label}</small>
                        <strong>{row.value}</strong>
                      </span>
                    ))}
                  </div>
                  <p>
                    {language === "ko"
                      ? "Cloud attached 노드는 임시 Working Memory overlay이며 Local Brain에 저장되지 않습니다."
                      : "Cloud-attached nodes are temporary Working Memory overlays and are not saved into Local Brain."}
                  </p>
                </section>
                <section className="atanor-user-panel atanor-cloud-viewer-panel">
                  <h2>Web Seed Feeder</h2>
                  <span className="atanor-user-readonly-badge">{webFeederEnabled ? (language === "ko" ? "대기 중" : "LISTENING") : (language === "ko" ? "비활성" : "DISABLED")}</span>
                  <div className="atanor-user-viewer-grid">
                    {webFeederRows.map((row) => (
                      <span key={row.label}>
                        <small>{row.label}</small>
                        <strong>{row.value}</strong>
                      </span>
                    ))}
                  </div>
                  <p>{webFeederMessage}</p>
                  <p>
                    {language === "ko"
                      ? "Cloud Brain 카운트는 후보 생성이 아니라 실제 수집과 검증 이후에만 갱신됩니다."
                      : "Cloud Brain counts change only after actual ingestion and verification, not candidate creation."}
                  </p>
                </section>
                <button
                  className="atanor-cloud-diagnostics-toggle"
                  type="button"
                  onClick={() => setCloudDiagnosticsOpen((open) => !open)}
                  aria-expanded={cloudDiagnosticsOpen}
                >
                  {cloudDiagnosticsOpen
                    ? (language === "ko" ? "진단 닫기" : "Close Diagnostics")
                    : (language === "ko" ? "진단 열기" : "Open Diagnostics")}
                </button>
                {cloudDiagnosticsOpen ? (
                  <>
                <section className="atanor-user-panel atanor-cloud-viewer-panel">
                  <h2>{language === "ko" ? "Controlled Fixture Proof" : "Controlled Fixture Proof"}</h2>
                  <span className="atanor-user-readonly-badge">{controlledGrowthProof?.controlled_self_growth ? "FIXTURE PASSED" : "FIXTURE ONLY"}</span>
                  <button
                    className="atanor-proof-action"
                    type="button"
                    onClick={runControlledGrowthProof}
                    disabled={controlledGrowthRunning}
                  >
                    {controlledGrowthRunning
                      ? (language === "ko" ? "검증 중" : "Running")
                      : (language === "ko" ? "제한 fixture 검증 실행" : "Run bounded fixture proof")}
                  </button>
                  <div className="atanor-user-viewer-grid">
                    {controlledGrowthRows.map((row) => (
                      <span key={row.label}>
                        <small>{row.label}</small>
                        <strong>{row.value}</strong>
                      </span>
                    ))}
                  </div>
                  <p>{controlledGrowthMessage}</p>
                  {controlledGrowthError ? <p>{controlledGrowthError}</p> : null}
                </section>
                <section className="atanor-user-panel atanor-cloud-viewer-panel">
                  <h2>{language === "ko" ? "Renderer Stress Shell" : "Renderer Stress Shell"}</h2>
                  <span className="atanor-user-readonly-badge">{cloudSphereStats?.actualNodeMode ? "ACTUAL NODES" : "SHELL CHUNKS"}</span>
                  <div className="atanor-user-viewer-grid">
                    {cloudSphereRows.map((row) => (
                      <span key={row.label}>
                        <small>{row.label}</small>
                        <strong>{row.value}</strong>
                      </span>
                    ))}
                  </div>
                  <p>
                    {language === "ko"
                      ? "Cloud Brain 노드는 개별 주소를 유지합니다. ATANOR는 가짜 aggregate 노드로 압축하지 않고, 현재 카메라에 필요한 shell chunk와 zoom 영역만 물질화합니다."
                      : "Cloud Brain nodes remain individually addressable. ATANOR does not compress nodes into fake aggregate nodes; it materializes only camera-visible shell chunks and zoom-focused regions."}
                  </p>
                  <p>
                    {language === "ko"
                      ? "이것은 trillion-scale logical node 전체가 동시에 RAM에 로드되거나 렌더링된다는 뜻이 아닙니다."
                      : "This does not mean all trillion-scale logical nodes are loaded or rendered simultaneously."}
                  </p>
                </section>
                <section className="atanor-user-panel atanor-cloud-viewer-panel">
                  <h2>CORTEX-G2</h2>
                  <span className="atanor-user-readonly-badge">{cortexPanelState}</span>
                  <div className="atanor-user-viewer-grid">
                    {cortexRows.map((row) => (
                      <span key={row.label}>
                        <small>{row.label}</small>
                        <strong>{row.value}</strong>
                      </span>
                    ))}
                  </div>
                  <p>
                    {language === "ko"
                      ? "Seed, Cloud attached, Working Memory 노드를 작은 작업공간으로 활성화하고 예측 오차를 기록합니다. 의식이나 무제한 자기학습을 주장하지 않습니다."
                      : "Activates Seed, Cloud-attached, and Working Memory nodes into a bounded workspace and records prediction error. It does not claim consciousness or unrestricted self-learning."}
                  </p>
                </section>
                <section className="atanor-user-panel atanor-cloud-viewer-panel">
                  <h2>Q-Cortex</h2>
                  <span className="atanor-user-readonly-badge">{qCortexPanelState}</span>
                  <div className="atanor-user-viewer-grid">
                    {qCortexRows.map((row) => (
                      <span key={row.label}>
                        <small>{row.label}</small>
                        <strong>{row.value}</strong>
                      </span>
                    ))}
                  </div>
                  <p>
                    {language === "ko"
                      ? "QUBO/Ising 형식으로 salience, evidence, creative path, planning 선택을 고전적으로 최적화합니다. 실제 양자 하드웨어나 양자 가속을 주장하지 않습니다."
                      : "Optimizes salience, evidence, creative paths, and planning as classical QUBO/Ising-style routing. It does not claim real quantum hardware or quantum speedup."}
                  </p>
                </section>
                {workspaceMode === "lab" ? (
                  <section className="atanor-user-panel atanor-cloud-viewer-panel">
                    <h2>Base Brain Lab</h2>
                    <span className="atanor-user-readonly-badge">{baseBrainPanelState}</span>
                    <div className="atanor-user-viewer-grid">
                      {baseBrainRows.map((row) => (
                        <span key={row.label}>
                          <small>{row.label}</small>
                          <strong>{row.value}</strong>
                        </span>
                      ))}
                    </div>
                    <input
                      className="atanor-base-brain-input"
                      value={baseBrainQuery}
                      onChange={(event) => setBaseBrainQuery(event.target.value)}
                      aria-label="Ask Base Brain without user data"
                    />
                    <button
                      className="atanor-proof-action"
                      type="button"
                      onClick={() => buildBaseBrainPack()}
                      disabled={baseBrainRunning}
                    >
                      {language === "ko" ? "Base Pack 빌드" : "Build Base Pack"}
                    </button>
                    <button
                      className="atanor-proof-action"
                      type="button"
                      onClick={() => askBaseBrain()}
                      disabled={baseBrainRunning || !baseBrainQuery.trim()}
                    >
                      {language === "ko" ? "사용자 데이터 없이 질문" : "Ask without user data"}
                    </button>
                    <button
                      className="atanor-proof-action"
                      type="button"
                      onClick={() => runBaseBrainBenchmark(10)}
                      disabled={baseBrainRunning}
                    >
                      {language === "ko" ? "Zero-user 벤치마크" : "Zero-user benchmark"}
                    </button>
                    {baseBrainBenchmark ? (
                      <div className="atanor-user-viewer-grid">
                        {baseBrainBenchmarkRows.map((row) => (
                          <span key={row.label}>
                            <small>{row.label}</small>
                            <strong>{row.value}</strong>
                          </span>
                        ))}
                      </div>
                    ) : null}
                    {baseBrainAnswer?.answer ? (
                      <div className="atanor-mini-log">
                        <strong>{language === "ko" ? "응답" : "Answer"}</strong>
                        <span>{String(baseBrainAnswer.answer)}</span>
                        <small>
                          {`semantic ${String(baseBrainAnswer.semantic_context_count ?? 0)} / surface ${String(baseBrainAnswer.surface_candidate_count ?? 0)} / LLM ${String(Boolean(baseBrainAnswer.external_llm_used))}`}
                        </small>
                      </div>
                    ) : null}
                    <p>
                      {language === "ko"
                        ? "사용자 문서, 외부 LLM, 외부 sLLM, 웹 호출 없이 Seed/Semantic/Surface Pack만으로 제한된 일반 질문을 검증합니다."
                        : "Verifies limited general answers using only Seed, Semantic, and Surface packs: no user documents, external LLM, external sLLM, or web calls."}
                    </p>
                    {baseBrainError ? <p>{baseBrainError}</p> : null}
                  </section>
                ) : null}
                {workspaceMode === "lab" ? (
                  <section className="atanor-user-panel atanor-cloud-viewer-panel">
                    <h2>Answer Quality Lab</h2>
                    <span className="atanor-user-readonly-badge">{answerQualityPanelState}</span>
                    <button
                      className="atanor-proof-action"
                      type="button"
                      onClick={() => runAnswerQualityLab(8)}
                      disabled={answerQualityRunning || answerRepairRunning}
                    >
                      {answerQualityRunning
                        ? (language === "ko" ? "소형 벤치마크 실행 중" : "Running mini benchmark")
                        : (language === "ko" ? "소형 벤치마크 실행" : "Run mini benchmark")}
                    </button>
                    <button
                      className="atanor-proof-action"
                      type="button"
                      onClick={() => runAnswerRepairComparison(8)}
                      disabled={answerQualityRunning || answerRepairRunning}
                    >
                      {answerRepairRunning
                        ? (language === "ko" ? "수리 비교 실행 중" : "Running repair comparison")
                        : (language === "ko" ? "수리 비교 실행" : "Run Repair Comparison")}
                    </button>
                    <div className="atanor-user-viewer-grid">
                      {answerQualityRows.map((row) => (
                        <span key={row.label}>
                          <small>{row.label}</small>
                          <strong>{row.value}</strong>
                        </span>
                      ))}
                    </div>
                    {answerQualityWorstCases.length ? (
                      <div className="atanor-user-viewer-grid">
                        {answerQualityWorstCases.slice(0, 4).map((item, index) => (
                          <span key={`${item.prompt_id ?? index}-${item.generator ?? "case"}`}>
                            <small>{String(item.generator ?? "case")}</small>
                            <strong>{answerQualityPct(item.overall)}</strong>
                          </span>
                        ))}
                      </div>
                    ) : null}
                    {answerRepairComparison ? (
                      <div className="atanor-user-viewer-grid">
                        {answerRepairRows.map((row) => (
                          <span key={row.label}>
                            <small>{row.label}</small>
                            <strong>{row.value}</strong>
                          </span>
                        ))}
                      </div>
                    ) : null}
                    <p>
                      {language === "ko"
                        ? "로컬 휴리스틱으로 자연도와 trace 숨김을 측정하고, 수리 후보는 검토 가능한 파일로만 남깁니다. 외부 LLM judge와 자동 승격은 없습니다."
                        : "Measures naturalness and trace hygiene locally. Repair candidates stay reviewable; no external LLM judge and no auto-promotion."}
                    </p>
                    {answerQualityError ? <p>{answerQualityError}</p> : null}
                    {answerRepairError ? <p>{answerRepairError}</p> : null}
                  </section>
                ) : null}
                {workspaceMode === "lab" ? (
                  <section className="atanor-user-panel atanor-cloud-viewer-panel">
                    <h2>Surface Repair Review Queue</h2>
                    <span className="atanor-user-readonly-badge">
                      {repairReviewRunning
                        ? (language === "ko" ? "검토 처리 중" : "REVIEWING")
                        : (language === "ko" ? "수동 승인 필요" : "MANUAL REVIEW")}
                    </span>
                    <button
                      className="atanor-proof-action"
                      type="button"
                      onClick={() => generateRepairCandidatesFromFeedback()}
                      disabled={repairReviewRunning || !answerQualityFeedback.length}
                    >
                      {language === "ko" ? "피드백 후보 생성" : "Generate candidates"}
                    </button>
                    <button
                      className="atanor-proof-action"
                      type="button"
                      onClick={() => refreshRepairReviewQueue()}
                      disabled={repairReviewRunning}
                    >
                      {language === "ko" ? "큐 새로고침" : "Refresh queue"}
                    </button>
                    <div className="atanor-user-viewer-grid">
                      {reviewQueueRows.map((row) => (
                        <span key={row.label}>
                          <small>{row.label}</small>
                          <strong>{row.value}</strong>
                        </span>
                      ))}
                    </div>
                    {pendingRepairCandidates.slice(0, 3).map((candidate) => {
                      const proposedRule = (candidate.proposed_rule && typeof candidate.proposed_rule === "object" && !Array.isArray(candidate.proposed_rule))
                        ? candidate.proposed_rule as AnyRecord
                        : {};
                      return (
                        <div className="atanor-mini-log" key={String(candidate.candidate_id)}>
                          <strong>{String(proposedRule.name ?? candidate.candidate_id)}</strong>
                          <small>{String(candidate.severity ?? "medium")} · {String(candidate.source_run_id ?? "manual")}</small>
                          <span>{String(candidate.reason ?? proposedRule.description ?? "")}</span>
                          <button
                            className="atanor-proof-action"
                            type="button"
                            onClick={() => reviewCandidateAction(String(candidate.candidate_id), "approve")}
                            disabled={repairReviewRunning}
                          >
                            {language === "ko" ? "승인" : "Approve"}
                          </button>
                          <button
                            className="atanor-proof-action"
                            type="button"
                            onClick={() => reviewCandidateAction(String(candidate.candidate_id), "reject")}
                            disabled={repairReviewRunning}
                          >
                            {language === "ko" ? "거절" : "Reject"}
                          </button>
                        </div>
                      );
                    })}
                    {productionRepairRules.slice(0, 3).map((rule) => (
                      <div className="atanor-mini-log" key={String(rule.rule_id)}>
                        <strong>{String(rule.name ?? rule.rule_id)}</strong>
                        <small>{rule.enabled ? "enabled" : "disabled"} · usage {String(rule.usage_count ?? 0)}</small>
                        <button
                          className="atanor-proof-action"
                          type="button"
                          onClick={() => rollbackProductionRepairRule(String(rule.rule_id))}
                          disabled={repairReviewRunning || !rule.enabled}
                        >
                          {language === "ko" ? "롤백" : "Rollback"}
                        </button>
                      </div>
                    ))}
                    {repairAuditEvents.slice(0, 3).map((event) => (
                      <p key={String(event.event_id)}>
                        <span>{String(event.event_type)}</span>
                        <strong>{String(event.rule_id ?? event.candidate_id ?? "")}</strong>
                      </p>
                    ))}
                    <p>
                      {language === "ko"
                        ? "후보는 자동으로 운영 규칙이 되지 않습니다. 승인, 거절, 롤백, 사용 기록은 로컬 감사 로그에 남습니다."
                        : "Candidates never become production rules automatically. Approval, rejection, rollback, and usage are written to the local audit log."}
                    </p>
                    {repairReviewError ? <p>{repairReviewError}</p> : null}
                  </section>
                ) : null}
                <section className="atanor-user-panel atanor-user-task">
                  <h2>{copy.activeTask}</h2>
                  <strong>{activeTaskLabel}</strong>
                  <span>{activeTaskRouteText}</span>
                  <div><i style={{ width: `${Math.min(100, activeTaskProgress)}%` }} /></div>
                  <small>{daemonRuntimeText}</small>
                </section>
                <section className="atanor-user-panel">
                  <h2>{copy.systemStatus}</h2>
                  {displayStatusRows.map((row) => (
                    <p key={row.label}>
                      <span><i data-tone={row.tone} />{row.label}</span>
                      <strong>{row.value}</strong>
                    </p>
                  ))}
                </section>
                  </>
                ) : null}
              </>
            ) : (
              <>
                <section className="atanor-user-panel atanor-cloud-attachment-panel">
                  <h2>{language === "ko" ? "Working Memory Overlay" : "Working Memory Overlay"}</h2>
                  <span className="atanor-user-readonly-badge">{cloudAttachedNodeCount > 0 ? "CLOUD ATTACHED" : "DETACHED"}</span>
                  <div className="atanor-user-viewer-grid">
                    <span>
                      <small>{language === "ko" ? "Cloud nodes" : "Cloud nodes"}</small>
                      <strong>{cloudAttachedNodeCount}</strong>
                    </span>
                    <span>
                      <small>{language === "ko" ? "Cloud edges" : "Cloud edges"}</small>
                      <strong>{cloudAttachedEdgeCount}</strong>
                    </span>
                    <span>
                      <small>{language === "ko" ? "Bundles" : "Bundles"}</small>
                      <strong>{overlayBundleIds.length}</strong>
                    </span>
                    <span>
                      <small>{language === "ko" ? "Local write" : "Local write"}</small>
                      <strong>false</strong>
                    </span>
                  </div>
                  <div className="atanor-proof-actions-row">
                    <button className="atanor-proof-action" type="button" onClick={attachCloudContext} disabled={cloudAttachmentRunning}>
                      {cloudAttachmentRunning ? (language === "ko" ? "연결 중" : "Attaching") : (language === "ko" ? "Cloud Context 붙이기" : "Attach Cloud Context")}
                    </button>
                    <button className="atanor-proof-action" type="button" onClick={detachCloudContext} disabled={cloudAttachmentRunning || cloudAttachedNodeCount === 0}>
                      {language === "ko" ? "Detach" : "Detach"}
                    </button>
                    <button className="atanor-proof-action" type="button" onClick={clearCloudOverlay} disabled={cloudAttachmentRunning || cloudAttachedNodeCount === 0}>
                      {language === "ko" ? "Clear" : "Clear"}
                    </button>
                  </div>
                  <p>
                    {language === "ko"
                      ? "Cloud attached 노드는 임시 Working Memory overlay입니다. Local Brain에 저장되지 않습니다."
                      : "Cloud attached nodes are temporary Working Memory overlays. They are not saved into Local Brain."}
                  </p>
                  {cloudAttachmentError ? <p>{cloudAttachmentError}</p> : null}
                </section>
                <section className="atanor-user-panel">
                  <h2>{copy.systemStatus}</h2>
                  {displayStatusRows.map((row) => (
                    <p key={row.label}>
                      <span><i data-tone={row.tone} />{row.label}</span>
                      <strong>{row.value}</strong>
                    </p>
                  ))}
                </section>
                <section className="atanor-user-panel atanor-user-task">
                  <h2>{copy.activeTask}</h2>
                  <strong>{activeTaskLabel}</strong>
                  <span>{activeTaskRouteText}</span>
                  <div><i style={{ width: `${Math.min(100, activeTaskProgress)}%` }} /></div>
                  <small>{daemonRuntimeText}</small>
                </section>
                <section className="atanor-user-panel atanor-user-actions">
                  <h2>{copy.quickActions}</h2>
                  {quickActions.map((action) => (
                    <button key={action.label} onClick={action.action}>{action.label}<span aria-hidden="true">{">"}</span></button>
                  ))}
                </section>
              </>
            )}
          </aside>
          ) : null}
        </section>

        {showLowerSection ? (
        <section className="atanor-user-lower">
          <article className="atanor-user-chat-card">
            <header>
              <div>
                <h2>{lowerPanelTitle}</h2>
                <p>{lowerPanelSubtitle}</p>
              </div>
              {isCloudViewerSection ? (
                <span className="atanor-user-readonly-badge">{language === "ko" ? "보기 전용" : "READ ONLY"}</span>
              ) : (
                <button data-active={webSearchEnabled} onClick={() => setWebSearchEnabled((enabled) => !enabled)}>
                  {language === "ko" ? `웹 ${webSearchEnabled ? "켜짐" : "꺼짐"}` : `Web ${webSearchEnabled ? "On" : "Off"}`}
                </button>
              )}
            </header>
            {isCloudViewerSection ? (
              <div className="atanor-user-viewer-stack">
                <div className="atanor-user-viewer-grid">
                  {cloudViewerRows.map((row) => (
                    <span key={row.label}>
                      <small>{row.label}</small>
                      <strong>{row.value}</strong>
                    </span>
                  ))}
                </div>
                <p>
                  {language === "ko"
                    ? "Cloud Brain은 현재 공용 후보와 proof store 상태를 관찰하는 읽기 전용 화면입니다. 질문 생성과 개인 메모리 검색은 로컬 브레인에서만 실행됩니다."
                    : "Cloud Brain is an observation surface for shared knowledge candidates and edge sync. Answer generation and private memory search run only in Local Brain."}
                </p>
              </div>
            ) : (
              <>
                <div className="atanor-user-chat-scroll" ref={chatScrollRef}>
                  {chatMessages.slice(-5).map((message, index) => (
                    <article key={`${message.role}-${index}`} data-role={message.role}>
                      <span>{message.role === "user" ? "User" : "ATANOR"}</span>
                      <p>{message.text}</p>
                      {message.evidence?.length ? (
                        <details className="atanor-trace-details">
                          <summary>{language === "ko" ? "근거 / Brain path" : "Evidence / Brain path"}</summary>
                          <small>{message.evidence.slice(0, 2).map((doc) => doc.chunk_id ?? doc.doc_id ?? "evidence").join(" · ")}</small>
                        </details>
                      ) : null}
                    </article>
                  ))}
                </div>
                <div className="atanor-user-composer">
                  <textarea
                    value={chatInput}
                    onChange={(event) => setChatInput(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" && !event.shiftKey) {
                        event.preventDefault();
                        sendChat();
                      }
                    }}
                    placeholder={copy.placeholder}
                    aria-label={copy.placeholder}
                  />
                  <button disabled={isGeneratingAnswer} onClick={sendChat}>
                    {isGeneratingAnswer ? copy.generating : copy.send}
                  </button>
                </div>
              </>
            )}
          </article>

          <article className="atanor-user-activity">
            <header>
              <h2>{copy.recentActivity}</h2>
              <span>{localBackendConnected ? "stream connected" : "local companion pending"}</span>
            </header>
            <div>
              {recentCards.map((card) => (
                <section key={card.title}>
                  <time>{card.time}</time>
                  <strong>{card.title}</strong>
                  <span>{card.value}</span>
                </section>
              ))}
            </div>
          </article>
        </section>
        ) : null}
        </>
        )}
      </section>
      <TauriUpdatePrompt />
    </main>
  );

  /*
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
          <button className="back-button" onClick={resetConsole} title="湲곕낯 ?붾㈃?쇰줈 ?뚯븘媛湲? aria-label="湲곕낯 ?붾㈃?쇰줈 ?뚯븘媛湲?>??/button>
          <strong>ATANOR</strong>
        </div>
        <div className="workspace-switcher" aria-label="?묒뾽 怨듦컙 ?꾪솚">
          <button data-active={workspaceMode === "lab"} onClick={() => changeWorkspaceMode("lab")}>濡쒖뺄 釉뚮젅??[LOCAL BRAIN]</button>
          <button data-active={workspaceMode === "daemon"} onClick={() => changeWorkspaceMode("daemon")}>?대씪?곕뱶 釉뚮젅??[CLOUD BRAIN]</button>
        </div>
        <div className="layout-switcher" aria-label="?덉씠?꾩썐 ?꾪솚">
          {[
            ["graph", "洹몃옒??],
            ["split", "遺꾪븷"],
            ["workbench", "?뚰겕踰ㅼ튂"],
          ].map(([mode, label]) => (
            <button key={mode} data-active={layoutMode === mode} onClick={() => changeLayoutMode(mode as LayoutMode)}>
              {label}
            </button>
          ))}
        </div>
        <div className="header-status">
          {workspaceMode === "lab" ? (
            <button
              className="build-button"
              onClick={runNextLabStage}
              disabled={isBuilding || (Boolean(activeAction) && !continuousLearningActive)}
            >
              {headerBuildLabel}
            </button>
          ) : (
            <span className="viewer-pill">?쎄린 ?꾩슜</span>
          )}
          <span>{workspaceMode === "lab" ? `?④퀎 ${processSteps.length}` : "釉뚮젅??酉곗뼱"}</span>
          <strong>{workspaceMode === "daemon" ? "?대씪?곕뱶 釉뚮젅???곹깭" : rightMode === "chat" ? "RAG 梨꾪똿" : "?숈뒿 怨쇱젙"}</strong>
          <StatusDot state={headerStatusState} />
        </div>
      </header>

      {error ? <p className="error-banner">?묒뾽 ?ㅽ뙣: {error}</p> : null}

      <section className="console-content">
        <aside className="panel-wrap left" style={leftStyle}>
          <section className="memory-panel">
            <div className="memory-header">
              <div>
                <h1>?⑦넧濡쒖? 硫붾え由?/h1>
                <p>RAG媛 李몄“?섎뒗 媛쒕뀗 湲곗뼲留?/p>
              </div>
              <div className="memory-tools">
                <span>{displayMemoryNodeCount} ?몃뱶</span>
                <span>{displayMemoryEdgeCount} 愿怨?/span>
                <button onClick={() => runAction(refreshAll)}>?덈줈怨좎묠</button>
                <button onClick={() => changeLayoutMode(layoutMode === "graph" ? "split" : "graph")}>?뺣?</button>
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
                  placeholder="?몃뱶 寃??
                  aria-label="?⑦넧濡쒖? ?몃뱶 寃??
                />
                <button onClick={focusSearchResult}>李얘린</button>
              </div>
              <div className="graph-nav" aria-label="洹몃옒???대룞 諛??뺣?">
                <button onClick={() => zoomGraph(-0.18)} title="異뺤냼">??/button>
                <button onClick={() => zoomGraph(0.18)} title="?뺣?">竊?/button>
                <button onClick={() => panGraph(0, -8)} title="?꾨줈 ?대룞">??/button>
                <button onClick={() => panGraph(-8, 0)} title="?쇱そ ?대룞">??/button>
                <button onClick={() => panGraph(8, 0)} title="?ㅻⅨ履??대룞">??/button>
                <button onClick={() => panGraph(0, 8)} title="?꾨옒濡??대룞">??/button>
                <button onClick={resetGraph} title="洹몃옒??珥덇린?? aria-label="洹몃옒??珥덇린??>??/button>
              </div>
              <span className="zoom-readout">{Math.round(graphView.scale * 100)}%</span>
            </div>
            <div className="memory-canvas" data-dragging={dragState ? "true" : "false"}>
              {graphMode === "3d" && visibleGraph3D.nodes.length ? (
                <>
                  <Rag3DScene
                    activeEdgeKeys={activeSignalEdgeKeys}
                    activeNodeIds={activeSignalNodeIds}
                    graph={visibleGraph3D}
                    control={rag3dControl}
                    theme="dark"
                    visualState={ragVisualState}
                    onSelect={(node: Rag3DNode) => setSelectedMemory(node)}
                  />
                  <div className="rag3d-overlay">
                    <strong>3D GraphRAG ?먯깋</strong>
                    <span>{visibleGraph3D.nodes.length} ?몃뱶 / {visibleGraph3D.edges.length} 愿怨?/span>
                    <span>{graphOverlayMessage}</span>
                    {buildRun && graphSourceMode === "build" && visibleLiveNodeCount > 0 ? (
                      <span>
                        湲곗〈 ?듭빱 {preservedAnchorNodeCount} ?좎? / ???몃뱶 {visibleLiveNodeCount} ?꾩껜 ?꾩쟻 ?쒖떆
                      </span>
                    ) : null}
                    {buildRun && graphSourceMode === "build" && visibleLiveNodeCount === 0 ? (
                      <span>????듭빱 {preservedAnchorNodeCount}媛?援ъ꽦</span>
                    ) : null}
                    {newestLiveNodeId && graphSourceMode === "build" ? <span>理쒖떊 ???몃뱶 {newestLiveNodeId} / ?꾩껜 live ?몃뱶 ?쒖떆 以?/span> : null}
                    <span className="signal-trace" data-active={activeSignalNodeIds.length > 0 || isGeneratingAnswer}>{signalTraceText}</span>
                  </div>
                </>
              ) : workspaceMode === "daemon" && !daemonGraphReady ? (
                <div className="memory-empty-state">
                  <strong>?대씪?곕뱶 釉뚮젅??洹몃옒???湲?/strong>
                  <p>濡쒖뺄 FastAPI? 釉뚮젅???뚯빱媛 ?ㅼ젣濡??ㅽ뻾?섎㈃ ???곸뿭??怨듭쑀 ?⑦넧濡쒖? ?꾨낫 洹몃옒?꾧? ?섑??⑸땲??</p>
                  <span>{localBackendConnected ? "濡쒖뺄 API ?곌껐??쨌 worker not alive" : "濡쒖뺄 API ?곌껐 ??쨌 鍮??붾㈃ ?좎?"}</span>
                </div>
              ) : (
              <svg
                ref={graphRef}
                viewBox="0 0 100 100"
                preserveAspectRatio="none"
                aria-label="?⑦넧濡쒖? 硫붾え由?洹몃옒??
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
                {visibleGraph3D.nodes.length ? memoryLegendItems.slice(0, 12).map((node) => (
                  <span key={node.type}><i style={{ background: node.color }} />{memoryTypeText(node.type)}</span>
                )) : null}
              </div>
              {selectedMemory ? (
                <div className="memory-detail">
                  <button onClick={() => setSelectedMemory(null)}>횞</button>
                  <span>{selectedMemory.relation ? "愿怨? : "硫붾え由??몃뱶"}</span>
                  <strong>{selectedMemory.label ?? selectedMemory.relation}</strong>
                  <p>{selectedMemory.type ? memoryTypeText(selectedMemory.type) : `${selectedMemory.source} ??${selectedMemory.target}`}</p>
                </div>
              ) : null}
            </div>
          </section>
        </aside>

        <section className="panel-wrap right" style={rightStyle}>
          <div className="right-panel">
            <div className="right-toolbar">
              {workspaceMode === "lab" ? (
                <div className="mode-tabs">
                  <button data-active={rightMode === "process"} onClick={() => setRightMode("process")}>?숈뒿 怨쇱젙</button>
                  <button data-active={rightMode === "chat"} onClick={() => setRightMode("chat")}>RAG 梨꾪똿</button>
                </div>
              ) : (
                <span className="toolbar-title">?대씪?곕뱶 釉뚮젅??酉곗뼱</span>
              )}
              <button className="toolbar-toggle" onClick={() => setWorkbenchInfoOpen((open) => !open)}>
                {workbenchInfoOpen ? "?뺣낫 ?묎린" : "?ㅼ젙/?곹깭"}
              </button>
              {!workbenchInfoOpen ? (
                <div className="compact-toolbar-summary">
                  <span>{workspaceMode === "daemon" ? `${daemonStateText} 쨌 worker ${learningDaemon?.worker_alive ? "alive" : "not alive"}` : compactInfoSummary}</span>
                </div>
              ) : (
                <div className="toolbar-details">
                  {workspaceMode === "lab" ? (
                  <div className="learning-volume-switcher" aria-label="?숈뒿???좏깮">
                    <span>?숈뒿??/span>
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
                        title={`${learningVolumePresets[volume].textBudget} / ${learningVolumePresets[volume].chunkBudget} 泥?겕`}
                      >
                        {learningVolumePresets[volume].label}
                      </button>
                    ))}
                    <label className="node-target-input">
                      <span>?κ린 紐⑺몴</span>
                      {learningVolume === "infinite" ? (
                        <input
                          aria-label="?κ린 紐⑺몴 ?몃뱶 ??
                          disabled={isBuilding || continuousLearningActive}
                          readOnly
                          type="text"
                          value="??
                        />
                      ) : (
                        <input
                          aria-label="?κ린 紐⑺몴 ?몃뱶 ??
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
                      <span>??寃??/span>
                    </label>
                  </div>
                  ) : null}
                  <div className="local-backend-control" data-state={localBackendStatus}>
                    <span>濡쒖뺄 FastAPI</span>
                    <input
                      aria-label="濡쒖뺄 FastAPI 二쇱냼"
                      disabled={localBackendStatus === "checking"}
                      value={localBackendUrl}
                      onChange={(event) => {
                        setLocalBackendUrl(event.currentTarget.value);
                        if (localBackendConnected) {
                          setLocalBackendStatus("idle");
                          setLocalBackendMessage("二쇱냼媛 諛붾뚯뿀?듬땲?? ?ㅼ떆 ?곌껐?섏꽭??");
                        }
                      }}
                    />
                    <button
                      disabled={localBackendStatus === "checking"}
                      onClick={() => connectLocalBackend()}
                    >
                      {localBackendStatus === "checking" ? "?뺤씤 以? : localBackendConnected ? "?ъ뿰寃? : "?곌껐"}
                    </button>
                    {localBackendConnected ? <button onClick={disconnectLocalBackend}>?댁젣</button> : null}
                    <small>{localBackendDisplay}</small>
                  </div>
                  <div className="mini-metrics">
                    <span>?먮쫫 {flowHealth}%</span>
                    <span>{edgeBrokerLabel}</span>
                    <span>GPU {gpu?.utilization ?? 0}%</span>
                    <span>RAM soft {ramSoftGb}GB</span>
                    <span>{telemetryLabel}</span>
                  </div>
                </div>
              )}
            </div>

            {workspaceMode === "daemon" ? (
              <div className="daemon-view">
                <section className="daemon-hero" data-viewer-only={daemonViewerOnly}>
                  <div>
                    <span>{daemonModeText}</span>
                    <h2>?대씪?곕뱶 釉뚮젅??怨듭쑀 ?⑦넧濡쒖?</h2>
                    <p>
                      ?μ떆媛???湲곕컲 ?숈뒿???뚮젮 怨듭슜 ?⑦넧濡쒖? ?꾨낫瑜??ㅼ슦??釉뚮젅??怨듦컙?낅땲?? 諛고룷蹂몄뿉?쒕뒗
                      援ъ“? ?곹깭留?蹂댁뿬二쇨퀬, ?ㅼ젣 ?곸떆 ?섏쭛怨?怨좎젙/媛吏移섍린??濡쒖뺄 FastAPI? ??μ냼?먯꽌 ?ㅽ뻾?⑸땲??
                    </p>
                  </div>
                  <strong>{daemonStateText}</strong>
                </section>

                {daemonViewerOnly ? (
                  <div className="viewer-notice">
                    諛고룷蹂몄? ?묒? ?대씪?곕뱶 釉뚮젅??酉곗뼱?낅땲?? ?ㅼ젣 ?κ린 ?댁쟾, 泥댄겕?ъ씤?? ?щ???蹂듦뎄??濡쒖뺄?먯꽌
                    FastAPI瑜??ㅽ뻾???????붾㈃??濡쒖뺄 ?깆쑝濡??댁뿀?????쒖꽦?붾맗?덈떎.
                  </div>
                ) : null}

                <div className="daemon-metrics">
                  <div><span>?꾩쟻 ?쒓컙</span><strong>{daemonRuntimeText}</strong></div>
                  <div><span>?쇱슫??/span><strong>{learningDaemon?.total_rounds ?? 0}</strong></div>
                  <div><span>?숈뒿 諛섏쁺</span><strong>{learningDaemon?.learned_rounds ?? 0}</strong></div>
                  <div><span>HW Tier</span><strong>{edgeTierLabel}</strong></div>
                  <div><span>Broker</span><strong>{edgeBrokerState}</strong></div>
                  <div><span>?몃뱶</span><strong>{learningDaemon?.latest_node_count ?? memoryStatus?.node_count ?? 0}</strong></div>
                  <div><span>愿怨?/span><strong>{learningDaemon?.latest_edge_count ?? memoryStatus?.edge_count ?? 0}</strong></div>
                  <div><span>?대깽??/span><strong>{learningDaemon?.latest_event_count ?? memoryStatus?.event_count ?? 0}</strong></div>
                </div>

                <div className="daemon-readonly">
                  <span>?쎄린 ?꾩슜 愿痢?/span>
                  <strong>{localBackendConnected ? "濡쒖뺄 API ?곌껐?? : "濡쒖뺄 API ?곌껐 ?湲?}</strong>
                  <p>
                    ???붾㈃? ?대씪?곕뱶 釉뚮젅???뚯빱瑜?吏곸젒 議곗옉?섏? ?딆뒿?덈떎. 濡쒖뺄 FastAPI媛 ?곌껐?섎㈃ ?뚯빱 ?곹깭,
                    泥댄겕?ъ씤?? ?먯썝 ?ㅻ깄?? 怨듭슜 ?꾨낫 洹몃옒???꾩쟻?됰쭔 諛쏆븘??蹂댁뿬以띾땲??
                  </p>
                </div>

                <section className="daemon-section">
                  <div>
                    <h3>濡쒖뺄 釉뚮젅??蹂듦뎄</h3>
                    <p>
                      ?곹깭 ?뚯씪? {learningDaemon?.reboot_resilience?.state_file ?? "data/memory/daemon_state.json"}????λ맗?덈떎.
                      留덉?留?泥댄겕?ъ씤?몃뒗 {daemonCheckpointText}?낅땲?? PC ?щ?????濡쒖뺄 FastAPI瑜??ㅼ떆 耳쒕㈃
                      ?곹깭媛 `resume_needed`濡??밸땲?? ?ш컻??濡쒖뺄 釉뚮젅???뚯빱 紐낅졊 ?먮뒗 FastAPI 愿由?API?먯꽌 ?섑뻾?섍퀬,
                      ???붾㈃? ?댁뼱吏??곹깭瑜?愿痢≫빀?덈떎.
                    </p>
                  </div>
                  <div className="daemon-lines">
                    <span>worker {learningDaemon?.worker_alive ? "alive" : "not alive"}</span>
                    <span>checkpoint {learningDaemon?.checkpoint_count ?? 0}</span>
                    <span>disk {learningDaemon?.resource_snapshot?.disk_free_gb ?? "n/a"}GB free</span>
                    <span>RAM {learningDaemon?.resource_snapshot?.ram_available_gb ?? "n/a"}GB free</span>
                  </div>
                </section>

                <section className="daemon-section">
                  <div>
                    <h3>연구 목표 프롬프트</h3>
                    <p>
                      Codex Desktop 목표 설정에 넣을 장기 연구 지시문입니다. 생성 결과가 깨지면 그대로 관찰하고,
                      자원 한계 경고가 뜨면 실패 실험으로 기록한 뒤 새로운 연구책을 찾아 반영하는 루프를 명시합니다.
                    </p>
                  </div>
                  <textarea className="goal-prompt-box" readOnly value={codexResearchGoalPrompt} />
                </section>

                <section className="daemon-section">
                  <div>
                    <h3>?ㅽ뿕???곕룞 寃쎄퀎</h3>
                    <p>
                      ?ㅽ뿕?ㅼ씠 ?밴????쒓퀎??洹쇨굅 遺議깆뿉 留됲엳硫? ?대씪?곕뱶 釉뚮젅?몄? 寃利앸맂 怨듭슜 ?몃뱶 議곌컖留?                      ?꾩떆 而⑦뀓?ㅽ듃濡?鍮뚮젮以띾땲?? 濡쒖뺄 媛쒖씤 洹몃옒?꾩뿉 ?곴뎄 怨좎젙?섎젮硫?異쒖쿂, 諛섎났 鍮덈룄, Guardrail
                      ?듦낵, ?먯썝 ?ъ쑀 議곌굔??紐⑤몢 留뚯”?댁빞 ?⑸땲??
                    </p>
                  </div>
                </section>
              </div>
            ) : rightMode === "process" ? (
              <div className="process-view process-stage-screen">
                <div className="process-stage-switcher" aria-label="?ㅽ뿕???④퀎 ?꾪솚">
                  {processSteps.map((step, index) => (
                    <button
                      aria-current={step.key === activeLabStage ? "step" : undefined}
                      data-active={step.key === activeLabStage}
                      data-state={step.state}
                      disabled={!canOpenProcessStep(step.key)}
                      key={step.key}
                      onClick={() => openProcessStep(step.key)}
                    >
                      <span>{step.number}</span>
                      <strong>{step.title}</strong>
                      <em>{step.progress}%</em>
                      {index < processSteps.length - 1 ? <i /> : null}
                    </button>
                  ))}
                </div>
                {processSteps.filter((step) => step.key === activeProcessStep.key).map((step) => (
                  <article className="process-card process-card-stage" data-state={step.state} key={step.number}>
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
                    <div className="process-progress" aria-label={`${step.title} 吏꾪뻾??${step.progress}%`}>
                      <span style={{ width: `${step.progress}%` }} />
                      <em>{step.progress}%</em>
                    </div>
                    {!step.available ? <small className="stage-gate-note">{step.blockedText}</small> : null}
                    <button
                      className="inline-action"
                      onClick={step.action}
                      disabled={step.number === "01" && continuousLearningActive ? false : !step.available || Boolean(activeAction) || isBuilding}
                    >
                      {step.actionLabel}
                    </button>
                    {step.number === "01" && buildRun ? (
                      <div className="build-run-detail">
                        <div className="build-trace">
                          {buildRun.learning_trace.map((trace) => (
                            <span key={trace.step} data-state={trace.state}>{traceStepText(trace.step)}: {statusText(trace.state)}</span>
                          ))}
                          {growthPulseCount > 0 ? (
                            <span data-state="running">?ㅼ떆媛??깆옣 +{growthPulseCount}</span>
                          ) : null}
                          {buildIsInfinite ? (
                            <span data-state={continuousLearningActive ? "running" : "complete"}>???꾩쟻 {learningElapsedText}</span>
                          ) : null}
                          {buildRun ? (
                            <span data-state="complete">湲곗〈 ?듭빱 {preservedAnchorNodeCount} ?좎?</span>
                          ) : null}
                          {representativeCapReached ? (
                            <span data-state="running">???湲곗? {visualNodeCap} 珥덇낵, ?④? ?놁쓬</span>
                          ) : null}
                          {buildIsInfinite ? (
                            <span data-state="running">???몃뱶 ?쒖떆 {visibleLiveNodeCount} / ?④? ?놁쓬</span>
                          ) : null}
                          {resourceStopReason ? (
                            <span data-state="running">?덉쟾以묒? ?湲? {resourceStopReason}</span>
                          ) : null}
                        </div>
                        <div className="learning-budget-summary">
                          <span>{buildRun.learning_profile?.label ?? currentLearningPreset.label}</span>
                          <strong>??寃??{buildRun.web_search?.provider ?? (webSearchEnabled ? "static" : "off")}</strong>
                          <strong>{buildRun.training_gate.chunk_count ?? buildRun.training_units?.length ?? currentLearningPreset.chunkBudget} 泥?겕</strong>
                          <strong>{buildRun.learning_profile?.text_budget_label ?? currentLearningPreset.textBudget}</strong>
                          {buildRun.web_search?.bing_query_url ? (
                            <small>寃??query: {buildRun.web_search.query} / Bing ?쒖떆 URL: {buildRun.web_search.bing_query_url}</small>
                          ) : null}
                          <small>
                            ????몃뱶 理쒕? {buildRun.training_gate.visual_node_budget ?? buildRun.graph_3d.nodes.length}媛?                            {buildIsInfinite ? ` / ?꾩쟻 ?쒖떆 ${accumulatedLearningNodes.toLocaleString()}媛?/ ?꾩껜 ?쒖떆` : ""}
                          </small>
                          <small>
                            ?κ린 紐⑺몴 {buildTargetNodeLabel}{buildIsInfinite ? "" : "媛?}??????숈뒿 ?덉궛?닿퀬, API graph_3d??????듭빱 {buildRun.training_gate.representative_node_count ?? buildRun.graph_3d.nodes.length}媛쒕? 蹂대깄?덈떎.
                          </small>
                          <small>
                            ?꾩옱 ?붾㈃? {displayGraph3D.nodes.length}媛??몃뱶瑜??뚮뜑留?以묒엯?덈떎. ?섏쭛 ?④퀎?먯꽌??API媛 蹂대궦 ????듭빱瑜??쒖떆?섍퀬, ?숈뒿 ?④퀎?먯꽌??洹????洹몃옒?꾩쓽 愿怨꾨? ?뺤씤?⑸땲??
                          </small>
                          <small>
                            {buildIsInfinite ? "API ????듭빱??臾댁젣???숈뒿???꾩옱 ?섑뵆?낅땲??" : `API ????듭빱留?蹂대㈃ ?κ린 紐⑺몴????${representativeTargetPercent}%?낅땲??`} ?κ린 紐⑺몴 ?꾩껜瑜??ㅼ젣 ??ν븯?ㅻ㈃ append-only ?⑦넧濡쒖? ?대깽??濡쒓렇? SQLite hot index媛 怨꾩냽 ?꾩쟻?섏뼱???⑸땲??
                          </small>
                          {buildIsInfinite ? (
                            <small>?댁쁺 寃쎄퀎: ?섏쭛 臾몄꽌? ?듭빱 洹몃옒?꾨뒗 API 寃곌낵, live-synapse???????吏???깆옣 ?대깽?몄엯?덈떎.</small>
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
                          {diskFreeGb !== null ? <span data-state={resourceStopReason?.includes("?붿뒪??) ? "running" : "complete"}>Disk free {diskFreeGb.toFixed(1)}GB</span> : null}
                        </div>
                        <div className="learning-budget-summary">
                          <span>{benchmark.profile_name ?? "Hardware Benchmark"}</span>
                          <strong>異붿쿇 {benchmarkVolumeLabel}</strong>
                          <strong>{benchmark.training_tuning?.microbatch_tokens ?? 0} tokens</strong>
                          <small>
                            CPU score {benchmarkCpuScore ?? "n/a"} / {benchmark?.can_read_local_hardware ? "?ㅼ젣 PC 湲곗??쇰줈 ?먮룞 ?곸슜?? : "諛고룷 ?붾㈃??CPU/RAM? Vercel ?뚮뱶諛뺤뒪?대ŉ ?ㅼ젣 PC媛 ?꾨떃?덈떎"}
                          </small>
                          {resourceStopReason ? <small>?덉쟾以묒?: {resourceStopReason}</small> : null}
                        </div>
                      </div>
                    ) : null}
                    {step.number === "07" && stability ? (
                      <div className="build-run-detail">
                        <div className="build-trace">
                          <span data-state="running">Backpressure: {stability.backpressure_policy?.length ?? 0} 洹쒖튃</span>
                          <span data-state="complete">Checkpoint {stability.checkpoint_policy?.training_checkpoint_interval_minutes ?? 15}遺?/span>
                          <span data-state="complete" title={stability.graph_policy?.ui_render_strategy ?? "enabled"}>Graph LOD: frontier/anchor</span>
                          <span data-state={resourceStopReason ? "running" : "complete"}>{resourceStopReason ? "Auto-stop armed" : "Auto-stop clear"}</span>
                        </div>
                        <div className="learning-budget-summary">
                          <span>{stability.profile_name ?? "Sustained Profile"}</span>
                          <strong>{learningVolume === "infinite" ? "?? : stability.target_workload?.target_nodes ?? 10000} ?몃뱶</strong>
                          <strong>{learningVolume === "infinite" ? "?? : stability.target_workload?.target_edges ?? 40000} 愿怨?/strong>
                          <small>????ъ쑀 {stability.runtime_envelope?.storage_reserve_gb ?? 200}GB ?좎?</small>
                          {diskFreeGb !== null ? <small>?꾩옱 ?붿뒪???ъ쑀 {diskFreeGb.toFixed(1)}GB / {telemetryLabel}</small> : null}
                          {resourceStopReason ? <small>?꾩옱 ?먮떒: {resourceStopReason}</small> : null}
                        </div>
                      </div>
                    ) : null}
                    {step.title.includes("?숈뒿") ? <LossChart losses={losses} /> : null}
                    <div className="process-stage-footer">
                      <button
                        disabled={!previousProcessKey}
                        onClick={() => previousProcessKey ? openProcessStep(previousProcessKey) : undefined}
                      >
                        ?댁쟾 ?④퀎
                      </button>
                      <button
                        disabled={!nextProcessKey || !canOpenProcessStep(nextProcessKey)}
                        onClick={() => nextProcessKey ? openProcessStep(nextProcessKey) : undefined}
                      >
                        {nextProcessKey ? "?ㅼ쓬 ?④퀎" : "?꾨즺"}
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <div className="chat-view">
                <button className="chat-info-toggle" onClick={() => setChatInfoOpen((open) => !open)}>
                  {chatInfoOpen ? "?곹깭 ?묎린" : `?곹깭 ?쇱튂湲?쨌 ${chatSummaryText}`}
                </button>
                {chatInfoOpen ? (
                  <div className="chat-status-row">
                    <div><span>RAG ?좊ː??/span><strong>{Math.round((graphResult?.confidence ?? graphrag?.confidence ?? 0) * 100)}%</strong></div>
                    <div><span>Local/Cloud</span><strong>{fusionDisplayText}</strong></div>
                    <div><span>洹쇨굅 臾몄꽌</span><strong>{graphResult?.evidence_docs?.length ?? 0}</strong></div>
                    <div><span>?앹꽦 諛⑹떇</span><strong>{graphResult?.answer_kind ?? graphResult?.answer_engine?.mode ?? "以鍮?}</strong></div>
                    <div><span>Guardrail</span><strong>{guardScore === null ? "?먮룞 ?湲? : `${guardScore}??/ ${guardClaimCount} 二쇱옣`}</strong></div>
                    <div><span>??寃??/span><strong>{webSearchEnabled ? graphResult?.web_search?.provider ?? "on" : "off"}</strong></div>
                  </div>
                ) : null}
                <div className="chat-scroll" ref={chatScrollRef}>
                  {chatMessages.map((message, index) => (
                    <article className="message" data-role={message.role} key={`${message.role}-${index}`}>
                      <span>{message.role === "user" ? "?ъ슜?? : "ATANOR RAG"}</span>
                      <p>{message.text}</p>
                      {message.evidence?.length ? (
                        <details className="message-evidence atanor-trace-details">
                          <summary>{language === "ko" ? "근거 / Brain path" : "Evidence / Brain path"}</summary>
                          {message.evidence.slice(0, 3).map((doc) => (
                            <div key={doc.chunk_id ?? doc.doc_id}>
                              <strong>{doc.chunk_id ?? doc.doc_id}</strong>
                              <em>
                                ?먯닔 {doc.score ?? "-"}
                                {evidenceSignalText(doc)}
                              </em>
                              <small>{doc.snippet}</small>
                            </div>
                          ))}
                        </details>
                      ) : null}
                      {message.role === "assistant" && message.diagnostics?.degeneration ? (
                        <div className="message-evidence native-diagnostics">
                          <div>
                            <strong>Native diagnostics</strong>
                            <em>
                              loop {String(message.diagnostics.degeneration.loop_detected)} / stop {message.diagnostics.native_stop_reason ?? "n/a"}
                            </em>
                            <small>
                              repeated bigram {message.diagnostics.degeneration.repeated_bigram_ratio ?? "n/a"} 쨌 unique token {message.diagnostics.degeneration.unique_token_ratio ?? "n/a"} 쨌 trace saved {String(message.diagnostics.training_feedback_recorded ?? false)}
                            </small>
                          </div>
                        </div>
                      ) : null}
                    </article>
                  ))}
                </div>
                <div className="chat-composer">
                  <textarea value={chatInput} onChange={(event) => setChatInput(event.target.value)} aria-label="RAG 吏덈Ц ?낅젰" />
                  <button disabled={isGeneratingAnswer} onClick={sendChat}>{isGeneratingAnswer ? "?앹꽦 以? : "吏덈Ц 蹂대궡湲?}</button>
                </div>
              </div>
            )}
          </div>
        </section>
      </section>

      <section className="system-log">
        <div className="log-head">
          <span>?쒖뒪??濡쒓렇</span>
          <span>{pipeline?.generated_at ? new Date(pipeline.generated_at).toLocaleString("ko-KR") : "waiting"}</span>
        </div>
        {logs.map((log, index) => (
          <p key={`${log.message}-${index}`}><span>{log.time}</span>{log.message}</p>
        ))}
      </section>
      <TauriUpdatePrompt />
    </main>
  );
  */
}

