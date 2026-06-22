"use client";

import { useEffect, useMemo, useState } from "react";

type Language = "en" | "ko";
type AnyRecord = Record<string, any>;

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
  ["mcp_gateway_mock", "MCP Gateway"],
  ["browser_gateway_mock", "Browser Gateway"],
  ["cloud_gateway_mock", "Cloud Gateway"],
  ["hermes_intake", "Hermes Intake"],
] as const;

function joinApiUrl(baseUrl: string, path: string) {
  return `${baseUrl.replace(/\/$/, "")}${path}`;
}

async function jsonFetch(baseUrl: string, path: string, init?: RequestInit): Promise<AnyRecord> {
  const response = await fetch(joinApiUrl(baseUrl, path), { ...init, cache: "no-store" });
  return response.json();
}

export default function AgenticMicroOSPanel({ language, localBackendUrl }: Props) {
  const [status, setStatus] = useState<AnyRecord | null>(null);
  const [validation, setValidation] = useState<AnyRecord | null>(null);

  useEffect(() => {
    jsonFetch(localBackendUrl, "/api/agentic-os/status").then(setStatus).catch(() => setStatus({ error: "local_backend_unavailable" }));
  }, [localBackendUrl]);

  const blockedActions = useMemo(() => {
    const list = Array.isArray(status?.blocked_actions) ? status?.blocked_actions : [];
    return list.length ? list : ["unrestricted_shell", "arbitrary_js_eval", "local_brain_direct_write", "production_store_direct_write", "auto_commit", "auto_push"];
  }, [status]);

  async function validateThinkingAction() {
    const result = await jsonFetch(localBackendUrl, "/api/agentic-os/action/validate", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ action_type: "set_orb_state", payload: { state: "thinking" } }),
    }).catch((error) => ({ allowed: false, reason: String(error) }));
    setValidation(result);
  }

  const t = language === "ko"
    ? {
      title: "Agentic Micro-OS",
      subtitle: "증명 전용 상태 표면입니다. 실제 Hermes 실행, MCP, 브라우저 자동화, 셸, 기억 쓰기는 꺼져 있습니다.",
      proof: "proof-only",
      modules: "모듈 상태",
      blocked: "차단된 동작",
      validate: "Dashboard Action Bus 검사",
      smoke: "set_orb_state(\"thinking\") 검증",
      accepted: "accepted",
      rejected: "rejected",
      boundaryA: "에이전트는 SPLATRA Cosmos Cell 안에서만 자유롭게 실험합니다.",
      boundaryB: "Local Brain과 Cloud Brain은 승인된 접근 경로로만 연결됩니다.",
    }
    : {
      title: "Agentic Micro-OS",
      subtitle: "Proof-only status surface. Real Hermes runtime, MCP, browser automation, shell, and memory writes are disabled.",
      proof: "proof-only",
      modules: "Module Status",
      blocked: "Blocked Actions",
      validate: "Dashboard Action Bus Check",
      smoke: "Validate set_orb_state(\"thinking\")",
      accepted: "accepted",
      rejected: "rejected",
      boundaryA: "The agent can explore freely only inside the SPLATRA Cosmos Cell.",
      boundaryB: "Local Brain and Cloud Brain connect only through approved access roads.",
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
          <h3>{t.validate}</h3>
          <button type="button" className="agentic-os-action" onClick={() => validateThinkingAction()}>
            {t.smoke}
          </button>
          <p>
            {validation ? (validation.allowed ? t.accepted : t.rejected) : "idle"}
            {validation?.reason ? ` · ${validation.reason}` : ""}
          </p>
        </article>

        <article className="agentic-os-card">
          <h3>Safety Contract</h3>
          <p>{t.boundaryA}</p>
          <p>{t.boundaryB}</p>
          <div className="agentic-os-flags">
            <span>external_llm={String(status?.external_llm ?? false)}</span>
            <span>hermes_runtime_executed={String(status?.hermes_runtime_executed ?? false)}</span>
            <span>auto_push={String(status?.auto_push ?? false)}</span>
          </div>
        </article>
      </div>
    </section>
  );
}
