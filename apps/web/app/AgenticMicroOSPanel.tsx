"use client";

import { useEffect, useMemo, useState } from "react";

type Language = "en" | "ko";
type AnyRecord = Record<string, any>;
type SmokeKey = "dashboard" | "browser" | "mcp" | "splatra" | "openWeb";
type ReviewDecision = "approved" | "rejected" | "deferred" | "needs_more_evidence";

type Props = {
  language: Language;
  localBackendUrl: string;
};

const moduleLabels = [
  ["capability_kernel", "Capability Kernel"],
  ["virtual_fs", "Virtual FS"],
  ["brain_access_road", "Brain Access Road"],
  ["splatra_cosmos_cell", "SPLATRA Cosmos Cell"],
  ["dashboard_action_bus", "Dashboard Action Bus"],
  ["tool_gateway", "Tool Gateway"],
  ["browser_read", "Browser Read"],
  ["mcp_allowlist_gateway", "MCP Allowlist"],
  ["splatra_evaluator", "SPLATRA Evaluator"],
  ["web_explorer_loop", "Open-Web Explorer"],
  ["hermes_intake", "Hermes Intake"],
] as const;

const autonomyTiers = ["OBSERVE_ONLY", "DRAFT_PROPOSAL", "SIGNED_DELEGATION"] as const;
const autonomySwitches = [
  "shell",
  "full_file_read",
  "full_file_write",
  "git_commit",
  "git_push",
  "local_brain_write",
  "cloud_production_write",
  "external_network",
  "browser_control",
  "mcp_tools",
  "code_execution",
] as const;
const hostSafeTestToken = "SIGNED_SAFE_TEST";

function joinApiUrl(baseUrl: string, path: string) {
  return `${baseUrl.replace(/\/$/, "")}${path}`;
}

async function jsonFetch(baseUrl: string, path: string, init?: RequestInit): Promise<AnyRecord> {
  const sameOriginTargets = path.startsWith("/api/agentic-os") ? [""] : [];
  const backendTargets = baseUrl.includes("127.0.0.1:8500") || baseUrl.includes("localhost:8500")
    ? [baseUrl, "http://127.0.0.1:8502"]
    : [baseUrl];
  const targets = [...sameOriginTargets, ...backendTargets];
  let lastError: unknown = null;
  for (const target of targets) {
    try {
      const response = await fetch(target ? joinApiUrl(target, path) : path, { ...init, cache: "no-store" });
      if (!response.ok) {
        lastError = new Error(`HTTP ${response.status}`);
        continue;
      }
      return response.json();
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError;
}

function ResultLine({ result }: { result: AnyRecord | null }) {
  if (!result) return <p>idle</p>;
  const accepted = result.allowed === true || result.status === "read_public_snapshot" || result.status === "evaluated" || Boolean(result.run_id);
  const reason = result.reason || result.denied_reason || result.decision || result.report_reason || result.status || result.stopped_reason;
  return <p>{accepted ? "accepted" : "rejected"}{reason ? ` - ${reason}` : ""}</p>;
}

function MetricStrip({ result }: { result: AnyRecord | null }) {
  if (!result?.run_id) return null;
  return (
    <div className="agentic-os-flags">
      <span>read={String(result.pages_read ?? 0)}</span>
      <span>rejected={String(result.pages_rejected ?? 0)}</span>
      <span>drafts={String(result.candidate_drafts_count ?? 0)}</span>
      <span>skills={String(result.skill_drafts_count ?? 0)}</span>
      <span>report={String(result.report_triggered ?? false)}</span>
    </div>
  );
}

export default function AgenticMicroOSPanel({ language, localBackendUrl }: Props) {
  const [status, setStatus] = useState<AnyRecord | null>(null);
  const [permissionStatus, setPermissionStatus] = useState<AnyRecord | null>(null);
  const [reviewStatus, setReviewStatus] = useState<AnyRecord | null>(null);
  const [reviewItems, setReviewItems] = useState<AnyRecord[]>([]);
  const [typedPhrase, setTypedPhrase] = useState("");
  const [durationSec, setDurationSec] = useState("600");
  const [subSwitches, setSubSwitches] = useState<Record<string, boolean>>({});
  const [permissionResult, setPermissionResult] = useState<AnyRecord | null>(null);
  const [hostExecutorStatus, setHostExecutorStatus] = useState<AnyRecord | null>(null);
  const [hostExecutorResult, setHostExecutorResult] = useState<AnyRecord | null>(null);
  const [results, setResults] = useState<Record<SmokeKey, AnyRecord | null>>({
    dashboard: null,
    browser: null,
    mcp: null,
    splatra: null,
    openWeb: null,
  });

  useEffect(() => {
    jsonFetch(localBackendUrl, "/api/agentic-os/status").then(setStatus).catch(() => setStatus({ error: "local_backend_unavailable" }));
    refreshPermissionGate().catch(() => undefined);
    refreshHostExecutor().catch(() => undefined);
    refreshReviewQueue().catch(() => undefined);
  }, [localBackendUrl]);

  const blockedActions = useMemo(() => {
    const list = Array.isArray(status?.blocked_actions) ? status?.blocked_actions : [];
    return list.length ? list : ["unrestricted_shell", "arbitrary_js_eval", "local_brain_direct_write", "production_store_direct_write", "auto_commit", "auto_push"];
  }, [status]);

  async function runSmoke(key: SmokeKey, path: string, body: AnyRecord) {
    const result = await jsonFetch(localBackendUrl, path, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    }).catch((error) => ({ allowed: false, reason: String(error) }));
    setResults((current) => ({ ...current, [key]: result }));
  }

  async function refreshReviewQueue() {
    const payload = await jsonFetch(localBackendUrl, "/api/agentic-os/review/items").catch((error) => ({ error: String(error), items: [] }));
    setReviewStatus(payload);
    setReviewItems(Array.isArray(payload.items) ? payload.items : []);
  }

  async function refreshPermissionGate() {
    const payload = await jsonFetch(localBackendUrl, "/api/agentic-os/permission/tier").catch((error) => ({ error: String(error) }));
    setPermissionStatus(payload);
    return payload;
  }

  async function setPermissionTier(tier: string) {
    const payload = await jsonFetch(localBackendUrl, "/api/agentic-os/permission/tier/set", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ tier, operator_id: "lab_operator" }),
    }).catch((error) => ({ allowed: false, reason: String(error) }));
    setPermissionResult(payload);
    await refreshPermissionGate().catch(() => undefined);
  }

  async function enableFullHost() {
    const payload = await jsonFetch(localBackendUrl, "/api/agentic-os/permission/full-host/enable", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        enabled_by: "lab_operator",
        typed_phrase: typedPhrase,
        duration_sec: Number(durationSec) || 0,
        sub_switches: subSwitches,
      }),
    }).catch((error) => ({ allowed: false, reason: String(error) }));
    setPermissionResult(payload);
    await refreshPermissionGate().catch(() => undefined);
  }

  async function disableFullHost() {
    const payload = await jsonFetch(localBackendUrl, "/api/agentic-os/permission/full-host/disable", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ operator_id: "lab_operator", reason: "lab operator disabled" }),
    }).catch((error) => ({ allowed: false, reason: String(error) }));
    setPermissionResult(payload);
    await refreshPermissionGate().catch(() => undefined);
  }

  async function triggerEmergencyStop() {
    const payload = await jsonFetch(localBackendUrl, "/api/agentic-os/permission/full-host/emergency-stop", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ operator_id: "lab_operator", reason: "lab emergency stop" }),
    }).catch((error) => ({ allowed: false, reason: String(error) }));
    setPermissionResult(payload);
    await refreshPermissionGate().catch(() => undefined);
    await refreshHostExecutor().catch(() => undefined);
  }

  async function refreshHostExecutor() {
    const payload = await jsonFetch(localBackendUrl, "/api/agentic-os/host-executor/status").catch((error) => ({ error: String(error) }));
    setHostExecutorStatus(payload);
    return payload;
  }

  async function executeHostAction(body: AnyRecord) {
    const payload = await jsonFetch(localBackendUrl, "/api/agentic-os/host-executor/execute", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    }).catch((error) => ({ allowed: false, executed: false, denied_reason: String(error) }));
    setHostExecutorResult(payload);
    await refreshHostExecutor().catch(() => undefined);
  }

  async function importLatestOpenWebRun() {
    const run = results.openWeb;
    if (!run?.run_id) return;
    const payload = await jsonFetch(localBackendUrl, "/api/agentic-os/review/import-web-run", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ run_payload: run }),
    }).catch((error) => ({ error: String(error), items: [] }));
    setReviewStatus(payload);
    setReviewItems(Array.isArray(payload.items) ? payload.items : []);
  }

  async function decideReviewItem(itemId: string, decision: ReviewDecision) {
    await jsonFetch(localBackendUrl, "/api/agentic-os/review/decide", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        item_id: itemId,
        decision,
        reviewer: "lab_operator",
        reason: `lab ${decision}`,
        approved_for: "draft_only",
      }),
    }).catch(() => null);
    await refreshReviewQueue().catch(() => undefined);
  }

  const t = language === "ko"
    ? {
      title: "Agentic Micro-OS",
      subtitle: "검토 전용 도구 관문입니다. 공개 웹 탐색 결과는 후보 초안으로만 남고, 기억 쓰기와 production 변경은 차단됩니다.",
      proof: "proof-only",
      modules: "Module Status",
      blocked: "Blocked Actions",
      dashboard: "Dashboard Action Bus",
      browser: "Browser Read",
      mcp: "MCP Allowlist",
      splatra: "SPLATRA Evaluator",
      openWeb: "Open-Web Explorer",
      reviewQueue: "Agentic Review Queue",
      safety: "Safety Contract",
      dashboardSmoke: "Validate set_orb_state",
      browserSmoke: "Read public screen snapshot",
      mcpSmoke: "Validate MCP descriptor",
      splatraSmoke: "Evaluate Cosmos candidate",
      openWebSmoke: "Run fixture open-web loop",
      reviewImport: "Import latest web run",
      reviewRefresh: "Refresh review queue",
    }
    : {
      title: "Agentic Micro-OS",
      subtitle: "Proof-only tool gateway. Public-web exploration creates reviewable drafts; memory mutation and promotion stay blocked.",
      proof: "proof-only",
      modules: "Module Status",
      blocked: "Blocked Actions",
      dashboard: "Dashboard Action Bus",
      browser: "Browser Read",
      mcp: "MCP Allowlist",
      splatra: "SPLATRA Evaluator",
      openWeb: "Open-Web Explorer",
      reviewQueue: "Agentic Review Queue",
      safety: "Safety Contract",
      dashboardSmoke: "Validate set_orb_state",
      browserSmoke: "Read public screen snapshot",
      mcpSmoke: "Validate MCP descriptor",
      splatraSmoke: "Evaluate Cosmos candidate",
      openWebSmoke: "Run fixture open-web loop",
      reviewImport: "Import latest web run",
      reviewRefresh: "Refresh review queue",
    };

  return (
    <section className="agentic-os-panel">
      <header className="agentic-os-hero">
        <div>
          <span>{t.proof}</span>
          <h2>{t.title}</h2>
          <p>{t.subtitle}</p>
        </div>
        <strong data-ready={status?.proof_only === true}>{status?.proof_only ? "READY" : "WAITING"}</strong>
      </header>

      <div className="agentic-os-grid">
        <article className="agentic-os-card">
          <h3>{t.modules}</h3>
          <div className="agentic-os-module-grid">
            {moduleLabels.map(([key, label]) => (
              <span key={key}>
                <small>{label}</small>
                <strong>{status?.modules?.[key] ?? "unknown"}</strong>
              </span>
            ))}
          </div>
        </article>

        <article className="agentic-os-card">
          <h3>{t.blocked}</h3>
          <div className="agentic-os-lock-list">
            {blockedActions.map((item: string) => <span key={item}>{item}</span>)}
          </div>
        </article>

        <article className={`agentic-os-card agentic-os-permission-card ${permissionStatus?.tier4_active ? "is-tier4" : ""}`}>
          <div className="agentic-os-permission-header">
            <div>
              <h3>Autonomy Permission Gate</h3>
              <p>Operator-confirmed permission tier. Tier 4 is time-limited, logged, and blocked by emergency stop.</p>
            </div>
            <strong>{permissionStatus?.tier ?? "unknown"}</strong>
          </div>
          {permissionStatus?.tier4_active ? (
            <div className="agentic-os-tier4-warning">
              FULL HOST AUTHORITY ENABLED. ATANOR may access and modify this PC within enabled sub-switches until the timer expires.
            </div>
          ) : null}
          <div className="agentic-os-actions">
            {autonomyTiers.map((tier) => (
              <button type="button" className="agentic-os-action" key={tier} onClick={() => setPermissionTier(tier)}>
                {tier}
              </button>
            ))}
            <button type="button" className="agentic-os-action danger" onClick={() => disableFullHost()}>
              disable full host
            </button>
            <button type="button" className="agentic-os-action danger" onClick={() => triggerEmergencyStop()}>
              emergency stop
            </button>
          </div>
          <div className="agentic-os-permission-form">
            <input
              aria-label="full host confirmation phrase"
              value={typedPhrase}
              onChange={(event) => setTypedPhrase(event.target.value)}
              placeholder="ENABLE FULL HOST AUTHORITY FOR ATANOR"
            />
            <select aria-label="full host duration" value={durationSec} onChange={(event) => setDurationSec(event.target.value)}>
              <option value="600">10 min</option>
              <option value="1800">30 min</option>
              <option value="7200">2 hours</option>
              <option value="21600">6 hours</option>
            </select>
            <button type="button" className="agentic-os-action danger" onClick={() => enableFullHost()}>
              enable Tier 4
            </button>
          </div>
          <div className="agentic-os-switch-grid">
            {autonomySwitches.map((name) => (
              <label key={name}>
                <input
                  type="checkbox"
                  checked={Boolean(subSwitches[name])}
                  onChange={(event) => setSubSwitches((current) => ({ ...current, [name]: event.target.checked }))}
                />
                <span>{name}</span>
              </label>
            ))}
          </div>
          <div className="agentic-os-flags">
            <span>active={String(permissionStatus?.tier4_active ?? false)}</span>
            <span>expires={permissionStatus?.session?.expires_at ?? "-"}</span>
            <span>audit={permissionStatus?.audit_log_path ?? "-"}</span>
            <span>emergency_stop={String(permissionStatus?.emergency_stop_triggered ?? false)}</span>
          </div>
          <div className="agentic-os-capability-matrix">
            <span>Tier 1: read summaries only</span>
            <span>Tier 2: review drafts and patch proposals only</span>
            <span>Tier 3: signed scoped delegation</span>
            <span>Tier 4: typed phrase + duration + sub-switches</span>
          </div>
          <ResultLine result={permissionResult} />
        </article>

        <article className="agentic-os-card agentic-os-host-executor-card">
          <div className="agentic-os-permission-header">
            <div>
              <h3>Host Executor v0</h3>
              <p>Harmless owner-approved diagnostics only. Destructive operations, production writes, Local Brain writes, commits, and pushes are rejected.</p>
            </div>
            <strong>{hostExecutorStatus?.available ? "AVAILABLE" : "WAITING"}</strong>
          </div>
          <div className="agentic-os-flags">
            <span>tier={permissionStatus?.tier ?? "-"}</span>
            <span>tier4={String(permissionStatus?.tier4_active ?? false)}</span>
            <span>emergency_stop={String(permissionStatus?.emergency_stop_triggered ?? false)}</span>
            <span>tmp={hostExecutorStatus?.runtime_tmp_dir ?? "-"}</span>
          </div>
          <div className="agentic-os-actions">
            <button type="button" className="agentic-os-action" onClick={() => executeHostAction({ action_type: "echo", content: "ATANOR host executor echo", safe_test_token: hostSafeTestToken })}>
              echo
            </button>
            <button type="button" className="agentic-os-action" onClick={() => executeHostAction({ action_type: "git_status", safe_test_token: hostSafeTestToken })}>
              git status
            </button>
            <button type="button" className="agentic-os-action" onClick={() => executeHostAction({ action_type: "write_temp_file", path: "lab-note.txt", content: "host executor lab proof", safe_test_token: hostSafeTestToken })}>
              write temp file
            </button>
            <button type="button" className="agentic-os-action" onClick={() => executeHostAction({ action_type: "read_text_file", path: `${hostExecutorStatus?.runtime_tmp_dir ?? "runtime/agentic_micro_os/tmp"}/lab-note.txt`, safe_test_token: hostSafeTestToken })}>
              read temp file
            </button>
            <button type="button" className="agentic-os-action danger" onClick={() => executeHostAction({ action_type: "run_arbitrary_command", content: "whoami", safe_test_token: hostSafeTestToken })}>
              reject arbitrary shell
            </button>
            <button type="button" className="agentic-os-action danger" onClick={() => executeHostAction({ action_type: "delete_file", path: "runtime/agentic_micro_os/tmp/lab-note.txt", safe_test_token: hostSafeTestToken })}>
              reject delete
            </button>
            <button type="button" className="agentic-os-action danger" onClick={() => executeHostAction({ action_type: "cloud_production_write", safe_test_token: hostSafeTestToken })}>
              reject production write
            </button>
          </div>
          {hostExecutorResult ? (
            <div className="agentic-os-host-result">
              <strong>{hostExecutorResult.allowed ? "allowed" : "denied"} · executed={String(hostExecutorResult.executed ?? false)}</strong>
              <p>{hostExecutorResult.denied_reason || hostExecutorResult.stdout_excerpt || hostExecutorResult.reason || "no output"}</p>
              <span>{(hostExecutorResult.path_refs ?? []).join(" · ")}</span>
            </div>
          ) : <p>idle</p>}
        </article>

        <article className="agentic-os-card">
          <h3>{t.dashboard}</h3>
          <button type="button" className="agentic-os-action" onClick={() => runSmoke("dashboard", "/api/agentic-os/action/validate", { action_type: "set_orb_state", payload: { state: "thinking" } })}>
            {t.dashboardSmoke}
          </button>
          <ResultLine result={results.dashboard} />
        </article>

        <article className="agentic-os-card">
          <h3>{t.browser}</h3>
          <p>Summarizes caller-provided public visible text. No browser automation or JavaScript execution.</p>
          <button type="button" className="agentic-os-action" onClick={() => runSmoke("browser", "/api/agentic-os/browser-read", { url: "http://127.0.0.1:3041/?section=agent-os", visible_text: "Agentic Micro-OS proof-only visible status" })}>
            {t.browserSmoke}
          </button>
          <ResultLine result={results.browser} />
        </article>

        <article className="agentic-os-card">
          <h3>{t.mcp}</h3>
          <p>Checks descriptor hash, method, and private payload boundaries. No real MCP server is called.</p>
          <button type="button" className="agentic-os-action" onClick={() => runSmoke("mcp", "/api/agentic-os/mcp/validate", { descriptor: "render_preview", method: "render_preview", payload: { scene: "orb" } })}>
            {t.mcpSmoke}
          </button>
          <ResultLine result={results.mcp} />
        </article>

        <article className="agentic-os-card">
          <h3>{t.splatra}</h3>
          <p>Scores SPLATRA candidates without applying patches or executing generated code.</p>
          <button type="button" className="agentic-os-action" onClick={() => runSmoke("splatra", "/api/agentic-os/splatra/evaluate", { candidate_id: "orb_candidate", particle_budget: 50000, target_fps: 60 })}>
            {t.splatraSmoke}
          </button>
          <ResultLine result={results.splatra} />
        </article>

        <article className="agentic-os-card">
          <h3>{t.openWeb}</h3>
          <p>Explores public URLs without a fixed allowlist while rejecting internal, login, payment, upload, and download-like URLs.</p>
          <button type="button" className="agentic-os-action" onClick={() => runSmoke("openWeb", "/api/agentic-os/web-explorer/open/run", {
            goal: "open web research for ATANOR local TTS, SPLATRA, Turbovec, MCP security, Hermes-style agents",
            seed_urls: ["https://example.com/fish"],
            max_pages: 6,
            max_depth: 2,
            per_domain_delay_sec: 0,
            fixtures: [
              { url: "https://example.com/fish", html: "<html><title>Fish S2 runtime</title><body>Fish Speech local TTS runtime requires isolated Python and model weights outside the repository. <a href='https://example.com/splatra'>SPLATRA particles</a></body></html>" },
              { url: "https://example.com/splatra", html: "<html><title>SPLATRA particles</title><body>SPLATRA WebGPU particle rendering uses compression, quantization, and bounded LOD budgets.</body></html>" },
            ],
          })}>
            {t.openWebSmoke}
          </button>
          <ResultLine result={results.openWeb} />
          <MetricStrip result={results.openWeb} />
        </article>

        <article className="agentic-os-card agentic-os-review-card">
          <h3>{t.reviewQueue}</h3>
          <p>Human review surface for candidate knowledge, skill drafts, source summaries, patches, and tool trajectories. Approval never mutates production.</p>
          <div className="agentic-os-flags">
            <span>pending={String(reviewStatus?.pending ?? 0)}</span>
            <span>approved={String(reviewStatus?.approved ?? 0)}</span>
            <span>rejected={String(reviewStatus?.rejected ?? 0)}</span>
            <span>deferred={String(reviewStatus?.deferred ?? 0)}</span>
            <span>high-risk={String(reviewStatus?.high_risk ?? 0)}</span>
            <span>duplicates={String(reviewStatus?.duplicate_warnings ?? 0)}</span>
          </div>
          <div className="agentic-os-actions">
            <button type="button" className="agentic-os-action" disabled={!results.openWeb?.run_id} onClick={() => importLatestOpenWebRun()}>
              {t.reviewImport}
            </button>
            <button type="button" className="agentic-os-action" onClick={() => refreshReviewQueue()}>
              {t.reviewRefresh}
            </button>
          </div>
          <div className="agentic-os-review-list">
            {reviewItems.length === 0 ? <p>no pending review items</p> : reviewItems.slice(0, 8).map((item) => (
              <div className="agentic-os-review-item" key={item.item_id}>
                <div>
                  <small>{item.item_type} · {item.risk_level} · {item.status}</small>
                  <strong>{item.title}</strong>
                  <p>{item.summary}</p>
                  <span>confidence={String(item.confidence)} novelty={String(item.novelty_score)} duplicate={String(item.duplicate_score)}</span>
                </div>
                <div className="agentic-os-review-actions">
                  <button type="button" onClick={() => decideReviewItem(item.item_id, "approved")}>approve as draft</button>
                  <button type="button" onClick={() => decideReviewItem(item.item_id, "rejected")}>reject</button>
                  <button type="button" onClick={() => decideReviewItem(item.item_id, "deferred")}>defer</button>
                  <button type="button" onClick={() => decideReviewItem(item.item_id, "needs_more_evidence")}>needs evidence</button>
                </div>
              </div>
            ))}
          </div>
        </article>

        <article className="agentic-os-card">
          <h3>{t.safety}</h3>
          <p>Local Brain, Cloud Brain, and candidate promotion are never mutated outside approval gates.</p>
          <p>External LLM/sLLM, Hermes runtime, unrestricted shell, and arbitrary JavaScript stay disabled.</p>
          <div className="agentic-os-flags">
            <span>external_llm={String(status?.external_llm ?? false)}</span>
            <span>external_sllm={String(status?.external_sllm ?? false)}</span>
            <span>local_brain_write={String(status?.local_brain_write ?? false)}</span>
            <span>production_store_mutated={String(status?.production_store_mutated ?? false)}</span>
            <span>auto_push={String(status?.auto_push ?? false)}</span>
          </div>
        </article>
      </div>
    </section>
  );
}
