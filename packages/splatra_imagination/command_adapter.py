from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from typing import Any, Literal

from .generator import ImaginationGenerator, select_archetype
from .models import Archetype, ImaginationFrame, ImaginationSeed, default_safety_flags


SceneCommand = Literal["spawn_object", "morph", "render_knowledge_hologram"]


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


def _select_command_archetype(command: str, explicit_archetype: Archetype | None = None) -> Archetype:
    if explicit_archetype:
        return explicit_archetype
    selected = select_archetype(f"splatra_command:{command}", curiosity=0.72)
    return "constellation" if selected == "orb" else selected


def compile_splatra_command(
    command: str,
    *,
    particle_budget: int = 1600,
    mode: str = "product",
    scene_command: SceneCommand = "spawn_object",
    archetype: Archetype | None = None,
) -> tuple[SplatraCommandPlan, ImaginationFrame]:
    """Compile an ATANOR visual command into a bounded SPLATRA scene action.

    This function intentionally does not infer topic-specific content such as
    "gravity means apple tree". Upstream ATANOR scene planning must author
    those beats. This adapter only validates and packages a command/action
    contract, keeping raw 3D buffers out of the agent context.
    """

    normalized = _normalize_command(command) or "abstract particle object"
    selected_archetype = _select_command_archetype(normalized, archetype)
    plan_id = _stable_id("splatra_cmd", f"{scene_command}:{selected_archetype}:{normalized}")
    object_id = _stable_id("obj", normalized)
    scene_action = {
        "op": scene_command,
        "args": {
            "id": object_id,
            "prompt": normalized,
            "archetype": selected_archetype,
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
        "topic_scene_templates": False,
    }
    seed = ImaginationSeed(
        seed_id=plan_id,
        archetype=selected_archetype,
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
            archetype=selected_archetype,
            prompt=normalized,
            scene_action=scene_action,
            splatra_contract=splatra_contract,
            safety_flags=default_safety_flags(),
        ),
        frame,
    )
