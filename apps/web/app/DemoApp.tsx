"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import AnswerExperimentSurface, { AnswerVisual } from "./AnswerExperimentSurface";

/**
 * ATANOR demo surface — a GPT/Gemini/Claude-style chat over the SAME engine
 * (/api/chat/atanor). White theme, left conversation rail + right chat. No
 * central orb / particles / 3D — just a small orb avatar on each AI answer.
 * The 7 product panels live in the rail's lower nav.
 */

type Msg = {
  role: "user" | "ai";
  text: string;
  visual?: AnswerVisual | null;
  kind?: string;
  cert?: string | null;
  pending?: boolean;
};

type Conversation = { id: string; title: string; messages: Msg[] };

const PANELS = [
  "로컬 브레인",
  "클라우드 브레인",
  "아틀라스",
  "AGORA",
  "Graph Hub",
  "브레인 링크",
  "설정",
];

function newConversation(): Conversation {
  return { id: Math.random().toString(36).slice(2), title: "새 대화", messages: [] };
}

function certSummary(cert: unknown): string | null {
  if (!cert || typeof cert !== "object") return null;
  const c = cert as Record<string, unknown>;
  const kind = String(c.derivation_kind || "");
  const map: Record<string, string> = {
    deterministic_arithmetic: "결정론적 계산 (외부 LLM 없음)",
    deterministic_word_problem: "단계별 추론 (외부 LLM 없음)",
    deterministic_geometry: "도형 공식 (외부 LLM 없음)",
    deterministic_exponent: "거듭제곱 계산 (외부 LLM 없음)",
    deterministic_function_plot: "함수 샘플링 (외부 LLM 없음)",
    web_attribution_extraction: "웹 근거에서 인물 추출 · 출처 표기",
    web_search_grounding: "웹 근거 기반 · 출처 표기",
    web_no_relevant_source: "관련 근거 없음 → 정직하게 보류",
    web_unreachable: "웹 확인 불가 → 보류",
  };
  return map[kind] || (kind ? kind.replace(/_/g, " ") : null);
}

function OrbAvatar() {
  // Lightweight CSS orb (no WebGL): the particle orb's identity as a profile dot.
  return <span className="atanor-demo-orb" aria-hidden="true" />;
}

export default function DemoApp() {
  const [conversations, setConversations] = useState<Conversation[]>([newConversation()]);
  const [activeId, setActiveId] = useState<string>(() => conversations[0].id);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const active = conversations.find((c) => c.id === activeId) ?? conversations[0];

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [active?.messages.length, busy]);

  function patchActive(fn: (c: Conversation) => Conversation) {
    setConversations((prev) => prev.map((c) => (c.id === activeId ? fn(c) : c)));
  }

  async function send(e: FormEvent) {
    e.preventDefault();
    const q = input.trim();
    if (!q || busy) return;
    setInput("");
    setBusy(true);
    const lang = /[가-힣]/.test(q) ? "ko" : "en";
    patchActive((c) => ({
      ...c,
      title: c.messages.length === 0 ? q.slice(0, 40) : c.title,
      messages: [...c.messages, { role: "user", text: q }, { role: "ai", text: "", pending: true }],
    }));
    try {
      const res = await fetch("/api/chat/atanor", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q, language: lang, web_search: true }),
      });
      const data = await res.json();
      const r = (data?.result ?? data) as Record<string, unknown>;
      const answer = String(r?.answer ?? "").trim() || "(응답 없음)";
      patchActive((c) => {
        const msgs = c.messages.slice();
        msgs[msgs.length - 1] = {
          role: "ai",
          text: answer,
          visual: (r?.answer_visual as AnswerVisual | undefined) ?? null,
          kind: String(r?.answer_kind ?? ""),
          cert: certSummary(r?.reasoning_certificate),
        };
        return { ...c, messages: msgs };
      });
    } catch {
      patchActive((c) => {
        const msgs = c.messages.slice();
        msgs[msgs.length - 1] = { role: "ai", text: "연결 오류가 발생했어요. 잠시 후 다시 시도해 주세요." };
        return { ...c, messages: msgs };
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="atanor-demo">
      <aside className="atanor-demo-rail">
        <div className="atanor-demo-brand">
          <OrbAvatar />
          <strong>ATANOR</strong>
          <span className="atanor-demo-badge">demo</span>
        </div>
        <button
          className="atanor-demo-new"
          onClick={() => {
            const c = newConversation();
            setConversations((prev) => [c, ...prev]);
            setActiveId(c.id);
          }}
        >
          + 새 대화
        </button>
        <div className="atanor-demo-history">
          {conversations.map((c) => (
            <button
              key={c.id}
              className={`atanor-demo-history-item${c.id === activeId ? " is-active" : ""}`}
              onClick={() => setActiveId(c.id)}
              title={c.title}
            >
              {c.title || "새 대화"}
            </button>
          ))}
        </div>
        <nav className="atanor-demo-panels">
          {PANELS.map((p) => (
            <button key={p} className="atanor-demo-panel" title={`${p} (준비 중)`} disabled>
              {p}
            </button>
          ))}
        </nav>
      </aside>

      <main className="atanor-demo-main">
        <div className="atanor-demo-thread" ref={scrollRef}>
          {active.messages.length === 0 ? (
            <div className="atanor-demo-empty">
              <OrbAvatar />
              <h1>무엇이든 물어보세요</h1>
              <p>로컬 그래프 추론 엔진이 근거를 갖춰 답하고, 모르면 정직하게 보류합니다.</p>
              <div className="atanor-demo-suggest">
                {["정사각형 한 변이 7이면 둘레는?", "엔비디아 창립자가 누구야?", "y = x^2 + 1 그려줘", "광합성이 뭐야?"].map((s) => (
                  <button key={s} onClick={() => setInput(s)}>{s}</button>
                ))}
              </div>
            </div>
          ) : (
            active.messages.map((m, i) => (
              <div key={i} className={`atanor-demo-msg is-${m.role}`}>
                {m.role === "ai" ? <OrbAvatar /> : null}
                <div className="atanor-demo-bubble">
                  {m.pending ? (
                    <span className="atanor-demo-typing"><i /><i /><i /></span>
                  ) : (
                    <>
                      <div className="atanor-demo-text">{m.text}</div>
                      {m.visual ? (
                        <div className="atanor-demo-visual">
                          <AnswerExperimentSurface visual={m.visual} />
                        </div>
                      ) : null}
                      {m.cert ? <div className="atanor-demo-cert">🔒 {m.cert}</div> : null}
                    </>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
        <form className="atanor-demo-composer" onSubmit={send}>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="메시지를 입력하세요…"
            aria-label="메시지 입력"
          />
          <button type="submit" disabled={busy || !input.trim()} aria-label="보내기">
            {busy ? "…" : "↑"}
          </button>
        </form>
        <div className="atanor-demo-foot">로컬 엔진 · 외부 LLM 없음 · 출처를 갖춘 답변, 불확실하면 보류</div>
      </main>
    </div>
  );
}
