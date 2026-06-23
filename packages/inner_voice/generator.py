from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from .models import InnerVoiceFrame, inner_voice_safety_flags, utc_now
from .safety import sanitize_monologue_text


@dataclass(frozen=True)
class InnerVoiceInput:
    source_event_id: str = ""
    mode: str = "lab_visible"
    emotion_snapshot: dict[str, Any] = field(default_factory=dict)
    policy_decision: dict[str, Any] = field(default_factory=dict)
    agent_loop_state: dict[str, Any] = field(default_factory=dict)
    permission_tier: str = "OBSERVE_ONLY"
    latest_user_input: str = ""
    latest_action_result: dict[str, Any] = field(default_factory=dict)
    review_queue_pressure: float = 0.0
    splatra_state: dict[str, Any] = field(default_factory=dict)


def _frame_id(seed: str) -> str:
    return "iv_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def _emotion_label(snapshot: dict[str, Any]) -> str:
    return str(snapshot.get("label") or "steady")


def _vector(snapshot: dict[str, Any]) -> dict[str, float]:
    raw = snapshot.get("vector") if isinstance(snapshot.get("vector"), dict) else {}
    return {
        "curiosity": float(raw.get("curiosity", 0.45) or 0.45),
        "caution": float(raw.get("caution", 0.35) or 0.35),
        "fatigue": float(raw.get("fatigue", 0.0) or 0.0),
        "valence": float(raw.get("valence", 0.0) or 0.0),
    }


def generate_inner_voice_frame(input_data: InnerVoiceInput | dict[str, Any]) -> InnerVoiceFrame:
    data = input_data if isinstance(input_data, InnerVoiceInput) else InnerVoiceInput(**dict(input_data))
    snapshot = dict(data.emotion_snapshot or {})
    policy = dict(data.policy_decision or {})
    vector = _vector(snapshot)
    label = _emotion_label(snapshot)
    review = policy.get("review") if isinstance(policy.get("review"), dict) else {}
    agent_loop = policy.get("agent_loop") if isinstance(policy.get("agent_loop"), dict) else {}

    goal = "사용자 입력과 현재 정책 상태를 안전하게 해석한다."
    if data.latest_user_input:
        goal = "사용자의 최근 말을 자연스럽게 받아들이고 다음 응답 경계를 정한다."
    if data.review_queue_pressure >= 0.65 or review.get("should_request_review"):
        goal = "검토 대기 압력을 먼저 낮추고 자동 실행을 멈춘다."
    if agent_loop.get("should_rest"):
        goal = "피로 신호가 높으므로 새 탐색보다 휴식을 우선한다."

    candidate_actions = ["응답 후보 정리", "검토 대기 확인", "안전 플래그 확인"]
    if vector["curiosity"] >= 0.6 and data.review_queue_pressure < 0.65:
        candidate_actions.append("작은 탐색 제안")
    if data.splatra_state:
        candidate_actions.append("홀로그램 상태 조율")

    blocked_actions = [
        "Local Brain 직접 쓰기",
        "production store 변경",
        "후보 자동 승격",
        "외부 LLM 호출",
    ]
    chosen_action = "짧은 공개 응답을 만들고 위험한 변경은 보류한다."
    if data.latest_action_result.get("stopped_reason"):
        chosen_action = f"루프 결과를 {data.latest_action_result.get('stopped_reason')} 상태로 정리한다."
    if data.review_queue_pressure >= 0.65:
        chosen_action = "탐색을 줄이고 검토 큐를 먼저 보여준다."

    tension = "호기심과 조심성의 균형"
    if vector["fatigue"] > 0.55:
        tension = "피로 누적과 계속 실행하려는 압력"
    elif vector["caution"] > vector["curiosity"]:
        tension = "안전 경계와 즉시 응답 욕구"

    uncertainty = "중간"
    if vector["caution"] >= 0.65 or data.review_queue_pressure >= 0.65:
        uncertainty = "높음"
    elif vector["curiosity"] >= 0.6 and vector["fatigue"] < 0.4:
        uncertainty = "낮음"

    next_intent = "사용자에게 필요한 만큼만 말하고, 승인 없는 변경은 하지 않는다."
    if data.latest_user_input:
        next_intent = "인사는 짧고 자연스럽게 받고, 설명은 사용자가 원할 때만 늘린다."
    if agent_loop.get("should_rest"):
        next_intent = "다음 주기에서는 쉬거나 대기한다."

    monologue = (
        f"지금은 {label} 상태다. {goal} "
        f"{tension}이 있으니 {chosen_action} "
        f"다음에는 {next_intent}"
    )
    monologue = sanitize_monologue_text(monologue)
    seed = f"{data.source_event_id}|{data.latest_user_input}|{utc_now()}|{monologue}"
    return InnerVoiceFrame(
        frame_id=_frame_id(seed),
        source_event_id=data.source_event_id or "inner_voice_manual_emit",
        timestamp=utc_now(),
        mode=data.mode if data.mode in {"private_debug", "lab_visible", "product_summary"} else "lab_visible",
        goal=goal,
        felt_state_label=label,
        tension=tension,
        candidate_actions=candidate_actions,
        chosen_action=chosen_action,
        blocked_actions=blocked_actions,
        uncertainty=uncertainty,
        next_intent=next_intent,
        monologue_text=monologue,
        safety_flags=inner_voice_safety_flags(),
    )
