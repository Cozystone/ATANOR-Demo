"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";

/* PureField — the SPLATRA cognitive plane under the owner's four absolute rules:
   1. NO lines, ever. There is no THREE.Line anywhere in this file.
   2. Points ONLY: one THREE.Points, one PointsMaterial. No boxes, no geometry.
   3. Gaussian grains: each dot is a soft self-luminous photon (radial-blur
      sprite), never a hard pixel.
   4. Fluid drift: layered trigonometric displacement — deep-sea plankton /
      nebula motion. No grids, no scaffolds, no shapes.
   Everything animates through refs — React re-renders (typing, state) can
   NEVER reset rotation or positions. Energy nudges drift speed only. */

type PureFieldProps = {
  budget?: number;
  energy?: number; // 0 calm nebula … 1 charged attention (drift speed only)
};

function gaussian(): number {
  // Box–Muller: soft cloud distribution, dense core and thin halo
  let u = 0;
  let v = 0;
  while (u === 0) u = Math.random();
  while (v === 0) v = Math.random();
  return Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2.0 * Math.PI * v);
}

function grainTexture(): THREE.Texture {
  const c = document.createElement("canvas");
  c.width = 64;
  c.height = 64;
  const g = c.getContext("2d")!;
  const grad = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  grad.addColorStop(0, "rgba(255,255,255,1)");
  grad.addColorStop(0.35, "rgba(255,255,255,0.55)");
  grad.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = grad;
  g.fillRect(0, 0, 64, 64);
  const tex = new THREE.CanvasTexture(c);
  tex.needsUpdate = true;
  return tex;
}

const PALETTE = [
  new THREE.Color("#1fd4e8"),
  new THREE.Color("#7f7fe8"),
  new THREE.Color("#b06ae0"),
  new THREE.Color("#cdd6e2"),
];

export default function PureField({ budget = 5200, energy = 0.15 }: PureFieldProps) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const energyRef = useRef(energy);
  useEffect(() => {
    energyRef.current = energy;
  }, [energy]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return undefined;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(46, 1, 0.1, 100);
    camera.position.set(0, 0, 10);
    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: false, powerPreference: "high-performance" });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
    renderer.setClearColor(0x000000, 0);
    host.appendChild(renderer.domElement);

    const n = Math.max(900, budget);
    const base = new Float32Array(n * 3);
    const pos = new Float32Array(n * 3);
    const col = new Float32Array(n * 3);
    const phase = new Float32Array(n);
    for (let i = 0; i < n; i += 1) {
      // wide flat-ish nebula: broad in x, softer in y, shallow in z
      base[i * 3] = gaussian() * 5.2;
      base[i * 3 + 1] = gaussian() * 3.0;
      base[i * 3 + 2] = gaussian() * 2.2;
      const c = PALETTE[Math.floor(Math.random() * PALETTE.length)];
      const dim = 0.35 + Math.random() * 0.5;
      col[i * 3] = c.r * dim;
      col[i * 3 + 1] = c.g * dim;
      col[i * 3 + 2] = c.b * dim;
      phase[i] = Math.random() * Math.PI * 2;
    }
    pos.set(base);

    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    geo.setAttribute("color", new THREE.BufferAttribute(col, 3));
    const mat = new THREE.PointsMaterial({
      map: grainTexture(),
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      transparent: true,
      opacity: 0.75,
      size: 0.09,
      sizeAttenuation: true,
      vertexColors: true,
    });
    const points = new THREE.Points(geo, mat);
    scene.add(points);

    const clock = new THREE.Clock();
    let raf = 0;
    let last = 0;
    const STEP = 1 / 30; // soft motion needs no more; halves CPU on soft-GL

    function resize() {
      const r = host!.getBoundingClientRect();
      const w = Math.max(320, r.width || 1280);
      const h = Math.max(240, r.height || 800);
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    }

    function frame() {
      const t = clock.getElapsedTime();
      if (t - last >= STEP) {
        last = t;
        const e = 0.35 + energyRef.current * 1.1;
        const attr = geo.getAttribute("position") as THREE.BufferAttribute;
        for (let i = 0; i < n; i += 1) {
          const bx = base[i * 3];
          const by = base[i * 3 + 1];
          const bz = base[i * 3 + 2];
          const p = phase[i];
          // two layered incommensurate waves — drift, never a grid
          attr.array[i * 3] = bx + Math.sin(t * 0.11 * e + p + by * 0.35) * 0.55 + Math.sin(t * 0.041 + p * 1.7) * 0.3;
          attr.array[i * 3 + 1] = by + Math.cos(t * 0.09 * e + p * 1.3 + bx * 0.22) * 0.42 + Math.cos(t * 0.033 + p) * 0.25;
          attr.array[i * 3 + 2] = bz + Math.sin(t * 0.07 * e + p * 0.6 + bx * 0.1) * 0.3;
        }
        attr.needsUpdate = true;
        points.rotation.y = t * 0.008; // one slow, never-resetting breath
      }
      renderer.render(scene, camera);
      raf = window.requestAnimationFrame(frame);
    }

    resize();
    frame();
    const ro = new ResizeObserver(resize);
    ro.observe(host);
    return () => {
      window.cancelAnimationFrame(raf);
      ro.disconnect();
      geo.dispose();
      mat.map?.dispose();
      mat.dispose();
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, [budget]);

  return <div ref={hostRef} style={{ position: "absolute", inset: 0 }} />;
}
