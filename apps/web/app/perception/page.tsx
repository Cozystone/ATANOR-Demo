"use client";
// 실시간 지각 스트림 v0 (Phase 4-5) — 후면 카메라 + 온디바이스 객체감지.
// 원칙: 프레임 비저장. 감지는 전부 이 페이지 안(WASM CNN)에서 일어나고,
// 서버로 가는 것은 라벨 문자열뿐이다(127.0.0.1). 본 것은 에피소드 타임라인에
// 기록되고, 물병 시나리오 프리미티브가 근거 있는 제안만 돌려준다.
import { useEffect, useRef, useState } from "react";

const MP_VER = "0.10.14";
const MP_URL = `https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@${MP_VER}`;
const MODEL_URL =
  "https://storage.googleapis.com/mediapipe-models/object_detector/efficientdet_lite0/float16/1/efficientdet_lite0.tflite";

// COCO 라벨 → 한국어 (표면 번역표 — 지식이 아니라 표기)
const KO: Record<string, string> = {
  person: "사람", bottle: "물병", cup: "컵", chair: "의자", laptop: "노트북",
  "cell phone": "휴대폰", book: "책", keyboard: "키보드", mouse: "마우스",
  tv: "TV", clock: "시계", scissors: "가위", backpack: "가방", umbrella: "우산",
  "potted plant": "화분", vase: "꽃병", "wine glass": "유리잔", bowl: "그릇",
  banana: "바나나", apple: "사과", orange: "오렌지", cat: "고양이", dog: "개",
};

type Sighting = { label: string; score: number; at: number };
type Suggestion = { object: string; age_days: number; suggestion: string };

export default function PerceptionPage() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [phase, setPhase] = useState<"boot" | "camera" | "model" | "live" | "denied" | "failed">("boot");
  const [sightings, setSightings] = useState<Sighting[]>([]);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [detail, setDetail] = useState("");

  useEffect(() => {
    let stop = false;
    let stream: MediaStream | null = null;
    let timer: ReturnType<typeof setInterval> | null = null;
    (async () => {
      // 1) camera (rear preferred; desktop falls back to any)
      setPhase("camera");
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: "environment" } }, audio: false,
        });
      } catch {
        setPhase("denied");
        return;
      }
      if (stop || !videoRef.current) return;
      videoRef.current.srcObject = stream;
      await videoRef.current.play().catch(() => {});

      // 2) on-device detector (WASM CNN via CDN — bundler-opaque dynamic import)
      setPhase("model");
      let detector: { detectForVideo: (v: HTMLVideoElement, t: number) => { detections: { categories: { categoryName: string; score: number }[] }[] } };
      try {
        const importUrl = new Function("u", "return import(u)");
        const vision = await importUrl(MP_URL);
        const fileset = await vision.FilesetResolver.forVisionTasks(`${MP_URL}/wasm`);
        detector = await vision.ObjectDetector.createFromOptions(fileset, {
          baseOptions: { modelAssetPath: MODEL_URL },
          scoreThreshold: 0.5,
          runningMode: "VIDEO",
        });
      } catch (e) {
        setDetail(String(e).slice(0, 140));
        setPhase("failed");
        return;
      }
      if (stop) return;
      setPhase("live");

      // 3) detect ~1.5s cadence; ONLY labels leave this page
      const seen = new Map<string, number>();
      timer = setInterval(async () => {
        const v = videoRef.current;
        if (!v || v.readyState < 2) return;
        let dets: { categories: { categoryName: string; score: number }[] }[] = [];
        try {
          dets = detector.detectForVideo(v, performance.now()).detections || [];
        } catch { return; }
        const now = Date.now();
        const fresh: Sighting[] = [];
        for (const d of dets) {
          const c = d.categories?.[0];
          if (!c || c.score < 0.5) continue;
          const label = KO[c.categoryName] || c.categoryName;
          if (now - (seen.get(label) || 0) < 30_000) continue; // page-side cooldown
          seen.set(label, now);
          fresh.push({ label, score: c.score, at: now });
        }
        if (!fresh.length) return;
        setSightings((prev) => [...fresh, ...prev].slice(0, 12));
        try {
          const r = await fetch("/api/perception/visual-ingest", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ detections: fresh.map((f) => ({ label: f.label, score: f.score })) }),
          });
          const out = await r.json();
          if (out?.suggestions?.length) {
            setSuggestions((prev) => {
              const known = new Set(prev.map((s) => s.object));
              return [...prev, ...out.suggestions.filter((s: Suggestion) => !known.has(s.object))].slice(-4);
            });
          }
        } catch { /* server offline: sightings stay page-local */ }
      }, 1500);
    })();
    return () => {
      stop = true;
      if (timer) clearInterval(timer);
      stream?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  const hudBox: React.CSSProperties = {
    background: "rgba(10,15,25,0.82)", padding: "14px 18px", borderRadius: 8,
    border: "1px solid rgba(56,189,248,0.25)", backdropFilter: "blur(10px)",
    fontFamily: "ui-monospace, monospace", fontSize: 13, color: "#e2e8f0",
  };

  return (
    <div style={{ position: "fixed", inset: 0, background: "#05070A", overflow: "hidden" }}>
      <video ref={videoRef} playsInline muted
             style={{ position: "absolute", inset: 0, width: "100%", height: "100%",
                      objectFit: "cover", opacity: phase === "live" ? 0.9 : 0.25 }} />
      <div style={{ position: "absolute", top: 20, left: 22, maxWidth: 360, ...hudBox }}>
        <div style={{ letterSpacing: "0.2em", color: "#38bdf8", fontWeight: 700, marginBottom: 8 }}>
          실시간 지각 스트림 v0
        </div>
        {phase === "camera" && <div style={{ opacity: 0.7 }}>카메라 권한을 기다리는 중…</div>}
        {phase === "model" && <div style={{ opacity: 0.7 }}>온디바이스 감지 모델을 여는 중… (프레임은 이 페이지 밖으로 나가지 않습니다)</div>}
        {phase === "denied" && <div style={{ opacity: 0.7 }}>카메라 권한이 없어 지각이 꺼져 있어요. 허용하면 이 기기 안에서만 감지합니다.</div>}
        {phase === "failed" && <div style={{ opacity: 0.7 }}>감지 모델을 불러오지 못했습니다 (네트워크/CDN). {detail}</div>}
        {phase === "live" && (
          <>
            <div style={{ opacity: 0.75, marginBottom: 6 }}>
              감지는 전부 기기 안(WASM)에서 — 서버로 가는 건 라벨뿐입니다.
            </div>
            <div style={{ opacity: 0.55, fontSize: 11 }}>
              본 것은 에피소드 타임라인에 기록되고, 근거가 쌓인 만큼만 제안이 옵니다.
            </div>
          </>
        )}
        {sightings.length > 0 && (
          <div style={{ marginTop: 10 }}>
            {sightings.slice(0, 6).map((s, i) => (
              <div key={i} style={{ display: "flex", justifyContent: "space-between", opacity: 0.85 }}>
                <span>{s.label}</span>
                <span style={{ color: "#38bdf8" }}>{(s.score * 100).toFixed(0)}%</span>
              </div>
            ))}
          </div>
        )}
      </div>
      {suggestions.map((s, i) => (
        <div key={s.object} style={{
          position: "absolute", bottom: 26 + i * 86, left: "50%", transform: "translateX(-50%)",
          maxWidth: 460, ...hudBox, border: "1px solid rgba(210,82,31,0.5)",
        }}>
          <div style={{ color: "#d2521f", fontWeight: 700, marginBottom: 4 }}>제안 — 기록에 근거함</div>
          <div>{s.suggestion}</div>
          <div style={{ opacity: 0.5, fontSize: 11, marginTop: 4 }}>근거: {s.object} 관련 기록 {s.age_days}일 전</div>
        </div>
      ))}
    </div>
  );
}
