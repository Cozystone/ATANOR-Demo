"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";

export type Rag3DNode = {
  id: string;
  label: string;
  type: string;
  x: number;
  y: number;
  z: number;
  confidence?: number;
  source_type?: string;
  sourceType?: string;
  cluster_id?: string;
};

export type Rag3DEdge = {
  source: string;
  target: string;
  relation: string;
  weight?: number;
  confidence?: number;
  source_type?: string;
};

export type Rag3DGraph = {
  nodes: Rag3DNode[];
  edges: Rag3DEdge[];
  traversal_path?: string[];
};

export type Rag3DControl = {
  serial: number;
  action: "zoom-in" | "zoom-out" | "left" | "right" | "up" | "down" | "reset";
};

export type Rag3DVisualState = "loading" | "learning" | "activating" | "completed" | "idle" | "low_memory_viewer";

type Rag3DSceneProps = {
  graph: Rag3DGraph | null;
  activeEdgeKeys?: string[];
  activeNodeIds?: string[];
  newNodeIds?: string[];
  control?: Rag3DControl;
  preserveSourceCoordinates?: boolean;
  onViewportChange?: (viewport: {
    cameraZ: number;
    focus: { x: number; y: number; z: number };
    radius: number;
  }) => void;
  onSelect?: (node: Rag3DNode) => void;
  theme?: "light" | "dark";
  visualState?: Rag3DVisualState;
};

type VisibleEdge = Rag3DEdge & {
  active: boolean;
  index: number;
};

type SignalHalo = {
  bornAt: number;
  id: string;
  newNode: boolean;
  position: THREE.Vector3;
  scale: number;
};

type EdgePulse = {
  phase: number;
  source: string;
  target: string;
};

type SceneState = {
  activeEdgeKeys: Set<string>;
  activeNodeIds: Set<string>;
  activationHops: Map<string, number>;
  activationEdgeIntensity: Map<string, number>;
  camera: THREE.PerspectiveCamera;
  coordinateMutationWarned: boolean;
  dynamicObjects: THREE.Object3D[];
  edgeCapacity: number;
  edgeColorArray: Float32Array | null;
  edgeGeometry: THREE.BufferGeometry | null;
  edgeLines: THREE.LineSegments | null;
  edgePositionArray: Float32Array | null;
  edgePositionBufferDirty: boolean;
  edgePulseCount: number;
  frame: number;
  frozenPositionSnapshot: Float32Array | null;
  graphEdges: Rag3DEdge[];
  graphNodes: Rag3DNode[];
  group: THREE.Group;
  haloCapacity: number;
  haloItems: SignalHalo[];
  haloMesh: THREE.InstancedMesh | null;
  knownNodeIds: Set<string>;
  lastFitDistance: number;
  lastGraphNodeCount: number;
  lastViewportEmitFrame: number;
  layoutDiagnostics: Record<string, number | string | number[]>;
  newNodeIds: Set<string>;
  nodeBornAt: Map<string, number>;
  nodeCapacity: number;
  nodeColorArray: Float32Array | null;
  nodeGeometry: THREE.BufferGeometry | null;
  nodeIndexById: Map<string, number>;
  nodePoints: THREE.Points | null;
  nodePositionArray: Float32Array | null;
  nodePositionBufferDirty: boolean;
  nodePositionById: Map<string, THREE.Vector3>;
  nodeTargetById: Map<string, THREE.Vector3>;
  pointNodes: Rag3DNode[];
  pulseCapacity: number;
  pulseItems: EdgePulse[];
  pulseMesh: THREE.InstancedMesh | null;
  renderer: THREE.WebGLRenderer;
  scene: THREE.Scene;
  startedAt: number;
  userCameraControlUntilFrame: number;
  visibleEdges: VisibleEdge[];
  visualState: Rag3DVisualState;
  preserveSourceCoordinates: boolean;
  onViewportChange?: Rag3DSceneProps["onViewportChange"];
};

const BASE_EDGE_COLOR = 0x334155;
const BASE_EDGE_ACTIVE_NEAR = 0x64748b;
const NEON_ORANGE = 0xff5500;
const COLD_LABEL = "#e8e8e2";
const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));
const NEW_NODE_ANIMATION_SECONDS = 1.5;

const baseEdgeColor = new THREE.Color(BASE_EDGE_COLOR);
const nearActiveEdgeColor = new THREE.Color(BASE_EDGE_ACTIVE_NEAR);
const neonOrangeColor = new THREE.Color(NEON_ORANGE);
const localMemoryColor = new THREE.Color(0xd6dee8);
const representativeNodeColor = new THREE.Color(0x526170);
const cloudFragmentColor = new THREE.Color(0x3fd7ff);
const tempColor = new THREE.Color();
const tempMatrix = new THREE.Matrix4();
const tempQuaternion = new THREE.Quaternion();
const tempRingQuaternion = new THREE.Quaternion().setFromEuler(new THREE.Euler(Math.PI / 2, 0, 0));
const tempScale = new THREE.Vector3();
const tempPosition = new THREE.Vector3();

function edgeKey(source: string, target: string) {
  return `${source}:${target}`;
}

function edgeIsExplicitlyActive(activeEdgeKeys: Set<string>, source: string, target: string) {
  return activeEdgeKeys.has(edgeKey(source, target)) || activeEdgeKeys.has(edgeKey(target, source));
}

function coordinateAnimationAllowed(visualState: Rag3DVisualState) {
  return visualState === "loading" || visualState === "learning";
}

function movingPulseAllowed(visualState: Rag3DVisualState) {
  return visualState === "loading" || visualState === "learning";
}

function resolveVisualState(
  requested: Rag3DVisualState | undefined,
  graph: Rag3DGraph | null,
  activeNodeIds: Set<string>,
  activeEdgeKeys: Set<string>,
  newNodeIds: Set<string>,
): Rag3DVisualState {
  if (requested) return requested;
  if (!graph?.nodes?.length) return "idle";
  if (newNodeIds.size > 0) return "learning";
  if (activeNodeIds.size > 0 || activeEdgeKeys.size > 0) return "completed";
  return "idle";
}

function centroidTuple(position: THREE.Vector3) {
  return [Number(position.x.toFixed(3)), Number(position.y.toFixed(3)), Number(position.z.toFixed(3))];
}

function positionCentroid(positions: THREE.Vector3[], indices?: number[]) {
  const centroid = new THREE.Vector3();
  const selected = indices?.length ? indices.map((index) => positions[index]).filter(Boolean) : positions;
  selected.forEach((position) => centroid.add(position));
  if (selected.length) centroid.divideScalar(selected.length);
  return centroid;
}

function nodeBaseColor(node: Rag3DNode) {
  const sourceType = nodeSourceType(node);
  if (/cloud|web|external|fragment/i.test(sourceType)) return cloudFragmentColor;
  if (/representative|sample|snapshot/i.test(sourceType) || node.id.startsWith("live-synapse")) return representativeNodeColor;
  return localMemoryColor;
}

function frozenStatusText(visualState: Rag3DVisualState) {
  if (visualState === "completed") return "Activation complete";
  if (visualState === "idle" || visualState === "low_memory_viewer") return "Graph settled";
  return null;
}

function disposeMaterial(material?: THREE.Material | THREE.Material[]) {
  if (Array.isArray(material)) {
    material.forEach((item) => item.dispose());
    return;
  }
  material?.dispose();
}

function disposeObject(object: THREE.Object3D) {
  object.traverse((child) => {
    const mesh = child as THREE.Mesh;
    mesh.geometry?.dispose?.();
    disposeMaterial(mesh.material as THREE.Material | THREE.Material[] | undefined);
  });
}

function removeDynamicObjects(state: SceneState) {
  for (const object of state.dynamicObjects) {
    state.group.remove(object);
    disposeObject(object);
  }
  state.dynamicObjects = [];
}

function addDynamicObject(state: SceneState, object: THREE.Object3D) {
  state.dynamicObjects.push(object);
  state.group.add(object);
}

function nextCapacity(count: number, minimum: number) {
  let capacity = minimum;
  while (capacity < count) capacity *= 2;
  return capacity;
}

function expandedFloatBuffer(previous: Float32Array | null, nextLength: number) {
  const next = new Float32Array(nextLength);
  if (previous) next.set(previous.subarray(0, Math.min(previous.length, next.length)));
  return next;
}

function hashUnit(value: string, salt: number) {
  let hash = 2166136261 ^ salt;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return ((hash >>> 0) / 4294967295) * 2 - 1;
}

function hash01(value: string, salt: number) {
  return (hashUnit(value, salt) + 1) / 2;
}

function stableVolumePoint(id: string, index: number, total: number) {
  const count = Math.max(1, total);
  const y = THREE.MathUtils.clamp(1 - ((index + 0.5) / count) * 2 + hashUnit(id, 13) * 0.035, -0.98, 0.98);
  const theta = index * GOLDEN_ANGLE + hashUnit(id, 29) * 0.82;
  const radial = Math.sqrt(Math.max(0.0001, 1 - y * y));
  const volumeRadius = Math.min(44, 6.2 + Math.cbrt(count) * 1.56);
  const shellNoise = 0.68 + Math.cbrt(hash01(id, 47)) * 0.5;
  const localJitter = 1 + hashUnit(id, 71) * 0.065;
  const radius = volumeRadius * Math.min(1.14, shellNoise * localJitter);
  return new THREE.Vector3(
    Math.cos(theta) * radial * radius,
    y * radius,
    Math.sin(theta) * radial * radius,
  );
}

function cameraDistanceForNodeCount(total: number) {
  return Math.min(260, 10 + Math.cbrt(Math.max(1, total)) * 3.8 + Math.sqrt(Math.max(1, total)) * 0.33);
}

function maxZoomDistanceForNodeCount(total: number) {
  const fitDistance = cameraDistanceForNodeCount(total);
  return Math.min(12000, Math.max(420, fitDistance * 28, Math.sqrt(Math.max(1, total)) * 42));
}

function clampCameraZ(camera: THREE.PerspectiveCamera, total: number) {
  camera.position.z = Math.max(3.2, Math.min(maxZoomDistanceForNodeCount(total), camera.position.z));
}

function normalizedSourcePositions(nodes: Rag3DNode[]) {
  const center = new THREE.Vector3();
  const rawPositions = nodes.map((node) => new THREE.Vector3(node.x, node.y, node.z));
  rawPositions.forEach((position) => center.add(position));
  if (rawPositions.length) center.divideScalar(rawPositions.length);
  let radius = 1;
  rawPositions.forEach((position) => {
    radius = Math.max(radius, position.distanceTo(center));
  });
  const sourceLimit = Math.min(18, 4.6 + Math.cbrt(Math.max(1, nodes.length)) * 0.82);
  const scale = radius > sourceLimit ? sourceLimit / radius : 1;
  return rawPositions.map((position) => position.sub(center).multiplyScalar(scale));
}

function initialSpreadPosition(node: Rag3DNode, source: THREE.Vector3, index: number, total: number) {
  if (total <= 14) return source;
  const target = stableVolumePoint(node.id, index, total);
  const sourceWeight = node.id.startsWith("live-synapse") ? 0.18 : total > 800 ? 0.07 : total > 300 ? 0.11 : 0.17;
  return source.multiplyScalar(sourceWeight).add(target.multiplyScalar(1 - sourceWeight));
}

function nodeSourceType(node: Rag3DNode) {
  return String(node.source_type ?? node.sourceType ?? (node.id.includes("cloud") || node.id.includes("web-") ? "cloud_fragment" : "local_memory"));
}

function semanticClusterKey(node: Rag3DNode) {
  return String(node.cluster_id ?? `${nodeSourceType(node)}:${node.type || "concept"}`);
}

function seededClusterCenter(key: string, index: number, total: number) {
  const theta = index * GOLDEN_ANGLE + hashUnit(key, 101) * 0.48;
  const z = hashUnit(key, 131) * 0.55;
  const radial = Math.sqrt(Math.max(0.08, 1 - z * z));
  const radius = 4.2 + Math.cbrt(Math.max(1, total)) * 0.54;
  return new THREE.Vector3(
    Math.cos(theta) * radial * radius,
    Math.sin(theta) * radial * radius,
    z * radius * 0.72,
  );
}

function edgeWeight(edge: Rag3DEdge) {
  return THREE.MathUtils.clamp(Number(edge.weight ?? edge.confidence ?? 0.52), 0.08, 2.4);
}

function computeOrganicGraphLayout(
  nodes: Rag3DNode[],
  edges: Rag3DEdge[],
  options: { activeNodeIds?: Set<string>; maxIterations?: number } = {},
) {
  const sources = normalizedSourcePositions(nodes);
  const nodeIndex = new Map(nodes.map((node, index) => [node.id, index]));
  const degree = new Map<string, number>();
  edges.forEach((edge) => {
    degree.set(edge.source, (degree.get(edge.source) ?? 0) + edgeWeight(edge));
    degree.set(edge.target, (degree.get(edge.target) ?? 0) + edgeWeight(edge));
  });
  const maxDegree = Math.max(1, ...nodes.map((node) => degree.get(node.id) ?? 0));
  const clusterKeys = Array.from(new Set(nodes.map(semanticClusterKey))).sort();
  const clusterCenters = new Map(clusterKeys.map((key, index) => [key, seededClusterCenter(key, index, clusterKeys.length)]));
  const total = Math.max(1, nodes.length);
  const baseRadius = Math.min(70, 7.4 + Math.cbrt(total) * 1.82);
  const activeNodeIds = options.activeNodeIds ?? new Set<string>();
  const positions = nodes.map((node, index) => {
    const source = initialSpreadPosition(node, sources[index].clone(), index, nodes.length);
    const cluster = clusterCenters.get(semanticClusterKey(node)) ?? new THREE.Vector3();
    const degreeRatio = (degree.get(node.id) ?? 0) / maxDegree;
    const isCloud = /cloud|web|external|fragment/i.test(nodeSourceType(node));
    const isPredicate = /predicate|relation|edge/i.test(node.type ?? "");
    const semantic = stableVolumePoint(node.id, index, total).multiplyScalar(isCloud ? 1.12 : 0.76);
    const position = new THREE.Vector3()
      .addScaledVector(semantic, 0.58)
      .addScaledVector(cluster, isPredicate ? 0.18 : 0.34)
      .addScaledVector(source, 0.08);
    const radiusFactor = isCloud ? 1.34 : 1 - degreeRatio * 0.46;
    position.normalize().multiplyScalar(Math.max(1.2, baseRadius * radiusFactor));
    position.x += hashUnit(node.id, 173) * 0.8;
    position.y += hashUnit(node.id, 211) * 0.8;
    position.z += hashUnit(node.id, 241) * 0.45;
    return position;
  });
  if (nodes.length <= 1) return { positions, diagnostics: layoutDiagnostics(nodes, edges, positions, activeNodeIds) };

  const sampledEdges = edges
    .filter((edge) => nodeIndex.has(edge.source) && nodeIndex.has(edge.target))
    .sort((left, right) => edgeWeight(right) - edgeWeight(left))
    .filter((edge, index) => index < 24_000 || activeNodeIds.has(edge.source) || activeNodeIds.has(edge.target) || index % Math.ceil(edges.length / 24_000) === 0);
  const iterations = Math.min(options.maxIterations ?? 60, nodes.length > 5_000 ? 18 : nodes.length > 2_000 ? 28 : nodes.length > 800 ? 42 : 64);
  const minDistance = nodes.length > 5_000 ? 0.52 : nodes.length > 1_400 ? 0.72 : nodes.length > 700 ? 0.9 : 1.05;
  const repulsionStride = nodes.length > 3_000 ? 7 : nodes.length > 1_200 ? 5 : nodes.length > 500 ? 3 : 1;

  for (let pass = 0; pass < iterations; pass += 1) {
    const cooling = 1 - pass / Math.max(1, iterations);
    for (const edge of sampledEdges) {
      const sourceIndex = nodeIndex.get(edge.source);
      const targetIndex = nodeIndex.get(edge.target);
      if (sourceIndex === undefined || targetIndex === undefined) continue;
      const source = positions[sourceIndex];
      const target = positions[targetIndex];
      const delta = target.clone().sub(source);
      const distance = Math.max(0.001, delta.length());
      const desired = THREE.MathUtils.lerp(1.8, 4.8, 1 / Math.sqrt(edgeWeight(edge) + 0.2));
      const spring = (distance - desired) * 0.012 * edgeWeight(edge) * cooling;
      delta.normalize().multiplyScalar(spring);
      source.add(delta);
      target.sub(delta);
    }
    for (let left = 0; left < positions.length; left += repulsionStride) {
      for (let right = left + repulsionStride; right < positions.length; right += repulsionStride) {
        const delta = positions[left].clone().sub(positions[right]);
        let distance = delta.length();
        if (distance >= minDistance) continue;
        if (distance < 0.001) {
          delta.set(hashUnit(nodes[left].id, 307) * 0.03 + 0.02, hashUnit(nodes[right].id, 311) * 0.03 + 0.02, 0.02);
          distance = delta.length();
        }
        const push = (minDistance - distance) * 0.34 * cooling;
        delta.normalize().multiplyScalar(push);
        positions[left].add(delta);
        positions[right].sub(delta);
      }
    }
    positions.forEach((position, index) => {
      const node = nodes[index];
      const cluster = clusterCenters.get(semanticClusterKey(node));
      const degreeRatio = (degree.get(node.id) ?? 0) / maxDegree;
      if (cluster) position.lerp(cluster, (0.004 + degreeRatio * 0.005) * cooling);
      position.z *= 0.995;
    });
  }
  const center = new THREE.Vector3();
  positions.forEach((position) => center.add(position));
  center.divideScalar(positions.length);
  positions.forEach((position) => position.sub(center));
  return { positions, diagnostics: layoutDiagnostics(nodes, edges, positions, activeNodeIds) };
}

function layoutDiagnostics(nodes: Rag3DNode[], edges: Rag3DEdge[], positions: THREE.Vector3[], activeNodeIds: Set<string>) {
  const degree = new Map<string, number>();
  edges.forEach((edge) => {
    degree.set(edge.source, (degree.get(edge.source) ?? 0) + 1);
    degree.set(edge.target, (degree.get(edge.target) ?? 0) + 1);
  });
  const averageDegree = nodes.length ? Array.from(degree.values()).reduce((sum, value) => sum + value, 0) / nodes.length : 0;
  const clusterCount = new Set(nodes.map(semanticClusterKey)).size;
  const activeIndices = nodes
    .map((node, index) => (activeNodeIds.has(node.id) ? index : -1))
    .filter((index) => index >= 0);
  const graphCentroid = positionCentroid(positions);
  const activeCentroid = activeIndices.length ? positionCentroid(positions, activeIndices) : graphCentroid.clone();
  return {
    layout_mode: "organic_semantic_force",
    graph_centroid: centroidTuple(graphCentroid),
    active_centroid: centroidTuple(activeCentroid),
    active_centroid_offset: Number(activeCentroid.distanceTo(graphCentroid).toFixed(3)),
    active_seed_count: activeNodeIds.size,
    active_cluster_count: new Set(nodes.filter((node) => activeNodeIds.has(node.id)).map(semanticClusterKey)).size,
    local_nodes: nodes.filter((node) => !/cloud|web|external|fragment/i.test(nodeSourceType(node))).length,
    cloud_fragment_nodes: nodes.filter((node) => /cloud|web|external|fragment/i.test(nodeSourceType(node))).length,
    average_degree: Number(averageDegree.toFixed(3)),
    visible_edges: edges.length,
    semantic_cluster_count: clusterCount,
    z_axis_ratio: axisDominanceRatio(positions),
  };
}

function axisDominanceRatio(positions: THREE.Vector3[]) {
  if (positions.length < 2) return 0;
  const mean = positions.reduce((acc, position) => acc.add(position), new THREE.Vector3()).divideScalar(positions.length);
  const variance = positions.reduce(
    (acc, position) => {
      acc.x += (position.x - mean.x) ** 2;
      acc.y += (position.y - mean.y) ** 2;
      acc.z += (position.z - mean.z) ** 2;
      return acc;
    },
    new THREE.Vector3(),
  ).divideScalar(positions.length);
  const horizontal = Math.max(0.0001, (variance.x + variance.y) / 2);
  return Number((variance.z / horizontal).toFixed(3));
}

function computeActivationMaps(nodes: Rag3DNode[], edges: Rag3DEdge[], activeNodeIds: Set<string>, activeEdgeKeys: Set<string>) {
  const nodeIds = new Set(nodes.map((node) => node.id));
  const adjacency = new Map<string, string[]>();
  edges.forEach((edge) => {
    if (!nodeIds.has(edge.source) || !nodeIds.has(edge.target)) return;
    if (!adjacency.has(edge.source)) adjacency.set(edge.source, []);
    if (!adjacency.has(edge.target)) adjacency.set(edge.target, []);
    adjacency.get(edge.source)!.push(edge.target);
    adjacency.get(edge.target)!.push(edge.source);
  });
  const hops = new Map<string, number>();
  const queue: Array<{ id: string; hop: number }> = [];
  activeNodeIds.forEach((id) => {
    if (nodeIds.has(id)) {
      hops.set(id, 0);
      queue.push({ id, hop: 0 });
    }
  });
  edges.forEach((edge) => {
    if (edgeIsExplicitlyActive(activeEdgeKeys, edge.source, edge.target)) {
      [edge.source, edge.target].forEach((id) => {
        if (nodeIds.has(id) && !hops.has(id)) {
          hops.set(id, 0);
          queue.push({ id, hop: 0 });
        }
      });
    }
  });
  while (queue.length) {
    const item = queue.shift()!;
    if (item.hop >= 3) continue;
    for (const next of adjacency.get(item.id) ?? []) {
      const nextHop = item.hop + 1;
      if ((hops.get(next) ?? Infinity) <= nextHop) continue;
      hops.set(next, nextHop);
      queue.push({ id: next, hop: nextHop });
    }
  }
  const edgeIntensity = new Map<string, number>();
  edges.forEach((edge) => {
    const sourceHop = hops.get(edge.source);
    const targetHop = hops.get(edge.target);
    if (sourceHop === undefined && targetHop === undefined && !edgeIsExplicitlyActive(activeEdgeKeys, edge.source, edge.target)) return;
    const hop = Math.min(sourceHop ?? 4, targetHop ?? 4);
    edgeIntensity.set(edgeKey(edge.source, edge.target), Math.exp(-hop * 0.78));
  });
  return { hops, edgeIntensity };
}

function spreadPositions(nodes: Rag3DNode[], edges: Rag3DEdge[] = [], activeNodeIds = new Set<string>()) {
  return computeOrganicGraphLayout(nodes, edges, { activeNodeIds });
}

function sourceCoordinatePositions(nodes: Rag3DNode[]) {
  return nodes.map((node) => new THREE.Vector3(node.x, node.y, node.z));
}

function viewportRadiusForCamera(camera: THREE.PerspectiveCamera) {
  const fovRadians = THREE.MathUtils.degToRad(camera.fov);
  return Math.max(8, Math.min(220, camera.position.z * Math.tan(fovRadians / 2) * 1.75));
}

function fitDistanceForPositions(positions: THREE.Vector3[], camera: THREE.PerspectiveCamera) {
  if (!positions.length) return cameraDistanceForNodeCount(0);
  const center = new THREE.Vector3();
  positions.forEach((position) => center.add(position));
  center.divideScalar(positions.length);
  let radius = 1;
  positions.forEach((position) => {
    radius = Math.max(radius, position.distanceTo(center));
  });
  const fovRadians = THREE.MathUtils.degToRad(camera.fov);
  const aspectCompensation = camera.aspect < 1 ? 1 / Math.max(0.62, camera.aspect) : 1;
  return Math.min(2200, Math.max(cameraDistanceForNodeCount(positions.length), (radius * 1.45 * aspectCompensation) / Math.tan(fovRadians / 2)));
}

function labelSprite(text: string, scale = 1) {
  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 128;
  const context = canvas.getContext("2d");
  if (context) {
    context.clearRect(0, 0, canvas.width, canvas.height);
    context.font = "800 42px Arial";
    context.fillStyle = COLD_LABEL;
    context.strokeStyle = "rgba(0,0,0,0.9)";
    context.lineWidth = 8;
    context.strokeText(text.slice(0, 22), 20, 76);
    context.fillText(text.slice(0, 22), 20, 76);
  }
  const texture = new THREE.CanvasTexture(canvas);
  const material = new THREE.SpriteMaterial({ map: texture, transparent: true, opacity: 0.86 });
  const sprite = new THREE.Sprite(material);
  sprite.scale.set(2.4 * scale, 0.6 * scale, 1);
  return sprite;
}

function shouldShowLabel(node: Rag3DNode, totalNodes: number, isActive: boolean) {
  if (node.id.startsWith("live-synapse")) return false;
  if (isActive) return true;
  return totalNodes <= 40;
}

function ensureNodeBuffers(state: SceneState, nodeCount: number) {
  if (state.nodePoints && state.nodeGeometry && state.nodeCapacity >= nodeCount) {
    state.nodeGeometry.setDrawRange(0, nodeCount);
    return;
  }

  const nextNodeCapacity = nextCapacity(nodeCount, 1024);
  state.nodeCapacity = nextNodeCapacity;
  state.nodePositionArray = expandedFloatBuffer(state.nodePositionArray, nextNodeCapacity * 3);
  state.nodeColorArray = expandedFloatBuffer(state.nodeColorArray, nextNodeCapacity * 3);

  if (!state.nodeGeometry) {
    state.nodeGeometry = new THREE.BufferGeometry();
  }
  state.nodeGeometry.setAttribute("position", new THREE.BufferAttribute(state.nodePositionArray, 3).setUsage(THREE.DynamicDrawUsage));
  state.nodeGeometry.setAttribute("color", new THREE.BufferAttribute(state.nodeColorArray, 3).setUsage(THREE.DynamicDrawUsage));
  state.nodeGeometry.setDrawRange(0, nodeCount);
  state.nodePositionBufferDirty = true;

  if (!state.nodePoints) {
    const pointMaterial = new THREE.PointsMaterial({
      alphaTest: 0.01,
      blending: THREE.NormalBlending,
      depthTest: false,
      depthWrite: false,
      opacity: 0.96,
      size: nodeCount > 100_000 ? 0.035 : nodeCount > 25_000 ? 0.047 : nodeCount > 5_000 ? 0.062 : nodeCount > 1_000 ? 0.105 : 0.22,
      sizeAttenuation: true,
      transparent: true,
      vertexColors: true,
    });
    state.nodePoints = new THREE.Points(state.nodeGeometry, pointMaterial);
    state.nodePoints.renderOrder = 2;
    state.nodePoints.userData.kind = "node-points";
    state.group.add(state.nodePoints);
  } else {
    state.nodePoints.geometry = state.nodeGeometry;
    const material = state.nodePoints.material as THREE.PointsMaterial;
    material.size = nodeCount > 100_000 ? 0.035 : nodeCount > 25_000 ? 0.047 : nodeCount > 5_000 ? 0.062 : nodeCount > 1_000 ? 0.105 : 0.22;
    material.needsUpdate = true;
  }
}

function ensureEdgeBuffers(state: SceneState, vertexCount: number) {
  if (state.edgeLines && state.edgeGeometry && state.edgeCapacity >= vertexCount) {
    state.edgeGeometry.setDrawRange(0, vertexCount);
    return;
  }

  const nextEdgeCapacity = nextCapacity(vertexCount, 4096);
  state.edgeCapacity = nextEdgeCapacity;
  state.edgePositionArray = expandedFloatBuffer(state.edgePositionArray, nextEdgeCapacity * 3);
  state.edgeColorArray = expandedFloatBuffer(state.edgeColorArray, nextEdgeCapacity * 3);

  if (!state.edgeGeometry) {
    state.edgeGeometry = new THREE.BufferGeometry();
  }
  state.edgeGeometry.setAttribute("position", new THREE.BufferAttribute(state.edgePositionArray, 3).setUsage(THREE.DynamicDrawUsage));
  state.edgeGeometry.setAttribute("color", new THREE.BufferAttribute(state.edgeColorArray, 3).setUsage(THREE.DynamicDrawUsage));
  state.edgeGeometry.setDrawRange(0, vertexCount);
  state.edgePositionBufferDirty = true;

  if (!state.edgeLines) {
    const edgeMaterial = new THREE.LineBasicMaterial({
      blending: THREE.NormalBlending,
      depthTest: false,
      depthWrite: false,
      opacity: 0.58,
      transparent: true,
      vertexColors: true,
    });
    state.edgeLines = new THREE.LineSegments(state.edgeGeometry, edgeMaterial);
    state.edgeLines.renderOrder = 1;
    state.group.add(state.edgeLines);
  } else {
    state.edgeLines.geometry = state.edgeGeometry;
  }
}

function ensureHaloMesh(state: SceneState, count: number) {
  if (count <= 0) {
    if (state.haloMesh) state.haloMesh.count = 0;
    return;
  }
  if (state.haloMesh && state.haloCapacity >= count) {
    state.haloMesh.count = count;
    return;
  }

  if (state.haloMesh) {
    state.group.remove(state.haloMesh);
    disposeObject(state.haloMesh);
  }
  state.haloCapacity = nextCapacity(count, 64);
  const geometry = new THREE.TorusGeometry(1, 0.018, 8, 48);
  const material = new THREE.MeshBasicMaterial({
    blending: THREE.NormalBlending,
    color: NEON_ORANGE,
    depthTest: false,
    depthWrite: false,
    opacity: 0.34,
    transparent: true,
  });
  state.haloMesh = new THREE.InstancedMesh(geometry, material, state.haloCapacity);
  state.haloMesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  state.haloMesh.count = count;
  state.haloMesh.renderOrder = 4;
  state.group.add(state.haloMesh);
}

function ensurePulseMesh(state: SceneState, count: number) {
  if (count <= 0) {
    if (state.pulseMesh) state.pulseMesh.count = 0;
    return;
  }
  if (state.pulseMesh && state.pulseCapacity >= count) {
    state.pulseMesh.count = count;
    return;
  }

  if (state.pulseMesh) {
    state.group.remove(state.pulseMesh);
    disposeObject(state.pulseMesh);
  }
  state.pulseCapacity = nextCapacity(count, 128);
  const geometry = new THREE.SphereGeometry(1, 8, 8);
  const material = new THREE.MeshBasicMaterial({
    blending: THREE.NormalBlending,
    color: NEON_ORANGE,
    depthTest: false,
    depthWrite: false,
    opacity: 0.86,
    transparent: true,
  });
  state.pulseMesh = new THREE.InstancedMesh(geometry, material, state.pulseCapacity);
  state.pulseMesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  state.pulseMesh.count = count;
  state.pulseMesh.renderOrder = 5;
  state.group.add(state.pulseMesh);
}

function findSpawnPositionForNode(nodeId: string, edges: Rag3DEdge[], positions: Map<string, THREE.Vector3>, fallback: THREE.Vector3) {
  for (const edge of edges) {
    if (edge.source === nodeId) {
      const source = positions.get(edge.target);
      if (source) return source.clone();
    }
    if (edge.target === nodeId) {
      const source = positions.get(edge.source);
      if (source) return source.clone();
    }
  }
  return fallback.clone().multiplyScalar(0.54);
}

function syncGraph(
  state: SceneState,
  graph: Rag3DGraph | null,
  activeNodeIds: Set<string>,
  activeEdgeKeys: Set<string>,
  newNodeIds: Set<string>,
  requestedVisualState?: Rag3DVisualState,
) {
  const nextVisualState = resolveVisualState(requestedVisualState, graph, activeNodeIds, activeEdgeKeys, newNodeIds);
  if (state.visualState !== nextVisualState) {
    state.frozenPositionSnapshot = null;
    state.coordinateMutationWarned = false;
  }
  state.visualState = nextVisualState;
  state.activeNodeIds = new Set(activeNodeIds);
  state.activeEdgeKeys = new Set(activeEdgeKeys);
  state.newNodeIds = new Set(newNodeIds);
  state.graphNodes = graph?.nodes ?? [];
  state.graphEdges = graph?.edges ?? [];

  if (!graph?.nodes?.length) {
    state.nodePoints?.geometry.setDrawRange(0, 0);
    state.edgeLines?.geometry.setDrawRange(0, 0);
    if (state.haloMesh) state.haloMesh.count = 0;
    if (state.pulseMesh) state.pulseMesh.count = 0;
    removeDynamicObjects(state);
    return;
  }

  const elapsed = (performance.now() - state.startedAt) / 1000;
  const activation = computeActivationMaps(graph.nodes, graph.edges, activeNodeIds, activeEdgeKeys);
  state.activationHops = activation.hops;
  state.activationEdgeIntensity = activation.edgeIntensity;
  const organicLayout = spreadPositions(graph.nodes, graph.edges, activeNodeIds);
  state.layoutDiagnostics = {
    ...organicLayout.diagnostics,
    hop1_count: Array.from(activation.hops.values()).filter((hop) => hop === 1).length,
    hop2_count: Array.from(activation.hops.values()).filter((hop) => hop === 2).length,
    hop3_count: Array.from(activation.hops.values()).filter((hop) => hop === 3).length,
    visual_state: nextVisualState,
  };
  const targets = state.preserveSourceCoordinates ? sourceCoordinatePositions(graph.nodes) : organicLayout.positions;
  const nextKnownNodeIds = new Set<string>();
  const nextNodeIndexById = new Map<string, number>();
  const stillPresent = new Set<string>();
  const targetMap = new Map<string, THREE.Vector3>();

  graph.nodes.forEach((node, index) => {
    const target = targets[index];
    nextKnownNodeIds.add(node.id);
    nextNodeIndexById.set(node.id, index);
    targetMap.set(node.id, target);
    stillPresent.add(node.id);

    if (!state.nodePositionById.has(node.id)) {
      const spawn = coordinateAnimationAllowed(nextVisualState)
        ? findSpawnPositionForNode(node.id, graph.edges, state.nodePositionById, target)
        : target.clone();
      state.nodePositionById.set(node.id, spawn);
      state.nodeBornAt.set(node.id, elapsed);
    }
  });

  for (const id of Array.from(state.nodePositionById.keys())) {
    if (!stillPresent.has(id)) {
      state.nodePositionById.delete(id);
      state.nodeTargetById.delete(id);
      state.nodeBornAt.delete(id);
    }
  }

  state.nodeTargetById = targetMap;
  state.nodeIndexById = nextNodeIndexById;
  state.pointNodes = graph.nodes;
  state.nodePositionBufferDirty = true;
  state.edgePositionBufferDirty = true;
  state.frozenPositionSnapshot = null;
  state.coordinateMutationWarned = false;

  const fitDistance = fitDistanceForPositions(targets, state.camera);
  const graphExpanded = graph.nodes.length > state.lastGraphNodeCount;
  const userControllingCamera = state.frame < state.userCameraControlUntilFrame;
  if (!userControllingCamera && (graphExpanded || fitDistance > state.lastFitDistance || fitDistance > state.camera.position.z)) {
    state.camera.position.z = Math.max(state.camera.position.z, fitDistance);
    state.lastFitDistance = fitDistance;
  } else if (!userControllingCamera && state.camera.position.z > fitDistance * 1.32) {
    state.camera.position.z = fitDistance * 1.12;
    state.lastFitDistance = fitDistance;
  }
  state.lastGraphNodeCount = graph.nodes.length;
  if (!state.preserveSourceCoordinates) {
    clampCameraZ(state.camera, graph.nodes.length);
  }

  const traversalPairs = new Set<string>();
  for (let index = 0; index < (graph.traversal_path?.length ?? 0) - 1; index += 1) {
    traversalPairs.add(`${graph.traversal_path?.[index]}:${graph.traversal_path?.[index + 1]}`);
  }

  const maxEdges = graph.nodes.length > 100_000 ? 80_000 : graph.nodes.length > 25_000 ? 70_000 : graph.nodes.length > 5_000 ? 60_000 : Number.POSITIVE_INFINITY;
  const edgeStride = Number.isFinite(maxEdges) && graph.edges.length > maxEdges ? Math.ceil(graph.edges.length / maxEdges) : 1;
  state.visibleEdges = [];
  for (const [index, edge] of graph.edges.entries()) {
    if (!state.nodeIndexById.has(edge.source) || !state.nodeIndexById.has(edge.target)) continue;
    const explicitActive = edgeIsExplicitlyActive(activeEdgeKeys, edge.source, edge.target);
    const directActive = activeNodeIds.has(edge.source) || activeNodeIds.has(edge.target);
    const hopActive = (state.activationEdgeIntensity.get(edgeKey(edge.source, edge.target)) ?? 0) > 0;
    const traversalActive = traversalPairs.has(`${edge.source}:${edge.target}`);
    if (!explicitActive && !directActive && !hopActive && !traversalActive && index % edgeStride !== 0) continue;
    state.visibleEdges.push({ ...edge, active: explicitActive || directActive || hopActive || traversalActive, index });
  }

  ensureNodeBuffers(state, graph.nodes.length);
  ensureEdgeBuffers(state, state.visibleEdges.length * 2);

  const hasSignalEvent = activeNodeIds.size > 0 || activeEdgeKeys.size > 0 || newNodeIds.size > 0;
  state.haloItems = graph.nodes
    .filter((node) => {
      const bornAt = state.nodeBornAt.get(node.id);
      const newPulse = hasSignalEvent && typeof bornAt === "number" && elapsed - bornAt < NEW_NODE_ANIMATION_SECONDS;
      return activeNodeIds.has(node.id) || (state.activationHops.get(node.id) ?? 99) <= 2 || newNodeIds.has(node.id) || newPulse;
    })
    .slice(0, 512)
    .map((node) => {
      const bornAt = state.nodeBornAt.get(node.id) ?? elapsed;
      const position = state.nodePositionById.get(node.id) ?? state.nodeTargetById.get(node.id) ?? new THREE.Vector3();
      return {
        bornAt,
        id: node.id,
        newNode: newNodeIds.has(node.id) || (hasSignalEvent && elapsed - bornAt < NEW_NODE_ANIMATION_SECONDS),
        position,
        scale: 0.72 + (node.confidence ?? 0.65) * 0.38,
      };
    });
  ensureHaloMesh(state, state.haloItems.length);

  state.pulseItems = movingPulseAllowed(nextVisualState)
    ? state.visibleEdges
      .filter((edge) => edge.active)
      .slice(0, 640)
      .flatMap((edge) => [0, 1, 2].map((pulse) => ({ source: edge.source, target: edge.target, phase: pulse / 3 })))
    : [];
  ensurePulseMesh(state, state.pulseItems.length);
  state.edgePulseCount = state.pulseItems.length;

  removeDynamicObjects(state);
  const labelScale = graph.nodes.length > 18 ? 0.72 : graph.nodes.length > 12 ? 0.84 : 1;
  graph.nodes.forEach((node) => {
    const isActive = activeNodeIds.has(node.id);
    if (!shouldShowLabel(node, graph.nodes.length, isActive)) return;
    const position = state.nodePositionById.get(node.id);
    if (!position) return;
    const sprite = labelSprite(node.label, labelScale);
    sprite.position.set(position.x + 0.32, position.y + 0.18, position.z);
    addDynamicObject(state, sprite);
  });

  state.knownNodeIds = nextKnownNodeIds;
}

function nodeSignalStrength(state: SceneState, node: Rag3DNode, elapsed: number) {
  const active = state.activeNodeIds.has(node.id);
  const hop = state.activationHops.get(node.id);
  const bornAt = state.nodeBornAt.get(node.id);
  const newAge = typeof bornAt === "number" ? elapsed - bornAt : Number.POSITIVE_INFINITY;
  const newPulse = coordinateAnimationAllowed(state.visualState) && (state.newNodeIds.has(node.id) || newAge < NEW_NODE_ANIMATION_SECONDS);
  if (state.visualState === "low_memory_viewer") return active ? 0.42 : 0;
  if (active) {
    const amplitude = state.visualState === "completed" ? 0.08 : 0.24;
    const base = state.visualState === "completed" ? 0.62 : 0.76;
    return base + Math.sin(elapsed * 10 + hash01(node.id, 31) * Math.PI * 2) * amplitude;
  }
  if (hop !== undefined && hop <= 3) {
    const base = Math.exp(-hop * 0.82);
    const pulseAmplitude = state.visualState === "completed" ? 0.06 : 0.18;
    const pulseBase = state.visualState === "completed" ? 0.46 : 0.58;
    return THREE.MathUtils.clamp(base * (pulseBase + Math.sin(elapsed * 8 + hash01(node.id, 37) * Math.PI * 2) * pulseAmplitude), 0.06, 0.72);
  }
  if (newPulse) return THREE.MathUtils.clamp(1 - newAge / NEW_NODE_ANIMATION_SECONDS, 0, 1);
  return 0;
}

function edgeSignalStrength(state: SceneState, edge: VisibleEdge, elapsed: number) {
  if (!edge.active) return 0;
  const hopIntensity = state.activationEdgeIntensity.get(edgeKey(edge.source, edge.target))
    ?? state.activationEdgeIntensity.get(edgeKey(edge.target, edge.source))
    ?? 0;
  const phase = hash01(edge.source + edge.target, 19) * Math.PI * 2;
  const pulse = state.visualState === "completed"
    ? 0.62 + Math.sin(elapsed * 8 + phase) * 0.12
    : 0.68 + Math.sin(elapsed * 10 + phase) * 0.32;
  return THREE.MathUtils.clamp(Math.max(hopIntensity * pulse, edgeIsExplicitlyActive(state.activeEdgeKeys, edge.source, edge.target) ? pulse : 0), 0, 1);
}

function assertCompletedCoordinatesStable(state: SceneState) {
  if (state.visualState !== "completed" || !state.nodePositionArray) return;
  const length = state.graphNodes.length * 3;
  const current = state.nodePositionArray.subarray(0, length);
  if (!state.frozenPositionSnapshot || state.frozenPositionSnapshot.length !== length) {
    state.frozenPositionSnapshot = new Float32Array(current);
    return;
  }
  if (state.coordinateMutationWarned) return;
  for (let index = 0; index < length; index += 1) {
    if (Math.abs(current[index] - state.frozenPositionSnapshot[index]) > 0.00001) {
      console.warn("Unexpected coordinate mutation in completed graph state");
      state.coordinateMutationWarned = true;
      state.frozenPositionSnapshot = new Float32Array(current);
      return;
    }
  }
}

function updateNodeBuffers(state: SceneState, elapsed: number) {
  if (!state.nodePositionArray || !state.nodeColorArray || !state.nodeGeometry) return;
  const positionAttribute = state.nodeGeometry.getAttribute("position") as THREE.BufferAttribute;
  const colorAttribute = state.nodeGeometry.getAttribute("color") as THREE.BufferAttribute;
  const allowPositionMutation = coordinateAnimationAllowed(state.visualState);
  let positionBufferChanged = state.nodePositionBufferDirty;

  state.graphNodes.forEach((node, index) => {
    const position = state.nodePositionById.get(node.id) ?? new THREE.Vector3();
    const target = state.nodeTargetById.get(node.id) ?? position;
    const bornAt = state.nodeBornAt.get(node.id);
    const age = typeof bornAt === "number" ? elapsed - bornAt : 99;
    if (allowPositionMutation) {
      const beforeX = position.x;
      const beforeY = position.y;
      const beforeZ = position.z;
      const expansionRate = age < NEW_NODE_ANIMATION_SECONDS ? 0.115 : 0.045;
      position.lerp(target, expansionRate);
      if (Math.abs(position.x - beforeX) > 0.00001 || Math.abs(position.y - beforeY) > 0.00001 || Math.abs(position.z - beforeZ) > 0.00001) {
        positionBufferChanged = true;
      }
    }

    state.nodePositionArray![index * 3] = position.x;
    state.nodePositionArray![index * 3 + 1] = position.y;
    state.nodePositionArray![index * 3 + 2] = position.z;

    const signal = nodeSignalStrength(state, node, elapsed);
    tempColor.copy(nodeBaseColor(node)).lerp(neonOrangeColor, signal);
    state.nodeColorArray![index * 3] = tempColor.r;
    state.nodeColorArray![index * 3 + 1] = tempColor.g;
    state.nodeColorArray![index * 3 + 2] = tempColor.b;
  });

  if (positionBufferChanged) {
    positionAttribute.needsUpdate = true;
    state.nodeGeometry.computeBoundingSphere();
    state.nodePositionBufferDirty = false;
  }
  colorAttribute.needsUpdate = true;
  assertCompletedCoordinatesStable(state);
}

function updateEdgeBuffers(state: SceneState, elapsed: number) {
  if (!state.edgePositionArray || !state.edgeColorArray || !state.edgeGeometry) return;
  const positionAttribute = state.edgeGeometry.getAttribute("position") as THREE.BufferAttribute;
  const colorAttribute = state.edgeGeometry.getAttribute("color") as THREE.BufferAttribute;
  const positionBufferChanged = state.edgePositionBufferDirty || coordinateAnimationAllowed(state.visualState);

  state.visibleEdges.forEach((edge, edgeIndex) => {
    const source = state.nodePositionById.get(edge.source);
    const target = state.nodePositionById.get(edge.target);
    if (!source || !target) return;
    const vertexIndex = edgeIndex * 6;
    state.edgePositionArray![vertexIndex] = source.x;
    state.edgePositionArray![vertexIndex + 1] = source.y;
    state.edgePositionArray![vertexIndex + 2] = source.z;
    state.edgePositionArray![vertexIndex + 3] = target.x;
    state.edgePositionArray![vertexIndex + 4] = target.y;
    state.edgePositionArray![vertexIndex + 5] = target.z;

    const signal = edgeSignalStrength(state, edge, elapsed);
    const base = edge.active && signal < 0.12 ? nearActiveEdgeColor : baseEdgeColor;
    tempColor.copy(base).lerp(neonOrangeColor, signal);
    state.edgeColorArray![vertexIndex] = tempColor.r;
    state.edgeColorArray![vertexIndex + 1] = tempColor.g;
    state.edgeColorArray![vertexIndex + 2] = tempColor.b;
    state.edgeColorArray![vertexIndex + 3] = tempColor.r;
    state.edgeColorArray![vertexIndex + 4] = tempColor.g;
    state.edgeColorArray![vertexIndex + 5] = tempColor.b;
  });

  if (positionBufferChanged) {
    positionAttribute.needsUpdate = true;
    state.edgePositionBufferDirty = false;
  }
  colorAttribute.needsUpdate = true;
}

function updateHaloMesh(state: SceneState, elapsed: number) {
  if (!state.haloMesh) return;
  state.haloMesh.count = state.haloItems.length;
  state.haloItems.forEach((halo, index) => {
    const position = state.nodePositionById.get(halo.id) ?? halo.position;
    const age = elapsed - halo.bornAt;
    const t = THREE.MathUtils.clamp(age / NEW_NODE_ANIMATION_SECONDS, 0, 1);
    const signal = halo.newNode
      ? 1 - t
      : 0.7 + Math.sin(elapsed * 10 + hash01(halo.id, 43) * Math.PI * 2) * 0.3;
    const ringScale = halo.scale * (halo.newNode ? THREE.MathUtils.lerp(1.75, 0.68, t) : THREE.MathUtils.lerp(0.92, 1.18, signal));
    tempScale.setScalar(Math.max(0.001, ringScale));
    tempMatrix.compose(position, tempRingQuaternion, tempScale);
    state.haloMesh!.setMatrixAt(index, tempMatrix);
  });
  const material = state.haloMesh.material as THREE.MeshBasicMaterial;
  material.opacity = state.haloItems.some((halo) => halo.newNode) ? 0.28 : 0.18;
  material.needsUpdate = true;
  state.haloMesh.instanceMatrix.needsUpdate = true;
}

function updatePulseMesh(state: SceneState, elapsed: number) {
  if (!state.pulseMesh) return;
  if (!movingPulseAllowed(state.visualState)) {
    state.pulseMesh.count = 0;
    return;
  }
  state.pulseMesh.count = state.pulseItems.length;
  state.pulseItems.forEach((pulse, index) => {
    const source = state.nodePositionById.get(pulse.source);
    const target = state.nodePositionById.get(pulse.target);
    if (!source || !target) return;
    const t = (elapsed * 1.8 + pulse.phase) % 1;
    tempPosition.copy(source).lerp(target, t);
    tempScale.setScalar(0.05 + Math.sin(t * Math.PI) * 0.085);
    tempMatrix.compose(tempPosition, tempQuaternion, tempScale);
    state.pulseMesh!.setMatrixAt(index, tempMatrix);
  });
  state.pulseMesh.instanceMatrix.needsUpdate = true;
}

export default function Rag3DScene({
  graph,
  activeEdgeKeys = [],
  activeNodeIds = [],
  newNodeIds = [],
  control,
  preserveSourceCoordinates = false,
  onViewportChange,
  onSelect,
  theme = "light",
  visualState,
}: Rag3DSceneProps) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const selectRef = useRef(onSelect);
  const viewportChangeRef = useRef(onViewportChange);
  const sceneStateRef = useRef<SceneState | null>(null);
  const activeEdgeRef = useRef(new Set(activeEdgeKeys));
  const activeNodeRef = useRef(new Set(activeNodeIds));
  const newNodeRef = useRef(new Set(newNodeIds));
  const graphRef = useRef<Rag3DGraph | null>(graph);

  useEffect(() => {
    selectRef.current = onSelect;
  }, [onSelect]);

  useEffect(() => {
    viewportChangeRef.current = onViewportChange;
    const state = sceneStateRef.current;
    if (state) state.onViewportChange = onViewportChange;
  }, [onViewportChange]);

  useEffect(() => {
    graphRef.current = graph;
    const state = sceneStateRef.current;
    if (state) syncGraph(state, graph, activeNodeRef.current, activeEdgeRef.current, newNodeRef.current, visualState);
  }, [graph, visualState]);

  useEffect(() => {
    const state = sceneStateRef.current;
    if (!state) return;
    state.preserveSourceCoordinates = preserveSourceCoordinates;
    syncGraph(state, graphRef.current, activeNodeRef.current, activeEdgeRef.current, newNodeRef.current, visualState);
  }, [preserveSourceCoordinates, visualState]);

  useEffect(() => {
    activeNodeRef.current = new Set(activeNodeIds);
    activeEdgeRef.current = new Set(activeEdgeKeys);
    const state = sceneStateRef.current;
    if (state) syncGraph(state, graphRef.current, activeNodeRef.current, activeEdgeRef.current, newNodeRef.current, visualState);
  }, [activeEdgeKeys, activeNodeIds, visualState]);

  useEffect(() => {
    newNodeRef.current = new Set(newNodeIds);
    const state = sceneStateRef.current;
    if (state) syncGraph(state, graphRef.current, activeNodeRef.current, activeEdgeRef.current, newNodeRef.current, visualState);
  }, [newNodeIds, visualState]);

  useEffect(() => {
    if (!control) return;
    const state = sceneStateRef.current;
    if (!state) return;
    const { camera, group } = state;
    state.preserveSourceCoordinates = preserveSourceCoordinates;

    const totalNodes = graphRef.current?.nodes?.length ?? 0;
    state.userCameraControlUntilFrame = state.frame + 420;
    if (control.action === "zoom-in") camera.position.z = Math.max(3.2, camera.position.z - Math.max(1.2, camera.position.z * 0.12));
    if (control.action === "zoom-out") camera.position.z = Math.min(maxZoomDistanceForNodeCount(totalNodes), camera.position.z + Math.max(1.8, camera.position.z * 0.18));
    if (control.action === "left") group.rotation.y -= 0.22;
    if (control.action === "right") group.rotation.y += 0.22;
    if (control.action === "up") group.rotation.x -= 0.18;
    if (control.action === "down") group.rotation.x += 0.18;
    if (control.action === "reset") {
      camera.position.set(0, 0, Math.max(cameraDistanceForNodeCount(totalNodes), state.lastFitDistance));
      group.rotation.set(0, 0, 0);
    }
  }, [control]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const container = host;

    const scene = new THREE.Scene();
    const darkMode = theme === "dark";
    scene.background = new THREE.Color(darkMode ? 0x030303 : 0xf8faf8);
    const camera = new THREE.PerspectiveCamera(48, container.clientWidth / Math.max(1, container.clientHeight), 0.1, 16000);
    camera.position.set(0, 0, 13);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.setClearColor(new THREE.Color(darkMode ? 0x030303 : 0xf8faf8), 1);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(container.clientWidth, container.clientHeight);
    container.replaceChildren(renderer.domElement);

    const group = new THREE.Group();
    scene.add(group);
    scene.add(new THREE.AmbientLight(0xffffff, darkMode ? 0.78 : 1.25));
    const light = new THREE.DirectionalLight(0xffffff, darkMode ? 0.8 : 1.3);
    light.position.set(4, 7, 8);
    scene.add(light);

    const grid = new THREE.GridHelper(14, 14, darkMode ? 0x151515 : 0xcdd3cf, darkMode ? 0x0b0b0b : 0xe3e6e3);
    grid.rotation.x = Math.PI / 2;
    grid.position.z = -2.2;
    group.add(grid);

    const state: SceneState = {
      activeEdgeKeys: new Set(),
      activeNodeIds: new Set(),
      activationHops: new Map(),
      activationEdgeIntensity: new Map(),
      camera,
      coordinateMutationWarned: false,
      dynamicObjects: [],
      edgeCapacity: 0,
      edgeColorArray: null,
      edgeGeometry: null,
      edgeLines: null,
      edgePositionBufferDirty: true,
      edgePositionArray: null,
      edgePulseCount: 0,
      frame: 0,
      frozenPositionSnapshot: null,
      graphEdges: [],
      graphNodes: [],
      group,
      haloCapacity: 0,
      haloItems: [],
      haloMesh: null,
      knownNodeIds: new Set(),
      lastFitDistance: 0,
      lastGraphNodeCount: 0,
      lastViewportEmitFrame: -999,
      layoutDiagnostics: { layout_mode: "organic_semantic_force" },
      newNodeIds: new Set(),
      nodeBornAt: new Map(),
      nodeCapacity: 0,
      nodeColorArray: null,
      nodeGeometry: null,
      nodeIndexById: new Map(),
      nodePoints: null,
      nodePositionArray: null,
      nodePositionBufferDirty: true,
      nodePositionById: new Map(),
      nodeTargetById: new Map(),
      pointNodes: [],
      pulseCapacity: 0,
      pulseItems: [],
      pulseMesh: null,
      renderer,
      scene,
      startedAt: performance.now(),
      userCameraControlUntilFrame: 0,
      visibleEdges: [],
      visualState: resolveVisualState(visualState, graphRef.current, activeNodeRef.current, activeEdgeRef.current, newNodeRef.current),
      preserveSourceCoordinates,
      onViewportChange: viewportChangeRef.current,
    };
    sceneStateRef.current = state;
    syncGraph(state, graphRef.current, activeNodeRef.current, activeEdgeRef.current, newNodeRef.current, visualState);

    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    const drag = { active: false, moved: false, x: 0, y: 0 };

    function pointerEventToNdc(event: PointerEvent) {
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    }

    function handlePointerDown(event: PointerEvent) {
      state.userCameraControlUntilFrame = state.frame + 420;
      drag.active = true;
      drag.x = event.clientX;
      drag.y = event.clientY;
      drag.moved = false;
      renderer.domElement.setPointerCapture(event.pointerId);
    }

    function handlePointerMove(event: PointerEvent) {
      if (!drag.active) return;
      state.userCameraControlUntilFrame = state.frame + 420;
      const dx = event.clientX - drag.x;
      const dy = event.clientY - drag.y;
      if (Math.abs(dx) + Math.abs(dy) > 2) drag.moved = true;
      group.rotation.y += dx * 0.006;
      group.rotation.x += dy * 0.004;
      drag.x = event.clientX;
      drag.y = event.clientY;
    }

    function handlePointerUp(event: PointerEvent) {
      renderer.domElement.releasePointerCapture(event.pointerId);
      drag.active = false;
      if (drag.moved) return;
      pointerEventToNdc(event);
      raycaster.setFromCamera(pointer, camera);
      raycaster.params.Points.threshold = Math.max(0.22, camera.position.z * 0.006);
      const hit = state.nodePoints ? raycaster.intersectObject(state.nodePoints)[0] : null;
      if (hit && typeof hit.index === "number") {
        const node = state.pointNodes[hit.index];
        if (node) selectRef.current?.(node);
      }
    }

    function handleWheel(event: WheelEvent) {
      event.preventDefault();
      const totalNodes = graphRef.current?.nodes?.length ?? 0;
      state.userCameraControlUntilFrame = state.frame + 420;
      camera.position.z = Math.max(3.2, Math.min(maxZoomDistanceForNodeCount(totalNodes), camera.position.z + event.deltaY * Math.max(0.016, camera.position.z * 0.0018)));
    }

    function handleResize() {
      camera.aspect = container.clientWidth / Math.max(1, container.clientHeight);
      camera.updateProjectionMatrix();
      renderer.setSize(container.clientWidth, container.clientHeight);
    }

    renderer.domElement.addEventListener("pointerdown", handlePointerDown);
    renderer.domElement.addEventListener("pointermove", handlePointerMove);
    renderer.domElement.addEventListener("pointerup", handlePointerUp);
    renderer.domElement.addEventListener("wheel", handleWheel, { passive: false });
    window.addEventListener("resize", handleResize);

    let animation = 0;
    function animate() {
      animation = requestAnimationFrame(animate);
      state.frame += 1;
      const elapsed = (performance.now() - state.startedAt) / 1000;
      if (!drag.active && coordinateAnimationAllowed(state.visualState)) group.rotation.y += 0.00125;

      updateNodeBuffers(state, elapsed);
      updateEdgeBuffers(state, elapsed);
      updateHaloMesh(state, elapsed);
      updatePulseMesh(state, elapsed);

      const totalNodes = graphRef.current?.nodes?.length ?? 0;
      container.dataset.cameraZ = camera.position.z.toFixed(1);
      container.dataset.maxZoom = maxZoomDistanceForNodeCount(totalNodes).toFixed(1);
      container.dataset.nodeCount = String(totalNodes);
      container.dataset.activeEdgeCount = String(state.activeEdgeKeys.size);
      container.dataset.edgePulseCount = String(state.edgePulseCount);
      container.dataset.bufferMode = "persistent-append";
      container.dataset.visualState = state.visualState;
      container.dataset.layoutMode = String(state.layoutDiagnostics.layout_mode ?? "organic_semantic_force");
      container.dataset.activeClusterCount = String(state.layoutDiagnostics.active_cluster_count ?? 0);
      container.dataset.averageDegree = String(state.layoutDiagnostics.average_degree ?? 0);
      container.dataset.zAxisRatio = String(state.layoutDiagnostics.z_axis_ratio ?? 0);
      container.dataset.activeCentroidOffset = String(state.layoutDiagnostics.active_centroid_offset ?? 0);
      container.dataset.hop1Count = String(state.layoutDiagnostics.hop1_count ?? 0);
      container.dataset.hop2Count = String(state.layoutDiagnostics.hop2_count ?? 0);
      if (state.onViewportChange && state.frame - state.lastViewportEmitFrame >= 12) {
        state.lastViewportEmitFrame = state.frame;
        state.onViewportChange({
          cameraZ: camera.position.z,
          focus: { x: 0, y: 0, z: 0 },
          radius: viewportRadiusForCamera(camera),
        });
      }
      renderer.render(scene, camera);
    }
    animate();

    return () => {
      cancelAnimationFrame(animation);
      window.removeEventListener("resize", handleResize);
      renderer.domElement.removeEventListener("pointerdown", handlePointerDown);
      renderer.domElement.removeEventListener("pointermove", handlePointerMove);
      renderer.domElement.removeEventListener("pointerup", handlePointerUp);
      renderer.domElement.removeEventListener("wheel", handleWheel);
      removeDynamicObjects(state);
      if (state.nodePoints) {
        state.group.remove(state.nodePoints);
        disposeObject(state.nodePoints);
      }
      if (state.edgeLines) {
        state.group.remove(state.edgeLines);
        disposeObject(state.edgeLines);
      }
      if (state.haloMesh) {
        state.group.remove(state.haloMesh);
        disposeObject(state.haloMesh);
      }
      if (state.pulseMesh) {
        state.group.remove(state.pulseMesh);
        disposeObject(state.pulseMesh);
      }
      disposeObject(grid);
      renderer.dispose();
      container.replaceChildren();
      sceneStateRef.current = null;
    };
  }, [theme]);

  const displayVisualState = resolveVisualState(
    visualState,
    graph,
    new Set(activeNodeIds),
    new Set(activeEdgeKeys),
    new Set(newNodeIds),
  );
  const settledText = frozenStatusText(displayVisualState);

  return (
    <div className="rag3d-shell">
      <div className="rag3d-host" ref={hostRef} aria-label="3D RAG traversal graph" />
      {settledText ? <span className="rag3d-settled-label">{settledText}</span> : null}
    </div>
  );
}
