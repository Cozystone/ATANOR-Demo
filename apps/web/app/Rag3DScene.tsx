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
  frame: number;
  group: THREE.Group;
  knownNodeIds: Set<string>;
  raycastMeshes: THREE.Mesh[];
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
  state.raycastMeshes = [];
}

function addDynamicObject(state: SceneState, object: THREE.Object3D) {
  state.dynamicObjects.push(object);
  state.group.add(object);
}

function edgeKey(source: string, target: string) {
  return `${source}:${target}`;
}

function cameraDistanceForNodeCount(total: number) {
  return Math.min(44, 11 + Math.sqrt(Math.max(1, total)) * 0.82);
}

function maxZoomDistanceForNodeCount(total: number) {
  const fitDistance = cameraDistanceForNodeCount(total);
  return Math.min(900, Math.max(80, fitDistance * 7.5, Math.sqrt(Math.max(1, total)) * 7.2));
}

function clampCameraZ(camera: THREE.PerspectiveCamera, total: number) {
  camera.position.z = Math.max(4.8, Math.min(maxZoomDistanceForNodeCount(total), camera.position.z));
}

function initialSpreadPosition(node: Rag3DNode, index: number, total: number) {
  const source = new THREE.Vector3(node.x, node.y, node.z);
  if (total <= 14) return source;
  const goldenAngle = Math.PI * (3 - Math.sqrt(5));
  const offset = index + 0.5;
  const y = 1 - (offset / total) * 2;
  const radial = Math.sqrt(Math.max(0, 1 - y * y));
  const shell = 3.6 + Math.sqrt(total) * 0.54;
  const angle = index * goldenAngle;
  const target = new THREE.Vector3(
    Math.cos(angle) * radial * shell,
    y * shell * 0.82,
    Math.sin(angle) * radial * shell,
  );
  const sourceWeight = total > 90 ? 0.18 : total > 40 ? 0.28 : 0.42;
  return source.multiplyScalar(sourceWeight).add(target.multiplyScalar(1 - sourceWeight));
}

function spreadPositions(nodes: Rag3DNode[]) {
  const positions = nodes.map((node, index) => initialSpreadPosition(node, index, nodes.length));
  if (nodes.length <= 1) return positions;
  const minDistance = nodes.length > 140 ? 0.38 : nodes.length > 80 ? 0.48 : nodes.length > 40 ? 0.58 : 0.74;
  const iterations = nodes.length > 140 ? 4 : nodes.length > 80 ? 5 : 7;
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

function renderGraph(state: SceneState, graph: Rag3DGraph | null, activeNodeIds: Set<string>, activeEdgeKeys: Set<string>) {
  clearDynamicObjects(state);
  if (!graph?.nodes?.length) return;

  const nodeMap = new Map<string, THREE.Vector3>();
  const labelScale = graph.nodes.length > 18 ? 0.72 : graph.nodes.length > 12 ? 0.84 : 1;
  const nextKnownNodeIds = new Set<string>();
  const positions = spreadPositions(graph.nodes);
  state.camera.position.z = Math.max(state.camera.position.z, cameraDistanceForNodeCount(graph.nodes.length));
  clampCameraZ(state.camera, graph.nodes.length);

  for (const [index, node] of graph.nodes.entries()) {
    nextKnownNodeIds.add(node.id);
    const position = positions[index];
    nodeMap.set(node.id, position);
    const isActive = activeNodeIds.has(node.id);
    const color = isActive ? 0xff6b35 : palette[node.type] ?? 0x68736d;
    const radius = 0.17 + (node.confidence ?? 0.7) * 0.12;
    const geometry = new THREE.SphereGeometry(radius, 24, 24);
    const material = new THREE.MeshStandardMaterial({
      color,
      emissive: isActive ? 0xff6b35 : 0x000000,
      emissiveIntensity: isActive ? 0.72 : 0,
      roughness: 0.42,
      metalness: 0.18,
    });
    const mesh = new THREE.Mesh(geometry, material);
    mesh.position.copy(position);
    mesh.userData.node = node;
    mesh.userData.active = isActive;
    mesh.userData.spawnFrame = state.knownNodeIds.has(node.id) ? state.frame - 100 : state.frame;
    state.raycastMeshes.push(mesh);
    addDynamicObject(state, mesh);

    const halo = new THREE.Mesh(
      new THREE.SphereGeometry(radius * 1.7, 24, 24),
      new THREE.MeshBasicMaterial({ color, transparent: true, opacity: isActive ? 0.26 : 0.08 }),
    );
    halo.position.copy(position);
    addDynamicObject(state, halo);

    if (shouldShowLabel(node, graph.nodes.length, isActive)) {
      const sprite = labelSprite(node.label, labelScale);
      sprite.position.set(position.x + 0.32, position.y + 0.18, position.z);
      addDynamicObject(state, sprite);
    }
  }

  const traversalPairs = new Set<string>();
  for (let index = 0; index < (graph.traversal_path?.length ?? 0) - 1; index += 1) {
    traversalPairs.add(`${graph.traversal_path?.[index]}:${graph.traversal_path?.[index + 1]}`);
  }

  for (const edge of graph.edges) {
    const source = nodeMap.get(edge.source);
    const target = nodeMap.get(edge.target);
    if (!source || !target) continue;
    const isTraversal = traversalPairs.has(`${edge.source}:${edge.target}`);
    const isActive = activeEdgeKeys.has(edgeKey(edge.source, edge.target)) || activeEdgeKeys.has(edgeKey(edge.target, edge.source));
    const geometry = new THREE.BufferGeometry().setFromPoints([source, target]);
    const material = new THREE.LineBasicMaterial({
      color: isActive ? 0xff6b35 : isTraversal ? 0x9aa39e : 0x73827a,
      transparent: true,
      opacity: isActive ? 0.9 : isTraversal ? 0.7 : 0.52,
    });
    addDynamicObject(state, new THREE.Line(geometry, material));
  }
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
      camera.position.set(0, 0, cameraDistanceForNodeCount(totalNodes));
      group.rotation.set(0, 0, 0);
    }
  }, [control]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const container = host;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf8faf8);
    const camera = new THREE.PerspectiveCamera(48, container.clientWidth / Math.max(1, container.clientHeight), 0.1, 1000);
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
      frame: 0,
      group,
      knownNodeIds: new Set(),
      raycastMeshes: [],
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
      const hit = raycaster.intersectObjects(state.raycastMeshes)[0];
      if (hit?.object.userData.node) selectRef.current?.(hit.object.userData.node);
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
      for (const mesh of state.raycastMeshes) {
        const age = Math.min(1, (state.frame - (mesh.userData.spawnFrame ?? state.frame)) / 18);
        const activePulse = mesh.userData.active ? 1 + Math.sin(state.frame * 0.14 + mesh.position.x) * 0.18 : 1;
        mesh.scale.setScalar(age * activePulse * (1 + Math.sin(state.frame * 0.02 + mesh.position.x) * 0.025));
      }
      const totalNodes = graphRef.current?.nodes?.length ?? 0;
      container.dataset.cameraZ = camera.position.z.toFixed(1);
      container.dataset.maxZoom = maxZoomDistanceForNodeCount(totalNodes).toFixed(1);
      container.dataset.nodeCount = String(totalNodes);
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
