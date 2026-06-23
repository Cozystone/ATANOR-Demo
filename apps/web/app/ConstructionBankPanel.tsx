"use client";

import { useEffect, useState } from "react";

type AnyRecord = Record<string, any>;

const seedSources = [
  {
    source_type: "operator_example",
    language: "ko",
    route_type: "voice_status",
    act: "voice_question",
    text: "Fish 직접 합성은 아직 연결 전이라 Windows 로컬 음성으로 먼저 발화합니다.",
    source_refs: ["apps/api/app/routers/dual_brain.py"],
    grounding_quality: "medium",
  },
  {
    source_type: "operator_example",
    language: "ko",
    route_type: "splatra_request",
    act: "open_chat",
    text: "SPLATRA 구슬 변경은 바로 적용하지 않고 검토 가능한 UI 패치 후보로 남깁니다.",
    source_refs: ["apps/web/app/HologramVoiceOrb.tsx"],
    grounding_quality: "medium",
  },
];

async function apiJson(path: string, init?: RequestInit): Promise<AnyRecord> {
  const response = await fetch(path, { ...init, cache: "no-store" });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

export default function ConstructionBankPanel() {
  const [status, setStatus] = useState<AnyRecord | null>(null);
  const [candidates, setCandidates] = useState<AnyRecord[]>([]);
  const [retrieval, setRetrieval] = useState<AnyRecord | null>(null);
  const [selectedId, setSelectedId] = useState("");
  const [message, setMessage] = useState("idle");

  async function refresh() {
    const [nextStatus, list] = await Promise.all([
      apiJson("/api/construction-bank/status"),
      apiJson("/api/construction-bank/candidates"),
    ]);
    setStatus(nextStatus);
    setCandidates(list.candidates ?? []);
    if (!selectedId && list.candidates?.[0]?.candidate_id) {
      setSelectedId(list.candidates[0].candidate_id);
    }
  }

  async function extractSeed() {
    const payload = await apiJson("/api/construction-bank/extract", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ sources: seedSources, store: true }),
    });
    setMessage(`extracted=${payload.extracted} stored=${payload.stored}`);
    await refresh();
  }

  async function previewRetrieve() {
    const payload = await apiJson("/api/construction-bank/retrieve", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ route_type: "voice_status", language: "ko", act: "voice_question", audience: "lab" }),
    });
    setRetrieval(payload);
    setMessage(payload.retrieved_self_grown_construction ? "retrieved candidate" : "hand-authored fallback");
  }

  async function exportReview() {
    if (!selectedId) return;
    const payload = await apiJson("/api/construction-bank/export-review-item", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ candidate_id: selectedId }),
    });
    setMessage(`review item=${payload.review_item?.item_id ?? "created"}`);
    await refresh();
  }

  useEffect(() => {
    refresh().catch((error) => setMessage(error instanceof Error ? error.message : "refresh failed"));
  }, []);

  return (
    <article className="agentic-os-card agentic-os-review-card">
      <h3>Self-Grown Construction Bank</h3>
      <p>Proof-only candidate bank for ASM-v0 constructions. Candidates require human review and never become production-active here.</p>
      <div className="agentic-os-flags">
        <span>total={String(status?.total_candidates ?? 0)}</span>
        <span>candidate={String(status?.by_status?.candidate ?? 0)}</span>
        <span>reviewed={String(status?.by_status?.reviewed ?? 0)}</span>
        <span>production_active={String(status?.production_active_count ?? 0)}</span>
      </div>
      <div className="agentic-os-actions">
        <button type="button" className="agentic-os-action" onClick={() => extractSeed()}>extract proof examples</button>
        <button type="button" className="agentic-os-action" onClick={() => previewRetrieve()}>preview retrieval</button>
        <button type="button" className="agentic-os-action" disabled={!selectedId} onClick={() => exportReview()}>send to Review Queue</button>
        <button type="button" className="agentic-os-action" onClick={() => refresh()}>refresh</button>
      </div>
      <p>{message}</p>
      <div className="agentic-os-review-list">
        {candidates.length === 0 ? <p>no construction candidates yet</p> : candidates.slice(0, 5).map((candidate) => (
          <button
            type="button"
            className="agentic-os-review-item"
            key={candidate.candidate_id}
            onClick={() => setSelectedId(candidate.candidate_id)}
            data-active={selectedId === candidate.candidate_id}
          >
            <div>
              <small>{candidate.source_type} · {candidate.route_type} · {candidate.status}</small>
              <strong>{candidate.construction_family}</strong>
              <p>{candidate.example_text}</p>
              <span>template={String(candidate.template_risk)} grounding={String(candidate.grounding_score)} natural={String(candidate.naturalness_score)}</span>
            </div>
          </button>
        ))}
      </div>
      {retrieval ? (
        <pre style={{ whiteSpace: "pre-wrap", maxHeight: 180, overflow: "auto" }}>
          {JSON.stringify({
            retrieved: retrieval.retrieved_self_grown_construction,
            candidate: retrieval.construction_candidate_id,
            status: retrieval.candidate_status,
            production_active: retrieval.production_active,
          }, null, 2)}
        </pre>
      ) : null}
    </article>
  );
}
