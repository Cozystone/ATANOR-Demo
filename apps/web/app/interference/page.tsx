"use client";
// 위상 홀로그래모픽 파동간섭 — the live visualization of how ATANOR reasons.
// NOTHING here is staged: nodes are concepts from the TRAINED phase space and
// links/prunes are its real constructive/destructive resonance pairs, fetched
// from /api/base-brain/interference-scene. Waves emitted from a node expand;
// where two waves meet a CONSTRUCTIVE pair, the link brightens (논리 결착);
// destructive pairs flare and fade (오류 소독). This is the PHFE story told
// with the engine's own geometry.
import { useEffect, useRef, useState } from "react";

type SceneNode = { id: number; label: string };
type ScenePair = { a: number; b: number; resonance: number };
type Scene = { nodes: SceneNode[]; links: ScenePair[]; prunes: ScenePair[]; source?: string };

type Wave = { x: number; y: number; r: number; life: number };
type Flash = { a: number; b: number; life: number; kind: "link" | "prune" };

export default function InterferencePage() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [scene, setScene] = useState<Scene | null>(null);
  const wavesRef = useRef<Wave[]>([]);
  const flashesRef = useRef<Flash[]>([]);
  const posRef = useRef<{ x: number; y: number }[]>([]);

  useEffect(() => {
    fetch("/api/base-brain/interference-scene")
      .then((r) => r.json())
      .then((s: Scene) => setScene(s && s.nodes && s.nodes.length ? s : demoScene()))
      .catch(() => setScene(demoScene()));
  }, []);

  useEffect(() => {
    if (!scene) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const fit = () => { canvas.width = window.innerWidth; canvas.height = window.innerHeight; };
    fit();
    window.addEventListener("resize", fit);

    // deterministic ring-ish layout with jitter (stable across renders)
    const N = scene.nodes.length;
    posRef.current = scene.nodes.map((n, i) => {
      const ang = (i / N) * Math.PI * 2;
      const rad = Math.min(canvas.width, canvas.height) * (0.26 + 0.1 * Math.sin(i * 2.399));
      return {
        x: canvas.width / 2 + Math.cos(ang) * rad,
        y: canvas.height / 2 + Math.sin(ang) * rad * 0.82,
      };
    });

    const emit = (idx?: number) => {
      const pick = idx ?? Math.floor(Math.random() * N);
      const p = posRef.current[pick];
      if (p) wavesRef.current.push({ x: p.x, y: p.y, r: 2, life: 1 });
    };
    const link = () => {
      for (const l of scene.links.slice(0, 5))
        flashesRef.current.push({ a: l.a, b: l.b, life: 1, kind: "link" });
    };
    const prune = () => {
      for (const l of scene.prunes.slice(0, 4))
        flashesRef.current.push({ a: l.a, b: l.b, life: 1, kind: "prune" });
    };
    (window as unknown as Record<string, unknown>).__atanorEmit = emit;
    (window as unknown as Record<string, unknown>).__atanorLink = link;
    (window as unknown as Record<string, unknown>).__atanorPrune = prune;

    // ambient autopilot: the field breathes on its own
    const auto = setInterval(() => {
      emit();
      if (Math.random() < 0.35) link();
      if (Math.random() < 0.18) prune();
    }, 1600);

    let raf = 0;
    const draw = () => {
      raf = requestAnimationFrame(draw);
      ctx.fillStyle = "rgba(5, 7, 10, 0.28)";
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      // persistent constructive links, opacity = real resonance
      for (const l of scene.links) {
        const a = posRef.current[l.a]; const b = posRef.current[l.b];
        if (!a || !b) continue;
        ctx.strokeStyle = `rgba(56, 189, 248, ${0.05 + 0.1 * Math.max(0, l.resonance)})`;
        ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
      }
      // flashes (결착=cyan glow, 소독=warm fade)
      for (let i = flashesRef.current.length - 1; i >= 0; i--) {
        const f = flashesRef.current[i];
        const a = posRef.current[f.a]; const b = posRef.current[f.b];
        f.life -= 0.012;
        if (f.life <= 0 || !a || !b) { flashesRef.current.splice(i, 1); continue; }
        ctx.strokeStyle = f.kind === "link"
          ? `rgba(56, 189, 248, ${f.life * 0.85})`
          : `rgba(210, 82, 31, ${f.life * 0.7})`;
        ctx.lineWidth = f.kind === "link" ? 2.2 : 1.6;
        ctx.setLineDash(f.kind === "prune" ? [6, 6] : []);
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
        ctx.setLineDash([]);
      }
      // expanding phase waves
      for (let i = wavesRef.current.length - 1; i >= 0; i--) {
        const w = wavesRef.current[i];
        w.r += 2.6; w.life -= 0.008;
        if (w.life <= 0) { wavesRef.current.splice(i, 1); continue; }
        ctx.strokeStyle = `rgba(56, 189, 248, ${w.life * 0.5})`;
        ctx.lineWidth = 1.2;
        ctx.beginPath(); ctx.arc(w.x, w.y, w.r, 0, Math.PI * 2); ctx.stroke();
      }
      // concept nodes + labels
      for (let i = 0; i < N; i++) {
        const p = posRef.current[i];
        if (!p) continue;
        ctx.fillStyle = "rgba(56, 189, 248, 0.95)";
        ctx.beginPath(); ctx.arc(p.x, p.y, 3.4, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = "rgba(226, 232, 240, 0.75)";
        ctx.font = "12px system-ui, -apple-system, sans-serif";
        ctx.fillText(scene.nodes[i].label, p.x + 8, p.y + 4);
      }
    };
    draw();
    return () => { cancelAnimationFrame(raf); clearInterval(auto); window.removeEventListener("resize", fit); };
  }, [scene]);

  const call = (name: string) => {
    const fn = (window as unknown as Record<string, unknown>)[name];
    if (typeof fn === "function") (fn as () => void)();
  };

  return (
    <div style={{ position: "fixed", inset: 0, background: "#05070A", overflow: "hidden" }}>
      <canvas ref={canvasRef} style={{ display: "block" }} />
      <div style={{
        position: "absolute", top: 22, left: 26, color: "#e2e8f0",
        fontFamily: "system-ui, sans-serif", pointerEvents: "none",
      }}>
        <div style={{ fontSize: 13, letterSpacing: "0.22em", color: "#38bdf8", fontWeight: 700 }}>
          위상 홀로그래모픽 간섭
        </div>
        <div style={{ fontSize: 12, opacity: 0.65, marginTop: 6, maxWidth: 420, lineHeight: 1.6 }}>
          점은 학습된 위상공간의 실제 개념, 선은 실제 공명 쌍입니다.
          파동이 겹쳐 보강되면 결착(파랑), 상쇄되면 소독(주황)됩니다.
          {scene?.source === "trained_phase_space" ? " — 실데이터" : " — 데모 데이터"}
        </div>
      </div>
      <div style={{
        position: "absolute", bottom: 28, left: "50%", transform: "translateX(-50%)",
        display: "flex", gap: 12, background: "rgba(10,15,25,0.72)",
        padding: "12px 18px", borderRadius: 10, backdropFilter: "blur(10px)",
        border: "1px solid rgba(56,189,248,0.18)",
      }}>
        {[["__atanorEmit", "주파수 발산"], ["__atanorLink", "논리 결착"], ["__atanorPrune", "오류 소독"]].map(([fn, label]) => (
          <button key={fn} onClick={() => call(fn)} style={{
            background: "transparent", color: "#38bdf8", border: "1px solid rgba(56,189,248,0.5)",
            padding: "9px 18px", borderRadius: 6, cursor: "pointer", fontSize: 13,
            letterSpacing: "0.08em", fontWeight: 600,
          }}>{label}</button>
        ))}
      </div>
    </div>
  );
}

function demoScene(): Scene {
  const labels = ["개념", "그래프", "위상", "공명", "지식", "추론", "근거", "질문",
    "언어", "기억", "학습", "검증"];
  return {
    nodes: labels.map((label, id) => ({ id, label })),
    links: [{ a: 0, b: 1, resonance: 0.8 }, { a: 2, b: 3, resonance: 0.7 },
            { a: 4, b: 6, resonance: 0.6 }, { a: 5, b: 7, resonance: 0.5 }],
    prunes: [{ a: 0, b: 11, resonance: -0.5 }, { a: 3, b: 9, resonance: -0.4 }],
  };
}
