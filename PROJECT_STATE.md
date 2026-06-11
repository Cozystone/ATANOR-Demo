# Project State

## Current Status

Homage1.0 Alpha is implemented and deployed as an interactive MVP with a
MiroFish-inspired console UI and research-backed Neuro-Efficiency Layer.

Deployment:

- https://homage-alpha.vercel.app

## Completed Alpha Scope

- DataGate API and BakeBoard integration.
- Ontology Forge deterministic concept/edge extraction.
- GraphRAG deterministic hybrid retrieval with chunk ranking, ontology
  expansion, synthesized answer text, citations, and retrieval trace.
- Guardrail deterministic claim support and overclaim detection.
- GPU/system telemetry with graceful fallback.
- Homage-Core-30M model scaffold and safe training dry-run trace.
- Homage Utterance Engine Alpha:
  - PRD-style `intent -> concepts -> ontology path -> claim plan -> evidence -> surface text` answer flow
  - native GraphRAG answer generation metadata: PMV, claim plan, active concepts, answer engine stages
  - no external or pretrained LLM calls
- Neuro-Efficiency Layer for event sparsity, modular routing, continual
  learning policy, few-shot prototypes, self-supervised masking, compression,
  and estimated compute reduction.
- Sustained Learning Stability Profile:
  - `GET/POST /api/neuro/stability`
  - target hardware envelope for Ryzen 9 9950X3D, RTX 5080 16GB, 32GB RAM, 1TB SSD
  - RAM/VRAM/storage watermarks, queue caps, graph hot-window policy,
    checkpoint cadence, and backpressure rules
  - BakeBoard `지속 운전 안전장치` stage with selectable learning-volume targets
- MiroFish-inspired BakeBoard console:
  - top graph/split/workbench layout switcher
  - left ontology-memory graph visualization
  - right learning process or RAG chat workbench
  - bottom system dashboard log
- Next.js API fallback layer so deployed BakeBoard works without local FastAPI.
- Research note: `docs/RESEARCH_NEURO_EFFICIENCY.md`.
- UI reference note: `docs/UI_REFERENCE_MIROFISH.md`.
- RAG reference note: `docs/RAG_REFERENCE.md`.
- PRD engine audit: `docs/PRD_ENGINE_AUDIT.md`.
- Build Start Alpha flow:
  - `POST /api/factory/build/start`
  - allowlisted web reference harvest
  - typed ontology/RAG graph frames
  - Three.js 3D GraphRAG traversal visualization
  - Alpha training gate before Homage Oven dry-run handoff
  - evidence snippets carried into the RAG chat workbench
  - continuous live-synapse growth pulses after Build Start
- Build flow note: `docs/BUILD_FLOW_3D_RAG.md`.
- Long-run stability note: `docs/LONG_RUN_STABILITY_PLAN.md`.

## Verification

- Python editable package install passed for all Alpha packages including
  `packages/neuro_efficiency`.
- `pytest packages/datagate packages/ontology_forge packages/rag_engine packages/guard packages/model packages/trainer packages/neuro_efficiency apps/api -q` passed: 49 tests.
- Python compile check passed for backend and packages.
- `npm --workspace apps/web run build` passed.
- MiroFish repo and live demo were inspected; code was not copied because the
  source license is AGPL-3.0.
- Local API smoke passed:
  - DataGate completed on sample raw docs.
  - Ontology Forge created 11 nodes and 4 edges.
  - GraphRAG returned synthesized answer text, citations, evidence, trace, and
    confidence.
  - Guardrail returned claim support and guard score.
  - GPU telemetry returned real data or fallback.
  - Homage Oven dry-run returned loss trace and checkpoint manifest.
  - `/api/neuro/plan` returned the Homage Neuro-Efficiency Layer plan.
  - `/api/pipeline/status` returned 7 stages.
- Local browser verification passed for the split console UI, ontology memory
  graph, layout switcher, RAG chat, synthesized answer, and retrieval-signal
  evidence cards.
- Local browser verification also passed for graph search, zoom in/out,
  directional pan, pointer drag pan, graph reset, graph/split/workbench layout
  modes, process action buttons, RAG send, Guardrail check, Refresh, and header
  reset.
- Vercel production deploy succeeded.
- `homage.vercel.app` was already in use; production is aliased to
  `https://homage-alpha.vercel.app`.
- Deployed browser verification passed for the split console UI, ontology
  memory graph, layout switcher, RAG chat, evidence-backed response, and
  `/api/neuro/plan`.
- Latest deployed alias verification passed for graph search/zoom and
  auto-scrolled RAG answer evidence rendering.
- Local browser verification passed for `Build 시작`, reference harvest
  reporting, staged 3D GraphRAG growth, drag rotation, wheel zoom, nonblank
  canvas screenshot inspection, training-gate display, and RAG evidence cards.
- `POST /api/factory/build/start` is included in the Next.js production build.
- Latest Vercel production deploy succeeded and `https://homage-alpha.vercel.app`
  now points to the Build Start / 3D GraphRAG version.
- Deployed browser verification passed for `Build 시작`, 3D GraphRAG canvas
  rendering, drag/zoom interaction, training-gate display, and RAG evidence
  cards.
- Compact console verification passed:
  - split layout is now 70/30, measured as 1008px / 432px at 1440px width
  - UI density was reduced across header, graph controls, process cards, chat,
    and system log
  - Build Start continues adding live-synapse nodes after the initial graph
    frames
  - Learning Process buttons show running state, update their cards directly,
    and were verified locally and on the deployed alias
  - Latest production deploy is aliased to `https://homage-alpha.vercel.app`
- Native Homage Utterance Engine verification passed:
  - local API and browser answered GraphRAG questions with
    `homage-native-graphrag-utterance-v1`
  - color legend questions route to `homage-graph-legend-v1` with no evidence
    card fallback
  - answer metadata includes PMV, claim plan, active concepts, native engine
    stages, and `external_llm: false`
  - production API at `https://homage-alpha.vercel.app` returned the same
    native engine metadata after redeploy
- Sustained Learning Stability verification passed:
  - `python -m compileall packages\neuro_efficiency apps\api\app` passed
  - `python -m pytest packages\neuro_efficiency apps\api -q` passed: 11 tests
  - full Alpha Python suite passed with explicit `PYTHONPATH`: 55 tests
  - `npm --workspace apps/web run build` passed
  - local browser verification passed for the `지속 운전 안전장치` process card,
    learning-volume `최대` selection, `안정성 계산` button, and persistence after
    the 10-second auto-refresh interval
  - production deploy succeeded and `https://homage-alpha.vercel.app` now
    points to the sustained stability version
  - production API verification passed for `GET/POST /api/neuro/stability`
  - production browser verification passed for the `최대` stability profile card
  - screenshots:
    - `docs/screenshots/88-sustained-stability-local.png`
    - `docs/screenshots/89-sustained-stability-max-local.png`
    - `docs/screenshots/90-sustained-stability-final-local.png`
    - `docs/screenshots/91-sustained-stability-production.png`
    - `docs/screenshots/92-sustained-stability-production-card.png`
    - `docs/screenshots/93-sustained-stability-production-card-visible.png`

## Known Limitations

- Alpha does not use external or pretrained LLMs. The new Homage Utterance
  Engine is a native Alpha generator around GraphRAG context bundles, while
  Homage-Core remains a shape/training scaffold rather than a trained decoder
  that can freely sample language.
- Build Start is an Alpha orchestrator. It fetches a small allowlisted reference
  set and uses curated reference snippets for the UI/training-gate trace; it is
  not broad autonomous crawling or real model training yet.
- Deployed Vercel app uses deterministic demo fallback API routes.
- Local FastAPI run state is in-memory and single-process.
- DataGate is full-batch overwrite only.
- Ontology extraction is regex/rule-based and intentionally simple.
- Homage Oven dry-run is a scaffold, not production training.
- Neuro-Efficiency values are deterministic estimates until real event traces,
  model update logs, and hardware profiles are persisted.
- The ontology-memory graph is a deterministic UI visualization, not a full
  force-directed runtime graph engine yet, but it now supports zoom, pan,
  drag, search focus, node detail, reset, and full-screen graph mode.
- PRD audit confirms Alpha is not yet the full final engine: Harvest crawling,
  Knowledge Bakery vector DB/summary tree, real Homage-Core-30M training, and
  a separate Utterance Engine remain future work.
- The 3D GraphRAG visual is a live client-side visualization of the Alpha
  graph/traversal contract; persistent vector storage, graph mutation history,
  and real continual-training events remain future work.
- Live-synapse growth is currently a deterministic client-side Alpha simulation
  of continual learning. It visually proves the growth loop, but persistent
  graph mutation storage and real training updates are still next milestones.
- Sustained stability is currently an enforceable planning/API/UI layer. The
  live ontology store still needs to move from JSON snapshots to append-only
  graph events plus a SQLite WAL hot index before very long unattended runs.
- npm audit still reports dependency advisories; no force fix applied.

## Next Recommended Milestone

1. Add the append-only ontology event log and SQLite WAL hot graph index.
2. Persist Alpha run history and Build Start graph frames with SQLite.
3. Persist live-synapse graph mutations and replay them as a real learning
   event stream.
4. Add a real Harvest connector with source allowlists, robots policy, and
   deduped document provenance.
5. Persist Knowledge Bakery vector/graph memory and graph mutation history.
6. Log real event density from DataGate and GraphRAG traces.
