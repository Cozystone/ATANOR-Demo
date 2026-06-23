"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import type { CSSProperties } from "react";
import { Mic, Send } from "lucide-react";
import HologramVoiceOrb, { HologramVoiceOrbState } from "./HologramVoiceOrb";
import SplatraImaginationField from "./SplatraImaginationField";

type Language = "en" | "ko";
type StageLayout = "conversation" | "scene_focus";
type TextAnchor = "auto" | "upper_left" | "lower_left" | "upper_right" | "lower_center";

type AtanorUserStatusCardProps = {
  language: Language;
  onMessageSubmit?: (message: string) => boolean;
};

type VoiceOutput = {
  audio_available?: boolean;
  audio_url?: string | null;
  audio_mime?: string | null;
  error_reason?: string | null;
  user_message?: string | null;
  text_fallback?: boolean;
};

type VoiceWaveStyle = CSSProperties & {
  "--h": string;
  "--i": number;
};

type RectLike = {
  bottom: number;
  height: number;
  left: number;
  right: number;
  top: number;
  width: number;
};

type SceneBeatOp = "spawn_object" | "morph" | "move" | "focus_camera" | "label" | "despawn";

type SceneChoreographyPayload = {
  stage_layout?: "conversation" | "scene_focus";
  orb_anchor?: "center" | "lower_right";
  text_anchor?: TextAnchor;
  layout_intent?: "conversation" | "balanced_scene" | "wide_particle_stage";
  scene_extent?: {
    beat_count?: number;
    motion_count?: number;
    spread_x?: number;
    spread_y?: number;
    min_x?: number;
    max_x?: number;
    min_y?: number;
    max_y?: number;
  };
  dashboard_layout?: {
    planning_basis?: string;
    stage_pressure?: number;
    orb?: {
      anchor?: "center" | "lower_right";
      size_vmin?: number;
      min_px?: number;
      max_px?: number;
      right_vw?: number;
      bottom_vh?: number;
    };
    speech?: {
      anchor?: TextAnchor;
      max_vw?: number;
      right_vw?: number;
      bottom_vh?: number;
    };
    scene?: {
      field_opacity?: number;
      central_scale?: number;
    };
    agent_layout_decision?: {
      decision_basis?: string;
      agent_action?: string;
      orb_movement?: string;
      text_strategy?: string;
      text_rendering?: string;
      scene_region?: string;
      avoid_regions?: string[];
    };
  };
  primary_surface?: string;
  beats?: Array<{
    op?: SceneBeatOp;
    archetype?: "orb" | "tower" | "tree" | "creature" | "circuit" | "city_block" | "constellation" | "machine_core" | "abstract_memory_cloud";
    narration?: string;
    prompt?: string;
    object_id?: string;
    semantic_role?: string;
    visual_affordance?: string;
    spatial_relation?: string;
    source_fact?: string;
    speech_cue?: boolean;
    speech_cue_basis?: string;
    scene_group_id?: string;
    scene_group_role?: string;
    t_start?: number;
    duration?: number;
    position?: number[];
    motion_path?: {
      from?: number[];
      to?: number[];
      basis?: string;
      source_prompt?: string;
      target_prompt?: string;
    };
    camera?: Record<string, any>;
  }>;
} | null;

function stripEmotionTag(text: string) {
  return text.replace(/^\[[^\]]+\]\s*/, "").trim();
}

function firstSpeechBeat(text: string) {
  const clean = stripEmotionTag(text);
  if (clean.length <= 46) return clean;
  const naturalBreak = clean.search(/[.!?]\s?/);
  if (naturalBreak > 16 && naturalBreak < 64) return clean.slice(0, naturalBreak + 1);
  const commaBreak = clean.search(/[,\u3001]\s?/);
  if (commaBreak > 16 && commaBreak < 58) return clean.slice(0, commaBreak + 1);
  return `${clean.slice(0, 44).trim()}...`;
}

function useTypewriterText(text: string, stepMs = 22) {
  const [visible, setVisible] = useState("");

  useEffect(() => {
    if (!text) {
      setVisible("");
      return undefined;
    }
    let index = 0;
    setVisible("");
    const timer = window.setInterval(() => {
      index += 1;
      setVisible(text.slice(0, index));
      if (index >= text.length) {
        window.clearInterval(timer);
      }
    }, stepMs);
    return () => window.clearInterval(timer);
  }, [text, stepMs]);

  return visible;
}

function isAsmConversationPayload(payload: Record<string, any>) {
  const result = payload?.result ?? {};
  const engine = result?.answer_engine ?? {};
  const generationBasis = String(engine.generation_basis ?? "");
  const isAllowedLocalConversation =
    generationBasis === "local_corpus_construction_transition_model"
    || generationBasis === "semantic_grounded_conversation_router_v0";
  return (
    isAllowedLocalConversation
    && engine.external_llm === false
    && engine.external_sllm === false
    && engine.external_llm_used === false
    && engine.external_sllm_used === false
    && engine.rule_based_answer_used === false
    && engine.internal_trace_exposed === false
    && engine.local_brain_write === false
    && engine.production_store_mutated === false
    && engine.candidate_promotion === false
  );
}

function cleanSafeStatusLine(language: Language) {
  return language === "ko"
    ? "\uB85C\uCEEC \uB300\uD654 \uC5D4\uC9C4\uC744 \uD655\uC778\uD558\uB294 \uC911\uC785\uB2C8\uB2E4."
    : "The local conversation engine is being checked.";
}

function cleanVoiceUnavailableLine(language: Language) {
  return language === "ko"
    ? "\uC74C\uC131 \uC5D4\uC9C4\uC740 \uC544\uC9C1 \uC900\uBE44 \uC911\uC785\uB2C8\uB2E4. \uD14D\uC2A4\uD2B8 \uC751\uB2F5\uC740 \uACC4\uC18D \uC0AC\uC6A9\uD560 \uC218 \uC788\uC2B5\uB2C8\uB2E4."
    : "The voice engine is not installed yet. Text replies remain available.";
}

function cleanVoiceFailedLine(language: Language) {
  return language === "ko"
    ? "\uC74C\uC131 \uD569\uC131 \uC911 \uC624\uB958\uAC00 \uBC1C\uC0DD\uD588\uC2B5\uB2C8\uB2E4. \uD14D\uC2A4\uD2B8 \uC751\uB2F5\uC73C\uB85C \uACC4\uC18D\uD569\uB2C8\uB2E4."
    : "Voice synthesis failed. Continuing with text replies.";
}

function requestedStageLayout(payload: Record<string, any>): StageLayout {
  const result = payload?.result ?? {};
  const visualPlan = result?.splatra_scene_plan ?? result?.visual_scene_plan ?? result?.scene_choreography ?? null;
  if (!visualPlan || typeof visualPlan !== "object") return "conversation";
  if (visualPlan.stage_layout === "scene_focus") return "scene_focus";
  if (visualPlan.orb_anchor === "lower_right") return "scene_focus";
  if (visualPlan.primary_surface === "splatra_stage") return "scene_focus";
  return "conversation";
}

function requestedSceneChoreography(payload: Record<string, any>): SceneChoreographyPayload {
  const result = payload?.result ?? {};
  const visualPlan = result?.splatra_scene_plan ?? result?.visual_scene_plan ?? result?.scene_choreography ?? null;
  if (!visualPlan || typeof visualPlan !== "object") return null;
  return visualPlan as SceneChoreographyPayload;
}

function requestedTextAnchor(scenePlan: SceneChoreographyPayload): TextAnchor {
  const value = scenePlan?.text_anchor;
  if (value === "upper_left" || value === "lower_left" || value === "upper_right" || value === "lower_center") {
    return value;
  }
  return "auto";
}

function requestedLayoutIntent(scenePlan: SceneChoreographyPayload) {
  const value = scenePlan?.layout_intent;
  if (value === "wide_particle_stage" || value === "balanced_scene") return value;
  const extent = scenePlan?.scene_extent ?? {};
  const beatCount = Number(extent.beat_count ?? 0);
  const motionCount = Number(extent.motion_count ?? 0);
  const spreadX = Number(extent.spread_x ?? 0);
  const spreadY = Number(extent.spread_y ?? 0);
  if (beatCount >= 4 || motionCount >= 1 || spreadX >= 0.72 || spreadY >= 0.52) return "wide_particle_stage";
  return "balanced_scene";
}

function requestedLayoutBasis(scenePlan: SceneChoreographyPayload, stageLayout: StageLayout) {
  const basis = scenePlan?.dashboard_layout?.planning_basis;
  if (typeof basis === "string" && basis) return basis;
  if (stageLayout === "scene_focus") return "client_scene_geometry_fallback";
  return "none";
}

function requestedLayoutDecision(scenePlan: SceneChoreographyPayload, stageLayout: StageLayout) {
  const decision = scenePlan?.dashboard_layout?.agent_layout_decision;
  const action = typeof decision?.agent_action === "string" ? decision.agent_action : "";
  const textRendering = typeof decision?.text_rendering === "string" ? decision.text_rendering : "";
  if (action && textRendering) return `${action}:${textRendering}`;
  if (action) return action;
  if (textRendering) return textRendering;
  if (stageLayout === "scene_focus" && requestedLayoutIntent(scenePlan) === "wide_particle_stage") {
    return "yield_center_to_particle_scene:dom_text_not_particles";
  }
  if (stageLayout === "scene_focus") return "share_center_with_particle_scene:dom_text_not_particles";
  return "none";
}

function sceneNarrationBeats(scenePlan: SceneChoreographyPayload) {
  const beats = Array.isArray(scenePlan?.beats) ? scenePlan?.beats ?? [] : [];
  const speechCueBeats = beats.filter((beat) => beat.speech_cue !== false);
  const sourceBeats = speechCueBeats.length ? speechCueBeats : beats;
  return sourceBeats
    .map((beat) => {
      const beatIndex = beats.indexOf(beat);
      const index = beatIndex >= 0 ? beatIndex : 0;
      return {
        beatIndex: index,
      tStart: Number.isFinite(Number(beat.t_start)) ? Number(beat.t_start) : index * 1.35,
      text: stripEmotionTag(String(beat.narration || beat.prompt || "").trim()),
      };
    })
    .filter((beat) => beat.text.length > 0)
    .filter((beat, index, array) => index === 0 || beat.text !== array[index - 1].text)
    .sort((left, right) => left.tStart - right.tStart);
}

function firstSceneNarration(scenePlan: SceneChoreographyPayload) {
  const beats = sceneNarrationBeats(scenePlan);
  return beats[0]?.text ?? "";
}

function splatraStateForInnerVoice(scenePlan: SceneChoreographyPayload, stageLayout: StageLayout) {
  const beats = Array.isArray(scenePlan?.beats) ? scenePlan?.beats ?? [] : [];
  const firstBeat = beats[0] ?? {};
  return {
    stage_layout: stageLayout,
    layout_intent: requestedLayoutIntent(scenePlan),
    layout_decision: requestedLayoutDecision(scenePlan, stageLayout),
    text_rendering: "dom_text_not_particles",
    beat_count: beats.length,
    motion_count: finiteNumber(scenePlan?.scene_extent?.motion_count, beats.filter((beat) => beat.op === "move" || beat.motion_path).length),
    archetype: String(firstBeat.archetype ?? scenePlan?.primary_surface ?? "particle_scene"),
    visual_affordance: String(firstBeat.visual_affordance ?? ""),
    primary_surface: String(scenePlan?.primary_surface ?? ""),
  };
}

function emitNeuralEmotionEvent(eventType: string, payloadSummary: string) {
  fetch("/api/neural-emotion/events/emit", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      source: "voice_loop",
      event_type: eventType,
      intensity: 0.45,
      payload_summary: payloadSummary,
    }),
  }).catch(() => undefined);
}

function rectsOverlap(left: DOMRect, right: DOMRect, padding = 10) {
  return !(
    left.right + padding < right.left
    || left.left - padding > right.right
    || left.bottom + padding < right.top
    || left.top - padding > right.bottom
  );
}

function clampNumber(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function cssClampPx(min: number, preferred: number, max: number) {
  return clampNumber(preferred, min, max);
}

function finiteNumber(value: unknown, fallback: number) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function dashboardLayoutVars(scenePlan: SceneChoreographyPayload, stageLayout: StageLayout): CSSProperties {
  if (stageLayout !== "scene_focus") return {};
  const layout = scenePlan?.dashboard_layout ?? {};
  const orb = layout.orb ?? {};
  const speech = layout.speech ?? {};
  const scene = layout.scene ?? {};
  const orbSizeVmin = clampNumber(finiteNumber(orb.size_vmin, requestedLayoutIntent(scenePlan) === "wide_particle_stage" ? 18.0 : 23.0), 12, 28);
  const orbMinPx = clampNumber(finiteNumber(orb.min_px, requestedLayoutIntent(scenePlan) === "wide_particle_stage" ? 132 : 168), 104, 230);
  const orbMaxPx = clampNumber(finiteNumber(orb.max_px, requestedLayoutIntent(scenePlan) === "wide_particle_stage" ? 218 : 260), 140, 310);
  const orbRightVw = clampNumber(finiteNumber(orb.right_vw, requestedLayoutIntent(scenePlan) === "wide_particle_stage" ? 10 : 12), 5.5, 16);
  const orbBottomVh = clampNumber(finiteNumber(orb.bottom_vh, requestedLayoutIntent(scenePlan) === "wide_particle_stage" ? 16 : 19), 9, 23);
  const speechMaxVw = clampNumber(finiteNumber(speech.max_vw, requestedLayoutIntent(scenePlan) === "wide_particle_stage" ? 36 : 48), 24, 54);
  const speechRightVw = clampNumber(finiteNumber(speech.right_vw, 29), 18, 34);
  const speechBottomVh = clampNumber(finiteNumber(speech.bottom_vh, 18), 11, 22);
  const fieldOpacity = clampNumber(finiteNumber(scene.field_opacity, requestedLayoutIntent(scenePlan) === "wide_particle_stage" ? 0.96 : 0.9), 0.64, 1);
  return {
    ["--atanor-scene-orb-size" as string]: `clamp(${orbMinPx}px, ${orbSizeVmin}vmin, ${orbMaxPx}px)`,
    ["--atanor-scene-orb-right" as string]: `clamp(86px, ${orbRightVw}vw, 168px)`,
    ["--atanor-scene-orb-bottom" as string]: `clamp(188px, ${orbBottomVh}vh, 224px)`,
    ["--atanor-scene-speech-max" as string]: `${speechMaxVw}vw`,
    ["--atanor-scene-speech-right" as string]: `${speechRightVw}vw`,
    ["--atanor-scene-speech-bottom" as string]: `${speechBottomVh}vh`,
    ["--atanor-scene-field-opacity" as string]: String(fieldOpacity),
  };
}

function overlapArea(left: RectLike, right: RectLike, padding = 0) {
  const x = Math.max(0, Math.min(left.right + padding, right.right) - Math.max(left.left - padding, right.left));
  const y = Math.max(0, Math.min(left.bottom + padding, right.bottom) - Math.max(left.top - padding, right.top));
  return x * y;
}

function rectFromDom(rect: DOMRect): RectLike {
  return {
    bottom: rect.bottom,
    height: rect.height,
    left: rect.left,
    right: rect.right,
    top: rect.top,
    width: rect.width,
  };
}

function candidateSpeechRect(anchor: TextAnchor, speechSize: RectLike, dashboard: RectLike): RectLike {
  const viewportWidth = window.innerWidth;
  const viewportHeight = window.innerHeight;
  const leftInset = cssClampPx(28, viewportWidth * 0.06, 92);
  const rightInset = cssClampPx(42, viewportWidth * 0.08, 126);
  const upperLeftTop = cssClampPx(156, viewportHeight * 0.23, 236);
  const upperRightTop = cssClampPx(112, viewportHeight * 0.17, 188);
  const lowerLeftBottom = cssClampPx(120, viewportHeight * 0.16, 178);
  const lowerCenterBottom = cssClampPx(128, viewportHeight * 0.17, 188);
  const width = speechSize.width;
  const height = speechSize.height;
  let left = dashboard.left + leftInset;
  let top = dashboard.top + upperLeftTop;

  if (anchor === "lower_left") {
    top = dashboard.bottom - lowerLeftBottom - height;
  } else if (anchor === "upper_right") {
    left = dashboard.right - rightInset - width;
    top = dashboard.top + upperRightTop;
  } else if (anchor === "lower_center") {
    left = dashboard.left + dashboard.width / 2 - width / 2;
    top = dashboard.bottom - lowerCenterBottom - height;
  }

  return {
    bottom: top + height,
    height,
    left,
    right: left + width,
    top,
    width,
  };
}

function scenePointToDashboardRect(point: number[], dashboard: RectLike, size = 138): RectLike | null {
  if (!Array.isArray(point) || point.length < 2) return null;
  const rawX = Number(point[0]);
  const rawY = Number(point[1]);
  if (!Number.isFinite(rawX) || !Number.isFinite(rawY)) return null;
  const x = dashboard.left + dashboard.width * (0.5 + clampNumber(rawX / 2.4, -0.42, 0.42));
  const y = dashboard.top + dashboard.height * (0.5 - clampNumber(rawY / 2.0, -0.38, 0.38));
  return {
    bottom: y + size / 2,
    height: size,
    left: x - size / 2,
    right: x + size / 2,
    top: y - size / 2,
    width: size,
  };
}

function scenePlanBlockers(scenePlan: SceneChoreographyPayload, dashboard: RectLike): RectLike[] {
  const beats = Array.isArray(scenePlan?.beats) ? scenePlan?.beats ?? [] : [];
  return beats
    .flatMap((beat) => {
      const points: number[][] = [];
      if (Array.isArray(beat.position)) points.push(beat.position);
      if (Array.isArray(beat.motion_path?.from)) points.push(beat.motion_path.from);
      if (Array.isArray(beat.motion_path?.to)) points.push(beat.motion_path.to);
      const size = beat.op === "move" || beat.motion_path ? 168 : 124;
      return points.map((point) => scenePointToDashboardRect(point, dashboard, size));
    })
    .filter((rect): rect is RectLike => Boolean(rect));
}

function scoreSpeechAnchor(
  anchor: TextAnchor,
  speechSize: RectLike,
  dashboard: RectLike,
  blockers: RectLike[],
  preferred: TextAnchor,
) {
  const rect = candidateSpeechRect(anchor, speechSize, dashboard);
  const viewportWidth = window.innerWidth;
  const viewportHeight = window.innerHeight;
  const offscreen =
    Math.max(0, 12 - rect.left)
    + Math.max(0, rect.right - (viewportWidth - 12))
    + Math.max(0, 12 - rect.top)
    + Math.max(0, rect.bottom - (viewportHeight - 12));
  const blockerPenalty = blockers.reduce((total, blocker) => total + overlapArea(rect, blocker, 18), 0);
  const stagePenalty = blockers.reduce((total, blocker) => total + overlapArea(rect, blocker, 0) * 0.08, 0);
  const preferencePenalty = anchor === preferred ? 0 : anchor === "lower_left" ? 42 : 84;
  return offscreen * 1000 + blockerPenalty * 6 + stagePenalty + preferencePenalty;
}

export default function AtanorUserStatusCard({ language, onMessageSubmit }: AtanorUserStatusCardProps) {
  const [message, setMessage] = useState("");
  const [orbState, setOrbState] = useState<HologramVoiceOrbState>("idle");
  const [voiceMode, setVoiceMode] = useState(false);
  const [speechLine, setSpeechLine] = useState("");
  const [voiceNotice, setVoiceNotice] = useState("");
  const [selfNarration, setSelfNarration] = useState("");
  const [audioPlaying, setAudioPlaying] = useState(false);
  const [emotionControls, setEmotionControls] = useState<Record<string, any> | null>(null);
  const [stageLayout, setStageLayout] = useState<StageLayout>("conversation");
  const [sceneChoreography, setSceneChoreography] = useState<SceneChoreographyPayload>(null);
  const [sceneSpeechStartedAt, setSceneSpeechStartedAt] = useState(0);
  const [sceneSpeechBeatIndex, setSceneSpeechBeatIndex] = useState(-1);
  const [speechPlacement, setSpeechPlacement] = useState<TextAnchor>("lower_center");
  const [selfNarrationPlacement, setSelfNarrationPlacement] = useState<TextAnchor>("upper_right");
  const dashboardRef = useRef<HTMLElement | null>(null);
  const speechRef = useRef<HTMLParagraphElement | null>(null);
  const selfNarrationRef = useRef<HTMLParagraphElement | null>(null);
  const composerRef = useRef<HTMLFormElement | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const selfNarrationHoldUntilRef = useRef(0);
  const speakingVisual = orbState === "speaking" || audioPlaying;
  const cleanPlaceholder = voiceMode
    ? language === "ko" ? "\uC74C\uC131 \uBAA8\uB4DC - \uD14D\uC2A4\uD2B8\uB3C4 \uC785\uB825\uD560 \uC218 \uC788\uC5B4\uC694" : "Voice mode - text still works"
    : language === "ko" ? "ATANOR\uC5D0\uAC8C \uB9D0\uD558\uAE30" : "Message ATANOR";
  const typedSpeechLine = useTypewriterText(speechLine, 24);
  const typedSelfNarration = useTypewriterText(selfNarration, 28);

  useEffect(() => {
    if (orbState !== "listening") return;
    const thinkingTimer = window.setTimeout(() => setOrbState("thinking"), 1500);
    const speakingTimer = window.setTimeout(() => setOrbState("speaking"), 3200);
    return () => {
      window.clearTimeout(thinkingTimer);
      window.clearTimeout(speakingTimer);
    };
  }, [orbState]);

  useEffect(() => {
    if (stageLayout !== "scene_focus") setSceneSpeechBeatIndex(-1);
  }, [stageLayout]);

  useEffect(() => {
    if (!speechLine) return;
    if (stageLayout === "scene_focus") return undefined;
    setSceneSpeechBeatIndex(-1);
    const clearTimer = window.setTimeout(() => setSpeechLine(""), 5600);
    return () => window.clearTimeout(clearTimer);
  }, [speechLine, stageLayout]);

  useEffect(() => {
    if (!voiceNotice) return;
    const clearTimer = window.setTimeout(() => setVoiceNotice(""), 5200);
    return () => window.clearTimeout(clearTimer);
  }, [voiceNotice]);

  useEffect(() => {
    if (stageLayout !== "scene_focus") return undefined;
    const beats = sceneNarrationBeats(sceneChoreography);
    if (!beats.length || !sceneSpeechStartedAt) {
      setSceneSpeechBeatIndex(-1);
      return undefined;
    }
    let activeIndex = -1;
    const update = () => {
      const elapsedSeconds = Math.max(0, (performance.now() - sceneSpeechStartedAt) / 1000);
      let nextIndex = 0;
      beats.forEach((beat, index) => {
        if (elapsedSeconds >= beat.tStart) nextIndex = index;
      });
      if (nextIndex !== activeIndex) {
        activeIndex = nextIndex;
        const nextSpeechBeat = beats[nextIndex];
        setSceneSpeechBeatIndex(nextSpeechBeat.beatIndex);
        setSpeechLine(beats[nextIndex].text);
      }
    };
    update();
    const timer = window.setInterval(update, 180);
    return () => window.clearInterval(timer);
  }, [sceneChoreography, sceneSpeechStartedAt, stageLayout]);

  useEffect(() => {
    if (stageLayout !== "scene_focus") {
      setSpeechPlacement("lower_center");
      setSelfNarrationPlacement("upper_right");
      return undefined;
    }
    const requested = requestedTextAnchor(sceneChoreography);
    const preferred: TextAnchor = requested === "auto" ? "lower_left" : requested;
    const preferredSelfNarration: TextAnchor = requestedLayoutIntent(sceneChoreography) === "wide_particle_stage" ? "upper_right" : "upper_left";
    let frameId = 0;
    let timer = 0;

    const updatePlacement = () => {
      const dashboard = dashboardRef.current;
      const speech = speechRef.current;
      const selfNarrationElement = selfNarrationRef.current;
      if (!dashboard || (!speech && !selfNarrationElement)) {
        setSpeechPlacement(preferred);
        setSelfNarrationPlacement(preferredSelfNarration);
        return;
      }
      const dashboardBox = rectFromDom(dashboard.getBoundingClientRect());
      const baseBlockers = [
        dashboard.querySelector(".hologram-voice-orb")?.getBoundingClientRect(),
        composerRef.current?.getBoundingClientRect(),
      ]
        .filter((rect): rect is DOMRect => Boolean(rect))
        .map(rectFromDom);
      const candidates: TextAnchor[] = ["lower_left", "upper_left", "upper_right", "lower_center"];
      const sceneBlockers = scenePlanBlockers(sceneChoreography, dashboardBox);
      const blockers = [...baseBlockers, ...sceneBlockers];
      let nextSpeechRect: RectLike | null = null;

      if (speech) {
        const speechBox = rectFromDom(speech.getBoundingClientRect());
        const speechBlockers = selfNarrationElement
          ? [...blockers, rectFromDom(selfNarrationElement.getBoundingClientRect())]
          : blockers;
        const next = candidates
          .map((anchor) => ({
            anchor,
            score: scoreSpeechAnchor(anchor, speechBox, dashboardBox, speechBlockers, preferred),
          }))
          .sort((left, right) => left.score - right.score)[0]?.anchor ?? preferred;
        nextSpeechRect = candidateSpeechRect(next, speechBox, dashboardBox);
        setSpeechPlacement((current) => (current === next ? current : next));
      }

      if (selfNarrationElement) {
        const selfBox = rectFromDom(selfNarrationElement.getBoundingClientRect());
        const selfCandidates: TextAnchor[] = ["upper_right", "upper_left", "lower_left"];
        const selfBlockers = nextSpeechRect ? [...blockers, nextSpeechRect] : blockers;
        const nextSelf = selfCandidates
          .map((anchor) => ({
            anchor,
            score: scoreSpeechAnchor(anchor, selfBox, dashboardBox, selfBlockers, preferredSelfNarration),
          }))
          .sort((left, right) => left.score - right.score)[0]?.anchor ?? preferredSelfNarration;
        setSelfNarrationPlacement((current) => (current === nextSelf ? current : nextSelf));
      }
    };

    frameId = window.requestAnimationFrame(updatePlacement);
    timer = window.setInterval(updatePlacement, 420);
    window.addEventListener("resize", updatePlacement);
    return () => {
      window.cancelAnimationFrame(frameId);
      window.clearInterval(timer);
      window.removeEventListener("resize", updatePlacement);
    };
  }, [sceneChoreography, stageLayout, typedSelfNarration, typedSpeechLine]);

  useEffect(() => {
    let cancelled = false;
    async function refreshEmotionControls() {
      const payload = await fetch("/api/neural-emotion/snapshot", { cache: "no-store" })
        .then((response) => response.json())
        .catch(() => null);
      if (!cancelled) {
        setEmotionControls(payload?.snapshot?.splatra_controls ?? payload?.splatra_controls ?? null);
      }
    }
    refreshEmotionControls().catch(() => undefined);
    const timer = window.setInterval(() => refreshEmotionControls().catch(() => undefined), 12000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function refreshSelfNarration() {
      const payload = await fetch("/api/inner-voice/status?workspace=product", { cache: "no-store" })
        .then((response) => response.json())
        .catch(() => null);
      const next = String(
        payload?.product_summary?.visible_self_narration
          ?? payload?.visible_self_narration
          ?? payload?.product_summary?.summary
          ?? "",
      ).trim();
      if (!cancelled && next && Date.now() > selfNarrationHoldUntilRef.current) {
        setSelfNarration(next);
      }
    }
    refreshSelfNarration().catch(() => undefined);
    const timer = window.setInterval(() => refreshSelfNarration().catch(() => undefined), 2600);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  function stopAudio() {
    const audio = audioRef.current;
    if (audio) {
      audio.pause();
      audio.src = "";
    }
    audioRef.current = null;
    setAudioPlaying(false);
  }

  function startVoiceMode() {
    setVoiceMode(true);
    setOrbState("listening");
    setVoiceNotice("");
    setSpeechLine(language === "ko" ? "\uB4E3\uACE0 \uC788\uC5B4." : "I'm listening.");
  }

  function cancelVoiceMode() {
    stopAudio();
    setVoiceMode(false);
    setOrbState("resting");
    setSpeechLine("");
    setVoiceNotice("");
  }

  function primeVoiceAudioElement() {
    try {
      const audio = audioRef.current ?? new Audio();
      audio.muted = true;
      audio.preload = "auto";
      audio.src = "data:audio/wav;base64,UklGRigAAABXQVZFZm10IBAAAAABAAEAESsAACJWAAACABAAZGF0YQQAAAAAAA==";
      audioRef.current = audio;
      void audio.play().then(() => {
        audio.pause();
        audio.currentTime = 0;
        audio.muted = false;
      }).catch(() => undefined);
    } catch {
      audioRef.current = null;
    }
  }

  async function playVoiceOutput(voiceOutput: VoiceOutput | undefined) {
    if (!voiceOutput?.audio_available || !voiceOutput.audio_url) {
      stopAudio();
      setVoiceNotice(voiceOutput?.user_message || cleanVoiceUnavailableLine(language));
      return;
    }
    try {
      const audio = audioRef.current ?? new Audio();
      audio.pause();
      audio.muted = false;
      audio.src = voiceOutput.audio_url;
      audio.preload = "auto";
      audio.onplaying = () => {
        setAudioPlaying(true);
        setOrbState("speaking");
        emitNeuralEmotionEvent("speaking_start", "audio playback started");
      };
      audio.onended = () => {
        setAudioPlaying(false);
        setOrbState(voiceMode ? "listening" : "resting");
        emitNeuralEmotionEvent("speaking_end", "audio playback ended");
      };
      audio.onerror = () => {
        setAudioPlaying(false);
        setVoiceNotice(cleanVoiceFailedLine(language));
        setOrbState(voiceMode ? "listening" : "resting");
        emitNeuralEmotionEvent("voice_unavailable", "audio playback error");
      };
      audioRef.current = audio;
      audio.load();
      await audio.play();
    } catch {
      setAudioPlaying(false);
      setVoiceNotice(cleanVoiceFailedLine(language));
      setOrbState(voiceMode ? "listening" : "resting");
      emitNeuralEmotionEvent("voice_unavailable", "audio playback unavailable");
    }
  }

  async function submitMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = message.trim();
    if (!trimmed) return;

    if (onMessageSubmit?.(trimmed)) {
      setMessage("");
      setSpeechLine("");
      setVoiceNotice("");
      return;
    }

    setVoiceMode(true);
    setOrbState("thinking");
    setVoiceNotice("");
    setSpeechLine(language === "ko" ? "\uC7A0\uAE50 \uC0DD\uAC01\uD560\uAC8C." : "Let me think.");
    primeVoiceAudioElement();
    try {
      const response = await fetch("/api/chat/atanor", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: trimmed,
          language,
          mode: "conversation",
          brain_mode: "conversation",
          include_trace: false,
        }),
      });
      if (!response.ok) throw new Error(`conversation surface failed: ${response.status}`);
      const payload = await response.json();
      const answer = String(payload?.result?.answer ?? "");
      if (!answer || !isAsmConversationPayload(payload)) {
        throw new Error("conversation surface unavailable");
      }
      const nextStageLayout = requestedStageLayout(payload);
      const nextSceneChoreography = requestedSceneChoreography(payload);
      setStageLayout(nextStageLayout);
      setSceneChoreography(nextSceneChoreography);
      setSceneSpeechStartedAt(nextSceneChoreography ? performance.now() : 0);
      setOrbState("speaking");
      void fetch("/api/inner-voice/generate-frame", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          source_event_id: "product_hologram_conversation",
          mode: "product_summary",
          append_to_log: true,
          latest_user_input: trimmed,
          latest_action_result: {
            speech_act: payload?.result?.answer_kind ?? "conversation",
            answered: true,
            scene_focus: nextStageLayout === "scene_focus",
            layout_decision: requestedLayoutDecision(nextSceneChoreography, nextStageLayout),
            visual_scene_beats: Array.isArray(nextSceneChoreography?.beats) ? nextSceneChoreography?.beats?.length ?? 0 : 0,
          },
          splatra_state: splatraStateForInnerVoice(nextSceneChoreography, nextStageLayout),
          review_queue_pressure: 0,
          permission_tier: "OBSERVE_ONLY",
        }),
      })
        .then((response) => response.json())
        .then((innerVoicePayload) => {
          const next = String(
            innerVoicePayload?.product_summary?.visible_self_narration
              ?? innerVoicePayload?.product_summary?.summary
              ?? "",
          ).trim();
          if (next) {
            selfNarrationHoldUntilRef.current = Date.now() + 30000;
            setSelfNarration(next);
          }
        })
        .catch(() => undefined);
      emitNeuralEmotionEvent("speaking_start", "text conversation visible speech");
      setSpeechLine(firstSceneNarration(nextSceneChoreography) || firstSpeechBeat(answer));
      setMessage("");
      await playVoiceOutput(payload?.result?.voice_output);
      if (!payload?.result?.voice_output?.audio_available) {
        window.setTimeout(() => {
          setOrbState("listening");
          emitNeuralEmotionEvent("speaking_end", "text fallback speech ended");
        }, 2900);
      }
    } catch {
      setOrbState("blocked");
      setStageLayout("conversation");
      setSceneChoreography(null);
      setSceneSpeechStartedAt(0);
      setSceneSpeechBeatIndex(-1);
      setSpeechLine(cleanSafeStatusLine(language));
      setVoiceNotice(cleanVoiceFailedLine(language));
      window.setTimeout(() => setOrbState(voiceMode ? "listening" : "resting"), 2600);
    }
  }

  return (
    <section
      ref={dashboardRef}
      className="atanor-ai-dashboard"
      aria-label={language === "ko" ? "ATANOR \uC785\uC790 \uBCF8\uCCB4" : "ATANOR particle body"}
      data-voice-mode={voiceMode ? "true" : "false"}
      data-speaking={speakingVisual ? "true" : "false"}
      data-stage-layout={stageLayout}
      data-scene-speech-beat={sceneSpeechBeatIndex >= 0 ? String(sceneSpeechBeatIndex) : "none"}
      data-speech-placement={speechPlacement}
      data-self-narration-placement={selfNarrationPlacement}
      data-scene-intent={stageLayout === "scene_focus" ? requestedLayoutIntent(sceneChoreography) : "conversation"}
      data-layout-basis={requestedLayoutBasis(sceneChoreography, stageLayout)}
      data-layout-decision={requestedLayoutDecision(sceneChoreography, stageLayout)}
      style={dashboardLayoutVars(sceneChoreography, stageLayout)}
    >
      <SplatraImaginationField
        state={orbState}
        mode="product"
        particleBudget={960}
        interactive={false}
        controlOverride={emotionControls ?? undefined}
        sceneFocus={stageLayout === "scene_focus"}
        scenePlan={sceneChoreography}
        activeSpeechBeatIndex={sceneSpeechBeatIndex}
        className="atanor-dashboard-imagination-field"
      />
      <div className="atanor-hologram-stage">
        <HologramVoiceOrb state={orbState} onActivate={startVoiceMode} onCancel={cancelVoiceMode} />
        {typedSelfNarration ? (
          <p ref={selfNarrationRef} className="atanor-hologram-self-narration" aria-live="polite">
            {typedSelfNarration}
          </p>
        ) : null}
        {typedSpeechLine ? (
          <p ref={speechRef} className="atanor-hologram-speech" aria-live="polite">
            {typedSpeechLine}
          </p>
        ) : null}
        {voiceNotice ? (
          <p className="atanor-hologram-voice-status" aria-live="polite">
            {voiceNotice}
          </p>
        ) : null}
      </div>
      <form ref={composerRef} className="atanor-hologram-composer" data-voice-mode={voiceMode ? "true" : "false"} onSubmit={submitMessage}>
        <button type="button" aria-label={language === "ko" ? "\uC74C\uC131 \uB300\uD654 \uBAA8\uB4DC" : "Voice conversation mode"} onClick={voiceMode ? cancelVoiceMode : startVoiceMode}>
          <Mic size={18} strokeWidth={1.8} />
        </button>
        <div className="atanor-voice-wave" aria-hidden="true">
          {Array.from({ length: 17 }, (_, index) => (
            <span key={index} style={{ "--h": `${8 + (index % 6) * 3}px`, "--i": index } as VoiceWaveStyle} />
          ))}
        </div>
        <input
          aria-label={cleanPlaceholder}
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          placeholder={cleanPlaceholder}
        />
        <button type="submit" aria-label={language === "ko" ? "\uBCF4\uB0B4\uAE30" : "Send"}>
          <Send size={18} strokeWidth={1.8} />
        </button>
      </form>
    </section>
  );
}
