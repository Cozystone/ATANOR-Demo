"use client";

import { useEffect, useMemo, useRef, useState } from "react";

type Archetype =
  | "orb"
  | "tower"
  | "tree"
  | "creature"
  | "circuit"
  | "city_block"
  | "constellation"
  | "machine_core"
  | "abstract_memory_cloud";

type ImaginationMode = "product" | "lab";
type VisualState = "idle" | "listening" | "thinking" | "speaking" | "resting" | "approval_needed" | "blocked";

type Particle = {
  x: number;
  y: number;
  z: number;
  r: number;
  g: number;
  b: number;
  a: number;
  scale: number;
};

type ImaginationObject = {
  archetype?: Archetype;
  particles?: Particle[];
  metadata?: Record<string, any>;
};

type ImaginationFrame = {
  object?: ImaginationObject;
  objects?: ImaginationObject[];
  controls?: Record<string, any>;
  safety_flags?: Record<string, boolean>;
};

type Props = {
  mode?: ImaginationMode;
  state?: VisualState;
  particleBudget?: number;
  className?: string;
  interactive?: boolean;
  controlOverride?: Partial<{ valence: number; arousal: number; curiosity: number; speaking_energy: number; resting: boolean }>;
  onActivate?: () => void;
  onCancel?: () => void;
};

const ARCHETYPES: Archetype[] = [
  "orb",
  "tower",
  "tree",
  "creature",
  "circuit",
  "city_block",
  "constellation",
  "machine_core",
  "abstract_memory_cloud",
];

function normalizeFrame(payload: any): ImaginationFrame {
  const normalizeObject = (item: any): ImaginationObject => ({
    ...item,
    particles: Array.isArray(item?.particles)
      ? item.particles.map((particle: any) => ({
        x: Number(particle.x ?? 0),
        y: Number(particle.y ?? 0),
        z: Number(particle.z ?? 0),
        r: Number(particle.r ?? 0.5),
        g: Number(particle.g ?? 0.8),
        b: Number(particle.b ?? 1),
        a: Number(particle.a ?? 0.5),
        scale: Number(particle.scale ?? Math.max(0.6, Number(particle.radius ?? 0.01) * 120)),
      }))
      : [],
  });
  if (payload?.frame?.objects?.length) {
    return {
      object: normalizeObject(payload.frame.objects[0]),
      objects: payload.frame.objects.map(normalizeObject),
      controls: payload.frame.controls,
      safety_flags: payload.frame.safety_flags ?? payload.safety_flags,
    };
  }
  if (payload?.object) {
    return { ...payload, object: normalizeObject(payload.object) };
  }
  if (payload?.frame?.object) {
    return { ...payload.frame, object: normalizeObject(payload.frame.object) };
  }
  return payload?.frame ?? payload;
}

const STATE_CONTROLS: Record<VisualState, { valence: number; arousal: number; curiosity: number; speaking_energy: number; resting: boolean }> = {
  idle: { valence: 0.58, arousal: 0.34, curiosity: 0.45, speaking_energy: 0.0, resting: false },
  listening: { valence: 0.62, arousal: 0.48, curiosity: 0.7, speaking_energy: 0.08, resting: false },
  thinking: { valence: 0.5, arousal: 0.42, curiosity: 0.86, speaking_energy: 0.0, resting: false },
  speaking: { valence: 0.66, arousal: 0.72, curiosity: 0.56, speaking_energy: 0.88, resting: false },
  resting: { valence: 0.52, arousal: 0.14, curiosity: 0.28, speaking_energy: 0.0, resting: true },
  approval_needed: { valence: 0.48, arousal: 0.64, curiosity: 0.52, speaking_energy: 0.16, resting: false },
  blocked: { valence: 0.25, arousal: 0.55, curiosity: 0.4, speaking_energy: 0.0, resting: false },
};

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function seeded(index: number, salt = 0) {
  const value = Math.sin(index * 12.9898 + salt * 78.233) * 43758.5453123;
  return value - Math.floor(value);
}

function fallbackParticles(archetype: Archetype, count: number): Particle[] {
  return Array.from({ length: count }, (_, index) => {
    const t = (index + 0.5) / count;
    const theta = index * Math.PI * (3 - Math.sqrt(5));
    const y = 1 - 2 * t;
    const ring = Math.sqrt(Math.max(0, 1 - y * y));
    const r = archetype === "tower" ? 0.5 + t * 0.3 : archetype === "constellation" ? 1.55 + seeded(index) * 0.34 : 1.1;
    const x = Math.cos(theta) * ring * r;
    const z = Math.sin(theta) * ring * r;
    const ribbon = Math.sin(t * Math.PI * 8 + seeded(index, 4) * 3) * 0.22;
    const cyan = 0.58 + seeded(index, 2) * 0.34;
    const magenta = seeded(index, 3) > 0.62 ? 0.74 : 0.36;
    return {
      x: archetype === "circuit" ? (seeded(index, 6) - 0.5) * 2.4 : x + ribbon * 0.14,
      y: archetype === "tower" ? t * 2.8 - 1.4 : y + ribbon,
      z: archetype === "circuit" ? (seeded(index, 7) - 0.5) * 1.2 : z,
      r: archetype === "machine_core" ? 0.42 + magenta : 0.16 + magenta * 0.35,
      g: cyan,
      b: 1,
      a: 0.32 + seeded(index, 5) * 0.48,
      scale: 0.75 + seeded(index, 8) * 1.4,
    };
  });
}

function drawParticles(
  ctx: CanvasRenderingContext2D,
  particles: Particle[],
  width: number,
  height: number,
  elapsed: number,
  controls: { arousal: number; curiosity: number; speaking_energy: number; resting: boolean },
  ambient = false,
) {
  ctx.clearRect(0, 0, width, height);
  const cx = width / 2;
  const cy = height / 2;
  const scale = Math.min(width, height) * (ambient ? 0.18 : 0.26);
  const rotation = elapsed * (controls.resting ? 0.08 : 0.18 + controls.arousal * 0.16);
  const tilt = Math.sin(elapsed * 0.21) * 0.18;
  const pulse = 1 + Math.sin(elapsed * 3.6) * controls.speaking_energy * 0.045;
  const cosY = Math.cos(rotation);
  const sinY = Math.sin(rotation);
  const cosX = Math.cos(tilt);
  const sinX = Math.sin(tilt);

  for (const point of particles) {
    let x = point.x;
    let y = point.y;
    let z = point.z;
    const rx = x * cosY - z * sinY;
    const rz = x * sinY + z * cosY;
    x = rx;
    z = rz;
    const ry = y * cosX - z * sinX;
    z = y * sinX + z * cosX;
    y = ry;
    const depth = clamp((z + 2.4) / 4.8, 0.08, 1);
    let px = cx + x * scale * pulse;
    let py = cy + y * scale * pulse;
    let size = clamp(point.scale * (0.82 + depth * 1.35), 0.8, 4.8);
    let alpha = clamp(point.a * (0.22 + depth * 0.82), 0.08, 0.86);

    if (ambient) {
      const homeX = seeded(point.x * 1000 + point.y * 911, 22) * width;
      const homeY = seeded(point.z * 1000 + point.x * 677, 23) * height;
      const edgeBias = Math.abs(homeX - cx) / Math.max(1, width / 2);
      const verticalBias = Math.abs(homeY - cy) / Math.max(1, height / 2);
      const recombineWave = (Math.sin(elapsed * 0.18) + 1) * 0.5;
      const recombine = controls.resting ? 0.08 : 0.14 + controls.curiosity * 0.16 + controls.speaking_energy * 0.16 + recombineWave * 0.08;
      const orbitX = cx + x * scale * 2.6;
      const orbitY = cy + y * scale * 1.9;
      const drift = Math.sin(elapsed * 0.23 + homeX * 0.002 + homeY * 0.003) * 18;
      px = homeX * (1 - recombine) + orbitX * recombine + drift;
      py = homeY * (1 - recombine) + orbitY * recombine + Math.cos(elapsed * 0.17 + homeX * 0.002) * 12;
      size = clamp(point.scale * (0.42 + depth * 0.74 + controls.speaking_energy * 0.24), 0.45, 2.2);
      alpha = clamp(point.a * (0.14 + depth * 0.44) * (0.74 + edgeBias * 0.22 + verticalBias * 0.12), 0.035, 0.48);
      const centerDistance = Math.hypot(px - cx, py - cy);
      const bodyClearRadius = Math.min(width, height) * 0.34;
      const bodyFeather = Math.min(width, height) * 0.16;
      const clearance = clamp((centerDistance - bodyClearRadius) / bodyFeather, 0.05, 1);
      alpha *= clearance;
      if (clearance < 0.08) size *= 0.62;
    }

    ctx.fillStyle = `rgba(${Math.floor(point.r * 255)}, ${Math.floor(point.g * 255)}, ${Math.floor(point.b * 255)}, ${alpha})`;
    ctx.beginPath();
    ctx.arc(px, py, size, 0, Math.PI * 2);
    ctx.fill();
  }

  if (ambient) {
    const fieldGlow = ctx.createRadialGradient(cx, cy, 0, cx, cy, Math.max(width, height) * 0.68);
    fieldGlow.addColorStop(0, "rgba(255,255,255,0.012)");
    fieldGlow.addColorStop(0.42, "rgba(30,228,255,0.022)");
    fieldGlow.addColorStop(1, "rgba(0,0,0,0)");
    ctx.fillStyle = fieldGlow;
    ctx.fillRect(0, 0, width, height);
    return;
  }

  const shellRadius = Math.min(width, height) * (0.215 + controls.speaking_energy * 0.012);
  const glow = ctx.createRadialGradient(cx, cy, shellRadius * 0.2, cx, cy, shellRadius * 1.35);
  glow.addColorStop(0, "rgba(255,255,255,0.18)");
  glow.addColorStop(0.42, "rgba(44,231,255,0.055)");
  glow.addColorStop(1, "rgba(0,0,0,0)");
  ctx.fillStyle = glow;
  ctx.beginPath();
  ctx.arc(cx, cy, shellRadius * 1.35, 0, Math.PI * 2);
  ctx.fill();
  ctx.strokeStyle = "rgba(128,226,255,0.2)";
  ctx.lineWidth = Math.max(1, Math.min(width, height) * 0.0018);
  ctx.beginPath();
  ctx.arc(cx, cy, shellRadius, 0, Math.PI * 2);
  ctx.stroke();
}

export default function SplatraImaginationField({
  mode = "product",
  state = "idle",
  particleBudget,
  className,
  interactive = true,
  controlOverride,
  onActivate,
  onCancel,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [archetype, setArchetype] = useState<Archetype>("orb");
  const [frame, setFrame] = useState<ImaginationFrame | null>(null);
  const [status, setStatus] = useState<Record<string, any> | null>(null);
  const [error, setError] = useState("");
  const [reducedMotion, setReducedMotion] = useState(false);
  const budget = particleBudget ?? (mode === "lab" ? 1400 : 520);
  const controls = useMemo(() => {
    const base = STATE_CONTROLS[state] ?? STATE_CONTROLS.idle;
    if (!controlOverride) return base;
    return {
      ...base,
      ...Object.fromEntries(
        Object.entries(controlOverride).filter(([, value]) => value !== undefined && value !== null),
      ),
    };
  }, [controlOverride, state]);
  const particles = frame?.object?.particles?.length ? frame.object.particles : fallbackParticles(archetype, budget);
  const activeArchetype = frame?.object?.archetype ?? archetype;

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReducedMotion(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    fetch("/api/agentic-os/splatra/imagination/status", { cache: "no-store" })
      .then((response) => response.json())
      .then(setStatus)
      .catch(() => setStatus({ available: false }));
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function load(nextArchetype: Archetype) {
      try {
        const response = await fetch("/api/agentic-os/splatra/imagination/generate", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            archetype: nextArchetype,
            state,
            particle_budget: budget,
            include_particles: true,
            ...controls,
          }),
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const payload = await response.json();
        if (!cancelled) {
          setFrame(normalizeFrame(payload));
          setError("");
        }
      } catch (loadError) {
        if (!cancelled) setError(String(loadError));
      }
    }
    load(archetype);
    return () => {
      cancelled = true;
    };
  }, [archetype, budget, controls, state]);

  useEffect(() => {
    if (mode !== "product" || reducedMotion) return undefined;
    const timer = window.setInterval(() => {
      setArchetype((current) => {
        const index = ARCHETYPES.indexOf(current);
        return ARCHETYPES[(index + 1) % ARCHETYPES.length];
      });
    }, 6800);
    return () => window.clearInterval(timer);
  }, [mode, reducedMotion]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;
    const ctx = canvas.getContext("2d");
    if (!ctx) return undefined;
    let animationId = 0;
    const startedAt = performance.now();
    const render = () => {
      const rect = canvas.getBoundingClientRect();
      const ratio = Math.min(window.devicePixelRatio || 1, mode === "lab" ? 1.6 : 1.25);
      const width = Math.max(280, Math.floor(rect.width * ratio));
      const height = Math.max(260, Math.floor(rect.height * ratio));
      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width;
        canvas.height = height;
      }
      drawParticles(
        ctx,
        particles,
        width,
        height,
        reducedMotion ? 0.5 : (performance.now() - startedAt) / 1000,
        controls,
        !interactive && mode === "product",
      );
      if (!reducedMotion) animationId = window.requestAnimationFrame(render);
    };
    render();
    return () => window.cancelAnimationFrame(animationId);
  }, [controls, mode, particles, reducedMotion]);

  function handleClick() {
    if (state === "listening") {
      onCancel?.();
    } else {
      onActivate?.();
    }
  }

  const canvas = <canvas ref={canvasRef} />;

  return (
    <section className={`splatra-imagination-field ${className ?? ""}`} data-mode={mode} data-state={state}>
      {interactive ? (
        <button
          type="button"
          className="splatra-imagination-canvas-button"
          aria-label="SPLATRA procedural imagination field"
          onClick={handleClick}
        >
          {canvas}
        </button>
      ) : (
        <div className="splatra-imagination-canvas-button" aria-hidden="true">
          {canvas}
        </div>
      )}
      {mode === "lab" ? (
        <div className="splatra-imagination-lab">
          <div>
            <small>SPLATRA Imagination Field</small>
            <strong>{activeArchetype}</strong>
            <span>{status?.proof_only === false ? "blocked" : "proof-only"} / verified knowledge={String(status?.is_verified_knowledge ?? false)}</span>
          </div>
          <label>
            <span>archetype</span>
            <select value={archetype} onChange={(event) => setArchetype(event.target.value as Archetype)}>
              {ARCHETYPES.map((name) => <option key={name} value={name}>{name}</option>)}
            </select>
          </label>
          <div className="splatra-imagination-flags">
            <span>particles={particles.length}</span>
            <span>compression={frame?.object?.metadata?.turbovec?.compressed_ref?.compression_ratio?.toFixed?.(2) ?? "-"}</span>
            <span>lod={frame?.object?.metadata?.turbovec?.lod_summary?.levels?.join?.("/") ?? "-"}</span>
            <span>error={error ? "fallback" : "none"}</span>
          </div>
        </div>
      ) : null}
    </section>
  );
}
