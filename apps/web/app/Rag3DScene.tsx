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
  control?: Rag3DControl;
  onSelect?: (node: Rag3DNode) => void;
};

type SceneState = {
  camera: THREE.PerspectiveCamera;
  dynamicObjects: THREE.Object3D[];
  edgePulseCount: number;
  frame: number;
  group: THREE.Group;
  knownNodeIds: Set<string>;
  lastFitDistance: number;
  nodePoints: THREE.Points | null;
  pointNodes: Rag3DNode[];
  renderer: THREE.WebGLRenderer;
  scene: THREE.Scene;
};

const palette: Record<string, number> = {
  source: 0xff6b35,
  critique: 0xc5283d,
  ontology: 0x1a936f,
  retrieval: 0x006a9f,
  visualization: 0x8c3fa7,
  guardrail: 0xe89d2a,
  training: 0x111715,
  concept: 0x22936f,
  keyword: 0x4a8fdb,
  heading: 0x7b8794,
  quality: 0x3f6f5f,
  memory: 0x1a936f,
  verification: 0xe89d2a,
  learning: 0x111715,
  efficiency: 0x006a9f,
  summary: 0x6d746f,
  token: 0x4a8fdb,
  predicate: 0xff6b35,
  phrase: 0x8c3fa7,
  compound: 0x1a936f,
  quantity: 0xe89d2a,
  relation: 0x73827a,
  verb: 0xff6b35,
};

function labelSprite(text: string, scale = 1) {
  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 128;
  const context = canvas.getContext("2d");
  if (context) {
    context.clearRect(0, 0, canvas.width, canvas.height);
    context.font = "700 42px Arial";
    context.fillStyle = "#141715";
    context.strokeStyle = "rgba(255,255,255,0.88)";
    context.lineWidth = 9;
    context.strokeText(text.slice(0, 22), 20, 76);
    context.fillText(text.slice(0, 22), 20, 76);
  }
  const texture = new THREE.CanvasTexture(canvas);
  const material = new THREE.SpriteMaterial({ map: texture, transparent: true });
  const sprite = new THREE.Sprite(material);
  sprite.scale.set(2.4 * scale, 0.6 * scale, 1);
  return sprite;
}

function shouldShowLabel(node: Rag3DNode, totalNodes: number, isActive: boolean) {
  if (node.id.startsWith("live-synapse")) return false;
  if (isActive) return true;
  return totalNodes <= 40;
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

function clearDynamicObjects(state: SceneState) {
  for (const object of state.dynamicObjects) {
    state.group.remove(object);
    disposeObject(object);
  }
  state.dynamicObjects = [];
  state.nodePoints = null;
  state.pointNodes = [];
}

function addDynamicObject(state: SceneState, object: THREE.Object3D) {
  state.dynamicObjects.push(object);
  state.group.add(object);
}

function edgeKey(source: string, target: string) {
  return `${source}:${target}`;
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
  const u = hashUnit(id, 13);
  const theta = (hashUnit(id, 29) + 1) * Math.PI;
  const radial = Math.sqrt(Math.max(0.0001, 1 - u * u));
  const volumeRadius = Math.min(20, 4.6 + Math.cbrt(Math.max(1, total)) * 0.9);
  const internalDepth = 0.28 + Math.cbrt(hash01(id, 47)) * 0.72;
  const localJitter = ((index % 19) / 19) * 0.22;
  const radius = volumeRadius * Math.min(1, internalDepth + localJitter);
  return new THREE.Vector3(
    Math.cos(theta) * radial * radius,
    u * radius * 0.96,
    Math.sin(theta) * radial * radius,
  );
}

function cameraDistanceForNodeCount(total: number) {
  return Math.min(210, 10 + Math.cbrt(Math.max(1, total)) * 3.3 + Math.sqrt(Math.max(1, total)) * 0.28);
}

function maxZoomDistanceForNodeCount(total: number) {
  const fitDistance = cameraDistanceForNodeCount(total);
  return Math.min(2600, Math.max(140, fitDistance * 12, Math.sqrt(Math.max(1, total)) * 14));
}

function clampCameraZ(camera: THREE.PerspectiveCamera, total: number) {
  camera.position.z = Math.max(4.8, Math.min(maxZoomDistanceForNodeCount(total), camera.position.z));
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
  const sourceLimit = Math.min(17, 4.2 + Math.cbrt(Math.max(1, nodes.length)) * 0.78);
  const scale = radius > sourceLimit ? sourceLimit / radius : 1;
  return rawPositions.map((position) => position.sub(center).multiplyScalar(scale));
}

function initialSpreadPosition(node: Rag3DNode, source: THREE.Vector3, index: number, total: number) {
  if (total <= 14) return source;
  const target = stableVolumePoint(node.id, index, total);
  const sourceWeight = node.id.startsWith("live-synapse") ? 0.55 : total > 800 ? 0.5 : 0.52;
  return source.multiplyScalar(sourceWeight).add(target.multiplyScalar(1 - sourceWeight));
}

function spreadPositions(nodes: Rag3DNode[]) {
  const sources = normalizedSourcePositions(nodes);
  const positions = nodes.map((node, index) => initialSpreadPosition(node, sources[index].clone(), index, nodes.length));
  if (nodes.length <= 1) return positions;
  if (nodes.length > 1_400) return positions;
  const minDistance = nodes.length > 700 ? 0.64 : nodes.length > 300 ? 0.72 : nodes.length > 140 ? 0.78 : nodes.length > 80 ? 0.66 : 0.74;
  const iterations = nodes.length > 700 ? 2 : nodes.length > 300 ? 3 : nodes.length > 140 ? 4 : nodes.length > 80 ? 5 : 7;
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
        const push = (minDistance - distance) * 0.5;
        delta.normalize().multiplyScalar(push);
        positions[left].add(delta);
        positions[right].sub(delta);
      }
    }
  }
  return positions;
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

function renderGraph(state: SceneState, graph: Rag3DGraph | null, activeNodeIds: Set<string>, activeEdgeKeys: Set<string>) {
  clearDynamicObjects(state);
  if (!graph?.nodes?.length) return;

  const nodeMap = new Map<string, THREE.Vector3>();
  const labelScale = graph.nodes.length > 18 ? 0.72 : graph.nodes.length > 12 ? 0.84 : 1;
  const nextKnownNodeIds = new Set<string>();
  const positions = spreadPositions(graph.nodes);
  const sphereSegments = graph.nodes.length > 1_200 ? 10 : graph.nodes.length > 600 ? 14 : 24;
  const identityQuaternion = new THREE.Quaternion();
  const ringQuaternion = new THREE.Quaternion().setFromEuler(new THREE.Euler(Math.PI / 2, 0, 0));
  const instanceMatrix = new THREE.Matrix4();
  const instanceColor = new THREE.Color();
  const instanceScale = new THREE.Vector3();
  const haloInstances: Array<{ color: number; position: THREE.Vector3; scale: number }> = [];
  const ringInstances: Array<{ position: THREE.Vector3; scale: number }> = [];
  const pulseInstances: Array<{ phase: number; source: THREE.Vector3; target: THREE.Vector3 }> = [];
  const fitDistance = fitDistanceForPositions(positions, state.camera);
  if (fitDistance > state.lastFitDistance || fitDistance > state.camera.position.z) {
    state.camera.position.z = Math.max(state.camera.position.z, fitDistance);
    state.lastFitDistance = fitDistance;
  } else if (state.camera.position.z > fitDistance * 1.32) {
    state.camera.position.z = fitDistance * 1.12;
    state.lastFitDistance = fitDistance;
  }
  clampCameraZ(state.camera, graph.nodes.length);

  const pointPositions = new Float32Array(graph.nodes.length * 3);
  const pointColors = new Float32Array(graph.nodes.length * 3);
  const colorValue = new THREE.Color();
  for (const [index, node] of graph.nodes.entries()) {
    nextKnownNodeIds.add(node.id);
    const position = positions[index];
    nodeMap.set(node.id, position);
    const isActive = activeNodeIds.has(node.id);
    const color = isActive ? 0xff6b35 : palette[node.type] ?? 0x68736d;
    pointPositions[index * 3] = position.x;
    pointPositions[index * 3 + 1] = position.y;
    pointPositions[index * 3 + 2] = position.z;
    colorValue.setHex(color);
    pointColors[index * 3] = colorValue.r;
    pointColors[index * 3 + 1] = colorValue.g;
    pointColors[index * 3 + 2] = colorValue.b;

    if (isActive || (node.type === "summary" && graph.nodes.length <= 2_000)) {
      const radius = (0.17 + (node.confidence ?? 0.7) * 0.12) * (isActive ? 1.22 : 1);
      haloInstances.push({
        color: isActive ? 0xff8a3d : color,
        position,
        scale: radius * (isActive ? 2.25 : 1.7),
      });
    }

    if (isActive) {
      const radius = (0.17 + (node.confidence ?? 0.7) * 0.12) * 1.22;
      ringInstances.push({ position, scale: radius * 2.55 });
    }

    if (shouldShowLabel(node, graph.nodes.length, isActive)) {
      const sprite = labelSprite(node.label, labelScale);
      sprite.position.set(position.x + 0.32, position.y + 0.18, position.z);
      addDynamicObject(state, sprite);
    }
  }
  const pointGeometry = new THREE.BufferGeometry();
  pointGeometry.setAttribute("position", new THREE.BufferAttribute(pointPositions, 3));
  pointGeometry.setAttribute("color", new THREE.BufferAttribute(pointColors, 3));
  pointGeometry.computeBoundingSphere();
  const pointMaterial = new THREE.PointsMaterial({
    size: graph.nodes.length > 100_000 ? 0.038 : graph.nodes.length > 25_000 ? 0.05 : graph.nodes.length > 5_000 ? 0.066 : 0.095,
    vertexColors: true,
    sizeAttenuation: true,
    transparent: true,
    opacity: 0.96,
  });
  const points = new THREE.Points(pointGeometry, pointMaterial);
  points.userData.kind = "node-points";
  state.nodePoints = points;
  state.pointNodes = graph.nodes;
  addDynamicObject(state, points);

  if (haloInstances.length) {
    const haloGeometry = new THREE.SphereGeometry(1, sphereSegments, sphereSegments);
    const haloMaterial = new THREE.MeshBasicMaterial({
      color: 0xffffff,
      transparent: true,
      opacity: activeNodeIds.size ? 0.3 : 0.08,
      vertexColors: true,
    });
    const halos = new THREE.InstancedMesh(haloGeometry, haloMaterial, haloInstances.length);
    haloInstances.forEach((halo, index) => {
      instanceScale.setScalar(halo.scale);
      instanceMatrix.compose(halo.position, identityQuaternion, instanceScale);
      halos.setMatrixAt(index, instanceMatrix);
      halos.setColorAt(index, instanceColor.setHex(halo.color));
    });
    halos.instanceMatrix.needsUpdate = true;
    if (halos.instanceColor) halos.instanceColor.needsUpdate = true;
    halos.userData.activeHalo = true;
    addDynamicObject(state, halos);
  }

  if (ringInstances.length) {
    const ringGeometry = new THREE.TorusGeometry(1, 0.035, 8, 40);
    const ringMaterial = new THREE.MeshBasicMaterial({ color: 0xff7a1a, transparent: true, opacity: 0.56 });
    const rings = new THREE.InstancedMesh(ringGeometry, ringMaterial, ringInstances.length);
    ringInstances.forEach((ring, index) => {
      instanceScale.setScalar(ring.scale);
      instanceMatrix.compose(ring.position, ringQuaternion, instanceScale);
      rings.setMatrixAt(index, instanceMatrix);
    });
    rings.instanceMatrix.needsUpdate = true;
    rings.userData.activeHalo = true;
    addDynamicObject(state, rings);
  }

  const traversalPairs = new Set<string>();
  for (let index = 0; index < (graph.traversal_path?.length ?? 0) - 1; index += 1) {
    traversalPairs.add(`${graph.traversal_path?.[index]}:${graph.traversal_path?.[index + 1]}`);
  }

  let edgePulseCount = 0;
  const maxEdges = graph.nodes.length > 100_000 ? 18_000 : graph.nodes.length > 25_000 ? 14_000 : graph.nodes.length > 5_000 ? 9_000 : graph.nodes.length > 1_600 ? 5_000 : Number.POSITIVE_INFINITY;
  const edgeStride = Number.isFinite(maxEdges) && graph.edges.length > maxEdges
    ? Math.ceil(graph.edges.length / maxEdges)
    : 1;
  const edgePositions: number[] = [];
  const edgeColors: number[] = [];
  for (const [index, edge] of graph.edges.entries()) {
    const isTraversalCandidate = traversalPairs.has(`${edge.source}:${edge.target}`);
    const isActiveCandidate = activeEdgeKeys.has(edgeKey(edge.source, edge.target)) || activeEdgeKeys.has(edgeKey(edge.target, edge.source));
    if (!isTraversalCandidate && !isActiveCandidate && index % edgeStride !== 0) continue;
    const source = nodeMap.get(edge.source);
    const target = nodeMap.get(edge.target);
    if (!source || !target) continue;
    const isTraversal = isTraversalCandidate;
    const isActive = isActiveCandidate;
    const edgeColor = isActive ? 0xff6b35 : isTraversal ? 0x9aa39e : 0x73827a;
    colorValue.setHex(edgeColor);
    edgePositions.push(source.x, source.y, source.z, target.x, target.y, target.z);
    edgeColors.push(colorValue.r, colorValue.g, colorValue.b, colorValue.r, colorValue.g, colorValue.b);

    if (isActive) {
      for (let pulse = 0; pulse < 3; pulse += 1) {
        pulseInstances.push({
          source: source.clone(),
          target: target.clone(),
          phase: pulse / 3,
        });
        edgePulseCount += 1;
      }
    }
  }
  if (edgePositions.length) {
    const edgeGeometry = new THREE.BufferGeometry();
    edgeGeometry.setAttribute("position", new THREE.Float32BufferAttribute(edgePositions, 3));
    edgeGeometry.setAttribute("color", new THREE.Float32BufferAttribute(edgeColors, 3));
    const edgeMaterial = new THREE.LineBasicMaterial({
      vertexColors: true,
      transparent: true,
      opacity: graph.nodes.length > 25_000 ? 0.32 : 0.5,
    });
    addDynamicObject(state, new THREE.LineSegments(edgeGeometry, edgeMaterial));
  }
  if (pulseInstances.length) {
    const pulseGeometry = new THREE.SphereGeometry(1, 8, 8);
    const pulseMaterial = new THREE.MeshBasicMaterial({ color: 0xff7a1a, transparent: true, opacity: 0.76 });
    const pulses = new THREE.InstancedMesh(pulseGeometry, pulseMaterial, pulseInstances.length);
    pulseInstances.forEach((pulse, index) => {
      instanceScale.setScalar(0.08);
      instanceMatrix.compose(pulse.source, identityQuaternion, instanceScale);
      pulses.setMatrixAt(index, instanceMatrix);
    });
    pulses.instanceMatrix.needsUpdate = true;
    pulses.userData.edgePulseBatch = pulseInstances;
    addDynamicObject(state, pulses);
  }
  state.edgePulseCount = edgePulseCount;
  state.knownNodeIds = nextKnownNodeIds;
}

export default function Rag3DScene({ graph, activeEdgeKeys = [], activeNodeIds = [], control, onSelect }: Rag3DSceneProps) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const selectRef = useRef(onSelect);
  const sceneStateRef = useRef<SceneState | null>(null);
  const activeEdgeRef = useRef(new Set(activeEdgeKeys));
  const activeNodeRef = useRef(new Set(activeNodeIds));
  const graphRef = useRef<Rag3DGraph | null>(graph);

  useEffect(() => {
    selectRef.current = onSelect;
  }, [onSelect]);

  useEffect(() => {
    graphRef.current = graph;
    const state = sceneStateRef.current;
    if (state) renderGraph(state, graph, activeNodeRef.current, activeEdgeRef.current);
  }, [graph]);

  useEffect(() => {
    activeNodeRef.current = new Set(activeNodeIds);
    activeEdgeRef.current = new Set(activeEdgeKeys);
    const state = sceneStateRef.current;
    if (state) renderGraph(state, graphRef.current, activeNodeRef.current, activeEdgeRef.current);
  }, [activeEdgeKeys, activeNodeIds]);

  useEffect(() => {
    if (!control) return;
    const state = sceneStateRef.current;
    if (!state) return;
    const { camera, group } = state;

    const totalNodes = graphRef.current?.nodes?.length ?? 0;
    if (control.action === "zoom-in") camera.position.z = Math.max(4.8, camera.position.z - Math.max(1.1, camera.position.z * 0.09));
    if (control.action === "zoom-out") camera.position.z = Math.min(maxZoomDistanceForNodeCount(totalNodes), camera.position.z + Math.max(1.2, camera.position.z * 0.13));
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
    scene.background = new THREE.Color(0xf8faf8);
    const camera = new THREE.PerspectiveCamera(48, container.clientWidth / Math.max(1, container.clientHeight), 0.1, 5000);
    camera.position.set(0, 0, 13);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(container.clientWidth, container.clientHeight);
    container.replaceChildren(renderer.domElement);

    const group = new THREE.Group();
    scene.add(group);
    scene.add(new THREE.AmbientLight(0xffffff, 1.6));
    const light = new THREE.DirectionalLight(0xffffff, 1.4);
    light.position.set(4, 7, 8);
    scene.add(light);

    const grid = new THREE.GridHelper(14, 14, 0xcdd3cf, 0xe3e6e3);
    grid.rotation.x = Math.PI / 2;
    grid.position.z = -2.2;
    group.add(grid);

    const state: SceneState = {
      camera,
      dynamicObjects: [],
      edgePulseCount: 0,
      frame: 0,
      group,
      knownNodeIds: new Set(),
      lastFitDistance: 0,
      nodePoints: null,
      pointNodes: [],
      renderer,
      scene,
    };
    sceneStateRef.current = state;
    renderGraph(state, graphRef.current, activeNodeRef.current, activeEdgeRef.current);

    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    const drag = { active: false, x: 0, y: 0, moved: false };

    function pointerEventToNdc(event: PointerEvent) {
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    }

    function handlePointerDown(event: PointerEvent) {
      drag.active = true;
      drag.x = event.clientX;
      drag.y = event.clientY;
      drag.moved = false;
      renderer.domElement.setPointerCapture(event.pointerId);
    }

    function handlePointerMove(event: PointerEvent) {
      if (!drag.active) return;
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
      camera.position.z = Math.max(4.8, Math.min(maxZoomDistanceForNodeCount(totalNodes), camera.position.z + event.deltaY * Math.max(0.01, camera.position.z * 0.0009)));
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
      if (!drag.active) group.rotation.y += 0.00125;
      for (const object of state.dynamicObjects) {
        if (!object.userData.activeHalo) continue;
        const pulse = 1 + Math.sin(state.frame * 0.16 + object.position.y) * 0.2;
        object.scale.setScalar(pulse);
      }
      for (const object of state.dynamicObjects) {
        const pulse = object.userData.edgePulse as { source: THREE.Vector3; target: THREE.Vector3; phase: number } | undefined;
        const pulseBatch = object.userData.edgePulseBatch as Array<{ source: THREE.Vector3; target: THREE.Vector3; phase: number }> | undefined;
        if (pulseBatch && object instanceof THREE.InstancedMesh) {
          const matrix = new THREE.Matrix4();
          const scale = new THREE.Vector3();
          const position = new THREE.Vector3();
          const quaternion = new THREE.Quaternion();
          pulseBatch.forEach((item, index) => {
            const t = (state.frame * 0.018 + item.phase) % 1;
            position.copy(item.source).lerp(item.target, t);
            scale.setScalar(0.06 + Math.sin(t * Math.PI) * 0.075);
            matrix.compose(position, quaternion, scale);
            object.setMatrixAt(index, matrix);
          });
          object.instanceMatrix.needsUpdate = true;
          continue;
        }
        if (!pulse) continue;
        const t = (state.frame * 0.018 + pulse.phase) % 1;
        object.position.copy(pulse.source).lerp(pulse.target, t);
        object.scale.setScalar(0.75 + Math.sin((t * Math.PI)) * 0.7);
      }
      const totalNodes = graphRef.current?.nodes?.length ?? 0;
      container.dataset.cameraZ = camera.position.z.toFixed(1);
      container.dataset.maxZoom = maxZoomDistanceForNodeCount(totalNodes).toFixed(1);
      container.dataset.nodeCount = String(totalNodes);
      container.dataset.activeEdgeCount = String(activeEdgeRef.current.size);
      container.dataset.edgePulseCount = String(state.edgePulseCount);
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
      clearDynamicObjects(state);
      renderer.dispose();
      container.replaceChildren();
      sceneStateRef.current = null;
      disposeObject(grid);
    };
  }, []);

  return <div className="rag3d-host" ref={hostRef} aria-label="3D RAG traversal graph" />;
}
