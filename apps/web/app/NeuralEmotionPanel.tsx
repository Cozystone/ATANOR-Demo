"use client";

import { useEffect, useState } from "react";

type AnyRecord = Record<string, any>;

const eventButtons = [
  "greeting",
  "novelty_found",
  "tool_success",
  "tool_failure",
  "unsafe_request",
  "approval_granted",
  "approval_denied",
  "resting",
] as const;

function flagLine(flags: AnyRecord | undefined) {
  if (!flags) return "loading";
  return [
    `external_llm=${String(flags.external_llm)}`,
    `real_emotion_claim=${String(flags.real_emotion_claim)}`,
    `local_brain_write=${String(flags.local_brain_write)}`,
    `production_store_mutated=${String(flags.production_store_mutated)}`,
  ].join(" / ");
}

function Gauge({ label, value, min = 0, max = 1 }: { label: string; value: number; min?: number; max?: number }) {
  const normalized = Math.max(0, Math.min(1, (Number(value) - min) / (max - min)));
  return (
    <span className="agentic-os-neural-gauge">
      <small>{label}</small>
      <i><b style={{ width: `${Math.round(normalized * 100)}%` }} /></i>
      <strong>{Number(value).toFixed(3)}</strong>
    </span>
  );
}

export default function NeuralEmotionPanel() {
  const [snapshot, setSnapshot] = useState<AnyRecord | null>(null);
  const [lastEvent, setLastEvent] = useState<string>("none");

  async function refresh() {
    const payload = await fetch("/api/neural-emotion/snapshot", { cache: "no-store" })
      .then((response) => response.json())
      .catch((error) => ({ available: false, reason: String(error) }));
    setSnapshot(payload);
  }

  async function sendEvent(eventType: string) {
    const payload = await fetch("/api/neural-emotion/event", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ event_type: eventType, intensity: 1.0 }),
    })
      .then((response) => response.json())
      .catch((error) => ({ available: false, reason: String(error) }));
    setSnapshot(payload);
    setLastEvent(eventType);
  }

  async function decay() {
    const payload = await fetch("/api/neural-emotion/decay", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ half_life_seconds: 480 }),
    })
      .then((response) => response.json())
      .catch((error) => ({ available: false, reason: String(error) }));
    setSnapshot(payload);
    setLastEvent("decay");
  }

  useEffect(() => {
    refresh().catch(() => undefined);
  }, []);

  const data = snapshot?.snapshot ?? snapshot;
  const vector = data?.vector ?? {};
  return (
    <article className="agentic-os-card agentic-os-neural-emotion-card">
      <div className="agentic-os-permission-header">
        <div>
          <h3>Neural Emotion Engine v0</h3>
          <p>Bounded local state controls for discourse, SPLATRA motion, voice plans, and agentic priority. It is not real emotion or consciousness.</p>
        </div>
        <strong>{data?.label ?? "loading"}</strong>
      </div>
      <div className="agentic-os-neural-grid">
        <Gauge label="valence" value={Number(vector.valence ?? 0)} min={-1} max={1} />
        <Gauge label="arousal" value={Number(vector.arousal ?? 0)} min={-1} max={1} />
        <Gauge label="curiosity" value={Number(vector.curiosity ?? 0)} />
        <Gauge label="caution" value={Number(vector.caution ?? 0)} />
        <Gauge label="fatigue" value={Number(vector.fatigue ?? 0)} />
        <Gauge label="speaking" value={Number(vector.speaking_energy ?? 0)} />
      </div>
      <div className="agentic-os-actions">
        {eventButtons.map((eventType) => (
          <button key={eventType} type="button" className="agentic-os-action" onClick={() => sendEvent(eventType)}>
            {eventType}
          </button>
        ))}
        <button type="button" className="agentic-os-action" onClick={() => decay()}>
          decay
        </button>
        <button type="button" className="agentic-os-action" onClick={() => refresh()}>
          refresh
        </button>
      </div>
      <div className="agentic-os-flags">
        <span>last={lastEvent}</span>
        <span>{flagLine(snapshot?.safety_flags ?? data?.safety_flags)}</span>
      </div>
      <div className="agentic-os-control-readout">
        <pre>{JSON.stringify({
          surface: data?.surface_bias,
          splatra: data?.splatra_controls,
          voice: data?.voice_controls,
          agentic: data?.agentic_controls,
        }, null, 2)}</pre>
      </div>
    </article>
  );
}
