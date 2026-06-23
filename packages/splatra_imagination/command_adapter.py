from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from typing import Any, Literal

from .generator import ImaginationGenerator, select_archetype
from .models import Archetype, ImaginationFrame, ImaginationSeed, default_safety_flags


SceneCommand = Literal["spawn_object", "morph", "render_knowledge_hologram"]


ARCHETYPE_HINTS: dict[Archetype, tuple[str, ...]] = {
    "orb": ("sphere", "orb", "ball", "구", "구슬", "공"),
    "tower": ("tower", "spire", "building", "탑", "기둥"),
    "tree": ("tree", "branch", "forest", "나무", "가지", "숲"),
    "creature": ("creature", "animal", "character", "mascot", "생물", "동물", "캐릭터"),
    "circuit": ("circuit", "chip", "network", "trace", "회로", "칩", "네트워크"),
    "city_block": ("city", "street", "skyline", "block", "도시", "거리", "건물"),
    "constellation": ("constellation", "star", "galaxy", "별자리", "별", "은하"),
    "machine_core": ("machine", "engine", "reactor", "core", "기계", "엔진", "코어", "원자로"),
    "abstract_memory_cloud": ("cloud", "memory", "nebula", "thought", "구름", "기억", "성운", "생각"),
}


@dataclass(frozen=True)
class SplatraCommandPlan:
    plan_id: str
    command: str
    scene_command: SceneCommand
    archetype: Archetype
    prompt: str
    scene_action: dict[str, Any]
    splatra_contract: dict[str, Any]
    safety_flags: dict[str, bool]
    external_splatra_called: bool = False
    raw_buffer_in_agent_context: bool = False
    proof_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def _normalize_command(command: str) -> str:
    return re.sub(r"\s+", " ", command.strip())[:480]


def _select_command_archetype(command: str) -> Archetype:
    lower = command.lower()
    for archetype, hints in ARCHETYPE_HINTS.items():
        if any(hint.lower() in lower for hint in hints):
            return archetype
    selected = select_archetype(f"splatra_command:{command}", curiosity=0.72)
    return "constellation" if selected == "orb" else selected


def _scene_command_for(command: str) -> SceneCommand:
    lower = command.lower()
    if any(token in lower for token in ("graph", "knowledge", "관계", "그래프", "지식")):
        return "render_knowledge_hologram"
    if any(token in lower for token in ("morph", "change", "변형", "바꿔", "변해")):
        return "morph"
    return "spawn_object"


def compile_splatra_command(
    command: str,
    *,
    particle_budget: int = 1600,
    mode: str = "product",
) -> tuple[SplatraCommandPlan, ImaginationFrame]:
    """Compile an ATANOR visual command into a SPLATRA-style scene action.

    This adapter follows Cozystone/SPLATRA's contract: the agent receives a
    scene/action summary and a cartridge handle contract, never raw 3D buffers.
    It does not call an external LLM, sLLM, image model, Local Brain, production
    store, or candidate promotion path.
    """

    normalized = _normalize_command(command)
    if not normalized:
        normalized = "abstract particle object"
    archetype = _select_command_archetype(normalized)
    scene_command = _scene_command_for(normalized)
    plan_id = _stable_id("splatra_cmd", f"{scene_command}:{archetype}:{normalized}")
    object_id = _stable_id("obj", normalized)
    scene_action = {
        "op": scene_command,
        "args": {
            "id": object_id,
            "prompt": normalized,
            "archetype": archetype,
            "position": [0.0, 0.0, 0.0],
            "quality": "procedural_proof",
            "particle_budget": max(64, min(int(particle_budget), 100_000)),
        },
        "version": 1,
        "execute_js": False,
        "mutation_performed": False,
    }
    splatra_contract = {
        "compatible_source": "Cozystone/SPLATRA",
        "source_commit_observed": "3f5156e",
        "tool_schema": ["spawn_object", "morph", "render_knowledge_hologram", "focus_camera", "label"],
        "compatible_endpoints": ["POST /v1/chat", "POST /v1/generate_3d_object", "GET /v1/cartridge"],
        "side_channel": "viewer pulls cartridge; agent context gets summary only",
        "raw_buffers_in_agent_context": False,
        "spl2_or_spl3_cartridge_ready": False,
    }
    seed = ImaginationSeed(
        seed_id=plan_id,
        archetype=archetype,
        randomness=0.61,
        valence=0.12,
        arousal=0.62 if mode == "product" else 0.7,
        curiosity=0.78,
        particle_budget=max(64, min(int(particle_budget), 100_000)),
        state="imagining",
        created_at="splatra_command_adapter",
    )
    frame = ImaginationGenerator(max_particle_budget=100_000).generate_frame(seed)
    item = frame.objects[0]
    item.metadata["splatra_command_plan"] = {
        "plan_id": plan_id,
        "scene_command": scene_command,
        "prompt": normalized,
        "scene_action": scene_action,
        "splatra_contract": splatra_contract,
    }
    return (
        SplatraCommandPlan(
            plan_id=plan_id,
            command=normalized,
            scene_command=scene_command,
            archetype=archetype,
            prompt=normalized,
            scene_action=scene_action,
            splatra_contract=splatra_contract,
            safety_flags=default_safety_flags(),
        ),
        frame,
    )
