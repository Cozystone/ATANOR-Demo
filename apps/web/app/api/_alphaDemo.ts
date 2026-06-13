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
  learningDaemon: {
    state: "demo",
    desired_running: false,
    resume_needed: false,
    started_at: null as string | null,
    last_heartbeat_at: null as string | null,
    last_checkpoint_at: null as string | null,
    total_runtime_seconds: 0,
    total_rounds: 0,
    learned_rounds: 0,
    idle_rounds: 0,
  },
};

export function demoLearningDaemonStatus() {
  return {
    mode: "deployment-demo",
    state: demoState.learningDaemon.state,
    desired_running: demoState.learningDaemon.desired_running,
    resume_after_reboot: true,
    resume_needed: demoState.learningDaemon.resume_needed,
    worker_alive: false,
    started_at: demoState.learningDaemon.started_at,
    last_heartbeat_at: demoState.learningDaemon.last_heartbeat_at,
    last_checkpoint_at: demoState.learningDaemon.last_checkpoint_at,
    interval_seconds: 30,
    total_runtime_seconds: demoState.learningDaemon.total_runtime_seconds,
    total_rounds: demoState.learningDaemon.total_rounds,
    learned_rounds: demoState.learningDaemon.learned_rounds,
    idle_rounds: demoState.learningDaemon.idle_rounds,
    latest_event_count: 0,
    latest_node_count: 0,
    latest_edge_count: 0,
    checkpoint_count: demoState.learningDaemon.last_checkpoint_at ? 1 : 0,
    local_required: true,
    deployment_policy: "Vercel ??????袁⑸즴筌?씛彛???돗????????????썹땟戮녹??諭????????????ъ몥??우뒭亦낆쥋援??룰큿???뉗꽫?? ??? ??????????????숈춻????????????????????????????????ㅻ쑋?????????癲?? ???????嚥???癲??關?쒎첎???????????????嶺??????????쇰뮛????????????????????????????????됰Ŧ????????????癲ル슢??蹂좉슈??????????筌??????????????????????FastAPI?? data/memory ????????????????????????????????????븐뼐?????????",
    last_round_action: "deployment_demo_boundary",
    last_round_message: "??????袁⑸즴筌?씛彛???돗????????????썹땟戮녹??諭????????????ъ몥??우뒭亦낆쥋援??룰큿???뉗꽫??????????????븐뼐???????????????거???????Cloud Brain worker???????? ????????????????쇨덫櫻? ???????????FastAPI???????????怨뺤떪???????????????嚥???癲??關?쒎첎?????worker ??????癲?????????????????????쇨덫櫻?",
    resource_snapshot: {
      disk_free_gb: null,
      disk_total_gb: null,
      ram_available_gb: null,
      ram_total_gb: null,
    },
    reboot_resilience: {
      state_file: "data/memory/daemon_state.json",
      checkpoint_dir: "data/memory/daemon_checkpoints",
      heartbeat_interval_seconds: 30,
      checkpoint_interval_seconds: 300,
      resume_contract: "PC ??????????????????FastAPI???????????ш끽紐??????????諛몃마嶺뚮??????????????????????????????????궰????daemon_state.json??SQLite WAL?????Cloud Brain worker??????????? ???????μ떜媛?걫???????????????????",
    },
    llm_policy: {
      external_llm: false,
      local_quantized_llm: false,
      pretrained_generation_weights: false,
    },
  };
}

export function demoLearningDaemonStart() {
  demoState.learningDaemon = {
    ...demoState.learningDaemon,
    state: "demo",
    desired_running: false,
    resume_needed: false,
    last_heartbeat_at: now(),
    last_round_action: "deployment_demo_boundary",
  } as typeof demoState.learningDaemon;
  return demoLearningDaemonStatus();
}

export function demoLearningDaemonResume() {
  demoState.learningDaemon = {
    ...demoState.learningDaemon,
    state: "demo",
    desired_running: false,
    resume_needed: false,
    last_heartbeat_at: now(),
  };
  return demoLearningDaemonStatus();
}

export function demoLearningDaemonStop() {
  demoState.learningDaemon = {
    ...demoState.learningDaemon,
    state: "demo",
    desired_running: false,
    resume_needed: false,
    last_heartbeat_at: now(),
  };
  return demoLearningDaemonStatus();
}

export function demoLearningDaemonCheckpoint() {
  demoState.learningDaemon = {
    ...demoState.learningDaemon,
    state: "demo",
    desired_running: false,
    last_checkpoint_at: now(),
  };
  return demoLearningDaemonStatus();
}

function demoCloudBrainShell() {
  const daemon = {
    ...demoLearningDaemonStatus(),
    state: "viewer_only",
    latest_event_count: 0,
    latest_node_count: 0,
    latest_edge_count: 0,
  };
  return {
    name: "Cloud Brain",
    mode: "shared-public-ontology-facade",
    implementation: "deployment-viewer-alpha",
    state: daemon.state,
    viewer_only_on_deploy: true,
    public_cloud_backend_enabled: false,
    local_required: true,
    counts: {
      nodes: daemon.latest_node_count,
      edges: daemon.latest_edge_count,
      events: daemon.latest_event_count,
      rounds: daemon.total_rounds,
      learned_rounds: daemon.learned_rounds,
    },
    synaptic_lifecycle: ["virtual_edge", "potentiation", "consolidation", "decay", "pruning"],
    lab_integration_order: [
      "local_private_graph",
      "governed_web_search",
      "cloud_brain_candidate_fragments",
      "working_memory_activation",
      "native_graph_token_generation",
      "guardrail_promotion_check",
    ],
    answer_policy: {
      external_llm: false,
      local_quantized_llm: false,
      pretrained_generation_weights: false,
      template_only_answers: false,
    },
    daemon,
  };
}

export function demoCloudBrainStatus() {
  return demoCloudBrainShell();
}

export function demoCloudBrainQuery(query: string) {
  return {
    ...demoCloudBrainShell(),
    query,
    state: "viewer_only",
    source: "deployment_cloud_brain_viewer",
    public_cloud_backend_enabled: false,
    fragments: {
      active_nodes: [],
      active_edges: [],
      semantic_skeleton: [],
    },
    promotion_policy: {
      requires_repeated_signal: true,
      requires_provenance: true,
      requires_guardrail_pass: true,
      writes_public_cloud: false,
    },
    drift_report: null,
    reason: "Deployment Cloud Brain is a read-only viewer until a local worker or shared graph backend is connected.",
  };
}

export function demoCloudBrainIngest(input?: { source_url?: string; text?: string; dry_run?: boolean }) {
  return {
    ...demoCloudBrainShell(),
    state: input?.dry_run === false ? "planned" : "dry_run",
    accepted: false,
    payload_seen: Boolean(input?.source_url || input?.text),
    reason: "Deployment viewer has no public Cloud Brain ingestion backend yet.",
  };
}

export function demoCloudBrainConsolidate() {
  return {
    ...demoCloudBrainShell(),
    state: "viewer_only",
    consolidated: false,
    last_round_action: "deployment_viewer_no_mutation",
    last_round_message: "Deployment viewer is read-only; persistent graph changes run only in the local worker.",
  };
}

export function demoCloudBrainPrune(input?: { dry_run?: boolean; min_weight?: number; max_idle_days?: number }) {
  return {
    ...demoCloudBrainShell(),
    state: input?.dry_run === false ? "planned" : "dry_run",
    pruned: false,
    policy: {
      min_weight: input?.min_weight ?? 0.05,
      max_idle_days: input?.max_idle_days ?? 30,
      decay_factor: "planned",
    },
    reason: "Deployment viewer shows pruning plans only; it does not mutate the graph.",
  };
}

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
    architecture: "ATANOR Neuro-Efficiency Layer",
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

function normalizedQuery(query: string) {
  return query.trim().toLowerCase();
}

function cleanTopicToken(token: string) {
  return token;
}

function includesAny(query: string, terms: string[]) {
  return terms.some((term) => query.includes(term));
}

function isGreetingQuery(query: string) {
  const normalized = normalizedQuery(query);
  return /^(hi|hello|hey|yo)[\s!.?]*$/i.test(normalized);
}

function isThanksQuery(query: string) {
  const normalized = normalizedQuery(query);
  return /^(thanks|thank you)[\s!.?]*$/i.test(normalized);
}

export function isConversationalQuery(query: string) {
  return isGreetingQuery(query) || isThanksQuery(query);
}

export function isNodeInventoryQuery(query: string) {
  const normalized = normalizedQuery(query);
  return /(node|nodes|inventory)/i.test(normalized) && /(list|all|show|inventory|available)/i.test(normalized);
}

export function isLegendQuery(query: string) {
  const normalized = normalizedQuery(query);
  const asksColor = /(legend|color)/i.test(normalized);
  const asksMeaning = /(meaning|mean|label|graph|node)/i.test(normalized);
  return asksColor && asksMeaning;
}
function isInternalStructureQuery(query: string) {
  const normalized = normalizedQuery(query);
  const selfOrSystem = /(atanor|rag|graphrag|ghost|shell|payload|vault|architecture|system|engine|structure|graph)/i.test(normalized);
  const asksStructure = /(structure|explain|architecture|work|flow|how|what|define)/i.test(normalized);
  return selfOrSystem && asksStructure;
}

function nodeTypeText(type?: string) {
  const labels: Record<string, string> = {
    concept: "concept",
    keyword: "keyword",
    source: "source",
    ontology: "ontology",
    retrieval: "retrieval",
    guardrail: "guardrail",
    training: "training",
    visualization: "visualization",
    critique: "critique",
  };
  return labels[type ?? ""] ?? type ?? "node";
}

function nodeTypeColor(type?: string) {
  const colors: Record<string, string> = {
    source: "#ff6b35",
    critique: "#c5283d",
    ontology: "#1a936f",
    retrieval: "#006a9f",
    visualization: "#8c3fa7",
    guardrail: "#e89d2a",
    training: "#111715",
    concept: "#22936f",
    keyword: "#4a8fdb",
    heading: "#7b8794",
    quality: "#3f6f5f",
    memory: "#1a936f",
    verification: "#e89d2a",
    learning: "#111715",
    efficiency: "#006a9f",
  };
  return colors[type ?? ""] ?? "#68736d";
}

function nodeTypeDescription(type?: string) {
  const descriptions: Record<string, string> = {
    source: "raw source or payload origin",
    critique: "quality critique or correction signal",
    ontology: "conceptual ontology memory node",
    retrieval: "retrieval and GraphRAG routing node",
    visualization: "3D viewport and signal visualization node",
    guardrail: "claim validation and safety node",
    training: "learning, replay, or distillation node",
    concept: "canonical concept node",
    keyword: "searchable keyword node",
  };
  return descriptions[type ?? ""] ?? "ATANOR Ghost Shell graph node";
}
function nativeAnswerEngine(mode = "ontology-graph-token-prediction-alpha") {
  return {
    name: "ATANOR Graph Token Predictor",
    mode,
    external_llm: false,
    homage_core: "homage-core-30m-scaffold",
    prediction_basis: "ontology_token_transition_graph",
    surface_generation: "graph_walk",
    template_free_surface: true,
    stages: ["decompose_sentences", "build_token_edges", "merge_ontology_paths", "score_connected_tokens", "predict_next_token_sequence"],
  };
}

function makeNodeInventoryResult(query: string) {
  const nodeLines = demoNodes.map((node, index) => `${index + 1}. ${node.label} (${nodeTypeText(node.type)}, id: ${node.id}, confidence ${Math.round(node.confidence * 100)}%)`);
  return {
    query,
    method: "atanor-graph-inspection-v1",
    answer: `ATANOR Ghost Shell currently exposes ${demoNodes.length} demo nodes and ${demoEdges.length} demo edges.\n${nodeLines.join("\n")}`,
    matched_nodes: demoNodes,
    matched_edges: demoEdges,
    evidence_docs: [],
    citations: [],
    graph_paths: demoEdges.map((edge) => [edge.source, edge.relation, edge.target]),
    follow_up_questions: ["Show active hashes", "Explain Payload Vault"],
    retrieval_trace: {
      strategy: "graph inventory intent; retrieval skipped",
      query_terms: normalizedQuery(query).split(/\s+/).filter(Boolean),
      expanded_terms: [],
      ranked_chunk_ids: [],
      matched_node_ids: demoNodes.map((node) => node.id),
    },
    answer_kind: "inspection",
    answer_engine: { ...nativeAnswerEngine("graph-inspection-control-alpha"), name: "ATANOR Inspection Router", surface_generation: "disabled" },
    confidence: 0.99,
  };
}

function makeLegendResult(query: string) {
  const typeOrder: string[] = [];
  const typeCounts = new Map<string, number>();
  const representatives: typeof demoNodes = [];
  demoNodes.forEach((node) => {
    typeCounts.set(node.type, (typeCounts.get(node.type) ?? 0) + 1);
    if (!typeOrder.includes(node.type)) {
      typeOrder.push(node.type);
      representatives.push(node);
    }
  });
  const lines = typeOrder.map((type) => `- ${nodeTypeColor(type)} ${nodeTypeText(type)}: ${nodeTypeDescription(type)}. count ${typeCounts.get(type) ?? 0}`);
  return {
    query,
    method: "atanor-graph-legend-v1",
    answer: `ATANOR graph colors describe Ghost Shell node classes and active signal states.\n${lines.join("\n")}`,
    matched_nodes: representatives,
    matched_edges: demoEdges,
    evidence_docs: [],
    citations: [],
    graph_paths: demoEdges.map((edge) => [edge.source, edge.relation, edge.target]),
    follow_up_questions: ["Show node inventory", "Explain active signal states"],
    retrieval_trace: {
      strategy: "graph legend intent; retrieval skipped",
      query_terms: normalizedQuery(query).split(/\s+/).filter(Boolean),
      expanded_terms: typeOrder,
      ranked_chunk_ids: [],
      matched_node_ids: representatives.map((node) => node.id),
    },
    answer_kind: "inspection",
    answer_engine: { ...nativeAnswerEngine("graph-legend-control-alpha"), name: "ATANOR Inspection Router", surface_generation: "disabled" },
    confidence: 0.98,
  };
}

function nodeMatchesQuery(nodeId: string, query: string) {
  const normalized = normalizedQuery(query);
  const termMap: Record<string, string[]> = {
    graphrag: ["graphrag", "graph rag", "rag", "retrieval"],
    knowledgegraph: ["knowledgegraph", "knowledge graph", "ontology", "graph"],
    evidence: ["evidence", "citation", "source", "grounded"],
    guardrail: ["guardrail", "guard rail", "hallucination", "safety"],
  };
  return includesAny(normalized, termMap[nodeId] ?? []);
}

function makeConversationalResult(query: string, kind: "greeting" | "thanks" | "no_match") {
  const answer = kind === "greeting"
    ? "ATANOR online. Local Ghost Shell and Payload Vault are ready for traceable inference."
    : kind === "thanks"
      ? "Acknowledged. ATANOR will keep synthesis local, traceable, and air-gapped."
      : query;
  return {
    query,
    method: "atanor-conversation-router-v1",
    answer,
    matched_nodes: [],
    matched_edges: [],
    evidence_docs: [],
    citations: [],
    graph_paths: [],
    follow_up_questions: [],
    retrieval_trace: {
      strategy: kind === "no_match" ? "no evidence match; retrieval skipped" : "conversational intent; retrieval skipped",
      query_terms: normalizedQuery(query).split(/\s+/).filter(Boolean),
      expanded_terms: [],
      ranked_chunk_ids: [],
      matched_node_ids: [],
    },
    answer_kind: "conversation",
    answer_engine: {
      ...nativeAnswerEngine("conversation-surface-no-retrieval-alpha"),
      surface_generation: "native_conversation_surface",
      control_intent: kind,
    },
    confidence: kind === "no_match" ? 0.35 : 0.96,
  };
}

function makeOpenGenerationResult(query: string) {
  const internalDocs = [
    {
      doc_id: "atanor-internal-architecture",
      chunk_id: "atanor-internal-architecture#1",
      path: "internal://atanor-architecture",
      score: 0.32,
      snippet:
        "ATANOR combines DataGate, Ontology Forge, Ghost Shell, Payload Vault, GraphRAG, Guardrail, local synthesis, and hardware adaptation into a local-first transparent inference engine.",
      retrieval_signals: { internal_context: true },
    },
    {
      doc_id: "atanor-internal-architecture",
      chunk_id: "atanor-internal-architecture#2",
      path: "internal://atanor-architecture",
      score: 0.3,
      snippet:
        "ATANOR does not rely on external LLM APIs for answer synthesis. It uses traceable graph context, payload evidence, and local deterministic or on-device generation hooks.",
      retrieval_signals: { internal_context: true },
    },
  ];
  const graphPaths: string[][] = [];
  const utterance = makeNativeDemoUtterance(query, demoNodes, graphPaths, internalDocs);
  return {
    query,
    method: "atanor-graph-token-rag-v1",
    answer: utterance.answer,
    matched_nodes: demoNodes,
    matched_edges: demoEdges,
    evidence_docs: internalDocs,
    citations: internalDocs.map((doc) => ({ doc_id: doc.chunk_id, source_doc_id: doc.doc_id, path: doc.path, score: doc.score })),
    graph_paths: graphPaths,
    follow_up_questions: [],
    retrieval_trace: {
      strategy: "internal architecture docs + ontology token transition graph + graph-token prediction",
      query_terms: normalizedQuery(query).split(/\s+/).filter(Boolean),
      expanded_terms: ["atanor", "architecture", "graphrag", "ontology", "guardrail", "vault"],
      ranked_chunk_ids: internalDocs.map((doc) => doc.chunk_id),
      matched_node_ids: demoNodes.map((node) => node.id),
    },
    pmv: utterance.pmv,
    claim_plan: utterance.claim_plan,
    active_concepts: utterance.active_concepts,
    answer_kind: utterance.answer_kind,
    answer_engine: utterance.answer_engine,
    confidence: 0.64,
  };
}
function makeNoEvidenceResult(query: string) {
  const queryTerms = normalizedQuery(query).split(/\s+/).filter(Boolean);
  const tokens = queryTerms.slice(0, 4);
  const answer = [
    "NO_EVIDENCE",
    `query=${query.trim()}`,
    `active_concepts=${JSON.stringify(tokens)}`,
    "graph_token_prediction=not_enough_edges",
  ].join("\n");
  return {
    query,
    method: "atanor-research-no-evidence-v1",
    answer,
    matched_nodes: [],
    matched_edges: [],
    evidence_docs: [],
    citations: [],
    graph_paths: [],
    follow_up_questions: [],
    retrieval_trace: {
      strategy: "no evidence; graph token prediction disabled",
      query_terms: queryTerms,
      expanded_terms: [],
      ranked_chunk_ids: [],
      matched_node_ids: [],
    },
    pmv: {
      intent: "answer_grounded",
      topic: query,
      stance: "experimental_generation_not_authoritative",
      audience_level: "research",
      answer_goal: "show failure state without plausible filler",
      required_evidence: true,
      style: "diagnostic",
    },
    claim_plan: [],
    active_concepts: queryTerms.slice(0, 4),
    answer_kind: "no_evidence",
    answer_engine: { ...nativeAnswerEngine("no-evidence-diagnostic-alpha"), surface_generation: "disabled" },
    confidence: 0,
  };
}

function makeNativeDemoUtterance(query: string, matchedNodes: typeof demoNodes, graphPaths: string[][], evidenceDocs: any[]) {
  const activeConcepts = matchedNodes.map((node) => node.label).slice(0, 6);
  const intent = /(why|cause|reason)/i.test(query)
    ? "explain_cause"
    : /(how|process|flow|step)/i.test(query)
      ? "explain_process"
      : /(what|define)/i.test(query)
        ? "define"
        : "answer_grounded";  const graphDocs = graphPaths.map((path, index) => ({
    chunk_id: `graph-path#${index + 1}`,
    snippet: path.join(" "),
  }));
  const conceptDoc = activeConcepts.length ? [{ chunk_id: "active-concepts#1", snippet: activeConcepts.join(" ") }] : [];
  const prediction = makeGraphTokenPrediction(query, [...evidenceDocs, ...graphDocs, ...conceptDoc]);
  return {
    answer: prediction.answer,
    pmv: {
      intent,
      topic: activeConcepts[0] ?? query,
      stance: "experimental_generation_not_authoritative",
      audience_level: "research",
      answer_goal: "predict token sequence from ontology/token graph connectivity",
      required_evidence: true,
      style: "raw_graph_token_prediction",
    },
    claim_plan: [],
    active_concepts: activeConcepts,
    answer_kind: prediction.answer_kind,
    answer_engine: {
      ...nativeAnswerEngine(prediction.answer_kind === "no_evidence" ? "no-evidence-diagnostic-alpha" : "ontology-graph-token-prediction-alpha"),
      name: "ATANOR Graph Token Predictor",
      prediction_basis: "ontology_token_transition_graph",
      surface_generation: "graph_walk",
      diagnostics: prediction.diagnostics,
    },
  };
}

function cleanWebSnippet(value: any) {
  return String(value ?? "").replace(/\s+/g, " ").trim();
}

function predictionTokens(text: string) {
  return Array.from(text.toLowerCase().matchAll(/[\p{L}\p{N}_-]+/gu))
    .map((match) => match[0].replace(/^(?:-|_)+|(?:-|_)+$/g, ""))
    .filter((token) => token.length > 1 || /^\d+$/.test(token));
}

function trimParticle(token: string) {
  return token;
}
function makeGraphTokenPrediction(query: string, webEvidenceDocs: any[]) {
  const texts = webEvidenceDocs.map((doc) => cleanWebSnippet(doc.snippet || doc.text)).filter(Boolean);
  const transitions = new Map<string, Map<string, number>>();
  const frequencies = new Map<string, number>();
  const cooccurs = new Map<string, Map<string, number>>();

  function addNested(map: Map<string, Map<string, number>>, left: string, right: string, weight: number) {
    if (!map.has(left)) map.set(left, new Map());
    map.get(left)!.set(right, (map.get(left)!.get(right) ?? 0) + weight);
  }

  for (const text of texts) {
    const tokens = predictionTokens(text);
    tokens.forEach((token) => frequencies.set(token, (frequencies.get(token) ?? 0) + 1));
    for (let index = 0; index < tokens.length - 1; index += 1) {
      addNested(transitions, tokens[index], tokens[index + 1], 1);
    }
    for (let index = 0; index < tokens.length; index += 1) {
      for (const neighbor of tokens.slice(index + 1, index + 6)) {
        if (neighbor !== tokens[index]) {
          addNested(cooccurs, tokens[index], neighbor, 1);
          addNested(cooccurs, neighbor, tokens[index], 0.35);
        }
      }
    }
  }

  const seeds = predictionTokens(query).map(trimParticle).filter(Boolean);
  const startCandidates = seeds.filter((seed) => transitions.has(seed) || frequencies.has(seed));
  const start = [...startCandidates, ...frequencies.keys()]
    .sort((left, right) => ((transitions.get(right)?.size ?? 0) - (transitions.get(left)?.size ?? 0)) || ((frequencies.get(right) ?? 0) - (frequencies.get(left) ?? 0)))[0];

  if (!start) {
    return {
      answer: `NO_EVIDENCE\nquery=${query}\ngraph_token_prediction=not_enough_edges`,
      diagnostics: { seeds, token_count: 0, edge_count: 0 },
      answer_kind: "no_evidence",
    };
  }

  const generated = [start];
  const recent = new Map<string, number>([[start, 1]]);
  const usedEdgeKeys = new Set<string>();
  const usedEdges: any[] = [];
  let current = start;
  for (let step = 0; step < 55; step += 1) {
    const options = new Map<string, number>();
    transitions.get(current)?.forEach((weight, token) => options.set(token, (options.get(token) ?? 0) + weight));
    cooccurs.get(current)?.forEach((weight, token) => options.set(token, (options.get(token) ?? 0) + weight * 0.18));
    if (!options.size) break;
    const next = [...options.entries()]
      .map(([token, weight]) => {
        const penalty = 1 / (1 + (recent.get(token) ?? 0) * 1.8);
        const edgeReusePenalty = usedEdgeKeys.has(`${current}\u0000${token}`) ? 0.15 : 1;
        const seedBonus = seeds.includes(token) ? 0.45 : 0;
        const rarity = 1 / Math.sqrt(Math.max(1, frequencies.get(token) ?? 1));
        return { token, score: weight * penalty * edgeReusePenalty + seedBonus + rarity * 0.08 };
      })
      .sort((left, right) => right.score - left.score || left.token.localeCompare(right.token))[0];
    if (!next) break;
    generated.push(next.token);
    usedEdgeKeys.add(`${current}\u0000${next.token}`);
    usedEdges.push({ source: current, target: next.token, score: Number(next.score.toFixed(4)), step: step + 1 });
    recent.set(next.token, (recent.get(next.token) ?? 0) + 1);
    if ((recent.get(next.token) ?? 0) > 4 && step > 8) break;
    current = next.token;
  }

  return {
    answer: generated.join(" "),
    diagnostics: {
      seeds,
      token_count: [...frequencies.values()].reduce((sum, value) => sum + value, 0),
      unique_tokens: frequencies.size,
      edge_count: [...transitions.values()].reduce((sum, targets) => sum + targets.size, 0),
      used_edges: usedEdges.slice(0, 24),
    },
    answer_kind: "graph_token_prediction",
  };
}

function makeWebSearchResult(query: string, webEvidenceDocs: any[], webSearchPayload: any) {
  const base = makeNoEvidenceResult(query);
  if (!webEvidenceDocs.length) {
    return {
      ...base,
      web_search: webSearchPayload,
      retrieval_trace: {
        ...base.retrieval_trace,
        web_search_provider: webSearchPayload?.provider,
        web_search_status: webSearchPayload?.status,
      },
    };
  }
  const prediction = makeGraphTokenPrediction(query, webEvidenceDocs);
  return {
    ...base,
    method: "atanor-graph-token-web-rag-v1",
    answer: prediction.answer,
    evidence_docs: webEvidenceDocs,
    citations: webEvidenceDocs.map((doc) => ({ doc_id: doc.chunk_id, source_doc_id: doc.doc_id, path: doc.url ?? doc.path, url: doc.url, score: doc.score })),
    web_search: webSearchPayload,
    answer_engine: {
      ...nativeAnswerEngine("web-ontology-graph-token-prediction-alpha"),
      name: "ATANOR Graph Token Predictor",
      surface_generation: "graph_walk",
      prediction_basis: "ontology_token_transition_graph",
      diagnostics: prediction.diagnostics,
    },
    retrieval_trace: {
      ...base.retrieval_trace,
      strategy: "raw web search harvest + ontology token transition graph + graph-token prediction",
      web_search_provider: webSearchPayload?.provider,
      web_search_status: webSearchPayload?.status,
      web_result_urls: webEvidenceDocs.map((doc) => doc.url ?? doc.path),
    },
    answer_kind: prediction.answer_kind,
    confidence: Math.max(base.confidence, 0.52),
  };
}

export function makeEvidence(query: string, webEvidenceDocs: any[] = [], webSearchPayload: any = null) {
  if (isGreetingQuery(query)) return makeConversationalResult(query, "greeting");
  if (isThanksQuery(query)) return makeConversationalResult(query, "thanks");
  if (isLegendQuery(query)) return makeLegendResult(query);
  if (isNodeInventoryQuery(query)) return makeNodeInventoryResult(query);

  const matchedNodes = demoNodes.filter((node) => nodeMatchesQuery(node.id, query));
  if (!matchedNodes.length) {
    if (webEvidenceDocs.length || webSearchPayload) return makeWebSearchResult(query, webEvidenceDocs, webSearchPayload);
    return isInternalStructureQuery(query) ? makeOpenGenerationResult(query) : makeNoEvidenceResult(query);
  }

  const matchedNodeIds = new Set(matchedNodes.map((node) => node.id));
  const evidenceDocs = [
    {
      doc_id: "demo-001",
      chunk_id: "demo-001#1",
      path: "data/cleaned/demo-001.txt",
      score: 1.42,
      snippet: "GraphRAG??KnowledgeGraph ??????????????????? ????????????? ??????筌띯뫔????????룸챷援?????Evidence??????留⑶뜮??????????????????????쇨덫櫻?",
      retrieval_signals: { lexical: 1.04, coverage: 0.75, graph_boost: 0.31, phrase_bonus: 0.2 },
    },
    {
      doc_id: "demo-002",
      chunk_id: "demo-002#1",
      path: "data/cleaned/demo-002.txt",
      score: 0.96,
      snippet: "Guardrail?? ????????????袁⑸즴筌?????Evidence?? ??????????????????????????????????????????븐뼐?????????",
      retrieval_signals: { lexical: 0.62, coverage: 0.5, graph_boost: 0.2, phrase_bonus: 0 },
    },
  ].filter((doc) => matchedNodes.some((node) => node.evidence_doc_ids.includes(doc.doc_id)));
  const matchedEdges = demoEdges.filter((edge) => matchedNodeIds.has(edge.source) || matchedNodeIds.has(edge.target));
  const graphPaths = matchedEdges.map((edge) => [edge.source, edge.relation, edge.target]);
  const utterance = makeNativeDemoUtterance(query, matchedNodes, graphPaths, evidenceDocs);
  return {
    query,
    method: "homage-graph-token-rag-v1",
    answer: utterance.answer,
    matched_nodes: matchedNodes,
    matched_edges: matchedEdges,
    evidence_docs: evidenceDocs,
    citations: evidenceDocs.map((doc) => ({ doc_id: doc.chunk_id, source_doc_id: doc.doc_id, path: doc.path, score: doc.score })),
    graph_paths: graphPaths,
    pmv: utterance.pmv,
    claim_plan: utterance.claim_plan,
    active_concepts: utterance.active_concepts,
    answer_kind: utterance.answer_kind,
    answer_engine: utterance.answer_engine,
    follow_up_questions: [],
    retrieval_trace: {
      strategy: "hybrid lexical ranking + ontology expansion + graph-token prediction",
      query_terms: query.toLowerCase().split(/\s+/).filter(Boolean),
      expanded_terms: matchedNodes.map((node) => node.id),
      ranked_chunk_ids: evidenceDocs.map((doc) => doc.chunk_id),
      matched_node_ids: matchedNodes.map((node) => node.id),
    },
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
      { id: "homage-oven", name: "ATANOR Oven", state: "complete", progress: 100, summary: "Dry-run scaffold produced a short loss trace.", metric_label: "last loss", metric_value: String(demoState.oven.last_loss) },
      { id: "graphrag", name: "GraphRAG", state: "complete", progress: 100, summary: "Demo evidence bundle is ready.", metric_label: "confidence", metric_value: "0.82" },
      { id: "knowledge-bakery", name: "Knowledge Bakery", state: "complete", progress: 100, summary: "Demo sentence components, phrase nodes, and activation index are available.", metric_label: "memory", metric_value: `${demoMemoryStatus().node_count} nodes` },
      { id: "guardrail", name: "Guardrail", state: demoState.guard.state === "idle" ? "idle" : "complete", progress: demoState.guard.state === "idle" ? 0 : 100, summary: "Ready to check draft claims.", metric_label: "guard score", metric_value: String(demoState.guard.overall_guard_score) },
      { id: "gpu-monitor", name: "GPU Monitor", state: "warning", progress: 35, summary: "Deployed sandbox uses telemetry fallback.", metric_label: "vram", metric_value: "fallback" },
    ],
  };
}

export function demoDataGateRun() {
  demoState.datagate = { ...demoState.datagate, state: "completed", run_id: `dg-demo-${Date.now()}`, started_at: now(), finished_at: now() };
  return demoState.datagate;
}

export function demoOntologyRun() {
  demoState.ontology = { ...demoState.ontology, state: "completed", started_at: now(), finished_at: now() };
  return demoState.ontology;
}

export function demoGraphRAGQuery(query: string, webEvidenceDocs: any[] = [], webSearchPayload: any = null) {
  const result: any = makeEvidence(query || "GraphRAG evidence", webEvidenceDocs, webSearchPayload);
  const isConversationResult = result.method === "atanor-conversation-router-v1" || ["greeting", "thanks", "conversation"].includes(result.answer_kind);
  if (!isConversationResult) {
    result.memory_activation = demoMemoryActivate(result.query);
    result.answer_engine = {
      ...(result.answer_engine ?? {}),
      memory_activation: "knowledge_bakery_spread_activation_v1",
    };
  }
  demoState.graphrag = { ...demoState.graphrag, state: "completed", started_at: now(), finished_at: now(), last_query: result.query, confidence: result.confidence, result };
  return demoState.graphrag;
}

export function demoGuardCheck(draft: string) {
  const hasOverclaim = /always|never|guarantees|completely eliminates/i.test(draft);
  const hasEvidence = /GraphRAG|Evidence|Guardrail|KnowledgeGraph|ATANOR|Ghost Shell|Payload Vault/i.test(draft);
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

const demoMemoryExtraNodes = [
  { id: "uses", label: "uses", type: "predicate", count: 2, confidence: 0.68 },
  { id: "phrase-graphrag-uses", label: "GraphRAG uses", type: "phrase", count: 1, confidence: 0.65 },
  { id: "phrase-guardrail-requires", label: "Guardrail requires", type: "phrase", count: 1, confidence: 0.63 },
  { id: "local-memory", label: "Local Memory", type: "compound", count: 2, confidence: 0.66 },
];

const demoMemoryNodes = [...demoNodes, ...demoMemoryExtraNodes];

const demoMemoryEdges = [
  ...demoEdges,
  { source: "graphrag", relation: "forms_phrase", target: "phrase-graphrag-uses", confidence: 0.69, count: 1 },
  { source: "phrase-graphrag-uses", relation: "continues_as", target: "uses", confidence: 0.66, count: 1 },
  { source: "uses", relation: "precedes", target: "evidence", confidence: 0.65, count: 1 },
  { source: "guardrail", relation: "forms_phrase", target: "phrase-guardrail-requires", confidence: 0.64, count: 1 },
  { source: "local-memory", relation: "co_occurs", target: "knowledgegraph", confidence: 0.61, count: 1 },
];

function memoryVector(id: string, index: number) {
  const angle = index * 1.618;
  const radius = 2.2 + (index % 4) * 0.65;
  return {
    x: Math.cos(angle) * radius,
    y: Math.sin(angle) * radius * 0.72,
    z: ((index % 5) - 2) * 0.62,
  };
}

export function demoMemoryStatus() {
  return {
    state: "completed",
    started_at: now(),
    finished_at: now(),
    error: null,
    db_path: "demo://homage.db",
    event_log_path: "demo://events.jsonl",
    built_at: now(),
    vector_source: "local_relation_projection_v1",
    document_count: 2,
    chunk_count: 4,
    node_count: demoMemoryNodes.length,
    edge_count: demoMemoryEdges.length,
    event_count: 18,
    vector_count: demoMemoryNodes.length,
    transition_count: 6,
    cooccurrence_count: 7,
    phrase_count: demoMemoryExtraNodes.filter((node) => node.type === "phrase").length,
    predicate_count: demoMemoryExtraNodes.filter((node) => node.type === "predicate").length,
    llm_policy: {
      external_llm: false,
      local_quantized_llm: false,
      pretrained_generation_weights: false,
    },
  };
}

export function demoMemoryGraph(limit = 600) {
  const visibleNodes = demoMemoryNodes.slice(0, limit).map((node, index) => ({
    ...node,
    ...memoryVector(node.id, index),
    projection_source: "local_relation_projection_v1",
  }));
  const visibleIds = new Set(visibleNodes.map((node) => node.id));
  return {
    nodes: visibleNodes,
    edges: demoMemoryEdges.filter((edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target)),
    status: demoMemoryStatus(),
  };
}

export function demoMemoryActivate(query: string) {
  const terms = query.toLowerCase().split(/[^a-z0-9???????????-??]+/i).filter(Boolean);
  const activeNodes = demoMemoryNodes
    .map((node, index) => {
      const haystack = `${node.id} ${node.label} ${node.type}`.toLowerCase();
      const matchScore = terms.reduce((score, term) => score + (haystack.includes(term) ? 1 : 0), 0);
      return {
        id: node.id,
        label: node.label,
        type: node.type,
        activation_score: Number((0.42 + matchScore + node.confidence + index * 0.005).toFixed(5)),
        confidence: node.confidence,
        projection_3d: Object.values(memoryVector(node.id, index)),
      };
    })
    .filter((node) => node.activation_score > 1.05)
    .sort((left, right) => right.activation_score - left.activation_score)
    .slice(0, 12);
  const fallbackNodes = activeNodes.length ? activeNodes : demoMemoryNodes.slice(0, 6).map((node, index) => ({
    id: node.id,
    label: node.label,
    type: node.type,
    activation_score: Number((0.7 - index * 0.04).toFixed(5)),
    confidence: node.confidence,
    projection_3d: Object.values(memoryVector(node.id, index)),
  }));
  const activeIds = new Set(fallbackNodes.map((node) => node.id));
  return {
    query,
    state: "completed",
    seed_nodes: fallbackNodes.slice(0, 3).map((node) => node.id),
    active_nodes: fallbackNodes,
    active_edges: demoMemoryEdges
      .filter((edge) => activeIds.has(edge.source) && activeIds.has(edge.target))
      .map((edge) => ({ ...edge, activation_score: edge.confidence })),
    semantic_skeleton: fallbackNodes.slice(0, 6).map((node, index) => ({
      role: index < 2 ? "seed" : "activated",
      node: node.id,
      label: node.label,
      score: node.activation_score,
    })),
    activation_policy: {
      max_nodes: 40,
      max_depth: 3,
      external_llm: false,
      local_quantized_llm: false,
      pretrained_generation_weights: false,
    },
    drift_report: demoMemoryDriftCheck(),
  };
}

export function demoMemoryDriftCheck() {
  return {
    state: "passed",
    checked_at: now(),
    next_check_seconds: 60,
    violations: [],
    warnings: [],
    constraints: {
      external_llm: false,
      local_quantized_llm: false,
      pretrained_generation_weights: false,
      template_only_answers: false,
    },
    status: demoMemoryStatus(),
  };
}
