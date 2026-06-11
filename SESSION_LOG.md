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
