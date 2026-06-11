# Session Log

## 2026-06-11

- Read the PRD from `Homage1.0_PRD.md`.
- Created `docs/` and copied the PRD to `docs/Homage1.0_PRD.md`.
- Scaffolded FastAPI backend in `apps/api`.
- Scaffolded Next.js frontend in `apps/web`.
- Added mock `GET /api/pipeline/status` contract.
- Added BakeBoard dashboard cards.
- Added Next.js proxy route for local dashboard-to-backend status calls.
- Added project operating documents and README startup instructions.
- Installed Python and npm dependencies.
- Verified FastAPI compile, Next.js production build, live API status response, and live frontend HTTP 200.
- Verified the rendered BakeBoard in the in-app browser with all seven pipeline cards visible.

## 2026-06-11 — Milestone 2: DataGate core package (Claude Code)

- Read `docs/Homage1.0_PRD.md`, `PROJECT_STATE.md`, `TASK_BOARD.md`,
  `CONTEXT_CAPSULE.md`, and `HANDOFF_CLAUDE.md`.
- Implemented the DataGate core library at `packages/datagate` (per
  HANDOFF_CLAUDE.md §3–§5): `pyproject.toml` (name `datagate`, `pydantic>=2`,
  py>=3.11), `README.md`, and the `datagate/` modules `config`, `models`,
  `hashing`, `io`, `scoring`, `runner`, plus the `filters/` package
  (`base`, `min_length`, `duplicate_hash`, `special_char_ratio`,
  `link_density`, ordered `default_filters`).
- Enforced contract invariants in models: rejected ⇒ `rejection_reason` +
  `rejected_by`; accepted ⇒ `quality_score`; failed `FilterResult` ⇒ `reason`.
- Deterministic by design: sorted discovery, NFC+whitespace-collapse
  normalization, sha256 `doc_id`, no randomness/timestamps in decision paths.
  `DuplicateHashFilter` state resets per `PipelineRunner.run()`.
- Runner writes `data/cleaned/{doc_id}.txt`, `data/rejected/{doc_id}.txt`, and
  `data/metadata/documents.jsonl` (full-batch overwrite); unreadable files
  become `read_error` rejections.
- Added pytest suite (`tests/`): model validation, all four filters, scorer,
  end-to-end runner, and repeated-run determinism — 8-scenario fixture corpus.
- `pip install -e "packages/datagate[dev]"` succeeded; `pytest packages/datagate`
  → **36 passed**; confirmed `import datagate` pulls in no FastAPI.
- Updated `PROJECT_STATE.md`; created `HANDOFF_CLAUDE_CODE.md`.
- Deferred (out of scope this milestone): API router/service, pipeline-status
  stage-1 hookup, BakeBoard panel, Next.js proxy routes.

## 2026-06-11 - DataGate API/UI wiring

- Wired DataGate core into FastAPI with `/api/datagate/run` and
  `/api/datagate/status`.
- Updated `/api/pipeline/status` so DataGate reflects real run state while the
  other six stages remain mocked.
- Added Next.js DataGate proxy routes.
- Added a BakeBoard DataGate panel with Run button, polling, status summary,
  accept rate, rejection breakdown, timestamp, and error display.
- Added API tests for idle status, run completion, 409 running guard, and the
  seven-stage pipeline contract.
- Verified Python compile, `pytest packages/datagate apps/api -q`, and the
  frontend production build.
- Ran local smoke on backend `8001` and frontend `3001`; verified DataGate
  run/status, seven-stage pipeline status, Next proxy status, and BakeBoard UI
  Run button.

## 2026-06-11 - Homage1.0 Alpha end-to-end

- Implemented Ontology Forge, GraphRAG, Guardrail, telemetry, model scaffold,
  and trainer dry-run packages.
- Added FastAPI routers and services for all Alpha panels.
- Rebuilt BakeBoard into a unified single-page Alpha dashboard.
- Added deployed Next.js API fallback routes so the Vercel app works without
  local FastAPI.
- Added sample raw documents and training sample data.
- Verified 46 Python tests, Python compile, and frontend build.
- Ran local end-to-end smoke through DataGate, Ontology, GraphRAG, Guardrail,
  telemetry, Oven dry-run, pipeline status, and browser UI.
- Deployed to Vercel and verified the deployment in-browser.

## 2026-06-11 - Neuro-Efficiency research and architecture update

- Reviewed academic/professional sources for SNNs, neuromorphic software,
  continual learning, few-shot prototypes, self-supervised masking, model
  compression, and Loihi-style event hardware constraints.
- Added `docs/RESEARCH_NEURO_EFFICIENCY.md` with source links and structural
  decisions.
- Implemented `packages/neuro_efficiency`, a deterministic planning layer for
  event sparsity, modular routing, continual/few-shot/self-supervised learning
  policies, compression levers, and estimated compute reduction.
- Added FastAPI `GET/POST /api/neuro/plan`.
- Added Next.js deployed fallback route for `/api/neuro/plan`.
- Added a BakeBoard Neuro-Efficiency Layer panel and Rebalance action.
- Verified Python tests: 49 passed; compileall passed; Next production build
  passed.
- Verified local browser UI and deployed Vercel UI, including the Rebalance
  button.
- Deployed production:
  https://web-2ro6t5sdi-anthony-kims-projects-bc874109.vercel.app

## 2026-06-11 - MiroFish-inspired Korean console UI

- Inspected `666ghj/MiroFish` and the live demo at
  `https://666ghj.github.io/mirofish-demo/console/process/proj_f95898d38529`.
- Confirmed the useful UI pattern: top graph/split/workbench switcher, left
  memory graph, right process/workbench panel, and bottom system dashboard log.
- Noted MiroFish is AGPL-3.0, so no code was copied verbatim.
- Rebuilt the BakeBoard frontend in Korean as a MiroFish-inspired console:
  left ontology memory visualization, right learning-process/RAG-chat
  workbench, graph/split/workbench layout controls, and system log.
- Made RAG visible as a first-class chat workbench with evidence-backed
  responses.
- Verified `npm --workspace apps/web run build`.
- Verified local browser UI: split layout, layout switcher, and RAG chat
  response with evidence.
- Deployed and verified production:
  https://web-5rxd988wn-anthony-kims-projects-bc874109.vercel.app

## 2026-06-11 - Hybrid GraphRAG upgrade

- Reviewed Microsoft GraphRAG, Haystack, and MiroFish references for the RAG
  and visualization direction.
- Kept Homage on an internal deterministic engine instead of copying external
  code; MiroFish remains UI-structure inspiration only because it is AGPL-3.0.
- Upgraded `packages/rag_engine` from keyword matching to hybrid GraphRAG:
  document chunking, BM25-style lexical scoring, ontology node matching,
  one-hop graph expansion, phrase/coverage/graph retrieval signals, answer
  synthesis, citations, follow-up questions, and retrieval trace.
- Updated the Vercel fallback GraphRAG response to expose the same answer,
  citation, trace, and evidence-signal shape.
- Updated the Korean RAG chat UI to render synthesized answers and retrieval
  signals inside evidence cards.
- Added `docs/RAG_REFERENCE.md`.
- Verified locally in a browser at `http://127.0.0.1:3014`.
- Deployed production:
  https://web-8hayowqq4-anthony-kims-projects-bc874109.vercel.app
- `homage.vercel.app` was unavailable, so the deployment was aliased to:
  https://homage-alpha.vercel.app
- Verified the alias in-browser, including RAG chat answer rendering and
  retrieval-signal evidence cards.

## 2026-06-11 - RAG graph interaction and PRD audit

- Audited the current implementation against `docs/Homage1.0_PRD.md` and added
  `docs/PRD_ENGINE_AUDIT.md`.
- Confirmed Alpha covers DataGate, Ontology Forge, hybrid GraphRAG, Guardrail,
  telemetry, dry-run Oven, Neuro-Efficiency, and BakeBoard, while Harvest,
  Knowledge Bakery vector DB, full Homage-Core-30M training, and a separate
  Utterance Engine remain future work.
- Fixed RAG chat layout pressure by widening the workbench side in split mode,
  giving chat messages their own scroll region, widening action buttons, and
  auto-scrolling to the newest answer.
- Added interactive graph controls inspired by MiroFish-style operation:
  graph/split/workbench modes, refresh, full graph mode, node search/focus,
  zoom in/out, directional pan, pointer-drag pan, reset, and node/edge detail.
- Verified all visible buttons in the local browser: layout modes, Refresh,
  graph expand/reset/search/zoom/pan, RAG send, Guardrail check, DataGate,
  Ontology, GraphRAG open, Oven dry-run, Neuro replan, and header reset.
- Captured browser screenshots in `docs/screenshots/`.
- Verified `npm --workspace apps/web run build` and the 49-test Python suite.
- Deployed the updated UI to Vercel and re-aliased
  `https://homage-alpha.vercel.app` to the new production deployment.
- Verified the deployed alias in-browser with graph search/zoom and RAG answer
  evidence rendering.

## 2026-06-11 - Build Start and 3D GraphRAG flow

- Reviewed the Reddit discussion on LLM graph traversal for RAG and the linked
  `similarity-graph-traversal-semantic-rag-research` repository.
- Captured the design correction from the thread: semantic-similarity graphs
  are not full knowledge graphs unless Homage preserves typed entities,
  relation semantics, deduplication, and graph mutation/update history.
- Added `POST /api/factory/build/start`, an Alpha factory orchestrator that
  fetches a small allowlisted reference set, reports harvest status, emits
  typed ontology/RAG graph frames, and opens a training gate for the Homage Oven
  dry-run once enough typed nodes, edges, and evidence are visible.
- Added a Three.js `Rag3DScene` with drag rotation, wheel zoom, node selection,
  traversal highlighting, labels, and staged graph growth.
- Wired the Korean BakeBoard `Build 시작` button to switch into the 3D RAG
  memory view, show live process metrics, list harvested sources, and carry
  evidence into the RAG chat workbench.
- Added `docs/BUILD_FLOW_3D_RAG.md`.
- Verified `pytest` for all Python packages and API: 49 passed.
- Verified `npm --workspace apps/web run build`.
- Verified locally in the in-app browser with screenshots for Build Start,
  3D graph growth, drag/zoom interaction, and RAG evidence rendering.
- Deployed production:
  https://web-r27gc51la-anthony-kims-projects-bc874109.vercel.app
- Re-aliased production to:
  https://homage-alpha.vercel.app
- Verified the deployed alias in-browser with screenshots for Build Start, 3D
  GraphRAG growth, drag/zoom interaction, training-gate display, and RAG
  evidence rendering.

## 2026-06-11 - Compact console and continuous graph growth

- Changed the default split console from an almost even split to a 70/30 layout
  so the ontology/RAG memory graph dominates the screen while the process panel
  stays compact.
- Reduced UI density across the header, graph controls, process cards, chat
  composer, evidence cards, and system log.
- Added deterministic live-synapse growth pulses after Build Start so the 3D
  RAG graph keeps adding nodes and edges instead of stopping at the initial
  graph frames.
- Wired Learning Process buttons through a common running-state wrapper and
  direct result updates so DataGate, Ontology, GraphRAG, Guardrail, Oven, and
  Neuro actions visibly respond in the deployed fallback UI.
- Updated DataGate deployed fallback to return the completed run state instead
  of a bare running marker.
- Verified `npm --workspace apps/web run build`.
- Verified locally in-browser:
  - split ratio measured 1008px / 432px at 1440px width
  - Build Start grew from the base graph into live pulses
  - Learning Process buttons completed without errors
- Deployed production:
  https://web-2cq1iubf8-anthony-kims-projects-bc874109.vercel.app
- Re-aliased production to:
  https://homage-alpha.vercel.app
- Verified the deployed alias in-browser with compact 70/30 layout, live growth,
  DataGate process-button execution, and no application errors.

## 2026-06-11 - Native Homage Utterance Engine correction

- Re-read the PRD sections on role separation, Next Thought generation,
  Homage-Core, GraphRAG context bundles, and Homage Utterance Engine.
- Corrected the implementation direction away from external LLM adapters.
- Added a native Alpha utterance stage around GraphRAG:
  `intent -> concepts -> ontology path -> claim plan -> evidence -> surface text`.
- GraphRAG responses now return PMV, claim plan, active concepts, answer engine
  stages, and `external_llm: false`.
- Added graph color-legend intent handling so "색깔별 노드 의미" answers from
  the current ontology/RAG graph instead of falling through to generic evidence
  search.
- Verified locally with browser screenshots:
  - `docs/screenshots/84-native-cause-answer-local.png`
  - `docs/screenshots/85-native-legend-answer-local.png`
- Added chat send locking while an answer is generating to prevent slower
  GraphRAG responses from overwriting later local graph-inspection status.
- Redeployed production:
  https://web-bpxui7tde-anthony-kims-projects-bc874109.vercel.app
- Re-aliased production to:
  https://homage-alpha.vercel.app
- Verified production API responses for native GraphRAG and color legend
  answers with `external_llm: false`.

## 2026-06-11 - Sustained learning stability profile

- Added a target-hardware stability planner for Ryzen 9 9950X3D, RTX 5080
  16GB, 32GB RAM, and 1TB SSD.
- Added `GET/POST /api/neuro/stability` in FastAPI and the deployable Next.js
  fallback API route.
- Added queue caps, RAM/VRAM/storage watermarks, graph hot-window sizing,
  UI render budgets, checkpoint cadence, and backpressure policy.
- Added the BakeBoard `지속 운전 안전장치` process card and made learning-volume
  presets recalculate stability targets:
  - lite: 3,000 nodes / 9,000 edges / 12h
  - standard: 10,000 nodes / 40,000 edges / 72h
  - deep: 25,000 nodes / 100,000 edges / 168h
  - max: 50,000 nodes / 240,000 edges / 168h
- Fixed an auto-refresh bug where the stability card could revert from the
  selected learning volume back to the default profile.
- Tightened the stability summary card layout to avoid cramped text in the
  70/30 split view.
- Added `docs/LONG_RUN_STABILITY_PLAN.md`.
- Verified:
  - `python -m compileall packages\neuro_efficiency apps\api\app`
  - `python -m pytest packages\neuro_efficiency apps\api -q`: 11 passed
  - full Alpha Python suite with explicit `PYTHONPATH`: 55 passed
  - `npm --workspace apps/web run build`
  - local in-app browser at `http://127.0.0.1:3024`
- Deployed production:
  https://web-i1wdnz9bk-anthony-kims-projects-bc874109.vercel.app
- Re-aliased production to:
  https://homage-alpha.vercel.app
- Verified production `GET/POST /api/neuro/stability`.
- Verified production browser UI with the `최대` sustained-stability profile.
- Captured screenshots:
  - `docs/screenshots/88-sustained-stability-local.png`
  - `docs/screenshots/89-sustained-stability-max-local.png`
  - `docs/screenshots/90-sustained-stability-final-local.png`
  - `docs/screenshots/91-sustained-stability-production.png`
  - `docs/screenshots/92-sustained-stability-production-card.png`
  - `docs/screenshots/93-sustained-stability-production-card-visible.png`

## 2026-06-11 - Hardware benchmark adaptation

- Added `build_hardware_benchmark` to `packages/neuro_efficiency`.
- Added `GET/POST /api/neuro/benchmark` to FastAPI.
- Added a deployable Next.js fallback route at `/api/neuro/benchmark`.
- The local benchmark reads CPU thread count, RAM, GPU/VRAM through
  `nvidia-smi`, workspace disk capacity/free space, a short CPU loop probe, and
  a short disk write probe.
- Added tolerance so OS-reported 31GB RAM / 15.9GB VRAM is treated as the
  intended 32GB / 16GB hardware class.
- Added the BakeBoard `시스템 벤치마크` process card, startup benchmark run, and
  `벤치마크 재측정` button.
- Auto-apply now changes learning volume only when
  `can_read_local_hardware: true`, so Vercel fallback does not pretend to
  measure the user's actual PC.
- Verified the actual local machine:
  - profile: `Performance desktop`
  - recommendation: `max`
  - CPU threads: 32
  - RAM: about 31.1GB
  - GPU: NVIDIA GeForce RTX 5080
  - VRAM: about 15.9GB
  - disk write probe: about 900MB/s to 1GB/s in verification runs
- Verified locally with FastAPI on `127.0.0.1:8002` and Next production server
  on `127.0.0.1:3025`.
- Browser verification confirmed `최대` was automatically selected and Build
  Start prepared 768 chunks / 420k chars.
- Deployed production:
  https://web-ovsyv6i2f-anthony-kims-projects-bc874109.vercel.app
- Re-aliased production to:
  https://homage-alpha.vercel.app
- Verified production `GET /api/neuro/benchmark` returns `source:
  server-fallback` and `can_read_local_hardware: false`.
- Verified production browser UI shows fallback benchmark labeling instead of
  pretending to measure the viewer PC.
- Captured screenshot:
  - `docs/screenshots/94-hardware-benchmark-local.png`
  - `docs/screenshots/95-hardware-benchmark-production.png`

## 2026-06-11 - Active node signal and open structure answer

- Changed the RAG signal visualization from a path-like trace to active node
  pulses.
- The overlay now says `활성 노드` instead of `신호 경로`.
- Active GraphRAG nodes pulse orange while relation lines stay subdued, so the
  visualization reads more like momentary brain activation than route finding.
- Added internal architecture synthesis context for no-direct-evidence answers.
- `네 구조 설명해봐` now generates a native Homage architecture answer instead
  of saying the question is not directly connected to current evidence.
- Internal architecture context is used only for synthesis; returned
  `evidence_docs` and `citations` remain empty when no retrieved document chunk
  supports the answer.
- Added a regression test for structure questions without direct evidence.
- Verified:
  - `python -m compileall packages\rag_engine apps\api\app`
  - full Alpha Python suite with explicit `PYTHONPATH`: 59 passed
  - `npm --workspace apps/web run build`
  - local browser at `http://127.0.0.1:3026`
- Deployed production:
  https://web-ffvjjolxy-anthony-kims-projects-bc874109.vercel.app
- Re-aliased production to:
  https://homage-alpha.vercel.app
- Verified production API and browser UI:
  - `POST /api/graphrag/query` returns
    `homage-native-open-structure-v1`
  - `external_llm` remains `false`
  - no direct-evidence fallback text appears for `네 구조 설명해봐`
  - active node signal appears as orange pulsing nodes, not a path trace
- Captured screenshots:
  - `docs/screenshots/96-structure-answer-active-nodes-local.png`
  - `docs/screenshots/97-active-node-pulses-local.png`
  - `docs/screenshots/98-structure-answer-no-path-local.png`
  - `docs/screenshots/99-active-node-pulses-no-path-local.png`
  - `docs/screenshots/100-structure-answer-production.png`
  - `docs/screenshots/101-active-node-pulses-production.png`

## 2026-06-11 - No-evidence RAG and custom node target

- Split no-direct-evidence RAG behavior:
  - Homage/self-structure questions still use internal architecture context.
  - External unknown facts now return a no-evidence native answer instead of
    leaking the Homage architecture explanation.
- Removed `읽힌 경로` from generated GraphRAG answer text; the chat now says
  active node signal instead.
- Added regression coverage for unknown external entity questions.
- Added a direct `목표 노드` number input beside the learning-volume presets.
- Sent `target_nodes` to stability planning and Build Start.
- Build Start now scales chunk budget, text budget, and representative node
  budget from the custom target-node count.
- Increased representative graph generation and made generated ids unique
  across repeated topic waves.
- Improved 3D RAG spacing with deterministic spread layout, collision
  relaxation, label thinning for dense graphs, and graph-size camera scaling.
- Verified locally:
  - `python -m pytest packages\rag_engine -q`: 6 passed
  - full Alpha Python suite with explicit `PYTHONPATH`: 60 passed
  - `npm --workspace apps/web run build`
  - local browser at `http://127.0.0.1:3027`
- Browser verification:
  - `GraphRAG가 뭐야` answered without `읽힌 경로`
  - `유재석이 누구야` returned no-evidence memory coverage text with
    `external LLM` disabled wording
  - `1,200` target nodes produced a larger representative graph
  - max target-node stress reached `358/360` representative nodes and
    `358 nodes / 739 relations` by DOM verification
  - WebGL full screenshot capture timed out at the 358-node state; saved
    screenshots cover the visible 48, 73, 221, and 257 node states
- Deployed production:
  https://web-7784z7z4w-anthony-kims-projects-bc874109.vercel.app
- Re-aliased production to:
  https://homage-alpha.vercel.app
- Verified production API:
  - `유재석이 누구야` returns `homage-native-no-evidence-v1`
  - `external_llm` remains `false`
  - no Homage architecture leak or `읽힌 경로` text appears
  - `target_nodes: 50000` returns visual budget 360, 310 base nodes, 609 edges,
    and 2000 chunks
- Production browser verification confirmed the new `목표 노드` input is visible.
  In-app browser text entry on production was blocked by the browser virtual
  clipboard extension, so production interaction was verified through API plus
  visible UI capture.
- Captured screenshots:
  - `docs/screenshots/102-custom-node-target-local.png`
  - `docs/screenshots/103-rag-no-evidence-local.png`
  - `docs/screenshots/104-large-graph-spacing-local.png`
  - `docs/screenshots/105-large-graph-final-local.png`
  - `docs/screenshots/108-production-node-target-visible.png`
