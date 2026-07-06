"use client";

import { useEffect, useRef, useState } from "react";

/* ATANOR OS particle shell v0 (roadmap ④) — the machine boots into this face.
   The Ultimate orb (dark particle shell + cyan/violet ribbons + white core) is
   the whole desktop; push-to-talk (Space or tap) → LOCAL Whisper transcription
   → the real graph engine answers → the OS's own local voice speaks it.
   HONESTY CONTRACT of this v0: it has NO action authority — question/answer
   only, said on-screen. OS actions arrive later BEHIND the approval gate.
   Orb motion is driven by the REAL pipeline state, never faked. */

type ShellState = "idle" | "listening" | "thinking" | "speaking" | "offline";

export default function ShellPage() {
  // overlay mode (?overlay=1): transparent background so the orb floats over the real
  // desktop as an always-on-top layer (the GNOME extension pins the window).
  const overlay = typeof window !== "undefined" && new URLSearchParams(window.location.search).get("overlay") === "1";
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const stateRef = useRef<ShellState>("idle");
  const [shellState, setShellState] = useState<ShellState>("idle");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const recRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  type Pending = { token: string; text: string; kind?: string };
  const [pending, setPendingState] = useState<Pending | null>(null);
  const pendingRef = useRef<Pending | null>(null);
  const setPending = (p: Pending | null) => { pendingRef.current = p; setPendingState(p); };
  const [tier, setTier] = useState<number>(1);
  const TIER_NAMES = ["관찰", "승인", "가드", "자율"];

  const setState = (s: ShellState) => { stateRef.current = s; setShellState(s); };

  useEffect(() => {
    fetch("/api/os-action/status").then((r) => r.json()).then((s) => { if (typeof s?.tier === "number") setTier(s.tier); }).catch(() => {});
  }, []);

  const changeTier = async (t: number) => {
    setTier(t);
    await fetch("/api/os-action/tier", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ tier: t }) }).catch(() => {});
  };

  const approveNow = async () => {
    if (!pendingRef.current) return;
    const r = await fetch("/api/os-action/approve", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ token: pendingRef.current.token }) }).then((x) => x.json()).catch(() => null);
    setPending(null);
    if (r) { setAnswer(`${r.detail || "실행했습니다."} ${r.stdout ? "— " + String(r.stdout).slice(0, 160) : ""}`.trim()); speak(r.detail || "실행했습니다."); }
  };
  const rejectNow = async () => {
    if (!pendingRef.current) return;
    await fetch("/api/os-action/reject", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ token: pendingRef.current.token }) }).catch(() => {});
    setPending(null); setAnswer("취소했습니다.");
  };

  useEffect(() => {
    const cv = canvasRef.current;
    if (!cv) return;
    const ctx = cv.getContext("2d");
    if (!ctx) return;
    let w = 0, h = 0, raf = 0, t = 0;
    const SHELL: { th: number; ph: number; tw: number }[] = [];
    const RIBBONS = [
      { a: 2, b: 3, c: 1, ph: 0.0, hue: "126,224,232" },
      { a: 3, b: 2, c: 2, ph: 1.7, hue: "176,127,232" },
      { a: 1, b: 4, c: 3, ph: 3.9, hue: "150,180,236" },
    ];
    const resize = () => {
      const dpr = Math.min(devicePixelRatio || 1, 2);
      w = cv.clientWidth; h = cv.clientHeight;
      cv.width = w * dpr; cv.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      SHELL.length = 0;
      for (let i = 0; i < 2100; i++) {
        SHELL.push({ th: Math.random() * 6.283, ph: Math.acos(2 * Math.random() - 1), tw: Math.random() * 6.283 });
      }
    };
    resize();
    addEventListener("resize", resize);
    const frame = () => {
      ctx.clearRect(0, 0, w, h);
      const st = stateRef.current;
      // real-state modulation: listening pulses the core, thinking spins faster,
      // speaking breathes — idle is calm. Nothing animates that is not happening.
      const spin = st === "thinking" ? 0.34 : st === "listening" ? 0.16 : 0.1;
      const breath = st === "speaking" ? 0.05 * Math.sin(t * 3.1) : 0.015 * Math.sin(t * 1.1);
      const R0 = Math.min(w, h) * 0.3 * (1 + breath);
      const cx = w / 2, cy = h / 2, rotY = t * spin;
      for (const p of SHELL) {
        const th = p.th + rotY;
        const x3 = Math.sin(p.ph) * Math.cos(th), y3 = Math.cos(p.ph), z3 = Math.sin(p.ph) * Math.sin(th);
        const depth = (z3 + 1) / 2;
        const a = (0.05 + depth * 0.16) * (0.75 + 0.25 * Math.sin(t * 1.6 + p.tw));
        ctx.beginPath();
        ctx.arc(cx + x3 * R0, cy + y3 * R0, 0.5 + depth * 0.7, 0, 6.2832);
        ctx.fillStyle = `rgba(205,214,226,${a})`;
        ctx.fill();
      }
      for (const rb of RIBBONS) {
        const N = 130, drift = t * (st === "thinking" ? 1.2 : 0.55) + rb.ph;
        for (let i = 0; i < N; i++) {
          const u = (i / N) * 6.283 + drift;
          const x3 = Math.sin(rb.a * u + rb.ph), y3 = Math.sin(rb.b * u), z3 = Math.cos(rb.c * u + rb.ph * 0.5);
          const thR = rotY * 0.6;
          const xr = x3 * Math.cos(thR) - z3 * Math.sin(thR), zr = x3 * Math.sin(thR) + z3 * Math.cos(thR);
          const r = R0 * 0.55, depth = (zr + 1) / 2, head = i / N;
          const a = (0.1 + depth * 0.5) * (0.3 + 0.7 * head * head);
          ctx.beginPath();
          ctx.arc(cx + xr * r, cy + y3 * r * 0.9, 0.8 + depth * 1.6 + head, 0, 6.2832);
          ctx.fillStyle = `rgba(${rb.hue},${a})`;
          ctx.fill();
        }
      }
      const corePulse = st === "listening" ? 0.34 + 0.06 * Math.sin(t * 6) : 0.34;
      const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, R0 * corePulse);
      g.addColorStop(0, "rgba(255,255,255,.92)");
      g.addColorStop(0.18, "rgba(240,246,255,.5)");
      g.addColorStop(0.5, "rgba(190,210,240,.1)");
      g.addColorStop(1, "rgba(190,210,240,0)");
      ctx.fillStyle = g;
      ctx.beginPath(); ctx.arc(cx, cy, R0 * corePulse, 0, 6.2832); ctx.fill();
      t += 0.016;
      raf = requestAnimationFrame(frame);
    };
    frame();
    return () => { cancelAnimationFrame(raf); removeEventListener("resize", resize); };
  }, []);

  const speak = (text: string) => {
    try {
      const u = new SpeechSynthesisUtterance(text);
      u.lang = /[가-힣]/.test(text) ? "ko-KR" : "en-US";
      u.onend = () => setState("idle");
      setState("speaking");
      speechSynthesis.speak(u);
    } catch { setState("idle"); }
  };

  const runOsResult = (r: any) => {
    if (r?.outcome === 0 && r?.executed) {              // EXECUTE — done
      const msg = `${r.detail || "실행했습니다."} ${r.stdout ? "— " + String(r.stdout).slice(0, 160) : ""}`.trim();
      setAnswer(msg); setPending(null); speak(r.detail || "실행했습니다.");
    } else if (r?.approval_token) {                      // NEEDS_APPROVAL — hold
      setPending({ token: r.approval_token, text: r.detail || "이 작업을 실행할까요?", kind: r.action?.kind });
      setAnswer(r.detail || "승인이 필요한 작업입니다."); speak(r.detail || "승인이 필요합니다. 실행할까요?");
      setState("idle");
    } else {                                             // BLOCKED
      setAnswer(r?.detail || "실행할 수 없습니다."); setPending(null); setState("idle");
    }
  };

  const ask = async (q: string) => {
    setQuestion(q);
    setAnswer("");
    setState("thinking");
    // voice approval: while an action is held, '응/네/그래/실행/yes' approves, '아니/취소/no' rejects.
    if (pendingRef.current) {
      if (/^(응|네|그래|좋아|실행|해줘|yes|ok|okay|approve)/i.test(q.trim())) {
        const r = await fetch("/api/os-action/approve", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ token: pendingRef.current.token }) }).then(x => x.json()).catch(() => null);
        setPending(null); if (r) runOsResult({ ...r, approval_token: undefined }); else setState("idle");
        return;
      }
      if (/^(아니|아뇨|취소|하지마|no|cancel|stop)/i.test(q.trim())) {
        await fetch("/api/os-action/reject", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ token: pendingRef.current.token }) }).catch(() => {});
        setPending(null); setAnswer("취소했습니다."); speak("취소했습니다."); setState("idle");
        return;
      }
    }
    // OS command first — the orb drives the desktop; a plain question falls through.
    try {
      const os = await fetch("/api/os-action/propose", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ text: q }) }).then(x => x.json()).catch(() => null);
      if (os && os.is_os_action) { runOsResult(os); return; }
    } catch { /* fall through to knowledge answer */ }
    try {
      const res = await fetch("/api/chat/atanor", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ question: q, language: /[가-힣]/.test(q) ? "ko" : "en",
                               audience_level: "beginner", mode: "default", brain_mode: "unified" }),
      });
      const body = await res.json();
      const text = String(body?.result?.answer ?? body?.answer ?? "").trim();
      if (text) { setAnswer(text); speak(text); }
      else { setAnswer("…"); setState("idle"); }
    } catch { setAnswer("엔진에 연결할 수 없습니다."); setState("offline"); }
  };

  const toggleTalk = async () => {
    if (stateRef.current === "listening") { recRef.current?.stop(); return; }
    if (stateRef.current !== "idle" && stateRef.current !== "offline") return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream, { mimeType: "audio/webm" });
      chunksRef.current = [];
      rec.ondataavailable = (e) => { if (e.data.size) chunksRef.current.push(e.data); };
      rec.onstop = async () => {
        stream.getTracks().forEach((tr) => tr.stop());
        setState("thinking");
        try {
          const fd = new FormData();
          fd.append("file", new Blob(chunksRef.current, { type: "audio/webm" }), "mic.webm");
          const res = await fetch("/api/voice/transcribe", { method: "POST", body: fd });
          const body = await res.json().catch(() => ({}));
          const text = String(body?.text ?? "").trim();
          if (res.ok && text) void ask(text);
          else setState(res.ok ? "idle" : "offline");
        } catch { setState("offline"); }
      };
      recRef.current = rec;
      rec.start();
      setState("listening");
    } catch { setState("offline"); }
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.code === "Space") { e.preventDefault(); void toggleTalk(); }
    };
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const statusLine: Record<ShellState, string> = {
    idle: "스페이스 또는 터치 — 말하세요",
    listening: "듣는 중… (다시 눌러 끝내기)",
    thinking: "그래프에서 근거를 찾는 중…",
    speaking: "답하는 중",
    offline: "로컬 엔진에 연결할 수 없습니다",
  };

  return (
    <main onClick={() => void toggleTalk()}
      style={{ position: "fixed", inset: 0, background: overlay ? "transparent" : "#000", color: "#fff",
               display: "grid", gridTemplateRows: "1fr auto", cursor: "pointer",
               fontFamily: '"Helvetica Neue", Helvetica, Arial, "Pretendard Variable", sans-serif' }}>
      <canvas ref={canvasRef} style={{ width: "100%", height: "100%" }} />

      {/* trust tier — the ONE dial for autonomy (관찰 → 승인 → 가드 → 자율) */}
      <div onClick={(e) => e.stopPropagation()}
        style={{ position: "absolute", top: 18, right: 18, display: "flex", gap: 6,
                 padding: 5, borderRadius: 999, border: "1px solid rgba(255,255,255,.14)",
                 background: "rgba(255,255,255,.04)" }}>
        {TIER_NAMES.map((name, i) => (
          <button key={i} onClick={() => void changeTier(i)}
            title={["관찰: 실행 안 함", "승인: 매 작업 확인", "가드: 되돌릴 수 있는 건 자동, 위험한 건 확인", "자율: 위험도 실행(전체 시스템만 재확인)"][i]}
            style={{ padding: "5px 12px", borderRadius: 999, border: "none", cursor: "pointer",
                     fontSize: 12, fontWeight: 700,
                     background: tier === i ? (i >= 3 ? "#ff5a3c" : "#ff8a00") : "transparent",
                     color: tier === i ? "#000" : "rgba(255,255,255,.55)" }}>
            {name}
          </button>
        ))}
      </div>

      <div style={{ position: "absolute", left: 0, right: 0, bottom: "8vh", textAlign: "center",
                    padding: "0 24px", pointerEvents: pending ? "auto" : "none" }}>
        <div style={{ fontSize: 14, letterSpacing: ".08em", opacity: 0.55 }} data-state={shellState}>
          {statusLine[shellState]}
        </div>
        {question ? <div style={{ marginTop: 14, fontSize: 16, opacity: 0.75 }}>“{question}”</div> : null}
        {answer ? <div style={{ margin: "10px auto 0", maxWidth: 720, fontSize: 18, lineHeight: 1.5 }}>{answer}</div> : null}

        {/* held action — approve by click OR by saying '응' */}
        {pending ? (
          <div onClick={(e) => e.stopPropagation()}
            style={{ margin: "18px auto 0", maxWidth: 520, padding: "16px 20px", borderRadius: 16,
                     border: "1px solid rgba(255,138,0,.4)", background: "rgba(255,138,0,.08)" }}>
            <div style={{ fontSize: 15, marginBottom: 12 }}>{pending.text}</div>
            <div style={{ display: "flex", gap: 10, justifyContent: "center" }}>
              <button onClick={() => void approveNow()}
                style={{ padding: "9px 22px", borderRadius: 10, border: "none", cursor: "pointer",
                         background: "#ff8a00", color: "#000", fontWeight: 700 }}>실행 (또는 "응")</button>
              <button onClick={() => void rejectNow()}
                style={{ padding: "9px 22px", borderRadius: 10, cursor: "pointer",
                         border: "1px solid rgba(255,255,255,.25)", background: "transparent", color: "#fff" }}>취소</button>
            </div>
          </div>
        ) : null}

        <div style={{ marginTop: 26, fontSize: 11, letterSpacing: ".06em", opacity: 0.3 }}>
          모든 처리는 이 기기 안에서 · 근거 없으면 정직하게 기권 · 모든 조작은 감사 기록에 남고 즉시 정지 가능
        </div>
      </div>
    </main>
  );
}
