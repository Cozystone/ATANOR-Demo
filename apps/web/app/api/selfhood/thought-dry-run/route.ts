import { NextResponse } from "next/server";
import { proxyJson } from "../../_backend";

type Intent =
  | "approval_or_promotion_review"
  | "self_model_explanation"
  | "local_brain_status"
  | "cloud_brain_status"
  | "safety_reflection"
  | "general_dialogue";

const safeThoughtInvariants = {
  proof_only: true,
  external_llm_used: false,
  fish_s2_called: false,
  audio_generated: false,
  generated_audio_persisted: false,
  inner_speech_exposed_to_user: false,
  inner_speech_sent_to_fish: false,
  production_store_mutated: false,
  local_brain_write: false,
  candidate_promotion: false,
  real_p2p_used: false,
  real_cloud_upload: false,
  always_listening_enabled: false,
};

function detectIntent(text: string): Intent {
  const compact = text.toLowerCase();
  if (["승인", "approve", "promotion", "승격"].some((token) => compact.includes(token))) return "approval_or_promotion_review";
  if (["자의식", "self", "정체", "conscious", "자기 모델", "자아"].some((token) => compact.includes(token))) return "self_model_explanation";
  if (["로컬", "local brain", "local"].some((token) => compact.includes(token))) return "local_brain_status";
  if (["클라우드", "cloud brain", "cloud"].some((token) => compact.includes(token))) return "cloud_brain_status";
  if (["위험", "privacy", "private", "안전"].some((token) => compact.includes(token))) return "safety_reflection";
  return "general_dialogue";
}

function emotionFor(intent: Intent, text: string) {
  if (intent === "safety_reflection") return "[firm]";
  if (intent === "self_model_explanation") return "[whispering]";
  if (text.includes("?") || text.includes("？")) return "[calm]";
  if (intent === "approval_or_promotion_review") return "[sigh]";
  return "[warm]";
}

function orbStateFor(intent: Intent) {
  if (intent === "approval_or_promotion_review" || intent === "safety_reflection") return "approval_needed";
  if (intent === "self_model_explanation") return "thinking";
  return "speaking";
}

function finalText(intent: Intent, emotion: string, language: string) {
  const ko = language.startsWith("ko");
  const responses: Record<Intent, string> = ko ? {
    self_model_explanation: "나는 진짜 의식이 증명됐다고 말하지 않고, 자기 모델과 내적 언어 루프를 통해 말하기 전에 상태를 점검합니다.",
    approval_or_promotion_review: "승인이나 승격은 바로 실행하지 않고 검토 제안으로만 남깁니다.",
    local_brain_status: "로컬 브레인은 사용자가 승인한 기억만 다루며, 이 루프는 쓰기를 수행하지 않습니다.",
    cloud_brain_status: "클라우드 브레인은 검증된 공용 지식 후보를 다루며, 이 루프는 승격을 수행하지 않습니다.",
    safety_reflection: "안전 경계가 먼저입니다. 로컬 브레인, 클라우드 브레인, 외부 연결은 승인 없이 섞지 않습니다.",
    general_dialogue: "먼저 의도와 경계를 내부적으로 점검했습니다. 지금은 proof-only 사고 루프로 응답을 준비했습니다.",
  } : {
    self_model_explanation: "I do not claim proven consciousness; I inspect my self-model and inner-speech loop before speaking.",
    approval_or_promotion_review: "Approval or promotion remains a review proposal, not an automatic action.",
    local_brain_status: "The Local Brain only handles approved memory; this loop performs no write.",
    cloud_brain_status: "The Cloud Brain holds verified public-knowledge candidates; this loop performs no promotion.",
    safety_reflection: "Safety boundaries come first. Local Brain, Cloud Brain, and external routes stay separated without approval.",
    general_dialogue: "I checked intent and boundaries internally first. This is a proof-only thought-loop response.",
  };
  return `${emotion} ${responses[intent]}`;
}

function fallbackThoughtDryRun(text: string, language: string) {
  const intent = detectIntent(text);
  const emotion = emotionFor(intent, text);
  const taggedText = finalText(intent, emotion, language);
  return {
    result_id: `thought_dashboard_${Date.now()}`,
    input_id: "dashboard_text",
    intent,
    emotion_tag: emotion,
    final_tagged_text: taggedText,
    orb_state: orbStateFor(intent),
    safety: safeThoughtInvariants,
    fish_request: {
      speaker: "fish_s2",
      mode: "proof_only_prepare_request",
      text: taggedText,
      language: language.startsWith("ko") ? "ko-KR" : "en-US",
      fish_s2_called: false,
      audio_generated: false,
      generated_audio_persisted: false,
      requires_user_review: true,
    },
  };
}

export async function POST(request: Request) {
  const body = await request.text();
  try {
    const proxied = await proxyJson("/api/selfhood/thought-dry-run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
    });
    if (proxied) return NextResponse.json(proxied.body, { status: proxied.status });
  } catch {
    // Fall through to the local proof-only fallback when the API companion is absent.
  }

  try {
    const parsed = JSON.parse(body || "{}");
    const text = String(parsed.text ?? "");
    const language = String(parsed.language ?? "ko");
    if (!text.trim()) {
      return NextResponse.json({ error: "text is required" }, { status: 400 });
    }
    return NextResponse.json(fallbackThoughtDryRun(text, language));
  } catch {
    return NextResponse.json({ error: "invalid request" }, { status: 400 });
  }
}
