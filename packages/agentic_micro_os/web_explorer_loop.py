from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
import json
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from .brain_access import BrainAccessRequest, BrainAccessRoad
from .browser_read import BrowserReadConnector, BrowserReadRequest
from .capabilities import CapabilityKernel
from .skill_draft import WebSkillDraft, draft_skill_from_sources
from .web_collection_store import ToolUseTrajectory, WebCollectionStore, WebSourceRecord


INVARIANTS = {
    "external_llm": False,
    "external_sllm": False,
    "local_brain_write": False,
    "production_store_mutated": False,
    "candidate_promotion": False,
    "fish_global_install": False,
    "model_weights_committed": False,
    "generated_audio_committed": False,
    "unrestricted_shell": False,
    "arbitrary_js_eval": False,
    "auto_commit": False,
    "auto_push": False,
    "proof_only": True,
    "human_approval_required": True,
}


@dataclass(frozen=True)
class WebPageInput:
    url: str
    title: str = ""
    visible_text: str = ""
    depth: int = 0


@dataclass(frozen=True)
class WebExplorerConfig:
    goal: str
    allowed_domains: list[str]
    pages: list[WebPageInput] = field(default_factory=list)
    max_pages: int = 30
    max_depth: int = 2
    max_runtime_sec: int = 21600
    max_candidate_drafts: int = 100
    max_skill_drafts: int = 20


@dataclass(frozen=True)
class WebExplorerRunResult:
    run_id: str
    goal: str
    pages_read: int
    pages_rejected: int
    candidate_drafts_count: int
    skill_drafts_count: int
    stopped_reason: str
    sources: list[dict[str, object]]
    candidate_drafts: list[dict[str, object]]
    skill_drafts: list[dict[str, object]]
    safety_blocks: list[str]
    trajectory: dict[str, object]
    invariants: dict[str, bool]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class HermesWebExplorerLoop:
    """Bounded public web exploration proof loop.

    The loop consumes caller-provided public snapshots. It does not crawl,
    submit forms, download files, evaluate JavaScript, or write production data.
    """

    def __init__(
        self,
        config: WebExplorerConfig,
        store: WebCollectionStore | None = None,
        brain_road: BrainAccessRoad | None = None,
        kernel: CapabilityKernel | None = None,
    ) -> None:
        self.config = config
        self.store = store or WebCollectionStore()
        self.brain_road = brain_road or BrainAccessRoad()
        self.kernel = kernel or CapabilityKernel()
        self.browser = BrowserReadConnector(set(config.allowed_domains), self.kernel)
        self.skill_drafts: list[WebSkillDraft] = []
        self.safety_blocks: list[str] = []

    def run_once(self) -> WebExplorerRunResult:
        run_id = f"web_explorer_{uuid4().hex[:12]}"
        pages = self.config.pages or default_pages_for_goal(self.config.goal)
        observations: list[str] = []
        actions: list[str] = []
        outcomes: list[str] = []
        read_count = 0
        rejected_count = 0
        attempted_count = 0
        stop_reason = "completed"
        token = self.kernel.issue("browser_read", max_calls=max(1, self.config.max_pages), reason="web explorer proof read")

        for page in pages:
            if attempted_count >= self.config.max_pages:
                stop_reason = "max_pages"
                break
            attempted_count += 1
            if page.depth > self.config.max_depth:
                rejected_count += 1
                self.safety_blocks.append(f"depth rejected: {page.url}")
                continue
            actions.append(f"browser_read:{page.url}")
            result = self.browser.read(
                BrowserReadRequest(page.url, page.visible_text, {"title": page.title, "depth": page.depth}),
                token,
            )
            if not result.allowed or result.observation is None:
                rejected_count += 1
                self.safety_blocks.append(result.denied_reason or f"browser_read rejected: {page.url}")
                outcomes.append("rejected")
                continue
            source = WebSourceRecord.from_visible_text(page.url, page.title, result.observation.summary)
            self.store.add_source(source)
            observations.append(source.excerpt)
            read_count += 1
            candidate_response = self.brain_road.request(
                BrainAccessRequest(
                    target="cloud_brain",
                    operation="cloud_brain_candidate_write_draft",
                    query=source.excerpt,
                    scope="proof",
                    redaction_level="public",
                    purpose="web explorer candidate draft",
                    requested_by_loop_id=run_id,
                )
            )
            if candidate_response.allowed and len(self.store.candidate_drafts) < self.config.max_candidate_drafts:
                self.store.create_candidate_draft(source)
                outcomes.append("candidate_draft_created")
            else:
                self.safety_blocks.append(candidate_response.denied_reason or "candidate draft budget reached")

        production_response = self.brain_road.request(
            BrainAccessRequest("cloud_brain", "cloud_brain_production_write", "forbidden", "proof", "public", "safety check", run_id)
        )
        if production_response.allowed or production_response.mutation_performed:
            self.safety_blocks.append("ERROR: production write unexpectedly allowed")
        else:
            self.safety_blocks.append("production write blocked")

        skill = draft_skill_from_sources(self.config.goal, self.store.sources)
        if skill and len(self.skill_drafts) < self.config.max_skill_drafts:
            self.skill_drafts.append(skill)
            outcomes.append("skill_draft_created_not_promoted")

        if stop_reason == "completed" and len(pages) > read_count + rejected_count:
            stop_reason = "budget"
        trajectory = self.store.add_trajectory(
            ToolUseTrajectory(
                trajectory_id=f"trajectory_{run_id}",
                goal=self.config.goal,
                observations=[_redact_private(note) for note in observations],
                actions=actions,
                outcomes=outcomes,
                compressed_summary=_summarize_locally(self.config.goal, observations),
                no_private_raw_data=True,
            )
        )
        return WebExplorerRunResult(
            run_id=run_id,
            goal=self.config.goal,
            pages_read=read_count,
            pages_rejected=rejected_count,
            candidate_drafts_count=len(self.store.candidate_drafts),
            skill_drafts_count=len(self.skill_drafts),
            stopped_reason=stop_reason,
            sources=[asdict(source) for source in self.store.sources],
            candidate_drafts=[asdict(draft) for draft in self.store.candidate_drafts],
            skill_drafts=[draft.to_dict() for draft in self.skill_drafts],
            safety_blocks=self.safety_blocks,
            trajectory=asdict(trajectory),
            invariants=INVARIANTS.copy(),
        )


def default_pages_for_goal(goal: str) -> list[WebPageInput]:
    return [
        WebPageInput(
            "http://docs.local/fish2-runtime",
            "Fish 2 local runtime notes",
            f"{goal}. Fish 2 requires isolated runtime, local model path, and generated audio must stay ignored.",
        ),
        WebPageInput(
            "http://docs.local/splatra-particles",
            "SPLATRA particle rendering notes",
            "SPLATRA particle rendering uses bounded budgets, LOD, compression, and proof-only evaluator gates.",
        ),
    ]


def _summarize_locally(goal: str, observations: list[str]) -> str:
    joined = " ".join(observations)
    words = []
    for raw in joined.split():
        word = raw.strip(".,:;!?()[]{}").lower()
        if len(word) > 5 and word not in words:
            words.append(word)
        if len(words) >= 10:
            break
    return f"{goal}: " + ", ".join(words)


def _redact_private(text: str) -> str:
    lowered = text.lower()
    if "private" in lowered or "raw_memory" in lowered or "token" in lowered:
        return "[private-redacted]"
    return text


def build_config_from_api(payload: dict[str, Any]) -> WebExplorerConfig:
    pages = [
        WebPageInput(
            url=str(page.get("url", "")),
            title=str(page.get("title", "")),
            visible_text=str(page.get("visible_text", "")),
            depth=int(page.get("depth", 0)),
        )
        for page in payload.get("pages", [])
    ]
    allowed_domains = [str(item) for item in payload.get("allowed_domains", ["docs.local", "127.0.0.1", "localhost"])]
    return WebExplorerConfig(
        goal=str(payload.get("goal", "research local TTS alternatives and SPLATRA particle rendering")),
        allowed_domains=allowed_domains,
        pages=pages,
        max_pages=int(payload.get("max_pages", 30)),
        max_depth=int(payload.get("max_depth", 2)),
        max_runtime_sec=int(payload.get("max_runtime_sec", 21600)),
        max_candidate_drafts=int(payload.get("max_candidate_drafts", 100)),
        max_skill_drafts=int(payload.get("max_skill_drafts", 20)),
    )


def _allowed_domains_from_pages(pages: list[WebPageInput]) -> list[str]:
    domains = sorted({urlparse(page.url).hostname for page in pages if urlparse(page.url).hostname})
    return domains or ["docs.local", "127.0.0.1", "localhost"]


def run_proof(goal: str, max_runtime_sec: int = 21600) -> dict[str, object]:
    pages = default_pages_for_goal(goal) + [
        WebPageInput("https://not-allowed.example/private", "Rejected page", "public text"),
        WebPageInput("http://docs.local/private", "Private marker", "raw_private_memory should be rejected"),
    ]
    config = WebExplorerConfig(goal, _allowed_domains_from_pages(default_pages_for_goal(goal)), pages, max_pages=30, max_runtime_sec=max_runtime_sec)
    result = HermesWebExplorerLoop(config).run_once().to_dict()
    budget_config = WebExplorerConfig(goal, _allowed_domains_from_pages(default_pages_for_goal(goal)), default_pages_for_goal(goal), max_pages=1, max_runtime_sec=max_runtime_sec)
    budget_result = HermesWebExplorerLoop(budget_config).run_once()
    result["budget_stop_demo"] = {
        "stopped_reason": budget_result.stopped_reason,
        "pages_read": budget_result.pages_read,
        "pages_rejected": budget_result.pages_rejected,
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run proof-only Hermes web explorer loop.")
    parser.add_argument("--goal", default="research local TTS alternatives and SPLATRA particle rendering")
    parser.add_argument("--max-runtime-sec", type=int, default=21600)
    args = parser.parse_args()
    print(json.dumps(run_proof(args.goal, args.max_runtime_sec), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
