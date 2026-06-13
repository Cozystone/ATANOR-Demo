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
};

export type Rag3DEdge = {
  source: string;
  target: string;
  relation: string;
  weight?: number;
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
  camera: THREE.PerspectiveCamera;
  dynamicObjects: THREE.Object3D[];
  edgeCapacity: number;
  edgeColorArray: Float32Array | null;
  edgeGeometry: THREE.BufferGeometry | null;
  edgeLines: THREE.LineSegments | null;
  edgePositionArray: Float32Array | null;
  edgePulseCount: number;
  frame: number;
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
  newNodeIds: Set<string>;
  nodeBornAt: Map<string, number>;
  nodeCapacity: number;
  nodeColorArray: Float32Array | null;
  nodeGeometry: THREE.BufferGeometry | null;
  nodeIndexById: Map<string, number>;
  nodePoints: THREE.Points | null;
  nodePositionArray: Float32Array | null;
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
  preserveSourceCoordinates: boolean;
  onViewportChange?: Rag3DSceneProps["onViewportChange"];
};

const BASE_NODE_COLOR = 0x7f8a99;
const BASE_EDGE_COLOR = 0x334155;
const BASE_EDGE_ACTIVE_NEAR = 0x64748b;
const NEON_ORANGE = 0xff5500;
const COLD_LABEL = "#e8e8e2";
const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));
const NEW_NODE_ANIMATION_SECONDS = 1.5;

const baseNodeColor = new THREE.Color(BASE_NODE_COLOR);
const baseEdgeColor = new THREE.Color(BASE_EDGE_COLOR);
const nearActiveEdgeColor = new THREE.Color(BASE_EDGE_ACTIVE_NEAR);
const neonOrangeColor = new THREE.Color(NEON_ORANGE);
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

function spreadPositions(nodes: Rag3DNode[]) {
  const sources = normalizedSourcePositions(nodes);
  const positions = nodes.map((node, index) => initialSpreadPosition(node, sources[index].clone(), index, nodes.length));
  if (nodes.length <= 1) return positions;
  if (nodes.length > 5_000) return positions;
  const minDistance = nodes.length > 1_400 ? 0.86 : nodes.length > 700 ? 0.98 : nodes.length > 300 ? 1.08 : nodes.length > 140 ? 1.02 : nodes.length > 80 ? 0.9 : 0.82;
  const iterations = nodes.length > 1_400 ? 2 : nodes.length > 700 ? 4 : nodes.length > 300 ? 6 : nodes.length > 140 ? 7 : nodes.length > 80 ? 8 : 9;
  const repulsionStrength = nodes.length > 1_400 ? 0.62 : nodes.length > 700 ? 0.68 : 0.74;
  for (let pass = 0; pass < iterations; pass += 1) {
    for (let left = 0; left < positions.length; left += 1) {
      for (let right = left + 1; right < positions.length; right += 1) {
        const delta = positions[left].clone().sub(positions[right]);
        let distance = delta.length();
        if (distance >= minDistance) continue;
        if (distance < 0.001) {
          delta.set(
            ((left % 3) - 1) * 0.015 + 0.01,
            ((right % 5) - 2) * 0.015 + 0.01,
            0.02,
          );
          distance = delta.length();
        }
        const push = (minDistance - distance) * repulsionStrength;
        delta.normalize().multiplyScalar(push);
        positions[left].add(delta);
        positions[right].sub(delta);
      }
    }
  }
  const center = new THREE.Vector3();
  positions.forEach((position) => center.add(position));
  center.divideScalar(positions.length);
  positions.forEach((position) => position.sub(center));
  return positions;
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
  const geometry = new THREE.TorusGeometry(1, 0.038, 8, 56);
  const material = new THREE.MeshBasicMaterial({
    blending: THREE.NormalBlending,
    color: NEON_ORANGE,
    depthTest: false,
    depthWrite: false,
    opacity: 0.72,
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

function syncGraph(state: SceneState, graph: Rag3DGraph | null, activeNodeIds: Set<string>, activeEdgeKeys: Set<string>, newNodeIds: Set<string>) {
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
  const targets = state.preserveSourceCoordinates ? sourceCoordinatePositions(graph.nodes) : spreadPositions(graph.nodes);
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
      const spawn = findSpawnPositionForNode(node.id, graph.edges, state.nodePositionById, target);
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
    const traversalActive = traversalPairs.has(`${edge.source}:${edge.target}`);
    if (!explicitActive && !directActive && !traversalActive && index % edgeStride !== 0) continue;
    state.visibleEdges.push({ ...edge, active: explicitActive || directActive || traversalActive, index });
  }

  ensureNodeBuffers(state, graph.nodes.length);
  ensureEdgeBuffers(state, state.visibleEdges.length * 2);

  state.haloItems = graph.nodes
    .filter((node) => {
      const bornAt = state.nodeBornAt.get(node.id);
      const newPulse = typeof bornAt === "number" && elapsed - bornAt < NEW_NODE_ANIMATION_SECONDS;
      return activeNodeIds.has(node.id) || newNodeIds.has(node.id) || newPulse;
    })
    .slice(0, 512)
    .map((node) => {
      const bornAt = state.nodeBornAt.get(node.id) ?? elapsed;
      const position = state.nodePositionById.get(node.id) ?? state.nodeTargetById.get(node.id) ?? new THREE.Vector3();
      return {
        bornAt,
        id: node.id,
        newNode: newNodeIds.has(node.id) || elapsed - bornAt < NEW_NODE_ANIMATION_SECONDS,
        position,
        scale: 0.72 + (node.confidence ?? 0.65) * 0.38,
      };
    });
  ensureHaloMesh(state, state.haloItems.length);

  state.pulseItems = state.visibleEdges
    .filter((edge) => edge.active)
    .slice(0, 640)
    .flatMap((edge) => [0, 1, 2].map((pulse) => ({ source: edge.source, target: edge.target, phase: pulse / 3 })));
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
  const bornAt = state.nodeBornAt.get(node.id);
  const newAge = typeof bornAt === "number" ? elapsed - bornAt : Number.POSITIVE_INFINITY;
  const newPulse = state.newNodeIds.has(node.id) || newAge < NEW_NODE_ANIMATION_SECONDS;
  if (active) return 0.76 + Math.sin(elapsed * 10 + hash01(node.id, 31) * Math.PI * 2) * 0.24;
  if (newPulse) return THREE.MathUtils.clamp(1 - newAge / NEW_NODE_ANIMATION_SECONDS, 0, 1);
  return 0;
}

function edgeSignalStrength(state: SceneState, edge: VisibleEdge, elapsed: number) {
  if (!edge.active) return 0;
  const phase = hash01(edge.source + edge.target, 19) * Math.PI * 2;
  return 0.68 + Math.sin(elapsed * 10 + phase) * 0.32;
}

function updateNodeBuffers(state: SceneState, elapsed: number) {
  if (!state.nodePositionArray || !state.nodeColorArray || !state.nodeGeometry) return;
  const positionAttribute = state.nodeGeometry.getAttribute("position") as THREE.BufferAttribute;
  const colorAttribute = state.nodeGeometry.getAttribute("color") as THREE.BufferAttribute;

  state.graphNodes.forEach((node, index) => {
    const position = state.nodePositionById.get(node.id) ?? new THREE.Vector3();
    const target = state.nodeTargetById.get(node.id) ?? position;
    const bornAt = state.nodeBornAt.get(node.id);
    const age = typeof bornAt === "number" ? elapsed - bornAt : 99;
    const expansionRate = age < NEW_NODE_ANIMATION_SECONDS ? 0.115 : 0.045;
    position.lerp(target, expansionRate);

    state.nodePositionArray![index * 3] = position.x;
    state.nodePositionArray![index * 3 + 1] = position.y;
    state.nodePositionArray![index * 3 + 2] = position.z;

    const signal = nodeSignalStrength(state, node, elapsed);
    tempColor.copy(baseNodeColor).lerp(neonOrangeColor, signal);
    state.nodeColorArray![index * 3] = tempColor.r;
    state.nodeColorArray![index * 3 + 1] = tempColor.g;
    state.nodeColorArray![index * 3 + 2] = tempColor.b;
  });

  positionAttribute.needsUpdate = true;
  colorAttribute.needsUpdate = true;
  state.nodeGeometry.computeBoundingSphere();
}

function updateEdgeBuffers(state: SceneState, elapsed: number) {
  if (!state.edgePositionArray || !state.edgeColorArray || !state.edgeGeometry) return;
  const positionAttribute = state.edgeGeometry.getAttribute("position") as THREE.BufferAttribute;
  const colorAttribute = state.edgeGeometry.getAttribute("color") as THREE.BufferAttribute;

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

  positionAttribute.needsUpdate = true;
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
    const ringScale = halo.scale * (halo.newNode ? THREE.MathUtils.lerp(4.2, 1.15, t) : THREE.MathUtils.lerp(1.8, 2.28, signal));
    tempScale.setScalar(Math.max(0.001, ringScale));
    tempMatrix.compose(position, tempRingQuaternion, tempScale);
    state.haloMesh!.setMatrixAt(index, tempMatrix);
  });
  const material = state.haloMesh.material as THREE.MeshBasicMaterial;
  material.opacity = state.haloItems.some((halo) => halo.newNode) ? 0.62 : 0.36;
  material.needsUpdate = true;
  state.haloMesh.instanceMatrix.needsUpdate = true;
}

function updatePulseMesh(state: SceneState, elapsed: number) {
  if (!state.pulseMesh) return;
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
    if (state) syncGraph(state, graph, activeNodeRef.current, activeEdgeRef.current, newNodeRef.current);
  }, [graph]);

  useEffect(() => {
    const state = sceneStateRef.current;
    if (!state) return;
    state.preserveSourceCoordinates = preserveSourceCoordinates;
    syncGraph(state, graphRef.current, activeNodeRef.current, activeEdgeRef.current, newNodeRef.current);
  }, [preserveSourceCoordinates]);

  useEffect(() => {
    activeNodeRef.current = new Set(activeNodeIds);
    activeEdgeRef.current = new Set(activeEdgeKeys);
    const state = sceneStateRef.current;
    if (state) syncGraph(state, graphRef.current, activeNodeRef.current, activeEdgeRef.current, newNodeRef.current);
  }, [activeEdgeKeys, activeNodeIds]);

  useEffect(() => {
    newNodeRef.current = new Set(newNodeIds);
    const state = sceneStateRef.current;
    if (state) syncGraph(state, graphRef.current, activeNodeRef.current, activeEdgeRef.current, newNodeRef.current);
  }, [newNodeIds]);

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
      camera,
      dynamicObjects: [],
      edgeCapacity: 0,
      edgeColorArray: null,
      edgeGeometry: null,
      edgeLines: null,
      edgePositionArray: null,
      edgePulseCount: 0,
      frame: 0,
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
      newNodeIds: new Set(),
      nodeBornAt: new Map(),
      nodeCapacity: 0,
      nodeColorArray: null,
      nodeGeometry: null,
      nodeIndexById: new Map(),
      nodePoints: null,
      nodePositionArray: null,
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
      preserveSourceCoordinates,
      onViewportChange: viewportChangeRef.current,
    };
    sceneStateRef.current = state;
    syncGraph(state, graphRef.current, activeNodeRef.current, activeEdgeRef.current, newNodeRef.current);

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
      if (!drag.active) group.rotation.y += 0.00125;

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

  return <div className="rag3d-host" ref={hostRef} aria-label="3D RAG traversal graph" />;
}
