import os from "node:os";
import { NextResponse } from "next/server";
import { proxyJson } from "../../_backend";

type BenchmarkInput = {
  hardware_profile?: Record<string, any>;
  run_probes?: boolean;
};

const volumePayloads = {
  lite: { target_nodes: 3_000, target_edges: 9_000, duration_hours: 12 },
  standard: { target_nodes: 10_000, target_edges: 40_000, duration_hours: 72 },
  deep: { target_nodes: 25_000, target_edges: 100_000, duration_hours: 168 },
  max: { target_nodes: 50_000, target_edges: 240_000, duration_hours: 168 },
};

function num(value: unknown, fallback: number) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function fallbackBenchmark(input: BenchmarkInput = {}) {
  const hardware = {
    cpu: os.cpus()[0]?.model ?? "Deployment CPU",
    gpu: "Deployment sandbox",
    vram_gb: 0,
    ram_gb: Number((os.totalmem() / 1024 ** 3).toFixed(1)),
    storage: "Deployment filesystem",
    storage_gb: 1,
    cpu_logical: os.cpus().length,
    disk_free_gb: 1,
    platform: os.platform(),
    ...(input.hardware_profile ?? {}),
  };
  const ramGb = num(hardware.ram_gb, 8);
  const vramGb = num(hardware.vram_gb, 0);
  const threads = num(hardware.cpu_logical, 2);
  let learningVolume: keyof typeof volumePayloads = "lite";
  if (ramGb >= 30 && vramGb >= 15 && threads >= 12) {
    learningVolume = "max";
  } else if (ramGb >= 30 && threads >= 8) {
    learningVolume = "deep";
  } else if (ramGb >= 16) {
    learningVolume = "standard";
  }
  const payload = volumePayloads[learningVolume as keyof typeof volumePayloads];
  const hotWindowNodes = Math.min(Math.max(1024, Math.floor(payload.target_nodes / 6)), 6000);

  return {
    generated_at: new Date().toISOString(),
    source: "server-fallback",
    can_read_local_hardware: false,
    profile_name: process.env.VERCEL ? "Deployment sandbox fallback" : "Local Next fallback",
    confidence: "low",
    hardware_profile: hardware,
    probes: {
      ran: false,
      cpu_loop_score: null,
      disk_write_mb_s: null,
      duration_ms: 0,
      notes: ["Next fallback cannot read the viewer PC; run FastAPI locally for the real benchmark."],
    },
    recommended_learning_volume: learningVolume,
    recommended_stability_payload: payload,
    ontology_tuning: {
      datagate_batch_docs: ramGb < 64 ? 64 : 128,
      ontology_delta_chunks: ramGb < 64 ? 256 : 512,
      node_write_batch: 500,
      edge_write_batch: 2000,
      hot_window_nodes: hotWindowNodes,
      hot_window_edges: Math.min(Math.max(6000, hotWindowNodes * 8), 60000),
      ui_render_nodes: Math.min(600, Math.max(96, Math.floor(hotWindowNodes / 8))),
      storage_model: "append-only graph event log + SQLite WAL hot index + periodic compacted snapshots",
    },
    training_tuning: {
      precision: vramGb >= 12 ? "bf16-preferred" : "int8-cpu-safe",
      microbatch_tokens: learningVolume === "max" ? 1024 : learningVolume === "deep" ? 768 : learningVolume === "standard" ? 512 : 256,
      gradient_accumulation: learningVolume === "lite" ? 2 : learningVolume === "standard" ? 4 : 8,
      rag_query_concurrency: 2,
      checkpoint_interval_minutes: 15,
      checkpoint_keep_last: 8,
    },
    runtime_envelope: {
      ram_soft_gb: Number((ramGb * 0.72).toFixed(1)),
      ram_hard_gb: Number((ramGb * 0.86).toFixed(1)),
      vram_soft_gb: Number((vramGb * 0.74).toFixed(1)),
      vram_hard_gb: Number((vramGb * 0.9).toFixed(1)),
      storage_reserve_gb: 200,
    },
    backpressure_policy: [
      { condition: "RAM >= soft watermark", action: "pause harvest, flush ontology batches, compact hot graph window, keep RAG read-only" },
      { condition: "VRAM >= soft watermark", action: "pause Homage Oven batches, keep DataGate/Ontology on CPU, lower microbatch size" },
      { condition: "graph writer lag > 2 batches", action: "stop creating new relations; only merge known nodes until writer catches up" },
      { condition: "storage free <= reserve", action: "stop harvest, rotate checkpoints, compact graph snapshots, require operator review" },
    ],
    adjustment_policy: {
      auto_apply_when_source: "local-hardware-probe",
      reason: "fallback route cannot inspect the user's actual PC",
      rerun_trigger: "start local FastAPI backend or click benchmark again",
    },
  };
}

export async function GET() {
  try {
    const proxied = await proxyJson("/api/neuro/benchmark");
    if (proxied) return NextResponse.json(proxied.body, { status: proxied.status });
    return NextResponse.json(fallbackBenchmark());
  } catch {
    return NextResponse.json(fallbackBenchmark());
  }
}

export async function POST(request: Request) {
  const body = await request.json().catch(() => ({}));
  try {
    const proxied = await proxyJson("/api/neuro/benchmark", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (proxied) return NextResponse.json(proxied.body, { status: proxied.status });
    return NextResponse.json(fallbackBenchmark(body));
  } catch {
    return NextResponse.json(fallbackBenchmark(body));
  }
}
