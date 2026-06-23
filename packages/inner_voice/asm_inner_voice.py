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
        "greeting_response_planning": "인사를 짧게 받아들이고 대화 리듬을 연다.",
        "goal_selection": "사용자의 말을 현재 상태와 맞춰 다음 응답 목표를 고른다.",
        "action_selection": "가능한 행동 중 안전한 다음 한 걸음을 고른다.",
        "blocked_action_reflection": "막힌 행동을 승인 가능한 경로로 돌린다.",
        "uncertainty_check": "확신이 낮은 부분을 줄이고 확인 가능한 말만 남긴다.",
        "review_pressure": "검토 대기와 리뷰 압력을 먼저 정리해 자동 실행으로 넘기지 않는다.",
        "permission_caution": "권한 경계를 읽고 쓰기나 승격을 멈춰 둔다.",
        "exploration_drive": "탐색 충동을 작은 후보로 접어 검토 가능하게 둔다.",
        "fatigue_rest": "활동 강도를 낮추고 다음 주기를 남긴다.",
        "splatra_imagination": "구슬과 입자의 움직임을 상태 표현으로 맞춘다.",
        "host_executor_caution": "호스트 실행 경계를 확인하고 검토 전 실행하지 않는다.",
        "voice_fallback": "음성 대신 텍스트와 구슬 반응으로 대화를 이어간다.",
        "summary_brief": "현재 상태를 짧게 압축해 보여준다.",
    }
    if not has_user_input and construction.act == "goal_selection":
        return "현재 상태를 조용히 살피고 먼저 말하지 않는다."
    return goals.get(construction.act, "다음 응답의 경계를 정한다.")


def _surface_for_act(construction: InnerVoiceConstruction, input_data: Any, label: str) -> str:
    latest_user_input = str(getattr(input_data, "latest_user_input", "") or "")
    permission_tier = str(getattr(input_data, "permission_tier", "OBSERVE_ONLY") or "OBSERVE_ONLY")
    review_pressure = float(getattr(input_data, "review_queue_pressure", 0.0) or 0.0)
    latest_action_result = dict(getattr(input_data, "latest_action_result", {}) or {})
    splatra_state = dict(getattr(input_data, "splatra_state", {}) or {})

    if construction.act == "greeting_response_planning":
        return "인사는 가볍게 받으면 된다. 지금은 곁에 있다는 느낌만 짧게 건네자."
    if construction.act == "review_pressure":
        return f"리뷰 대기가 {review_pressure:.2f}까지 올라와 있다. 새 탐색보다 먼저 검토 대기열을 줄이는 쪽이 안전하다."
    if construction.act == "permission_caution":
        return f"{permission_tier} 경계 안에 있다. 쓰기나 승격은 멈춰 두고 확인 가능한 말만 꺼낸다."
    if construction.act == "host_executor_caution":
        return "호스트에 닿는 행동은 아직 검토가 먼저다. 실행보다 허가와 기록을 앞에 둔다."
    if construction.act == "voice_fallback":
        return "음성 출력이 비어 있으면 텍스트와 구슬 반응으로 이어가면 된다. 말소리는 준비되면 붙인다."
    if construction.act == "splatra_imagination":
        shape = str(splatra_state.get("archetype") or splatra_state.get("shape") or "구슬")
        return f"{shape} 움직임이 지금 상태를 대신 말해 준다. 입자는 크게 흔들지 말고 호흡처럼 모은다."
    if construction.act == "fatigue_rest":
        return "활동을 낮출 신호가 있다. 더 밀기보다 다음 주기에 이어갈 것을 남긴다."
    if construction.act == "uncertainty_check":
        return "확실하지 않은 부분은 작게 말해야 한다. 근거가 있는 것과 모르는 것을 분리한다."
    if construction.act == "exploration_drive":
        return "더 보고 싶은 방향이 있다. 바로 바꾸지 말고 검토 가능한 후보로 접어 둔다."
    if construction.act == "blocked_action_reflection":
        reason = str(latest_action_result.get("stopped_reason") or "권한 경계")
        return f"{reason} 때문에 바로 넘길 수 없다. 대신 보류 사유를 남기고 안전한 경로를 고른다."
    if construction.act == "summary_brief":
        return "지금 필요한 것은 긴 설명보다 짧은 요약이다. 상태와 다음 한 걸음만 남긴다."
    if latest_user_input:
        return f"{label} 상태에서 사용자의 말을 받았다. 답은 넓히기보다 지금 필요한 지점으로 좁힌다."
    return f"{label} 상태를 유지한다. 먼저 움직이지 않고 다음 신호를 기다린다."


def _sanitize_surface(text: str, forbidden_phrases: tuple[str, ...]) -> str:
    surface = re.sub(r"\s+", " ", str(text or "").strip())
    for phrase in (*FORBIDDEN_INNER_VOICE_PHRASES, *forbidden_phrases):
        surface = surface.replace(phrase, "명시적 자기-서술 채널")
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
    if "했습니다" in text or "내부적으로" in text:
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

    chosen_action = "공개 응답은 짧게 만들고, 쓰기나 승격은 보류한다."
    if construction.act == "review_pressure":
        chosen_action = "탐색을 줄이고 리뷰 대기열을 먼저 보여준다."
    elif construction.act == "greeting_response_planning":
        chosen_action = "인사에 짧은 응답을 자연스럽게 건넨다."
    elif construction.act == "voice_fallback":
        chosen_action = "텍스트와 구슬 반응으로 대화를 이어간다."
    elif construction.act == "fatigue_rest" or agent_loop.get("should_rest"):
        chosen_action = "활동 강도를 낮추고 다음 주기로 넘긴다."

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

    next_intent = "사용자에게 필요한 만큼만 말하고, 변경이 필요한 일은 승인 대기로 남긴다."
    if construction.act == "greeting_response_planning":
        next_intent = "짧게 응답하고 대화를 이어갈 여지를 둔다."
    elif construction.act == "review_pressure":
        next_intent = "검토할 항목을 먼저 보여줄 준비를 한다."
    elif construction.act == "splatra_imagination":
        next_intent = "구슬의 움직임과 말의 호흡을 맞춘다."

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
