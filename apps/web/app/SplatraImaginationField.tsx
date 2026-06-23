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

type ScenePlanBeat = {
  op?: "spawn_object" | "morph" | "move" | "focus_camera" | "label" | "despawn";
  archetype?: Archetype;
  prompt?: string;
  narration?: string;
  object_id?: string;
  semantic_role?: string;
  visual_affordance?: string;
  spatial_relation?: string;
  particle_behavior?: string;
  physics_hint?: {
    basis?: string;
    field?: string;
    material?: string;
    gravity_bias?: number;
    cohesion?: number;
    trail?: number;
  };
  source_fact?: string;
  scene_group_id?: string;
  scene_group_role?: string;
  t_start?: number;
  duration?: number;
  position?: number[];
  motion_path?: {
    from?: number[];
    to?: number[];
    basis?: string;
    source_prompt?: string;
    target_prompt?: string;
  };
  camera?: Record<string, any>;
};

type SceneMotionRole = "subject" | "source" | "target" | "";

type ScenePlan = {
  stage_layout?: "conversation" | "scene_focus";
  orb_anchor?: "center" | "lower_right";
  primary_surface?: string;
  dashboard_layout?: {
    scene?: {
      central_scale?: number;
    };
  };
  beats?: ScenePlanBeat[];
};

type SceneTransform = {
  offsetX: number;
  offsetY: number;
  zoom: number;
};

type SceneCameraView = {
  targetX: number;
  targetY: number;
  zoom: number;
};

type SceneRenderObject = {
  archetype: Archetype;
  beat: ScenePlanBeat;
  id: string;
  particles: Particle[];
};

type Props = {
  mode?: ImaginationMode;
  state?: VisualState;
  particleBudget?: number;
  className?: string;
  interactive?: boolean;
  sceneFocus?: boolean;
  scenePlan?: ScenePlan | null;
  activeSpeechBeatIndex?: number;
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

function scenePlanCentralScale(scenePlan: ScenePlan | null | undefined) {
  const value = Number(scenePlan?.dashboard_layout?.scene?.central_scale ?? 1);
  return Number.isFinite(value) ? clamp(value, 0.86, 1.22) : 1;
}

function smoothstep(value: number) {
  const t = clamp(value, 0, 1);
  return t * t * (3 - 2 * t);
}

function stableUnit(value: string, salt = 0) {
  let hash = 2166136261 ^ salt;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0) / 4294967295;
}

function flowFieldAngle(x: number, y: number, elapsed: number, salt = 0) {
  const low = Math.sin(x * 0.006 + elapsed * 0.36 + salt) + Math.cos(y * 0.005 - elapsed * 0.29);
  const high = Math.sin((x + y) * 0.0028 + elapsed * 0.48 + salt * 1.7);
  return (low * 0.72 + high * 0.46) * Math.PI;
}

function drawParticleStroke(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  angle: number,
  length: number,
  size: number,
  color: [number, number, number],
  alpha: number,
) {
  const dx = Math.cos(angle) * length;
  const dy = Math.sin(angle) * length;
  const [r, g, b] = color;
  const steps = Math.max(3, Math.min(10, Math.round(length / Math.max(1, size * 0.8))));
  for (let step = 0; step <= steps; step += 1) {
    const t = step / steps;
    const px = x - dx * 0.22 + dx * 1.22 * t;
    const py = y - dy * 0.22 + dy * 1.22 * t;
    const pointAlpha = alpha * (0.18 + t * 0.82);
    const pointSize = size * (0.18 + t * 0.34);
    ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${pointAlpha})`;
    ctx.beginPath();
    ctx.arc(px, py, pointSize, 0, Math.PI * 2);
    ctx.fill();
  }
}

function seeded(index: number, salt = 0) {
  const value = Math.sin(index * 12.9898 + salt * 78.233) * 43758.5453123;
  return value - Math.floor(value);
}

function drawGuideParticle(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  size: number,
  color: [number, number, number],
  alpha: number,
) {
  const [r, g, b] = color;
  ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${alpha})`;
  ctx.beginPath();
  ctx.arc(x, y, size, 0, Math.PI * 2);
  ctx.fill();
}

function drawParticleSegment(
  ctx: CanvasRenderingContext2D,
  from: [number, number],
  to: [number, number],
  color: [number, number, number],
  alpha: number,
  unit: number,
  salt = 0,
  elapsed = 0,
) {
  const dx = to[0] - from[0];
  const dy = to[1] - from[1];
  const distance = Math.hypot(dx, dy);
  const steps = Math.max(4, Math.ceil(distance / Math.max(17, unit * 0.042)));
  const normalX = distance > 0 ? -dy / distance : 0;
  const normalY = distance > 0 ? dx / distance : 0;
  const tangentX = distance > 0 ? dx / distance : 1;
  const tangentY = distance > 0 ? dy / distance : 0;
  const streamCount = 3;
  for (let lane = 0; lane < streamCount; lane += 1) {
    for (let index = 0; index <= steps; index += 1) {
      const rawT = index / steps;
      const t = (rawT + elapsed * (0.018 + lane * 0.011) + seeded(index, salt + lane * 101) * 0.055) % 1;
      if (index > 0 && index < steps && seeded(index, salt + lane * 37 + 41) < 0.48) continue;
      const phase = t * Math.PI * 6 + salt * 0.037 + elapsed * (1.15 + lane * 0.21);
      const laneOffset = (lane - 1) * unit * 0.018;
      const curl = Math.sin(phase) * unit * (0.015 + seeded(index, salt + 5) * 0.015);
      const shear = Math.cos(phase * 0.63 + salt) * unit * 0.01;
      const pulse = 0.46 + 0.54 * Math.sin(t * Math.PI);
      drawGuideParticle(
        ctx,
        from[0] + dx * t + normalX * (laneOffset + curl) + tangentX * shear,
        from[1] + dy * t + normalY * (laneOffset + curl) + tangentY * shear,
        unit * (0.001 + seeded(index, salt + lane * 53 + 7) * 0.0016) * (0.72 + pulse * 0.3),
        color,
        alpha * (0.07 + pulse * 0.22) * (lane === 1 ? 1 : 0.64),
      );
    }
  }
}

function drawParticlePolyline(
  ctx: CanvasRenderingContext2D,
  points: Array<[number, number]>,
  color: [number, number, number],
  alpha: number,
  unit: number,
  salt = 0,
  elapsed = 0,
) {
  for (let index = 0; index < points.length - 1; index += 1) {
    drawParticleSegment(ctx, points[index], points[index + 1], color, alpha, unit, salt + index * 17, elapsed);
  }
}

function drawParticleEllipse(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  rx: number,
  ry: number,
  rotation: number,
  color: [number, number, number],
  alpha: number,
  unit: number,
  salt = 0,
  elapsed = 0,
) {
  const steps = Math.max(30, Math.ceil((rx + ry) / Math.max(6, unit * 0.015)));
  for (let index = 0; index < steps; index += 1) {
    const t = (index / steps) * Math.PI * 2;
    const rawX = Math.cos(t) * rx;
    const rawY = Math.sin(t) * ry;
    const jitter = Math.sin(t * 3 + elapsed * 1.1 + salt) * unit * 0.003;
    const x = cx + rawX * Math.cos(rotation) - rawY * Math.sin(rotation) + Math.cos(t) * jitter;
    const y = cy + rawX * Math.sin(rotation) + rawY * Math.cos(rotation) + Math.sin(t) * jitter;
    drawGuideParticle(
      ctx,
      x,
      y,
      unit * (0.0018 + seeded(index, salt + 3) * 0.0018),
      color,
      alpha * (0.22 + seeded(index, salt + 9) * 0.46),
    );
  }
}

function drawParticleRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  color: [number, number, number],
  alpha: number,
  unit: number,
  salt = 0,
  elapsed = 0,
) {
  drawParticlePolyline(ctx, [[x, y], [x + w, y], [x + w, y + h], [x, y + h], [x, y]], color, alpha, unit, salt, elapsed);
}

function drawAmbientAirbendField(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  elapsed: number,
  controls: { arousal: number; curiosity: number; speaking_energy: number; resting: boolean },
) {
  const unit = Math.min(width, height);
  const cx = width / 2;
  const cy = height / 2;
  const count = Math.round(clamp((width * height) / 6200, 120, 360));
  const attraction = controls.resting ? 0.1 : 0.18 + controls.curiosity * 0.18 + controls.speaking_energy * 0.2;
  const fieldBreath = (Math.sin(elapsed * 0.22) + 1) * 0.5;

  for (let index = 0; index < count; index += 1) {
    const baseX = seeded(index, 7101) * width;
    const baseY = seeded(index, 7102) * height;
    const orbitAngle = elapsed * (0.035 + seeded(index, 7103) * 0.045) + seeded(index, 7104) * Math.PI * 2;
    const orbitRadiusX = width * (0.14 + seeded(index, 7105) * 0.42);
    const orbitRadiusY = height * (0.1 + seeded(index, 7106) * 0.28);
    const targetX = cx + Math.cos(orbitAngle) * orbitRadiusX;
    const targetY = cy + Math.sin(orbitAngle * 1.27) * orbitRadiusY;
    let x = baseX * (1 - attraction) + targetX * attraction;
    let y = baseY * (1 - attraction) + targetY * attraction;

    const centerDistance = Math.hypot(x - cx, y - cy);
    const bodyClearRadius = unit * 0.25;
    if (centerDistance < bodyClearRadius) {
      const push = (bodyClearRadius - centerDistance) / Math.max(1, bodyClearRadius);
      const angle = Math.atan2(y - cy, x - cx) || orbitAngle;
      x += Math.cos(angle) * push * unit * 0.22;
      y += Math.sin(angle) * push * unit * 0.22;
    }

    const fieldAngle = flowFieldAngle(x, y, elapsed, index * 0.37);
    const hueShift = Math.sin(elapsed * 0.18 + index * 0.11);
    const color: [number, number, number] = hueShift > 0.28
      ? [255, 104, 177]
      : hueShift < -0.34
        ? [138, 117, 255]
        : [76, 230, 255];
    const size = unit * (0.00075 + seeded(index, 7110) * 0.0012);
    const length = unit * (0.006 + controls.curiosity * 0.008 + fieldBreath * 0.004 + controls.speaking_energy * 0.008);
    const alpha = (controls.resting ? 0.026 : 0.038 + controls.arousal * 0.016 + controls.speaking_energy * 0.025)
      * (0.48 + seeded(index, 7111) * 0.82);
    drawParticleStroke(ctx, x, y, fieldAngle, length, size, color, alpha);
  }
}

function sceneBeatIndex(scenePlan: ScenePlan | null | undefined, elapsedSeconds: number): number {
  const beats = Array.isArray(scenePlan?.beats) ? scenePlan?.beats ?? [] : [];
  if (!beats.length) return -1;
  let activeIndex = 0;
  beats.forEach((beat, index) => {
    const start = Number.isFinite(Number(beat.t_start)) ? Number(beat.t_start) : index * 1.25;
    if (elapsedSeconds >= start) activeIndex = index;
  });
  return activeIndex;
}

function sceneArchetype(scenePlan: ScenePlan | null | undefined, beatIndex = -1): Archetype | null {
  const beats = Array.isArray(scenePlan?.beats) ? scenePlan?.beats ?? [] : [];
  const activeBeat = beatIndex >= 0 ? beats[beatIndex] : null;
  if (activeBeat?.archetype && PRODUCT_ARCHETYPES.includes(activeBeat.archetype)) return activeBeat.archetype;
  const explicit = beats.find((beat) => beat.archetype && PRODUCT_ARCHETYPES.includes(beat.archetype))?.archetype;
  if (explicit) return explicit;
  const prompt = beats.map((beat) => `${beat.prompt ?? ""} ${beat.object_id ?? ""}`).join(" ").trim();
  if (!prompt) return null;
  const hash = Array.from(prompt).reduce((acc, char) => ((acc * 31) + char.charCodeAt(0)) >>> 0, 2166136261);
  return PRODUCT_ARCHETYPES[hash % PRODUCT_ARCHETYPES.length];
}

function sceneTransform(beat: ScenePlanBeat | null | undefined, stageMode: boolean, elapsedSeconds = 0): SceneTransform {
  if (!stageMode || !beat) return { offsetX: 0, offsetY: 0, zoom: 1 };
  const position = Array.isArray(beat.position) ? beat.position : [];
  const camera = beat.camera && typeof beat.camera === "object" ? beat.camera : {};
  const cameraTarget = Array.isArray(camera.target) ? camera.target : [];
  const rawX = Number(position[0] ?? cameraTarget[0] ?? 0);
  const rawY = Number(position[1] ?? cameraTarget[1] ?? 0);
  const rawZoom = Number(camera.zoom ?? camera.distance ?? 1);
  const opBias = beat.op === "focus_camera" ? 1.08 : beat.op === "move" ? 1.16 : beat.op === "despawn" ? 0.82 : 1;
  const motionBias = beat.op === "move" ? 1.45 : 1;
  const beatStart = Number.isFinite(Number(beat.t_start)) ? Number(beat.t_start) : 0;
  const duration = Math.max(0.1, Number.isFinite(Number(beat.duration)) ? Number(beat.duration) : 1.2);
  const progress = smoothstep((elapsedSeconds - beatStart) / duration);
  const flowKey = `${beat.object_id ?? ""}:${beat.prompt ?? ""}:${beat.semantic_role ?? ""}`;
  const moveX = beat.op === "move" ? (stableUnit(flowKey, 11) - 0.5) * 0.18 * Math.sin(progress * Math.PI) : 0;
  const moveY = beat.op === "move" ? (stableUnit(flowKey, 19) - 0.5) * 0.12 * Math.sin(progress * Math.PI) : 0;
  return {
    offsetX: clamp((Number.isFinite(rawX) ? rawX * 0.08 * motionBias : 0) + moveX, -0.34, 0.34),
    offsetY: clamp((Number.isFinite(rawY) ? -rawY * 0.08 * motionBias : 0) + moveY, -0.28, 0.28),
    zoom: clamp((Number.isFinite(rawZoom) ? rawZoom : 1) * opBias * (beat.op === "move" ? 1 + progress * 0.05 : 1), 0.72, 1.42),
  };
}

function sceneBeatFocusProgress(beat: ScenePlanBeat | null | undefined, elapsedSeconds: number) {
  if (!beat) return 0;
  const start = Number.isFinite(Number(beat.t_start)) ? Number(beat.t_start) : 0;
  const duration = Math.max(0.1, Number.isFinite(Number(beat.duration)) ? Number(beat.duration) : 1.2);
  const leadIn = beat.op === "focus_camera" || beat.op === "move" || beat.motion_path ? 0.48 : 0.22;
  const focusWindow = Math.max(0.46, duration * 0.62);
  return smoothstep((elapsedSeconds - (start - leadIn)) / focusWindow);
}

function sceneCameraView(beat: ScenePlanBeat | null | undefined, stageMode: boolean, elapsedSeconds = 0): SceneCameraView {
  if (!stageMode || !beat) return { targetX: 0, targetY: 0, zoom: 1 };
  const position = Array.isArray(beat.position) ? beat.position : [];
  const camera = beat.camera && typeof beat.camera === "object" ? beat.camera : {};
  const cameraTarget = Array.isArray(camera.target) ? camera.target : [];
  const rawTargetX = Number(cameraTarget[0] ?? position[0] ?? 0);
  const rawTargetY = Number(cameraTarget[1] ?? position[1] ?? 0);
  const rawZoom = Number(camera.zoom ?? 1);
  const progress = sceneBeatFocusProgress(beat, elapsedSeconds);
  const focusBias = beat.op === "focus_camera" ? 0.16 : beat.op === "move" ? 0.08 : 0;
  return {
    targetX: Number.isFinite(rawTargetX) ? rawTargetX * progress : 0,
    targetY: Number.isFinite(rawTargetY) ? rawTargetY * progress : 0,
    zoom: clamp(1 + ((Number.isFinite(rawZoom) ? rawZoom : 1) + focusBias - 1) * progress, 0.82, 1.56),
  };
}

function sceneObjectPosition(beat: ScenePlanBeat | null | undefined) {
  const position = Array.isArray(beat?.position) ? beat?.position ?? [] : [];
  return {
    x: Number.isFinite(Number(position[0])) ? Number(position[0]) : 0,
    y: Number.isFinite(Number(position[1])) ? Number(position[1]) : 0,
  };
}

function physicsNumber(beat: ScenePlanBeat | null | undefined, key: "gravity_bias" | "cohesion" | "trail", fallback: number) {
  const value = Number(beat?.physics_hint?.[key] ?? fallback);
  return Number.isFinite(value) ? clamp(value, 0, 1.5) : fallback;
}

function sceneMotionPathPoint(beat: ScenePlanBeat | null | undefined, elapsedSeconds: number) {
  const from = Array.isArray(beat?.motion_path?.from) ? beat?.motion_path?.from ?? [] : [];
  const to = Array.isArray(beat?.motion_path?.to) ? beat?.motion_path?.to ?? [] : [];
  if (from.length < 2 || to.length < 2) return sceneObjectPosition(beat);
  const progress = sceneObjectProgress(beat as ScenePlanBeat, elapsedSeconds);
  const arc = Math.sin(progress * Math.PI) * 0.22;
  const fromX = Number.isFinite(Number(from[0])) ? Number(from[0]) : 0;
  const fromY = Number.isFinite(Number(from[1])) ? Number(from[1]) : 0;
  const toX = Number.isFinite(Number(to[0])) ? Number(to[0]) : 0;
  const toY = Number.isFinite(Number(to[1])) ? Number(to[1]) : 0;
  const gravityBias = physicsNumber(beat, "gravity_bias", 0.28);
  const behavior = String(beat?.particle_behavior ?? "");
  const lift = behavior === "gravity_arc" ? 0.17 : 0.22;
  const downwardPull = behavior === "gravity_arc" ? progress * progress * gravityBias * 0.18 : 0;
  return {
    x: fromX * (1 - progress) + toX * progress,
    y: fromY * (1 - progress) + toY * progress + arc * lift / 0.22 - downwardPull,
  };
}

function scenePointToCanvas(
  beat: ScenePlanBeat,
  point: { x: number; y: number },
  width: number,
  height: number,
  sceneElapsed: number,
  swing = { x: 0, y: 0 },
  cameraView: SceneCameraView = { targetX: 0, targetY: 0, zoom: 1 },
) {
  const transform = sceneTransform(beat, true, sceneElapsed);
  const viewX = (point.x - cameraView.targetX) * cameraView.zoom;
  const viewY = (point.y - cameraView.targetY) * cameraView.zoom;
  return {
    x: width / 2 + (viewX * 0.34 + transform.offsetX * 0.38 + swing.x) * width,
    y: height / 2 + (-viewY * 0.28 + transform.offsetY * 0.38 + swing.y) * height,
  };
}

function sceneObjectProgress(beat: ScenePlanBeat, elapsedSeconds: number) {
  const start = Number.isFinite(Number(beat.t_start)) ? Number(beat.t_start) : 0;
  const duration = Math.max(0.1, Number.isFinite(Number(beat.duration)) ? Number(beat.duration) : 1.2);
  return smoothstep((elapsedSeconds - start) / duration);
}

function sceneMotionSourceHold(beat: ScenePlanBeat, elapsedSeconds: number) {
  if (!beat.motion_path && beat.op !== "move") return 0;
  const start = Number.isFinite(Number(beat.t_start)) ? Number(beat.t_start) : 0;
  const leadIn = clamp((elapsedSeconds - (start - 0.72)) / 0.72, 0, 1);
  const beforeMotion = elapsedSeconds < start ? 1 : 0;
  return smoothstep(leadIn) * beforeMotion;
}

function sceneObjectAlpha(beat: ScenePlanBeat, elapsedSeconds: number, active: boolean) {
  const start = Number.isFinite(Number(beat.t_start)) ? Number(beat.t_start) : 0;
  const sourceHold = sceneMotionSourceHold(beat, elapsedSeconds);
  if (elapsedSeconds < start - 0.16 && sourceHold <= 0) return 0;
  const reveal = sceneObjectProgress(beat, elapsedSeconds);
  const sourceHoldBase = sourceHold > 0 ? 0.18 + sourceHold * 0.28 : 0;
  const base = beat.op === "despawn" ? 1 - reveal : Math.max(sourceHoldBase, 0.24, reveal);
  return clamp(base * (active ? 1 : 0.42), 0, 1);
}

function sceneMotionRole(beat: ScenePlanBeat): SceneMotionRole {
  const role = String(beat.semantic_role ?? "");
  if (role === "verified_motion_subject") return "subject";
  if (role === "verified_motion_source") return "source";
  if (role === "verified_motion_target") return "target";
  return "";
}

function sceneRoleStyle(beat: ScenePlanBeat, active: boolean) {
  const role = String(beat.semantic_role ?? "");
  const affordance = String(beat.visual_affordance ?? "");
  const motionRole = sceneMotionRole(beat);
  const moving = beat.op === "move" || role.includes("motion");
  const relation = role.includes("relation");
  const anchor = role.includes("anchor");
  const smallObject = affordance === "small_object" || affordance === "small_moving_object";
  const figure = affordance === "entity_figure";
  const organic = affordance === "organic_structure";
  const behavior = String(beat.particle_behavior ?? "");
  const cohesion = physicsNumber(beat, "cohesion", 0.56);
  const trailHint = physicsNumber(beat, "trail", 0.34);
  const physicsTrailBoost = behavior === "gravity_arc" ? 0.34 : behavior === "kinetic_flow" ? 0.22 : behavior === "magnetic_field" ? 0.16 : 0;
  const physicsScaleBoost = (cohesion - 0.5) * 0.18;
  if (motionRole === "subject") {
    return {
      alpha: active ? 1.46 : 1.24,
      scale: (smallObject ? 0.5 : 0.72) + physicsScaleBoost,
      trail: (active ? 1.38 : 0.94) + trailHint * 0.16 + physicsTrailBoost,
      focus: active ? 1.08 : 0.9,
    };
  }
  if (motionRole === "source") {
    return {
      alpha: active ? 1.08 : 0.86,
      scale: (organic ? 1.28 : 1.02) + physicsScaleBoost,
      trail: (active ? 0.34 : 0.18) + trailHint * 0.08,
      focus: active ? 0.92 : 0.62,
    };
  }
  if (motionRole === "target") {
    return {
      alpha: active ? 1.18 : 0.92,
      scale: (figure ? 1.12 : 1.04) + physicsScaleBoost,
      trail: (active ? 0.48 : 0.26) + trailHint * 0.1,
      focus: active ? 1 : 0.72,
    };
  }
  return {
    alpha: smallObject ? 1.32 : moving ? 1.16 : relation ? 1.02 : anchor ? 0.86 : 0.94,
    scale: (smallObject ? 0.56 : organic ? 1.22 : figure ? 1.06 : moving ? 1.2 : relation ? 1.08 : anchor ? 0.92 : 1) + physicsScaleBoost,
    trail: (smallObject && moving ? (active ? 1.18 : 0.78) : moving ? (active ? 1 : 0.62) : relation ? 0.34 : 0.16) + trailHint * 0.12 + physicsTrailBoost,
    focus: active ? 1 : smallObject ? 0.82 : moving ? 0.72 : 0.48,
  };
}

function sceneObjectId(beat: ScenePlanBeat, index: number) {
  return `${beat.object_id || beat.prompt || "scene"}:${index}`;
}

function sameSceneGroup(left: ScenePlanBeat | null | undefined, right: ScenePlanBeat | null | undefined) {
  const leftGroup = String(left?.scene_group_id ?? "");
  const rightGroup = String(right?.scene_group_id ?? "");
  return Boolean(leftGroup && rightGroup && leftGroup === rightGroup);
}

function sceneBeatModelPoints(beat: ScenePlanBeat, sceneElapsed: number) {
  const points = [sceneObjectPosition(beat), sceneMotionPathPoint(beat, sceneElapsed)];
  const from = Array.isArray(beat.motion_path?.from) ? beat.motion_path?.from ?? [] : [];
  const to = Array.isArray(beat.motion_path?.to) ? beat.motion_path?.to ?? [] : [];
  if (from.length >= 2) {
    points.push({
      x: Number.isFinite(Number(from[0])) ? Number(from[0]) : 0,
      y: Number.isFinite(Number(from[1])) ? Number(from[1]) : 0,
    });
  }
  if (to.length >= 2) {
    points.push({
      x: Number.isFinite(Number(to[0])) ? Number(to[0]) : 0,
      y: Number.isFinite(Number(to[1])) ? Number(to[1]) : 0,
    });
  }
  return points;
}

function sceneGroupCameraView(activeObject: SceneRenderObject | null, visibleObjects: SceneRenderObject[], sceneElapsed: number): SceneCameraView {
  const baseView = sceneCameraView(activeObject?.beat, true, sceneElapsed);
  if (!activeObject) return baseView;
  const groupObjects = visibleObjects.filter((object) => sameSceneGroup(object.beat, activeObject.beat));
  if (groupObjects.length < 2) return baseView;
  const points = groupObjects.flatMap((object) => sceneBeatModelPoints(object.beat, sceneElapsed));
  if (points.length < 2) return baseView;
  const xs = points.map((point) => point.x);
  const ys = points.map((point) => point.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const spread = Math.max(maxX - minX, maxY - minY);
  const groupTargetX = (minX + maxX) / 2;
  const groupTargetY = (minY + maxY) / 2;
  const groupZoom = clamp(1.48 - spread * 0.34 + groupObjects.length * 0.018, 0.9, 1.46);
  const motionFocusBoost = sceneMotionFocusBoost(activeObject.beat);
  const zoomCeiling = groupZoom + motionFocusBoost * 0.72;
  return {
    targetX: baseView.targetX * 0.38 + groupTargetX * 0.62,
    targetY: baseView.targetY * 0.38 + groupTargetY * 0.62,
    zoom: clamp(Math.min(baseView.zoom + motionFocusBoost, zoomCeiling), 0.82, 1.68),
  };
}

function sceneMotionFocusBoost(beat: ScenePlanBeat | null | undefined) {
  if (!beat?.motion_path && beat?.op !== "move") return 0;
  const behavior = String(beat?.particle_behavior ?? "");
  const gravityBias = physicsNumber(beat, "gravity_bias", 0.28);
  if (behavior === "gravity_arc") return clamp(0.16 + gravityBias * 0.12, 0.16, 0.32);
  if (behavior === "kinetic_flow") return 0.14;
  return 0.08;
}

function sceneRelationRank(object: SceneRenderObject) {
  const affordance = String(object.beat.visual_affordance ?? "");
  const role = String(object.beat.semantic_role ?? "");
  const motionRole = sceneMotionRole(object.beat);
  if (motionRole === "subject") return 0;
  if (motionRole === "source") return 1;
  if (motionRole === "target") return 2;
  if (object.beat.op === "move" || object.beat.motion_path) return 0;
  if (affordance === "small_moving_object" || affordance === "small_object") return 1;
  if (affordance === "entity_figure") return 2;
  if (affordance === "organic_structure") return 3;
  if (role.includes("relation")) return 4;
  return 5;
}

function sceneActiveGroupObjects(activeObject: SceneRenderObject | null, visibleObjects: SceneRenderObject[]) {
  if (!activeObject) return [];
  return visibleObjects
    .filter((object) => sameSceneGroup(object.beat, activeObject.beat))
    .sort((left, right) => sceneRelationRank(left) - sceneRelationRank(right))
    .slice(0, 6);
}

function buildSceneRenderObjects(scenePlan: ScenePlan | null | undefined, budget: number): SceneRenderObject[] {
  const beats = Array.isArray(scenePlan?.beats) ? scenePlan?.beats ?? [] : [];
  const seen = new Set<string>();
  const maxObjects = Math.min(10, Math.max(1, beats.length));
  const perObjectBudget = clamp(Math.floor(Math.max(280, budget * 1.8) / maxObjects), 96, 260);
  return beats
    .slice(0, maxObjects)
    .map((beat, index) => {
      const archetype = beat.archetype && PRODUCT_ARCHETYPES.includes(beat.archetype) ? beat.archetype : sceneArchetype(scenePlan, index) ?? "abstract_memory_cloud";
      const id = sceneObjectId(beat, index);
      return {
        archetype,
        beat,
        id,
        particles: sceneParticlesForBeat(beat, archetype, perObjectBudget),
      };
    })
    .filter((object) => {
      if (seen.has(object.id)) return false;
      seen.add(object.id);
      return true;
    });
}

function sceneParticlesForBeat(beat: ScenePlanBeat, archetype: Archetype, count: number): Particle[] {
  const affordance = String(beat.visual_affordance ?? "");
  if (affordance === "entity_figure") return figureParticles(count, `${beat.object_id ?? ""}:${beat.prompt ?? ""}`, scenePoseForBeat(beat));
  if (affordance === "organic_structure") {
    return organicStructureParticles(count, `${beat.object_id ?? ""}:${beat.prompt ?? ""}`, beat);
  }
  if (affordance === "small_object" || affordance === "small_moving_object") {
    return smallObjectParticles(count, `${beat.object_id ?? ""}:${beat.prompt ?? ""}`, affordance === "small_moving_object");
  }
  return fallbackParticles(archetype, count);
}

function scenePoseForBeat(beat: ScenePlanBeat) {
  const relation = String(beat.spatial_relation ?? "");
  const motionRole = sceneMotionRole(beat);
  if (relation === "under_target") return "seated";
  if (relation === "motion_target") return "reaching";
  if (motionRole === "target" && beat.visual_affordance === "entity_figure") return "reaching";
  const text = `${beat.prompt ?? ""} ${beat.narration ?? ""} ${beat.source_fact ?? ""}`.toLowerCase();
  if (/\b(sat|sitting|seated|rested|under)\b/.test(text)) return "seated";
  if (/\b(fell|falling|dropped|moved|toward|towards)\b/.test(text)) return "reaching";
  return "standing";
}

function semanticParticleColor(index: number, salt: number, warm = 0.32) {
  return {
    r: 0.1 + warm * 0.74 + seeded(index, salt + 3) * 0.14,
    g: 0.68 + seeded(index, salt + 5) * 0.24,
    b: 0.92 + seeded(index, salt + 7) * 0.08,
    a: 0.5 + seeded(index, salt + 11) * 0.42,
    scale: 0.76 + seeded(index, salt + 13) * 1.18,
  };
}

function segmentParticle(
  index: number,
  start: [number, number, number],
  end: [number, number, number],
  thickness: number,
  salt: number,
) {
  const t = seeded(index, salt);
  const angle = seeded(index, salt + 1) * Math.PI * 2;
  const radius = Math.sqrt(seeded(index, salt + 2)) * thickness;
  return {
    x: start[0] * (1 - t) + end[0] * t + Math.cos(angle) * radius,
    y: start[1] * (1 - t) + end[1] * t + (seeded(index, salt + 3) - 0.5) * thickness,
    z: start[2] * (1 - t) + end[2] * t + Math.sin(angle) * radius * 0.7,
  };
}

function figureParticles(count: number, seed: string, pose: "standing" | "seated" | "reaching" = "standing"): Particle[] {
  const salt = Math.floor(stableUnit(seed, 221) * 10000);
  const seated = pose === "seated";
  const reaching = pose === "reaching";
  const limbs: Array<{ start: [number, number, number]; end: [number, number, number]; thickness: number; warm: number }> = [
    { start: [0, 0.42, 0], end: [0, -0.35, 0], thickness: 0.13, warm: 0.26 },
    { start: [-0.05, 0.28, 0], end: [reaching ? -0.58 : -0.42, reaching ? 0.22 : -0.02, 0], thickness: 0.06, warm: 0.38 },
    { start: [0.05, 0.28, 0], end: [reaching ? 0.58 : 0.42, reaching ? 0.22 : -0.02, 0], thickness: 0.06, warm: 0.38 },
    { start: [-0.05, -0.34, 0], end: [seated ? -0.5 : -0.27, seated ? -0.48 : -0.88, 0], thickness: 0.07, warm: 0.3 },
    { start: [0.05, -0.34, 0], end: [seated ? 0.5 : 0.27, seated ? -0.48 : -0.88, 0], thickness: 0.07, warm: 0.3 },
  ];
  return Array.from({ length: count }, (_, index) => {
    const headCutoff = Math.floor(count * 0.22);
    let x = 0;
    let y = 0;
    let z = 0;
    let warm = 0.34;
    let scaleBoost = 1;
    if (index < headCutoff) {
      const local = index / Math.max(1, headCutoff);
      const theta = index * Math.PI * (3 - Math.sqrt(5));
      const yy = 1 - 2 * local;
      const ring = Math.sqrt(Math.max(0, 1 - yy * yy));
      const radius = 0.17 + (seeded(index, salt + 31) - 0.5) * 0.025;
      x = Math.cos(theta) * ring * radius;
      y = 0.66 + yy * radius;
      z = Math.sin(theta) * ring * radius * 0.72;
      warm = 0.46;
      scaleBoost = 1.22;
    } else {
      const limb = limbs[(index - headCutoff) % limbs.length];
      const point = segmentParticle(index, limb.start, limb.end, limb.thickness, salt + (index % limbs.length) * 19);
      x = point.x;
      y = point.y;
      z = point.z;
      warm = limb.warm;
      scaleBoost = limb.thickness > 0.1 ? 1.08 : 0.82;
    }
    const color = semanticParticleColor(index, salt, warm);
    return { x, y, z, ...color, scale: color.scale * scaleBoost };
  });
}

function organicStructureParticles(count: number, seed: string, beat: ScenePlanBeat): Particle[] {
  const particles = fallbackParticles("tree", count);
  const factText = `${beat.prompt ?? ""} ${beat.narration ?? ""} ${beat.source_fact ?? ""}`.toLowerCase();
  const hasFruit = /\b(apple|fruit|berry|seed)\b/.test(factText);
  if (!hasFruit) return particles;
  const salt = Math.floor(stableUnit(seed, 419) * 10000);
  const fruitCount = Math.max(8, Math.floor(count * 0.1));
  for (let index = 0; index < fruitCount && index < particles.length; index += 1) {
    const target = particles.length - 1 - index;
    const theta = index * Math.PI * (3 - Math.sqrt(5)) + seeded(index, salt) * 0.4;
    const r = 0.24 + seeded(index, salt + 3) * 0.56;
    particles[target] = {
      x: Math.cos(theta) * r * 0.78,
      y: 0.24 + seeded(index, salt + 5) * 0.88,
      z: Math.sin(theta) * r * 0.5,
      r: 0.9 + seeded(index, salt + 7) * 0.08,
      g: 0.28 + seeded(index, salt + 11) * 0.16,
      b: 0.38 + seeded(index, salt + 13) * 0.12,
      a: 0.74,
      scale: 1.42 + seeded(index, salt + 17) * 0.74,
    };
  }
  return particles;
}

function smallObjectParticles(count: number, seed: string, moving: boolean): Particle[] {
  const salt = Math.floor(stableUnit(seed, 337) * 10000);
  return Array.from({ length: count }, (_, index) => {
    const t = (index + 0.5) / count;
    const theta = index * Math.PI * (3 - Math.sqrt(5));
    const yy = 1 - 2 * t;
    const ring = Math.sqrt(Math.max(0, 1 - yy * yy));
    const radius = 0.26 + Math.sin(index * 0.29 + salt) * 0.018;
    const tail = moving && index > count * 0.72;
    const tailT = tail ? (index - count * 0.72) / Math.max(1, count * 0.28) : 0;
    const color = semanticParticleColor(index, salt, tail ? 0.62 : 0.78);
    return {
      x: Math.cos(theta) * ring * radius - tailT * (0.32 + seeded(index, salt + 17) * 0.18),
      y: yy * radius + Math.sin(tailT * Math.PI) * 0.05,
      z: Math.sin(theta) * ring * radius * 0.72,
      ...color,
      a: tail ? color.a * (1 - tailT * 0.62) : color.a,
      scale: color.scale * (tail ? 0.58 : 1.28),
    };
  });
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
  const guideColor: [number, number, number] = [76, 230, 255];
  const accentColor: [number, number, number] = [255, 104, 177];

  if (archetype === "constellation") {
    const stars = Array.from({ length: 14 }, (_, index) => {
      const angle = index * 2.399963 + 0.3;
      const radius = unit * (0.18 + seeded(index, 101) * 0.34);
      return [Math.cos(angle) * radius, Math.sin(angle * 0.72) * radius * 0.72] as const;
    });
    stars.forEach(([x, y], index) => {
      const next = stars[(index * 5 + 3) % stars.length];
      drawParticleSegment(ctx, [x, y], [next[0], next[1]], guideColor, alpha * 0.72, unit, index + 101, elapsed);
      drawGuideParticle(ctx, x, y, index % 3 === 0 ? unit * 0.006 : unit * 0.0032, accentColor, alpha * 0.9);
    });
  } else if (archetype === "city_block") {
    for (let i = 0; i < 10; i += 1) {
      const w = unit * (0.028 + seeded(i, 111) * 0.025);
      const h = unit * (0.13 + seeded(i, 112) * 0.3);
      const x = -unit * 0.43 + i * unit * 0.095;
      const y = unit * 0.31 - h;
      drawParticleRect(ctx, x, y, w, h, guideColor, alpha * 0.72, unit, i + 111, elapsed);
      for (let row = 0; row < 5; row += 1) {
        const yy = y + h * (0.2 + row * 0.15);
        drawParticleSegment(ctx, [x + w * 0.18, yy], [x + w * 0.82, yy], accentColor, alpha * 0.45, unit, i * 19 + row, elapsed);
      }
    }
  } else if (archetype === "circuit") {
    for (let i = 0; i < 8; i += 1) {
      const y = -unit * 0.34 + i * unit * 0.095;
      drawParticlePolyline(ctx, [
        [-unit * 0.45, y],
        [-unit * 0.16, y],
        [-unit * 0.06, y + (i % 2 ? -unit * 0.045 : unit * 0.045)],
        [unit * 0.44, y + (i % 2 ? -unit * 0.045 : unit * 0.045)],
      ], guideColor, alpha * 0.8, unit, i + 211, elapsed);
      drawGuideParticle(ctx, -unit * 0.16, y, unit * 0.0048, accentColor, alpha * 0.76);
    }
  } else if (archetype === "tree") {
    drawParticleSegment(ctx, [0, unit * 0.32], [0, -unit * 0.12], guideColor, alpha * 0.86, unit, 311, elapsed);
    for (let i = 0; i < 9; i += 1) {
      const y = unit * (0.17 - i * 0.045);
      const side = i % 2 ? -1 : 1;
      const mid: [number, number] = [side * unit * 0.14, y - unit * 0.08];
      const end: [number, number] = [side * unit * (0.23 + seeded(i, 121) * 0.12), y - unit * 0.13];
      drawParticlePolyline(ctx, [[0, y], mid, end], guideColor, alpha * 0.72, unit, i + 321, elapsed);
    }
    drawParticleEllipse(ctx, 0, -unit * 0.16, unit * 0.28, unit * 0.18, 0, guideColor, alpha * 0.72, unit, 331, elapsed);
  } else if (archetype === "machine_core") {
    for (let i = 0; i < 5; i += 1) {
      drawParticleEllipse(ctx, 0, 0, unit * (0.09 + i * 0.055), unit * (0.05 + i * 0.034), elapsed * 0.18 + i * 0.42, guideColor, alpha * 0.72, unit, i + 411, elapsed);
    }
  } else if (archetype === "tower") {
    drawParticlePolyline(ctx, [
      [-unit * 0.12, unit * 0.36],
      [-unit * 0.22, -unit * 0.28],
      [0, -unit * 0.42],
      [unit * 0.22, -unit * 0.28],
      [unit * 0.12, unit * 0.36],
      [-unit * 0.12, unit * 0.36],
    ], guideColor, alpha * 0.78, unit, 501, elapsed);
    for (let i = 0; i < 10; i += 1) {
      const y = -unit * 0.24 + i * unit * 0.055;
      drawParticleSegment(ctx, [-unit * (0.18 - i * 0.006), y], [unit * (0.18 - i * 0.006), y], accentColor, alpha * 0.52, unit, i + 521, elapsed);
    }
  } else if (archetype === "abstract_memory_cloud") {
    for (let i = 0; i < 7; i += 1) {
      const angle = i * 0.9;
      const x = Math.cos(angle) * unit * (0.08 + seeded(i, 131) * 0.18);
      const y = Math.sin(angle * 1.7) * unit * 0.16;
      drawParticleEllipse(ctx, x, y, unit * (0.08 + seeded(i, 132) * 0.08), unit * (0.045 + seeded(i, 133) * 0.05), angle, guideColor, alpha * 0.62, unit, i + 611, elapsed);
    }
  } else if (archetype === "creature") {
    drawParticleEllipse(ctx, 0, unit * 0.04, unit * 0.18, unit * 0.12, 0, guideColor, alpha * 0.78, unit, 701, elapsed);
    drawParticleEllipse(ctx, 0, -unit * 0.16, unit * 0.1, unit * 0.1, 0, guideColor, alpha * 0.78, unit, 711, elapsed);
    [[-0.28, 0.18], [0.28, 0.18], [-0.24, -0.05], [0.24, -0.05]].forEach(([x, y]) => {
      drawParticleSegment(ctx, [0, unit * 0.02], [x * unit, y * unit], guideColor, alpha * 0.72, unit, Math.round((x + y) * 1000), elapsed);
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
  guides = false,
  transform: SceneTransform = { offsetX: 0, offsetY: 0, zoom: 1 },
) {
  ctx.clearRect(0, 0, width, height);
  const cx = width / 2 + transform.offsetX * width;
  const cy = height / 2 + transform.offsetY * height;
  const scale = Math.min(width, height) * (ambient ? 0.18 : 0.26) * transform.zoom;
  const rotation = elapsed * (controls.resting ? 0.08 : 0.18 + controls.arousal * 0.16);
  const tilt = Math.sin(elapsed * 0.21) * 0.18;
  const pulse = 1 + Math.sin(elapsed * 3.6) * controls.speaking_energy * 0.045;
  const cosY = Math.cos(rotation);
  const sinY = Math.sin(rotation);
  const cosX = Math.cos(tilt);
  const sinX = Math.sin(tilt);

  if (!ambient && guides) {
    drawArchetypeGuides(ctx, archetype, width, height, elapsed, controls);
  }

  if (ambient) {
    ctx.globalCompositeOperation = "lighter";
    drawAmbientAirbendField(ctx, width, height, elapsed, controls);
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

    const color: [number, number, number] = [
      Math.floor(point.r * 255),
      Math.floor(point.g * 255),
      Math.floor(point.b * 255),
    ];
    if (ambient) {
      const angle = flowFieldAngle(px, py, elapsed, point.x * 1.7 + point.z * 0.9);
      const trailLength = clamp(size * (3.6 + controls.curiosity * 3.8 + controls.speaking_energy * 2.4), 1.8, 12);
      drawParticleStroke(ctx, px, py, angle, trailLength, size, color, alpha);
    } else {
      ctx.fillStyle = `rgba(${color[0]}, ${color[1]}, ${color[2]}, ${alpha})`;
      ctx.beginPath();
      ctx.arc(px, py, size, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  if (ambient) {
    ctx.globalCompositeOperation = "source-over";
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
  drawParticleEllipse(ctx, cx, cy, shellRadius, shellRadius, 0, [128, 226, 255], 0.22, Math.min(width, height), 901, elapsed);
}

function drawSceneObjectCloud(
  ctx: CanvasRenderingContext2D,
  object: SceneRenderObject,
  width: number,
  height: number,
  elapsed: number,
  sceneElapsed: number,
  active: boolean,
  controls: { arousal: number; curiosity: number; speaking_energy: number; resting: boolean },
  cameraView: SceneCameraView,
  centralScale = 1,
) {
  const alphaMultiplier = sceneObjectAlpha(object.beat, sceneElapsed, active);
  if (alphaMultiplier <= 0.02) return;
  const roleStyle = sceneRoleStyle(object.beat, active);
  const position = sceneMotionPathPoint(object.beat, sceneElapsed);
  const beatProgress = sceneObjectProgress(object.beat, sceneElapsed);
  const sourceHold = sceneMotionSourceHold(object.beat, sceneElapsed);
  const motionSwing = object.beat.op === "move" ? Math.sin(beatProgress * Math.PI) : 0;
  const flowSalt = stableUnit(object.id, 43);
  const center = scenePointToCanvas(
    object.beat,
    position,
    width,
    height,
    sceneElapsed,
    {
      x: motionSwing * (flowSalt - 0.5) * 0.11,
      y: motionSwing * (stableUnit(object.id, 47) - 0.5) * 0.08,
    },
    cameraView,
  );
  const cx = center.x;
  const cy = center.y;
  const transform = sceneTransform(object.beat, true, sceneElapsed);
  const scaleBias = (active ? 1.12 : 0.78) * roleStyle.scale * (sourceHold > 0 ? 0.84 : 1);
  const scale = Math.min(width, height) * 0.11 * transform.zoom * centralScale * scaleBias;
  const rotation = elapsed * (0.12 + controls.arousal * 0.11) + stableUnit(object.id, 5) * Math.PI * 2;
  const tilt = Math.sin(elapsed * 0.16 + stableUnit(object.id, 9) * 4) * 0.18;
  const pulse = 1 + Math.sin(elapsed * (2.1 + roleStyle.trail) + stableUnit(object.id, 17) * 4) * (active ? 0.035 : 0.018) * roleStyle.focus;
  const cosY = Math.cos(rotation);
  const sinY = Math.sin(rotation);
  const cosX = Math.cos(tilt);
  const sinX = Math.sin(tilt);

  if (roleStyle.trail > 0.4) {
    const wakeLength = Math.min(width, height) * (0.06 + roleStyle.trail * 0.035);
    const wakeAngle = flowFieldAngle(cx, cy, elapsed, flowSalt * 11);
    for (let index = 0; index < 9; index += 1) {
      const t = index / 8;
      const wakeX = cx - Math.cos(wakeAngle) * wakeLength * t;
      const wakeY = cy - Math.sin(wakeAngle) * wakeLength * t;
      drawGuideParticle(ctx, wakeX, wakeY, Math.min(width, height) * (0.002 + (1 - t) * 0.003), [76, 230, 255], alphaMultiplier * roleStyle.trail * (0.12 + (1 - t) * 0.26));
    }
  }

  for (const point of object.particles) {
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
    const px = cx + x * scale * pulse;
    const py = cy + y * scale * pulse;
    const color: [number, number, number] = [
      Math.floor(point.r * 255),
      Math.floor(point.g * 255),
      Math.floor(point.b * 255),
    ];
    const size = clamp(point.scale * (0.66 + depth * 1.08) * scaleBias, 0.52, active ? 4.1 : 2.8);
    const alpha = clamp(point.a * (0.16 + depth * 0.66) * alphaMultiplier * roleStyle.alpha, 0.025, active ? 0.82 : 0.5);
    const angle = flowFieldAngle(px, py, elapsed, point.x * 1.7 + point.z * 0.9 + stableUnit(object.id, 31));
    drawParticleStroke(ctx, px, py, angle, clamp(size * (2.4 + controls.curiosity * 2.6 + roleStyle.trail * 1.7), 1.6, 11), size, color, alpha);
  }
}

function drawSceneMotionPathFlow(
  ctx: CanvasRenderingContext2D,
  object: SceneRenderObject,
  width: number,
  height: number,
  elapsed: number,
  sceneElapsed: number,
  active: boolean,
  cameraView: SceneCameraView,
  centralScale = 1,
) {
  const from = Array.isArray(object.beat.motion_path?.from) ? object.beat.motion_path?.from ?? [] : [];
  const to = Array.isArray(object.beat.motion_path?.to) ? object.beat.motion_path?.to ?? [] : [];
  if (from.length < 2 || to.length < 2) return;

  const fromPoint = {
    x: Number.isFinite(Number(from[0])) ? Number(from[0]) : 0,
    y: Number.isFinite(Number(from[1])) ? Number(from[1]) : 0,
  };
  const toPoint = {
    x: Number.isFinite(Number(to[0])) ? Number(to[0]) : 0,
    y: Number.isFinite(Number(to[1])) ? Number(to[1]) : 0,
  };
  const progress = sceneObjectProgress(object.beat, sceneElapsed);
  const unit = Math.min(width, height);
  const steps = 18;
  const points: Array<[number, number]> = [];
  for (let index = 0; index <= steps; index += 1) {
    const t = index / steps;
    const arc = Math.sin(t * Math.PI) * 0.22;
    const modelPoint = {
      x: fromPoint.x * (1 - t) + toPoint.x * t,
      y: fromPoint.y * (1 - t) + toPoint.y * t + arc,
    };
    const canvasPoint = scenePointToCanvas(object.beat, modelPoint, width, height, sceneElapsed, { x: 0, y: 0 }, cameraView);
    points.push([canvasPoint.x, canvasPoint.y]);
  }
  const baseAlpha = (active ? 0.18 : 0.075) * centralScale;
  drawParticlePolyline(ctx, points, [76, 230, 255], baseAlpha, unit, Math.floor(stableUnit(object.id, 73) * 1000), elapsed);

  const streamCount = active ? 13 : 7;
  for (let index = 0; index < streamCount; index += 1) {
    const local = clamp(progress - index * 0.034 + Math.sin(elapsed * 0.9 + index) * 0.01, 0, 1);
    const arc = Math.sin(local * Math.PI) * 0.22;
    const modelPoint = {
      x: fromPoint.x * (1 - local) + toPoint.x * local,
      y: fromPoint.y * (1 - local) + toPoint.y * local + arc,
    };
    const canvasPoint = scenePointToCanvas(object.beat, modelPoint, width, height, sceneElapsed, { x: 0, y: 0 }, cameraView);
    const fade = 1 - index / Math.max(1, streamCount);
    drawGuideParticle(
      ctx,
      canvasPoint.x,
      canvasPoint.y,
      unit * (0.0022 + fade * 0.0038) * centralScale,
      index % 3 === 0 ? [255, 104, 177] : [76, 230, 255],
      (active ? 0.38 : 0.18) * fade,
    );
  }
}

function drawSceneMotionParticipantFlow(
  ctx: CanvasRenderingContext2D,
  points: Array<{ object: SceneRenderObject; x: number; y: number }>,
  unit: number,
  elapsed: number,
  centralScale: number,
  groupSalt: number,
) {
  const subject = points.find((point) => sceneMotionRole(point.object.beat) === "subject");
  const source = points.find((point) => sceneMotionRole(point.object.beat) === "source");
  const target = points.find((point) => sceneMotionRole(point.object.beat) === "target");
  if (!subject || !source || !target) return false;

  const sourceSubjectTarget: Array<[number, number]> = [
    [source.x, source.y],
    [
      (source.x + subject.x) / 2 + Math.sin(elapsed * 0.27 + groupSalt) * unit * 0.018,
      (source.y + subject.y) / 2 - unit * 0.075,
    ],
    [subject.x, subject.y],
    [
      (subject.x + target.x) / 2 + Math.cos(elapsed * 0.31 + groupSalt) * unit * 0.02,
      (subject.y + target.y) / 2 - unit * 0.052,
    ],
    [target.x, target.y],
  ];

  drawParticlePolyline(ctx, sourceSubjectTarget, [76, 230, 255], 0.12 * centralScale, unit, groupSalt + 401, elapsed);

  for (let index = 0; index < 22; index += 1) {
    const leg = index < 10 ? 0 : 1;
    const localIndex = leg === 0 ? index : index - 10;
    const steps = leg === 0 ? 10 : 12;
    const from = leg === 0 ? source : subject;
    const to = leg === 0 ? subject : target;
    const t = (localIndex / steps + elapsed * (0.045 + leg * 0.018) + seeded(index, groupSalt + 503) * 0.08) % 1;
    const lift = Math.sin(t * Math.PI) * unit * (leg === 0 ? -0.07 : -0.052);
    const curl = Math.sin(t * Math.PI * 5 + elapsed * 1.4 + groupSalt) * unit * 0.018;
    const x = from.x * (1 - t) + to.x * t + curl;
    const y = from.y * (1 - t) + to.y * t + lift;
    const fade = 0.38 + Math.sin(t * Math.PI) * 0.62;
    drawGuideParticle(
      ctx,
      x,
      y,
      unit * (0.002 + fade * 0.0028) * centralScale,
      leg === 0 ? [76, 230, 255] : [255, 104, 177],
      0.24 * fade * centralScale,
    );
  }

  drawParticleEllipse(ctx, subject.x, subject.y, unit * 0.026, unit * 0.017, elapsed * 0.32, [255, 255, 255], 0.13 * centralScale, unit, groupSalt + 607, elapsed);
  return true;
}

function drawSceneGroupRelationField(
  ctx: CanvasRenderingContext2D,
  activeObject: SceneRenderObject | null,
  visibleObjects: SceneRenderObject[],
  width: number,
  height: number,
  elapsed: number,
  sceneElapsed: number,
  cameraView: SceneCameraView,
  centralScale = 1,
) {
  const groupObjects = sceneActiveGroupObjects(activeObject, visibleObjects);
  if (groupObjects.length < 2) return;
  const unit = Math.min(width, height);
  const points = groupObjects.map((object) => {
    const modelPoint = sceneMotionPathPoint(object.beat, sceneElapsed);
    const canvasPoint = scenePointToCanvas(object.beat, modelPoint, width, height, sceneElapsed, { x: 0, y: 0 }, cameraView);
    return {
      object,
      x: canvasPoint.x,
      y: canvasPoint.y,
    };
  });
  const primary = points.find((point) => sceneMotionRole(point.object.beat) === "subject") ?? points[0];
  const xs = points.map((point) => point.x);
  const ys = points.map((point) => point.y);
  const centerX = xs.reduce((total, value) => total + value, 0) / points.length;
  const centerY = ys.reduce((total, value) => total + value, 0) / points.length;
  const radiusX = clamp((Math.max(...xs) - Math.min(...xs)) * 0.56 + unit * 0.055, unit * 0.055, unit * 0.22);
  const radiusY = clamp((Math.max(...ys) - Math.min(...ys)) * 0.56 + unit * 0.042, unit * 0.042, unit * 0.18);
  const groupSalt = Math.floor(stableUnit(String(activeObject?.beat.scene_group_id ?? activeObject?.id ?? "group"), 89) * 1000);
  drawParticleEllipse(ctx, centerX, centerY, radiusX, radiusY, elapsed * 0.07, [76, 230, 255], 0.045 * centralScale, unit, groupSalt, elapsed);
  const renderedMotionFlow = drawSceneMotionParticipantFlow(ctx, points, unit, elapsed, centralScale, groupSalt);

  points.slice(1).forEach((target, index) => {
    if (target.object.id === primary.object.id) return;
    if (renderedMotionFlow && sceneMotionRole(target.object.beat)) return;
    const relationLift = target.object.beat.visual_affordance === "organic_structure" || primary.object.beat.visual_affordance === "organic_structure"
      ? -unit * 0.055
      : unit * 0.028 * Math.sin(elapsed * 0.31 + index);
    const midX = (primary.x + target.x) / 2 + Math.sin(elapsed * 0.23 + index * 1.7) * unit * 0.012;
    const midY = (primary.y + target.y) / 2 + relationLift;
    const alpha = (target.object.beat.op === "move" || target.object.beat.motion_path ? 0.13 : 0.075) * centralScale;
    drawParticlePolyline(
      ctx,
      [[primary.x, primary.y], [midX, midY], [target.x, target.y]],
      index % 2 === 0 ? [76, 230, 255] : [255, 104, 177],
      alpha,
      unit,
      groupSalt + index * 31,
      elapsed,
    );
  });
}

function drawSceneFocusParticles(
  ctx: CanvasRenderingContext2D,
  sceneObjects: SceneRenderObject[],
  activeObjectId: string | null,
  width: number,
  height: number,
  elapsed: number,
  sceneElapsed: number,
  controls: { arousal: number; curiosity: number; speaking_energy: number; resting: boolean },
  centralScale = 1,
) {
  ctx.clearRect(0, 0, width, height);
  const centerGlow = ctx.createRadialGradient(width / 2, height / 2, 0, width / 2, height / 2, Math.max(width, height) * 0.48);
  centerGlow.addColorStop(0, "rgba(255,255,255,0.035)");
  centerGlow.addColorStop(0.38, "rgba(43,223,255,0.03)");
  centerGlow.addColorStop(1, "rgba(0,0,0,0)");
  ctx.fillStyle = centerGlow;
  ctx.fillRect(0, 0, width, height);

  const visibleObjects = sceneObjects.filter((object) => sceneObjectAlpha(object.beat, sceneElapsed, object.id === activeObjectId) > 0.02);
  const activeObject = visibleObjects.find((object) => object.id === activeObjectId) ?? visibleObjects[0] ?? null;
  const cameraView = sceneGroupCameraView(activeObject, visibleObjects, sceneElapsed);
  cameraView.zoom = clamp(cameraView.zoom * centralScale, 0.82, 1.82);
  drawSceneGroupRelationField(ctx, activeObject, visibleObjects, width, height, elapsed, sceneElapsed, cameraView, centralScale);
  visibleObjects.forEach((object) => {
    const sameGroup = sameSceneGroup(object.beat, activeObject?.beat);
    drawSceneMotionPathFlow(ctx, object, width, height, elapsed, sceneElapsed, object.id === activeObjectId || sameGroup, cameraView, centralScale);
  });

  visibleObjects.forEach((object) => {
    const sameGroup = sameSceneGroup(object.beat, activeObject?.beat);
    drawSceneObjectCloud(ctx, object, width, height, elapsed, sceneElapsed, object.id === activeObjectId || sameGroup, controls, cameraView, centralScale);
  });
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
  sceneFocus = false,
  scenePlan = null,
  activeSpeechBeatIndex = -1,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [archetype, setArchetype] = useState<Archetype>(() => (mode === "product" ? "constellation" : "orb"));
  const [seedNonce, setSeedNonce] = useState(0);
  const [frame, setFrame] = useState<ImaginationFrame | null>(null);
  const [status, setStatus] = useState<Record<string, any> | null>(null);
  const [error, setError] = useState("");
  const [reducedMotion, setReducedMotion] = useState(false);
  const [sceneStartedAt, setSceneStartedAt] = useState(0);
  const [activeSceneBeatIndex, setActiveSceneBeatIndex] = useState(-1);
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
  const stageMode = sceneFocus || scenePlan?.stage_layout === "scene_focus";
  const centralSceneScale = scenePlanCentralScale(scenePlan);
  const syncedBeatIndex = activeSpeechBeatIndex >= 0 ? activeSpeechBeatIndex : activeSceneBeatIndex;
  const activeSceneBeat = syncedBeatIndex >= 0 && Array.isArray(scenePlan?.beats) ? scenePlan?.beats?.[syncedBeatIndex] : null;
  const sceneObjects = useMemo(() => buildSceneRenderObjects(scenePlan, budget), [budget, scenePlan]);
  const activeSceneObjectId = activeSceneBeat ? sceneObjectId(activeSceneBeat, Math.max(0, syncedBeatIndex)) : null;
  const activeSceneGroupId = activeSceneBeat?.scene_group_id ?? "";
  const activeSceneGroupSize = activeSceneGroupId ? sceneObjects.filter((object) => sameSceneGroup(object.beat, activeSceneBeat)).length : 0;
  const activeSceneFocusBasis = activeSpeechBeatIndex >= 0 ? "speech_timeline" : activeSceneBeat ? "scene_timer" : "ambient_field";
  const activeSceneRole = activeSceneBeat?.semantic_role ?? "none";
  const activeSceneBehavior = activeSceneBeat?.particle_behavior ?? "none";

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
    const beats = Array.isArray(scenePlan?.beats) ? scenePlan?.beats ?? [] : [];
    if (!beats.length) {
      setActiveSceneBeatIndex(-1);
      return;
    }
    setSceneStartedAt(performance.now());
    setActiveSceneBeatIndex(0);
    const nextSceneArchetype = sceneArchetype(scenePlan, 0);
    if (!nextSceneArchetype) return;
    setArchetype(nextSceneArchetype);
    setSeedNonce((value) => value + 1);
  }, [scenePlan]);

  useEffect(() => {
    const beats = Array.isArray(scenePlan?.beats) ? scenePlan?.beats ?? [] : [];
    if (!stageMode || !beats.length || reducedMotion) return undefined;
    const timer = window.setInterval(() => {
      const elapsedSeconds = Math.max(0, (performance.now() - sceneStartedAt) / 1000);
      const nextIndex = sceneBeatIndex(scenePlan, elapsedSeconds);
      setActiveSceneBeatIndex((current) => {
        if (nextIndex === current) return current;
        const nextSceneArchetype = sceneArchetype(scenePlan, nextIndex);
        if (nextSceneArchetype) {
          setArchetype(nextSceneArchetype);
          setSeedNonce((value) => value + 1);
        }
        return nextIndex;
      });
    }, 180);
    return () => window.clearInterval(timer);
  }, [reducedMotion, scenePlan, sceneStartedAt, stageMode]);

  useEffect(() => {
    if (mode !== "product" || reducedMotion) return undefined;
    if (stageMode) return undefined;
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
  }, [controls, mode, reducedMotion, stageMode]);

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
      const elapsed = reducedMotion ? 0.5 : (performance.now() - startedAt) / 1000;
      const sceneElapsed = sceneStartedAt ? Math.max(0, (performance.now() - sceneStartedAt) / 1000) : elapsed;
      const activeTransform = sceneTransform(activeSceneBeat, stageMode, sceneElapsed);
      if (stageMode && sceneObjects.length) {
        drawSceneFocusParticles(ctx, sceneObjects, activeSceneObjectId, width, height, elapsed, sceneElapsed, controls, centralSceneScale);
      } else {
        drawParticles(
          ctx,
          particles,
          activeArchetype,
          width,
          height,
          elapsed,
          controls,
          !stageMode && !interactive && mode === "product",
          mode === "lab",
          activeTransform,
        );
      }
      if (!reducedMotion) animationId = window.requestAnimationFrame(render);
    };
    render();
    return () => window.cancelAnimationFrame(animationId);
  }, [activeArchetype, activeSceneBeat, activeSceneObjectId, centralSceneScale, controls, interactive, mode, particles, reducedMotion, sceneObjects, sceneStartedAt, stageMode]);

  function handleClick() {
    if (state === "listening") {
      onCancel?.();
    } else {
      onActivate?.();
    }
  }

  const canvas = <canvas ref={canvasRef} />;

  return (
    <section
      className={`splatra-imagination-field ${className ?? ""}`}
      data-mode={mode}
      data-state={state}
      data-scene-objects={sceneObjects.length}
      data-active-speech-beat={activeSpeechBeatIndex >= 0 ? activeSpeechBeatIndex : "none"}
      data-active-scene-object={activeSceneObjectId || "none"}
      data-active-scene-role={activeSceneRole}
      data-active-scene-behavior={activeSceneBehavior}
      data-active-scene-focus-basis={activeSceneFocusBasis}
      data-active-scene-group={activeSceneGroupId || "none"}
      data-active-scene-group-size={activeSceneGroupSize}
    >
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
        <span className="splatra-imagination-product-label" data-scene-beat={activeSceneBeat?.op ?? "ambient"} aria-hidden="true">
          imagination / {ARCHETYPE_LABELS[activeArchetype]}
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
