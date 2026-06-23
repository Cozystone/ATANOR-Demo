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
  controlOverride?: Partial<{
    valence: number;
    arousal: number;
    curiosity: number;
    speaking_energy: number;
    resting: boolean;
    fatigue: number;
    review_pressure: number;
    novelty_found: number;
  }>;
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
const PRODUCT_ARCHETYPES: Archetype[] = [
  "constellation",
  "city_block",
  "circuit",
  "tree",
  "machine_core",
  "tower",
  "abstract_memory_cloud",
  "creature",
];
const ARCHETYPE_LABELS: Record<Archetype, string> = {
  orb: "orb",
  tower: "tower",
  tree: "tree",
  creature: "creature",
  circuit: "circuit",
  city_block: "city block",
  constellation: "constellation",
  machine_core: "machine core",
  abstract_memory_cloud: "memory cloud",
};

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
  const palette = (index: number, warm = 0.32) => ({
    r: 0.1 + warm * 0.75 + seeded(index, 3) * 0.16,
    g: 0.66 + seeded(index, 2) * 0.28,
    b: 0.92 + seeded(index, 4) * 0.08,
    a: 0.45 + seeded(index, 5) * 0.5,
    scale: 0.72 + seeded(index, 8) * 1.35,
  });
  return Array.from({ length: count }, (_, index) => {
    const t = (index + 0.5) / count;
    let x = 0;
    let y = 0;
    let z = 0;
    let warm = 0.28;
    let scaleBoost = 1;
    if (archetype === "city_block") {
      const cols = 9;
      const col = index % cols;
      const row = Math.floor(index / cols);
      const height = 0.38 + seeded(col, 71) * 1.12;
      x = -1.35 + (col / (cols - 1)) * 2.7 + (seeded(index, 17) - 0.5) * 0.08;
      y = -1.15 + seeded(row, col) * height * 1.75;
      z = -0.55 + seeded(col, 19) * 1.1;
      warm = seeded(index, 28) > 0.74 ? 0.8 : 0.24;
      scaleBoost = index % 17 === 0 ? 1.5 : 0.82;
    } else if (archetype === "circuit") {
      const lane = index % 12;
      const step = Math.floor(index / 12);
      const horizontal = lane % 2 === 0;
      const coord = -1.38 + (lane / 11) * 2.76;
      const progress = (step % 90) / 89;
      x = horizontal ? -1.55 + progress * 3.1 : coord;
      y = horizontal ? coord : -1.35 + progress * 2.7;
      z = Math.sin(progress * Math.PI * 2 + lane) * 0.15;
      warm = index % 37 === 0 ? 0.8 : 0.18;
      scaleBoost = index % 37 === 0 ? 2.3 : 0.62;
    } else if (archetype === "tree") {
      if (index < count * 0.22) {
        const trunkT = index / Math.max(1, count * 0.22);
        x = (seeded(index, 31) - 0.5) * (0.12 + trunkT * 0.08);
        y = -1.35 + trunkT * 1.35;
        z = (seeded(index, 32) - 0.5) * 0.24;
        warm = 0.1;
        scaleBoost = 1.0;
      } else {
        const canopyT = (index - count * 0.22) / Math.max(1, count * 0.78);
        const theta = index * Math.PI * (3 - Math.sqrt(5));
        const radius = (0.15 + seeded(index, 33) * 1.05) * (1 - canopyT * 0.22);
        x = Math.cos(theta) * radius * 0.78;
        y = -0.05 + seeded(index, 34) * 1.38;
        z = Math.sin(theta) * radius * 0.58;
        warm = 0.2 + seeded(index, 35) * 0.28;
        scaleBoost = 1.18;
      }
    } else if (archetype === "tower") {
      const floors = 26;
      const floor = index % floors;
      const side = Math.floor(index / floors) % 4;
      const floorT = floor / (floors - 1);
      const width = 0.23 + floorT * 0.22;
      y = -1.45 + floorT * 2.9;
      x = side === 0 ? -width : side === 1 ? width : (seeded(index, 41) - 0.5) * width * 2;
      z = side === 2 ? -width : side === 3 ? width : (seeded(index, 42) - 0.5) * width * 2;
      warm = floor % 5 === 0 ? 0.72 : 0.24;
      scaleBoost = 0.82;
    } else if (archetype === "machine_core") {
      const ring = index % 6;
      const theta = t * Math.PI * 2 * (9 + ring * 0.6);
      const radius = 0.28 + ring * 0.18 + Math.sin(theta * 2.4) * 0.025;
      x = Math.cos(theta) * radius;
      y = Math.sin(theta * (1.0 + ring * 0.08)) * 0.24;
      z = Math.sin(theta) * radius;
      warm = ring % 2 ? 0.72 : 0.22;
      scaleBoost = ring === 0 ? 1.55 : 0.96;
    } else if (archetype === "constellation") {
      const anchor = index % 18;
      const theta = anchor * 2.399963 + seeded(anchor, 51);
      const baseR = 0.35 + seeded(anchor, 52) * 1.45;
      const star = index % 13 === 0;
      const drift = seeded(index, 53) * 0.18;
      x = Math.cos(theta) * baseR + (seeded(index, 54) - 0.5) * drift;
      y = Math.sin(theta * 0.72) * (0.35 + seeded(anchor, 55) * 0.9) + (seeded(index, 56) - 0.5) * drift;
      z = Math.sin(theta) * baseR * 0.42;
      warm = star ? 0.72 : 0.24;
      scaleBoost = star ? 2.8 : 0.46;
    } else if (archetype === "creature") {
      const centers = [[-0.24, 0.05, 0], [0.26, 0.02, 0], [0, 0.58, 0], [-0.58, -0.38, 0], [0.58, -0.38, 0]];
      const center = centers[index % centers.length];
      const spread = index % centers.length === 2 ? 0.16 : 0.22;
      const theta = seeded(index, 61) * Math.PI * 2;
      const dist = Math.sqrt(seeded(index, 62)) * spread;
      x = center[0] + Math.cos(theta) * dist;
      y = center[1] + (seeded(index, 63) - 0.5) * spread;
      z = center[2] + Math.sin(theta) * dist * 0.68;
      warm = 0.36 + seeded(index, 64) * 0.34;
      scaleBoost = 1.2;
    } else if (archetype === "abstract_memory_cloud") {
      const cluster = index % 8;
      const theta = cluster * 0.91 + seeded(cluster, 81);
      const cx = Math.cos(theta) * (0.22 + seeded(cluster, 82) * 0.88);
      const cy = Math.sin(theta * 1.7) * 0.7;
      const cz = Math.sin(theta) * 0.48;
      const spread = 0.12 + seeded(index, 83) * 0.46;
      x = cx + (seeded(index, 84) - 0.5) * spread;
      y = cy + (seeded(index, 85) - 0.5) * spread;
      z = cz + (seeded(index, 86) - 0.5) * spread;
      warm = 0.24 + seeded(index, 87) * 0.5;
      scaleBoost = 1.28;
    } else {
      const theta = index * Math.PI * (3 - Math.sqrt(5));
      const yy = 1 - 2 * t;
      const ring = Math.sqrt(Math.max(0, 1 - yy * yy));
      x = Math.cos(theta) * ring * 1.08;
      y = yy;
      z = Math.sin(theta) * ring * 1.08;
      warm = 0.36;
    }
    const color = palette(index, warm);
    return { x, y, z, ...color, scale: color.scale * scaleBoost };
  });
}

function drawArchetypeGuides(
  ctx: CanvasRenderingContext2D,
  archetype: Archetype,
  width: number,
  height: number,
  elapsed: number,
  controls: { arousal: number; curiosity: number; speaking_energy: number; resting: boolean },
) {
  const cx = width / 2;
  const cy = height / 2;
  const unit = Math.min(width, height);
  const alpha = controls.resting ? 0.08 : 0.16 + controls.arousal * 0.08 + controls.speaking_energy * 0.08;
  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate(Math.sin(elapsed * 0.08) * 0.08);
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.strokeStyle = `rgba(76, 230, 255, ${alpha})`;
  ctx.fillStyle = `rgba(255, 104, 177, ${alpha * 0.72})`;
  ctx.lineWidth = Math.max(1, unit * 0.0014);

  if (archetype === "constellation") {
    const stars = Array.from({ length: 14 }, (_, index) => {
      const angle = index * 2.399963 + 0.3;
      const radius = unit * (0.18 + seeded(index, 101) * 0.34);
      return [Math.cos(angle) * radius, Math.sin(angle * 0.72) * radius * 0.72] as const;
    });
    stars.forEach(([x, y], index) => {
      const next = stars[(index * 5 + 3) % stars.length];
      ctx.beginPath();
      ctx.moveTo(x, y);
      ctx.lineTo(next[0], next[1]);
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(x, y, index % 3 === 0 ? 3.6 : 1.8, 0, Math.PI * 2);
      ctx.fill();
    });
  } else if (archetype === "city_block") {
    for (let i = 0; i < 10; i += 1) {
      const w = unit * (0.028 + seeded(i, 111) * 0.025);
      const h = unit * (0.13 + seeded(i, 112) * 0.3);
      const x = -unit * 0.43 + i * unit * 0.095;
      const y = unit * 0.31 - h;
      ctx.strokeRect(x, y, w, h);
      for (let row = 0; row < 5; row += 1) {
        ctx.beginPath();
        ctx.moveTo(x + w * 0.18, y + h * (0.2 + row * 0.15));
        ctx.lineTo(x + w * 0.82, y + h * (0.2 + row * 0.15));
        ctx.stroke();
      }
    }
  } else if (archetype === "circuit") {
    for (let i = 0; i < 8; i += 1) {
      const y = -unit * 0.34 + i * unit * 0.095;
      ctx.beginPath();
      ctx.moveTo(-unit * 0.45, y);
      ctx.lineTo(-unit * 0.16, y);
      ctx.lineTo(-unit * 0.06, y + (i % 2 ? -unit * 0.045 : unit * 0.045));
      ctx.lineTo(unit * 0.44, y + (i % 2 ? -unit * 0.045 : unit * 0.045));
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(-unit * 0.16, y, 3, 0, Math.PI * 2);
      ctx.fill();
    }
  } else if (archetype === "tree") {
    ctx.beginPath();
    ctx.moveTo(0, unit * 0.32);
    ctx.lineTo(0, -unit * 0.12);
    ctx.stroke();
    for (let i = 0; i < 9; i += 1) {
      const y = unit * (0.17 - i * 0.045);
      const side = i % 2 ? -1 : 1;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.quadraticCurveTo(side * unit * 0.14, y - unit * 0.08, side * unit * (0.23 + seeded(i, 121) * 0.12), y - unit * 0.13);
      ctx.stroke();
    }
    ctx.beginPath();
    ctx.ellipse(0, -unit * 0.16, unit * 0.28, unit * 0.18, 0, 0, Math.PI * 2);
    ctx.stroke();
  } else if (archetype === "machine_core") {
    for (let i = 0; i < 5; i += 1) {
      ctx.beginPath();
      ctx.ellipse(0, 0, unit * (0.09 + i * 0.055), unit * (0.05 + i * 0.034), elapsed * 0.18 + i * 0.42, 0, Math.PI * 2);
      ctx.stroke();
    }
  } else if (archetype === "tower") {
    ctx.beginPath();
    ctx.moveTo(-unit * 0.12, unit * 0.36);
    ctx.lineTo(-unit * 0.22, -unit * 0.28);
    ctx.lineTo(0, -unit * 0.42);
    ctx.lineTo(unit * 0.22, -unit * 0.28);
    ctx.lineTo(unit * 0.12, unit * 0.36);
    ctx.closePath();
    ctx.stroke();
    for (let i = 0; i < 10; i += 1) {
      const y = -unit * 0.24 + i * unit * 0.055;
      ctx.beginPath();
      ctx.moveTo(-unit * (0.18 - i * 0.006), y);
      ctx.lineTo(unit * (0.18 - i * 0.006), y);
      ctx.stroke();
    }
  } else if (archetype === "abstract_memory_cloud") {
    for (let i = 0; i < 7; i += 1) {
      const angle = i * 0.9;
      const x = Math.cos(angle) * unit * (0.08 + seeded(i, 131) * 0.18);
      const y = Math.sin(angle * 1.7) * unit * 0.16;
      ctx.beginPath();
      ctx.ellipse(x, y, unit * (0.08 + seeded(i, 132) * 0.08), unit * (0.045 + seeded(i, 133) * 0.05), angle, 0, Math.PI * 2);
      ctx.stroke();
    }
  } else if (archetype === "creature") {
    ctx.beginPath();
    ctx.ellipse(0, unit * 0.04, unit * 0.18, unit * 0.12, 0, 0, Math.PI * 2);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(0, -unit * 0.16, unit * 0.1, 0, Math.PI * 2);
    ctx.stroke();
    [[-0.28, 0.18], [0.28, 0.18], [-0.24, -0.05], [0.24, -0.05]].forEach(([x, y]) => {
      ctx.beginPath();
      ctx.moveTo(0, unit * 0.02);
      ctx.lineTo(x * unit, y * unit);
      ctx.stroke();
    });
  }
  ctx.restore();
}

function drawParticles(
  ctx: CanvasRenderingContext2D,
  particles: Particle[],
  archetype: Archetype,
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

  if (ambient) {
    drawArchetypeGuides(ctx, archetype, width, height, elapsed, controls);
  }

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
  const [archetype, setArchetype] = useState<Archetype>(() => (mode === "product" ? "constellation" : "orb"));
  const [seedNonce, setSeedNonce] = useState(0);
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
            reduced_motion: reducedMotion,
            include_particles: true,
            seed_id: `dashboard_${nextArchetype}_${seedNonce}`,
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
  }, [archetype, budget, controls, reducedMotion, seedNonce, state]);

  useEffect(() => {
    if (mode !== "product" || reducedMotion) return undefined;
    const switchMs = clamp(15000 - Number(controls.curiosity ?? 0.45) * 6400 - Number(controls.speaking_energy ?? 0) * 1800, 7800, 17000);
    const timer = window.setInterval(() => {
      setArchetype((current) => {
        const pressure = Number((controls as any).review_pressure ?? 0);
        const novelty = Number((controls as any).novelty_found ?? controls.curiosity ?? 0);
        const sequence = pressure > 0.58
          ? ["machine_core", "circuit", "city_block", "constellation"] as Archetype[]
          : novelty > 0.62
            ? ["constellation", "circuit", "city_block", "abstract_memory_cloud"] as Archetype[]
            : PRODUCT_ARCHETYPES;
        const index = sequence.indexOf(current);
        return sequence[(index + 1) % sequence.length];
      });
    }, switchMs);
    return () => window.clearInterval(timer);
  }, [controls, mode, reducedMotion]);

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
        activeArchetype,
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
  }, [activeArchetype, controls, mode, particles, reducedMotion]);

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
      {mode === "product" ? (
        <span className="splatra-imagination-product-label" aria-hidden="true">
          imagination · {ARCHETYPE_LABELS[activeArchetype]}
        </span>
      ) : null}
      {mode === "lab" ? (
        <div className="splatra-imagination-lab">
          <div>
            <small>SPLATRA Imagination Field</small>
            <strong>{ARCHETYPE_LABELS[activeArchetype]}</strong>
            <span>{status?.proof_only === false ? "blocked" : "proof-only"} / product visible={String(status?.product_visible ?? true)}</span>
          </div>
          <label>
            <span>archetype</span>
            <select value={archetype} onChange={(event) => setArchetype(event.target.value as Archetype)}>
              {ARCHETYPES.map((name) => <option key={name} value={name}>{ARCHETYPE_LABELS[name]}</option>)}
            </select>
          </label>
          <div className="splatra-imagination-actions">
            <button
              type="button"
              onClick={() => setArchetype((current) => {
                const index = ARCHETYPES.indexOf(current);
                return ARCHETYPES[(index + 1) % ARCHETYPES.length];
              })}
            >
              switch
            </button>
            <button
              type="button"
              onClick={() => {
                const next = PRODUCT_ARCHETYPES[Math.floor(Math.random() * PRODUCT_ARCHETYPES.length)];
                setArchetype(next);
                setSeedNonce((value) => value + 1);
              }}
            >
              random
            </button>
          </div>
          <div className="splatra-imagination-flags">
            <span>particles={particles.length}</span>
            <span>compression={frame?.object?.metadata?.turbovec?.compressed_ref?.compression_ratio?.toFixed?.(2) ?? "-"}</span>
            <span>lod={frame?.object?.metadata?.turbovec?.lod_summary?.levels?.join?.("/") ?? "-"}</span>
            <span>intensity={Number(frame?.object?.metadata?.visual_intensity ?? status?.visual_intensity ?? 0).toFixed(2)}</span>
            <span>clear radius={frame?.object?.metadata?.clear_radius ?? status?.clear_radius ?? "0.34"}</span>
            <span>{Number(frame?.object?.metadata?.visual_intensity ?? status?.visual_intensity ?? 1) < 0.42 ? "too subtle" : "visible object"}</span>
            <span>error={error ? "fallback" : "none"}</span>
          </div>
        </div>
      ) : null}
    </section>
  );
}
