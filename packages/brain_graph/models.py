from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal


BRAIN_GRAPH_ROOT = Path("data/brain_graph")
PROOF_ROOT = BRAIN_GRAPH_ROOT / "proofs"
PROOF_JSON_PATH = PROOF_ROOT / "tab_aware_brain_graph_proof.json"
PROOF_MD_PATH = PROOF_ROOT / "tab_aware_brain_graph_proof.md"

BrainGraphView = Literal["local", "cloud"]

LOCAL_LAYERS = [
    "local_user",
    "working_memory_local",
    "local_base",
    "seed",
    "local_memory_candidate",
]

CLOUD_LAYERS = [
    "semantic_cloud",
    "cloud_attached",
    "graph_cartridge",
    "contributor",
    "working_memory_cloud",
    "surface_trace_summary",
]

DEFAULT_LOCAL_LAYERS = ["local_user", "working_memory_local", "local_base"]
DEFAULT_CLOUD_LAYERS = ["cloud_attached", "graph_cartridge", "working_memory_cloud", "semantic_cloud", "surface_trace_summary"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_brain_graph_dirs() -> None:
    for path in [BRAIN_GRAPH_ROOT, PROOF_ROOT, BRAIN_GRAPH_ROOT / "renders", BRAIN_GRAPH_ROOT / "status"]:
        path.mkdir(parents=True, exist_ok=True)


@dataclass(slots=True)
class RenderableBrainNode:
    id: str
    label: str
    layer: str
    source_scope: str
    persistent: bool
    temporary: bool
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    kind: str = "concept"
    trust_state: str = "unknown"
    verification_state: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RenderableBrainEdge:
    id: str
    source: str
    target: str
    relation: str
    layer: str
    source_scope: str
    persistent: bool
    temporary: bool
    weight: float = 1.0
    trust_state: str = "unknown"
    verification_state: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class LayerResult:
    layer: str
    available: bool
    nodes: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)
    side_panel: dict[str, Any] = field(default_factory=dict)
    stats: dict[str, Any] = field(default_factory=dict)
    missing_reason: str | None = None
    partial: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
