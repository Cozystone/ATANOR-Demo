from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from .constructions import CONSTRUCTIONS, FORBIDDEN_INNER_VOICE_PHRASES, InnerVoiceConstruction


KOREAN_GREETINGS = ("안녕", "안녕하세요", "하이", "반가워")


@dataclass(frozen=True)
class InnerVoiceSurface:
    construction: InnerVoiceConstruction
    act_scores: dict[str, float]
    goal: str
    tension: str
    candidate_actions: list[str]
    chosen_action: str
    blocked_actions: list[str]
    uncertainty: str
    next_intent: str
    monologue_text: str
    surface_score: float


def short_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _vector(snapshot: dict[str, Any]) -> dict[str, float]:
    raw = snapshot.get("vector") if isinstance(snapshot.get("vector"), dict) else {}
    return {
        "curiosity": float(raw.get("curiosity", 0.45) or 0.45),
        "caution": float(raw.get("caution", 0.35) or 0.35),
        "fatigue": float(raw.get("fatigue", 0.0) or 0.0),
        "valence": float(raw.get("valence", 0.0) or 0.0),
    }


def _label(snapshot: dict[str, Any]) -> str:
    return str(snapshot.get("label") or "steady")


def _is_greeting(text: str) -> bool:
    stripped = re.sub(r"\s+", "", str(text or "").lower())
    return any(item in stripped for item in KOREAN_GREETINGS)


def _policy_parts(policy: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    review = policy.get("review") if isinstance(policy.get("review"), dict) else {}
    agent_loop = policy.get("agent_loop") if isinstance(policy.get("agent_loop"), dict) else {}
    return review, agent_loop


def score_inner_voice_acts(input_data: Any) -> dict[str, float]:
    snapshot = dict(getattr(input_data, "emotion_snapshot", {}) or {})
    policy = dict(getattr(input_data, "policy_decision", {}) or {})
    vector = _vector(snapshot)
    review, agent_loop = _policy_parts(policy)
    latest_user_input = str(getattr(input_data, "latest_user_input", "") or "")
    latest_action_result = dict(getattr(input_data, "latest_action_result", {}) or {})
    permission_tier = str(getattr(input_data, "permission_tier", "OBSERVE_ONLY") or "OBSERVE_ONLY")
    review_pressure = float(getattr(input_data, "review_queue_pressure", 0.0) or 0.0)
    splatra_state = dict(getattr(input_data, "splatra_state", {}) or {})
    scores = {construction.act: construction.prior for construction in CONSTRUCTIONS}

    if _is_greeting(latest_user_input):
        scores["greeting_response_planning"] += 0.78
    if latest_user_input and not _is_greeting(latest_user_input):
        scores["greeting_response_planning"] -= 0.12
        scores["goal_selection"] += 0.22
        scores["action_selection"] += 0.12
    if review_pressure >= 0.55 or review.get("should_request_review"):
        scores["review_pressure"] += 0.75 + min(review_pressure, 1.0) * 0.25
    if permission_tier not in {"OBSERVE_ONLY", "READ_ONLY", ""}:
        scores["permission_caution"] += 0.7
        scores["host_executor_caution"] += 0.2
    if permission_tier in {"FULL_HOST_AUTHORITY", "HOST_EXECUTOR", "WRITE_ENABLED"}:
        scores["host_executor_caution"] += 0.75
    if latest_action_result.get("voice_unavailable") or latest_action_result.get("text_fallback"):
        scores["voice_fallback"] += 0.82
    if latest_action_result.get("stopped_reason"):
        scores["blocked_action_reflection"] += 0.45
        scores["summary_brief"] += 0.18
    if splatra_state:
        scores["splatra_imagination"] += 0.7
    if vector["fatigue"] >= 0.58 or agent_loop.get("should_rest"):
        scores["fatigue_rest"] += 0.78
    if vector["caution"] >= 0.68:
        scores["uncertainty_check"] += 0.48
        scores["permission_caution"] += 0.2
    if vector["curiosity"] >= 0.62 and review_pressure < 0.55:
        scores["exploration_drive"] += 0.52
    return {key: round(value, 4) for key, value in scores.items()}


def select_inner_voice_construction(input_data: Any) -> tuple[InnerVoiceConstruction, dict[str, float]]:
    scores = score_inner_voice_acts(input_data)
    best_act = max(scores, key=lambda act: (scores[act], act))
    for construction in CONSTRUCTIONS:
        if construction.act == best_act:
            return construction, scores
    return CONSTRUCTIONS[0], scores


def _goal_for(construction: InnerVoiceConstruction, has_user_input: bool) -> str:
    goals = {
        "greeting_response_planning": "인사를 짧고 따뜻하게 받아들이고 대화를 이어갈 준비를 합니다.",
        "goal_selection": "사용자의 말을 현재 상태와 맞춰 다음 응답 목표를 고릅니다.",
        "action_selection": "가능한 행동 중 안전하고 작은 다음 단계를 고릅니다.",
        "blocked_action_reflection": "막힌 행동을 승인 가능한 경로로 돌릴 방법을 찾습니다.",
        "uncertainty_check": "확실하지 않은 부분을 줄이고 확인 가능한 말만 남깁니다.",
        "review_pressure": "검토 대기열을 먼저 정리하고 자동 실행으로 넘기지 않습니다.",
        "permission_caution": "권한 경계를 읽고 쓰기나 변경은 멈춘 채 설명합니다.",
        "exploration_drive": "탐색 충동을 작은 후보로 낮추고 검토 가능하게 둡니다.",
        "fatigue_rest": "활동 강도를 낮추고 다음 주기를 준비합니다.",
        "splatra_imagination": "구슬과 입자의 움직임을 현재 말의 흐름에 맞춥니다.",
        "host_executor_caution": "호스트 실행 경계를 확인하고 검토 없는 실행을 피합니다.",
        "voice_fallback": "음성 출력이 비어 있으면 텍스트와 구슬 반응으로 이어갑니다.",
        "summary_brief": "현재 상태를 짧게 압축해 보여줄 준비를 합니다.",
    }
    if not has_user_input and construction.act == "goal_selection":
        return "현재 상태를 조용히 살피고 먼저 말하지 않습니다."
    return goals.get(construction.act, "다음 응답의 경계를 정합니다.")


def _surface_for_act(construction: InnerVoiceConstruction, input_data: Any, label: str) -> str:
    latest_user_input = str(getattr(input_data, "latest_user_input", "") or "")
    permission_tier = str(getattr(input_data, "permission_tier", "OBSERVE_ONLY") or "OBSERVE_ONLY")
    review_pressure = float(getattr(input_data, "review_queue_pressure", 0.0) or 0.0)
    latest_action_result = dict(getattr(input_data, "latest_action_result", {}) or {})
    splatra_state = dict(getattr(input_data, "splatra_state", {}) or {})

    if construction.act == "greeting_response_planning":
        return "인사를 가볍게 받아들이고 있습니다. 지금은 짧게 응답하면서 대화를 이어가겠습니다."
    if construction.act == "review_pressure":
        return f"리뷰 대기 압력이 {review_pressure:.2f}까지 올라와 있습니다. 탐색보다 검토 대기열을 먼저 줄이는 편이 안전합니다."
    if construction.act == "permission_caution":
        return f"{permission_tier} 경계 안에서 머물고 있습니다. 쓰기나 변경은 멈추고 확인 가능한 말만 드리겠습니다."
    if construction.act == "host_executor_caution":
        return "호스트에 닿는 행동은 아직 검토가 먼저입니다. 실행보다 근거와 기록을 앞에 두겠습니다."
    if construction.act == "voice_fallback":
        return "음성 출력이 아직 비어 있습니다. 텍스트와 구슬 반응을 맞추며 대화를 이어가겠습니다."
    if construction.act == "splatra_imagination":
        scene_focus = splatra_state.get("stage_layout") == "scene_focus"
        motion_count = int(float(splatra_state.get("motion_count") or 0))
        if scene_focus and motion_count > 0:
            return "중앙 무대를 비우고 입자의 흐름을 말의 순서에 맞추고 있습니다."
        if scene_focus:
            return "중앙 무대를 비우고 입자들이 설명의 형태를 잡도록 정렬하고 있습니다."
        return "구슬의 움직임을 지금 상태에 맞추고 있습니다. 입자를 크게 흔들기보다 호흡처럼 모으겠습니다."
    if construction.act == "fatigue_rest":
        return "활동을 조금 낮춰야 할 신호가 있습니다. 급히 밀어붙이지 않고 다음 주기를 준비하겠습니다."
    if construction.act == "uncertainty_check":
        return "확실하지 않은 부분은 작게 말하겠습니다. 근거가 있는 것과 모르는 것을 분리하겠습니다."
    if construction.act == "exploration_drive":
        return "더 보고 싶은 방향이 있습니다. 바로 바꾸지 않고 검토 가능한 후보로 작게 남기겠습니다."
    if construction.act == "blocked_action_reflection":
        reason = str(latest_action_result.get("stopped_reason") or "권한 경계")
        return f"{reason} 때문에 바로 넘기지 않겠습니다. 보류 사유를 남기고 안전한 경로를 고르겠습니다."
    if construction.act == "summary_brief":
        return "지금 필요한 것은 긴 설명보다 짧은 요약입니다. 상태와 다음 한 걸음만 보여드리겠습니다."
    if latest_user_input:
        return f"{label} 상태에서 사용자의 말을 받았습니다. 질문의 초점을 먼저 붙잡고 필요한 지점부터 답하겠습니다."
    return f"{label} 상태를 유지하고 있습니다. 먼저 움직이지 않고 다음 신호를 기다리겠습니다."


def _sanitize_surface(text: str, forbidden_phrases: tuple[str, ...]) -> str:
    surface = re.sub(r"\s+", " ", str(text or "").strip())
    for phrase in (*FORBIDDEN_INNER_VOICE_PHRASES, *forbidden_phrases):
        surface = surface.replace(phrase, "표시 가능한 자기-서술 채널")
    surface = surface.replace("chain-of-thought", "self-narration")
    surface = surface.replace("Chain-of-thought", "self-narration")
    if surface and not surface.endswith((".", "?", "!")):
        surface = f"{surface}."
    return surface[:220]


def _surface_score(text: str, construction: InnerVoiceConstruction) -> float:
    score = 0.64
    length = len(text)
    if 26 <= length <= construction.length_target + 70:
        score += 0.16
    if any(token in text for token in construction.lexical_field):
        score += 0.08
    if not any(phrase in text for phrase in FORBIDDEN_INNER_VOICE_PHRASES):
        score += 0.08
    if "했습니다" in text and "먼저 의도와 경계" in text:
        score -= 0.1
    return round(max(0.0, min(1.0, score)), 4)


def generate_construction_conditioned_surface(input_data: Any) -> InnerVoiceSurface:
    construction, scores = select_inner_voice_construction(input_data)
    snapshot = dict(getattr(input_data, "emotion_snapshot", {}) or {})
    label = _label(snapshot)
    latest_user_input = str(getattr(input_data, "latest_user_input", "") or "")
    policy = dict(getattr(input_data, "policy_decision", {}) or {})
    _, agent_loop = _policy_parts(policy)

    goal = _goal_for(construction, bool(latest_user_input))
    blocked_actions = [
        "Local Brain 직접 쓰기",
        "production store 변경",
        "후보 자동 승격",
        "외부 LLM 호출",
    ]
    candidate_actions = ["짧은 응답 준비", "안전 경계 확인", "검토 대기 확인"]
    if construction.act in {"exploration_drive", "splatra_imagination"}:
        candidate_actions.append("검토 가능한 후보 남기기")
    if construction.act in {"review_pressure", "permission_caution", "host_executor_caution"}:
        candidate_actions.append("자동 실행 보류")

    chosen_action = "공개 응답은 짧게 만들고, 쓰기나 변경은 보류하겠습니다."
    if construction.act == "review_pressure":
        chosen_action = "탐색을 줄이고 리뷰 대기열을 먼저 보여드리겠습니다."
    elif construction.act == "greeting_response_planning":
        chosen_action = "인사에 짧게 응답하고 자연스럽게 이어가겠습니다."
    elif construction.act == "voice_fallback":
        chosen_action = "텍스트와 구슬 반응으로 대화를 이어가겠습니다."
    elif construction.act == "fatigue_rest" or agent_loop.get("should_rest"):
        chosen_action = "활동 강도를 낮추고 다음 주기로 넘기겠습니다."

    tension = "표현하고 싶은 것과 안전 경계 사이의 균형"
    if construction.act in {"permission_caution", "host_executor_caution", "blocked_action_reflection"}:
        tension = "실행 욕구와 승인 경계 사이의 긴장"
    elif construction.act == "exploration_drive":
        tension = "탐색 충동과 검토 가능성 사이의 균형"
    elif construction.act == "fatigue_rest":
        tension = "계속하려는 흐름과 쉬어야 하는 신호 사이의 균형"

    uncertainty = "중간"
    if construction.act in {"uncertainty_check", "permission_caution", "host_executor_caution"}:
        uncertainty = "높음"
    elif construction.act in {"greeting_response_planning", "splatra_imagination"}:
        uncertainty = "낮음"

    next_intent = "사용자에게 필요한 만큼만 말하고, 변경이 필요하면 승인 대기로 남기겠습니다."
    if construction.act == "greeting_response_planning":
        next_intent = "짧게 응답하고 대화를 이어갈 자세를 잡겠습니다."
    elif construction.act == "review_pressure":
        next_intent = "검토할 항목을 먼저 보여드릴 준비를 하겠습니다."
    elif construction.act == "splatra_imagination":
        next_intent = "구슬의 움직임과 말의 호흡을 맞추겠습니다."

    monologue = _sanitize_surface(_surface_for_act(construction, input_data, label), construction.forbidden_phrases)
    return InnerVoiceSurface(
        construction=construction,
        act_scores=scores,
        goal=goal,
        tension=tension,
        candidate_actions=candidate_actions,
        chosen_action=chosen_action,
        blocked_actions=blocked_actions,
        uncertainty=uncertainty,
        next_intent=next_intent,
        monologue_text=monologue,
        surface_score=_surface_score(monologue, construction),
    )
