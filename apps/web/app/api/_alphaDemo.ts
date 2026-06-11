type State = "idle" | "running" | "completed" | "failed";

const now = () => new Date().toISOString();

const demoNodes = [
  { id: "graphrag", label: "GraphRAG", type: "concept", count: 4, confidence: 0.9, evidence_doc_ids: ["demo-001"] },
  { id: "knowledgegraph", label: "KnowledgeGraph", type: "concept", count: 3, confidence: 0.84, evidence_doc_ids: ["demo-001"] },
  { id: "evidence", label: "Evidence", type: "keyword", count: 3, confidence: 0.8, evidence_doc_ids: ["demo-001", "demo-002"] },
  { id: "guardrail", label: "Guardrail", type: "concept", count: 2, confidence: 0.72, evidence_doc_ids: ["demo-002"] },
];

const demoEdges = [
  { source: "graphrag", relation: "uses", target: "knowledgegraph", confidence: 0.82, evidence_doc_ids: ["demo-001"], status: "candidate" },
  { source: "evidence", relation: "reduces", target: "hallucinationrisk", confidence: 0.74, evidence_doc_ids: ["demo-002"], status: "candidate" },
  { source: "guardrail", relation: "requires", target: "evidence", confidence: 0.7, evidence_doc_ids: ["demo-002"], status: "candidate" },
];

const defaultNeuroText =
  "SNN event neuromorphic modular continual few-shot self-supervised masking pruning quantization distillation GraphRAG guardrail";

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

function tokensFor(text: string) {
  return text.toLowerCase().match(/[a-z0-9][a-z0-9_-]*/g) ?? defaultNeuroText.toLowerCase().split(/\s+/);
}

function scoreNeuroModules(tokens: string[], moduleBudget: number) {
  const tokenSet = new Set(tokens);
  const modules = [
    { id: "event_gate", name: "SNN Event Gate", role: "Route only salient state changes into downstream modules.", keywords: ["snn", "spiking", "event", "neuromorphic", "low-power"] },
    { id: "modular_router", name: "Modular Specialist Router", role: "Activate a small expert set instead of the whole model.", keywords: ["modular", "module", "specialist", "router", "distributed"] },
    { id: "memory_consolidator", name: "Continual Memory", role: "Protect important memories with EWC-style consolidation and replay.", keywords: ["continual", "ewc", "forgetting", "plasticity", "memory"] },
    { id: "prototype_memory", name: "Few-Shot Prototype Memory", role: "Store compact class/task prototypes for one-shot adaptation.", keywords: ["few-shot", "one-shot", "prototype", "small", "data"] },
    { id: "masking_teacher", name: "Self-Supervised Masking", role: "Pretrain from local unlabeled data with masked reconstruction tasks.", keywords: ["self-supervised", "mask", "masked", "contrastive", "mae"] },
    { id: "compression_distiller", name: "Compression Distiller", role: "Schedule pruning, quantization, and distillation for low-resource runs.", keywords: ["pruning", "quantization", "distillation", "efficient", "energy"] },
    { id: "graph_guard", name: "GraphRAG Guard Verifier", role: "Ground responses against ontology evidence and guardrail checks.", keywords: ["graphrag", "ontology", "evidence", "guard", "guardrail"] },
  ].map((module) => {
    const matches = module.keywords.filter((keyword) => tokenSet.has(keyword)).length;
    const score = clamp(0.22 + matches * 0.16, 0.05, 0.98);
    return { id: module.id, name: module.name, role: module.role, score: Number(score.toFixed(3)), state: score >= 0.38 ? "active" : "standby" };
  }).sort((left, right) => right.score - left.score);
  const active = modules.filter((module) => module.state === "active").slice(0, moduleBudget);
  return { modules, activeModules: (active.length >= 3 ? active : modules.slice(0, Math.min(moduleBudget, 3))).map((module) => module.id) };
}

export const demoState = {
  datagate: {
    state: "completed" as State,
    run_id: "dg-demo-alpha",
    total: 4,
    accepted: 3,
    rejected: 1,
    rejection_breakdown: { min_length: 1 },
    started_at: now(),
    finished_at: now(),
    error: null,
  },
  ontology: {
    state: "completed" as State,
    started_at: now(),
    finished_at: now(),
    error: null,
    node_count: demoNodes.length,
    edge_count: demoEdges.length,
    newest_nodes: demoNodes,
    newest_edges: demoEdges,
  },
  graph: { nodes: demoNodes, edges: demoEdges },
  graphrag: {
    state: "completed" as State,
    started_at: now(),
    finished_at: now(),
    error: null,
    last_query: "GraphRAG evidence",
    confidence: 0.82,
    result: makeEvidence("GraphRAG evidence"),
  },
  guard: {
    state: "idle" as State,
    started_at: null as string | null,
    finished_at: null as string | null,
    error: null as string | null,
    overall_guard_score: 0,
    result: null as any,
  },
  oven: {
    state: "completed" as State,
    started_at: now(),
    finished_at: now(),
    error: null,
    last_loss: 1.982,
    checkpoint_path: "checkpoints/homage-core-30m-dev/manifest.json",
    losses: [
      { step: 1, loss: 4.31, tokens: 128 },
      { step: 2, loss: 3.08, tokens: 256 },
      { step: 3, loss: 2.54, tokens: 384 },
      { step: 4, loss: 2.18, tokens: 512 },
      { step: 5, loss: 1.982, tokens: 640 },
    ],
  },
};

export function demoNeuroPlan(input?: { text?: string; task_type?: string; target_device?: string; token_budget?: number; module_budget?: number }) {
  const text = input?.text || defaultNeuroText;
  const tokens = tokensFor(text);
  const tokenCount = Math.max(1, tokens.length);
  const uniqueRatio = new Set(tokens).size / tokenCount;
  const transitions = tokens.reduce((count, token, index) => count + (index > 0 && token !== tokens[index - 1] ? 1 : 0), 0);
  const transitionRatio = transitions / Math.max(1, tokenCount - 1);
  const salient = new Set(["snn", "spiking", "event", "neuromorphic", "continual", "few-shot", "self-supervised", "pruning", "quantization", "distillation", "graphrag", "guardrail"]);
  const salienceRatio = tokens.filter((token) => salient.has(token)).length / tokenCount;
  const eventDensity = clamp(0.16 + uniqueRatio * 0.26 + transitionRatio * 0.18 + salienceRatio * 0.26, 0.2, 0.72);
  const sparsity = Number((1 - eventDensity).toFixed(3));
  const moduleBudget = clamp(input?.module_budget ?? 4, 2, 7);
  const { modules, activeModules } = scoreNeuroModules(tokens, moduleBudget);
  const pruningTarget = Number((sparsity > 0.55 ? 0.45 : 0.38).toFixed(3));
  const quantizationBits = 8;
  const denseCost = tokenCount * modules.length * 32;
  const efficientCost = denseCost * eventDensity * (quantizationBits / 32) * (1 - pruningTarget) * (activeModules.length / modules.length);
  const reductionRatio = Number(clamp(1 - efficientCost / denseCost, 0, 0.98).toFixed(3));
  const prototypeSlots = Math.max(8, Math.min(64, Math.floor(new Set(tokens).size / 2) + activeModules.length * 2));

  return {
    generated_at: now(),
    architecture: "Homage Neuro-Efficiency Layer",
    objective: "Run adaptive AI workloads with sparse events, modular routing, compact memory, and explicit compression controls.",
    workload: {
      task_type: input?.task_type ?? "alpha-dashboard",
      target_device: input?.target_device ?? "low-spec-cpu-gpu",
      token_count: tokenCount,
      token_budget: input?.token_budget ?? 512,
    },
    event_gate: {
      event_density: Number(eventDensity.toFixed(3)),
      sparsity,
      active_events: Math.max(1, Math.round(tokenCount * eventDensity)),
      suppressed_events: Math.max(0, tokenCount - Math.max(1, Math.round(tokenCount * eventDensity))),
      latency_mode: tokenCount < 230 ? "burst" : "adaptive",
      trigger: "token novelty + neuromorphic salience",
    },
    module_routing: { budget: moduleBudget, active_modules: activeModules, modules },
    learning_plan: {
      continual: {
        strategy: "EWC-style consolidation + tiny replay buffer",
        ewc_lambda: 0.42,
        replay_budget: prototypeSlots,
        protected_modules: activeModules.filter((id) => ["memory_consolidator", "prototype_memory", "graph_guard", "modular_router"].includes(id)).slice(0, 3),
      },
      few_shot: {
        strategy: "cosine prototype memory",
        prototype_slots: prototypeSlots,
        update_rule: "merge low-distance examples; fork high-novelty examples",
      },
      self_supervised: {
        strategy: "masked span reconstruction + graph edge prediction",
        mask_ratio: 0.42,
        local_signal: "use accepted DataGate documents and Ontology Forge edges",
      },
    },
    compression: {
      pruning_target: pruningTarget,
      quantization_bits: quantizationBits,
      distillation: "self-distill active specialists into a compact student checkpoint",
      activation_checkpointing: true,
      deployment_note: "Prefer event-sparse batches before hardware-specific SNN or FPGA kernels.",
    },
    energy_estimate: {
      dense_cost_units: Number(denseCost.toFixed(2)),
      efficient_cost_units: Number(efficientCost.toFixed(2)),
      reduction_ratio: reductionRatio,
      summary: `${Math.round(reductionRatio * 100)}% fewer scheduled compute units estimated`,
    },
    recommendations: [
      "Keep the transformer/GraphRAG path as the reference brain while testing event-gated specialists.",
      "Log active event density per run so pruning and quantization decisions use measured workload sparsity.",
      "Protect ontology and guard memories during continual updates before allowing broad model plasticity.",
      "Validate 8-bit quantization on guard and retrieval outputs before enabling for all modules.",
    ],
    research_basis: [
      { topic: "Surrogate-gradient SNN training", source: "Neftci, Mostafa, Zenke, 2019", url: "https://arxiv.org/abs/1901.09948" },
      { topic: "Elastic Weight Consolidation", source: "Kirkpatrick et al., 2017", url: "https://arxiv.org/abs/1612.00796" },
      { topic: "Prototypical Networks", source: "Snell, Swersky, Zemel, 2017", url: "https://arxiv.org/abs/1703.05175" },
      { topic: "Masked Autoencoders", source: "He et al., 2021", url: "https://arxiv.org/abs/2111.06377" },
    ],
  };
}

export function makeEvidence(query: string) {
  return {
    query,
    matched_nodes: demoNodes.filter((node) => query.toLowerCase().includes(node.label.toLowerCase()) || node.id === "evidence"),
    matched_edges: demoEdges,
    evidence_docs: [
      {
        doc_id: "demo-001",
        path: "data/cleaned/demo-001.txt",
        score: 1.12,
        snippet: "GraphRAG uses KnowledgeGraph structure to retrieve Evidence for grounded answers.",
      },
      {
        doc_id: "demo-002",
        path: "data/cleaned/demo-002.txt",
        score: 0.88,
        snippet: "Guardrail checks claims against Evidence and flags overconfident answer text.",
      },
    ],
    graph_paths: demoEdges.map((edge) => [edge.source, edge.relation, edge.target]),
    confidence: 0.82,
  };
}

export function demoPipelineStatus() {
  return {
    generated_at: now(),
    system_state: "alpha-demo",
    stages: [
      { id: "harvest", name: "Harvest", state: "complete", progress: 100, summary: "Demo local documents are staged.", metric_label: "documents", metric_value: "4 demo" },
      { id: "datagate", name: "DataGate", state: demoState.datagate.state === "completed" ? "complete" : demoState.datagate.state, progress: 100, summary: "DataGate accepted demo documents and rejected one short file.", metric_label: "quality gate", metric_value: "3/4 accepted" },
      { id: "ontology-forge", name: "Ontology Forge", state: "complete", progress: 100, summary: "Concept nodes and candidate edges are available.", metric_label: "graph", metric_value: `${demoNodes.length} nodes / ${demoEdges.length} edges` },
      { id: "homage-oven", name: "Homage Oven", state: "complete", progress: 100, summary: "Dry-run scaffold produced a short loss trace.", metric_label: "last loss", metric_value: String(demoState.oven.last_loss) },
      { id: "graphrag", name: "GraphRAG", state: "complete", progress: 100, summary: "Demo evidence bundle is ready.", metric_label: "confidence", metric_value: "0.82" },
      { id: "guardrail", name: "Guardrail", state: demoState.guard.state === "idle" ? "idle" : "complete", progress: demoState.guard.state === "idle" ? 0 : 100, summary: "Ready to check draft claims.", metric_label: "guard score", metric_value: String(demoState.guard.overall_guard_score) },
      { id: "gpu-monitor", name: "GPU Monitor", state: "warning", progress: 35, summary: "Deployed sandbox uses telemetry fallback.", metric_label: "vram", metric_value: "fallback" },
    ],
  };
}

export function demoDataGateRun() {
  demoState.datagate = { ...demoState.datagate, state: "completed", run_id: `dg-demo-${Date.now()}`, started_at: now(), finished_at: now() };
  return { run_id: demoState.datagate.run_id, state: "running" };
}

export function demoOntologyRun() {
  demoState.ontology = { ...demoState.ontology, state: "completed", started_at: now(), finished_at: now() };
  return demoState.ontology;
}

export function demoGraphRAGQuery(query: string) {
  const result = makeEvidence(query || "GraphRAG evidence");
  demoState.graphrag = { ...demoState.graphrag, state: "completed", started_at: now(), finished_at: now(), last_query: result.query, confidence: result.confidence, result };
  return demoState.graphrag;
}

export function demoGuardCheck(draft: string) {
  const hasOverclaim = /always|never|guarantees|completely eliminates|항상|절대|보장/i.test(draft);
  const hasEvidence = /GraphRAG|Evidence|Guardrail|KnowledgeGraph/i.test(draft);
  const support = hasEvidence ? "weak_support" : "unsupported";
  const score = Math.max(0, 100 - (support === "unsupported" ? 35 : 15) - (hasOverclaim ? 10 : 0));
  const result = {
    claims: [{ claim: draft || "GraphRAG uses Evidence.", support, evidence_overlap: hasEvidence ? 2 : 0, ontology_overlap: hasEvidence ? 1 : 0, warnings: hasOverclaim ? ["overclaim"] : [] }],
    warnings: hasOverclaim ? ["Overclaim language detected."] : [],
    recommended_revision_notes: hasOverclaim ? ["Soften absolute language and attach evidence."] : [],
    overall_guard_score: score,
  };
  demoState.guard = { state: "completed", started_at: now(), finished_at: now(), error: null, overall_guard_score: score, result };
  return demoState.guard;
}
