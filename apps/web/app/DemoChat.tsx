"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import AnswerExperimentSurface, { AnswerVisual } from "./AnswerExperimentSurface";

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
  pending?: boolean;
};

type Session = { id: string; title: string; messages: Msg[]; ts: number };

const SESSIONS_KEY = "atanor.demo.sessions";

function loadSessions(): Session[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(SESSIONS_KEY);
    const parsed = raw ? (JSON.parse(raw) as Session[]) : [];
    return Array.isArray(parsed) ? parsed : [];
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

export default function DemoChat({ language }: { language: "ko" | "en" }) {
  const ko = language === "ko";
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentId, setCurrentId] = useState<string>(() => `s-${Date.now()}`);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setSessions(loadSessions());
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages.length, busy]);

  // Persist the active session (with at least one settled exchange) into history.
  useEffect(() => {
    const settled = messages.filter((m) => !m.pending);
    if (!settled.some((m) => m.role === "ai" && m.text.trim())) return;
    setSessions((prev) => {
      const others = prev.filter((s) => s.id !== currentId);
      const next: Session[] = [
        { id: currentId, title: sessionTitle(settled), messages: settled, ts: Date.now() },
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

  function newChat() {
    setMessages([]);
    setInput("");
    setCurrentId(`s-${Date.now()}`);
  }

  function openSession(session: Session) {
    setMessages(session.messages);
    setCurrentId(session.id);
    setInput("");
  }

  async function send(e: FormEvent) {
    e.preventDefault();
    const q = input.trim();
    if (!q || busy) return;
    setInput("");
    setBusy(true);
    const lang = /[가-힣]/.test(q) ? "ko" : "en";
    setMessages((m) => [...m, { role: "user", text: q }, { role: "ai", text: "", pending: true }]);
    try {
      const res = await fetch("/api/chat/atanor", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q, language: lang, web_search: true }),
      });
      const data = await res.json();
      const r = (data?.result ?? data) as Record<string, unknown>;
      const answer = String(r?.answer ?? "").trim() || "(응답 없음)";
      setMessages((m) => {
        const next = m.slice();
        next[next.length - 1] = {
          role: "ai",
          text: answer,
          visual: (r?.answer_visual as AnswerVisual | undefined) ?? null,
          cert: certSummary(r?.reasoning_certificate),
        };
        return next;
      });
    } catch {
      setMessages((m) => {
        const next = m.slice();
        next[next.length - 1] = { role: "ai", text: "연결 오류가 발생했어요. 잠시 후 다시 시도해 주세요." };
        return next;
      });
    } finally {
      setBusy(false);
    }
  }

  const suggestions = ko
    ? ["정사각형 한 변이 7이면 둘레는?", "엔비디아 창립자가 누구야?", "y = x^2 + 1 그려줘", "광합성이 뭐야?"]
    : ["What is a black hole?", "Who founded Microsoft?", "What is 12 times 12?", "What is photosynthesis?"];

  return (
    <section className="atanor-demochat">
      <aside className="atanor-demochat-sessions">
        <button type="button" className="atanor-demochat-newchat" onClick={newChat}>
          <span className="atanor-demochat-newchat-icon" aria-hidden="true">✎</span>
          {ko ? "새 대화" : "New chat"}
        </button>
        <div className="atanor-demochat-recent-label">{ko ? "최근" : "Recent"}</div>
        <div className="atanor-demochat-session-list">
          {sessions.length === 0 ? (
            <p className="atanor-demochat-session-empty">{ko ? "대화 기록이 없습니다" : "No conversations yet"}</p>
          ) : (
            sessions.map((s) => (
              <button
                key={s.id}
                type="button"
                className="atanor-demochat-session-item"
                data-active={s.id === currentId}
                onClick={() => openSession(s)}
                title={s.title}
              >
                {s.title}
              </button>
            ))
          )}
        </div>
      </aside>

      <div className="atanor-demochat-main">
        <div className="atanor-demochat-thread" ref={scrollRef}>
          {messages.length === 0 ? (
            <div className="atanor-demochat-empty">
              <span className="atanor-demochat-orb" aria-hidden="true" />
              <h1>{ko ? "무엇이든 물어보세요" : "Ask me anything"}</h1>
              <p>{ko ? "로컬 그래프 추론 엔진이 근거를 갖춰 답하고, 모르면 정직하게 보류합니다." : "A local graph-reasoning engine — grounded answers, honest abstention."}</p>
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
                    <span className="atanor-demochat-typing"><i /><i /><i /></span>
                  ) : (
                    <>
                      <div className="atanor-demochat-text">{m.text}</div>
                      {m.visual ? <div className="atanor-demochat-visual"><AnswerExperimentSurface visual={m.visual} theme="light" /></div> : null}
                      {m.cert ? <div className="atanor-demochat-cert">🔒 {m.cert}</div> : null}
                    </>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
        <form className="atanor-demochat-composer" onSubmit={send}>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={ko ? "메시지를 입력하세요…" : "Message ATANOR…"}
            aria-label="message"
          />
          <button type="submit" disabled={busy || !input.trim()} aria-label="send">{busy ? "…" : "↑"}</button>
        </form>
        <div className="atanor-demochat-foot">{ko ? "로컬 엔진 · 외부 LLM 없음 · 출처를 갖춘 답변, 불확실하면 보류" : "Local engine · no external LLM · grounded, abstains when unsure"}</div>
      </div>
    </section>
  );
}
