"use client";

import { useEffect, useMemo, useState } from "react";

type Language = "en" | "ko";
type AnyRecord = Record<string, any>;
type SmokeKey = "dashboard" | "browser" | "mcp" | "splatra" | "openWeb";

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

function joinApiUrl(baseUrl: string, path: string) {
  return `${baseUrl.replace(/\/$/, "")}${path}`;
}

async function jsonFetch(baseUrl: string, path: string, init?: RequestInit): Promise<AnyRecord> {
  const response = await fetch(joinApiUrl(baseUrl, path), { ...init, cache: "no-store" });
  return response.json();
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
  const [results, setResults] = useState<Record<SmokeKey, AnyRecord | null>>({
    dashboard: null,
    browser: null,
    mcp: null,
    splatra: null,
    openWeb: null,
  });

  useEffect(() => {
    jsonFetch(localBackendUrl, "/api/agentic-os/status").then(setStatus).catch(() => setStatus({ error: "local_backend_unavailable" }));
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

  const t = language === "ko"
    ? {
      title: "Agentic Micro-OS",
      subtitle: "증명 전용 도구 게이트웨이입니다. 공개 웹 탐색은 예산과 denylist 안에서만 동작하고, 기억 변경과 승격은 차단됩니다.",
      proof: "proof-only",
      modules: "모듈 상태",
      blocked: "차단된 동작",
      dashboard: "Dashboard Action Bus",
      browser: "Browser Read",
      mcp: "MCP Allowlist",
      splatra: "SPLATRA Evaluator",
      openWeb: "Open-Web Explorer",
      safety: "Safety Contract",
      dashboardSmoke: "set_orb_state 검증",
      browserSmoke: "공개 화면 스냅샷 읽기",
      mcpSmoke: "MCP descriptor 검증",
      splatraSmoke: "Cosmos 후보 평가",
      openWebSmoke: "fixture open-web run",
      browserText: "이미 보이는 public 텍스트만 요약합니다. 브라우저 자동조작과 JS 실행은 없습니다.",
      mcpText: "descriptor hash, method, private payload 여부만 검사합니다. 실제 MCP 서버는 호출하지 않습니다.",
      splatraText: "SPLATRA 후보를 점수화하지만 패치 적용이나 생성 코드 실행은 하지 않습니다.",
      openWebText: "고정 allowlist 없이 공개 URL을 탐색할 수 있지만 내부망, 로그인, 결제, 업로드, 다운로드성 URL은 거절합니다.",
      boundaryA: "Local Brain, Cloud Brain, 후보 승격은 승인 게이트 밖에서 실행되지 않습니다.",
      boundaryB: "외부 LLM/sLLM, Hermes runtime, 임의 shell, 임의 JS는 비활성입니다.",
    }
    : {
      title: "Agentic Micro-OS",
      subtitle: "Proof-only tool gateway. Open-web exploration is budgeted and denylisted; memory mutation and promotion stay blocked.",
      proof: "proof-only",
      modules: "Module Status",
      blocked: "Blocked Actions",
      dashboard: "Dashboard Action Bus",
      browser: "Browser Read",
      mcp: "MCP Allowlist",
      splatra: "SPLATRA Evaluator",
      openWeb: "Open-Web Explorer",
      safety: "Safety Contract",
      dashboardSmoke: "Validate set_orb_state",
      browserSmoke: "Read public screen snapshot",
      mcpSmoke: "Validate MCP descriptor",
      splatraSmoke: "Evaluate Cosmos candidate",
      openWebSmoke: "Run fixture open-web loop",
      browserText: "Summarizes only caller-provided public visible text. No browser automation or JavaScript execution.",
      mcpText: "Checks descriptor hash, method, and private payload boundaries. No real MCP server is called.",
      splatraText: "Scores SPLATRA candidates without applying patches or executing generated code.",
      openWebText: "Explores public URLs without a fixed allowlist, while rejecting internal, login, payment, upload, and download-like URLs.",
      boundaryA: "Local Brain, Cloud Brain, and candidate promotion are never mutated outside approval gates.",
      boundaryB: "External LLM/sLLM, Hermes runtime, unrestricted shell, and arbitrary JavaScript stay disabled.",
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

        <article className="agentic-os-card">
          <h3>{t.dashboard}</h3>
          <button type="button" className="agentic-os-action" onClick={() => runSmoke("dashboard", "/api/agentic-os/action/validate", { action_type: "set_orb_state", payload: { state: "thinking" } })}>
            {t.dashboardSmoke}
          </button>
          <ResultLine result={results.dashboard} />
        </article>

        <article className="agentic-os-card">
          <h3>{t.browser}</h3>
          <p>{t.browserText}</p>
          <button type="button" className="agentic-os-action" onClick={() => runSmoke("browser", "/api/agentic-os/browser-read", { url: "http://127.0.0.1:3041/?section=agent-os", visible_text: "Agentic Micro-OS proof-only visible status" })}>
            {t.browserSmoke}
          </button>
          <ResultLine result={results.browser} />
        </article>

        <article className="agentic-os-card">
          <h3>{t.mcp}</h3>
          <p>{t.mcpText}</p>
          <button type="button" className="agentic-os-action" onClick={() => runSmoke("mcp", "/api/agentic-os/mcp/validate", { descriptor: "render_preview", method: "render_preview", payload: { scene: "orb" } })}>
            {t.mcpSmoke}
          </button>
          <ResultLine result={results.mcp} />
        </article>

        <article className="agentic-os-card">
          <h3>{t.splatra}</h3>
          <p>{t.splatraText}</p>
          <button type="button" className="agentic-os-action" onClick={() => runSmoke("splatra", "/api/agentic-os/splatra/evaluate", { candidate_id: "orb_candidate", particle_budget: 50000, target_fps: 60 })}>
            {t.splatraSmoke}
          </button>
          <ResultLine result={results.splatra} />
        </article>

        <article className="agentic-os-card">
          <h3>{t.openWeb}</h3>
          <p>{t.openWebText}</p>
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

        <article className="agentic-os-card">
          <h3>{t.safety}</h3>
          <p>{t.boundaryA}</p>
          <p>{t.boundaryB}</p>
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
