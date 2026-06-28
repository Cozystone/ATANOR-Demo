from __future__ import annotations

import re
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.services.alpha_services import alpha_service
from packages.base_brain.scene_grounding import extract_scene_grounding
from packages.base_brain.zero_user_answer import answer_with_base_brain
from packages.base_brain.atanor_self_knowledge import answer_self_question
from packages.base_brain.pack_loader import get_semantic_context, load_base_brain_pack
from packages.holographic_fold import (
    build_field_inputs,
    build_pair_representation,
    build_state_field,
    compare_fold_to_answer,
    fold_state,
    folded_core,
)
from packages.cgsr.cgsr.conversation_surface import generate_conversation_surface
from packages.cgsr.cgsr.conversation_context import ConversationContextPacket, build_conversation_context
from packages.cgsr.cgsr.conversation_grounding import (
    GroundedContext,
    gather_grounded_context,
    grounded_discourse_metadata,
    realize_grounded_context,
    semantic_safety_flags,
)
from packages.cgsr.cgsr.conversation_router import ConversationRoute, route_conversation_request
from packages.cgsr.cgsr.visual_imagination_planner import plan_visual_imagination
from packages.core_proof.three_core_answer_path import run_prompt_proof
from packages.splatra_imagination import (
    analyze_scene_choreography,
    build_candidate_cartridge_queue,
    compile_scene_choreography_commands,
    dispatch_candidate_queue_to_sidecar,
)
from packages.voice_loop.local_tts import LocalTTSUnavailable, synthesize_windows_sapi, voice_audio_path
from packages.voice_loop.runtime_availability import check_voice_runtime_availability
from packages.surface_brain.monitor import monitor_answer, repair_answer_for_mode
from packages.surface_brain.dual_projection import ingest_source_sentence_dual_projection
from packages.surface_brain.models import SourceSentence, honesty_flags
from packages.surface_brain.realization_planner import plan_speech, realize_answer
from packages.cloud_brain.candidate_read_model import candidate_cloud_status
from packages.cloud_brain.graph_exchange import run_local_cloud_exchange
from packages.cloud_brain.semantic_store import SemanticCloudStore
from packages.neural_emotion.event_bus import emit_runtime_event, infer_user_text_runtime_event
from packages.neural_emotion.event_bus import EVENT_BUS
from packages.neural_emotion.voice_bridge import attach_voice_plan_metadata, voice_controls
from packages.inner_voice import emit_inner_voice_from_state


router = APIRouter(tags=["dual-brain"])
PROJECT_ROOT = Path(__file__).resolve().parents[4]


# ----- Local Brain cumulative memory (private on-device) ----------------------
from packages.local_brain import LocalBrainMemory, extract_user_facts

LOCAL_BRAIN = LocalBrainMemory(PROJECT_ROOT / "runtime" / "local_brain" / "local_memory.json")
# Facts ATANOR has looked up on the web are retained locally, so re-asking is
# instant and still works offline (the agent remembers what it learned).
WEB_FACT_MEMORY = LocalBrainMemory(PROJECT_ROOT / "runtime" / "local_brain" / "web_fact_memory.json", max_facts=1000)

# Questions that ask the agent to recall something about the USER (not ATANOR).
_SELF_RECALL_KO = ("내 이름", "제 이름", "내가 누구", "내가 뭘 좋아", "내가 좋아하는", "나 뭐 좋아", "내 직업", "내가 어디", "나에 대해", "내 정보")
_SELF_RECALL_EN = ("my name", "what do i like", "what's my favorite", "what is my favorite", "where do i live", "my job", "about me", "what do you know about me")


def _is_self_recall_question(question: str) -> bool:
    raw = str(question or "")
    lowered = raw.lower()
    return any(m in raw for m in _SELF_RECALL_KO) or any(m in lowered for m in _SELF_RECALL_EN)


def _accumulate_user_facts(question: str, language: str) -> int:
    """Accumulate user preferences/info from this turn into the Local Brain.

    The extractor already skips interrogative turns, so a question like
    "내 이름이 뭐야?" never pollutes memory while a statement like
    "내 이름은 블루야" still accumulates.
    """
    try:
        facts = extract_user_facts(question, language)
        for kind, subject, value, confidence in facts:
            LOCAL_BRAIN.remember(kind, subject, value, source="conversation", source_ref="conversation_turn", confidence=confidence, save=False)
        if facts:
            LOCAL_BRAIN.save()
        return len(facts)
    except Exception:  # pragma: no cover - never break the chat
        return 0


def _local_brain_recall(question: str, language: str) -> dict[str, Any] | None:
    """If the user asks ATANOR to recall something about THEM and the Local Brain
    knows it, answer from private memory with a certificate. Else None."""
    try:
        raw = str(question or "")
        lowered = raw.lower()
        # Only treat it as a recall when there is a question/recall cue, so a
        # statement ("내 이름은 블루야") is not answered as if it were a question.
        has_cue = (
            "?" in raw
            or any(c in raw for c in ("뭐", "뭘", "뭣", "뭔", "누구", "말해", "알려", "기억", "어디", "였"))
            or any(c in lowered for c in ("what", "who", "where", "tell me", "remember", "do you know"))
        )
        if not has_cue:
            return None
        # Map the question to a known self-subject, then fetch that fact directly
        # (token overlap fails across languages: "내 이름" vs subject "name").
        subject: str | None = None
        if any(m in raw for m in ("내 이름", "제 이름", "내가 누구")) or "my name" in lowered or "who am i" in lowered:
            subject = "name"
        elif "싫어" in raw or any(w in lowered for w in ("dislike", "hate")):
            subject = "dislikes"
        elif "좋아" in raw or "선호" in raw or any(w in lowered for w in ("like", "favorite", "favourite", "prefer", "enjoy")):
            subject = "likes"
        elif "직업" in raw or any(w in lowered for w in ("job", "work")):
            subject = "job"
        elif "어디" in raw or "live" in lowered or "location" in lowered:
            subject = "location"
        if not subject:
            return None
        hits = [f for f in LOCAL_BRAIN.all_facts() if f.subject == subject]
        if not hits:
            return None
        is_ko = language == "ko"
        top = hits[0]

        def _eul(word: str) -> str:
            # pick the object particle by whether the last Hangul char has a 받침
            if word and "가" <= word[-1] <= "힣":
                return "을" if (ord(word[-1]) - 0xAC00) % 28 else "를"
            return "을(를)"

        if top.subject == "name":
            answer = f"당신의 이름은 {top.value}입니다." if is_ko else f"Your name is {top.value}."
        elif top.subject == "likes":
            answer = f"당신은 {top.value}{_eul(top.value)} 좋아한다고 하셨어요." if is_ko else f"You told me you like {top.value}."
        elif top.subject == "dislikes":
            answer = f"당신은 {top.value}{_eul(top.value)} 싫어한다고 하셨어요." if is_ko else f"You told me you dislike {top.value}."
        else:
            answer = f"제가 기억하기로는, {top.subject}: {top.value}." if is_ko else f"From what I remember — {top.subject}: {top.value}."
        steps = [{"type": "local_memory_fact", "fact": f"{f.subject}: {f.value}", "source": f.source} for f in hits]
        certificate = {
            "derivation_kind": "local_brain_memory_recall",
            "anchor_concept": {"id": top.subject, "label": top.subject, "match": "local_memory"},
            "steps": steps,
            "evidence_concepts": [f"local_memory:{f.subject}" for f in hits],
            "confidence": round(float(top.confidence), 4),
            "confidence_basis": "private_on_device_memory",
            "guarantees": {"external_llm": False, "fabricated_facts": False, "private_on_device": True, "uploaded_to_cloud": False},
        }
        return {"answer": answer, "reasoning_certificate": certificate, "confidence": float(top.confidence)}
    except Exception:  # pragma: no cover
        return None


def _verified_store_runtime() -> dict[str, Any]:
    configured = os.environ.get("ATANOR_VERIFIED_STORE_PATH")
    if configured:
        candidate = Path(configured)
        if candidate.exists() and candidate.is_dir():
            return {"verified_store_path": str(candidate)}
    for candidate in _verified_store_candidates():
        if candidate.exists() and candidate.is_dir():
            return {"verified_store_path": str(candidate)}
    return {}


def _verified_store_candidates() -> list[Path]:
    """Find read-only verified_store_v0 roots without creating or mutating data."""

    candidates: list[Path] = [
        PROJECT_ROOT / "data" / "cloud_brain" / "verified_store_v0",
        PROJECT_ROOT.parent / "24.Homage1.0" / "data" / "cloud_brain" / "verified_store_v0",
    ]
    workspace_parent = PROJECT_ROOT.parent
    if workspace_parent.exists() and workspace_parent.is_dir():
        for child in sorted(workspace_parent.iterdir(), key=lambda item: item.name.casefold()):
            if not child.is_dir() or child == PROJECT_ROOT:
                continue
            candidates.append(child / "data" / "cloud_brain" / "verified_store_v0")

    deduped: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate.resolve() if candidate.exists() else candidate)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def _candidate_runs_roots() -> list[Path]:
    """Find read-only Cloud Brain candidate-run roots across sibling worktrees.

    Mirrors `_verified_store_candidates` but points at `candidate_runs` (the
    review-gated queue). Read-only: never creates, mutates, or promotes.
    """

    roots: list[Path] = []
    seen: set[str] = set()
    for verified in _verified_store_candidates():
        runs = verified.parent / "candidate_runs"
        key = str(runs.resolve() if runs.exists() else runs)
        if key in seen:
            continue
        seen.add(key)
        roots.append(runs)
    return roots


def _review_queue_status() -> dict[str, Any] | None:
    """Read the live review-gated candidate queue without promotion.

    Returns the bounded candidate status (counts + honesty flags) for the most
    recent candidate run, or None if no candidate store can be resolved. This is
    a pure read: no production mutation, no Local Brain write, no promotion.
    """

    configured = os.environ.get("ATANOR_CANDIDATE_STORE_PATH")
    if configured:
        candidate = Path(configured)
        if candidate.exists() and candidate.is_dir():
            return candidate_cloud_status(candidate)
    for runs_dir in _candidate_runs_roots():
        if not runs_dir.exists() or not runs_dir.is_dir():
            continue
        stores = [
            item
            for item in runs_dir.iterdir()
            if item.is_dir() and (item / "manifest.json").exists()
        ]
        if stores:
            latest = max(stores, key=lambda item: item.stat().st_mtime)
            return candidate_cloud_status(latest)
    return None


def _splatra_dispatch_budget(
    queue: Any,
    *,
    visual_plan: Any,
    direct_splatra_generation: bool,
) -> dict[str, float | int]:
    """Keep quick fallback checks fast, but wait for real SPLATRA generation.

    SPLATRA's learned generators can take tens of seconds, especially when a
    verified scene asks for multiple particle objects. The answer path still
    receives only SGF summaries and side-channel URLs; raw buffers stay viewer-side.
    """

    if direct_splatra_generation:
        return {"poll_ticks": 30, "timeout_sec": 180.0}

    job_count = int(getattr(queue, "job_count", 0) or 0)
    scene = getattr(visual_plan, "scene_choreography", None)
    diagnostics = getattr(visual_plan, "diagnostics", {}) if visual_plan is not None else {}
    scene_source = str(diagnostics.get("scene_content_source") or "")
    layout_intent = ""
    if isinstance(scene, dict):
        layout_intent = str(scene.get("layout_intent") or "")

    verified_or_wide_scene = scene_source == "verified_store_facts" or layout_intent == "wide_particle_stage"
    if job_count >= 2 and verified_or_wide_scene:
        return {"poll_ticks": 2, "timeout_sec": 180.0}

    return {"poll_ticks": 2, "timeout_sec": 8.0}


class DualBrainIngestRequest(BaseModel):
    text: str = Field(min_length=1, max_length=12000)
    source_id: str | None = None
    url: str | None = None
    title: str | None = None
    license: str = "unknown"
    usage_allowed: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class AtanorChatRequest(BaseModel):
    question: str | None = Field(default=None, min_length=1, max_length=1000)
    query: str | None = Field(default=None, min_length=1, max_length=1000)
    message: str | None = Field(default=None, min_length=1, max_length=1000)
    language: str | None = None
    audience_level: str = "beginner"
    tone: str = "clear"
    mode: str = "default"
    web_search: bool = False
    brain_mode: str = "unified"
    include_trace: bool = False
    layout_feedback: dict[str, Any] = Field(default_factory=dict)
    conversation_context: list[dict[str, Any]] = Field(default_factory=list)

    def question_text(self) -> str:
        text = self.question or self.query or self.message or ""
        return re.sub(r"\s+", " ", text).strip()


def _flags() -> dict[str, Any]:
    return {
        **honesty_flags(),
        "final_answer_generation_claimed": True,
        "trace_hidden_by_default": True,
        "production_store_mutated": False,
        "candidate_promotion": False,
        "internal_trace_exposed": False,
    }


def _run_three_core_compact_trace(question: str) -> dict[str, Any]:
    """Run the symbolic three-core path as hidden trace, not as answer text."""
    try:
        record = run_prompt_proof(question)
    except Exception as exc:  # pragma: no cover - defensive trace isolation
        return {
            "used": False,
            "error": type(exc).__name__,
            "local_brain_write": False,
            "external_llm_used": False,
            "external_sllm_used": False,
            "trace_hidden_by_default": True,
        }
    sqc_atoms = record.get("sqc", {}).get("encoded_concepts") or []
    wave = record.get("wave_graph") or {}
    surface = record.get("surface") or {}
    return {
        "used": True,
        "sqc": {
            "used": bool(record.get("sqc", {}).get("used")),
            "atom_count": len(sqc_atoms),
            "memory_bytes": int(record.get("sqc", {}).get("memory_bytes") or 0),
            "compression_form": record.get("sqc", {}).get("compression_form"),
        },
        "fractal_seed_rail": {
            "used": bool(record.get("seed_rail", {}).get("used")),
            "activated_primitives": list(record.get("seed_rail", {}).get("activated_seed_primitives") or []),
            "rail_count": len(record.get("seed_rail", {}).get("reasoning_scaffold") or []),
        },
        "holographic_wave": {
            "used": bool(wave.get("used")),
            "candidate_paths": len(wave.get("candidate_paths") or []),
            "selected_path_id": (wave.get("selection_result") or {}).get("selected_path_id"),
            "selected_primitive": (wave.get("selection_result") or {}).get("selected_primitive"),
            "constructive_total": (wave.get("constructive_or_destructive_signal") or {}).get("constructive_total"),
            "destructive_total": (wave.get("constructive_or_destructive_signal") or {}).get("destructive_total"),
        },
        "surface_brain": {
            "used": bool(surface.get("used")),
            "candidate_count": len(surface.get("construction_candidates") or []),
            "selected_construction": list(surface.get("selected_construction") or []),
            "template_like": bool(surface.get("template_like")),
            "q_cortex_used": bool(surface.get("q_cortex_used")),
            "q_cortex_run_id": surface.get("q_cortex_run_id"),
        },
        "honesty": {
            "external_llm_used": bool(record.get("external_llm_used")),
            "external_sllm_used": bool(record.get("sllm_used")),
            "local_brain_write": bool(record.get("local_write")),
            "trace_hidden_by_default": True,
            "final_answer_source": "default_surface_or_base_brain_answer; three_core_is_hidden_trace",
        },
    }


def _attach_three_core_trace(
    response: dict[str, Any],
    *,
    request: AtanorChatRequest,
    three_core_trace: dict[str, Any],
) -> dict[str, Any]:
    result = response.get("result")
    if not isinstance(result, dict):
        return response
    compact_trace = result.setdefault("compact_trace", {})
    if isinstance(compact_trace, dict):
        compact_trace["three_core"] = three_core_trace
    else:
        result["compact_trace"] = {"three_core": three_core_trace}
    if request.include_trace or request.mode in {"trace", "research"}:
        trace = result.get("trace")
        if not isinstance(trace, dict):
            trace = {}
        trace["three_core"] = three_core_trace
        result["trace"] = trace
    else:
        result["trace"] = None
    if request.mode == "research":
        research_trace = result.get("research_trace")
        if not isinstance(research_trace, dict):
            research_trace = {}
        research_trace["three_core"] = three_core_trace
        result["research_trace"] = research_trace
    answer_engine = result.setdefault("answer_engine", {})
    if isinstance(answer_engine, dict):
        answer_engine["three_core_trace_attached"] = bool(three_core_trace.get("used"))
        answer_engine["three_core_answer_source"] = "hidden_trace_only"
    result["default_trace_visible"] = False
    result["trace_hidden_by_default"] = True
    return response


def _compact_conversation_text(question: str) -> str:
    return re.sub(r"[\s!.?,:;~\-_'\"()\[\]{}]+", "", question.strip().lower())


def _is_live_selfhood_conversation(question: str) -> bool:
    compact = _compact_conversation_text(question)
    if not compact:
        return True
    if compact in {"안녕", "안녕하세요", "하이", "반가워", "ㅎㅇ", "고마워", "감사", "감사합니다"}:
        return True
    if any(
        term in question
        for term in (
            "자기 모델",
            "자아 모델",
            "자의식",
            "내적 언어",
            "생각 중추",
            "유리 구",
            "구슬",
            "음성 모드",
        )
    ) and len(question.strip()) <= 80:
        return True
    if compact in {"안녕", "안녕하세요", "하이", "헬로", "반가워", "고마워", "감사", "감사합니다"}:
        return True
    lowered = question.strip().lower()
    if any(
        term in lowered
        for term in (
            "자기 모델",
            "자아 모델",
            "자의식",
            "내적 언어",
            "생각 중추",
            "유리 구",
            "구슬",
            "음성 모드",
        )
    ) and len(question.strip()) <= 80:
        return True
    if compact in {
        "안녕",
        "안녕하세요",
        "하이",
        "헬로",
        "반가워",
        "고마워",
        "감사",
        "감사합니다",
        "hi",
        "hello",
        "hey",
        "yo",
        "thanks",
        "thankyou",
    }:
        return True
    lowered = question.strip().lower()
    return any(
        term in lowered
        for term in (
            "자기 모델",
            "자아 모델",
            "자의식",
            "내적 언어",
            "생각 중추",
            "유리 구",
            "구슬",
            "orb",
            "self model",
            "selfhood",
            "inner speech",
            "voice mode",
        )
    ) and len(question.strip()) <= 80


def _live_selfhood_speech_act(question: str, language: str) -> str:
    compact = _compact_conversation_text(question)
    if language == "ko":
        if compact in {"안녕", "안녕하세요", "하이", "반가워", "ㅎㅇ"}:
            return "greeting"
        if compact in {"고마워", "감사", "감사합니다"}:
            return "thanks"
        if any(term in question for term in ("자기 모델", "자아 모델", "자의식", "내적 언어", "생각 중추")):
            return "self_model"
        if any(term in question for term in ("유리 구", "구슬")):
            return "orb"
        if compact in {"안녕", "안녕하세요", "하이", "헬로", "반가워"}:
            return "greeting"
        if compact in {"고마워", "감사", "감사합니다"}:
            return "thanks"
        if any(term in question for term in ("자기 모델", "자아 모델", "자의식", "내적 언어", "생각 중추")):
            return "self_model"
        if any(term in question for term in ("유리 구", "구슬")):
            return "orb"
        if compact in {"안녕", "안녕하세요", "하이", "헬로", "반가워"}:
            return "greeting"
        if compact in {"고마워", "감사", "감사합니다"}:
            return "thanks"
        if any(term in question for term in ("자기 모델", "자아 모델", "자의식", "내적 언어", "생각 중추")):
            return "self_model"
        if any(term in question for term in ("유리 구", "구슬")):
            return "orb"
        return "conversation"
    if compact in {"hi", "hello", "hey", "yo"}:
        return "greeting"
    if compact in {"thanks", "thankyou"}:
        return "thanks"
    if any(term in question.lower() for term in ("self model", "selfhood", "inner speech")):
        return "self_model"
    return "conversation"


def _voice_runtime_snapshot(text: str, language: str) -> dict[str, Any]:
    """Describe optional Fish TTS readiness without loading models or saving audio."""

    base = {
        "enabled": True,
        "requested": True,
        "selected_engine": "none",
        "tts_engine": "none",
        "runtime_available": False,
        "available": False,
        "fish_2_available": False,
        "fish_1_5_available": False,
        "audio_available": False,
        "audio_output_available": False,
        "audio_stream_available": False,
        "audio_url": None,
        "audio_mime": None,
        "audio_duration_ms": None,
        "error_reason": None,
        "reason": None,
        "install_hint": None,
        "text_fallback": True,
        "text_fallback_available": True,
        "visual_speaking_recommended": bool(text),
        "external_service": False,
        "generated_audio_persisted": False,
        "raw_voice_saved": False,
        "microphone_enabled": False,
        "always_listening_enabled": False,
        "voice_optional": True,
        "text_input_supported": True,
        "language": "ko-KR" if language == "ko" else "en-US",
        "status": "unavailable_missing_package",
        "user_message": (
            "음성 엔진이 아직 설치되어 있지 않습니다. 텍스트 응답은 계속 사용할 수 있습니다."
            if language == "ko"
            else "The voice engine is not installed yet. Text replies remain available."
        ),
    }
    base["user_message"] = (
        "음성 엔진은 아직 준비 중입니다. 텍스트 응답은 계속 사용할 수 있습니다."
        if language == "ko"
        else "The voice engine is not installed yet. Text replies remain available."
    )
    try:
        availability = check_voice_runtime_availability()
    except Exception as exc:  # pragma: no cover - optional runtime isolation
        return {**base, "status": "synthesis_failed", "error_reason": type(exc).__name__, "reason": str(exc)}
    fish2 = availability.get("fish_2")
    fish15 = availability.get("fish_1_5")
    selected = fish2 if fish2 and fish2.available else fish15 if fish15 and fish15.available else None
    if selected is None:
        reason = fish2.reason if fish2 else "fish_2_status_unavailable"
        error_reason = (
            "fish_runtime_missing"
            if fish2 and fish2.status == "unavailable_missing_package"
            else "fish_model_missing"
            if fish2 and fish2.status == "unavailable_missing_model"
            else fish2.status
            if fish2
            else "fish_runtime_missing"
        )
        return {
            **base,
            "fish_2_available": bool(fish2 and fish2.available),
            "fish_1_5_available": bool(fish15 and fish15.available),
            "status": fish2.status if fish2 else "unavailable_missing_package",
            "reason": reason,
            "error_reason": error_reason,
            "install_hint": fish2.install_hint if fish2 else "Install Fish runtime before enabling audio.",
            "unavailable_reason": reason,
        }

    # Runtime is configured, but this slice does not guess a Fish synthesis API.
    # Keep text/visual fallback unless a future adapter returns a real audio URL.
    return {
        **base,
        "selected_engine": selected.runtime_id,
        "tts_engine": selected.runtime_id,
        "runtime_available": True,
        "available": True,
        "fish_2_available": bool(fish2 and fish2.available),
        "fish_1_5_available": bool(fish15 and fish15.available),
        "status": "available_not_loaded",
        "reason": "Fish runtime configured, but audio synthesis is not wired in this proof slice",
        "error_reason": "synthesis_adapter_not_wired",
        "install_hint": "Wire the installed Fish synthesis API to return an ignored temp audio URL.",
        "unavailable_reason": "synthesis_adapter_not_wired",
        "user_message": (
            "음성 합성 연결은 아직 준비 중입니다. 텍스트 응답으로 계속합니다."
            if language == "ko"
            else "Voice synthesis wiring is still pending. Continuing with text replies."
        ),
    }


def _estimate_voice_duration_ms(text: str, language: str) -> int:
    compact = re.sub(r"\s+", "", text or "")
    if not compact:
        return 900
    per_char = 118 if language == "ko" else 62
    punctuation_pause = len(re.findall(r"[.!?,;:\u3001\u3002!?]", text or "")) * 120
    return max(900, min(18000, len(compact) * per_char + punctuation_pause + 420))


def _attach_voice_runtime_metadata(snapshot: dict[str, Any], text: str, language: str) -> dict[str, Any]:
    duration_ms = snapshot.get("audio_duration_ms") or _estimate_voice_duration_ms(text, language)
    with_duration = {
        **snapshot,
        "audio_duration_ms": duration_ms,
        "estimated_duration_ms": duration_ms,
        "speech_sync_source": "audio_duration" if snapshot.get("audio_duration_ms") else "estimated_from_text_length",
    }
    if language == "ko" and with_duration.get("tts_engine") == "windows_sapi":
        with_duration["user_message"] = "Fish 직접 합성은 아직 연결 전이라 Windows 로컬 음성으로 발화합니다."
    elif language == "ko" and with_duration.get("error_reason") == "synthesis_adapter_not_wired":
        with_duration["user_message"] = "음성 합성 연결은 아직 준비 중입니다. 텍스트 응답으로 계속합니다."
    emotion_vector = EVENT_BUS.engine.snapshot().vector
    return attach_voice_plan_metadata(
        with_duration,
        emotion_vector,
        selected_engine=str(with_duration.get("selected_engine") or "fallback"),
        audio_available=bool(with_duration.get("audio_available")),
    )


def _sapi_prosody_from_voice_controls(controls: dict[str, Any]) -> dict[str, int]:
    speed = float(controls.get("speed") or 1.0)
    energy = float(controls.get("energy") or 0.45)
    # Windows SAPI is only a local fallback, so keep it slightly slower and
    # softer than the abstract Fish-style controls. This avoids the brittle,
    # announcer-like delivery users hear when neutral local voices run fast.
    rate = max(-4, min(0, round((speed - 1.0) * 8 - 2)))
    volume = max(58, min(88, round(66 + energy * 17)))
    return {"rate": int(rate), "volume": int(volume)}


def _voice_runtime_snapshot_with_local_audio(text: str, language: str) -> dict[str, Any]:
    """Add a local temp WAV fallback without claiming Fish synthesis is wired."""

    snapshot = _voice_runtime_snapshot(text, language)
    if snapshot.get("audio_available") and snapshot.get("audio_url"):
        return snapshot
    preliminary_controls = voice_controls(
        EVENT_BUS.engine.snapshot().vector,
        selected_engine=str(snapshot.get("selected_engine") or "fallback"),
        audio_available=False,
    )
    sapi_prosody = _sapi_prosody_from_voice_controls(preliminary_controls)
    try:
        fallback = synthesize_windows_sapi(
            text,
            language=language,
            sentence_gap_ms=int(preliminary_controls.get("fallback_sentence_gap_ms") or 220),
            **sapi_prosody,
        )
    except LocalTTSUnavailable as exc:
        return {**snapshot, "fallback_error": str(exc)}
    return {
        **snapshot,
        "selected_engine": snapshot.get("selected_engine") if snapshot.get("selected_engine") != "none" else "fallback",
        "tts_engine": fallback.engine,
        "runtime_available": True,
        "available": True,
        "audio_available": True,
        "audio_output_available": True,
        "audio_url": fallback.audio_url,
        "audio_mime": fallback.audio_mime,
        "audio_duration_ms": fallback.duration_ms,
        "status": "local_tts_audio_available",
        "reason": (
            "Fish direct synthesis is not wired; local Windows speech generated a temporary WAV."
            if snapshot.get("runtime_available")
            else "Fish runtime is unavailable; local Windows speech generated a temporary WAV."
        ),
        "error_reason": None,
        "fallback_engine": fallback.engine,
        "local_tts_rate": fallback.rate,
        "local_tts_volume": fallback.volume,
        "local_tts_sentence_gap_ms": int(preliminary_controls.get("fallback_sentence_gap_ms") or 220),
        "fallback_prosody_source": "neural_emotion_voice_controls",
        "fallback_prosody_applied": True,
        "text_fallback": True,
        "external_service": False,
        "generated_audio_persisted": False,
        "raw_voice_saved": False,
        "user_message": (
            "Fish 직접 합성은 아직 연결 전이라 Windows 로컬 음성으로 발화합니다."
            if language == "ko"
            else "Fish direct synthesis is not wired yet; using local Windows speech output."
        ),
    }


@router.get("/api/voice-loop/audio/{filename}")
def get_voice_loop_audio(filename: str) -> FileResponse:
    try:
        path = voice_audio_path(filename)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="voice audio not found") from exc
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="voice audio not found")
    return FileResponse(path, media_type="audio/wav", filename=filename)


_GROUNDED_PASTE_PREFIXES = (
    "The retrieved evidence defines",
    "Within the retrieved evidence",
    "Grounded in the retrieved evidence",
    "The evidence points to",
    "확인된 근거는",
)
_GROUNDED_CITATION_NOISE = ("GMT", "PMC ", "PMID", "http", "doi:", "ISBN", "《", "》", "-판다랭크")


def _grounded_answer_low_quality(answer: str, language: str) -> bool:
    """A grounded answer should be demoted to the clean Base Brain surface when it
    is cross-language for the question, looks like un-synthesized pasted evidence,
    or carries raw web-citation noise."""
    text = str(answer or "")
    if not text.strip():
        return True
    hangul = len(re.findall(r"[가-힣]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    if language == "en" and hangul >= 3:
        return True  # English answer must not carry Korean
    if language == "ko" and hangul == 0 and latin >= 8:
        return True  # Korean answer that is entirely English
    if any(text.strip().startswith(prefix) for prefix in _GROUNDED_PASTE_PREFIXES):
        return True  # un-synthesized paste
    if any(marker in text for marker in _GROUNDED_CITATION_NOISE):
        return True  # raw citation fragment
    return False


def _live_selfhood_payload(
    request: AtanorChatRequest,
    *,
    question: str,
    language: str,
    conversation_context: ConversationContextPacket | None = None,
) -> dict[str, Any]:
    context_packet = conversation_context or build_conversation_context(question, request.conversation_context)
    route = route_conversation_request(context_packet.contextual_query)
    runtime = _verified_store_runtime()
    runtime["language"] = language
    review_status = _review_queue_status()
    if review_status is not None:
        runtime["review_queue_status"] = review_status
    grounded_context = gather_grounded_context(context_packet.contextual_query, route, runtime=runtime)
    speech_act = _live_selfhood_speech_act(question, language)
    generated = generate_conversation_surface(
        question,
        language=language,
        route=route,
        grounded_context=grounded_context,
        context={
            "conversation_context": context_packet.to_dict(),
            "contextual_query": context_packet.contextual_query,
            "volatile_request_context_only": True,
        },
    )
    inner_voice_frame = emit_inner_voice_from_state(
        source_event_id=f"conversation_router:{speech_act}",
        mode="lab_visible",
        emotion_snapshot=EVENT_BUS.engine.snapshot().to_dict(),
        policy_decision={},
        agent_loop_state={},
        permission_tier="OBSERVE_ONLY",
        latest_user_input=question,
        language=language,
        latest_action_result={
            "speech_act": speech_act,
            "generated": bool(generated.answer),
            "route_type": route.route_type,
            "grounding_quality": grounded_context.grounding_quality,
        },
        review_queue_pressure=0.0,
        splatra_state={},
    )
    diagnostics = dict(generated.diagnostics or {})
    answer_mode = str(diagnostics.get("answer_mode") or "unknown_fallback")
    grounding_used = bool(diagnostics.get("semantic_grounding_used"))
    visual_plan = plan_visual_imagination(
        question,
        route=route,
        grounded_context=grounded_context,
        diagnostics=diagnostics,
        answer_available=bool(generated.answer),
        client_layout_feedback=request.layout_feedback,
    )
    splatra_command_sequence_obj = (
        compile_scene_choreography_commands(visual_plan.scene_choreography)
        if visual_plan.scene_choreography
        else None
    )
    splatra_command_sequence = splatra_command_sequence_obj.to_dict() if splatra_command_sequence_obj else None
    splatra_interactive_scene_analysis_obj = (
        analyze_scene_choreography(visual_plan.scene_choreography)
        if visual_plan.scene_choreography
        else None
    )
    splatra_interactive_scene_analysis = (
        splatra_interactive_scene_analysis_obj.to_dict()
        if splatra_interactive_scene_analysis_obj
        else None
    )
    splatra_cartridge_queue_obj = (
        build_candidate_cartridge_queue(splatra_command_sequence_obj)
        if splatra_command_sequence_obj
        else None
    )
    direct_splatra_generation = (
        visual_plan.diagnostics.get("scene_authoring_basis") == "user_direct_splatra_generation_request"
    )
    splatra_dispatch_budget = (
        _splatra_dispatch_budget(
            splatra_cartridge_queue_obj,
            visual_plan=visual_plan,
            direct_splatra_generation=direct_splatra_generation,
        )
        if splatra_cartridge_queue_obj
        else None
    )
    splatra_sidecar_dispatch = (
        dispatch_candidate_queue_to_sidecar(
            splatra_cartridge_queue_obj,
            poll_ticks=int(splatra_dispatch_budget["poll_ticks"]),
            timeout_sec=float(splatra_dispatch_budget["timeout_sec"]),
        ).to_dict()
        if splatra_cartridge_queue_obj and splatra_dispatch_budget
        else None
    )
    splatra_cartridge_queue = splatra_cartridge_queue_obj.to_dict() if splatra_cartridge_queue_obj else None
    if splatra_cartridge_queue and splatra_sidecar_dispatch:
        splatra_cartridge_queue["sidecar_dispatch_budget"] = splatra_dispatch_budget
        splatra_cartridge_queue["sidecar_dispatch"] = splatra_sidecar_dispatch
        splatra_cartridge_queue["sidecar_status"] = splatra_sidecar_dispatch.get("status")
        splatra_cartridge_queue["sidecar_configured"] = bool(splatra_sidecar_dispatch.get("configured"))
        splatra_cartridge_queue["external_splatra_called"] = bool(splatra_sidecar_dispatch.get("external_splatra_called"))
    visual_policy = {
        "scene_content_source": visual_plan.diagnostics.get("scene_content_source", "none"),
        "scene_authoring_basis": visual_plan.diagnostics.get("scene_authoring_basis"),
        "visual_affordance_basis": visual_plan.diagnostics.get("visual_affordance_basis"),
        "layout_decision_basis": visual_plan.diagnostics.get("layout_decision_basis"),
        "reason": visual_plan.diagnostics.get("reason") or visual_plan.reason,
        "topic_scene_templates": False,
        "renderer_may_infer_topic": False,
        "particle_text": False,
        "text_rendering": "dom_text_not_particles",
        "orb_identity": "atanor_self_body_not_scene_object" if visual_plan.scene_choreography else "atanor_primary_self_body",
        "verified_evidence_required_for_general_knowledge": route.route_type == "general_knowledge_question",
    }
    compact_trace = {
        "local_coverage": "semantic_grounded_conversation" if grounding_used else "live_selfhood_conversation",
        "selfhood_loop": {
            "used": True,
            "internal_scratchpad_visible": False,
            "rule_based_answer_blocked": True,
            "asm_v0_is_general_lm": False,
            "requires_learned_generator": False,
            "speech_act": speech_act,
            "emotion_hint": "warm" if speech_act in {"greeting", "thanks"} else "calm",
        },
        "conversation_router": route.to_dict(),
        "semantic_grounding": grounded_context.to_dict(),
        "semantic_cloud_graph": {
            "attached_nodes": 0,
            "evidence_docs": len(grounded_context.source_refs),
            "grounding_source": grounded_context.grounding_source,
            "grounding_quality": grounded_context.grounding_quality,
        },
        "conversation_context": {
            "turn_count": len(context_packet.turns),
            "used_for_routing": bool(context_packet.turns),
            "followup_detected": context_packet.followup_detected,
            "focus_terms": list(context_packet.focus_terms),
            "focus_source": context_packet.focus_source,
            "resolution_strategy": context_packet.resolution_strategy,
            "used_for_learning": False,
            "local_brain_write": False,
            "production_store_mutated": False,
            "basis": context_packet.basis,
        },
        "surface_graph": {
            "construction_families": [],
            "discourse_moves": [],
            "conversation_surface": diagnostics,
        },
        "q_cortex": {"used": False, "run_id": None, "real_quantum_hardware_used": False},
        "working_memory": {"temporary_context": False, "local_brain_write": False},
        "visual_imagination": visual_plan.diagnostics,
        "splatra_scene_policy": visual_policy,
        "splatra_command_sequence": {
            "available": bool(splatra_command_sequence),
            "action_count": len(splatra_command_sequence.get("scene_actions", [])) if splatra_command_sequence else 0,
            "raw_buffers_in_agent_context": False,
            "topic_scene_templates": False,
            "renderer_may_infer_topic": False,
            "text_rendering": "dom_text_not_particles",
        },
        "splatra_interactive_scene_analysis": {
            "available": bool(splatra_interactive_scene_analysis),
            "object_count": int(splatra_interactive_scene_analysis.get("object_count", 0)) if splatra_interactive_scene_analysis else 0,
            "raw_splat_inference": False,
            "raw_buffers_in_agent_context": False,
            "interactive_scene_metadata": bool(splatra_interactive_scene_analysis),
        },
        "splatra_cartridge_queue": {
            "available": bool(splatra_cartridge_queue),
            "job_count": int(splatra_cartridge_queue.get("job_count", 0)) if splatra_cartridge_queue else 0,
            "execution_mode": splatra_cartridge_queue.get("execution_mode", "none") if splatra_cartridge_queue else "none",
            "external_splatra_called": bool(splatra_sidecar_dispatch.get("external_splatra_called", False)) if splatra_sidecar_dispatch else False,
            "sidecar_status": splatra_sidecar_dispatch.get("status", "none") if splatra_sidecar_dispatch else "none",
            "sidecar_configured": bool(splatra_sidecar_dispatch.get("configured", False)) if splatra_sidecar_dispatch else False,
            "raw_buffer_in_agent_context": False,
            "mutation_performed": False,
        },
        "confidence": "medium" if generated.confidence >= 0.5 else "abstained",
        "inner_voice": {
            "emitted": True,
            "frame_id": inner_voice_frame.frame_id,
            "raw_inner_voice_hidden": True,
            "inner_voice_is_explicit_generated_channel": True,
            "raw_hidden_cot_claim": False,
        },
    }
    engine = {
        "name": "ATANOR Semantic-Grounded Conversation Router v0",
        "semantic_plane": "semantic_grounding_router" if grounding_used else "conversation_surface_only",
        "surface_plane": "asm_v0_construction_conditioned_surface",
        "external_llm": False,
        "external_sllm": False,
        "external_llm_used": False,
        "external_sllm_used": False,
        "local_brain_write": False,
        "production_store_mutated": False,
        "candidate_promotion": False,
        "trace_hidden_by_default": True,
        "internal_scratchpad_visible": False,
        "internal_trace_exposed": False,
        "rule_based_answer_used": False,
        "direct_prompt_answer_table_used": bool(diagnostics.get("direct_prompt_answer_table_used", False)),
        "hand_authored_construction_used": bool(diagnostics.get("hand_authored_construction_used", True)),
        "heuristic_act_inference_used": bool(diagnostics.get("heuristic_act_inference_used", True)),
        "local_transition_surface_used": bool(diagnostics.get("local_transition_surface_used", False)),
        "semantic_grounding_used": grounding_used,
        "grounding_source": diagnostics.get("grounding_source", grounded_context.grounding_source),
        "grounding_quality": diagnostics.get("grounding_quality", grounded_context.grounding_quality),
        "grounded_discourse_mode": diagnostics.get("grounded_discourse_mode"),
        "grounded_discourse_basis": diagnostics.get("grounded_discourse_basis"),
        "grounded_fact_roles": diagnostics.get("grounded_fact_roles") or [],
        "answer_mode": answer_mode,
        "route_type": route.route_type,
        "honesty_note": diagnostics.get("honesty_note"),
        "semantic_grounding_metadata_present": True,
        "honesty_metadata_present": True,
        "conversation_context_used": bool(context_packet.turns),
        "conversation_context_basis": context_packet.basis,
        "conversation_followup_detected": context_packet.followup_detected,
        "conversation_resolution_strategy": context_packet.resolution_strategy,
        "eval_rows_used_for_learning": False,
        "generation_basis": diagnostics.get("generation_basis"),
        "template_free_surface": bool(diagnostics.get("template_free_surface", False)),
        "splatra_scene_policy": visual_policy,
        "diagnostics": diagnostics,
    }
    if not generated.answer or _grounded_answer_low_quality(generated.answer, language):
        # The live conversation router abstained (no safe surface walk yet, e.g.
        # sparse English constructions). Rather than show the user nothing, fall
        # back to the graph-grounded Base Brain answer, which carries its own
        # evidence and English realizer. Still no external LLM and no rule-based
        # canned answer — Base Brain composes from the seed/semantic graph.
        # Compose directly from Base Brain in its native "default" answer mode.
        # We intentionally do NOT route through the shared _base_brain_payload
        # helper here: once the conversation router has already run inside this
        # request, that helper path can yield an empty surface, whereas the
        # direct call still returns the graph-grounded answer.
        base = answer_with_base_brain(
            question,
            language=language,  # type: ignore[arg-type]
            audience_level=request.audience_level,  # type: ignore[arg-type]
            mode="default",
        )
        base_answer = str(base.get("answer") or "").strip()
        if base_answer:
            fallback_trace = {
                **compact_trace,
                "conversation_fallback": "base_brain_after_conversation_abstain",
                "local_coverage": "base_brain",
            }
            return {
                "state": "completed",
                "result": {
                    "answer": base_answer,
                    "language": language,
                    "confidence": float(base.get("confidence") or 0.62),
                    "answer_kind": "base_brain_after_conversation_abstain",
                    # M4 bridge to SPLATRA: visualize a scene only when the verified
                    # evidence is concrete. Abstract answers stay text-only.
                    "scene_grounding": base.get("scene_grounding"),
                    # Traceable derivation (the "reasoning certificate") — which
                    # ontology concept + graph edges produced this answer.
                    "reasoning_certificate": base.get("reasoning_certificate"),
                    "speech_act": speech_act,
                    "can_speak": True,
                    "abstained_conversation_reason": generated.diagnostics.get(
                        "abstain_reason", "no_safe_token_walk"
                    ),
                    "default_trace_visible": False,
                    "trace": fallback_trace
                    if request.include_trace or request.mode in {"trace", "research"}
                    else None,
                    "compact_trace": fallback_trace,
                    "research_trace": None,
                    "evidence_docs": [],
                    "matched_nodes": [],
                    "matched_edges": [],
                    "surface_plan": {
                        "plan_id": None,
                        "intent": "base_brain_after_conversation_abstain",
                        "construction_families": compact_trace["surface_graph"]["construction_families"],
                        "q_cortex_used": False,
                        "q_cortex_run_id": None,
                    },
                    "scene_choreography": None,
                    "visual_scene_plan": None,
                    "splatra_scene_plan": None,
                    "splatra_command_sequence": None,
                    "splatra_interactive_scene_analysis": None,
                    "splatra_cartridge_queue": None,
                    "splatra_scene_policy": visual_policy,
                    "answer_engine": {
                        **engine,
                        "answer_kind": "base_brain_after_conversation_abstain",
                        "base_brain_fallback": True,
                        # Honest provenance: this surface came from the Base Brain
                        # seed/semantic graph realizer, not the conversation router.
                        "generation_basis": "base_brain_seed_graph_surface_v0",
                        "external_llm": False,
                        "external_sllm": False,
                        "external_llm_used": False,
                        "external_sllm_used": False,
                        "rule_based_answer_used": False,
                        "internal_trace_exposed": False,
                        "local_brain_write": False,
                        "production_store_mutated": False,
                        "candidate_promotion": False,
                    },
                    **{**_flags(), "final_answer_generation_claimed": True},
                },
                **{**_flags(), "final_answer_generation_claimed": True},
            }
        payload = {
            "answer": None,
            "language": language,
            "confidence": 0.0,
            "answer_kind": "grounded_conversation_abstained",
            "speech_act": speech_act,
            "can_speak": False,
            "abstain_reason": generated.diagnostics.get("abstain_reason", "no_safe_token_walk"),
            "default_trace_visible": False,
            "trace": compact_trace if request.include_trace or request.mode in {"trace", "research"} else None,
            "compact_trace": compact_trace,
            "research_trace": {"selfhood_loop": compact_trace["selfhood_loop"]} if request.mode == "research" else None,
            "evidence_docs": [],
            "matched_nodes": [],
            "matched_edges": [],
            "surface_plan": {
                "plan_id": None,
                "intent": "live_selfhood_conversation",
                "construction_families": compact_trace["surface_graph"]["construction_families"],
                "q_cortex_used": False,
                "q_cortex_run_id": None,
            },
            "scene_choreography": None,
            "visual_scene_plan": None,
            "splatra_scene_plan": None,
            "splatra_command_sequence": None,
            "splatra_interactive_scene_analysis": None,
            "splatra_cartridge_queue": None,
            "splatra_scene_policy": visual_policy,
            "answer_engine": engine,
            **{**_flags(), "final_answer_generation_claimed": False},
        }
        return {"state": "abstained", "result": payload, **{**_flags(), "final_answer_generation_claimed": False}}
    voice_output = _attach_voice_runtime_metadata(
        _voice_runtime_snapshot_with_local_audio(generated.answer, language),
        generated.answer,
        language,
    )
    # M4 gate: only attach a SPLATRA scene when the answer is concretely grounded.
    # Abstract answers stay text-only so the readable answer is not replaced by
    # particle scene beats on the dashboard.
    answer_scene_grounding = extract_scene_grounding(generated.answer, [], language=language)
    scene_eligible = bool(answer_scene_grounding.get("eligible"))
    gated_scene = visual_plan.scene_choreography if scene_eligible else None
    payload = {
        "answer": generated.answer,
        "language": language,
        "confidence": generated.confidence,
        "answer_kind": "asm_v0_conversation_surface",
        "answer_mode": answer_mode,
        "route_type": route.route_type,
        "speech_act": speech_act,
        "can_speak": True,
        "voice_output": voice_output,
        "default_trace_visible": False,
        "trace": compact_trace if request.include_trace or request.mode in {"trace", "research"} else None,
        "compact_trace": compact_trace,
        "research_trace": {"selfhood_loop": compact_trace["selfhood_loop"]} if request.mode == "research" else None,
        "evidence_docs": [],
        "matched_nodes": [],
        "matched_edges": [],
        "surface_plan": {
            "plan_id": None,
            "intent": "live_selfhood_conversation",
            "construction_families": compact_trace["surface_graph"]["construction_families"],
            "q_cortex_used": False,
            "q_cortex_run_id": None,
        },
        "scene_choreography": gated_scene,
        "visual_scene_plan": gated_scene,
        "splatra_scene_plan": gated_scene,
        "scene_grounding": answer_scene_grounding,
        # Evidence-grounded answers (web / verified store) expose a reasoning
        # certificate citing their sources and how they were processed.
        "reasoning_certificate": _grounded_conversation_certificate(
            question, grounded_context, generated.confidence, language
        ),
        "splatra_command_sequence": splatra_command_sequence,
        "splatra_interactive_scene_analysis": splatra_interactive_scene_analysis,
        "splatra_cartridge_queue": splatra_cartridge_queue,
        "splatra_sidecar_dispatch": splatra_sidecar_dispatch,
        "splatra_scene_policy": visual_policy,
        "answer_engine": engine,
        **_flags(),
    }
    return {"state": "completed", "result": payload, **_flags()}


_ONTOLOGY_GROUNDING_SOURCES = {
    "asm_v0_construction_graph",
    "base_brain_semantic_graph",
    "product_conversation_grounding",
}


def _grounded_conversation_certificate(
    question: str,
    grounded_context: Any,
    confidence: float,
    language: str,
) -> dict[str, Any] | None:
    """Build a reasoning certificate for an evidence-grounded conversation answer.

    Web / verified-store answers carry real sources and a processing path; expose
    them as a certificate (which sources, which facts, how grounded) instead of
    silently dropping it. No new claims are invented — only what grounding already
    produced is cited.
    """

    source_refs = [str(ref) for ref in getattr(grounded_context, "source_refs", ()) if ref]
    facts = [str(fact) for fact in getattr(grounded_context, "facts", ()) if fact]
    grounding_source = str(getattr(grounded_context, "grounding_source", "") or "")
    grounding_quality = str(getattr(grounded_context, "grounding_quality", "none") or "none")
    if not source_refs or grounding_quality == "none" or grounding_source in {"", "none"}:
        return None

    is_ko = language == "ko"
    steps: list[dict[str, Any]] = [
        {
            "type": "evidence_grounding",
            "source": grounding_source,
            "fact": (
                f"검증 근거를 {grounding_quality} 품질로 정합한 뒤 그 범위 안에서만 답을 구성했습니다."
                if is_ko
                else f"Aligned verified evidence at {grounding_quality} quality and composed the answer only within that scope."
            ),
        }
    ]
    for fact in facts[:6]:
        steps.append({"type": "grounded_fact", "fact": fact})
    for ref in source_refs[:8]:
        steps.append({"type": "evidence_source", "source": ref})

    topic = (question or "").strip()[:80] or ("이 질문" if is_ko else "this question")
    is_web = "web_evidence" in grounding_source or "cloud_graph" in grounding_source or "verified_store" in grounding_source
    return {
        "derivation_kind": "web_evidence_grounding" if is_web else "verified_evidence_grounding",
        "anchor_concept": {"id": topic, "label": topic, "match": "grounded_evidence"},
        "steps": steps,
        "evidence_concepts": source_refs,
        "confidence": round(float(confidence), 4),
        "confidence_basis": f"{grounding_source}:{grounding_quality}",
        "guarantees": {
            "external_llm": False,
            "external_sllm": False,
            "fabricated_facts": False,
            "evidence_grounded": True,
            "ontology_traceable": grounding_source in _ONTOLOGY_GROUNDING_SOURCES,
            "source_count": len(source_refs),
        },
    }


def _clean_graph_count_question(question: str) -> bool:
    lowered = question.lower()
    count_terms = (
        "총",
        "몇",
        "개수",
        "수",
        "표시",
        "렌더",
        "렌더링",
        "viewport",
        "rendered",
        "현재",
        "지금",
        "count",
        "how many",
        "number of",
    )
    graph_terms = (
        "노드",
        "node",
        "nodes",
        "관계",
        "관계선",
        "연결",
        "연결선",
        "엣지",
        "edge",
        "edges",
        "link",
        "links",
        "relation",
        "relations",
        "graph",
        "graph count",
        "시드",
        "seed",
        "base",
        "앵커",
    )
    memory_scope_terms = (
        "내 로컬 메모리",
        "로컬 메모리",
        "개인 메모리",
        "로컬 브레인",
        "클라우드 브레인",
        "local brain",
        "cloud brain",
        "local graph",
        "cloud graph",
        "저장된 기억",
        "저장된 노드",
        "화면",
        "표시",
        "렌더",
        "렌더링",
        "viewport",
        "rendered",
        "로컬",
        "클라우드",
        "local",
        "cloud",
        "메모리",
        "브레인",
        "brain",
        "그래프",
        "기본",
        "시드",
        "앵커",
        "seed",
        "base",
    )
    return (
        any(term in lowered or term in question for term in count_terms)
        and any(term in lowered or term in question for term in graph_terms)
        and any(term in lowered or term in question for term in memory_scope_terms)
    )


def _local_graph_count_snapshot() -> dict[str, Any]:
    try:
        from packages.brain_graph.aggregator import aggregate_brain_graph

        graph = aggregate_brain_graph(
            view="local",
            layers=["local_user", "local_base", "seed", "working_memory_local"],
            max_nodes=1200,
            max_edges=2400,
            mode="fast",
        )
    except Exception as exc:  # pragma: no cover - status must not fall through
        return {
            "available": False,
            "error": type(exc).__name__,
            "personal_local_memory_count": {"nodes": 0, "edges": 0},
            "local_viewport_materialized_count": {"nodes": None, "edges": None},
            "seed_anchor_count": None,
            "base_anchor_count": None,
            "rendered_edge_count": None,
            "logical_local_node_count": None,
        }
    stats = graph.get("stats") if isinstance(graph.get("stats"), dict) else {}
    layer_counts = stats.get("layer_counts") if isinstance(stats.get("layer_counts"), dict) else {}
    edge_layer_counts = stats.get("edge_layer_counts") if isinstance(stats.get("edge_layer_counts"), dict) else {}
    personal_nodes = int(layer_counts.get("local_user") or stats.get("local_user_nodes") or 0)
    personal_edges = int(edge_layer_counts.get("local_user") or 0)
    rendered_nodes = int(stats.get("rendered_nodes") or len(graph.get("nodes") or []))
    rendered_edges = int(stats.get("rendered_edges") or len(graph.get("edges") or []))
    return {
        "available": True,
        "personal_local_memory_count": {"nodes": personal_nodes, "edges": personal_edges},
        "local_viewport_materialized_count": {"nodes": rendered_nodes, "edges": rendered_edges},
        "seed_anchor_count": int(layer_counts.get("seed") or 0),
        "base_anchor_count": int(layer_counts.get("local_base") or 0),
        "working_memory_local_count": int(layer_counts.get("working_memory_local") or 0),
        "rendered_edge_count": rendered_edges,
        "logical_local_node_count": personal_nodes,
        "local_graph_pipeline": graph.get("honesty", {}).get("view_is_tab_aware", True),
    }


def _clean_graph_count_payload(
    request: AtanorChatRequest,
    *,
    question: str,
    language: str,
) -> dict[str, Any]:
    lowered = question.lower()
    wants_cloud = "cloud" in lowered or "클라우드" in question
    wants_local = "local" in lowered or "로컬" in question or not wants_cloud
    wants_viewport = any(term in lowered or term in question for term in ("화면", "표시", "렌더", "렌더링", "viewport", "rendered"))
    wants_seed_base = any(term in lowered or term in question for term in ("seed", "base", "시드", "기본", "앵커"))
    status_error: str | None = None
    local_snapshot = _local_graph_count_snapshot()
    try:
        cloud_status = SemanticCloudStore().status()
    except Exception as exc:  # pragma: no cover - status questions must stay safe
        status_error = type(exc).__name__
        cloud_status = {"concepts": 0, "relations": 0, "evidence": 0}
    personal_local = local_snapshot.get("personal_local_memory_count") if isinstance(local_snapshot.get("personal_local_memory_count"), dict) else {}
    local_nodes = int(personal_local.get("nodes") or 0)
    local_edges = int(personal_local.get("edges") or 0)
    viewport = local_snapshot.get("local_viewport_materialized_count") if isinstance(local_snapshot.get("local_viewport_materialized_count"), dict) else {}
    viewport_nodes = viewport.get("nodes")
    viewport_edges = viewport.get("edges")
    seed_anchor_count = local_snapshot.get("seed_anchor_count")
    base_anchor_count = local_snapshot.get("base_anchor_count")
    cloud_nodes = int(cloud_status.get("concepts") or 0)
    cloud_edges = int(cloud_status.get("relations") or 0)
    if wants_cloud and not wants_local:
        nodes = cloud_nodes
        edges = cloud_edges
        scope_ko = "클라우드 브레인 proof store"
        scope_en = "Cloud Brain proof store"
    elif wants_local and not wants_cloud:
        nodes = local_nodes
        edges = local_edges
        scope_ko = "로컬 브레인 개인 메모리 저장소"
        scope_en = "Local Brain private memory store"
    else:
        nodes = local_nodes + cloud_nodes
        edges = local_edges + cloud_edges
        scope_ko = "로컬 브레인과 클라우드 브레인 합산"
        scope_en = "Local Brain plus Cloud Brain"
    status_unavailable = status_error is not None and (wants_cloud or not wants_local)
    if status_unavailable and language == "ko":
        answer = "현재 그래프 상태를 읽을 수 없습니다. 일반 지식 답변으로 대체하지 않습니다."
    elif status_unavailable:
        answer = "ATANOR cannot read the graph status right now. It will not substitute an unrelated general-knowledge answer."
    elif language == "ko":
        if wants_local and not wants_cloud and (wants_viewport or wants_seed_base):
            if local_snapshot.get("available"):
                answer = (
                    f"개인 Local Brain 저장 메모리는 {local_nodes:,}개 노드 / {local_edges:,}개 연결선입니다. "
                    f"현재 화면에 물질화된 로컬 그래프 뷰포트는 {int(viewport_nodes or 0):,}개 노드 / {int(viewport_edges or 0):,}개 렌더링 연결선입니다. "
                    f"이 화면 값에는 기본 Seed/Base 앵커가 포함될 수 있으며, Seed 앵커 {int(seed_anchor_count or 0):,}개와 Base 앵커 {int(base_anchor_count or 0):,}개는 개인 저장 메모리로 계산하지 않습니다."
                )
            else:
                answer = "현재 로컬 그래프 뷰포트 상태를 읽을 수 없습니다. 일반 지식 답변으로 대체하지 않습니다."
        elif wants_local and not wants_cloud:
            answer = (
                f"개인 Local Brain 저장 메모리는 {local_nodes:,}개 노드 / {local_edges:,}개 연결선입니다. "
                f"현재 화면에 보이는 로컬 그래프 뷰포트는 별도 카테고리이며, 지금 확인된 표시 노드는 {int(viewport_nodes or 0):,}개, 표시 연결선은 {int(viewport_edges or 0):,}개입니다. "
                "Seed/Base 기본 그래프와 Working Memory 임시 노드는 개인 저장 메모리와 구분됩니다."
            )
        else:
            answer = (
                f"{scope_ko} 기준 현재 확인된 논리 노드는 {nodes:,}개, 연결선은 {edges:,}개입니다. "
                "개인 Local Brain 저장 메모리, 화면 뷰포트, Seed/Base 앵커, Cloud proof store는 서로 다른 count 카테고리입니다."
            )
    else:
        if wants_local and not wants_cloud and (wants_viewport or wants_seed_base):
            if local_snapshot.get("available"):
                answer = (
                    f"Personal Local Brain stored memory is {local_nodes:,} nodes / {local_edges:,} relations. "
                    f"The current local graph viewport has {int(viewport_nodes or 0):,} materialized nodes and {int(viewport_edges or 0):,} rendered edges. "
                    f"Seed anchors ({int(seed_anchor_count or 0):,}) and Base anchors ({int(base_anchor_count or 0):,}) are visible scaffolds, not personal stored memory."
                )
            else:
                answer = "ATANOR cannot read the local graph viewport status right now. It will not substitute an unrelated general-knowledge answer."
        elif wants_local and not wants_cloud:
            answer = (
                f"Personal Local Brain stored memory is {local_nodes:,} nodes / {local_edges:,} relations. "
                f"The visible local graph viewport is a separate category: {int(viewport_nodes or 0):,} displayed nodes and {int(viewport_edges or 0):,} displayed edges. "
                "Seed/Base scaffolds and temporary Working Memory nodes are not counted as personal stored memory."
            )
        else:
            answer = (
                f"For the {scope_en}, ATANOR currently sees {nodes:,} logical nodes and {edges:,} relations. "
                "Personal Local Brain memory, viewport rendering, Seed/Base anchors, and Cloud proof-store counts are separate categories."
            )
    compact_trace = {
        "local_coverage": "status_question",
        "graph_status": {
            "local_nodes": local_nodes,
            "local_edges": local_edges,
            "personal_local_memory_count": {"nodes": local_nodes, "edges": local_edges},
            "local_viewport_materialized_count": local_snapshot.get("local_viewport_materialized_count"),
            "seed_anchor_count": seed_anchor_count,
            "base_anchor_count": base_anchor_count,
            "rendered_edge_count": local_snapshot.get("rendered_edge_count"),
            "logical_local_node_count": local_snapshot.get("logical_local_node_count"),
            "count_categories": {
                "personal_local_memory_count": "user-owned Local Brain stored memories",
                "local_viewport_materialized_count": "nodes/edges currently visible or materialized in the local graph view",
                "seed_anchor_count": "default Seed anchors, not personal memory",
                "base_anchor_count": "Base Brain anchors, not personal memory",
                "rendered_edge_count": "edges currently rendered in the viewport",
                "logical_local_node_count": "full personal local logical graph count when available",
            },
            "cloud_nodes": cloud_nodes,
            "cloud_edges": cloud_edges,
            "selected_scope": "cloud" if wants_cloud and not wants_local else "local" if wants_local and not wants_cloud else "combined",
            "status_unavailable": status_unavailable,
            "status_error": status_error,
        },
        "semantic_cloud_graph": {"attached_nodes": 0, "evidence_docs": 0},
        "surface_graph": {"construction_families": ["direct_status_answer"], "discourse_moves": ["direct_answer"]},
        "q_cortex": {"used": False, "real_quantum_hardware_used": False},
        "working_memory": {"temporary_context": False, "local_brain_write": False},
        "confidence": "high",
    }
    payload = {
        "answer": answer,
        "language": language,
        "confidence": 0.52 if status_unavailable else 0.96,
        "default_trace_visible": False,
        "trace": compact_trace if request.include_trace or request.mode in {"trace", "research"} else None,
        "compact_trace": compact_trace,
        "research_trace": {"graph_status": compact_trace["graph_status"]} if request.mode == "research" else None,
        "evidence_docs": [],
        "surface_plan": {
            "plan_id": None,
            "intent": "graph_status_count",
            "construction_families": ["direct_status_answer"],
            "q_cortex_used": False,
            "q_cortex_run_id": None,
        },
        "answer_engine": {
            "name": "ATANOR Status Router",
            "semantic_plane": "Local/Cloud status counters",
            "surface_plane": "Direct status answer",
            "external_llm": False,
            "external_sllm": False,
            "local_brain_write": False,
            "trace_hidden_by_default": True,
        },
        **_flags(),
    }
    return {"state": "completed", "result": payload, **_flags()}


def _is_graph_count_question(question: str) -> bool:
    lowered = question.lower()
    count_terms = ("몇개", "몇 개", "개수", "총 개", "count", "how many", "number of")
    graph_terms = ("노드", "node", "관계", "relation", "edge", "그래프", "graph")
    return any(term in lowered for term in count_terms) and any(term in lowered for term in graph_terms)


def _is_splatra_visual_request(question: str) -> bool:
    """Keep direct visual-generation intent out of legacy text-only fallback."""

    return route_conversation_request(question).route_type == "splatra_request"


def _should_use_web_grounded_conversation(question: str) -> bool:
    route = route_conversation_request(question)
    if route.route_type in {
        "agentic_os_request",
        "greeting_smalltalk",
        "limitation_question",
        "local_cloud_brain_explanation",
        "memory_request",
        "project_status",
        "splatra_request",
        "unsafe_or_private_request",
        "voice_status",
    }:
        return False
    if route.route_type in {"general_knowledge_question", "unknown"}:
        return True
    lowered = question.lower()
    return any(
        term in lowered or term in question
        for term in (
            "search",
            "look up",
            "latest",
            "recent",
            "today",
            "news",
            "current",
            "what",
            "why",
            "how",
            "explain",
            "definition",
            "검색",
            "찾아",
            "최신",
            "최근",
            "오늘",
            "뉴스",
            "현재",
            "웹",
            "인터넷",
            "무엇",
            "뭐야",
            "왜",
            "어떻게",
            "설명",
            "정의",
            "법칙",
            "원리",
            "누구",
            "누가",
            "who",
            "뜻",
            "알려줘",
        )
    )


def _should_try_base_brain_first(question: str) -> bool:
    lowered = question.lower()
    return any(
        term in lowered or term in question
        for term in (
            "local brain",
            "cloud brain",
            "q-cortex",
            "qcortex",
            "atanor",
            "아타노르",
            "로컬 브레인",
            "클라우드 브레인",
            "양자컴퓨터",
            "ram",
            "ssd",
            "컴퓨터 메모리",
            "휘발성 메모리",
            "주기억장치",
            "memory vs ssd",
            "volatile memory",
            "computer memory",
            "근거 중심",
            "과장 없이",
            "템플릿",
            "내부 경로",
            "숨기",
            "초등학생",
            "중학생",
            "전문가",
            "영어로",
            "한국어답게",
            "번역투",
        )
    )


def _graph_count_payload(request: AtanorChatRequest, question: str, language: str) -> dict[str, Any]:
    status = SemanticCloudStore().status()
    cloud_nodes = int(status.get("concepts") or 0)
    cloud_relations = int(status.get("relations") or 0)
    evidence = int(status.get("evidence") or 0)
    candidate_pairs = cloud_nodes * max(0, cloud_nodes - 1) // 2
    local_nodes = 0
    local_relations = 0
    if language == "ko":
        answer = (
            f"현재 확인된 기준으로 Local Brain 사용자 메모리는 {local_nodes:,}개 노드 / {local_relations:,}개 관계입니다. "
            f"Cloud Brain proof store에는 논리 노드 {cloud_nodes:,}개, 검증 저장 관계 {cloud_relations:,}개, 근거 {evidence:,}개가 있습니다. "
            f"참고로 가능한 노드쌍은 {candidate_pairs:,}개지만, ATANOR는 모든 쌍을 관계로 저장하지 않고 실제로 추출/검증된 관계만 저장합니다."
        )
    else:
        answer = (
            f"Current Local Brain user memory is {local_nodes:,} nodes / {local_relations:,} relations. "
            f"The Cloud Brain proof store has {cloud_nodes:,} logical nodes, {cloud_relations:,} verified stored relations, and {evidence:,} evidence records. "
            f"There are {candidate_pairs:,} possible node pairs, but ATANOR stores only extracted and verified relations, not every possible pair."
        )
    compact_trace = {
        "local_coverage": "status_query",
        "semantic_cloud_graph": {
            "attached_nodes": 0,
            "evidence_docs": 0,
            "cloud_logical_nodes": cloud_nodes,
            "cloud_stored_relations": cloud_relations,
            "candidate_pairs": candidate_pairs,
        },
        "surface_graph": {"construction_families": ["direct_status_answer"], "discourse_moves": ["answer"]},
        "q_cortex": {"used": False, "run_id": None, "real_quantum_hardware_used": False},
        "working_memory": {"temporary_context": False, "local_brain_write": False},
        "confidence": "high",
    }
    payload = {
        "answer": answer,
        "language": language,
        "confidence": 0.98,
        "answer_kind": "graph_status",
        "default_trace_visible": False,
        "trace": compact_trace if request.include_trace or request.mode in {"trace", "research"} else None,
        "compact_trace": compact_trace,
        "research_trace": {"semantic_cloud_status": status} if request.mode == "research" else None,
        "evidence_docs": [],
        "matched_nodes": [],
        "surface_plan": {
            "plan_id": None,
            "intent": "graph_status",
            "construction_families": ["direct_status_answer"],
            "q_cortex_used": False,
            "q_cortex_run_id": None,
        },
        "answer_engine": {
            "name": "ATANOR Status Router",
            "semantic_plane": "Semantic Cloud Proof Store",
            "surface_plane": "Direct Status Answer",
            "external_llm": False,
            "external_sllm": False,
            "local_brain_write": False,
            "trace_hidden_by_default": True,
        },
        **_flags(),
    }
    return {"state": "completed", "result": payload, **_flags()}


def _emit_conversation_result_events(response: dict[str, Any]) -> None:
    result = response.get("result") if isinstance(response, dict) else {}
    if not isinstance(result, dict):
        return
    state = str(response.get("state") or "")
    answer_kind = str(result.get("answer_kind") or "")
    has_answer = bool(str(result.get("answer") or "").strip())
    emit_runtime_event(
        source="asm_v0",
        event_type="conversation_success" if has_answer and state != "abstained" else "repeated_failure",
        payload_summary=f"state={state}; answer_kind={answer_kind}; has_answer={has_answer}",
        intensity=0.55 if has_answer else 0.75,
    )
    voice_output = result.get("voice_output")
    if isinstance(voice_output, dict):
        emit_runtime_event(
            source="voice_loop",
            event_type="voice_available" if voice_output.get("audio_available") else "voice_unavailable",
            payload_summary=f"audio_available={voice_output.get('audio_available')}; fallback={voice_output.get('text_fallback')}",
            intensity=0.45,
        )


@router.post("/api/dual-brain/ingest")
def dual_brain_ingest(request: DualBrainIngestRequest) -> dict[str, Any]:
    source = SourceSentence.from_text(
        request.text,
        source_id=request.source_id,
        url=request.url,
        title=request.title,
        license=request.license,
        usage_allowed=request.usage_allowed,
        metadata=request.metadata,
    )
    return {**ingest_source_sentence_dual_projection(source), **_flags()}


def _semantic_context_from_rag(result: dict[str, Any]) -> dict[str, Any]:
    concepts = list(result.get("active_concepts") or [])
    for node in result.get("matched_nodes") or []:
        label = node.get("label") or node.get("primary_name") or node.get("id")
        if label and label not in concepts:
            concepts.append(label)
    relations = []
    for edge in result.get("matched_edges") or []:
        relations.append(
            {
                "source": edge.get("source") or edge.get("source_hash"),
                "relation": edge.get("relation") or edge.get("predicate"),
                "target": edge.get("target") or edge.get("target_hash"),
                "confidence": edge.get("confidence") or edge.get("weight") or 0.5,
            }
        )
    return {
        "concepts": concepts,
        "relations": relations,
        "evidence": list(result.get("evidence_docs") or []),
        "claims": list(result.get("claim_plan") or []),
        "confidence": float(result.get("confidence") or 0.0),
        "local_coverage": "high" if result.get("memory_activation") else "low" if not concepts else "medium",
        "retrieval_trace": result.get("retrieval_trace", {}),
    }


def _clean_rag_fact_text(value: Any, *, limit: int = 420) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if not text:
        return ""
    if "payload-vault://" in text or re.search(r"\b[0-9a-f]{24,}\b", text, flags=re.IGNORECASE):
        return ""
    if UNSAFE_DEFAULT_ANSWER_RE.search(text):
        return ""
    original_sentence_matches = re.findall(r"[^.!?。]+[.!?。]", text)
    sentence_matches = [
        sentence.strip()
        for sentence in original_sentence_matches
        if not re.search(r"(으로|로|와|과|및|또는|그리고|처음)\.$", sentence.strip())
    ]
    if sentence_matches and len(sentence_matches) < len(original_sentence_matches):
        text = " ".join(sentence_matches)
        if len(text) <= limit:
            return text
    if len(text) <= limit:
        return text
    first_two_sentences = " ".join(sentence.strip() for sentence in sentence_matches[:2])
    if limit >= 160 and first_two_sentences and len(first_two_sentences) <= limit + 80:
        return first_two_sentences
    first_sentence = sentence_matches[0].strip() if sentence_matches else ""
    if first_sentence and len(first_sentence) <= limit + 80:
        return first_sentence
    clipped = text[:limit].rstrip()
    boundary = max(
        clipped.rfind(mark)
        for mark in (
            ".",
            "?",
            "!",
            "다.",
            "요.",
            "이다.",
            "였다.",
            "었다.",
            "하였다.",
            "되었다.",
        )
    )
    if boundary >= max(32, int(limit * 0.35)):
        return clipped[: boundary + 1].rstrip()
    return clipped.rstrip(" ,;:") + "..."


def _clean_public_fact_bound_answer(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if not text:
        return ""
    text = re.sub(r"([.!?。])(?=\S)", r"\1 ", text)
    sentences = [sentence.strip() for sentence in re.findall(r"[^.!?。]+[.!?。]", text)]
    if not sentences:
        return text
    filtered = [
        sentence
        for sentence in sentences
        if not re.search(r"(으로|로|와|과|및|또는|그리고|처음)\.$", sentence)
    ]
    if not filtered:
        return text
    return " ".join(filtered)


CONTEXT_DEPENDENT_FACT_OPENERS = (
    "첫 번째 항",
    "두 번째 항",
    "세 번째 항",
    "맨 첫 번째 항",
    "첫 번째 단계",
    "두 번째 단계",
    "세 번째 단계",
    "맨 첫 번째 단계",
    "그 중",
    "그중",
    "따라서",
    "그러므로",
    "이 오차",
    "이 항",
    "이 경우",
    "이는",
    "이것은",
    "그것은",
    "the first term",
    "the second term",
    "the third term",
    "therefore",
    "this term",
    "this error",
    "in this case",
)


def _is_context_dependent_fact_fragment(text: str) -> bool:
    """Reject source fragments that need a missing previous paragraph.

    This is a retrieval-quality gate, not an answer template. It prevents
    verified but non-standalone snippets such as formula-term commentary from
    becoming the user-facing explanation.
    """

    compact = re.sub(r"\s+", " ", str(text or "").strip()).casefold()
    if not compact:
        return False
    return compact.startswith(tuple(opener.casefold() for opener in CONTEXT_DEPENDENT_FACT_OPENERS))


def _is_visual_event_evidence_doc(doc: dict[str, Any]) -> bool:
    return bool(doc.get("visual_evidence_enrichment")) or str(doc.get("source_type") or "") == "encyclopedia_visual_event_extract"


def _ordered_evidence_for_grounded_context(evidence: Any) -> list[dict[str, Any]]:
    """Keep definition evidence first, but preserve source-local visual events.

    Web search may attach visual/motion sentences from the same source page
    after the generic definition hits. If the first six grounded facts are all
    generic snippets, the visual planner never sees the evidence-local motion
    sentence and has to abstain. This ordering does not invent topic props; it
    only gives marked source-local visual-event evidence a stable slot.
    """

    docs = [doc for doc in evidence or [] if isinstance(doc, dict)]
    visual_docs = [doc for doc in docs if _is_visual_event_evidence_doc(doc)]
    if not visual_docs:
        return docs
    non_visual_docs = [doc for doc in docs if not _is_visual_event_evidence_doc(doc)]
    return non_visual_docs[:2] + visual_docs[:2] + non_visual_docs[2:]


def _grounded_context_from_semantic_context(
    question: str,
    *,
    route: Any,
    semantic_context: dict[str, Any],
) -> GroundedContext:
    """Convert RAG/web evidence into the visual planner's fact-bound context.

    The planner must not infer props from a topic such as "gravity". It receives
    only evidence-local snippets, claims, and relation labels already returned by
    the retrieval layer.
    """

    facts: list[str] = []
    source_refs: list[str] = []
    for doc in _ordered_evidence_for_grounded_context(semantic_context.get("evidence")):
        title = _clean_rag_fact_text(doc.get("title"), limit=96)
        snippet = _clean_rag_fact_text(doc.get("snippet") or doc.get("text"), limit=360)
        if title and snippet and title.casefold() not in snippet.casefold():
            fact = f"{title}. {snippet}"
        else:
            fact = snippet or title
        if fact and not _is_context_dependent_fact_fragment(snippet or fact):
            facts.append(fact)
        ref = _clean_rag_fact_text(doc.get("url") or doc.get("path") or doc.get("source_ref") or title, limit=180)
        if ref:
            source_refs.append(ref)

    for claim in semantic_context.get("claims") or []:
        if isinstance(claim, dict):
            fact = _clean_rag_fact_text(claim.get("claim") or claim.get("text") or claim.get("summary"), limit=360)
            ref = _clean_rag_fact_text(claim.get("source") or claim.get("source_ref") or claim.get("source_scope"), limit=180)
        else:
            fact = _clean_rag_fact_text(claim, limit=360)
            ref = ""
        if fact:
            facts.append(fact)
        if ref:
            source_refs.append(ref)

    if not facts:
        for relation in semantic_context.get("relations") or []:
            if not isinstance(relation, dict):
                continue
            source = _clean_rag_fact_text(relation.get("source"), limit=80)
            predicate = _clean_rag_fact_text(relation.get("relation") or relation.get("predicate"), limit=80)
            target = _clean_rag_fact_text(relation.get("target"), limit=120)
            if source and predicate and target:
                facts.append(f"{source} {predicate} {target}.")

    deduped_facts: list[str] = []
    seen_facts: set[str] = set()
    for fact in facts:
        key = fact.casefold()
        if key in seen_facts:
            continue
        seen_facts.add(key)
        deduped_facts.append(fact)
        if len(deduped_facts) >= 6:
            break

    if not deduped_facts:
        return GroundedContext(
            route_type=route.route_type,
            facts=(),
            constraints=("Verified grounding is insufficient for a confident visual scene.",),
            unknowns=("No evidence-local visual facts matched the question.",),
            source_refs=(),
            grounding_source="none",
            grounding_quality="none",
            safety_flags=semantic_safety_flags(),
        )

    refs: list[str] = []
    seen_refs: set[str] = set()
    for ref in source_refs:
        key = ref.casefold()
        if key in seen_refs:
            continue
        seen_refs.add(key)
        refs.append(ref)
        if len(refs) >= len(deduped_facts):
            break

    quality = "high" if len(refs) >= 2 else "medium"
    return GroundedContext(
        route_type=route.route_type,
        facts=tuple(deduped_facts),
        constraints=(
            "Use only retrieved web/graph evidence facts.",
            "Do not invent illustrative facts or scene entities beyond retrieved evidence.",
            "Render narration as DOM text, never as particle text.",
        ),
        unknowns=(),
        source_refs=tuple(refs),
        grounding_source="semantic_cloud_graph_web_evidence_readonly",
        grounding_quality=quality,
        safety_flags=semantic_safety_flags(),
    )


def _web_fact_bound_surface(
    question: str,
    *,
    route: Any,
    grounded_context: GroundedContext,
    language: str,
) -> str | None:
    """Prefer evidence-local facts over graph-token fragments for web answers.

    This does not introduce a prompt answer table. It only serializes facts that
    have already passed through the read-only web/graph evidence path.
    """

    if getattr(route, "route_type", "") != "general_knowledge_question":
        return None
    if grounded_context.grounding_quality == "none" or not grounded_context.facts:
        return None
    return realize_grounded_context(question, grounded_context, language=language)


def _needs_base_brain_fallback(semantic_context: dict[str, Any]) -> bool:
    return not (semantic_context.get("relations") or semantic_context.get("evidence") or semantic_context.get("claims"))


def _first_sentences(text: str, *, max_chars: int = 360) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    last = max(cut.rfind(". "), cut.rfind(". "), cut.rfind("다. "))
    return (cut[: last + 1] if last > 60 else cut).strip()


def _store_web_fact(question: str, title: str, answer: str, url: str) -> None:
    """Retain a web-looked-up fact locally so re-asking is instant / offline-safe."""
    try:
        subject = (title or question).strip()[:80]
        if subject and answer:
            WEB_FACT_MEMORY.remember("knowledge", subject, answer, source="conversation", source_ref=f"web:{url}", confidence=0.7)
    except Exception:  # pragma: no cover
        pass


def _recall_web_fact(question: str) -> dict[str, Any] | None:
    """Return a previously looked-up web fact relevant to the question, if any."""
    try:
        hits = WEB_FACT_MEMORY.recall(question, limit=1)
        if not hits:
            return None
        fact = hits[0]
        # require a real topic overlap so we don't surface an unrelated cached fact
        q_tokens = {t for t in re.split(r"\s+", re.sub(r"[?!.]", " ", question.lower())) if len(t) >= 3}
        s_tokens = {t for t in re.split(r"\s+", fact.subject.lower()) if len(t) >= 2}
        if not (q_tokens & s_tokens):
            return None
        url = fact.source_ref[4:] if fact.source_ref.startswith("web:") else ""
        return {
            "answer": fact.value,
            "reasoning_certificate": {
                "derivation_kind": "local_web_fact_recall",
                "anchor_concept": {"id": fact.subject, "label": fact.subject, "match": "local_web_memory"},
                "steps": [{"type": "remembered_web_fact", "source": url or "local_web_memory", "fact": fact.value[:160]}],
                "evidence_concepts": [url] if url else [],
                "confidence": 0.6,
                "confidence_basis": "previously_looked_up_web_fact",
                "guarantees": {"external_llm": False, "fabricated_facts": False, "from_earlier_lookup": True},
            },
            "confidence": 0.6,
            "provider": "local_web_memory",
            "source_url": url,
            "source_title": fact.subject,
        }
    except Exception:  # pragma: no cover
        return None


_OPEN_BROWSER_KO = ("검색해", "검색 해", "찾아봐", "찾아 줘", "찾아줘", "띄워", "띄워줘", "열어줘", "보여줘", "브라우저")
_OPEN_BROWSER_EN = ("search for", "look up", "look it up", "open the", "open a", "show me the", "browse", "pull up", "find online")


def _render_iframe_for_intent(question: str, language: str) -> dict[str, Any] | None:
    """If the user explicitly asks ATANOR to search/open/show something, the agent
    opens a search/document in the iframe stage of its own accord."""
    raw = str(question or "")
    lowered = raw.lower()
    if not (any(m in raw for m in _OPEN_BROWSER_KO) or any(m in lowered for m in _OPEN_BROWSER_EN)):
        return None
    topic = re.sub(r"(검색해줘|검색해|검색|찾아봐|찾아줘|띄워줘|띄워|열어줘|보여줘|에 대해|에 대한|브라우저로|브라우저)", " ", raw)
    topic = re.sub(r"\b(search for|look it up|look up|open the|open a|show me the|browse|pull up|find online|please|on the web|online)\b", " ", topic, flags=re.IGNORECASE)
    topic = re.sub(r"[?!.]", " ", topic)
    topic = re.sub(r"\s+", " ", topic).strip()
    if len(topic) < 2:
        return None
    host = "ko.wikipedia.org" if re.search(r"[가-힣]", topic) else "en.wikipedia.org"
    from urllib.parse import quote_plus

    return {"url": f"https://{host}/wiki/Special:Search?search={quote_plus(topic)}", "title": topic[:60]}


# (relation_key, KO question markers, EN question markers, EN past-participle verb)
_ATTRIBUTION_RELATIONS: tuple[tuple[str, tuple[str, ...], tuple[str, ...], str], ...] = (
    ("invented", ("발명",), ("invent",), "invented"),
    ("discovered", ("발견",), ("discover",), "discovered"),
    ("wrote", ("쓴", "저자", "지은"), ("wrote", "author of", "who wrote"), "written"),
    ("founded", ("설립", "세운", "창립", "창업", "설립자", "창립자", "창업자", "공동창업"), ("found", "establish", "co-found"), "founded"),
    ("painted", ("그린",), ("paint",), "painted"),
    ("composed", ("작곡",), ("compose",), "composed"),
    ("directed", ("감독",), ("direct",), "directed"),
    ("built", ("지은", "건설"), ("built", "who built"), "built"),
    ("created", ("만든", "창시"), ("creat", "develop"), "created"),
)

_PERSON_RE = r"([A-Z][\w.'\-]+(?:\s+(?:[A-Z][\w.'\-]+|of|von|van|de|der|da|al))*\s+[A-Z][\w.'\-]+)"


def _detect_attribution_relation(question: str) -> tuple[str, str] | None:
    raw = str(question or "")
    lowered = raw.lower()
    for key, ko_markers, en_markers, verb in _ATTRIBUTION_RELATIONS:
        if any(m in raw for m in ko_markers) or any(m in lowered for m in en_markers):
            # only treat as an attribution ("who …") question, not a definition
            if "누가" in raw or "누구" in raw or re.search(r"\bwho\b", lowered) or any(m in raw for m in ko_markers):
                return key, verb
    return None


def _extract_attribution(question: str, snippets: list[str]) -> str | None:
    """Deterministically pull the PERSON credited for an action ('invented by
    Alexander Graham Bell') from retrieved web snippets. No LLM. Returns a name."""
    rel = _detect_attribution_relation(question)
    if not rel:
        return None
    key, verb = rel
    ko_markers = next((m for k, m, _e, _v in _ATTRIBUTION_RELATIONS if k == key), ())
    en_patterns = [
        re.compile(rf"\b{verb}\s+by\s+{_PERSON_RE}"),
        re.compile(rf"\b(?:credited to|attributed to|invention of [^.]*?by)\s+{_PERSON_RE}", re.IGNORECASE),
        re.compile(rf"{_PERSON_RE}\s+(?:{verb}|is credited with|is the inventor)"),
    ]
    # Korean is SOV ("벨이 전화기를 발명했다"): the subject (name) and the verb are
    # separated by the object, so we capture a NON-GREEDY name run, keep the
    # subject particle OUTSIDE the capture, and allow one object phrase before the
    # verb. A comma/middot list captures co-founders ("젠슨 황, 크리스 …, 커티스 …").
    # A single name is ≤3 space-separated Hangul tokens ("레오나르도 다 빈치"); bounding
    # it stops the non-greedy capture from swallowing preceding descriptors
    # ("16세기 르네상스 시대에 …"). A comma list captures co-founders.
    NAME_SINGLE = r"[가-힣]{2,8}(?:\s[가-힣]{1,8}){0,2}"
    NAME_LIST = rf"({NAME_SINGLE}(?:\s*[,·]\s*{NAME_SINGLE}){{0,4}})"
    NAME = rf"({NAME_SINGLE})"
    ko_patterns = []
    for m in ko_markers:
        # year-anchored founders (list-aware): "1993년 4월 5일 NAME, NAME, NAME이 설립"
        ko_patterns.append(re.compile(rf"\d{{4}}년[\s\d월일.~-]*{NAME_LIST}(?:이|가|은|는|등이|등은)\s*(?:[가-힣]+(?:을|를)\s+)?(?:{m})"))
        # "NAME, NAME가 설립/창립한" — list-aware, no year
        ko_patterns.append(re.compile(rf"{NAME_LIST}(?:이|가|은|는|등이|등은)\s*(?:{m})하"))
        # "NAME가 (OBJECT를) VERB" — single person, SOV (covers 발명/그린/만든)
        ko_patterns.append(re.compile(rf"{NAME}(?:이|가|은|는)\s+(?:[가-힣]+(?:을|를|에)\s+)?(?:{m})"))
        # "VERB한 사람은 NAME" — require an explicit head noun so "그린 초상화" is not a name
        ko_patterns.append(re.compile(rf"(?:{m})한?\s*(?:사람은|사람이|이는|장본인은)\s*{NAME}(?:이|가|은|는|\.|,)"))
    # Definitional fragments that must never be returned as a "name".
    _bad_name_bits = (
        "초상화", "그림", "작품", "회사", "기업", "본사", "현재", "당시", "미국", "한국", "프랑스",
        "파리", "영어", "데이터", "기술", "컴퓨", "박물관", "대학", "정부", "도시", "지역", "세계",
        "사람", "이름", "누구", "수도", "영화", "소설", "전화", "신호", "음성", "이론", "세기", "시대", "르네상스",
    )

    def _clean_ko_name(raw: str) -> str:
        n = raw.strip(" .,·")
        n = re.sub(r"^(?:일|월|은|는|이|가|을|를|도|와|과|의)\s+", "", n)  # stray leading particle/date
        n = re.sub(r"\s*(?:에\s*의해|에게|께서|이|가|은|는|을|를|등)$", "", n)
        return n.strip(" .,·")

    def _valid_ko_name(n: str) -> bool:
        return bool(n) and not any(b in n for b in _bad_name_bits) and not re.search(r"[0-9]", n) and 2 <= len(n) <= 50

    for snippet in snippets:
        text = re.sub(r"\s+", " ", str(snippet or ""))
        is_ko_text = bool(re.search(r"[가-힣]", text))
        patterns = ko_patterns if is_ko_text else en_patterns
        for pattern in patterns:
            match = pattern.search(text)
            if not match:
                continue
            if is_ko_text:
                name = _clean_ko_name(match.group(1))
                if _valid_ko_name(name):
                    return name
            else:
                name = match.group(1).strip(" .,")
                if name.split()[0] not in {"The", "A", "An", "It", "This", "He", "She"} and 2 <= len(name) <= 60:
                    return name
    return None


async def _web_grounded_rescue(question: str, language: str) -> dict[str, Any] | None:
    """When the local engine has no answer and web search is ON, answer from a
    real web source (Wikipedia, or a configured provider) and cite it. This is
    retrieval-augmented grounding — the answer IS the retrieved evidence,
    attributed; no LLM, no fabrication. Returns None if nothing relevant."""
    try:
        from app.services.web_search import search_web, wikipedia_search

        payload = await search_web(question, 5)
    except Exception:  # pragma: no cover - network/optional
        payload = None
    provider = str((payload or {}).get("provider") or "")
    rows_available = list((payload or {}).get("results") or [])
    is_ko = language == "ko"
    # Reliable free fallback: a configured provider may be missing/unconfigured
    # (→ "static" fixtures) or the provider path may yield nothing. Wikipedia is a
    # keyless public encyclopedia, so try it directly (language-aware) before ever
    # declaring the web unreachable. This is what makes the answer reflect search.
    if provider in ("", "static") or not rows_available:
        try:
            wiki_rows = wikipedia_search(question, 5)
        except Exception:  # pragma: no cover - network/optional
            wiki_rows = []
        if wiki_rows:
            provider = "wikipedia"
            payload = {"provider": "wikipedia", "results": wiki_rows}
    # For a knowledge query the web search tries real retrieval first and only
    # falls back to "static" when the live web could not be reached (offline /
    # rate-limited / down). Say so honestly instead of pasting fixtures.
    if provider in ("", "static"):
        # Offline / unreachable: answer from a fact ATANOR looked up earlier, if it
        # has one (the agent remembers what it learned from the web).
        cached = _recall_web_fact(question)
        if cached:
            return cached
        return {
            "answer": (
                "지금 인터넷에서 확인하지 못했어요 (웹 연결 또는 검색 불가). 로컬에 있는 지식 범위 안에서만 답할 수 있어요."
                if is_ko
                else "I couldn't reach the web to check this right now (no connection or search unavailable). I can only answer from local knowledge."
            ),
            "reasoning_certificate": {
                "derivation_kind": "web_unreachable",
                "anchor_concept": None,
                "steps": [{"type": "web_status", "fact": "live web retrieval unavailable; no fixtures used"}],
                "evidence_concepts": [],
                "confidence": 0.2,
                "confidence_basis": "web_unreachable",
                "guarantees": {"external_llm": False, "fabricated_facts": False, "static_fixtures_used": False},
            },
            "confidence": 0.2,
            "provider": "offline",
            "source_url": "",
            "source_title": "",
            "web_unreachable": True,
        }
    if provider == "microsoft-grounding":
        return None
    def _is_citation_cruft(snippet: str) -> bool:
        # bibliography / reference entries, not prose ("Lewis (1995). ... McFarland & Co.")
        return bool(
            re.match(r"^\s*([A-Z][\w.'\-]+,?\s+){1,3}\(\d{4}\)", snippet)
            or re.match(r"^\s*(\d|pp\b|p\.|vol\b|archived|retrieved|ISBN)", snippet, re.IGNORECASE)
            or re.search(r"\b(ISBN|McFarland|Press|Co\.|pp\.\s*\d|Archived|Retrieved)\b", snippet[:120])
        )

    def _looks_like_definition(snippet: str) -> bool:
        if _is_citation_cruft(snippet):
            return False
        head = snippet[:80]
        return bool(re.search(r"\b(is|was|are|were)\s+(a|an|the)\b", head) or re.search(r"(이다|입니다|[은는이가]\s)", head))

    rows = [
        r for r in (payload.get("results") or [])
        if len(str(r.get("snippet") or "").strip()) >= 60 and not _is_citation_cruft(str(r.get("snippet") or ""))
    ]
    # RELEVANCE GATE (critical correctness): a full-text encyclopedia search can
    # return a page that merely *mentions* the term in passing (e.g. asking
    # "팔란티어가 뭐야?" surfaced a Miraculous Ladybug character-list page). Such a
    # page is definition-shaped but NOT about the entity. We must never present an
    # off-topic page as the answer, and never graft it into the brain. So require
    # that the query's core entity term actually anchors the result — in the TITLE,
    # or as the subject in the first sentence — before a row is eligible.
    try:
        from app.services.web_search import _lookup_terms, _normalize_lookup_query

        _core_terms = [t for t in _lookup_terms(_normalize_lookup_query(question)) if len(t) >= 2]
    except Exception:  # pragma: no cover - defensive
        _core_terms = []

    def _on_topic(row: dict[str, Any]) -> bool:
        if not _core_terms:
            return True  # nothing to anchor on; fall back to prior behaviour
        title_l = str(row.get("title") or "").lower()
        subject = str(row.get("snippet") or "")[:48].lower()
        # Title anchor is the strongest signal the page is *about* the entity.
        if any(term in title_l for term in _core_terms):
            return True
        # Otherwise the term must lead the snippet AND the search counted a hit.
        return any(term in subject for term in _core_terms) and int(row.get("query_terms_matched") or 0) >= 1

    on_topic_rows = [r for r in rows if _on_topic(r)]
    if not on_topic_rows:
        # No retrieved page is genuinely about the asked entity. Abstain honestly
        # rather than answer from an unrelated page — and graft nothing.
        return {
            "answer": (
                f"‘{question.strip()}’에 대해 확인된 근거가 있는 문서를 웹에서 찾지 못했어요. 추측해서 답하지 않을게요 — 질문을 조금 더 구체적으로 주시면 다시 찾아볼게요."
                if is_ko
                else f"I couldn't find a reliable source genuinely about “{question.strip()}.” I won't guess — give me a bit more detail and I'll look again."
            ),
            "reasoning_certificate": {
                "derivation_kind": "web_no_relevant_source",
                "anchor_concept": None,
                "steps": [{"type": "web_relevance_gate", "fact": "retrieved pages did not anchor the asked entity (title/subject mismatch); abstained instead of answering off-topic"}],
                "evidence_concepts": [],
                "confidence": 0.15,
                "confidence_basis": "no_relevant_source",
                "guarantees": {"external_llm": False, "fabricated_facts": False, "off_topic_source_used": False, "grafted_to_brain": False},
            },
            "confidence": 0.15,
            "provider": "web_no_match",
            "source_url": "",
            "source_title": "",
            "web_no_relevant_source": True,
        }
    rows = on_topic_rows
    # prefer a definition-shaped snippet with the strongest term match; fall back
    # to the most term-relevant readable snippet.
    best = next((r for r in rows if _looks_like_definition(str(r.get("snippet") or ""))), None)
    if best is None:
        best = max(rows, key=lambda r: int(r.get("query_terms_matched") or 0), default=None)
    if not best:
        return None
    title = str(best.get("title") or "")
    url = str(best.get("url") or "")
    is_ko = language == "ko"
    suffix = f" (출처: {title})" if is_ko and title else (f" (source: {title})" if title else "")

    # Graft the cited web result(s) into the Cloud Brain as real concept nodes,
    # ordering the answer's own source first, and hand the new nodes back so the
    # Local Brain graph can light them up as they are added.
    # Only on-topic rows (the relevance-gated set) may be grafted — never the
    # unrelated pages a full-text search may have returned alongside.
    ordered_rows = [best] + [r for r in rows if r is not best]
    graft = _graft_web_nodes_to_cloud_brain(ordered_rows, language) if provider == "wikipedia" else {}
    grafted_nodes = graft.get("grafted_nodes") or []
    web_graft = {
        "cloud_brain_concepts_added": int(graft.get("concepts_added") or 0),
        "cloud_brain_relations_added": int(graft.get("relations_added") or 0),
        "candidate_store_path": graft.get("candidate_store_path"),
        "production_store_mutated": bool(graft.get("production_store_mutated")),
    } if graft else {}

    # Attribution questions ("who invented X?") get the PERSON, not just a
    # definition — extracted deterministically from the retrieved snippets.
    all_snippets = [str(r.get("snippet") or "") for r in rows]
    person = _extract_attribution(question, all_snippets)
    # The intro extract often omits the founder/inventor (it's deeper in the
    # article). If this is an attribution question and the short snippets didn't
    # yield a person, fetch the full article text once and scan that.
    _rel_now = _detect_attribution_relation(question)
    if not person and _rel_now and "wikipedia.org" in str(url):
        host = "ko.wikipedia.org" if "ko.wikipedia.org" in str(url) else "en.wikipedia.org"
        # Use the CANONICAL page title from the URL path ("엔비디아"), not the search
        # display title ("엔비디아 코퍼레이션") which may not resolve in the API.
        from urllib.parse import unquote

        page_title = unquote(str(url).split("/wiki/")[-1].split("?")[0]).replace("_", " ") or title
        try:
            from app.services.web_search import _wikipedia_extract_for_page, wikipedia_infobox_people

            # 1) deeper prose (inventors/authors often appear below the intro)
            if "ko.wikipedia.org" in str(url):
                full_extract = _wikipedia_extract_for_page(page_title)
                if full_extract:
                    person = _extract_attribution(question, [full_extract])
            # 2) the infobox (founders/inventors that live only in the 설립자 field)
            if not person:
                person = wikipedia_infobox_people(page_title, host=host, relation_key=_rel_now[0])
        except Exception:  # pragma: no cover - network/optional
            person = person
    if person:
        rel = _detect_attribution_relation(question)
        rel_key = rel[0] if rel else "created"
        rel_phrase = rel[1] if rel else "attributed to"
        topic = re.sub(r"^(the|a|an)\s+", "", _first_sentences(title, max_chars=60), flags=re.IGNORECASE) or (title or "It")
        verb_ko = {
            "invented": "발명한", "discovered": "발견한", "wrote": "쓴", "founded": "설립한",
            "painted": "그린", "composed": "작곡한", "directed": "감독한", "built": "지은", "created": "만든",
        }.get(rel_key, "만든")
        # Pick the correct object particle (을/를) by whether the topic ends in a
        # consonant (받침), so it reads "엔비디아를" not "엔비디아을(를)".
        _last = topic[-1] if topic else ""
        _has_batchim = bool(_last) and "가" <= _last <= "힣" and (ord(_last) - 0xAC00) % 28 != 0
        _obj_josa = "을" if _has_batchim else "를"
        attribution = (
            f"{topic}{_obj_josa} {verb_ko} 사람은 {person}입니다."
            if is_ko
            else f"{title or topic} was {rel_phrase} {person}."
        )
        cert = {
            "derivation_kind": "web_attribution_extraction",
            "anchor_concept": {"id": person, "label": person, "match": "web_retrieval"},
            "steps": [{"type": "web_attribution", "source": url or provider, "fact": f"{rel[1] if rel else 'attributed to'} {person}"}],
            "evidence_concepts": [url] if url else [provider],
            "confidence": 0.7,
            "confidence_basis": f"web_attribution:{provider}",
            "guarantees": {"external_llm": False, "fabricated_facts": False, "evidence_grounded": True, "source_cited": True},
        }
        attribution_text = (attribution + suffix).strip()
        _store_web_fact(question, title, attribution_text, url)
        return {
            "answer": attribution_text, "reasoning_certificate": cert, "confidence": 0.7,
            "provider": provider, "source_url": url, "source_title": title,
            "grafted_nodes": grafted_nodes, "web_graft": web_graft,
        }

    answer = _first_sentences(str(best.get("snippet") or ""), max_chars=420)
    if len(answer) < 40:
        return None
    certificate = {
        "derivation_kind": "web_search_grounding",
        "anchor_concept": {"id": title or question[:60], "label": title or question[:60], "match": "web_retrieval"},
        "steps": [
            {"type": "web_source", "source": url or provider, "fact": _first_sentences(str(best.get("snippet") or ""), max_chars=160)},
        ],
        "evidence_concepts": [url] if url else [provider],
        "confidence": 0.72,
        "confidence_basis": f"web_retrieval:{provider}",
        "guarantees": {"external_llm": False, "fabricated_facts": False, "evidence_grounded": True, "source_cited": True},
    }
    answer_text = (answer + suffix).strip()
    _store_web_fact(question, title, answer_text, url)
    return {
        "answer": answer_text,
        "reasoning_certificate": certificate,
        "confidence": 0.72,
        "provider": provider,
        "source_url": url,
        "source_title": title,
        "grafted_nodes": grafted_nodes,
        "web_graft": web_graft,
    }


def _graft_web_nodes_to_cloud_brain(results: list[dict[str, Any]], language: str) -> dict[str, Any]:
    """Add cited web results to the Cloud Brain candidate store as real concepts
    and return the new node descriptors. Never raises (grounding answer must not
    depend on the graft succeeding)."""
    try:
        from app.services.wikipedia_grounded_learning import ingest_web_result

        return ingest_web_result(results, language=language, max_nodes=3)
    except Exception:  # pragma: no cover - graft is best-effort
        return {}


def _is_recent_learning_question(question: str) -> bool:
    lower = question.lower()
    return any(token in question for token in ("최근 학습", "최근 배운", "학습한 개념", "새로 배운")) or (
        "recent" in lower and any(token in lower for token in ("learn", "concept", "memory"))
    )


def _safe_public_concept_label(row: dict[str, Any]) -> str:
    label = str(row.get("canonical_name") or row.get("label") or "").strip()
    if not label:
        labels = row.get("language_labels")
        if isinstance(labels, dict):
            label = str(labels.get("ko") or labels.get("en") or "").strip()
    if not label:
        return ""
    if re.fullmatch(r"[0-9a-f]{10,64}", label, flags=re.IGNORECASE):
        return ""
    if re.fullmatch(r"[0-9a-f]{8}-[0-9a-f-]{20,}", label, flags=re.IGNORECASE):
        return ""
    if label.lower().startswith(("ghost:", "hash:", "cbn_", "payload-vault://")):
        return ""
    if len(label) < 2:
        return ""
    label = re.sub(r"\s+", " ", label).strip(" .,:;!?()[]{}\"'")
    lower = label.lower()
    if lower in {
        "it",
        "this",
        "that",
        "data",
        "the",
        "a",
        "an",
        "one",
        "several",
        "usually",
        "unknown",
        "there",
        "bibliography",
        "references",
        "contents",
        "text",
        "what",
        "guide",
        "library",
        "article",
        "page",
        "home",
        "about",
        "presidents",
        "president-elect",
        "external links",
        "see also",
        "award",
        "recognition",
        "portal",
        "charcoal",
        "ours",
        "man",
        "he",
        "another",
        "stub",
        "interactions",
    }:
        return ""
    if len(label) > 48:
        return ""
    if len(label.split()) > 5:
        return ""
    if any(
        marker in lower
        for marker in (
            " such as ",
            " one of ",
            " not the ",
            " usually ",
            " widely used ",
            " backed financially ",
            " with privacy concerns",
            " can be ",
            " may be ",
            " listed on ",
            " website",
            " online service",
            " public metadata record",
            " bibliography",
            " full-text collection",
            " full text collection",
            " non-profit professional",
            " non profit professional",
            " organized into ",
            " published in partnership",
            " no longer published",
            " co-sponsored by ",
            " co sponsored by ",
            " regarded as ",
            " credited with ",
            " administered by ",
            " no clinical evidence",
            " home to ",
            " estimated to ",
            " jump to ",
            " move to ",
            " edit ",
        )
    ):
        return ""
    if lower.startswith(("listed ", "there ", "this ", "that ", "from ", "according ", "part of ")):
        return ""
    if re.search(r"[,.]", label) and not re.search(r"\b(?:AI|API|SQL|RAG|GraphRAG|SQLite|HTTP|GPU|CPU)\b", label):
        return ""
    has_hangul = bool(re.search(r"[\uac00-\ud7a3]", label))
    has_acronym = bool(re.search(r"\b[A-Z]{2,}\b", label))
    has_title_word = bool(re.search(r"\b[A-Z][a-zA-Z0-9.+#-]{2,}\b", label))
    if not (has_hangul or has_acronym or has_title_word):
        return ""
    return label[:48]


def _augment_recent_learning_context(semantic_context: dict[str, Any]) -> dict[str, Any]:
    store = SemanticCloudStore()
    concepts = list(store.load_concepts().values())
    relations = store.load_relations()
    concepts.sort(
        key=lambda row: (
            str(row.get("updated_at") or row.get("created_at") or ""),
            int(row.get("seen_count") or 0),
        ),
        reverse=True,
    )
    labels: list[str] = []
    seen: set[str] = set()
    for row in concepts:
        label = _safe_public_concept_label(row)
        key = label.lower()
        if label and key not in seen:
            labels.append(label)
            seen.add(key)
        if len(labels) >= 8:
            break
    merged = dict(semantic_context)
    merged["semantic_store_counts"] = {
        "concepts": len(concepts),
        "relations": len(relations),
    }
    if labels:
        merged["concepts"] = labels + [item for item in list(semantic_context.get("concepts") or []) if str(item) not in labels]
        merged["local_coverage"] = semantic_context.get("local_coverage") or "semantic_cloud_growth"
        merged.setdefault("claims", []).append(
            {
                "claim": "Semantic proof store is growing from public web seed metadata.",
                "source_scope": "cloud_proof_store",
                "local_brain_write": False,
            }
        )
        return merged
    merged["local_coverage"] = semantic_context.get("local_coverage") or "semantic_cloud_growth"
    return merged


UNSAFE_DEFAULT_ANSWER_RE = re.compile(
    r"(?:[�占]|ì|ë|í|ð|筌|荑|濡|洹|蹂|留|좊|쾶|ㅽ|"
    r"\b[0-9a-f]{24,}\b|payload-vault://|source_hash|node_id|semantic_projection_id|"
    r"Local Brain|Cloud Brain|Working Memory|Q-Cortex)",
    re.IGNORECASE,
)


def _answer_is_unsafe(answer: str) -> bool:
    text = str(answer or "")
    if UNSAFE_DEFAULT_ANSWER_RE.search(text):
        return True
    if any(term in text for term in ("먼저 의도와 경계", "내부적으로 점검", "내부 점검", "숨겨진 사고", "내적 독백")):
        return True
    monitor = monitor_answer(text)
    return bool(set(monitor.get("issues") or []) & {"encoding_artifact", "internal_trace_leakage", "internal_identifier_leakage"})


def _answer_is_abstention(answer: str) -> bool:
    text = re.sub(r"\s+", " ", str(answer or "").strip().lower())
    if not text:
        return True
    return any(
        marker in text
        for marker in (
            "not have enough verified evidence",
            "verified evidence to answer confidently",
            "not have enough base concepts",
            "not have enough local evidence",
            "not have enough confidently matched evidence",
            "지금 확인된 근거가 부족",
            "확인 가능한 근거가 부족",
            "근거가 부족",
            "단정하기 어렵",
            "설명할 근거가 없",
        )
    )


def _public_evidence_docs(docs: list[dict[str, Any]], *, mode: str) -> list[dict[str, Any]]:
    if mode in {"trace", "research"}:
        return docs
    public_docs: list[dict[str, Any]] = []
    for doc in docs:
        text_blob = " ".join(
            str(doc.get(key) or "")
            for key in ("path", "url", "snippet", "text", "title", "chunk_id", "hash_key", "source_hash")
        )
        if "payload-vault://" in text_blob or re.search(r"\b[0-9a-f]{24,}\b", text_blob, flags=re.IGNORECASE):
            continue
        if UNSAFE_DEFAULT_ANSWER_RE.search(text_blob):
            continue
        public_docs.append(
            {
                "title": doc.get("title") or doc.get("doc_id") or "source",
                "url": doc.get("url") or doc.get("path"),
                "snippet": doc.get("snippet") or doc.get("text") or "",
                "score": doc.get("score"),
            }
        )
    return public_docs[:6]


def _compact_exchange_trace(exchange: dict[str, Any] | None) -> dict[str, Any]:
    if not exchange:
        return {
            "enabled": False,
            "states": [],
            "local": "not_run",
            "cloud": "not_run",
            "web_atlas": "not_run",
            "working_memory_nodes": 0,
            "auto_detached": False,
            "local_write": False,
            "cloud_promotion": "manual_required",
        }
    chunk = exchange.get("cloud_graph_chunk") if isinstance(exchange.get("cloud_graph_chunk"), dict) else {}
    evidence = exchange.get("evidence_bundle") if isinstance(exchange.get("evidence_bundle"), dict) else {}
    working_memory = exchange.get("working_memory") if isinstance(exchange.get("working_memory"), dict) else {}
    promotion = exchange.get("promotion") if isinstance(exchange.get("promotion"), dict) else {}
    return {
        "enabled": True,
        "states": list(exchange.get("states") or []),
        "local": "hit" if "local_hit" in (exchange.get("states") or []) else "miss",
        "cloud": "hit" if chunk else "miss",
        "cloud_chunk_id": chunk.get("chunk_id"),
        "cloud_nodes": len(chunk.get("semantic_nodes") or []),
        "cloud_relations": len(chunk.get("relations") or []),
        "web_atlas": evidence.get("extraction_status") if evidence else "not_requested",
        "working_memory_nodes": int(working_memory.get("temporary_context_count") or 0),
        "auto_detached": bool(working_memory.get("auto_detached")),
        "pinned": bool(working_memory.get("pinned")),
        "local_write": False,
        "cloud_promotion": promotion.get("cloud_promotion") or "manual_required",
        "candidate_pending": bool(promotion.get("candidate_pending")),
        "fake_counts": False,
        "pair_edges_sent": 0,
    }


def _augment_semantic_context_with_exchange(semantic_context: dict[str, Any], exchange: dict[str, Any] | None) -> dict[str, Any]:
    if not exchange or not isinstance(exchange.get("cloud_graph_chunk"), dict):
        return semantic_context
    chunk = exchange["cloud_graph_chunk"]
    labels = [
        str(node.get("label") or node.get("concept_id") or node.get("id"))
        for node in list(chunk.get("semantic_nodes") or [])
        if isinstance(node, dict)
    ]
    if not labels:
        return semantic_context
    merged = dict(semantic_context)
    existing = [str(item) for item in list(merged.get("concepts") or [])]
    merged["concepts"] = labels + [item for item in existing if item not in labels]
    merged["local_coverage"] = merged.get("local_coverage") or "cloud_chunk_attached"
    evidence = list(merged.get("evidence") or [])
    evidence.append(
        {
            "title": "Temporary Cloud graph chunk",
            "snippet": ", ".join(labels[:6]),
            "source_scope": "cloud",
            "temporary": True,
            "local_brain_write": False,
        }
    )
    merged["evidence"] = evidence
    return merged


def _base_brain_payload(
    request: AtanorChatRequest,
    *,
    question: str,
    language: str,
    rag_result: dict[str, Any],
    exchange: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    base = answer_with_base_brain(
        question,
        language=language,  # type: ignore[arg-type]
        audience_level=request.audience_level,  # type: ignore[arg-type]
        mode=request.mode,  # type: ignore[arg-type]
    )
    if int(base.get("semantic_context_count") or 0) <= 0 and not str(base.get("answer") or "").strip():
        return None
    compact_trace = {
        "local_coverage": "base_brain",
        "base_brain": {
            "semantic_context_count": int(base.get("semantic_context_count") or 0),
            "surface_candidate_count": int(base.get("surface_candidate_count") or 0),
            "local_user_brain_used": False,
        },
        "semantic_cloud_graph": {
            "attached_nodes": 0,
            "evidence_docs": 0,
        },
        "surface_graph": {
            "construction_families": list((base.get("compact_trace") or {}).get("selected_surface_candidates") or []),
            "discourse_moves": [],
        },
        "q_cortex": {
            "used": bool(base.get("q_cortex_used")),
            "run_id": (base.get("trace") or {}).get("q_cortex_run_id"),
            "real_quantum_hardware_used": False,
        },
        "working_memory": {
            "temporary_context": bool(exchange and (exchange.get("cloud_graph_chunk") or exchange.get("evidence_bundle"))),
            "local_brain_write": False,
        },
        "local_cloud_exchange": _compact_exchange_trace(exchange),
        "confidence": "medium" if base.get("answer") else "low",
    }
    payload = {
        "answer": base["answer"],
        "language": language,
        "confidence": float(base.get("confidence") or 0.64),
        "default_trace_visible": False,
        "trace": compact_trace if request.include_trace or request.mode in {"trace", "research"} else None,
        "compact_trace": compact_trace,
        "research_trace": {
            "base_brain": base,
            "rag_retrieval_trace": rag_result.get("retrieval_trace", {}),
        } if request.mode == "research" else None,
        "evidence_docs": [],
        "surface_plan": {
            "plan_id": None,
            "intent": (base.get("trace") or {}).get("intent"),
            "construction_families": compact_trace["surface_graph"]["construction_families"],
            "q_cortex_used": base.get("q_cortex_used"),
            "q_cortex_run_id": (base.get("trace") or {}).get("q_cortex_run_id"),
        },
        "answer_engine": {
            "name": "ATANOR Base Brain + Surface Repair",
            "semantic_plane": "Seed Graph / Base Brain",
            "surface_plane": "Surface Brain",
            "external_llm": False,
            "external_sllm": False,
            "local_brain_write": False,
            "trace_hidden_by_default": True,
            "q_cortex_optional": True,
            "network_barrier": "sealed_for_generation",
        },
        **_flags(),
    }
    return {"state": "completed", "result": payload, **_flags()}


_FRONTEND_ALLOWED_BASES = {
    "local_corpus_construction_transition_model",
    "semantic_grounded_conversation_router_v0",
    "semantic_cloud_graph_surface_brain_v0",
    "base_brain_seed_graph_surface_v0",
}


def _looks_like_abstention(text: str) -> bool:
    low = str(text or "").lower()
    return (
        "enough" in low
        or "confidently yet" in low
        or "부족" in str(text)
        or "단정하기 어렵" in str(text)
    )


def _engine_passes_frontend_gate(engine: dict[str, Any]) -> bool:
    """Mirror the web client's isAsmConversationPayload honesty gate. An answer
    that cannot prove it is graph-derived (allowed basis + all honesty flags
    False) is not rendered by the dashboard, so we must demote it."""
    if str(engine.get("generation_basis") or "") not in _FRONTEND_ALLOWED_BASES:
        return False
    for flag in (
        "external_llm", "external_sllm", "external_llm_used", "external_sllm_used",
        "rule_based_answer_used", "internal_trace_exposed", "local_brain_write",
        "production_store_mutated", "candidate_promotion",
    ):
        if engine.get(flag) is not False:
            return False
    return True


def _demote_low_quality_to_base_brain(response: dict[str, Any], request: AtanorChatRequest) -> dict[str, Any]:
    """Final quality gate across ALL answer paths: replace the surfaced answer
    with the clean Base Brain answer (or Base Brain's honest abstention) when it
    is cross-language / pasted / citation-noise, OR when its engine cannot prove
    graph-derived honesty (so the dashboard's render gate would reject it). Keeps
    the dashboard from showing raw web snippets \u2014 and from silently dropping good
    answers whose provenance metadata is incomplete."""
    result = response.get("result")
    if not isinstance(result, dict):
        return response
    answer = str(result.get("answer") or "")
    if not answer.strip():
        return response
    question = request.question_text()
    language = request.language or ("ko" if any("\uac00" <= char <= "\ud7a3" for char in question) else "en")
    engine_now = result.get("answer_engine") if isinstance(result.get("answer_engine"), dict) else {}
    answer_is_abstention = _looks_like_abstention(answer)
    base = answer_with_base_brain(
        question, language=language, audience_level=request.audience_level, mode="default"  # type: ignore[arg-type]
    )
    base_answer = str(base.get("answer") or "").strip()
    base_conf = float(base.get("confidence") or 0.0)
    grounding_source = str(engine_now.get("grounding_source") or "")
    # A loosely-matched verified-store paste yields to a Base-Brain answer that
    # actually NAMES the concept (conf >= 0.85): the precise graph answer beats a
    # tangential pasted fact (e.g. "AI 학습과 AI 추론" → a cognitive-science snippet).
    prefer_base = (
        grounding_source == "verified_store_v0_readonly"
        and base_conf >= 0.85
        and not _looks_like_abstention(base_answer)
    )
    # Demote when: the answer is cross-language/pasted/citation-noise, OR its
    # engine can't prove graph-derived honesty (would fail the dashboard render
    # gate), OR the live path abstained (the grounded path only hand-authors a few
    # topics, so it abstains on concepts Base Brain actually knows, e.g. Docker),
    # OR a verified-store paste should yield to a confident Base-Brain naming.
    if (
        not _grounded_answer_low_quality(answer, language)
        and _engine_passes_frontend_gate(engine_now)
        and not answer_is_abstention
        and not prefer_base
    ):
        return response
    if not base_answer:
        return response
    # Don't swap one honest abstention for another: if the live path abstained and
    # Base Brain also has nothing concrete, keep the original.
    if answer_is_abstention and _looks_like_abstention(base_answer):
        return response
    result["answer"] = base_answer
    result["answer_kind"] = "base_brain_after_low_quality_grounding"
    result["confidence"] = float(base.get("confidence") or 0.5)
    result["scene_grounding"] = base.get("scene_grounding")
    result["reasoning_certificate"] = base.get("reasoning_certificate")
    result["scene_choreography"] = None
    result["visual_scene_plan"] = None
    result["splatra_scene_plan"] = None
    engine = result.get("answer_engine")
    if not isinstance(engine, dict):
        engine = {}
    engine["generation_basis"] = "base_brain_seed_graph_surface_v0"
    for flag in (
        "external_llm", "external_sllm", "external_llm_used", "external_sllm_used",
        "rule_based_answer_used", "internal_trace_exposed", "local_brain_write",
        "production_store_mutated", "candidate_promotion",
    ):
        engine[flag] = False
    result["answer_engine"] = engine
    return response


def _concepts_for_fold(question: str) -> list[dict[str, Any]]:
    """Real base-brain concepts (+ relation neighbours) matched to the query."""

    pack = load_base_brain_pack()
    matched = get_semantic_context(question, pack, limit=24)
    concepts: list[dict[str, Any]] = []
    for concept in matched:
        score = float(concept.get("match_score") or 0.0)
        hop = 0 if score >= 4.0 else (1 if score >= 1.0 else 2)
        importance = min(1.0, max(0.1, 0.3 + score * 0.12))
        concepts.append({**concept, "importance": importance, "hop_depth": hop})
    return concepts


_SHOW_FOLD_MARKERS_KO = ("작동방식", "작동 방식", "어떻게 작동", "어떻게 동작", "구조 보여", "구조를 보여", "생각을 보여", "생각하는 걸 보여", "3d로 보여", "3d로 펼", "접히는 걸 보여")
_SHOW_FOLD_MARKERS_EN = ("show how you work", "show how you think", "how do you work", "how do you think", "show your structure", "think in 3d", "show me your reasoning in 3d", "visualize your")


# "작동/동작" markers are ambiguous: "너 어떻게 작동해?" is a self-demo request, but
# "백신은 어떻게 작동해?" is a knowledge question. These require a self-reference; the
# other markers (구조/생각/3D 보여) are inherently about showing ATANOR's own structure.
_FOLD_MARKERS_NEED_SELF = ("어떻게 작동", "어떻게 동작", "작동방식", "작동 방식")
_SELF_REFERENCE_RE = re.compile(
    r"(너\b|너는|너의|넌|네\b|니가|당신|ATANOR|아타노르|atanor|자기\s*자신|스스로|자네|"
    r"\byou\b|\byour\b|yourself)",
    re.IGNORECASE,
)


def _is_show_fold_request(question: str) -> bool:
    text = re.sub(r"\s+", " ", str(question or "").strip().lower())
    if not text:
        return False
    if any(marker in text for marker in _SHOW_FOLD_MARKERS_EN):
        return True
    raw = str(question or "")
    has_self = bool(_SELF_REFERENCE_RE.search(raw))
    for marker in _SHOW_FOLD_MARKERS_KO:
        if marker not in raw:
            continue
        # Ambiguous "작동" markers only fold when the subject is ATANOR itself.
        if marker in _FOLD_MARKERS_NEED_SELF and not has_self:
            continue
        return True
    return False


def _is_local_graph_request(question: str) -> bool:
    raw = str(question or "")
    lowered = raw.lower()
    return ("로컬 그래프" in raw or "로컬그래프" in raw or "local graph" in lowered) and (
        "파동" in raw or "보여" in raw or "알려" in raw or "wave" in lowered or "show" in lowered
    )


def _atanor_self_concepts() -> list[dict[str, Any]]:
    """Real base-brain concepts that describe ATANOR itself (for the self-fold)."""

    pack = load_base_brain_pack()
    seed = "ATANOR 구조 로컬 브레인 클라우드 브레인 graph hub atlas brain graph 추론 그래프"
    matched = get_semantic_context(seed, pack, limit=24)
    concepts: list[dict[str, Any]] = []
    for concept in matched:
        score = float(concept.get("match_score") or 0.0)
        hop = 0 if score >= 4.0 else (1 if score >= 1.0 else 2)
        concepts.append({**concept, "importance": min(1.0, max(0.2, 0.4 + score * 0.1)), "hop_depth": hop})
    return concepts


def _local_graph_concepts() -> list[dict[str, Any]]:
    """ALL base-brain concepts (the local knowledge graph) as fold inputs."""

    pack = load_base_brain_pack()
    concepts: list[dict[str, Any]] = []
    for concept in pack.semantic_graph.get("concepts", []) or []:
        confidence = float(concept.get("confidence", 0.75) or 0.75)
        concepts.append({**concept, "importance": min(1.0, max(0.2, 0.4 + confidence * 0.4)), "hop_depth": 0})
    return concepts


def _build_fold_scene(question: str, concepts: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    """Fold a concept set and assemble a renderable 3D scene (read-only).

    Defaults to ATANOR's self-knowledge; pass `concepts` to fold an explicit
    graph (e.g. the whole local knowledge graph).
    """

    concepts = concepts if concepts is not None else _atanor_self_concepts()
    if not concepts:
        return None
    emotion = None
    try:
        snapshot = EVENT_BUS.engine.snapshot().to_dict()
        emotion = {**snapshot, "provenance": "neural_emotion:snapshot"}
    except Exception:  # pragma: no cover - optional
        emotion = None
    raw_nodes, edges = build_field_inputs(question, concepts=concepts, emotion=emotion)
    if not raw_nodes:
        return None
    label_by_id = {node["node_id"]: node.get("label") or node["node_id"] for node in raw_nodes}
    field = build_state_field(question, raw_nodes)
    folded = fold_state(field, edges=edges, capture_trajectory=True, trajectory_frames=48)
    index = {node.node_id: i for i, node in enumerate(folded.nodes)}
    pair_rep = build_pair_representation(field, edges=edges)
    scene_edges = [
        {
            "i": index[pair.i],
            "j": index[pair.j],
            "intf": round(pair.interference_energy, 4),
            "constructive": bool(pair.constructive),
        }
        for pair in pair_rep.pairs
        if pair.has_edge and pair.i in index and pair.j in index
    ]
    scene_nodes = [
        {
            "id": node.node_id,
            "label": label_by_id.get(node.node_id, node.node_id),
            "source_type": node.source_type,
            "position": list(node.position),
            "radius": round(node.radius, 4),
            "coherence": round(node.coherence, 4),
            # real wave parameters → renderer computes the live interference field
            "amplitude": round(node.amplitude, 5),
            "phase": round(node.phase, 5),
            "frequency": round(node.frequency, 2),
        }
        for node in folded.nodes
    ]
    return {
        "render_kind": "phase_holographic_fold_v0",
        "nodes": scene_nodes,
        "edges": scene_edges,
        "core": folded_core(folded, top_k=5),
        "trajectory": list(folded.trajectory),
        "meta": {
            "active_node_count": folded.metadata.get("active_node_count"),
            "global_coherence": folded.metadata.get("global_coherence"),
            "fold_timing_ms": folded.metadata.get("fold_timing_ms"),
            "trajectory_frame_count": folded.metadata.get("trajectory_frame_count"),
            "mean_radius_by_source": folded.metadata.get("mean_radius_by_source"),
            "original_brain_state_mutated": False,
            "fold_driver_mode": "compare_mode",
            "note": "ATANOR 내부 상태(검증 개념·후보·감정)를 위상 홀로그래픽 폴딩으로 접은 실제 구조입니다. 답변을 구동하지는 않습니다.",
        },
    }


@router.get("/api/holographic-fold/local")
async def holographic_fold_local() -> dict[str, Any]:
    """Fold the whole local knowledge graph (real engine) → renderable scene."""

    try:
        scene = _build_fold_scene("local knowledge graph", concepts=_local_graph_concepts())
    except Exception:  # pragma: no cover - never break the dashboard
        scene = None
    return {"folded_state_field": scene, "render_fold_scene": bool(scene)}


def _attach_holographic_fold_trace(response: dict[str, Any], request: AtanorChatRequest) -> dict[str, Any]:
    """Attach a compare_mode Phase-Holographic-Fold trace (hidden, read-only).

    The fold's recommended core is compared to the answer's own evidence and
    LOGGED only. It never changes the answer (compare_mode, spec §7). Fully
    defensive: any failure leaves the response untouched.
    """

    try:
        result = response.get("result")
        if not isinstance(result, dict) or not result.get("answer"):
            return response
        question = request.question_text()
        if not question:
            return response

        # VISUALIZATION commands ("local graph waves" / "show how ATANOR works")
        # are handled FIRST: they fold an explicit graph (the whole local graph or
        # the self-concepts) and must not be blocked by the compare-trace concept
        # gate below, which can be empty for a pure render request.
        local_req = _is_local_graph_request(question)
        if local_req or _is_show_fold_request(question):
            scene = (
                _build_fold_scene(question, concepts=_local_graph_concepts())
                if local_req
                else _build_fold_scene(question)
            )
            if scene:
                if local_req:
                    scene["render_kind"] = "local_graph_wave"
                result["folded_state_field"] = scene
                result["render_fold_scene"] = True
                # This is a render command, not a knowledge question — the scene is
                # the real content. Replace any tangential grounded paste with a
                # short, data-aware caption describing exactly what is shown.
                is_ko = bool(re.search(r"[가-힣]", question))
                node_count = len(scene.get("nodes") or [])
                if local_req:
                    result["answer"] = (
                        f"실시간 로컬 지식 그래프 {node_count}개 노드를 불러와, 각 노드의 파동이 퍼지며 겹치는 실제 간섭장을 보여드립니다."
                        if is_ko
                        else f"Loading the live local knowledge graph ({node_count} nodes) and rendering the real superposed wave-interference field of every node."
                    )
                else:
                    result["answer"] = (
                        "ATANOR의 내부 상태(검증 개념·후보·감정)를 위상 홀로그래픽 폴딩으로 3D 구조로 접어 보여드립니다."
                        if is_ko
                        else "Folding ATANOR's internal state (verified concepts, candidates, emotion) into a 3D phase-holographic structure."
                    )

        concepts = _concepts_for_fold(question)
        if not concepts:
            return response
        emotion = None
        try:
            snapshot = EVENT_BUS.engine.snapshot().to_dict()
            emotion = {**snapshot, "provenance": "neural_emotion:snapshot"}
        except Exception:  # pragma: no cover - optional emotion source
            emotion = None
        raw_nodes, edges = build_field_inputs(question, concepts=concepts, emotion=emotion)
        if not raw_nodes:
            return response
        field = build_state_field(question, raw_nodes)
        folded = fold_state(field, edges=edges)

        # resolve the answer's evidence (concept ids OR display names) to node ids
        resolver: dict[str, str] = {}
        for node in field.nodes:
            resolver[node.node_id.casefold()] = node.node_id
            resolver[node.label.casefold()] = node.node_id
            if node.node_id.startswith("concept:"):
                resolver[node.node_id.split("concept:", 1)[1].casefold()] = node.node_id
        certificate = result.get("reasoning_certificate")
        certificate = certificate if isinstance(certificate, dict) else {}
        evidence_raw = list(certificate.get("evidence_concepts") or [])
        anchor = certificate.get("anchor_concept")
        if anchor:
            evidence_raw.append(anchor)

        def _evidence_key(item: Any) -> str:
            # evidence entries may be plain ids or concept dicts ({id, label, ...})
            if isinstance(item, dict):
                item = item.get("id") or item.get("concept_id") or item.get("canonical_name") or ""
            return str(item).strip().casefold()

        evidence_ids = []
        for item in evidence_raw:
            key = _evidence_key(item)
            if not key:
                continue
            evidence_ids.append(resolver.get(key) or resolver.get(f"concept:{key}") or f"concept:{key}")

        report = compare_fold_to_answer(folded, evidence_ids)
        report["folded_global_coherence"] = folded.metadata.get("global_coherence")
        report["fold_timing_ms"] = folded.metadata.get("fold_timing_ms")
        report["mean_radius_by_source"] = folded.metadata.get("mean_radius_by_source")

        compact = result.setdefault("compact_trace", {})
        if isinstance(compact, dict):
            compact["holographic_fold"] = report
        engine = result.setdefault("answer_engine", {})
        if isinstance(engine, dict):
            engine["phase_holographic_fold_attached"] = True
            engine["fold_driver_mode"] = "compare_mode"
            engine["fold_answer_source"] = "hidden_trace_only"

    except Exception:  # pragma: no cover - never break the answer path
        return response
    return response


@router.post("/api/chat/atanor")
async def chat_atanor(request: AtanorChatRequest) -> dict[str, Any]:
    question = request.question_text()
    language = request.language or ("ko" if any("가" <= c <= "힣" for c in (question or "")) else "en")
    # A context-resolved query so a follow-up ("where is it?") carries the prior
    # topic into web grounding / recall.
    try:
        web_query = build_conversation_context(question, request.conversation_context).contextual_query or question
    except Exception:  # pragma: no cover - defensive
        web_query = question
    # Local Brain cumulative learning: accumulate user prefs/info from this turn.
    _accumulate_user_facts(question, language)
    recall = _local_brain_recall(question, language)
    # "Living creature" sense: answer questions about ATANOR's own live state by
    # pulling from every subsystem at once.
    self_state = _self_state_answer(question, language)
    # Self-model: who ATANOR is and how it works, answered from a stable curated
    # self-knowledge base (not the web). "너 이름이 뭐야" / "어떻게 작동해" land here.
    self_knowledge = answer_self_question(question, language) if not self_state else None
    # Deterministic multi-hop comparison ("A와 B 중 누가 먼저 태어났어?"): two real
    # lookups + a deterministic compare, no LLM. None when not a comparison or when
    # it can't extract both values (abstains, never guesses).
    # Deterministic Reasoning VM (arithmetic / counting word problems) — fully
    # offline: no LLM, no GPU, no web. Highest-priority reasoner; runs even when
    # web search is off, and pre-empts the web-dependent reasoners below.
    reasoning_vm = None
    if not (self_state or self_knowledge or recall):
        try:
            from app.services.reasoning_vm import solve_reasoning

            reasoning_vm = solve_reasoning(question, language)
        except Exception:  # pragma: no cover - reasoner must never break chat
            reasoning_vm = None
    comparison = None
    chained = None
    if request.web_search and not (self_state or self_knowledge or recall or reasoning_vm):
        try:
            from app.services.comparison_reasoner import answer_comparison

            comparison = answer_comparison(question, language)
        except Exception:  # pragma: no cover - reasoner must never break chat
            comparison = None
        if not comparison:
            try:
                from app.services.chained_reasoner import answer_chain

                chained = answer_chain(question, language)
            except Exception:  # pragma: no cover - reasoner must never break chat
                chained = None

    # Attribution intercept: "누가 X를 발명/창립했어?" must answer with the PERSON, not
    # a definition. The grounded-conversation path can't do this, so route confirmed
    # attribution questions through the rescue's deterministic person extraction
    # (prose + infobox). Only overrides when a real name is found; else the normal
    # answer (definition) stands.
    attribution_answer = None
    if request.web_search and not (self_state or self_knowledge or recall or reasoning_vm) and _detect_attribution_relation(question):
        try:
            _attrib = await _web_grounded_rescue(web_query, language)
            if _attrib and _attrib.get("reasoning_certificate", {}).get("derivation_kind") == "web_attribution_extraction":
                attribution_answer = _attrib
        except Exception:  # pragma: no cover - network/optional
            attribution_answer = None

    response = _demote_low_quality_to_base_brain(await _chat_atanor_dispatch(request), request)
    response = _attach_holographic_fold_trace(response, request)

    if self_state and isinstance(response.get("result"), dict):
        result = response["result"]
        result["answer"] = self_state["answer"]
        result["reasoning_certificate"] = self_state["reasoning_certificate"]
        result["confidence"] = self_state["confidence"]
        result["answer_kind"] = "atanor_self_sense"
        result["can_speak"] = True

    # Self-model answer (name / how I work / what I am) — authoritative over the
    # public engine, which cannot know ATANOR's own identity.
    if self_knowledge and isinstance(response.get("result"), dict):
        result = response["result"]
        result["answer"] = self_knowledge["answer"]
        result["reasoning_certificate"] = self_knowledge["reasoning_certificate"]
        result["confidence"] = self_knowledge["confidence"]
        result["answer_kind"] = "atanor_self_knowledge"
        result["can_speak"] = True

    # Reasoning VM answer (math / counting word problem) — authoritative,
    # deterministic, offline. Highest priority over the web-grounded engine.
    if reasoning_vm and isinstance(response.get("result"), dict):
        result = response["result"]
        result["answer"] = reasoning_vm["answer"]
        result["reasoning_certificate"] = reasoning_vm["reasoning_certificate"]
        result["confidence"] = reasoning_vm["confidence"]
        result["answer_kind"] = "reasoning_vm"
        result["can_speak"] = True
        # Experimental answer-interface surface (formula / GeoGebra-like figure).
        if reasoning_vm.get("answer_visual"):
            result["answer_visual"] = reasoning_vm["answer_visual"]

    # Attribution answer (who founded/invented/painted X) — authoritative over a
    # definition for a "who" question.
    if attribution_answer and isinstance(response.get("result"), dict):
        result = response["result"]
        result["answer"] = attribution_answer["answer"]
        result["reasoning_certificate"] = attribution_answer["reasoning_certificate"]
        result["confidence"] = attribution_answer["confidence"]
        result["answer_kind"] = "web_attribution"
        result["can_speak"] = True
        if attribution_answer.get("source_url"):
            result["source_url"] = attribution_answer["source_url"]
            result["source_title"] = attribution_answer.get("source_title")

    # Multi-hop comparison answer — authoritative over the single-fact engine.
    if comparison and isinstance(response.get("result"), dict):
        result = response["result"]
        result["answer"] = comparison["answer"]
        result["reasoning_certificate"] = comparison["reasoning_certificate"]
        result["confidence"] = comparison["confidence"]
        result["answer_kind"] = "comparison_reasoning"
        result["can_speak"] = True
        if comparison.get("source_url"):
            result["render_iframe"] = {"url": comparison["source_url"], "title": comparison.get("source_title") or question[:60]}

    # Chained (2-hop) reasoning answer — authoritative over the single-fact engine.
    if chained and isinstance(response.get("result"), dict):
        result = response["result"]
        result["answer"] = chained["answer"]
        result["reasoning_certificate"] = chained["reasoning_certificate"]
        result["confidence"] = chained["confidence"]
        result["answer_kind"] = "chained_reasoning"
        result["can_speak"] = True
        if chained.get("source_url"):
            result["render_iframe"] = {"url": chained["source_url"], "title": chained.get("source_title") or question[:60]}

    # Web-grounded rescue (outermost): if the final answer is still an abstention
    # from ANY internal path, ground it from a real cited web source — regardless
    # of the web_search toggle. A factual question must not dead-end on "근거가
    # 부족" just because the client forgot to flip a switch; genuinely unanswerable
    # questions still abstain (the rescue returns None and the abstention stays).
    if not (self_state or self_knowledge or comparison or chained or recall or reasoning_vm) and isinstance(response.get("result"), dict):
        result = response["result"]
        ans = str(result.get("answer") or "")
        if not ans or _answer_is_abstention(ans):
            rescue = await _web_grounded_rescue(web_query, language)
            if rescue:
                result["answer"] = rescue["answer"]
                result["reasoning_certificate"] = rescue["reasoning_certificate"]
                result["confidence"] = rescue["confidence"]
                result["answer_kind"] = "web_unreachable" if rescue.get("web_unreachable") else "web_search_grounded"
                result["web_search_provider"] = rescue["provider"]
                result["can_speak"] = True
                # New Cloud Brain nodes grafted from the web result, handed to the
                # Local Brain graph so it can light them up as they appear.
                if rescue.get("grafted_nodes"):
                    result["web_grafted_nodes"] = rescue["grafted_nodes"]
                    result["web_graft"] = rescue.get("web_graft") or {}
                # The agent surfaces the source document on its own — the dashboard
                # opens it in the iframe stage (orb slides aside).
                if rescue.get("source_url"):
                    result["render_iframe"] = {"url": rescue["source_url"], "title": rescue.get("source_title") or question[:60]}

    # If the user asked ATANOR to recall something about THEM and the Local Brain
    # knows it, that private memory is authoritative — the public engine cannot
    # know the user's name/preferences, so override its answer.
    if recall and isinstance(response.get("result"), dict):
        result = response["result"]
        result["answer"] = recall["answer"]
        result["reasoning_certificate"] = recall["reasoning_certificate"]
        result["confidence"] = recall["confidence"]
        result["answer_kind"] = "local_brain_memory_recall"
        result["can_speak"] = True

    # No local answer and not already grounded — surface a fact ATANOR looked up
    # on the web earlier (it remembers what it learned, even with web search off).
    if isinstance(response.get("result"), dict):
        result = response["result"]
        ans = str(result.get("answer") or "")
        if (not ans or _answer_is_abstention(ans)) and result.get("answer_kind") not in (
            "web_search_grounded", "web_unreachable", "local_brain_memory_recall", "atanor_self_sense"
        ):
            cached = _recall_web_fact(web_query)
            if cached:
                result["answer"] = cached["answer"]
                result["reasoning_certificate"] = cached["reasoning_certificate"]
                result["confidence"] = cached["confidence"]
                result["answer_kind"] = "local_web_fact_recall"
                result["web_search_provider"] = "local_web_memory"
                result["can_speak"] = True

    # Graft web-sourced evidence into the Cloud Brain as real nodes and hand the
    # new nodes to the Local Brain graph — for ANY path that grounded the answer
    # on the web (RAG conversation grounding OR the abstention rescue). The orb
    # answer and these glowing new nodes come from the same retrieved evidence.
    answer_kind_now = str((response.get("result") or {}).get("answer_kind") or "")
    # A self/identity/personal answer (ATANOR about itself, base-brain identity, a
    # demoted low-quality grounding, or a Local Brain recall) is NOT a web lookup —
    # never graft web nodes or open a source page for it ("너 이름이 뭐야" must not
    # surface a stranger's Wikipedia page).
    answer_is_self_or_local = bool(self_state or recall) or any(
        marker in answer_kind_now
        for marker in ("self", "atanor", "base_brain", "local", "low_quality", "unreachable")
    )
    if request.web_search and not answer_is_self_or_local and isinstance(response.get("result"), dict):
        result = response["result"]
        ans = str(result.get("answer") or "")
        if ans and not _answer_is_abstention(ans) and not result.get("web_grafted_nodes"):
            web_docs = [
                doc for doc in (result.get("evidence_docs") or [])
                if isinstance(doc, dict) and "wikipedia.org" in str(doc.get("url") or "")
            ]
            if web_docs:
                graft = _graft_web_nodes_to_cloud_brain(web_docs, language)
                if graft.get("grafted_nodes"):
                    result["web_grafted_nodes"] = graft["grafted_nodes"]
                    result["web_graft"] = {
                        "cloud_brain_concepts_added": int(graft.get("concepts_added") or 0),
                        "cloud_brain_relations_added": int(graft.get("relations_added") or 0),
                        "candidate_store_path": graft.get("candidate_store_path"),
                        "production_store_mutated": bool(graft.get("production_store_mutated")),
                    }

    # Explicit "search / open / show me X" → the agent opens the iframe stage of
    # its own accord (the dashboard auto-renders it; orb slides aside).
    if isinstance(response.get("result"), dict) and not response["result"].get("render_iframe"):
        intent_iframe = _render_iframe_for_intent(question, language)
        if intent_iframe:
            response["result"]["render_iframe"] = intent_iframe

    # Dashboard control: the orb obeys layout instructions ("창 닫아") by emitting a
    # directive the frontend executes. A control instruction is never also a search.
    directive = _dashboard_directive_for(question)
    if directive and isinstance(response.get("result"), dict):
        response["result"]["dashboard_directive"] = directive
        if directive.get("action") == "close_window":
            for key in ("render_iframe", "render_iframe_tabs"):
                response["result"].pop(key, None)

    # Pick ONE primary answer modality so the dashboard renders a single thing —
    # a readable document (iframe), a particle scene, or plain text — instead of
    # stacking unrecognisable particles. A web-grounded factual/entity lookup
    # ("손흥민이 누구야") opens its source page; a visual/physics question keeps its
    # particle scene; everything else is text.
    if isinstance(response.get("result"), dict) and not (directive and directive.get("action") == "close_window"):
        response["result"] = _decide_answer_modality(response["result"], question)
    return response


_VISUAL_SCENE_CUE_RE = re.compile(
    r"(떨어|낙하|중력|궤도|움직|이동|회전|충돌|흐르|퍼지|파동|간섭|시각|보여|그려|장면|"
    r"fall|drop|gravity|orbit|motion|move|rotat|collide|wave|interfere|visual|show me|draw|scene)",
    re.IGNORECASE,
)

# The orb has authority over the dashboard surface. The user can instruct it in
# natural language; each directive is acted on by the frontend (no buttons).
_CLOSE_WINDOW_RE = re.compile(
    r"((창|탭|페이지|문서|화면|이거|그거|이걸|그걸|window|tab|page|it)\s*\S{0,5}(닫|꺼|치워|없애|지워|close|hide|dismiss))"
    r"|^\s*(창\s*)?(닫아(줘)?|닫어|꺼(줘)?|치워(줘)?|없애|닫기|close( it)?|dismiss)\s*$",
    re.IGNORECASE,
)
_NEW_TAB_RE = re.compile(r"(새\s*(탭|창)|탭\s*(추가|열어)|new\s+tab|open\s+(a\s+)?tab)", re.IGNORECASE)


def _dashboard_directive_for(question: str) -> dict[str, Any] | None:
    """Map a natural-language dashboard instruction to a control directive the
    orb executes on the surface (close/dismiss the document window, etc.)."""
    text = (question or "").strip()
    if not text:
        return None
    if _CLOSE_WINDOW_RE.search(text):
        return {"action": "close_window"}
    return None


def _decide_answer_modality(result: dict[str, Any], question: str) -> dict[str, Any]:
    """Resolve a single primary modality and prune the others.

    iframe (document) wins for web-grounded entity/factual lookups; a particle
    scene is kept only for explicitly visual/physical questions; otherwise text.
    """
    grafted = result.get("web_grafted_nodes") or []
    wants_visual = bool(_VISUAL_SCENE_CUE_RE.search(question or ""))

    # A web-grounded entity lookup with no explicit iframe yet → open its source.
    if grafted and not result.get("render_iframe") and not wants_visual:
        primary = grafted[0] if isinstance(grafted[0], dict) else {}
        src = str(primary.get("source_url") or "")
        if src:
            result["render_iframe"] = {"url": src, "title": str(primary.get("label") or question[:60])}

    scene_keys = (
        "scene_choreography", "splatra_scene_plan", "splatra_command_sequence",
        "splatra_interactive_scene_analysis", "splatra_cartridge_queue",
        "splatra_sidecar_dispatch", "visual_scene_plan", "render_fold_scene",
        "folded_state_field",
    )
    has_scene = any(result.get(key) for key in scene_keys)

    if result.get("render_iframe") and not wants_visual:
        result["answer_modality"] = "iframe"
        # Open the answer's source plus its related grafted pages as browser-style
        # tabs in one window.
        tabs: list[dict[str, str]] = []
        seen: set[str] = set()
        primary = result["render_iframe"]
        primary_url = str(primary.get("url") or "")
        if primary_url:
            tabs.append({"url": primary_url, "title": str(primary.get("title") or "")})
            seen.add(primary_url)
        for node in grafted:
            if not isinstance(node, dict):
                continue
            url = str(node.get("source_url") or "")
            if url and url not in seen:
                tabs.append({"url": url, "title": str(node.get("label") or "")})
                seen.add(url)
            if len(tabs) >= 5:
                break
        if len(tabs) > 1:
            result["render_iframe_tabs"] = tabs
        # Don't render a particle scene behind the document.
        for key in scene_keys:
            result.pop(key, None)
    elif wants_visual and has_scene:
        result["answer_modality"] = "particle_scene"
        result.pop("render_iframe", None)
    elif has_scene and not result.get("render_iframe"):
        result["answer_modality"] = "particle_scene"
    else:
        result["answer_modality"] = "iframe" if result.get("render_iframe") else "text"
    return result


def _atanor_self_sense() -> dict[str, Any]:
    """A unified 'body sense' of the whole program — the agent lives inside it and
    can feel every part in one call. Read-only aggregation across subsystems; each
    source is wrapped so one failing subsystem never blanks the others."""

    sense: dict[str, Any] = {"schema": "atanor.self-sense.v1"}

    # Local Brain (private memory)
    try:
        sense["local_brain"] = LOCAL_BRAIN.status()
    except Exception:
        sense["local_brain"] = {"available": False}

    # Web facts it has looked up and remembered locally
    try:
        sense["web_memory"] = {"facts_remembered": int(WEB_FACT_MEMORY.status().get("total_facts") or 0)}
    except Exception:
        sense["web_memory"] = {"facts_remembered": 0}

    # Cloud Brain (public learned graph)
    try:
        from apps.api.app.routers.cloud_brain import cloud_brain_status

        cb = cloud_brain_status()
        sense["cloud_brain"] = {"nodes": (cb.get("counts") or {}).get("nodes", 0), "edges": (cb.get("counts") or {}).get("edges", 0), "state": cb.get("state")}
    except Exception:
        sense["cloud_brain"] = {"available": False}

    # Autonomous loop + review queue + community (AGORA)
    try:
        from apps.api.app.routers.agentic_micro_os import AUTONOMOUS_DAEMON, REVIEW_QUEUE

        sense["autonomous"] = {"running": AUTONOMOUS_DAEMON.is_running(), "review_pending": int(REVIEW_QUEUE.status().get("pending") or 0), "learned_total": int(REVIEW_QUEUE.status().get("items_total") or 0)}
    except Exception:
        sense["autonomous"] = {"available": False}

    # Emotion / inner state
    try:
        snapshot = EVENT_BUS.engine.snapshot().to_dict()
        vector = snapshot.get("vector") or {}
        sense["mood"] = {"valence": vector.get("valence"), "curiosity": vector.get("curiosity"), "fatigue": vector.get("fatigue")}
    except Exception:
        sense["mood"] = {"available": False}

    return sense


@router.get("/api/atanor/self-sense")
def atanor_self_sense() -> dict[str, Any]:
    return {**_flags(), **_atanor_self_sense()}


_SELF_STATE_KO = ("지금 뭐", "뭐하고", "뭐 하고", "무엇을 하", "네 상태", "너 상태", "기분", "뭘 배웠", "무엇을 배웠", "뭐 배웠", "얼마나 알", "무슨 생각", "어떻게 지내")
_SELF_STATE_EN = ("what are you doing", "what have you learned", "how are you", "your state", "your mood", "what do you know", "how much do you know", "what are you thinking")


def _self_state_answer(question: str, language: str) -> dict[str, Any] | None:
    """Answer a question about ATANOR's own live state by pulling from every part
    of the program (the 'living creature' sense). Real numbers, no fabrication."""
    try:
        raw = str(question or "")
        lowered = raw.lower()
        if not (any(m in raw for m in _SELF_STATE_KO) or any(m in lowered for m in _SELF_STATE_EN)):
            return None
        s = _atanor_self_sense()
        cb = s.get("cloud_brain") or {}
        lb = s.get("local_brain") or {}
        au = s.get("autonomous") or {}
        mood = s.get("mood") or {}
        nodes = int(cb.get("nodes") or 0)
        facts = int(lb.get("total_facts") or 0)
        web_facts = int((s.get("web_memory") or {}).get("facts_remembered") or 0)
        learned = int(au.get("learned_total") or 0)
        running = bool(au.get("running"))
        is_ko = language == "ko"
        if is_ko:
            act = "지금 자율 루프를 돌리며 공개 웹과 AGORA를 살피고 있어요" if running else "지금은 자율 루프를 멈추고 대기 중이에요"
            answer = (
                f"{act}. 클라우드 브레인에는 검증 개념이 {nodes:,}개 있고, 검토 큐에는 {learned:,}개의 학습 후보가 있어요. "
                f"웹에서 찾아 기억해 둔 사실은 {web_facts}개이고, 당신에 대해서는 {facts}가지를 기억하고 있어요. 호기심은 {float(mood.get('curiosity') or 0):.2f}예요."
            )
        else:
            act = "I'm running the autonomous loop, scanning the public web and AGORA" if running else "the autonomous loop is paused"
            answer = (
                f"Right now {act}. The Cloud Brain holds {nodes:,} verified concepts and the review queue has {learned:,} learned candidates. "
                f"I've looked up and remembered {web_facts} web fact(s), and I remember {facts} thing(s) about you. My curiosity is {float(mood.get('curiosity') or 0):.2f}."
            )
        certificate = {
            "derivation_kind": "atanor_self_sense",
            "anchor_concept": {"id": "atanor_self", "label": "ATANOR self-state", "match": "live_sensorium"},
            "steps": [
                {"type": "subsystem", "source": "cloud_brain", "fact": f"{nodes} concepts"},
                {"type": "subsystem", "source": "review_queue", "fact": f"{learned} learned candidates"},
                {"type": "subsystem", "source": "local_brain", "fact": f"{facts} facts about the user"},
                {"type": "subsystem", "source": "autonomous_loop", "fact": "running" if running else "paused"},
            ],
            "evidence_concepts": ["cloud_brain", "local_brain", "review_queue", "autonomous_loop", "mood"],
            "confidence": 0.9,
            "confidence_basis": "live_subsystem_readout",
            "guarantees": {"external_llm": False, "fabricated_facts": False, "live_program_state": True},
        }
        return {"answer": answer, "reasoning_certificate": certificate, "confidence": 0.9}
    except Exception:  # pragma: no cover
        return None


class GraphHubImportRequest(BaseModel):
    source_id: str
    kind: str = "knowledge"  # "persona" or "knowledge"
    items: list[dict[str, Any]] = Field(default_factory=list)


@router.get("/api/local-brain/memory/status")
def local_brain_memory_status() -> dict[str, Any]:
    return {**_flags(), **LOCAL_BRAIN.status()}


@router.get("/api/local-brain/memory/facts")
def local_brain_memory_facts() -> dict[str, Any]:
    return {**_flags(), "facts": [f.to_dict() for f in LOCAL_BRAIN.all_facts()], **LOCAL_BRAIN.status()}


@router.post("/api/local-brain/memory/import-graph-hub")
def local_brain_import_graph_hub(request: GraphHubImportRequest) -> dict[str, Any]:
    kind = request.kind if request.kind in {"persona", "knowledge"} else "knowledge"
    added = LOCAL_BRAIN.import_graph_hub_source(request.source_id, kind, request.items)  # type: ignore[arg-type]
    return {
        **_flags(),
        "imported": len(added),
        "items": [f.to_dict() for f in added],
        "uploaded_to_cloud": False,
        "production_store_mutated": False,
        **LOCAL_BRAIN.status(),
    }


async def _chat_atanor_dispatch(request: AtanorChatRequest) -> dict[str, Any]:
    question = request.question_text()
    if not question:
        raise HTTPException(status_code=422, detail="question, query, or message is required")
    language = request.language or ("ko" if any("\uac00" <= char <= "\ud7a3" for char in question) else "en")
    conversation_context = build_conversation_context(question, request.conversation_context)
    routing_question = conversation_context.contextual_query
    emit_runtime_event(
        source="asm_v0",
        event_type=infer_user_text_runtime_event(question),
        payload_summary=f"input_language={language}; mode={request.mode}",
        intensity=0.6,
    )
    three_core_trace = _run_three_core_compact_trace(question)
    route = route_conversation_request(routing_question)
    splatra_visual_request = _is_splatra_visual_request(routing_question)
    web_grounded_conversation = bool(request.web_search and _should_use_web_grounded_conversation(routing_question))
    if splatra_visual_request or (
        (
            request.mode in {"conversation", "live_selfhood", "dashboard_conversation"}
            or _is_live_selfhood_conversation(question)
        )
        and not web_grounded_conversation
    ):
        response = _attach_three_core_trace(
            _live_selfhood_payload(
                request,
                question=question,
                language=language,
                conversation_context=conversation_context,
            ),
            request=request,
            three_core_trace=three_core_trace,
        )
        _emit_conversation_result_events(response)
        return response
    if _clean_graph_count_question(question) or _is_graph_count_question(question):
        response = _attach_three_core_trace(
            _clean_graph_count_payload(request, question=question, language=language),
            request=request,
            three_core_trace=three_core_trace,
        )
        _emit_conversation_result_events(response)
        return response
    if _should_try_base_brain_first(question):
        early = _base_brain_payload(request, question=question, language=language, rag_result={})
        if early is not None:
            response = _attach_three_core_trace(early, request=request, three_core_trace=three_core_trace)
            _emit_conversation_result_events(response)
            return response
    rag_status = await alpha_service.query_graphrag(
        routing_question,
        request.web_search,
        None,
        brain_mode=request.brain_mode,
        locale=request.language,
        include_trace=True,
    )
    rag_result = rag_status.get("result") or {}
    semantic_context = _semantic_context_from_rag(rag_result)
    if _is_recent_learning_question(routing_question):
        semantic_context = _augment_recent_learning_context(semantic_context)
    if _needs_base_brain_fallback(semantic_context):
        exchange = run_local_cloud_exchange(
            question,
            pin_context=request.mode in {"trace", "research"},
            allow_web=request.web_search,
            max_chunks=1,
            max_latency_ms=900,
        )
        fallback = _base_brain_payload(request, question=question, language=language, rag_result=rag_result, exchange=exchange)
        if fallback is not None:
            # Web-grounded rescue: if Base Brain has no local answer but web search
            # is on, answer from a real cited web source instead of abstaining.
            fb_result = fallback.get("result") if isinstance(fallback, dict) else None
            if request.web_search and isinstance(fb_result, dict) and (
                not fb_result.get("answer") or _answer_is_abstention(str(fb_result.get("answer") or ""))
            ):
                rescue = await _web_grounded_rescue(question, language)
                if rescue:
                    fb_result["answer"] = rescue["answer"]
                    fb_result["reasoning_certificate"] = rescue["reasoning_certificate"]
                    fb_result["confidence"] = rescue["confidence"]
                    fb_result["answer_kind"] = "web_unreachable" if rescue.get("web_unreachable") else "web_search_grounded"
                    fb_result["web_search_provider"] = rescue["provider"]
                    fb_result["can_speak"] = True
                    if rescue.get("source_url"):
                        fb_result["render_iframe"] = {"url": rescue["source_url"], "title": rescue.get("source_title") or question[:60]}
            response = _attach_three_core_trace(fallback, request=request, three_core_trace=three_core_trace)
            _emit_conversation_result_events(response)
            return response
        semantic_context = _augment_semantic_context_with_exchange(semantic_context, exchange)
    else:
        exchange = None
        if semantic_context.get("local_coverage") in {None, "low", "weak", "none"}:
            exchange = run_local_cloud_exchange(
                question,
                pin_context=request.mode in {"trace", "research"},
                allow_web=request.web_search,
                max_chunks=1,
                max_latency_ms=900,
            )
            semantic_context = _augment_semantic_context_with_exchange(semantic_context, exchange)
    plan = plan_speech(
        routing_question,
        semantic_context,
        language=language,
        audience_level=request.audience_level,
        tone=request.tone,
        mode=request.mode,
    )
    realized = realize_answer(plan, semantic_context, query=question)
    if request.mode not in {"trace", "research"} and (
        _answer_is_unsafe(str(realized.get("answer") or ""))
        or _answer_is_abstention(str(realized.get("answer") or ""))
    ):
        grounded_web_answer = str(rag_result.get("answer") or "").strip()
        if (
            request.web_search
            and grounded_web_answer
            and rag_result.get("web_search")
            and (semantic_context.get("evidence") or semantic_context.get("relations") or semantic_context.get("claims"))
        ):
            realized["answer"] = grounded_web_answer
            realized["confidence"] = max(
                float(realized.get("confidence") or 0.0),
                float(rag_result.get("confidence") or 0.0),
                0.52,
            )
            realized["repair"] = {
                **(realized.get("repair") or {}),
                "safety_applied": True,
                "source": "web_grounded_native_graph_token_answer",
                "web_search_provider": (rag_result.get("web_search") or {}).get("provider"),
            }
    if request.mode not in {"trace", "research"} and _answer_is_unsafe(str(realized.get("answer") or "")):
        fallback = _base_brain_payload(request, question=question, language=language, rag_result=rag_result)
        if fallback is not None:
            result = fallback["result"]
            result.setdefault("compact_trace", {})["safety_fallback"] = "base_brain_after_unsafe_surface_answer"
            response = _attach_three_core_trace(fallback, request=request, three_core_trace=three_core_trace)
            _emit_conversation_result_events(response)
            return response
        repair_trace: dict[str, Any] = {}
        repaired = repair_answer_for_mode(str(realized.get("answer") or ""), mode="default", trace=repair_trace)
        realized["answer"] = repaired.get("repaired_answer") or (
            "현재 확인된 근거만으로는 단정하기 어렵습니다." if language == "ko" else "I do not have enough verified evidence to answer confidently yet."
        )
        realized["repair"] = {
            **(realized.get("repair") or {}),
            "safety_applied": True,
            "applied_rules": repaired.get("applied_rules", []),
            "moved_to_trace_count": len(repaired.get("moved_to_trace", [])),
        }
    visual_grounding = _grounded_context_from_semantic_context(
        question,
        route=route,
        semantic_context=semantic_context,
    )
    visual_route = route
    if route.route_type == "unknown" and visual_grounding.facts:
        visual_route = ConversationRoute(
            route_type="general_knowledge_question",
            grounding_required=True,
            grounding_sources=("semantic_cloud_graph_web_evidence_readonly",),
            confidence=max(float(getattr(route, "confidence", 0.0) or 0.0), 0.62),
            fallback_allowed=False,
            rationale_summary="web/graph evidence is available for a fact-bound visual explanation",
        )
        visual_grounding = GroundedContext(
            route_type=visual_route.route_type,
            facts=visual_grounding.facts,
            constraints=visual_grounding.constraints,
            unknowns=visual_grounding.unknowns,
            source_refs=visual_grounding.source_refs,
            grounding_source=visual_grounding.grounding_source,
            grounding_quality=visual_grounding.grounding_quality,
            safety_flags=visual_grounding.safety_flags,
        )
    fact_bound_web_answer = (
        _web_fact_bound_surface(
            routing_question,
            route=visual_route,
            grounded_context=visual_grounding,
            language=language,
        )
        if request.web_search and request.mode not in {"trace", "research"}
        else None
    )
    if fact_bound_web_answer:
        discourse_metadata = grounded_discourse_metadata(routing_question, visual_grounding)
        realized["answer"] = fact_bound_web_answer
        realized["confidence"] = max(
            float(realized.get("confidence") or 0.0),
            float(rag_result.get("confidence") or 0.0),
            0.64 if visual_grounding.grounding_quality == "high" else 0.56,
        )
        realized["repair"] = {
            **(realized.get("repair") or {}),
            "safety_applied": True,
            "source": "semantic_cloud_graph_fact_bound_surface",
            "fact_bound_surface": True,
            "web_search_provider": (rag_result.get("web_search") or {}).get("provider"),
            "grounding_quality": visual_grounding.grounding_quality,
            **discourse_metadata,
        }
    visual_plan = plan_visual_imagination(
        question,
        route=visual_route,
        grounded_context=visual_grounding,
        diagnostics={
            "external_llm_used": False,
            "external_sllm_used": False,
            "rule_based_answer_used": False,
            "generation_basis": "semantic_cloud_graph_surface_brain_v0",
        },
        answer_available=bool(str(realized.get("answer") or "").strip()),
        client_layout_feedback=request.layout_feedback,
    )
    splatra_command_sequence_obj = (
        compile_scene_choreography_commands(visual_plan.scene_choreography)
        if visual_plan.scene_choreography
        else None
    )
    splatra_command_sequence = splatra_command_sequence_obj.to_dict() if splatra_command_sequence_obj else None
    splatra_interactive_scene_analysis_obj = (
        analyze_scene_choreography(visual_plan.scene_choreography)
        if visual_plan.scene_choreography
        else None
    )
    splatra_interactive_scene_analysis = (
        splatra_interactive_scene_analysis_obj.to_dict()
        if splatra_interactive_scene_analysis_obj
        else None
    )
    visual_policy = {
        "scene_content_source": visual_plan.diagnostics.get("scene_content_source", "none"),
        "scene_authoring_basis": visual_plan.diagnostics.get("scene_authoring_basis"),
        "visual_affordance_basis": visual_plan.diagnostics.get("visual_affordance_basis"),
        "layout_decision_basis": visual_plan.diagnostics.get("layout_decision_basis"),
        "reason": visual_plan.diagnostics.get("reason") or visual_plan.reason,
        "topic_scene_templates": False,
        "renderer_may_infer_topic": False,
        "particle_text": False,
        "text_rendering": "dom_text_not_particles",
        "orb_identity": "atanor_self_body_not_scene_object" if visual_plan.scene_choreography else "atanor_primary_self_body",
        "verified_evidence_required_for_general_knowledge": visual_route.route_type == "general_knowledge_question",
    }
    compact_trace = {
        "local_coverage": semantic_context.get("local_coverage"),
        "semantic_cloud_graph": {
            "attached_nodes": len(semantic_context.get("concepts") or []),
            "evidence_docs": len(semantic_context.get("evidence") or []),
        },
        "conversation_context": {
            "turn_count": len(conversation_context.turns),
            "used_for_routing": bool(conversation_context.turns),
            "followup_detected": conversation_context.followup_detected,
            "focus_terms": list(conversation_context.focus_terms),
            "focus_source": conversation_context.focus_source,
            "resolution_strategy": conversation_context.resolution_strategy,
            "used_for_learning": False,
            "local_brain_write": False,
            "production_store_mutated": False,
            "basis": conversation_context.basis,
        },
        "surface_graph": {
            "construction_families": realized["trace_summary"].get("selected_construction_families", []),
            "discourse_moves": realized["trace_summary"].get("selected_discourse_moves", []),
        },
        "q_cortex": {
            "used": bool(plan.get("q_cortex_used")),
            "run_id": plan.get("q_cortex_run_id"),
            "real_quantum_hardware_used": False,
        },
        "working_memory": {
            "temporary_context": bool((rag_result.get("retrieval_trace") or {}).get("working_memory_overlay")),
            "local_brain_write": False,
        },
        "local_cloud_exchange": _compact_exchange_trace(exchange),
        "visual_imagination": visual_plan.diagnostics,
        "splatra_scene_policy": visual_policy,
        "splatra_command_sequence": {
            "available": bool(splatra_command_sequence),
            "action_count": len(splatra_command_sequence.get("scene_actions", [])) if splatra_command_sequence else 0,
            "raw_buffers_in_agent_context": False,
            "topic_scene_templates": False,
            "renderer_may_infer_topic": False,
            "text_rendering": "dom_text_not_particles",
        },
        "splatra_interactive_scene_analysis": {
            "available": bool(splatra_interactive_scene_analysis),
            "object_count": int(splatra_interactive_scene_analysis.get("object_count", 0)) if splatra_interactive_scene_analysis else 0,
            "raw_splat_inference": False,
            "raw_buffers_in_agent_context": False,
            "interactive_scene_metadata": bool(splatra_interactive_scene_analysis),
        },
        "answer_surface": {
            "source": (realized.get("repair") or {}).get("source") or "surface_brain_realizer",
            "fact_bound_surface": bool((realized.get("repair") or {}).get("fact_bound_surface")),
            "grounding_quality": (realized.get("repair") or {}).get("grounding_quality"),
            "grounded_discourse_mode": (realized.get("repair") or {}).get("grounded_discourse_mode"),
            "grounded_fact_roles": (realized.get("repair") or {}).get("grounded_fact_roles") or [],
            "grounded_discourse_basis": (realized.get("repair") or {}).get("grounded_discourse_basis"),
            "graph_token_fragment_promoted": (realized.get("repair") or {}).get("source")
            == "web_grounded_native_graph_token_answer",
        },
        "confidence": "high" if realized["confidence"] >= 0.75 else "medium" if realized["confidence"] >= 0.5 else "low",
    }
    if compact_trace["answer_surface"]["fact_bound_surface"]:
        realized["answer"] = _clean_public_fact_bound_answer(realized.get("answer"))
    payload = {
        "answer": realized["answer"],
        "language": realized["language"],
        "confidence": realized["confidence"],
        "default_trace_visible": False,
        "trace": compact_trace if request.include_trace or request.mode in {"trace", "research"} else None,
        "compact_trace": compact_trace,
        "research_trace": {
            "semantic_context": semantic_context,
            "surface_plan": plan,
            "realized_answer": realized,
            "rag_retrieval_trace": rag_result.get("retrieval_trace", {}),
        } if request.mode == "research" else None,
        "evidence_docs": _public_evidence_docs(list(semantic_context.get("evidence") or []), mode=request.mode),
        "surface_plan": {
            "plan_id": plan.get("plan_id"),
            "intent": plan.get("intent"),
            "construction_families": compact_trace["surface_graph"]["construction_families"],
            "q_cortex_used": plan.get("q_cortex_used"),
            "q_cortex_run_id": plan.get("q_cortex_run_id"),
        },
        "scene_choreography": visual_plan.scene_choreography,
        "visual_scene_plan": visual_plan.scene_choreography,
        "splatra_scene_plan": visual_plan.scene_choreography,
        "splatra_command_sequence": splatra_command_sequence,
        "splatra_interactive_scene_analysis": splatra_interactive_scene_analysis,
        "splatra_cartridge_queue": None,
        "splatra_sidecar_dispatch": None,
        "splatra_scene_policy": visual_policy,
        "answer_engine": {
            "name": "ATANOR Surface Brain",
            "semantic_plane": "Semantic Cloud Graph",
            "surface_plane": "Surface Cloud Graph",
            "external_llm": False,
            "external_sllm": False,
            "external_llm_used": False,
            "external_sllm_used": False,
            "local_brain_write": False,
            "production_store_mutated": False,
            "candidate_promotion": False,
            "internal_trace_exposed": False,
            "rule_based_answer_used": False,
            "generation_basis": "semantic_cloud_graph_surface_brain_v0",
            "trace_hidden_by_default": True,
            "q_cortex_optional": True,
            "network_barrier": "sealed_for_generation",
            "splatra_scene_policy": visual_policy,
            "conversation_context_used": bool(conversation_context.turns),
            "conversation_context_basis": conversation_context.basis,
            "conversation_followup_detected": conversation_context.followup_detected,
            "conversation_resolution_strategy": conversation_context.resolution_strategy,
            "answer_surface_source": compact_trace["answer_surface"]["source"],
            "fact_bound_surface": compact_trace["answer_surface"]["fact_bound_surface"],
            "grounded_discourse_mode": compact_trace["answer_surface"]["grounded_discourse_mode"],
            "grounded_discourse_basis": compact_trace["answer_surface"]["grounded_discourse_basis"],
            "graph_token_fragment_promoted": compact_trace["answer_surface"]["graph_token_fragment_promoted"],
            "eval_rows_used_for_learning": False,
        },
        **_flags(),
    }
    response = _attach_three_core_trace({"state": "completed", "result": payload, **_flags()}, request=request, three_core_trace=three_core_trace)
    _emit_conversation_result_events(response)
    return response
