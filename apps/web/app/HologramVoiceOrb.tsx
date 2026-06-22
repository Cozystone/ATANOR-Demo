"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";

export type HologramVoiceOrbState =
  | "idle"
  | "listening"
  | "thinking"
  | "speaking"
  | "resting"
  | "approval_needed"
  | "blocked";

type HologramVoiceOrbProps = {
  state: HologramVoiceOrbState;
  onActivate: () => void;
  onCancel: () => void;
};

const PARTICLE_COUNT = 9600;
const SHELL_PARTICLE_COUNT = 5200;
const SHAPE_COUNT = 6;
const COLOR_STOPS = [
  new THREE.Color("#25f4ff"),
  new THREE.Color("#42a8ff"),
  new THREE.Color("#bf73ff"),
  new THREE.Color("#ff64d8"),
];

function siriShapePoint(shape: number, t: number, seed: number): THREE.Vector3 {
  const ribbon = Math.floor(seed * 3);
  const phase = shape * 0.72 + ribbon * 2.05;
  const angle = t * Math.PI * 2.45 + phase;
  const band = (seed - Math.floor(seed * 3) / 3) * 3 - 0.5;
  const radius = 1.05 + Math.sin(angle * 2.1 + shape) * 0.13;
  const twist = Math.sin(t * Math.PI * 2 + phase) * 0.42;
  const vertical = Math.sin(angle * 1.1 + phase) * (0.36 + ribbon * 0.035) + band * 0.16;
  const x = Math.cos(angle + twist) * radius * (0.82 + ribbon * 0.045);
  const z = Math.sin(angle + twist) * radius * (0.42 + ribbon * 0.08);
  const y = vertical;
  const point = new THREE.Vector3(x, y, z);
  point.applyAxisAngle(new THREE.Vector3(0, 0, 1), -0.42 + ribbon * 0.34 + Math.sin(shape) * 0.06);
  point.applyAxisAngle(new THREE.Vector3(1, 0, 0), 0.45 + ribbon * 0.2);
  point.multiplyScalar(1.12);
  return point;
}

function buildGeometry() {
  const positions = new Float32Array(PARTICLE_COUNT * 3);
  const morphs = Array.from({ length: SHAPE_COUNT }, () => new Float32Array(PARTICLE_COUNT * 3));
  const colors = new Float32Array(PARTICLE_COUNT * 3);
  const sizes = new Float32Array(PARTICLE_COUNT);

  for (let i = 0; i < PARTICLE_COUNT; i += 1) {
    const t = i / PARTICLE_COUNT;
    const seed = (Math.sin(i * 12.9898) * 43758.5453) % 1;
    const positiveSeed = seed < 0 ? seed + 1 : seed;
    const ribbon = Math.floor(positiveSeed * 3);
    const color = COLOR_STOPS[ribbon].clone();
    color.lerp(COLOR_STOPS[ribbon + 1], 0.18 + positiveSeed * 0.28);

    colors[i * 3] = color.r;
    colors[i * 3 + 1] = color.g;
    colors[i * 3 + 2] = color.b;
    sizes[i] = 0.014 + positiveSeed * 0.018;

    for (let shape = 0; shape < SHAPE_COUNT; shape += 1) {
      const point = siriShapePoint(shape, t, positiveSeed);
      morphs[shape][i * 3] = point.x;
      morphs[shape][i * 3 + 1] = point.y;
      morphs[shape][i * 3 + 2] = point.z;
    }

    positions[i * 3] = morphs[0][i * 3];
    positions[i * 3 + 1] = morphs[0][i * 3 + 1];
    positions[i * 3 + 2] = morphs[0][i * 3 + 2];
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));
  geometry.setAttribute("size", new THREE.BufferAttribute(sizes, 1));
  return { geometry, morphs };
}

function buildShellGeometry() {
  const positions = new Float32Array(SHELL_PARTICLE_COUNT * 3);
  const colors = new Float32Array(SHELL_PARTICLE_COUNT * 3);
  const sizes = new Float32Array(SHELL_PARTICLE_COUNT);
  const shellColor = new THREE.Color("#5ee7ff");
  const rimColor = new THREE.Color("#8d7cff");
  const golden = Math.PI * (3 - Math.sqrt(5));

  for (let i = 0; i < SHELL_PARTICLE_COUNT; i += 1) {
    const t = (i + 0.5) / SHELL_PARTICLE_COUNT;
    const theta = i * golden;
    const y = 1 - 2 * t;
    const ring = Math.sqrt(Math.max(0, 1 - y * y));
    const radius = 1.86 + Math.sin(theta * 2.1) * 0.012;
    const x = Math.cos(theta) * ring * radius;
    const z = Math.sin(theta) * ring * radius;
    positions[i * 3] = x;
    positions[i * 3 + 1] = y * radius;
    positions[i * 3 + 2] = z;

    const edgeGlow = Math.pow(Math.abs(x) * 0.52 + Math.abs(y) * 0.2, 1.4);
    const color = shellColor.clone().lerp(rimColor, Math.min(1, edgeGlow * 0.55));
    colors[i * 3] = color.r;
    colors[i * 3 + 1] = color.g;
    colors[i * 3 + 2] = color.b;
    sizes[i] = 0.0045 + edgeGlow * 0.0065;
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));
  geometry.setAttribute("size", new THREE.BufferAttribute(sizes, 1));
  return geometry;
}

export default function HologramVoiceOrb({ state, onActivate, onCancel }: HologramVoiceOrbProps) {
  const hostRef = useRef<HTMLButtonElement | null>(null);
  const stateRef = useRef(state);

  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return undefined;
    const activeHost = host;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 100);
    camera.position.set(0, 0, 7);

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, powerPreference: "high-performance" });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setClearColor(0x000000, 0);
    activeHost.appendChild(renderer.domElement);

    const { geometry, morphs } = buildGeometry();
    const material = new THREE.PointsMaterial({
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      opacity: 0.9,
      size: 0.045,
      sizeAttenuation: true,
      transparent: true,
      vertexColors: true,
    });
    const points = new THREE.Points(geometry, material);
    scene.add(points);

    const glow = new THREE.Mesh(
      new THREE.SphereGeometry(1.92, 48, 32),
      new THREE.MeshBasicMaterial({
        color: new THREE.Color("#102a3c"),
        opacity: 0.09,
        transparent: true,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      }),
    );
    scene.add(glow);

    const shell = new THREE.Mesh(
      new THREE.SphereGeometry(1.84, 96, 64),
      new THREE.MeshBasicMaterial({
        color: new THREE.Color("#4ec9ff"),
        opacity: 0.055,
        transparent: true,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
        side: THREE.DoubleSide,
      }),
    );
    scene.add(shell);

    const shellGeometry = buildShellGeometry();
    const shellParticleMaterial = new THREE.PointsMaterial({
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      opacity: 0.22,
      size: 0.022,
      sizeAttenuation: true,
      transparent: true,
      vertexColors: true,
    });
    const shellParticles = new THREE.Points(shellGeometry, shellParticleMaterial);
    scene.add(shellParticles);

    const clock = new THREE.Clock();
    let animationId = 0;
    let activeShape = 0;
    let nextShape = 1;
    let morphStart = 0;

    function resize() {
      const rect = activeHost.getBoundingClientRect();
      const size = Math.max(280, Math.min(rect.width || 520, rect.height || 520));
      renderer.setSize(size, size, false);
      camera.aspect = 1;
      camera.updateProjectionMatrix();
    }

    function renderFrame() {
      const elapsed = clock.getElapsedTime();
      if (elapsed - morphStart > 4.2) {
        activeShape = nextShape;
        nextShape = (nextShape + 1 + Math.floor(elapsed) % (SHAPE_COUNT - 1)) % SHAPE_COUNT;
        if (nextShape === activeShape) nextShape = (nextShape + 1) % SHAPE_COUNT;
        morphStart = elapsed;
      }

      const morphT = Math.min(1, Math.max(0, (elapsed - morphStart) / 1.65));
      const ease = morphT * morphT * (3 - 2 * morphT);
      const positions = geometry.getAttribute("position") as THREE.BufferAttribute;
      const from = morphs[activeShape];
      const to = morphs[nextShape];
      const pulse = stateRef.current === "listening" ? 1.08 : stateRef.current === "speaking" ? 1.12 : stateRef.current === "thinking" ? 1.06 : 1;

      for (let i = 0; i < PARTICLE_COUNT * 3; i += 3) {
        positions.array[i] = (from[i] + (to[i] - from[i]) * ease) * pulse;
        positions.array[i + 1] = (from[i + 1] + (to[i + 1] - from[i + 1]) * ease) * pulse;
        positions.array[i + 2] = (from[i + 2] + (to[i + 2] - from[i + 2]) * ease) * pulse;
      }
      positions.needsUpdate = true;

      material.opacity = stateRef.current === "resting" ? 0.56 : stateRef.current === "blocked" ? 0.72 : 0.86;
      points.rotation.y = elapsed * 0.28;
      points.rotation.z = Math.sin(elapsed * 0.37) * 0.08;
      glow.scale.setScalar(1 + Math.sin(elapsed * 1.15) * 0.025);
      shell.rotation.y = elapsed * 0.08;
      shell.rotation.x = Math.sin(elapsed * 0.31) * 0.035;
      shellParticles.rotation.y = -elapsed * 0.04;
      shellParticles.rotation.x = Math.sin(elapsed * 0.2) * 0.025;
      renderer.render(scene, camera);
      animationId = window.requestAnimationFrame(renderFrame);
    }

    resize();
    renderFrame();
    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(activeHost);

    return () => {
      window.cancelAnimationFrame(animationId);
      resizeObserver.disconnect();
      geometry.dispose();
      material.dispose();
      glow.geometry.dispose();
      (glow.material as THREE.Material).dispose();
      shell.geometry.dispose();
      (shell.material as THREE.Material).dispose();
      shellGeometry.dispose();
      shellParticleMaterial.dispose();
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, []);

  return (
    <button
      ref={hostRef}
      type="button"
      className="hologram-voice-orb"
      data-state={state}
      aria-label="ATANOR hologram voice orb"
      aria-pressed={state === "listening"}
      onClick={state === "listening" ? onCancel : onActivate}
    />
  );
}
