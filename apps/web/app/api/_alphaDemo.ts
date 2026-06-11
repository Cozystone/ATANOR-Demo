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

function normalizedQuery(query: string) {
  return query.trim().toLowerCase();
}

function includesAny(query: string, terms: string[]) {
  return terms.some((term) => query.includes(term));
}

function isGreetingQuery(query: string) {
  const normalized = normalizedQuery(query);
  return /^(안녕|안녕하세요|하이|헬로|반가워|hi|hello|hey|yo)[\s!.?。！？]*$/i.test(normalized);
}

function isThanksQuery(query: string) {
  const normalized = normalizedQuery(query);
  return /^(고마워|감사|감사합니다|땡큐|thanks|thank you)[\s!.?。！？]*$/i.test(normalized);
}

function nodeMatchesQuery(nodeId: string, query: string) {
  const normalized = normalizedQuery(query);
  const termMap: Record<string, string[]> = {
    graphrag: ["graphrag", "graph rag", "그래프rag", "그래프 rag", "rag", "검색", "질문", "답변", "retrieval"],
    knowledgegraph: ["knowledgegraph", "knowledge graph", "지식그래프", "지식 그래프", "온톨로지", "그래프", "노드", "관계"],
    evidence: ["evidence", "근거", "문서", "출처", "citation", "인용", "검증"],
    guardrail: ["guardrail", "guard rail", "가드레일", "검증", "환각", "과장", "hallucination"],
  };
  return includesAny(normalized, termMap[nodeId] ?? []);
}

function makeConversationalResult(query: string, kind: "greeting" | "thanks" | "no_match") {
  const answerByKind = {
    greeting:
      "안녕하세요. 저는 Homage RAG 콘솔입니다. 빌드로 만들어진 온톨로지 메모리와 근거 문서를 바탕으로 답할 수 있어요. 예를 들어 GraphRAG, Guardrail, 온톨로지 관계, 학습 과정에 대해 물어보면 근거 경로를 함께 보여드릴게요.",
    thanks:
      "천만에요. 이어서 GraphRAG 검색, Guardrail 검증, 온톨로지 메모리 구조 중 궁금한 부분을 물어보면 바로 이어서 확인해드릴게요.",
    no_match:
      "지금 질문은 현재 데모 온톨로지의 근거 문서와 직접 연결되지 않았습니다. GraphRAG, 지식 그래프, 근거 문서, Guardrail 검증처럼 학습된 메모리의 개념으로 질문하면 관련 노드와 문서 근거를 함께 찾아드릴게요.",
  };
  return {
    query,
    method: "homage-conversation-router-v1",
    answer: answerByKind[kind],
    matched_nodes: [],
    matched_edges: [],
    evidence_docs: [],
    citations: [],
    graph_paths: [],
    follow_up_questions: ["GraphRAG가 근거를 어떻게 쓰는지 볼까요?", "Guardrail 검증 흐름을 확인할까요?"],
    retrieval_trace: {
      strategy: kind === "no_match" ? "no evidence match; retrieval skipped" : "conversational intent; retrieval skipped",
      query_terms: normalizedQuery(query).split(/\s+/).filter(Boolean),
      expanded_terms: [],
      ranked_chunk_ids: [],
      matched_node_ids: [],
    },
    confidence: kind === "no_match" ? 0.35 : 0.96,
  };
}

export function makeEvidence(query: string) {
  if (isGreetingQuery(query)) return makeConversationalResult(query, "greeting");
  if (isThanksQuery(query)) return makeConversationalResult(query, "thanks");

  const matchedNodes = demoNodes.filter((node) => nodeMatchesQuery(node.id, query));
  if (!matchedNodes.length) return makeConversationalResult(query, "no_match");

  const matchedNodeIds = new Set(matchedNodes.map((node) => node.id));
  const evidenceDocs = [
    {
      doc_id: "demo-001",
      chunk_id: "demo-001#1",
      path: "data/cleaned/demo-001.txt",
      score: 1.42,
      snippet: "GraphRAG는 KnowledgeGraph 구조를 사용해 답변 근거가 되는 Evidence를 검색합니다.",
      retrieval_signals: { lexical: 1.04, coverage: 0.75, graph_boost: 0.31, phrase_bonus: 0.2 },
    },
    {
      doc_id: "demo-002",
      chunk_id: "demo-002#1",
      path: "data/cleaned/demo-002.txt",
      score: 0.96,
      snippet: "Guardrail은 답변의 주장을 Evidence와 대조하고 과신 표현을 표시합니다.",
      retrieval_signals: { lexical: 0.62, coverage: 0.5, graph_boost: 0.2, phrase_bonus: 0 },
    },
  ].filter((doc) => matchedNodes.some((node) => node.evidence_doc_ids.includes(doc.doc_id)));
  const matchedEdges = demoEdges.filter((edge) => matchedNodeIds.has(edge.source) || matchedNodeIds.has(edge.target));
  const graphPaths = matchedEdges.map((edge) => [edge.source, edge.relation, edge.target]);
  return {
    query,
    method: "homage-hybrid-graphrag-v1",
    answer: `질문 '${query}'는 ${matchedNodes.map((node) => node.label).join(", ")} 노드와 연결됩니다. GraphRAG는 관련 지식 그래프 경로를 확장한 뒤, 연결된 문서 근거만 사용해 답변을 합성합니다.`,
    matched_nodes: matchedNodes,
    matched_edges: matchedEdges,
    evidence_docs: evidenceDocs,
    citations: evidenceDocs.map((doc) => ({ doc_id: doc.chunk_id, source_doc_id: doc.doc_id, path: doc.path, score: doc.score })),
    graph_paths: graphPaths,
    follow_up_questions: ["이 답변을 Guardrail로 검증할까요?", "관련 온톨로지 경로를 더 넓게 확장할까요?"],
    retrieval_trace: {
      strategy: "hybrid lexical BM25-style ranking + ontology 1-hop expansion + deterministic synthesis",
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
      { id: "homage-oven", name: "Homage Oven", state: "complete", progress: 100, summary: "Dry-run scaffold produced a short loss trace.", metric_label: "last loss", metric_value: String(demoState.oven.last_loss) },
      { id: "graphrag", name: "GraphRAG", state: "complete", progress: 100, summary: "Demo evidence bundle is ready.", metric_label: "confidence", metric_value: "0.82" },
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

export function demoGraphRAGQuery(query: string) {
  const result = makeEvidence(query || "GraphRAG evidence");
  demoState.graphrag = { ...demoState.graphrag, state: "completed", started_at: now(), finished_at: now(), last_query: result.query, confidence: result.confidence, result };
  return demoState.graphrag;
}

export function demoGuardCheck(draft: string) {
  const hasOverclaim = /always|never|guarantees|completely eliminates|항상|절대|보장/i.test(draft);
  const hasEvidence = /GraphRAG|Evidence|Guardrail|KnowledgeGraph|근거|문서|가드레일|지식\s*그래프|검증/i.test(draft);
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
