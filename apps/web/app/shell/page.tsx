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
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const stateRef = useRef<ShellState>("idle");
  const [shellState, setShellState] = useState<ShellState>("idle");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const recRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const setState = (s: ShellState) => { stateRef.current = s; setShellState(s); };

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

  const ask = async (q: string) => {
    setQuestion(q);
    setAnswer("");
    setState("thinking");
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
      style={{ position: "fixed", inset: 0, background: "#000", color: "#fff",
               display: "grid", gridTemplateRows: "1fr auto", cursor: "pointer",
               fontFamily: '"Helvetica Neue", Helvetica, Arial, "Pretendard Variable", sans-serif' }}>
      <canvas ref={canvasRef} style={{ width: "100%", height: "100%" }} />
      <div style={{ position: "absolute", left: 0, right: 0, bottom: "8vh", textAlign: "center",
                    padding: "0 24px", pointerEvents: "none" }}>
        <div style={{ fontSize: 14, letterSpacing: ".08em", opacity: 0.55 }} data-state={shellState}>
          {statusLine[shellState]}
        </div>
        {question ? <div style={{ marginTop: 14, fontSize: 16, opacity: 0.75 }}>“{question}”</div> : null}
        {answer ? <div style={{ margin: "10px auto 0", maxWidth: 720, fontSize: 18, lineHeight: 1.5 }}>{answer}</div> : null}
        <div style={{ marginTop: 26, fontSize: 11, letterSpacing: ".06em", opacity: 0.3 }}>
          모든 음성과 답변은 이 기기 안에서 처리됩니다 · 근거가 없으면 정직하게 기권합니다 · v0는 행동 권한이 없습니다 (질문/답변 전용)
        </div>
      </div>
    </main>
  );
}
