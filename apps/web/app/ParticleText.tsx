"use client";

import { useEffect, useRef } from "react";

type Tone = "speech" | "self";

type ParticleTextProps = {
  text: string;
  tone?: Tone;
  className?: string;
  speedMs?: number;
  maxLines?: number;
  "aria-live"?: "off" | "polite" | "assertive";
};

type TextParticle = {
  x: number;
  y: number;
  sx: number;
  sy: number;
  phase: number;
  alpha: number;
};

function segmentText(text: string) {
  if (typeof Intl !== "undefined" && "Segmenter" in Intl) {
    const Segmenter = (Intl as any).Segmenter;
    const segmenter = new Segmenter(undefined, { granularity: "grapheme" });
    return Array.from(segmenter.segment(text), (part: any) => String(part.segment));
  }
  return Array.from(text);
}

function wrapText(ctx: CanvasRenderingContext2D, text: string, maxWidth: number, maxLines: number) {
  const units = segmentText(text.replace(/\s+/g, " ").trim());
  const lines: string[] = [];
  let line = "";

  for (const unit of units) {
    const candidate = line + unit;
    if (line && ctx.measureText(candidate).width > maxWidth) {
      lines.push(line.trimEnd());
      line = unit.trimStart();
      if (lines.length >= maxLines) break;
    } else {
      line = candidate;
    }
  }

  if (lines.length < maxLines && line.trim()) lines.push(line.trim());
  return lines;
}

function buildParticles(text: string, width: number, height: number, tone: Tone, maxLines: number) {
  const canvas = document.createElement("canvas");
  const ratio = 2;
  canvas.width = Math.max(1, Math.floor(width * ratio));
  canvas.height = Math.max(1, Math.floor(height * ratio));
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  if (!ctx || !text.trim()) return [];

  const fontSize = tone === "self"
    ? Math.max(13, Math.min(19, width / 22))
    : Math.max(16, Math.min(25, width / 18));
  const lineHeight = fontSize * (tone === "self" ? 1.46 : 1.38);
  ctx.scale(ratio, ratio);
  ctx.clearRect(0, 0, width, height);
  ctx.font = `${tone === "self" ? 720 : 760} ${fontSize}px Helvetica, Arial, "Apple SD Gothic Neo", "Malgun Gothic", sans-serif`;
  ctx.textBaseline = "top";
  ctx.fillStyle = "white";

  const lines = wrapText(ctx, text, width - 8, maxLines);
  const totalHeight = lines.length * lineHeight;
  const top = Math.max(2, (height - totalHeight) / 2);
  lines.forEach((line, index) => {
    ctx.fillText(line, 4, top + index * lineHeight);
  });

  const image = ctx.getImageData(0, 0, canvas.width, canvas.height);
  const particles: TextParticle[] = [];
  const step = tone === "self" ? 4 : 3;
  const maxParticles = tone === "self" ? 1150 : 1800;
  for (let y = 0; y < canvas.height; y += step) {
    for (let x = 0; x < canvas.width; x += step) {
      const alpha = image.data[(y * canvas.width + x) * 4 + 3] / 255;
      if (alpha < 0.38) continue;
      const tx = x / ratio;
      const ty = y / ratio;
      const seed = Math.sin((x + 1) * 12.9898 + (y + 7) * 78.233) * 43758.5453;
      const phase = seed - Math.floor(seed);
      particles.push({
        x: tx,
        y: ty,
        sx: tx + (phase - 0.5) * width * 0.42,
        sy: ty + Math.sin(phase * Math.PI * 2) * height * 0.32,
        phase,
        alpha,
      });
      if (particles.length >= maxParticles) return particles;
    }
  }
  return particles;
}

export default function ParticleText({
  text,
  tone = "speech",
  className,
  speedMs = 24,
  maxLines = 3,
  "aria-live": ariaLive = "polite",
}: ParticleTextProps) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const visibleRef = useRef("");
  const particlesRef = useRef<TextParticle[]>([]);

  useEffect(() => {
    visibleRef.current = "";
    if (!text) {
      particlesRef.current = [];
      return undefined;
    }
    let index = 0;
    const timer = window.setInterval(() => {
      index += 1;
      visibleRef.current = text.slice(0, index);
      if (index >= text.length) window.clearInterval(timer);
    }, speedMs);
    return () => window.clearInterval(timer);
  }, [speedMs, text]);

  useEffect(() => {
    const host = hostRef.current;
    const canvas = canvasRef.current;
    if (!host || !canvas) return undefined;
    const ctx = canvas.getContext("2d");
    if (!ctx) return undefined;
    const activeHost = host;
    const activeCanvas = canvas;
    const activeCtx = ctx;

    let animationId = 0;
    let lastVisible = "";
    const startedAt = performance.now();

    function resizeAndRebuild() {
      const rect = activeHost.getBoundingClientRect();
      const ratio = Math.min(window.devicePixelRatio || 1, 1.7);
      const width = Math.max(120, Math.floor(rect.width));
      const height = Math.max(52, Math.floor(rect.height));
      const canvasWidth = Math.floor(width * ratio);
      const canvasHeight = Math.floor(height * ratio);
      if (activeCanvas.width !== canvasWidth || activeCanvas.height !== canvasHeight) {
        activeCanvas.width = canvasWidth;
        activeCanvas.height = canvasHeight;
        activeCanvas.style.width = `${width}px`;
        activeCanvas.style.height = `${height}px`;
      }
      particlesRef.current = buildParticles(visibleRef.current, width, height, tone, maxLines);
      lastVisible = visibleRef.current;
    }

    const observer = new ResizeObserver(resizeAndRebuild);
    observer.observe(activeHost);
    resizeAndRebuild();

    function render() {
      const rect = activeHost.getBoundingClientRect();
      const ratio = Math.min(window.devicePixelRatio || 1, 1.7);
      const width = Math.max(120, Math.floor(rect.width));
      const height = Math.max(52, Math.floor(rect.height));
      if (visibleRef.current !== lastVisible) {
        particlesRef.current = buildParticles(visibleRef.current, width, height, tone, maxLines);
        lastVisible = visibleRef.current;
      }

      activeCtx.setTransform(ratio, 0, 0, ratio, 0, 0);
      activeCtx.clearRect(0, 0, width, height);
      activeCtx.globalCompositeOperation = "lighter";
      const elapsed = (performance.now() - startedAt) / 1000;
      const color = tone === "self" ? [255, 136, 58] : [228, 250, 255];
      for (const particle of particlesRef.current) {
        const settle = Math.min(1, Math.max(0, (elapsed * 0.9 + particle.phase * 0.75) % 1.4));
        const ease = settle >= 1 ? 1 : settle * settle * (3 - 2 * settle);
        const wave = Math.sin(elapsed * 2.2 + particle.phase * 12.0) * (tone === "self" ? 1.5 : 1.9);
        const x = particle.sx + (particle.x - particle.sx) * ease + wave;
        const y = particle.sy + (particle.y - particle.sy) * ease + Math.cos(elapsed * 1.8 + particle.phase * 9.0) * 1.1;
        const alpha = particle.alpha * (tone === "self" ? 0.75 : 0.66);
        activeCtx.fillStyle = `rgba(${color[0]}, ${color[1]}, ${color[2]}, ${alpha})`;
        activeCtx.beginPath();
        activeCtx.arc(x, y, tone === "self" ? 1.05 : 1.2, 0, Math.PI * 2);
        activeCtx.fill();
      }
      activeCtx.globalCompositeOperation = "source-over";
      animationId = window.requestAnimationFrame(render);
    }

    render();
    return () => {
      observer.disconnect();
      window.cancelAnimationFrame(animationId);
    };
  }, [maxLines, tone]);

  return (
    <div ref={hostRef} className={className} data-particle-text-tone={tone}>
      <canvas ref={canvasRef} aria-hidden="true" />
      <span className="atanor-particle-text-accessible" aria-live={ariaLive}>{text}</span>
    </div>
  );
}
