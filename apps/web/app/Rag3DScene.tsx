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
  control?: Rag3DControl;
  onSelect?: (node: Rag3DNode) => void;
};

const palette: Record<string, number> = {
  source: 0xff6b35,
  critique: 0xc5283d,
  ontology: 0x1a936f,
  retrieval: 0x006a9f,
  visualization: 0x8c3fa7,
  guardrail: 0xe89d2a,
  training: 0x111715,
};

function labelSprite(text: string) {
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
  sprite.scale.set(2.4, 0.6, 1);
  return sprite;
}

export default function Rag3DScene({ graph, control, onSelect }: Rag3DSceneProps) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const selectRef = useRef(onSelect);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const groupRef = useRef<THREE.Group | null>(null);

  useEffect(() => {
    selectRef.current = onSelect;
  }, [onSelect]);

  useEffect(() => {
    if (!control) return;
    const camera = cameraRef.current;
    const group = groupRef.current;
    if (!camera || !group) return;

    if (control.action === "zoom-in") camera.position.z = Math.max(5.2, camera.position.z - 1.1);
    if (control.action === "zoom-out") camera.position.z = Math.min(25, camera.position.z + 1.1);
    if (control.action === "left") group.rotation.y -= 0.22;
    if (control.action === "right") group.rotation.y += 0.22;
    if (control.action === "up") group.rotation.x -= 0.18;
    if (control.action === "down") group.rotation.x += 0.18;
    if (control.action === "reset") {
      camera.position.set(0, 0, 13);
      group.rotation.set(0, 0, 0);
    }
  }, [control]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host || !graph?.nodes?.length) return;
    const container = host;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf8faf8);
    const camera = new THREE.PerspectiveCamera(48, container.clientWidth / Math.max(1, container.clientHeight), 0.1, 1000);
    camera.position.set(0, 0, 13);
    cameraRef.current = camera;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(container.clientWidth, container.clientHeight);
    container.replaceChildren(renderer.domElement);

    const group = new THREE.Group();
    groupRef.current = group;
    scene.add(group);
    scene.add(new THREE.AmbientLight(0xffffff, 1.6));
    const light = new THREE.DirectionalLight(0xffffff, 1.4);
    light.position.set(4, 7, 8);
    scene.add(light);

    const grid = new THREE.GridHelper(14, 14, 0xcdd3cf, 0xe3e6e3);
    grid.rotation.x = Math.PI / 2;
    grid.position.z = -2.2;
    group.add(grid);

    const nodeMap = new Map<string, THREE.Vector3>();
    const raycastMeshes: THREE.Mesh[] = [];
    for (const node of graph.nodes) {
      const position = new THREE.Vector3(node.x, node.y, node.z);
      nodeMap.set(node.id, position);
      const color = palette[node.type] ?? 0x68736d;
      const geometry = new THREE.SphereGeometry(0.17 + (node.confidence ?? 0.7) * 0.12, 24, 24);
      const material = new THREE.MeshStandardMaterial({ color, roughness: 0.42, metalness: 0.18 });
      const mesh = new THREE.Mesh(geometry, material);
      mesh.position.copy(position);
      mesh.userData.node = node;
      raycastMeshes.push(mesh);
      group.add(mesh);

      const halo = new THREE.Mesh(
        new THREE.SphereGeometry(0.36, 24, 24),
        new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.08 }),
      );
      halo.position.copy(position);
      group.add(halo);

      const sprite = labelSprite(node.label);
      sprite.position.set(position.x + 0.32, position.y + 0.18, position.z);
      group.add(sprite);
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
      const geometry = new THREE.BufferGeometry().setFromPoints([source, target]);
      const material = new THREE.LineBasicMaterial({
        color: isTraversal ? 0xff6b35 : 0x7d8780,
        transparent: true,
        opacity: isTraversal ? 0.95 : 0.42,
      });
      group.add(new THREE.Line(geometry, material));
    }

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
      const hit = raycaster.intersectObjects(raycastMeshes)[0];
      if (hit?.object.userData.node) selectRef.current?.(hit.object.userData.node);
    }

    function handleWheel(event: WheelEvent) {
      event.preventDefault();
      camera.position.z = Math.max(6, Math.min(22, camera.position.z + event.deltaY * 0.01));
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

    let frame = 0;
    let animation = 0;
    function animate() {
      animation = requestAnimationFrame(animate);
      frame += 1;
      if (!drag.active) group.rotation.y += 0.0018;
      for (const mesh of raycastMeshes) {
        mesh.scale.setScalar(1 + Math.sin(frame * 0.025 + mesh.position.x) * 0.035);
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
      renderer.dispose();
      container.replaceChildren();
      cameraRef.current = null;
      groupRef.current = null;
      scene.traverse((object) => {
        const mesh = object as THREE.Mesh;
        mesh.geometry?.dispose?.();
        const material = mesh.material as THREE.Material | THREE.Material[] | undefined;
        if (Array.isArray(material)) material.forEach((item) => item.dispose());
        else material?.dispose?.();
      });
    };
  }, [graph]);

  return <div className="rag3d-host" ref={hostRef} aria-label="3D RAG traversal graph" />;
}
