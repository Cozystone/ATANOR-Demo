"use client";

import { useCallback, useRef, useState } from "react";

// SPLATRA 3D 스튜디오 — 대시보드에서 말/텍스트로 파티클 엔진을 부린다.
// 생성은 엔진(/api/splatra 프록시)으로, 몸짓·재질·깜빡임은 뷰어에 직접
// (postMessage) 명령한다. 감정 구동은 기계 자신의 캐릭터일 때만(/v1/embody).
const VIEWER = process.env.NEXT_PUBLIC_SPLATRA_BASE || "http://127.0.0.1:8010";

type Cmd =
  | { kind: "generate"; prompt: string }
  | { kind: "anim"; style: string }
  | { kind: "rig"; drive: number }
  | { kind: "stop" }
  | { kind: "reset" };

function parseIntent(raw: string): Cmd {
  const t = raw.trim().toLowerCase();
  if (/멈춰|정지|그만|stop/.test(t)) return { kind: "stop" };
  if (/원래대로|되돌려|리셋|reset|얼려|굳혀/.test(t)) return { kind: "reset" };
  if (/물처럼|녹여|녹아|액체|melt|water/.test(t)) return { kind: "anim", style: "water" };
  if (/흙처럼|모래|부서|가루|crumble|soil|sand/.test(t)) return { kind: "anim", style: "soil" };
  if (/흔들|움직여|춤|살아|animate|wiggle|dance/.test(t)) return { kind: "anim", style: "rig" };
  if (/걸어|걷게|walk/.test(t)) return { kind: "anim", style: "walk" };
  if (/손( )?흔들|인사|wave/.test(t)) return { kind: "anim", style: "handwave" };
  if (/돌려|회전|spin/.test(t)) return { kind: "anim", style: "spin" };
  if (/숨( )?쉬|breathe/.test(t)) return { kind: "anim", style: "breathe" };
  return { kind: "generate", prompt: raw.trim() };
}

export default function Studio3D() {
  const frame = useRef<HTMLIFrameElement>(null);
  const [busy, setBusy] = useState(false);
  const [log, setLog] = useState<string[]>([]);
  const [text, setText] = useState("");

  const say = (m: string) => setLog((l) => [...l.slice(-6), m]);
  const toViewer = (msg: object) =>
    frame.current?.contentWindow?.postMessage(msg, "*");

  const run = useCallback(async () => {
    const raw = text.trim();
    if (!raw || busy) return;
    setText("");
    const cmd = parseIntent(raw);
    if (cmd.kind === "stop") { toViewer({ splatra: "animate", style: "stop" }); say("⏸ 정지"); return; }
    if (cmd.kind === "reset") { toViewer({ splatra: "animate", style: "flow" }); say("↺ 복원"); return; }
    if (cmd.kind === "anim") { toViewer({ splatra: "animate", style: cmd.style }); say(`▶ ${cmd.style}`); return; }
    if (cmd.kind === "rig") { toViewer({ splatra: "animate", style: "rig" }); say("🦴 rig"); return; }
    setBusy(true);
    say(`⚒ 생성 중: ${cmd.prompt}`);
    try {
      const res = await fetch("/api/splatra/v1/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: cmd.prompt }),
      });
      const d = await res.json();
      if (res.ok) {
        say(`✓ ${d.narration || d.reply || "완료"}`.slice(0, 120));
        toViewer({ splatra: "reload" });
      } else say(`✕ ${d.error || d.detail || res.status}`);
    } catch { say("✕ 엔진 연결 실패 (:8010)"); }
    setBusy(false);
  }, [text, busy]);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", background: "#0a0a0c" }}>
      <iframe ref={frame} src={`${VIEWER}/studio`} title="SPLATRA studio"
        style={{ flex: 1, border: "none", width: "100%" }} />
      <div style={{ padding: "10px 14px", borderTop: "1px solid #222", display: "flex", gap: 10, alignItems: "center" }}>
        <input value={text} onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && run()}
          placeholder='말하듯 입력 — "파란 토러스 만들어줘", "흔들어봐", "물처럼 녹여", "원래대로"'
          style={{ flex: 1, background: "#141417", color: "#eee", border: "1px solid #2a2a2e",
                   borderRadius: 8, padding: "10px 12px", fontSize: 14, outline: "none" }} />
        <button onClick={run} disabled={busy}
          style={{ background: "#d2521f", color: "#fff", border: "none", borderRadius: 8,
                   padding: "10px 18px", fontSize: 14, cursor: "pointer", opacity: busy ? 0.5 : 1 }}>
          실행
        </button>
      </div>
      <div style={{ padding: "4px 14px 10px", color: "#9a9aa0", fontSize: 12, minHeight: 20 }}>
        {log.join("  ·  ")}
      </div>
    </div>
  );
}
