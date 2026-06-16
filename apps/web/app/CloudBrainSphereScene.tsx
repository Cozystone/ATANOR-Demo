"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";

type AnyRecord = Record<string, any>;

export type CloudBrainSphereStats = {
  logicalNodes: string;
  actualMaterializedNodes: number;
  renderedNodes: number;
  activeTiles: number;
  zoomLevel: number;
  renderBudgetNodes: number;
  renderBudgetEdges: number;
  compressionUsed: boolean;
  semanticAggregateNodesUsed: boolean;
  shellMode: boolean;
  actualNodeMode: boolean;
};

type Props = {
  edgeOpacity?: number;
  highEnd?: boolean;
  onStats?: (stats: CloudBrainSphereStats) => void;
};

const MAX_RENDERED_POINTS_BASELINE = 5000;
const MAX_RENDERED_POINTS_HIGH_END = 50000;
const MAX_RENDERED_EDGES_BASELINE = 10000;
const MAX_RENDERED_EDGES_HIGH_END = 100000;

function shellPoint(index: number, total: number, radius: number) {
  const golden = Math.PI * (3 - Math.sqrt(5));
  const y = 1 - (index / Math.max(1, total - 1)) * 2;
  const r = Math.sqrt(Math.max(0, 1 - y * y));
  const theta = golden * index;
  return new THREE.Vector3(Math.cos(theta) * r * radius, y * radius, Math.sin(theta) * r * radius);
}

async function apiJson<T>(path: string): Promise<T> {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error(`${path} failed: ${response.status}`);
  return response.json() as Promise<T>;
}

export default function CloudBrainSphereScene({ edgeOpacity = 0.2, highEnd = false, onStats }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const sceneRef = useRef<{
    renderer: THREE.WebGLRenderer;
    scene: THREE.Scene;
    camera: THREE.PerspectiveCamera;
    shell: THREE.Points;
    nodes: THREE.Points;
    edges: THREE.LineSegments;
    animation: number;
    rotation: number;
  } | null>(null);
  const [zoomLevel, setZoomLevel] = useState(0);
  const [manifest, setManifest] = useState<AnyRecord | null>(null);
  const [materialized, setMaterialized] = useState<AnyRecord | null>(null);
  const budgets = useMemo(() => ({
    nodes: highEnd ? MAX_RENDERED_POINTS_HIGH_END : MAX_RENDERED_POINTS_BASELINE,
    edges: highEnd ? MAX_RENDERED_EDGES_HIGH_END : MAX_RENDERED_EDGES_BASELINE,
  }), [highEnd]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const nextManifest = await apiJson<AnyRecord>("/api/cloud-brain/sphere/manifest").catch(() => null);
      const nextMaterialized = await apiJson<AnyRecord>(
        `/api/cloud-brain/sphere/materialize?tile_id=sphere_l0_x0000_y0000_r0&zoom=${zoomLevel}&budget_nodes=${budgets.nodes}&budget_edges=${budgets.edges}`,
      ).catch(() => null);
      if (cancelled) return;
      setManifest(nextManifest);
      setMaterialized(nextMaterialized);
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [budgets.edges, budgets.nodes, zoomLevel]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(container.clientWidth, container.clientHeight);
    container.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(42, Math.max(1, container.clientWidth) / Math.max(1, container.clientHeight), 0.1, 100);
    camera.position.set(0, 0, 3.1);

    const shellGeometry = new THREE.BufferGeometry();
    const shellCount = 1800;
    const shellPositions = new Float32Array(shellCount * 3);
    for (let index = 0; index < shellCount; index += 1) {
      const point = shellPoint(index, shellCount, 1.08);
      shellPositions[index * 3] = point.x;
      shellPositions[index * 3 + 1] = point.y;
      shellPositions[index * 3 + 2] = point.z;
    }
    shellGeometry.setAttribute("position", new THREE.BufferAttribute(shellPositions, 3));
    const shell = new THREE.Points(
      shellGeometry,
      new THREE.PointsMaterial({
        color: new THREE.Color("#55708f"),
        opacity: 0.18,
        transparent: true,
        size: 0.008,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      }),
    );
    scene.add(shell);

    const nodes = new THREE.Points(
      new THREE.BufferGeometry(),
      new THREE.PointsMaterial({
        color: new THREE.Color("#ff9f1c"),
        opacity: 0.92,
        transparent: true,
        size: 0.026,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      }),
    );
    scene.add(nodes);

    const edges = new THREE.LineSegments(
      new THREE.BufferGeometry(),
      new THREE.LineBasicMaterial({
        color: new THREE.Color("#f8fbff"),
        opacity: Math.max(0.04, Math.min(0.72, edgeOpacity)),
        transparent: true,
        blending: THREE.AdditiveBlending,
      }),
    );
    scene.add(edges);

    const state = { renderer, scene, camera, shell, nodes, edges, animation: 0, rotation: 0 };
    sceneRef.current = state;

    const resize = () => {
      const width = Math.max(1, container.clientWidth);
      const height = Math.max(1, container.clientHeight);
      renderer.setSize(width, height);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    };
    const animate = () => {
      state.rotation += 0.0018;
      shell.rotation.y = state.rotation;
      nodes.rotation.y = state.rotation;
      edges.rotation.y = state.rotation;
      renderer.render(scene, camera);
      state.animation = window.requestAnimationFrame(animate);
    };
    resize();
    animate();
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
      window.cancelAnimationFrame(state.animation);
      renderer.dispose();
      shellGeometry.dispose();
      (shell.material as THREE.Material).dispose();
      (nodes.geometry as THREE.BufferGeometry).dispose();
      (nodes.material as THREE.Material).dispose();
      (edges.geometry as THREE.BufferGeometry).dispose();
      (edges.material as THREE.Material).dispose();
      renderer.domElement.remove();
      sceneRef.current = null;
    };
  }, []);

  useEffect(() => {
    const state = sceneRef.current;
    if (!state) return;
    const nodeRows = Array.isArray(materialized?.materialized_nodes) ? materialized.materialized_nodes : [];
    const positions = new Float32Array(nodeRows.length * 3);
    nodeRows.forEach((node: AnyRecord, index: number) => {
      positions[index * 3] = Number(node.x ?? 0);
      positions[index * 3 + 1] = Number(node.y ?? 0);
      positions[index * 3 + 2] = Number(node.z ?? 0);
    });
    const nodeGeometry = new THREE.BufferGeometry();
    nodeGeometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    state.nodes.geometry.dispose();
    state.nodes.geometry = nodeGeometry;

    const nodeById = new Map(nodeRows.map((node: AnyRecord) => [String(node.cloud_node_id), node]));
    const edgeRows = Array.isArray(materialized?.materialized_edges) ? materialized.materialized_edges : [];
    const edgePositions: number[] = [];
    for (const edge of edgeRows) {
      const source = nodeById.get(String(edge.source));
      const target = nodeById.get(String(edge.target));
      if (!source || !target) continue;
      edgePositions.push(Number(source.x ?? 0), Number(source.y ?? 0), Number(source.z ?? 0));
      edgePositions.push(Number(target.x ?? 0), Number(target.y ?? 0), Number(target.z ?? 0));
    }
    const edgeGeometry = new THREE.BufferGeometry();
    edgeGeometry.setAttribute("position", new THREE.Float32BufferAttribute(edgePositions, 3));
    state.edges.geometry.dispose();
    state.edges.geometry = edgeGeometry;
    const edgeMaterial = state.edges.material as THREE.LineBasicMaterial;
    edgeMaterial.opacity = Math.max(0.04, Math.min(0.72, edgeOpacity));

    onStats?.({
      logicalNodes: String(manifest?.logical_total_nodes ?? materialized?.logical_nodes_addressable ?? "0"),
      actualMaterializedNodes: Number(manifest?.actual_materialized_nodes ?? 0),
      renderedNodes: Number(materialized?.rendered_nodes ?? nodeRows.length),
      activeTiles: Math.max(1, Number(Array.isArray(materialized?.child_tiles) ? materialized.child_tiles.length : 1)),
      zoomLevel,
      renderBudgetNodes: Number(materialized?.render_budget_nodes ?? budgets.nodes),
      renderBudgetEdges: Number(materialized?.render_budget_edges ?? budgets.edges),
      compressionUsed: Boolean(materialized?.compression_used || manifest?.compression_used),
      semanticAggregateNodesUsed: Boolean(materialized?.semantic_aggregate_nodes_used || manifest?.semantic_aggregate_nodes_used),
      shellMode: String(materialized?.render_mode ?? "shell") === "shell",
      actualNodeMode: String(materialized?.render_mode ?? "") === "actual_nodes",
    });
  }, [budgets.edges, budgets.nodes, edgeOpacity, manifest, materialized, onStats, zoomLevel]);

  return (
    <div
      className="atanor-cloud-sphere-scene"
      ref={containerRef}
      onWheel={(event) => {
        event.preventDefault();
        setZoomLevel((current) => Math.max(0, Math.min(6, current + (event.deltaY > 0 ? -1 : 1))));
      }}
    >
      <div className="atanor-cloud-sphere-overlay">
        <span>Trillion Sphere Renderer</span>
        <strong>{materialized?.render_mode ?? "shell"}</strong>
      </div>
    </div>
  );
}
