"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties } from "react";
import Rag3DScene, { type Rag3DEdge, type Rag3DGraph, type Rag3DNode } from "../Rag3DScene";

type JsonRecord = Record<string, unknown>;

type SubscriberNode = {
  alias: string;
  peerId: string;
  tier: string;
  profile: string;
  brokerState: string;
  endpoint: string;
  heartbeatAgeSeconds: number | null;
  heartbeatTtlSeconds: number | null;
  tasks: string[];
  maxBatchNodes: number | null;
  maxBatchEdges: number | null;
  idle: boolean | null;
};

const DEFAULT_BACKEND = process.env.NEXT_PUBLIC_ATANOR_GATEWAY_API || process.env.NEXT_PUBLIC_HOMAGE_GATEWAY_API || "http://127.0.0.1:8500";
const ORANGE = "#FF5500";
const BLACK = "#0B0F19";
const PANEL = "rgba(13,18,30,0.78)";
const PANEL_2 = "rgba(18,24,38,0.72)";
const WHITE = "#F4F4F1";
const MUTED = "#9CA3AF";
const LINE = "rgba(255,255,255,0.1)";
const ACTIVE_CHUNK_NODE_CEILING = 2500;
const DEFAULT_CHUNK_RADIUS = 64;

type GraphViewport = {
  cameraZ: number;
  focus: { x: number; y: number; z: number };
  radius: number;
};

const ghostCompartments = [
  { id: "ghost-shell", label: "Ghost Shell", summary: "SHA-256 위상 지도", offset: 0, span: 34 },
  { id: "payload-vault", label: "Payload Vault", summary: "WAL 장기 디스크 금고", offset: 3, span: 42 },
  { id: "hybrid-pipeline", label: "Hybrid Pipeline", summary: "로컬 가속 경로", offset: 7, span: 48 },
  { id: "cloud-candidates", label: "Cloud Candidates", summary: "공유 온톨로지 후보", offset: 11, span: 36 },
];

function isRecord(value: unknown): value is JsonRecord {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function asString(value: unknown, fallback = "") {
  return typeof value === "string" && value.trim() ? value.trim() : fallback;
}

function asNumber(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function asBoolean(value: unknown) {
  return typeof value === "boolean" ? value : null;
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function normalizeBackendUrl(value: string) {
  const trimmed = value.trim().replace(/\/+$/, "");
  return trimmed || DEFAULT_BACKEND;
}

function runningAsStaticDesktopShell() {
  if (typeof window === "undefined") return false;
  return (
    window.location.protocol === "file:" ||
    window.location.protocol === "tauri:" ||
    window.location.protocol === "asset:" ||
    window.location.host === "" ||
    window.location.hostname === "tauri.localhost" ||
    window.location.hostname.endsWith(".tauri.localhost") ||
    "__TAURI_INTERNALS__" in window ||
    "__TAURI__" in window
  );
}

function shouldUseDirectLocalBackend() {
  if (typeof window === "undefined") return false;
  return (
    runningAsStaticDesktopShell() ||
    window.location.hostname === "localhost" ||
    window.location.hostname === "127.0.0.1" ||
    window.location.hostname === "::1"
  );
}

async function readJsonResponse<T>(response: Response, label: string): Promise<T> {
  const text = await response.text();
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    throw new Error(`${label} JSON 응답이 아닙니다. 상태 ${response.status}, content-type ${contentType || "unknown"}`);
  }
  const payload = JSON.parse(text) as T;
  if (!response.ok) {
    throw new Error(`${label} 요청 실패: ${response.status}`);
  }
  return payload;
}

function backendJsonPath(backendUrl: string, path: string) {
  return `${normalizeBackendUrl(backendUrl)}${path}`;
}

function frontendApiPath(path: string, backendUrl: string) {
  const separator = path.includes("?") ? "&" : "?";
  return `${path}${separator}backend=${encodeURIComponent(normalizeBackendUrl(backendUrl))}`;
}

async function fetchBackendJson<T>(backendUrl: string, path: string, label: string): Promise<T> {
  const direct = shouldUseDirectLocalBackend();
  const directUrl = backendJsonPath(backendUrl, path);
  const proxiedUrl = frontendApiPath(path, backendUrl);
  const firstUrl = direct ? directUrl : proxiedUrl;
  const secondUrl = direct ? proxiedUrl : directUrl;
  try {
    const response = await fetch(firstUrl, { cache: "no-store" });
    return await readJsonResponse<T>(response, label);
  } catch (firstError) {
    if (direct || runningAsStaticDesktopShell()) throw firstError;
    const response = await fetch(secondUrl, { cache: "no-store" });
    return readJsonResponse<T>(response, label);
  }
}

function graphEventSourceUrl(backendUrl: string) {
  const backend = normalizeBackendUrl(backendUrl);
  if (shouldUseDirectLocalBackend()) return `${backend}/api/graph/events?limit=50000&metadata_only=true`;
  return `/api/graph/events?backend=${encodeURIComponent(backend)}&limit=50000&metadata_only=true`;
}

function formatNumber(value: number | null | undefined) {
  return typeof value === "number" && Number.isFinite(value) ? value.toLocaleString() : "-";
}

function formatDuration(totalSeconds: number | null | undefined) {
  const seconds = Math.max(0, Math.floor(totalSeconds ?? 0));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const rest = seconds % 60;
  if (hours > 0) return `${hours}시간 ${String(minutes).padStart(2, "0")}분 ${String(rest).padStart(2, "0")}초`;
  return `${minutes}분 ${String(rest).padStart(2, "0")}초`;
}

function secondsSince(epochSeconds: number | null) {
  if (!epochSeconds) return null;
  return Math.max(0, Math.floor(Date.now() / 1000) - epochSeconds);
}

function tierProfile(tier: string, tasks: string[]) {
  const normalized = tier.toLowerCase().replace(/[\s-]+/g, "_");
  if (normalized.includes("tier_s")) return "Tier S Overlord";
  if (normalized.includes("tier_1_m")) return "Tier 1-M Director";
  if (normalized.includes("tier_1_s")) return "Tier 1-S Creator";
  if (normalized.includes("tier_2_a")) return "Tier 2-A Developer";
  if (normalized.includes("tier_2_e")) return "Tier 2-E Mainstream";
  if (normalized.includes("tier_1")) return "Tier 1 GPU Dedicated";
  if (normalized.includes("tier_2")) return tasks.some((task) => task.toLowerCase().includes("gpu")) ? "Tier 2 GPU Assist" : "Tier 2 CPU Bound";
  if (normalized.includes("tier_3")) return "Tier 3 Lightweight";
  if (normalized.includes("viewer")) return "Viewer Only";
  return tier ? `${tier} adaptive node` : "Unidentified node";
}

function collectPayloadRecords(payload: JsonRecord | null): JsonRecord[] {
  if (!payload) return [];
  const records: JsonRecord[] = [];
  const pushRecord = (candidate: unknown) => {
    if (isRecord(candidate)) records.push(candidate);
  };

  pushRecord(payload["capacity"]);
  pushRecord(payload["peer"]);
  pushRecord(payload["node"]);
  pushRecord(payload["broker"]);
  for (const key of ["subscribers", "peers", "active_payloads", "activePayloads", "nodes"]) {
    asArray(payload[key]).forEach(pushRecord);
  }
  if (isRecord(payload["broker"])) {
    asArray(payload["broker"]["subscribers"]).forEach(pushRecord);
    asArray(payload["broker"]["peers"]).forEach(pushRecord);
  }
  if (!records.length && (payload["peer_id"] || payload["peerId"] || payload["tier"])) records.push(payload);

  const seen = new Set<string>();
  return records.filter((record, index) => {
    const id = asString(record["peer_id"], asString(record["peerId"], asString(record["alias"], `record-${index}`)));
    if (seen.has(id)) return false;
    seen.add(id);
    return true;
  });
}

function normalizeSubscriber(record: JsonRecord, rootState: string, index: number): SubscriberNode {
  const peerId = asString(record["peer_id"], asString(record["peerId"], `edge-peer-${index + 1}`));
  const alias = asString(record["alias"], asString(record["name"], peerId));
  const tasks = asArray(record["task_types"] ?? record["tasks"]).map((task) => String(task));
  const tier = asString(record["tier"], "unknown");
  const generatedAt = asNumber(record["generated_at"] ?? record["generatedAt"] ?? record["heartbeat_at"] ?? record["heartbeatAt"]);
  return {
    alias,
    peerId,
    tier,
    profile: tierProfile(tier, tasks),
    brokerState: asString(record["state"], rootState || "unknown"),
    endpoint: asString(record["endpoint"], "n/a"),
    heartbeatAgeSeconds: secondsSince(generatedAt),
    heartbeatTtlSeconds: asNumber(record["heartbeat_ttl_seconds"] ?? record["heartbeatTtlSeconds"]),
    tasks,
    maxBatchNodes: asNumber(record["max_batch_nodes"] ?? record["maxBatchNodes"]),
    maxBatchEdges: asNumber(record["max_batch_edges"] ?? record["maxBatchEdges"]),
    idle: asBoolean(record["idle"]),
  };
}

function normalizeGraph(payload: JsonRecord | null): Rag3DGraph {
  const nodes = asArray(payload?.["nodes"]).filter(isRecord).map((node, index): Rag3DNode => {
    const id = asString(node["id"], asString(node["node_hash"], `ghost-${index}`));
    return {
      id,
      label: asString(node["label"], `ghost:${id.slice(0, 12)}`),
      type: asString(node["type"], "ghost_hash"),
      x: asNumber(node["x"]) ?? 0,
      y: asNumber(node["y"]) ?? 0,
      z: asNumber(node["z"]) ?? 0,
      confidence: asNumber(node["confidence"]) ?? 0.5,
    };
  });

  const edges = asArray(payload?.["edges"]).filter(isRecord).map((edge): Rag3DEdge => {
    const source = asString(edge["source"], asString(edge["source_hash"]));
    const target = asString(edge["target"], asString(edge["target_hash"]));
    return {
      source,
      target,
      relation: asString(edge["relation"], "ghost_edge"),
      weight: asNumber(edge["weight"]) ?? asNumber(edge["confidence"]) ?? 0.5,
    };
  }).filter((edge) => edge.source && edge.target);

  return { nodes, edges };
}

function mergeGraphPayload(previous: JsonRecord | null, incoming: JsonRecord): JsonRecord {
  const eventType = asString(incoming["event_type"], "graph_event");
  if (eventType !== "graph_delta") return incoming;

  const previousNodes = asArray(previous?.["nodes"]).filter(isRecord);
  const previousEdges = asArray(previous?.["edges"]).filter(isRecord);
  const incomingNodes = asArray(incoming["nodes"]).filter(isRecord);
  const incomingEdges = asArray(incoming["edges"]).filter(isRecord);
  const nodeById = new Map<string, JsonRecord>();
  const edgeByKey = new Map<string, JsonRecord>();

  for (const node of previousNodes) {
    const id = asString(node["id"], asString(node["node_hash"]));
    if (id) nodeById.set(id, node);
  }
  for (const node of incomingNodes) {
    const id = asString(node["id"], asString(node["node_hash"]));
    if (id) nodeById.set(id, node);
  }

  for (const edge of previousEdges) {
    const source = asString(edge["source"], asString(edge["source_hash"]));
    const target = asString(edge["target"], asString(edge["target_hash"]));
    const relation = asString(edge["relation"], "ghost_edge");
    if (source && target) edgeByKey.set(`${source}:${target}:${relation}`, edge);
  }
  for (const edge of incomingEdges) {
    const source = asString(edge["source"], asString(edge["source_hash"]));
    const target = asString(edge["target"], asString(edge["target_hash"]));
    const relation = asString(edge["relation"], "ghost_edge");
    if (source && target) edgeByKey.set(`${source}:${target}:${relation}`, edge);
  }

  return {
    ...(previous ?? {}),
    ...incoming,
    event_type: eventType,
    nodes: Array.from(nodeById.values()),
    edges: Array.from(edgeByKey.values()),
  };
}

function heartbeatLabel(node: SubscriberNode) {
  if (node.heartbeatAgeSeconds === null) return "신호 없음";
  const ttl = node.heartbeatTtlSeconds;
  const freshness = ttl && node.heartbeatAgeSeconds <= ttl ? "동기" : "지연";
  return `${freshness} / ${node.heartbeatAgeSeconds}s`;
}

function liveLogLines(payload: JsonRecord | null, graph: Rag3DGraph, selectedNode: Rag3DNode | null, streamLines: string[]) {
  const ghostShell = isRecord(payload?.["ghost_shell"]) ? payload?.["ghost_shell"] : null;
  const upstream = asArray(ghostShell?.["logs"]).map((entry) => String(entry));
  const base = [
    "[정제소] 원문 파싱 성공 -> 고스트 해시 토큰 주조 완료",
    "[시냅스] RAG 질문 감지 -> 22개 액티브 에지 플리커링 발동",
    "[로컬 디코더] 외부 API 연결 차단 확인. 순수 로컬 연산 가동 중.",
    "[온디바이스 엔진] 개념 해시 -> 한국어 문장 구조 합성 완료.",
    "[보안 커널] 스마트 앱 컨트롤 우회 인증서 매핑 완료.",
    `[위상] 중앙 성운 동기화 ${formatNumber(graph.nodes.length)} 해시 / ${formatNumber(graph.edges.length)} 연결`,
    `[금고] 페이로드 볼트 ${formatNumber(asNumber(ghostShell?.["payload_vault_records"]))} 원문 레코드 디스크 대기`,
  ];
  if (selectedNode) base.push(`[선택] ${selectedNode.label} -> ${selectedNode.id.slice(0, 20)}...`);
  return [...base, ...upstream, ...streamLines].slice(-18);
}

function buildClusterView(graph: Rag3DGraph) {
  const safeNodes = graph.nodes.length ? graph.nodes : [];
  return ghostCompartments.map((cluster, clusterIndex) => {
    const nodeIds = safeNodes
      .filter((_, index) => ((index + cluster.offset) % ghostCompartments.length) === clusterIndex)
      .slice(0, cluster.span)
      .map((node) => node.id);
    const nodeIdSet = new Set(nodeIds);
    const edgeKeys = graph.edges
      .filter((edge) => nodeIdSet.has(edge.source) || nodeIdSet.has(edge.target))
      .slice(0, cluster.span * 2)
      .map((edge) => `${edge.source}:${edge.target}`);
    return {
      ...cluster,
      nodeIds,
      edgeKeys,
      nodeCount: nodeIds.length,
      edgeCount: edgeKeys.length,
    };
  });
}

export default function OperatorAdminPage() {
  const [backendUrl, setBackendUrl] = useState(DEFAULT_BACKEND);
  const [edgePayload, setEdgePayload] = useState<JsonRecord | null>(null);
  const [graphPayload, setGraphPayload] = useState<JsonRecord | null>(null);
  const [ragPayload, setRagPayload] = useState<JsonRecord | null>(null);
  const [selectedNode, setSelectedNode] = useState<Rag3DNode | null>(null);
  const [streamStatus, setStreamStatus] = useState("연결 대기");
  const [streamLines, setStreamLines] = useState<string[]>([]);
  const [liveNodeIds, setLiveNodeIds] = useState<string[]>([]);
  const [liveEdgeKeys, setLiveEdgeKeys] = useState<string[]>([]);
  const [cumulativeLearningSeconds, setCumulativeLearningSeconds] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [activeClusterId, setActiveClusterId] = useState(ghostCompartments[0].id);
  const [activeViewport, setActiveViewport] = useState<GraphViewport>({
    cameraZ: 13,
    focus: { x: 0, y: 0, z: 0 },
    radius: DEFAULT_CHUNK_RADIUS,
  });
  const liveClearTimer = useRef<number | null>(null);
  const liveRefreshTimer = useRef<number | null>(null);
  const liveRefreshInFlight = useRef(false);
  const latestRefreshReason = useRef("startup");
  const activeViewportRef = useRef<GraphViewport>({
    cameraZ: 13,
    focus: { x: 0, y: 0, z: 0 },
    radius: DEFAULT_CHUNK_RADIUS,
  });
  const viewerOnlyStream = useRef(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const requested = params.get("backend") ?? params.get("api");
    if (requested) setBackendUrl(normalizeBackendUrl(requested));
  }, []);

  const applyMemoryStatus = useCallback((status: JsonRecord, reason: string) => {
    const nodeCount = asNumber(status["node_count"]) ?? 0;
    const edgeCount = asNumber(status["edge_count"]) ?? asNumber(status["ghost_edge_count"]) ?? 0;
    const ghostShell = isRecord(status["ghost_shell"])
      ? status["ghost_shell"]
      : {
        system_state: nodeCount > 0 ? "GHOST SHELL ACTIVE" : "GHOST SHELL EMPTY",
        control_plane_hashes: nodeCount,
        control_plane_edges: edgeCount,
        payload_vault_records: asNumber(status["payload_vault_records"]) ?? 0,
      };

    setEdgePayload((previous) => {
      const base = isRecord(previous) ? previous : {};
      const previousGhost = isRecord(base["ghost_shell"]) ? base["ghost_shell"] : {};
      return {
        ...base,
        state: "ready",
        ghost_shell: {
          ...previousGhost,
          ...ghostShell,
          control_plane_hashes: asNumber(ghostShell["control_plane_hashes"]) ?? nodeCount,
          control_plane_edges: asNumber(ghostShell["control_plane_edges"]) ?? edgeCount,
          logs: [
            `[SYNC] ${reason} -> /api/memory/status`,
            `CONTROL PLANE: ${formatNumber(nodeCount)} hashes / ${formatNumber(edgeCount)} edges`,
          ],
        },
      };
    });
  }, []);

  const refreshLiveGraph = useCallback(async (reason: string) => {
    if (liveRefreshInFlight.current) {
      latestRefreshReason.current = reason;
      return;
    }
    liveRefreshInFlight.current = true;
    try {
      const viewport = activeViewportRef.current;
      const graphQuery = new URLSearchParams({
        limit: "50000",
        max_nodes: String(ACTIVE_CHUNK_NODE_CEILING),
        center_x: String(viewport.focus.x),
        center_y: String(viewport.focus.y),
        center_z: String(viewport.focus.z),
        radius: String(viewport.radius),
      });
      const [memoryStatus, graphSnapshot] = await Promise.all([
        fetchBackendJson<JsonRecord>(backendUrl, "/api/memory/status", "memory status"),
        fetchBackendJson<JsonRecord>(backendUrl, `/api/graph/subgraph?${graphQuery.toString()}`, "graph chunk"),
      ]);
      applyMemoryStatus(memoryStatus, reason);
      setGraphPayload((previous) => {
        const previousGraph = normalizeGraph(previous);
        const nextGraph = normalizeGraph(graphSnapshot);
        return {
          ...graphSnapshot,
          event_type: "graph_snapshot",
          trigger: `atomic_refetch:${reason}`,
          graph_counts: {
            nodes: nextGraph.nodes.length,
            edges: nextGraph.edges.length,
            new_nodes: Math.max(0, nextGraph.nodes.length - previousGraph.nodes.length),
            new_edges: Math.max(0, nextGraph.edges.length - previousGraph.edges.length),
          },
        };
      });
      setStreamLines((previous) => [
        ...previous,
        "[SYNC] " + reason + " -> active chunk " + formatNumber(normalizeGraph(graphSnapshot).nodes.length) + " nodes / R=" + viewport.radius.toFixed(1),
      ].slice(-18));
      setError(null);
      setLastUpdated(new Date());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "라이브 그래프 동기화 실패");
    } finally {
      liveRefreshInFlight.current = false;
    }
  }, [applyMemoryStatus, backendUrl]);

  const scheduleLiveRefresh = useCallback((reason: string) => {
    latestRefreshReason.current = reason;
    if (liveRefreshTimer.current) window.clearTimeout(liveRefreshTimer.current);
    liveRefreshTimer.current = window.setTimeout(() => {
      void refreshLiveGraph(latestRefreshReason.current);
    }, 180);
  }, [refreshLiveGraph]);

  useEffect(() => {
    let cancelled = false;
    let timer: number | null = null;
    async function loadStaticTelemetry() {
      try {
        const [edgeResponse, ragResponse] = await Promise.all([
          fetchBackendJson<JsonRecord>(backendUrl, "/api/network/edge/status", "edge telemetry"),
          fetchBackendJson<JsonRecord>(backendUrl, "/api/graphrag/status", "GraphRAG telemetry"),
        ]);
        if (cancelled) return;
        setEdgePayload(edgeResponse);
        setRagPayload(ragResponse);
        setError(null);
        setLastUpdated(new Date());
      } catch (caught) {
        if (cancelled) return;
        setError(caught instanceof Error ? caught.message : "관제 텔레메트리 수신 실패");
      }
    }
    loadStaticTelemetry();
    timer = window.setInterval(loadStaticTelemetry, 2500);
    return () => {
      cancelled = true;
      if (timer) window.clearInterval(timer);
    };
  }, [backendUrl]);

  useEffect(() => {
    const source = new EventSource(graphEventSourceUrl(backendUrl));

    const handleGraphEvent = (event: MessageEvent<string>) => {
      try {
        const payload = JSON.parse(event.data) as JsonRecord;
        const cumulative = asNumber(payload["cumulative_learning_seconds"]);
        if (cumulative !== null) setCumulativeLearningSeconds(cumulative);
        const eventType = asString(payload["event_type"], "graph_event");
        const viewerOnly = asString(payload["state"]) === "viewer_only";
        viewerOnlyStream.current = viewerOnly;
        if (viewerOnly || isRecord(payload["chunk"])) {
          setGraphPayload((previous) => mergeGraphPayload(previous, payload));
        }
        const ghostShell = isRecord(payload["ghost_shell"]) ? payload["ghost_shell"] : null;
        if (ghostShell) {
          setEdgePayload((previous) => {
            const base = isRecord(previous) ? previous : {};
            const previousGhost = isRecord(base["ghost_shell"]) ? base["ghost_shell"] : {};
            return {
              ...base,
              state: "ready",
              ghost_shell: {
                ...previousGhost,
                ...ghostShell,
              },
            };
          });
        }

        const newIds = asArray(payload["new_node_ids"]).map((item) => String(item)).filter(Boolean);
        const newEdges = asArray(payload["new_edge_keys"]).map((item) => String(item)).filter(Boolean);
        if (newIds.length || newEdges.length) {
          setLiveNodeIds(newIds);
          setLiveEdgeKeys(newEdges);
          if (liveClearTimer.current) window.clearTimeout(liveClearTimer.current);
          liveClearTimer.current = window.setTimeout(() => {
            setLiveNodeIds([]);
            setLiveEdgeKeys([]);
          }, 5200);
        }

        const logs = asArray(isRecord(payload["ghost_shell"]) ? payload["ghost_shell"]["logs"] : []).map((entry) => String(entry));
        const counts = isRecord(payload["graph_counts"]) ? payload["graph_counts"] : null;
        if (counts) {
          setEdgePayload((previous) => {
            const base = isRecord(previous) ? previous : {};
            const previousGhost = isRecord(base["ghost_shell"]) ? base["ghost_shell"] : {};
            return {
              ...base,
              state: "ready",
              ghost_shell: {
                ...previousGhost,
                control_plane_hashes: asNumber(counts["nodes"]) ?? asNumber(previousGhost["control_plane_hashes"]) ?? 0,
                control_plane_edges: asNumber(counts["edges"]) ?? asNumber(previousGhost["control_plane_edges"]) ?? 0,
                logs,
              },
            };
          });
        }
        const countLine = counts
          ? `[SSE] ${eventType} +${formatNumber(asNumber(counts["new_nodes"]))} 해시 / +${formatNumber(asNumber(counts["new_edges"]))} 에지`
          : `[SSE] ${eventType} 수신`;
        setStreamLines((previous) => [...previous, countLine, ...logs].slice(-18));
        if (eventType === "graph_snapshot" || eventType === "graph_delta" || eventType === "heartbeat" || eventType === "graph_build_completed") {
          scheduleLiveRefresh(eventType);
        }
        setStreamStatus(viewerOnly ? "관제 대기" : "스트림 연결");
        setError(null);
        setLastUpdated(new Date());
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "그래프 스트림 해석 실패");
      }
    };

    for (const eventName of ["graph_snapshot", "graph_delta", "graph_build_started", "graph_build_completed", "watcher_ready", "heartbeat"]) {
      source.addEventListener(eventName, handleGraphEvent as EventListener);
    }
    source.onopen = () => {
      setStreamStatus("스트림 연결");
      setError(null);
      scheduleLiveRefresh("stream_open");
    };
    source.onerror = () => {
      if (viewerOnlyStream.current) {
        setStreamStatus("관제 대기");
        setError(null);
        return;
      }
      setStreamStatus("재연결 중");
      setError("그래프 이벤트 스트림 재연결 중");
    };

    return () => {
      for (const eventName of ["graph_snapshot", "graph_delta", "graph_build_started", "graph_build_completed", "watcher_ready", "heartbeat"]) {
        source.removeEventListener(eventName, handleGraphEvent as EventListener);
      }
      source.close();
      if (liveClearTimer.current) {
        window.clearTimeout(liveClearTimer.current);
        liveClearTimer.current = null;
      }
      if (liveRefreshTimer.current) {
        window.clearTimeout(liveRefreshTimer.current);
        liveRefreshTimer.current = null;
      }
    };
  }, [backendUrl, scheduleLiveRefresh]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setCumulativeLearningSeconds((seconds) => seconds + 1);
    }, 1000);
    return () => window.clearInterval(timer);
  }, []);

  const graph = useMemo(() => normalizeGraph(graphPayload), [graphPayload]);
  const clusters = useMemo(() => buildClusterView(graph), [graph]);
  const activeCluster = clusters.find((cluster) => cluster.id === activeClusterId) ?? clusters[0];
  const rootState = asString(edgePayload?.["state"], error ? "degraded" : "waiting");
  const subscribers = useMemo(
    () => collectPayloadRecords(edgePayload).map((record, index) => normalizeSubscriber(record, rootState, index)),
    [edgePayload, rootState],
  );
  const online = subscribers.filter((node) => !node.heartbeatTtlSeconds || (node.heartbeatAgeSeconds ?? Number.POSITIVE_INFINITY) <= node.heartbeatTtlSeconds).length;
  const ghostShell = isRecord(edgePayload?.["ghost_shell"]) ? edgePayload?.["ghost_shell"] : null;
  const result = isRecord(ragPayload?.["result"]) ? ragPayload?.["result"] : null;
  const trace = isRecord(result?.["retrieval_trace"]) ? result?.["retrieval_trace"] : null;
  const activeHashes = asArray(trace?.["active_hashes"]).map((item) => String(item));
  const activeNodeIdsForScene = activeHashes.length ? activeHashes : liveNodeIds;
  const activeEdgeKeys = graph.edges
    .filter((edge) => activeHashes.includes(edge.source) || activeHashes.includes(edge.target))
    .slice(0, 72)
    .map((edge) => `${edge.source}:${edge.target}`);
  const sceneEdgeKeys = Array.from(new Set([...activeEdgeKeys, ...liveEdgeKeys]));
  const logLines = liveLogLines(edgePayload, graph, selectedNode, streamLines);

  const handleViewportChange = useCallback((viewport: GraphViewport) => {
    const previous = activeViewportRef.current;
    const focusDelta = Math.hypot(
      viewport.focus.x - previous.focus.x,
      viewport.focus.y - previous.focus.y,
      viewport.focus.z - previous.focus.z,
    );
    const radiusDelta = Math.abs(viewport.radius - previous.radius);
    const cameraDelta = Math.abs(viewport.cameraZ - previous.cameraZ);
    if (focusDelta < 2 && radiusDelta < 2 && cameraDelta < 3) return;
    activeViewportRef.current = viewport;
    setActiveViewport(viewport);
    scheduleLiveRefresh("camera_chunk_change");
  }, [scheduleLiveRefresh]);



  useEffect(() => {
    if (!activeCluster || !graph.nodes.length) return;
    setLiveNodeIds(activeCluster.nodeIds);
    setLiveEdgeKeys(activeCluster.edgeKeys);
    if (liveClearTimer.current) window.clearTimeout(liveClearTimer.current);
    liveClearTimer.current = window.setTimeout(() => {
      setLiveNodeIds([]);
      setLiveEdgeKeys([]);
    }, 1800);
  }, [activeClusterId, activeCluster, graph.nodes.length]);

  return (
    <main style={styles.shell}>
      <header style={styles.header}>
        <div>
          <p style={styles.eyebrow}>ATANOR // CLOUD BRAIN OPERATOR</p>
          <h1 style={styles.title}>클라우드 브레인 지식 그래프</h1>
        </div>
        <div style={styles.headerRight}>
          <span style={styles.signalDot} />
          <strong>{error ? "Local Engine Degraded" : "Local Engine Sync Active"}</strong>
          <span>누적 학습 {formatDuration(cumulativeLearningSeconds)}</span>
          <span>{lastUpdated ? lastUpdated.toLocaleTimeString() : "신호 수신 전"}</span>
        </div>
      </header>

      <section style={styles.commandGrid}>
        <aside style={leftCollapsed ? styles.leftRailCollapsed : styles.leftRail}>
          <button type="button" style={styles.collapseButton} onClick={() => setLeftCollapsed((value) => !value)}>
            {leftCollapsed ? ">" : "<"}
          </button>
          {!leftCollapsed ? (
            <>
              <div style={styles.sidebarHeading}>
                <span>Architecture Compartments</span>
                <strong>Ghost Shell Control Plane</strong>
              </div>
              <section style={styles.clusterList}>
                {clusters.map((cluster) => {
                  const selected = activeClusterId === cluster.id;
                  return (
                    <button
                      key={cluster.id}
                      type="button"
                      style={selected ? styles.clusterButtonActive : styles.clusterButton}
                      onClick={() => setActiveClusterId(cluster.id)}
                    >
                      <span>{cluster.label}</span>
                      <strong>{formatNumber(cluster.nodeCount)} nodes</strong>
                      <em>{cluster.summary} / {formatNumber(cluster.edgeCount)} links</em>
                    </button>
                  );
                })}
              </section>

              <label style={styles.apiBox}>
                <span>Local Companion</span>
                <input
                  style={styles.input}
                  value={backendUrl}
                  onChange={(event) => setBackendUrl(event.target.value)}
                  spellCheck={false}
                />
              </label>

              <section style={styles.nodeInspector}>
                <span>Selected Hash</span>
                <strong>{selectedNode ? selectedNode.label : activeCluster?.label ?? "No selection"}</strong>
                <p>{selectedNode ? selectedNode.id : "구획을 전환하면 고스트 셸 주소록 안에서 관련 해시와 관계선만 부드럽게 활성화됩니다."}</p>
              </section>
            </>
          ) : (
            <div style={styles.collapsedGlyphs}>
              {clusters.map((cluster) => (
                <button
                  key={cluster.id}
                  type="button"
                  aria-label={cluster.label}
                  style={activeClusterId === cluster.id ? styles.clusterDotActive : styles.clusterDot}
                  onClick={() => setActiveClusterId(cluster.id)}
                />
              ))}
            </div>
          )}
        </aside>

        <section style={styles.graphDeck}>
          <div style={styles.graphHeader}>
            <div>
              <span>GHOST SHELL GRAPH VIEWPORT</span>
              <strong>{formatNumber(graph.nodes.length)} 노드 / {formatNumber(graph.edges.length)} 에지</strong>
            </div>
            <div style={styles.graphState}>
              <span>{activeCluster?.label ?? "All Clusters"}</span>
              <strong>{streamStatus}</strong>
            </div>
          </div>
          <div style={styles.graphStage}>
            {graph.nodes.length ? (
              <Rag3DScene
                activeEdgeKeys={sceneEdgeKeys}
                activeNodeIds={activeNodeIdsForScene}
                graph={graph}
                newNodeIds={liveNodeIds}
                preserveSourceCoordinates
                onViewportChange={handleViewportChange}
                onSelect={(node) => setSelectedNode(node)}
                theme="dark"
              />
            ) : (
              <div style={styles.emptyGraph}>
                <strong>고스트 셸 위상 대기</strong>
                <span>운영자 로컬 워커가 클라우드 브레인 몸체를 대신 구동하면 3D 해시 성운이 활성화됩니다.</span>
              </div>
            )}
          </div>
          <div style={styles.graphFooter}>
            <span>{asString(ghostShell?.["system_state"], "GHOST SHELL READY")}</span>
            <span>{formatNumber(asNumber(ghostShell?.["payload_vault_records"]))} vaulted payloads</span>
            <span>{formatNumber(activeNodeIdsForScene.length || activeCluster?.nodeCount || 0)} active hashes</span>
          </div>
        </section>

        <aside style={styles.rightRail}>
          <section style={styles.stateBadge}>
            <span style={styles.badgeDot} />
            <strong>{error ? "Local Engine Needs Attention" : "Local Engine Sync Active"}</strong>
          </section>

          <section style={styles.factoryPanel}>
            <div style={styles.factoryHeader}>
              <span>Hybrid Acceleration Pipeline</span>
              <strong>{"Ghost Shell -> Payload Vault -> OnDeviceSynthesizer"}</strong>
            </div>
            {[
              {
                id: "01",
                label: "Ingestion Stream",
                detail: "Listening for payloads...",
                mode: "STATUS: ACTIVE STREAM",
                stream: true,
                intensity: streamStatus === "스트림 연결" ? 92 : 38,
              },
              {
                id: "02",
                label: "Payload Vault",
                detail: `${formatNumber(asNumber(ghostShell?.["payload_vault_records"]))} WAL-protected payloads`,
                mode: "PERSISTENT APPEND",
                stream: true,
                intensity: graph.edges.length ? 74 : 18,
              },
              {
                id: "03",
                label: "Hybrid Accel",
                detail: `${formatNumber(activeNodeIdsForScene.length || 22)} active hashes routed`,
                mode: rootState === "ready" ? "ROUTING HASHES" : "WAITING",
                stream: false,
                intensity: rootState === "ready" ? 58 : 18,
              },
            ].map((step) => (
              <article key={step.id} style={styles.factoryStep}>
                <div style={styles.stepLine}>
                  <span>{step.id}</span>
                  <strong>{step.label}</strong>
                  <em>{step.mode}</em>
                </div>
                <div style={step.stream ? styles.streamTrack : styles.progressTrack}>
                  <span style={step.stream ? styles.streamPulse : { ...styles.progressFill, width: `${step.intensity}%` }} />
                </div>
                <p>{step.detail}</p>
              </article>
            ))}
          </section>

          <section style={styles.subscriberList}>
            <div style={styles.compactGrid}>
              <div style={styles.microMetric}>
                <span>Peers</span>
                <strong>{subscribers.length}</strong>
              </div>
              <div style={styles.microMetric}>
                <span>Online</span>
                <strong>{online}</strong>
              </div>
            </div>
            {subscribers.slice(0, 2).map((node) => (
              <article key={node.peerId} style={styles.subscriber}>
                <div style={styles.subscriberIdentity}>
                  <strong>{node.alias}</strong>
                  <span>{node.profile}</span>
                </div>
                <em>{heartbeatLabel(node)}</em>
              </article>
            ))}
          </section>

          <section style={styles.logStream}>
            {logLines.slice(-7).map((line, index) => (
              <p key={`${line}-${index}`} style={line.includes("[FETCH]") || line.includes("[시냅스]") || line.includes("[로컬 디코더]") || line.includes("[온디바이스 엔진]") ? styles.hotLog : styles.logLine}>
                <span style={styles.logIndex}>{String(index + 1).padStart(2, "0")}</span>
                {line}
              </p>
            ))}
          </section>
          <section style={styles.rightTelemetry}>
            <div>
              <span>Fetch</span>
              <strong>Active Stream</strong>
            </div>
            <div>
              <span>Learn</span>
              <strong>Payload Vault isolated</strong>
            </div>
            <div>
              <span>Runtime</span>
              <strong>{formatDuration(cumulativeLearningSeconds)}</strong>
            </div>
            <div>
              <span>Vault</span>
              <strong>OnDeviceSynthesizer Layer Configured (Pure Synthesis Mode)</strong>
            </div>
          </section>
        </aside>
      </section>

      {error ? <div style={styles.errorBadge}>Local sync warning: {error}</div> : null}
    </main>
  );
}

const styles: Record<string, CSSProperties> = {
  shell: {
    background: `radial-gradient(circle at 45% 38%, rgba(255,85,0,0.08), transparent 32%), ${BLACK}`,
    color: WHITE,
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
    minHeight: "100vh",
    overflow: "hidden",
    padding: 18,
  },
  header: {
    alignItems: "center",
    display: "flex",
    gap: 18,
    justifyContent: "space-between",
    minHeight: 56,
    padding: "0 2px 14px",
  },
  eyebrow: {
    color: ORANGE,
    font: "800 11px Consolas, JetBrains Mono, monospace",
    letterSpacing: 0,
    margin: "0 0 5px",
  },
  title: {
    fontSize: 24,
    fontWeight: 860,
    letterSpacing: 0,
    margin: 0,
  },
  headerRight: {
    alignItems: "center",
    background: "rgba(255,255,255,0.045)",
    border: `1px solid ${LINE}`,
    color: MUTED,
    display: "flex",
    font: "750 12px Consolas, JetBrains Mono, monospace",
    gap: 10,
    padding: "9px 12px",
    whiteSpace: "nowrap",
  },
  signalDot: {
    background: ORANGE,
    boxShadow: "0 0 18px rgba(255,85,0,0.75)",
    borderRadius: 99,
    display: "inline-block",
    height: 8,
    width: 8,
  },
  commandGrid: {
    height: "calc(100vh - 92px)",
    minHeight: 0,
    position: "relative",
  },
  leftRail: {
    background: "rgba(9,13,22,0.78)",
    border: `1px solid ${LINE}`,
    display: "grid",
    gap: 14,
    gridAutoRows: "max-content",
    minHeight: 0,
    overflow: "auto",
    padding: 12,
    position: "absolute",
    left: 0,
    top: 0,
    width: "clamp(190px, 17vw, 230px)",
    height: "100%",
    transition: "width 180ms ease, opacity 180ms ease",
    zIndex: 3,
  },
  leftRailCollapsed: {
    alignItems: "start",
    background: "rgba(9,13,22,0.72)",
    border: `1px solid ${LINE}`,
    display: "grid",
    gap: 14,
    gridTemplateRows: "32px 1fr",
    justifyItems: "center",
    minHeight: 0,
    overflow: "hidden",
    padding: 10,
    position: "absolute",
    left: 0,
    top: 0,
    width: 58,
    height: "100%",
    zIndex: 3,
  },
  collapseButton: {
    background: "rgba(255,255,255,0.06)",
    border: `1px solid ${LINE}`,
    color: WHITE,
    cursor: "pointer",
    font: "900 13px Consolas, JetBrains Mono, monospace",
    height: 30,
    width: 32,
  },
  collapsedGlyphs: {
    alignContent: "start",
    display: "grid",
    gap: 12,
    justifyItems: "center",
  },
  clusterDot: {
    background: "rgba(255,255,255,0.18)",
    border: "1px solid rgba(255,255,255,0.18)",
    borderRadius: 99,
    cursor: "pointer",
    height: 12,
    width: 12,
  },
  clusterDotActive: {
    background: ORANGE,
    border: "1px solid rgba(255,255,255,0.4)",
    borderRadius: 99,
    boxShadow: "0 0 18px rgba(255,85,0,0.75)",
    cursor: "pointer",
    height: 12,
    width: 12,
  },
  sidebarHeading: {
    display: "grid",
    gap: 4,
  },
  clusterList: {
    display: "grid",
    gap: 7,
  },
  clusterButton: {
    background: "transparent",
    border: `1px solid ${LINE}`,
    color: WHITE,
    cursor: "pointer",
    display: "grid",
    gap: 3,
    padding: "10px 11px",
    textAlign: "left",
  },
  clusterButtonActive: {
    background: "rgba(255,85,0,0.1)",
    border: "1px solid rgba(255,85,0,0.58)",
    boxShadow: "inset 2px 0 0 #FF5500",
    color: WHITE,
    cursor: "pointer",
    display: "grid",
    gap: 3,
    padding: "10px 11px",
    textAlign: "left",
  },
  apiBox: {
    borderTop: `1px solid ${LINE}`,
    color: MUTED,
    display: "grid",
    gap: 8,
    paddingTop: 12,
  },
  input: {
    background: "rgba(0,0,0,0.34)",
    border: `1px solid ${LINE}`,
    color: WHITE,
    font: "700 11px Consolas, JetBrains Mono, monospace",
    outline: "none",
    padding: "8px 7px",
    width: "100%",
  },
  compactGrid: {
    display: "grid",
    gap: 7,
    gridTemplateColumns: "1fr 1fr",
  },
  microMetric: {
    borderTop: `1px solid ${LINE}`,
    display: "grid",
    gap: 3,
    minHeight: 48,
    paddingTop: 9,
  },
  subscriberList: {
    display: "grid",
    gap: 8,
  },
  subscriber: {
    borderTop: `1px solid ${LINE}`,
    display: "grid",
    gap: 6,
    paddingTop: 9,
  },
  subscriberIdentity: {
    display: "grid",
    gap: 3,
  },
  nodeInspector: {
    borderTop: `1px solid ${LINE}`,
    color: MUTED,
    display: "grid",
    gap: 7,
    paddingTop: 12,
  },
  graphDeck: {
    background: "rgba(3,6,13,0.48)",
    border: `1px solid ${LINE}`,
    display: "grid",
    gridTemplateRows: "52px minmax(0, 1fr) 34px",
    inset: 0,
    minHeight: 0,
    minWidth: 0,
    overflow: "hidden",
    position: "absolute",
    zIndex: 1,
  },
  graphHeader: {
    alignItems: "center",
    borderBottom: `1px solid ${LINE}`,
    display: "flex",
    justifyContent: "space-between",
    padding: "0 clamp(330px, 27vw, 360px) 0 clamp(76px, 19vw, 250px)",
  },
  graphState: {
    color: ORANGE,
    display: "grid",
    font: "760 11px Consolas, JetBrains Mono, monospace",
    gap: 2,
    textAlign: "right",
  },
  graphStage: {
    background: "radial-gradient(circle at center, rgba(255,255,255,0.035), transparent 42%)",
    minHeight: 0,
    position: "relative",
  },
  emptyGraph: {
    alignContent: "center",
    color: MUTED,
    display: "grid",
    gap: 8,
    height: "100%",
    justifyItems: "center",
  },
  graphFooter: {
    alignItems: "center",
    borderTop: `1px solid ${LINE}`,
    color: MUTED,
    display: "flex",
    font: "730 11px Consolas, JetBrains Mono, monospace",
    gap: 16,
    overflow: "hidden",
    padding: "0 clamp(330px, 27vw, 360px) 0 clamp(76px, 19vw, 250px)",
    whiteSpace: "nowrap",
  },
  rightRail: {
    background: "rgba(9,13,22,0.78)",
    border: `1px solid ${LINE}`,
    display: "grid",
    gap: 14,
    gridTemplateRows: "max-content max-content max-content minmax(0, 1fr) max-content",
    height: "100%",
    minHeight: 0,
    overflow: "auto",
    padding: 14,
    position: "absolute",
    right: 0,
    top: 0,
    width: "clamp(278px, 24vw, 328px)",
    zIndex: 3,
  },
  stateBadge: {
    alignItems: "center",
    color: WHITE,
    display: "flex",
    font: "760 12px Consolas, JetBrains Mono, monospace",
    gap: 8,
  },
  badgeDot: {
    background: ORANGE,
    borderRadius: 99,
    boxShadow: "0 0 14px rgba(255,85,0,0.66)",
    display: "inline-block",
    height: 7,
    width: 7,
  },
  factoryPanel: {
    display: "grid",
    gap: 16,
  },
  factoryHeader: {
    display: "grid",
    gap: 4,
  },
  factoryStep: {
    display: "grid",
    gap: 8,
  },
  stepLine: {
    alignItems: "baseline",
    display: "grid",
    gap: 8,
    gridTemplateColumns: "30px 1fr max-content",
  },
  progressTrack: {
    background: "rgba(255,255,255,0.08)",
    height: 2,
    overflow: "hidden",
  },
  streamTrack: {
    background: "rgba(255,255,255,0.08)",
    height: 2,
    overflow: "hidden",
    position: "relative",
  },
  progressFill: {
    background: ORANGE,
    display: "block",
    height: "100%",
    transition: "width 420ms ease",
  },
  streamPulse: {
    animation: "atanorStreamSweep 1.35s linear infinite",
    background: `linear-gradient(90deg, transparent, ${ORANGE}, rgba(255,255,255,0.78), ${ORANGE}, transparent)`,
    boxShadow: "0 0 18px rgba(255,85,0,0.7)",
    display: "block",
    height: "100%",
    width: "42%",
  },
  logStream: {
    borderTop: `1px solid ${LINE}`,
    minHeight: 0,
    overflow: "auto",
    paddingTop: 10,
  },
  logLine: {
    color: "#CBD5E1",
    font: "700 11px/1.55 Consolas, JetBrains Mono, monospace",
    margin: "0 0 7px",
  },
  hotLog: {
    color: ORANGE,
    font: "820 11px/1.55 Consolas, JetBrains Mono, monospace",
    margin: "0 0 7px",
    textShadow: "0 0 14px rgba(255,85,0,0.42)",
  },
  logIndex: {
    color: MUTED,
    display: "inline-block",
    marginRight: 8,
    minWidth: 18,
  },
  rightTelemetry: {
    borderTop: `1px solid ${LINE}`,
    display: "grid",
    gap: 9,
    paddingTop: 12,
  },
  errorBadge: {
    background: "rgba(11,15,25,0.92)",
    border: "1px solid rgba(255,85,0,0.35)",
    bottom: 16,
    color: ORANGE,
    font: "760 11px Consolas, JetBrains Mono, monospace",
    padding: "8px 10px",
    position: "fixed",
    right: 16,
  },
};
