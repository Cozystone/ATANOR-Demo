"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import {
  ArrowUp,
  ChevronDown,
  Command,
  FileText,
  Loader2,
  Paperclip,
  Plus,
  Puzzle,
  ShieldCheck,
  SlidersHorizontal,
  SquarePen,
  Video,
  X,
  type LucideIcon,
} from "lucide-react";
import AnswerExperimentSurface, { AnswerVisual } from "./AnswerExperimentSurface";
import AnswerPathScene from "./AnswerPathScene";
import LivingMindPanel from "./LivingMindPanel";
import PluginGallery, { PLUGIN_ICONS } from "./PluginGallery";

type MenuPlugin = { id: string; name: string; icon: string; composer: { slash: string } };

/**
 * Demo chat surface — a GPT/Gemini-style thread that REPLACES the central orb in
 * the existing ATANOR frame (sidebar / branding / panels stay). White content area
 * for general legibility; same engine (/api/chat/atanor). No orb / particles / 3D.
 * A Gemini-style session-history rail (left) lists past conversations.
 */

type Msg = {
  role: "user" | "ai";
  text: string;
  visual?: AnswerVisual | null;
  cert?: string | null;
  /** P5-⑪: the full reasoning_certificate, for the semantic-zoom answer-path view */
  certFull?: Record<string, unknown> | null;
  followUps?: string[];
  pending?: boolean;
  /** live stage label while pending (P5: real state transitions, never fake progress) */
  stage?: string | null;
  /** evidence items streamed BEFORE the answer — irrevocable, labelled as evidence */
  evidence?: { kind: string; value: unknown }[];
  /** engine unreachable / empty reply — renders as an actionable error bubble */
  error?: { retryQuery: string };
};

type Session = { id: string; title: string; messages: Msg[]; ts: number };

const SESSIONS_KEY = "atanor.demo.sessions";

function loadSessions(): Session[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(SESSIONS_KEY);
    const parsed = raw ? (JSON.parse(raw) as Session[]) : [];
    if (!Array.isArray(parsed)) return [];
    // dedupe by title (keep newest) — collapses history saved before dedupe existed
    const seen = new Set<string>();
    return parsed.filter((s) => {
      if (seen.has(s.title)) return false;
      seen.add(s.title);
      return true;
    });
  } catch {
    return [];
  }
}

function sessionTitle(messages: Msg[]): string {
  const firstUser = messages.find((m) => m.role === "user" && m.text.trim());
  const t = (firstUser?.text ?? "").trim();
  return t ? (t.length > 38 ? `${t.slice(0, 38)}…` : t) : "새 대화";
}

function certSummary(cert: unknown): string | null {
  if (!cert || typeof cert !== "object") return null;
  const kind = String((cert as Record<string, unknown>).derivation_kind || "");
  const map: Record<string, string> = {
    deterministic_arithmetic: "결정론적 계산 · 외부 LLM 없음",
    deterministic_word_problem: "단계별 추론 · 외부 LLM 없음",
    deterministic_geometry: "도형 공식 · 외부 LLM 없음",
    deterministic_exponent: "거듭제곱 · 외부 LLM 없음",
    deterministic_function_plot: "함수 샘플링 · 외부 LLM 없음",
    web_attribution_extraction: "웹 근거에서 인물 추출 · 출처 표기",
    web_search_grounding: "웹 근거 기반 · 출처 표기",
    web_no_relevant_source: "관련 근거 없음 → 정직하게 보류",
    web_unreachable: "웹 확인 불가 → 보류",
    atanor_self_knowledge: "자기 모델 (큐레이션)",
    atanor_self_model_realized: "자기 모델 · 표면 실현 (질문에 맞춰 구성)",
  };
  return map[kind] || (kind ? kind.replace(/_/g, " ") : null);
}

/** P5-⑪: a certificate is worth drawing when it carries a real graph derivation
 * (an anchor + at least one relation hop). Thin/abstained/web certs get no toggle. */
function hasDrawablePath(cert: Record<string, unknown> | null | undefined): boolean {
  if (!cert || typeof cert !== "object") return false;
  if (String(cert.derivation_kind || "") !== "ontology_graph_derivation") return false;
  const steps = Array.isArray(cert.steps) ? (cert.steps as Record<string, unknown>[]) : [];
  return steps.some((s) => String(s.type || "").startsWith("graph_relation"));
}

export default function DemoChat({ language }: { language: "ko" | "en" }) {
  const ko = language === "ko";
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentId, setCurrentId] = useState<string>(() => `s-${Date.now()}`);
  const [galleryOpen, setGalleryOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [menuPlugins, setMenuPlugins] = useState<MenuPlugin[]>([]);
  const [capsOpen, setCapsOpen] = useState(false);
  const [attaching, setAttaching] = useState(false);
  // P5-⑪: which answers have their semantic-zoom derivation path expanded.
  const [openPaths, setOpenPaths] = useState<Set<number>>(new Set());
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const fileRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    setSessions(loadSessions());
  }, []);

  // Plugins listed inline in the "+" menu (Codex-style), fetched once.
  useEffect(() => {
    fetch("/api/plugins", { cache: "no-store" })
      .then((r) => r.json())
      .then((d) => setMenuPlugins(Array.isArray(d?.plugins) ? d.plugins : []))
      .catch(() => {});
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages.length, busy]);

  // Persist the active session (with at least one settled exchange) into history.
  useEffect(() => {
    const settled = messages.filter((m) => !m.pending);
    if (!settled.some((m) => m.role === "ai" && m.text.trim())) return;
    setSessions((prev) => {
      const title = sessionTitle(settled);
      // dedupe: the same question re-asked replaces its older session instead of stacking
      const others = prev.filter((s) => s.id !== currentId && s.title !== title);
      const next: Session[] = [
        { id: currentId, title, messages: settled, ts: Date.now() },
        ...others,
      ].slice(0, 40);
      try {
        window.localStorage.setItem(SESSIONS_KEY, JSON.stringify(next));
      } catch {
        /* ignore quota */
      }
      return next;
    });
  }, [messages, currentId]);

  function closePanels() {
    setGalleryOpen(false);
    setCapsOpen(false);
    setMenuOpen(false);
  }

  function newChat() {
    setMessages([]);
    setInput("");
    setCurrentId(`s-${Date.now()}`);
    closePanels();
  }

  function deleteSession(id: string) {
    setSessions((prev) => {
      const next = prev.filter((s) => s.id !== id);
      try {
        window.localStorage.setItem(SESSIONS_KEY, JSON.stringify(next));
      } catch {
        /* ignore quota */
      }
      return next;
    });
    if (id === currentId) newChat();
  }

  function openSession(session: Session) {
    setMessages(session.messages);
    setCurrentId(session.id);
    setInput("");
    closePanels();
  }

  /** P5-⑫: consume the stage/evidence SSE stream. Returns the final result, or null
   * to signal fallback to the plain JSON endpoint. Only irrevocable content is
   * surfaced early (stage labels = true engine states; evidence = labelled quotes). */
  async function streamQuery(q: string, lang: string): Promise<Record<string, unknown> | null> {
    const res = await fetch("http://127.0.0.1:8502/api/chat/atanor/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q, language: lang, web_search: true }),
    });
    if (!res.ok || !res.body) return null;
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let result: Record<string, unknown> | null = null;
    const stageLabel: Record<string, string> = {
      analyzing: lang === "ko" ? "질문 분석 중" : "analyzing",
      grounding: lang === "ko" ? "근거 확인 중" : "grounding",
    };
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split("\n\n");
      buffer = events.pop() ?? "";
      for (const ev of events) {
        const line = ev.split("\n").find((l) => l.startsWith("data: "));
        if (!line) continue;
        let payload: Record<string, unknown>;
        try {
          payload = JSON.parse(line.slice(6));
        } catch {
          continue;
        }
        if (payload.type === "stage") {
          const label = stageLabel[String(payload.stage)] ?? String(payload.stage);
          setMessages((m) => {
            const next = m.slice();
            const last = next[next.length - 1];
            if (last?.pending) next[next.length - 1] = { ...last, stage: label };
            return next;
          });
        } else if (payload.type === "evidence") {
          const items = (payload.items as { kind: string; value: unknown }[]) ?? [];
          if (items.length) {
            setMessages((m) => {
              const next = m.slice();
              const last = next[next.length - 1];
              if (last?.pending) next[next.length - 1] = { ...last, evidence: items };
              return next;
            });
          }
        } else if (payload.type === "answer") {
          const envelope = (payload.result as Record<string, unknown>) ?? null;
          const inner = envelope && typeof envelope.result === "object" && envelope.result
            ? (envelope.result as Record<string, unknown>)
            : envelope;
          result = inner;
        } else if (payload.type === "error") {
          return null;
        }
      }
    }
    return result;
  }

  async function runQuery(q: string) {
    q = q.trim();
    if (!q || busy) return;
    setInput("");
    setBusy(true);
    closePanels();
    const lang = /[가-힣]/.test(q) ? "ko" : "en";
    setMessages((m) => [...m, { role: "user", text: q }, { role: "ai", text: "", pending: true }]);
    try {
      let r: Record<string, unknown> | null = null;
      try {
        r = await streamQuery(q, lang);
      } catch {
        r = null; // stream unavailable → legacy path below
      }
      if (!r) {
        const res = await fetch("/api/chat/atanor", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question: q, language: lang, web_search: true }),
        });
        const data = await res.json();
        r = (data?.result ?? data) as Record<string, unknown>;
      }
      const answer = String(r?.answer ?? "").trim();
      if (!answer) {
        // empty reply = engine reachable but returned nothing → actionable, not a dead "(응답 없음)"
        setMessages((m) => {
          const next = m.slice();
          next[next.length - 1] = {
            role: "ai",
            text: ko ? "엔진이 응답을 만들지 못했어요." : "The engine returned no answer.",
            error: { retryQuery: q },
          };
          return next;
        });
        return;
      }
      const followRaw = r?.follow_ups;
      const followUps = Array.isArray(followRaw)
        ? (followRaw as unknown[]).map((f) => String(f)).filter((f) => f.trim()).slice(0, 4)
        : undefined;
      setMessages((m) => {
        const next = m.slice();
        next[next.length - 1] = {
          role: "ai",
          text: answer,
          visual: (r?.answer_visual as AnswerVisual | undefined) ?? null,
          cert: certSummary(r?.reasoning_certificate),
          certFull: (r?.reasoning_certificate as Record<string, unknown> | undefined) ?? null,
          followUps,
        };
        return next;
      });
    } catch {
      setMessages((m) => {
        const next = m.slice();
        next[next.length - 1] = {
          role: "ai",
          text: ko ? "로컬 엔진에 연결할 수 없어요. 엔진이 꺼져 있을 수 있습니다." : "Can't reach the local engine — it may be offline.",
          error: { retryQuery: q },
        };
        return next;
      });
    } finally {
      setBusy(false);
    }
  }

  async function send(e: FormEvent) {
    e.preventDefault();
    await runQuery(input);
  }

  async function onPickFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    setMenuOpen(false);
    if (!file) return;
    setAttaching(true);
    try {
      const b64 = await new Promise<string>((res, rej) => {
        const fr = new FileReader();
        fr.onload = () => res(String(fr.result));
        fr.onerror = rej;
        fr.readAsDataURL(file);
      });
      const r = await fetch("/api/media/read", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image_b64: b64 }),
      });
      const d = await r.json();
      if (d?.ok && d.text) {
        setInput((v) => (v ? v + "\n" : "") + `[첨부 이미지에서 읽은 텍스트]\n${d.text}\n\n`);
      } else {
        setInput((v) => v + (ko ? `\n(이미지 OCR 불가: ${d?.error || "오류"})` : `\n(OCR failed: ${d?.error})`));
      }
    } catch {
      setInput((v) => v + (ko ? "\n(이미지 읽기 실패)" : "\n(image read failed)"));
    } finally {
      setAttaching(false);
    }
  }

  // The chat-bar "+" menu, structured like Codex: sectioned (추가 / 플러그인 / 도구),
  // each row = icon + name + inline description; plugins listed inline.
  type MenuRow = { Icon: LucideIcon; name: string; desc: string; onClick: () => void };
  const addRows: MenuRow[] = [
    { Icon: Paperclip, name: ko ? "파일 · 이미지 첨부" : "Attach file · image", desc: ko ? "ATANOR가 읽어요 (OCR)" : "ATANOR reads it (OCR)", onClick: () => fileRef.current?.click() },
    { Icon: Video, name: ko ? "영상 · 링크" : "Video · link", desc: ko ? "유튜브/이미지 URL 붙여넣기" : "paste a YouTube/image URL", onClick: () => { setMenuOpen(false); setInput((v) => v + " https://youtu.be/"); } },
  ];
  const toolRows: MenuRow[] = [
    { Icon: ShieldCheck, name: ko ? "권한 · 기능" : "Permissions · capabilities", desc: ko ? "ATANOR가 할 수 있는 것" : "what ATANOR may do", onClick: () => { setMenuOpen(false); setCapsOpen(true); } },
    { Icon: Command, name: ko ? "슬래시 명령어" : "Slash commands", desc: "/새대화 · /도움말", onClick: () => { setMenuOpen(false); setInput("/"); } },
  ];
  const pluginRows: MenuRow[] = menuPlugins.slice(0, 5).map((p) => ({
    Icon: PLUGIN_ICONS[p.icon] ?? Puzzle,
    name: p.name,
    desc: p.composer?.slash ?? "",
    onClick: () => { setMenuOpen(false); setInput((v) => (v ? v.trimEnd() + " " : "") + (p.composer?.slash ?? "") + " "); },
  }));
  const capabilities: { on: boolean; label: string; note: string }[] = [
    { on: true, label: ko ? "로컬 그래프 추론" : "Local graph reasoning", note: ko ? "외부 LLM 없음" : "no external LLM" },
    { on: true, label: ko ? "웹 검색 (SearXNG)" : "Web search (SearXNG)", note: ko ? "다양한 소스 · 무제한" : "diverse · unlimited" },
    { on: true, label: ko ? "이미지 읽기 (OCR)" : "Image read (OCR)", note: ko ? "한국어 · 영어" : "Korean · English" },
    { on: true, label: ko ? "영상 자막 읽기" : "Video transcript", note: "YouTube" },
    { on: true, label: ko ? "실시간 누적 학습" : "Continuous learning", note: ko ? "그래프 성장" : "graph grows" },
    { on: false, label: ko ? "개인 데이터 외부 전송" : "Send private data out", note: ko ? "차단됨" : "blocked" },
  ];

  const suggestions = ko
    ? ["정사각형 한 변이 7이면 둘레는?", "엔비디아 창립자가 누구야?", "y = x^2 + 1 그려줘", "광합성이 뭐야?"]
    : ["What is a black hole?", "Who founded Microsoft?", "What is 12 times 12?", "What is photosynthesis?"];

  return (
    <section className="atanor-demochat">
      <aside className="atanor-demochat-sessions">
        <button type="button" className="atanor-demochat-newchat" onClick={newChat}>
          <SquarePen size={16} strokeWidth={1.7} aria-hidden="true" />
          {ko ? "새 대화" : "New chat"}
        </button>
        <nav className="atanor-demochat-nav">
          <button type="button" className="atanor-demochat-navitem" data-active={galleryOpen} onClick={() => { setGalleryOpen(true); setCapsOpen(false); setMenuOpen(false); }}>
            <Puzzle size={17} strokeWidth={1.6} aria-hidden="true" />{ko ? "플러그인" : "Plugins"}
          </button>
          <button type="button" className="atanor-demochat-navitem" data-active={capsOpen} onClick={() => { setCapsOpen(true); setMenuOpen(false); }}>
            <SlidersHorizontal size={17} strokeWidth={1.6} aria-hidden="true" />{ko ? "사용자 지정" : "Customize"}
          </button>
          <button type="button" className="atanor-demochat-navitem" onClick={() => fileRef.current?.click()}>
            <FileText size={17} strokeWidth={1.6} aria-hidden="true" />{ko ? "파일 읽기" : "Read a file"}
          </button>
        </nav>
        <div className="atanor-demochat-recent-label">{ko ? "최근" : "Recent"}</div>
        <div className="atanor-demochat-session-list">
          {sessions.length === 0 ? (
            <p className="atanor-demochat-session-empty">{ko ? "대화 기록이 없습니다" : "No conversations yet"}</p>
          ) : (
            sessions.map((s) => (
              <div key={s.id} className="atanor-demochat-session-row" data-active={s.id === currentId}>
                <button
                  type="button"
                  className="atanor-demochat-session-item"
                  data-active={s.id === currentId}
                  onClick={() => openSession(s)}
                  title={s.title}
                >
                  {s.title}
                </button>
                <button
                  type="button"
                  className="atanor-demochat-session-del"
                  aria-label={ko ? "대화 삭제" : "Delete conversation"}
                  onClick={() => deleteSession(s.id)}
                >
                  <X size={12} strokeWidth={1.8} />
                </button>
              </div>
            ))
          )}
        </div>
      </aside>

      <div className="atanor-demochat-main">
        <PluginGallery
          open={galleryOpen}
          onClose={() => setGalleryOpen(false)}
          language={language}
          onUse={(p) => setInput((v) => (v ? v.trimEnd() + " " : "") + p.composer.slash + " ")}
        />
        <div className="atanor-demochat-thread" ref={scrollRef}>
          {messages.length === 0 ? (
            <div className="atanor-demochat-empty">
              {/* The AI is already alive and thinking before you ask anything — you
                  meet its living mind, then may interrupt it with a question. */}
              <LivingMindPanel />
              <p className="atanor-demochat-interrupt-hint">
                {ko ? "생각을 이어가는 중이에요 — 언제든 끼어들어 대화하세요." : "It's thinking — jump in anytime."}
              </p>
              <div className="atanor-demochat-suggest">
                {suggestions.map((s) => (
                  <button key={s} onClick={() => setInput(s)}>{s}</button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((m, i) => (
              <div key={i} className={`atanor-demochat-msg is-${m.role}`}>
                {m.role === "ai" ? <span className="atanor-demochat-orb" aria-hidden="true" /> : null}
                <div className="atanor-demochat-bubble">
                  {m.pending ? (
                    <>
                      <span className="atanor-demochat-typing"><i /><i /><i /></span>
                      {m.stage ? <span className="atanor-demochat-stage">{m.stage}…</span> : null}
                      {m.evidence?.length ? (
                        <div className="atanor-demochat-evidence">
                          {m.evidence.slice(0, 4).map((e, j) => (
                            <span key={j} className="atanor-demochat-evidence-chip">
                              {e.kind === "derivation" ? `🔒 ${String(e.value)}` : typeof e.value === "string" ? e.value : JSON.stringify(e.value).slice(0, 60)}
                            </span>
                          ))}
                        </div>
                      ) : null}
                    </>
                  ) : (
                    <>
                      <div className="atanor-demochat-text">{m.text}</div>
                      {m.error ? (
                        <div className="atanor-demochat-retry">
                          <button type="button" disabled={busy} onClick={() => runQuery(m.error!.retryQuery)}>
                            {ko ? "다시 시도" : "Retry"}
                          </button>
                        </div>
                      ) : null}
                      {m.visual ? <div className="atanor-demochat-visual"><AnswerExperimentSurface visual={m.visual} theme="light" /></div> : null}
                      {m.cert ? <div className="atanor-demochat-cert">🔒 {m.cert}</div> : null}
                      {hasDrawablePath(m.certFull) ? (
                        <div className="atanor-demochat-path">
                          <button
                            type="button"
                            className="atanor-demochat-path-toggle"
                            aria-expanded={openPaths.has(i)}
                            onClick={() =>
                              setOpenPaths((prev) => {
                                const next = new Set(prev);
                                if (next.has(i)) next.delete(i);
                                else next.add(i);
                                return next;
                              })
                            }
                          >
                            {openPaths.has(i) ? "▾ 근거 경로 접기" : "▸ 근거 경로 보기 (시맨틱 줌)"}
                          </button>
                          {openPaths.has(i) ? <AnswerPathScene cert={m.certFull as Record<string, unknown>} /> : null}
                        </div>
                      ) : null}
                      {m.role === "ai" && Array.isArray(m.followUps) && m.followUps.length ? (
                        <div className="atanor-demochat-followups">
                          <span className="atanor-demochat-followups-label">{ko ? "관련해서 더 물어보기" : "Ask a related question"}</span>
                          <div className="atanor-demochat-followups-chips">
                            {m.followUps.map((f) => (
                              <button key={f} type="button" disabled={busy} onClick={() => runQuery(f)}>{f}</button>
                            ))}
                          </div>
                        </div>
                      ) : null}
                    </>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
        <div className="atanor-demochat-composer-wrap" style={{ position: "relative" }}>
          <input ref={fileRef} type="file" accept="image/*" hidden onChange={onPickFile} />

          {menuOpen ? (
            <>
              <div className="atanor-cm-scrim" onClick={() => setMenuOpen(false)} />
              <div className="atanor-cm-menu" role="menu">
                <section className="atanor-cm-sec">
                  <div className="atanor-cm-section">{ko ? "추가" : "Add"}</div>
                  <div className="atanor-cm-items">
                    {addRows.map((it) => (
                      <button key={it.name} type="button" className="atanor-cm-item" onClick={it.onClick} role="menuitem">
                        <span className="atanor-cm-ico" aria-hidden="true"><it.Icon size={17} strokeWidth={1.6} /></span>
                        <span className="atanor-cm-row"><span className="atanor-cm-name">{it.name}</span><span className="atanor-cm-desc">{it.desc}</span></span>
                      </button>
                    ))}
                  </div>
                </section>
                <section className="atanor-cm-sec">
                  <div className="atanor-cm-section">{ko ? "플러그인" : "Plugins"}</div>
                  <div className="atanor-cm-items">
                    {pluginRows.map((it) => (
                      <button key={it.name} type="button" className="atanor-cm-item" onClick={it.onClick} role="menuitem">
                        <span className="atanor-cm-ico" aria-hidden="true"><it.Icon size={17} strokeWidth={1.6} /></span>
                        <span className="atanor-cm-row"><span className="atanor-cm-name">{it.name}</span><span className="atanor-cm-desc">{it.desc}</span></span>
                      </button>
                    ))}
                    <button type="button" className="atanor-cm-item" onClick={() => { setMenuOpen(false); setGalleryOpen(true); }} role="menuitem">
                      <span className="atanor-cm-ico" aria-hidden="true"><Puzzle size={17} strokeWidth={1.6} /></span>
                      <span className="atanor-cm-row"><span className="atanor-cm-name">{ko ? "모든 플러그인" : "All plugins"}</span><span className="atanor-cm-desc">{ko ? "전체 보기" : "browse all"}</span></span>
                    </button>
                  </div>
                </section>
                <section className="atanor-cm-sec">
                  <div className="atanor-cm-section">{ko ? "도구" : "Tools"}</div>
                  <div className="atanor-cm-items">
                    {toolRows.map((it) => (
                      <button key={it.name} type="button" className="atanor-cm-item" onClick={it.onClick} role="menuitem">
                        <span className="atanor-cm-ico" aria-hidden="true"><it.Icon size={17} strokeWidth={1.6} /></span>
                        <span className="atanor-cm-row"><span className="atanor-cm-name">{it.name}</span><span className="atanor-cm-desc">{it.desc}</span></span>
                      </button>
                    ))}
                  </div>
                </section>
              </div>
            </>
          ) : null}

          {capsOpen ? (
            <>
              <div className="atanor-cm-scrim" onClick={() => setCapsOpen(false)} />
              <div className="atanor-caps" role="dialog" aria-label={ko ? "권한 · 기능" : "Capabilities"}>
                <div className="atanor-caps-head"><span className="atanor-caps-title"><ShieldCheck size={16} strokeWidth={1.7} aria-hidden="true" />{ko ? "권한 · 기능" : "Permissions · capabilities"}</span><button type="button" onClick={() => setCapsOpen(false)} aria-label="close"><X size={15} strokeWidth={1.8} /></button></div>
                <ul className="atanor-caps-list">
                  {capabilities.map((c) => (
                    <li key={c.label} data-on={c.on}>
                      <span className="atanor-caps-dot" data-on={c.on} aria-hidden="true" />
                      <span className="atanor-caps-label">{c.label}</span>
                      <span className="atanor-caps-note">{c.note}</span>
                    </li>
                  ))}
                </ul>
                <div className="atanor-caps-foot">{ko ? "로컬 우선 · 출처를 갖춘 답변 · 추측 없음" : "Local-first · grounded · never guesses"}</div>
              </div>
            </>
          ) : null}

          <form className="atanor-demochat-composer" onSubmit={send}>
            <input
              className="atanor-demochat-cinput"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={ko ? "메시지를 입력하세요…" : "Message ATANOR…"}
              aria-label="message"
            />
            <div className="atanor-demochat-controls">
              <button
                type="button"
                className="atanor-demochat-plugins"
                data-open={menuOpen}
                onClick={() => { setMenuOpen((v) => !v); setCapsOpen(false); }}
                aria-label={ko ? "추가 · 도구" : "Add · tools"}
                aria-expanded={menuOpen}
                title={ko ? "파일 · 플러그인 · 권한" : "File · plugins · permissions"}
              >{attaching ? <Loader2 size={18} strokeWidth={1.8} className="atanor-spin" /> : <Plus size={19} strokeWidth={1.9} style={{ transform: menuOpen ? "rotate(45deg)" : "none", transition: "transform .14s" }} />}</button>
              <button
                type="button"
                className="atanor-demochat-mode"
                data-open={capsOpen}
                onClick={() => { setCapsOpen((v) => !v); setMenuOpen(false); }}
                aria-expanded={capsOpen}
                title={ko ? "권한 · 기능" : "Permissions · capabilities"}
              >
                <ShieldCheck size={14} strokeWidth={1.8} aria-hidden="true" />
                <span>{ko ? "로컬 우선" : "Local-first"}</span>
                <ChevronDown size={13} strokeWidth={1.8} aria-hidden="true" />
              </button>
              <span className="atanor-demochat-controls-spacer" />
              <button type="submit" className="atanor-demochat-send" disabled={busy || !input.trim()} aria-label="send">
                {busy ? <Loader2 size={17} strokeWidth={1.8} className="atanor-spin" /> : <ArrowUp size={17} strokeWidth={2} />}
              </button>
            </div>
          </form>
        </div>
        <div className="atanor-demochat-foot">{ko ? "로컬 엔진 · 외부 LLM 없음 · 모든 질문에 근거 기반 답변, 추측 없음" : "Local engine · no external LLM · grounded answers to everything, no guessing"}</div>
      </div>
    </section>
  );
}
