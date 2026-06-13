"use client";

import { useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";

type EdgePayload = Record<string, unknown>;

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

const DEFAULT_BACKEND = "http://127.0.0.1:8500";
const ORANGE = "#ff6b35";
const BLACK = "#050605";
const PANEL = "#101310";
const LINE = "rgba(255,255,255,0.12)";
const MUTED = "#8f9892";

function isRecord(value: unknown): value is EdgePayload {
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

function tierProfile(tier: string, tasks: string[]) {
  const normalized = tier.toLowerCase().replace(/[\s-]+/g, "_");
  if (normalized.includes("tier_1")) return "Tier 1 GPU Dedicated";
  if (normalized.includes("tier_2")) return tasks.some((task) => task.toLowerCase().includes("gpu")) ? "Tier 2 GPU Assist" : "Tier 2 CPU Bound";
  if (normalized.includes("tier_3")) return "Tier 3 Minimal / Cloud Assist";
  if (normalized.includes("viewer")) return "Viewer Only";
  return tier ? `${tier} Adaptive` : "Unknown Capacity";
}

function secondsSince(epochSeconds: number | null) {
  if (!epochSeconds) return null;
  return Math.max(0, Math.floor(Date.now() / 1000) - epochSeconds);
}

function collectPayloadRecords(payload: EdgePayload | null): EdgePayload[] {
  if (!payload) return [];
  const records: EdgePayload[] = [];
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

function normalizeSubscriber(record: EdgePayload, rootState: string, index: number): SubscriberNode {
  const peerId = asString(record["peer_id"], asString(record["peerId"], `edge-peer-${index + 1}`));
  const alias = asString(record["alias"], asString(record["name"], peerId));
  const tasks = asArray(record["task_types"] ?? record["tasks"]).map((task) => String(task));
  const tier = asString(record["tier"], "unknown");
  const generatedAt = asNumber(record["generated_at"] ?? record["generatedAt"] ?? record["heartbeat_at"] ?? record["heartbeatAt"]);
  const heartbeatTtlSeconds = asNumber(record["heartbeat_ttl_seconds"] ?? record["heartbeatTtlSeconds"]);
  return {
    alias,
    peerId,
    tier,
    profile: tierProfile(tier, tasks),
    brokerState: asString(record["state"], rootState || "unknown"),
    endpoint: asString(record["endpoint"], "n/a"),
    heartbeatAgeSeconds: secondsSince(generatedAt),
    heartbeatTtlSeconds,
    tasks,
    maxBatchNodes: asNumber(record["max_batch_nodes"] ?? record["maxBatchNodes"]),
    maxBatchEdges: asNumber(record["max_batch_edges"] ?? record["maxBatchEdges"]),
    idle: asBoolean(record["idle"]),
  };
}

function heartbeatLabel(node: SubscriberNode) {
  if (node.heartbeatAgeSeconds === null) return "no heartbeat";
  const ttl = node.heartbeatTtlSeconds;
  const freshness = ttl && node.heartbeatAgeSeconds <= ttl ? "sync" : "stale";
  return `${freshness} · ${node.heartbeatAgeSeconds}s`;
}

function formatLimit(value: number | null) {
  return value === null ? "-" : value.toLocaleString();
}

export default function OperatorAdminPage() {
  const [backendUrl, setBackendUrl] = useState(DEFAULT_BACKEND);
  const [payload, setPayload] = useState<EdgePayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const requested = params.get("backend") ?? params.get("api");
    if (requested) setBackendUrl(normalizeBackendUrl(requested));
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function loadEdgeStatus() {
      const endpoint = `/api/network/edge/status?backend=${encodeURIComponent(normalizeBackendUrl(backendUrl))}`;
      try {
        const response = await fetch(endpoint, { cache: "no-store" });
        const nextPayload = (await response.json()) as EdgePayload;
        if (cancelled) return;
        setPayload(nextPayload);
        setError(response.ok ? null : `HTTP ${response.status}`);
        setLastUpdated(new Date());
      } catch (caught) {
        if (cancelled) return;
        setError(caught instanceof Error ? caught.message : "edge status unavailable");
      }
    }
    loadEdgeStatus();
    const timer = window.setInterval(loadEdgeStatus, 3000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [backendUrl]);

  const subscribers = useMemo(
    () => collectPayloadRecords(payload).map((record, index) => normalizeSubscriber(record, asString(payload?.["state"], "unknown"), index)),
    [payload],
  );
  const online = subscribers.filter((node) => !node.heartbeatTtlSeconds || (node.heartbeatAgeSeconds ?? Number.POSITIVE_INFINITY) <= node.heartbeatTtlSeconds).length;
  const rootState = asString(payload?.["state"], error ? "degraded" : "waiting");

  return (
    <main style={styles.shell}>
      <section style={styles.header}>
        <div>
          <p style={styles.eyebrow}>HOMAGE OPERATOR CENTER</p>
          <h1 style={styles.title}>Edge Subscriber Telemetry</h1>
        </div>
        <div style={styles.statusCluster}>
          <span style={styles.statusPill} data-state={rootState}>{rootState}</span>
          <span style={styles.clock}>{lastUpdated ? lastUpdated.toLocaleTimeString() : "awaiting sync"}</span>
        </div>
      </section>

      <section style={styles.controlLine}>
        <label style={styles.inputLabel}>
          LOCAL API
          <input
            style={styles.input}
            value={backendUrl}
            onChange={(event) => setBackendUrl(event.target.value)}
            spellCheck={false}
          />
        </label>
        <div style={styles.metric}>
          <span>Subscribers</span>
          <strong>{subscribers.length}</strong>
        </div>
        <div style={styles.metric}>
          <span>Online</span>
          <strong>{online}</strong>
        </div>
        <div style={styles.metric}>
          <span>Broker</span>
          <strong>{asString(payload?.["architecture"], "edge_compute_broker")}</strong>
        </div>
      </section>

      {error ? <p style={styles.error}>EDGE STATUS DEGRADED · {error}</p> : null}

      <section style={styles.grid}>
        {subscribers.length ? (
          subscribers.map((node) => (
            <article key={node.peerId} style={styles.card}>
              <div style={styles.cardHead}>
                <div>
                  <strong style={styles.alias}>{node.alias}</strong>
                  <span style={styles.peer}>{node.peerId}</span>
                </div>
                <span style={styles.tier}>{node.profile}</span>
              </div>
              <dl style={styles.specs}>
                <div>
                  <dt>Heartbeat</dt>
                  <dd style={node.heartbeatTtlSeconds && (node.heartbeatAgeSeconds ?? 999999) > node.heartbeatTtlSeconds ? styles.stale : styles.live}>
                    {heartbeatLabel(node)}
                  </dd>
                </div>
                <div>
                  <dt>Broker</dt>
                  <dd>{node.brokerState}{node.idle === null ? "" : node.idle ? " · idle" : " · active"}</dd>
                </div>
                <div>
                  <dt>Batch</dt>
                  <dd>{formatLimit(node.maxBatchNodes)} nodes / {formatLimit(node.maxBatchEdges)} edges</dd>
                </div>
                <div>
                  <dt>Endpoint</dt>
                  <dd>{node.endpoint}</dd>
                </div>
              </dl>
              <div style={styles.tasks}>
                {(node.tasks.length ? node.tasks : ["status_view"]).map((task) => <span key={task}>{task}</span>)}
              </div>
            </article>
          ))
        ) : (
          <article style={styles.empty}>
            <strong>No subscriber payloads</strong>
            <span>Waiting for /api/network/edge/status heartbeat.</span>
          </article>
        )}
      </section>
    </main>
  );
}

const styles: Record<string, CSSProperties> = {
  shell: {
    minHeight: "100vh",
    background: BLACK,
    color: "#f5f6f4",
    padding: 24,
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
  },
  header: {
    alignItems: "center",
    borderBottom: `1px solid ${LINE}`,
    display: "flex",
    justifyContent: "space-between",
    gap: 16,
    paddingBottom: 18,
  },
  eyebrow: {
    color: ORANGE,
    fontSize: 11,
    fontWeight: 900,
    letterSpacing: 0,
    margin: "0 0 6px",
  },
  title: {
    fontSize: 24,
    letterSpacing: 0,
    margin: 0,
  },
  statusCluster: {
    alignItems: "center",
    display: "flex",
    gap: 10,
  },
  statusPill: {
    border: `1px solid ${ORANGE}`,
    borderRadius: 6,
    color: ORANGE,
    fontSize: 12,
    fontWeight: 900,
    padding: "7px 10px",
    textTransform: "uppercase",
  },
  clock: {
    color: MUTED,
    fontFamily: "Consolas, JetBrains Mono, monospace",
    fontSize: 12,
  },
  controlLine: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
    gap: 10,
    marginTop: 16,
  },
  inputLabel: {
    border: `1px solid ${LINE}`,
    borderRadius: 8,
    color: MUTED,
    display: "grid",
    fontSize: 11,
    fontWeight: 900,
    gap: 7,
    padding: 10,
  },
  input: {
    background: "#090b09",
    border: `1px solid ${LINE}`,
    borderRadius: 6,
    color: "#f5f6f4",
    font: "800 13px Consolas, JetBrains Mono, monospace",
    outline: "none",
    padding: "8px 9px",
  },
  metric: {
    alignContent: "center",
    background: PANEL,
    border: `1px solid ${LINE}`,
    borderRadius: 8,
    display: "grid",
    gap: 4,
    minWidth: 130,
    padding: "10px 12px",
  },
  error: {
    border: "1px solid rgba(255,107,53,0.42)",
    borderRadius: 8,
    color: ORANGE,
    fontWeight: 900,
    margin: "12px 0 0",
    padding: 10,
  },
  grid: {
    display: "grid",
    gap: 10,
    marginTop: 16,
  },
  card: {
    background: PANEL,
    border: `1px solid ${LINE}`,
    borderRadius: 8,
    padding: 14,
  },
  cardHead: {
    alignItems: "flex-start",
    display: "flex",
    flexWrap: "wrap",
    justifyContent: "space-between",
    gap: 14,
  },
  alias: {
    display: "block",
    fontSize: 17,
  },
  peer: {
    color: MUTED,
    display: "block",
    fontFamily: "Consolas, JetBrains Mono, monospace",
    fontSize: 12,
    marginTop: 4,
  },
  tier: {
    border: "1px solid rgba(255,107,53,0.5)",
    borderRadius: 6,
    color: ORANGE,
    fontSize: 12,
    fontWeight: 900,
    padding: "6px 8px",
    whiteSpace: "nowrap",
  },
  specs: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(135px, 1fr))",
    gap: 8,
    margin: "14px 0 0",
  },
  live: {
    color: "#f5f6f4",
  },
  stale: {
    color: ORANGE,
  },
  tasks: {
    display: "flex",
    flexWrap: "wrap",
    gap: 6,
    marginTop: 12,
  },
  empty: {
    border: `1px dashed ${LINE}`,
    borderRadius: 8,
    color: MUTED,
    display: "grid",
    gap: 5,
    padding: 18,
  },
};
