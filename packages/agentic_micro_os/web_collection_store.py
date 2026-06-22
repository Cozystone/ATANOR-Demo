from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class WebSourceRecord:
    source_url: str
    title: str
    content_hash: str
    excerpt: str
    collected_at: str
    confidence: float
    candidate_status: str = "draft"

    @classmethod
    def from_visible_text(cls, source_url: str, title: str, visible_text: str, confidence: float = 0.62) -> "WebSourceRecord":
        normalized = " ".join(visible_text.split())
        excerpt = normalized[:500] if normalized else "empty public snapshot"
        digest = hashlib.sha256(f"{source_url}\n{title}\n{excerpt}".encode("utf-8")).hexdigest()
        return cls(
            source_url=source_url,
            title=title or source_url,
            content_hash=digest,
            excerpt=excerpt,
            collected_at=utc_now_iso(),
            confidence=max(0.0, min(confidence, 1.0)),
        )


@dataclass(frozen=True)
class CloudBrainCandidateDraft:
    draft_id: str
    source_url: str
    title: str
    content_hash: str
    excerpt: str
    confidence: float
    candidate_status: str = "draft"
    production_mutation: bool = False
    approval_required: bool = True


@dataclass(frozen=True)
class ToolUseTrajectory:
    trajectory_id: str
    goal: str
    observations: list[str]
    actions: list[str]
    outcomes: list[str]
    compressed_summary: str
    no_private_raw_data: bool = True


@dataclass
class WebCollectionStore:
    sources: list[WebSourceRecord] = field(default_factory=list)
    candidate_drafts: list[CloudBrainCandidateDraft] = field(default_factory=list)
    trajectories: list[ToolUseTrajectory] = field(default_factory=list)

    def add_source(self, source: WebSourceRecord) -> WebSourceRecord:
        if not any(existing.content_hash == source.content_hash for existing in self.sources):
            self.sources.append(source)
        return source

    def create_candidate_draft(self, source: WebSourceRecord) -> CloudBrainCandidateDraft:
        draft = CloudBrainCandidateDraft(
            draft_id=f"cloud_candidate_{len(self.candidate_drafts)}",
            source_url=source.source_url,
            title=source.title,
            content_hash=source.content_hash,
            excerpt=source.excerpt,
            confidence=source.confidence,
        )
        self.candidate_drafts.append(draft)
        return draft

    def add_trajectory(self, trajectory: ToolUseTrajectory) -> ToolUseTrajectory:
        self.trajectories.append(trajectory)
        return trajectory

    def to_dict(self) -> dict[str, object]:
        return {
            "sources": [asdict(source) for source in self.sources],
            "candidate_drafts": [asdict(draft) for draft in self.candidate_drafts],
            "trajectories": [asdict(trajectory) for trajectory in self.trajectories],
        }
