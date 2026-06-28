"use client";

import { useCallback, useEffect, useState } from "react";

/**
 * ATANOR Plugin Kit — a Codex-inspired plugin surface that hangs off the chat
 * bar. Plugins are diverse *sentence-collection* sources (paste / web / RSS /
 * wiki / file / clipboard) plus a gated PC tool. Every capability carries a risk
 * tier; sensitive ones need an explicit Allow and the dangerous pc:control needs
 * a typed phrase — a default-deny approval gate. Collected sentences flow into
 * the Cloud-Brain firehose (수집 ≠ 이해, kept honestly separate).
 */

type Cap = { id: string; risk: string; label: string; label_en: string; state: string };
type Plugin = {
  id: string; name: string; marketplace: string; version: string; kind: string;
  icon: string; description: string; max_risk: string; enabled: boolean; ready: boolean;
  composer: { slash: string; label: string; placeholder: string; field: string | null };
  capabilities: Cap[];
};
type ListResp = {
  plugins: Plugin[]; marketplaces: string[]; pc_control_phrase: string; offline?: boolean;
};

const RISK_COLOR: Record<string, string> = { safe: "#34d399", sensitive: "#fbbf24", dangerous: "#f87171" };
const RISK_KO: Record<string, string> = { safe: "안전", sensitive: "민감", dangerous: "위험" };

export default function PluginKitPanel({ open, onClose, language = "ko" }: {
  open: boolean; onClose: () => void; language?: "ko" | "en";
}) {
  const ko = language === "ko";
  const [data, setData] = useState<ListResp | null>(null);
  const [loading, setLoading] = useState(false);
  const [inputs, setInputs] = useState<Record<string, string>>({});
  const [phrase, setPhrase] = useState<Record<string, string>>({});
  const [results, setResults] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch("/api/plugins", { cache: "no-store" });
      setData(await r.json());
    } catch {
      /* keep last */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { if (open) refresh(); }, [open, refresh]);

  async function toggle(p: Plugin) {
    await fetch(`/api/plugins/${encodeURIComponent(p.id)}/enable`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: !p.enabled }),
    }).catch(() => {});
    refresh();
  }

  async function decide(p: Plugin, cap: Cap, decision: "grant" | "deny") {
    const body: Record<string, unknown> = { decision };
    if (cap.risk === "dangerous") body.phrase = phrase[p.id] ?? "";
    const r = await fetch(`/api/plugins/${encodeURIComponent(p.id)}/permissions/${encodeURIComponent(cap.id)}`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    if (!r.ok) {
      const j = await r.json().catch(() => ({}));
      setResults((s) => ({ ...s, [p.id]: typeof j.detail === "string" ? j.detail : (ko ? "승인 문구가 정확해야 합니다." : "Phrase must match.") }));
    }
    refresh();
  }

  async function run(p: Plugin) {
    setBusy(p.id);
    setResults((s) => ({ ...s, [p.id]: "" }));
    const field = p.composer.field;
    const input: Record<string, unknown> = {};
    if (field) input[field] = inputs[p.id] ?? "";
    try {
      const r = await fetch(`/api/plugins/${encodeURIComponent(p.id)}/run`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ input }),
      });
      const j = await r.json();
      if (!r.ok) {
        const cap = j?.detail?.capability || j?.capability;
        setResults((s) => ({ ...s, [p.id]: cap ? (ko ? `권한 필요: ${cap}` : `Needs permission: ${cap}`) : (j?.detail || j?.error || (ko ? "실행 실패" : "Failed")) }));
      } else {
        setResults((s) => ({ ...s, [p.id]: ko
          ? `수집 ${j.unique}문장 · 파이어호스 전송 ${j.fed_firehose ? "✓" : "—"}${j.sample?.[0] ? ` · 예: "${j.sample[0].slice(0, 40)}"` : ""}`
          : `Collected ${j.unique} · firehose ${j.fed_firehose ? "✓" : "—"}` }));
      }
    } catch {
      setResults((s) => ({ ...s, [p.id]: ko ? "엔진(:8502) 연결 필요" : "Engine (:8502) required" }));
    } finally {
      setBusy(null);
      refresh();
    }
  }

  if (!open) return null;

  const byMarket: Record<string, Plugin[]> = {};
  (data?.plugins ?? []).forEach((p) => { (byMarket[p.marketplace] ||= []).push(p); });

  return (
    <div onClick={onClose} style={{ position: "fixed", inset: 0, zIndex: 1000, background: "rgba(4,7,14,0.55)", backdropFilter: "blur(2px)" }}>
      <aside onClick={(e) => e.stopPropagation()} style={{
        position: "absolute", top: 0, right: 0, height: "100%", width: "min(560px, 94vw)",
        background: "#0b1018", borderLeft: "1px solid #1d2734", color: "#dfe7f1",
        display: "flex", flexDirection: "column", boxShadow: "-24px 0 60px rgba(0,0,0,0.5)",
      }}>
        <header style={{ display: "flex", alignItems: "center", gap: 10, padding: "16px 18px", borderBottom: "1px solid #1d2734" }}>
          <span style={{ fontSize: 18 }}>🧩</span>
          <div style={{ flex: 1 }}>
            <strong style={{ fontSize: 15 }}>{ko ? "플러그인 키트" : "Plugin Kit"}</strong>
            <div style={{ fontSize: 11, color: "#7f8ea3" }}>
              {ko ? "다양한 소스로 문장 수집 + 권한 범위 · 승인 게이트" : "Diverse sentence sources + permission scopes"}
              {data?.offline ? (ko ? " · 엔진 오프라인(카탈로그만)" : " · engine offline") : ""}
            </div>
          </div>
          <button onClick={refresh} title="refresh" style={btnGhost}>↻</button>
          <button onClick={onClose} aria-label="close" style={btnGhost}>×</button>
        </header>

        <div style={{ overflowY: "auto", padding: "8px 14px 28px" }}>
          {loading && !data ? <p style={{ color: "#7f8ea3", padding: 16 }}>{ko ? "불러오는 중…" : "Loading…"}</p> : null}
          {(data?.marketplaces ?? Object.keys(byMarket)).map((mk) => (
            <section key={mk} style={{ marginTop: 14 }}>
              <div style={{ fontSize: 11, letterSpacing: 0.5, color: "#6b7a90", textTransform: "uppercase", margin: "6px 4px" }}>{mk}</div>
              {(byMarket[mk] ?? []).map((p) => {
                const result = results[p.id];
                const sourceReady = p.kind === "source" && p.enabled && p.ready;
                return (
                  <article key={p.id} style={card}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <strong style={{ fontSize: 13.5 }}>{p.name}</strong>
                          <code style={{ fontSize: 10, color: "#6b7a90" }}>{p.composer.slash}</code>
                          <span style={{ ...pill, background: `${RISK_COLOR[p.max_risk]}22`, color: RISK_COLOR[p.max_risk], borderColor: `${RISK_COLOR[p.max_risk]}55` }}>
                            {ko ? RISK_KO[p.max_risk] : p.max_risk}
                          </span>
                        </div>
                        <div style={{ fontSize: 11.5, color: "#8b9ab0", marginTop: 3 }}>{p.description}</div>
                      </div>
                      <button onClick={() => toggle(p)} style={{ ...toggleBtn, background: p.enabled ? "#1f6feb" : "#1a2330", color: p.enabled ? "#fff" : "#8b9ab0" }}>
                        {p.enabled ? "ON" : "OFF"}
                      </button>
                    </div>

                    {/* capabilities + approval */}
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 9 }}>
                      {p.capabilities.map((c) => (
                        <div key={c.id} style={{ display: "flex", alignItems: "center", gap: 5, ...pill, borderColor: "#26313f" }}>
                          <span style={{ width: 7, height: 7, borderRadius: 9, background: RISK_COLOR[c.risk] }} />
                          <span style={{ color: "#aebbcd" }}>{ko ? c.label : c.label_en}</span>
                          {c.risk !== "safe" ? (
                            c.state === "granted"
                              ? <button onClick={() => decide(p, c, "deny")} style={{ ...miniBtn, color: "#34d399" }}>{ko ? "허용됨 ✓" : "Allowed ✓"}</button>
                              : <button onClick={() => decide(p, c, "grant")} style={{ ...miniBtn, color: RISK_COLOR[c.risk] }}>{ko ? "허용" : "Allow"}</button>
                          ) : null}
                        </div>
                      ))}
                    </div>

                    {/* dangerous phrase gate */}
                    {p.capabilities.some((c) => c.risk === "dangerous" && c.state !== "granted") ? (
                      <div style={{ marginTop: 8 }}>
                        <input value={phrase[p.id] ?? ""} onChange={(e) => setPhrase((s) => ({ ...s, [p.id]: e.target.value }))}
                          placeholder={ko ? `승인 문구 입력: "${data?.pc_control_phrase ?? ""}"` : `Type phrase: "${data?.pc_control_phrase ?? ""}"`}
                          style={field} />
                      </div>
                    ) : null}

                    {/* composer (collect) */}
                    {p.kind === "source" ? (
                      <div style={{ display: "flex", gap: 6, marginTop: 9 }}>
                        {p.composer.field ? (
                          <input value={inputs[p.id] ?? ""} onChange={(e) => setInputs((s) => ({ ...s, [p.id]: e.target.value }))}
                            placeholder={p.composer.placeholder} style={{ ...field, flex: 1 }} disabled={!sourceReady} />
                        ) : <div style={{ flex: 1, fontSize: 11.5, color: "#6b7a90", alignSelf: "center" }}>{p.composer.placeholder}</div>}
                        <button onClick={() => run(p)} disabled={!sourceReady || busy === p.id} style={{ ...runBtn, opacity: sourceReady ? 1 : 0.45 }}>
                          {busy === p.id ? "…" : (ko ? "수집" : "Collect")}
                        </button>
                      </div>
                    ) : (
                      <div style={{ display: "flex", gap: 6, marginTop: 9 }}>
                        <input value={inputs[p.id] ?? ""} onChange={(e) => setInputs((s) => ({ ...s, [p.id]: e.target.value }))}
                          placeholder={p.composer.placeholder} style={{ ...field, flex: 1 }} disabled={!(p.enabled && p.ready)} />
                        <button onClick={() => run(p)} disabled={!(p.enabled && p.ready) || busy === p.id} style={{ ...runBtn, opacity: p.enabled && p.ready ? 1 : 0.45 }}>
                          {busy === p.id ? "…" : (ko ? "실행" : "Run")}
                        </button>
                      </div>
                    )}

                    {result ? <div style={{ marginTop: 7, fontSize: 11.5, color: result.includes("✓") || result.includes("수집") ? "#7fd4ff" : "#f0a35a" }}>{result}</div> : null}
                  </article>
                );
              })}
            </section>
          ))}
          <p style={{ fontSize: 10.5, color: "#5b6a7e", marginTop: 18, lineHeight: 1.6 }}>
            {ko
              ? "수집(본 문장) ≠ 이해(개념)는 분리해서 셉니다 · 공개 소스만 · ToS 위반 스크래핑 없음 · PC 제어는 읽기전용·허용목록·문구승인."
              : "Collected ≠ understood · public sources only · no ToS-violating scraping · PC control is read-only, allowlisted, phrase-gated."}
          </p>
        </div>
      </aside>
    </div>
  );
}

const btnGhost: React.CSSProperties = { background: "transparent", border: "none", color: "#8b9ab0", fontSize: 17, cursor: "pointer", padding: "2px 6px" };
const card: React.CSSProperties = { background: "#0f1521", border: "1px solid #1d2734", borderRadius: 12, padding: "12px 13px", marginBottom: 9 };
const pill: React.CSSProperties = { fontSize: 10, padding: "2px 7px", borderRadius: 999, border: "1px solid", whiteSpace: "nowrap" };
const toggleBtn: React.CSSProperties = { border: "none", borderRadius: 8, padding: "5px 11px", fontSize: 11, fontWeight: 700, cursor: "pointer" };
const miniBtn: React.CSSProperties = { background: "transparent", border: "none", fontSize: 10.5, fontWeight: 700, cursor: "pointer", padding: "0 2px" };
const field: React.CSSProperties = { background: "#070b12", border: "1px solid #26313f", borderRadius: 8, color: "#dfe7f1", padding: "7px 10px", fontSize: 12, outline: "none", width: "100%" };
const runBtn: React.CSSProperties = { background: "#1f6feb", border: "none", borderRadius: 8, color: "#fff", padding: "7px 14px", fontSize: 12, fontWeight: 700, cursor: "pointer" };
