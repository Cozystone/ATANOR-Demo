# Context Capsule

## Current Objective

Homage1.0 Alpha end-to-end MVP is implemented, verified, and deployed with a
research-backed Neuro-Efficiency Layer and a sustained-learning stability
profile with startup hardware benchmark adaptation.
Latest work also changed RAG answer behavior so no-direct-evidence structure
questions still generate a native architecture answer, external unknown facts
return no-evidence memory coverage instead of architecture leakage, and GraphRAG
signals now show active node pulses rather than path text. The latest update
adds `∞` continuous learning mode with cumulative elapsed time, a stop control,
and a bounded rolling 3D graph render window. The current follow-up clarifies
the real/simulated boundary, adds adaptive 3D zoom, and blocks/stops infinite
learning when real local telemetry crosses safety watermarks. Current work adds
a local-web-to-local-FastAPI companion connection and clarifies that
`target_nodes` is a long-run budget while `graph_3d` is a representative browser
sample. Production UI still works as a fallback demo; real PC measurement should
use local web + local FastAPI unless an HTTPS local companion is configured.

## Current Branch

`feature/datagate-v0`

## Last Commit

Latest local commit before this update: Clarify live learning limits and safety telemetry

## Deployment

- https://homage-alpha.vercel.app

## Relevant Files

- `apps/api/app/main.py`
- `apps/api/app/services/alpha_services.py`
- `apps/web/app/page.tsx`
- `apps/web/app/api/_alphaDemo.ts`
- `apps/api/app/routers/neuro.py`
- `apps/web/app/api/neuro/plan/route.ts`
- `apps/web/app/api/neuro/stability/route.ts`
- `apps/web/app/api/neuro/benchmark/route.ts`
- `packages/neuro_efficiency`
- `docs/RESEARCH_NEURO_EFFICIENCY.md`
- `docs/LONG_RUN_STABILITY_PLAN.md`
- `docs/HARDWARE_BENCHMARK_ADAPTATION.md`
- `packages/ontology_forge`
- `packages/rag_engine`
- `packages/guard`
- `packages/model`
- `packages/trainer`

## What Changed

- Added deterministic Alpha pipeline packages.
- Added FastAPI endpoints for Ontology, GraphRAG, Guardrail, telemetry, and Oven dry-run.
- Added unified BakeBoard Alpha UI with training loss visualization.
- Added deployable Next.js fallback API routes.
- Added Neuro-Efficiency package/API/UI for event sparsity, modular routing,
  continual/few-shot/self-supervised learning policy, compression, and estimated
  compute reduction.
- Added Sustained Learning Stability Profile with RAM/VRAM/storage watermarks,
  queue caps, graph hot-window/UI LOD policy, checkpoint cadence, and
  backpressure rules for the user's target desktop hardware.
- Added `GET/POST /api/neuro/stability` to FastAPI and the deployable Next.js
  fallback route.
- Added the BakeBoard `지속 운전 안전장치` process card and learning-volume
  targets for lite/standard/deep/max long-run profiles.
- Added `GET/POST /api/neuro/benchmark` to measure local CPU/RAM/GPU/disk at
  startup and recommend `lite` / `standard` / `deep` / `max`.
- Added the BakeBoard `시스템 벤치마크` card and `벤치마크 재측정` action.
- The actual local machine measured as `Performance desktop` and recommended
  `max`; BakeBoard auto-selected `최대` when connected to local FastAPI.
- Added open-structure RAG generation for questions like `네 구조 설명해봐`.
- Changed signal UI from `신호 경로` to `활성 노드`; orange pulsing now marks
  currently active nodes, not a fixed route.
- Added no-evidence routing so external unknown facts do not leak Homage
  architecture answers.
- Added direct target-node input for learning volume and wired it into
  stability planning plus Build Start.
- Added `∞` learning-volume mode:
  - target nodes: 250,000
  - scheduled chunks: 2,000
  - text budget: continuous
  - representative 3D render window: 600 nodes
  - cumulative learning timer and `학습 중지` stop control
- Updated Build Start fallback to return `alpha-continuous-harvest` and
  `training_gate.continuous: true` for infinite learning.
- Live-synapse growth now supports a rolling window so candidate nodes can keep
  accumulating while the browser renders a bounded representative graph.
- Live-synapse display now reports preserved API anchor nodes, visible new
  `live-synapse-*` nodes, summarized `live-summary-*` history nodes, and the
  latest new node id.
- 3D zoom-out is graph-size responsive instead of capped at a fixed camera
  distance; the 3D host exposes camera/node debug data for browser verification.
- FastAPI system telemetry now includes `source: local-fastapi`, RAM total/used,
  RAM available, disk free, and CPU percent when available.
- Next system telemetry fallback marks itself as `deployment-sandbox` or
  `local-next` so deployed sandbox CPU/RAM values are not confused with the
  user's PC.
- Local BakeBoard can now connect from the browser to the viewer's own
  `http://127.0.0.1:8000` FastAPI backend for local telemetry, benchmark,
  stability, and Build Start APIs.
- Production browser verification showed that HTTPS deployment pages can be
  blocked from calling an HTTP loopback backend before the request reaches
  FastAPI; the UI now explains this and recommends local web or HTTPS local
  companion for real PC measurement.
- FastAPI now serves `POST /api/factory/build/start` with the same Alpha Build
  Start contract as the Next fallback.
- Build Start responses now expose target/sample semantics:
  `target_semantics`, `representative_node_count`, `representative_edge_count`,
  `target_realized`, and `sampling_explanation`.
- Local connector GET requests no longer force CORS preflights with
  `Content-Type: application/json`; transient local API failures now keep the
  connector healthy when `/health` still succeeds.
- The UI now explains that standard `10,000` target runs can visibly stop around
  `210` nodes / `427` relations because the representative render window is
  full; this is not full long-run target realization.
- Real local benchmark hardware is passed into stability recalculation.
- Infinite learning preflight/auto-stop now checks real telemetry for RAM,
  VRAM, and disk reserve pressure.
- Current Alpha learning is not random sentence learning: the system chunks
  accepted/reference text, extracts concept candidates deterministically,
  generates typed relations, and visualizes continual growth until durable graph
  mutation persistence is implemented.
- Improved dense 3D graph spacing with spread layout, collision relaxation,
  label thinning, and camera scaling.
- Added research note with SNN, neuromorphic, EWC, prototype, MAE, compression,
  and Loihi references.
- Added long-run stability note.
- Deployed and browser-tested the production app.

## Commands Run

- `pytest packages/datagate packages/ontology_forge packages/rag_engine packages/guard packages/model packages/trainer packages/neuro_efficiency apps/api -q`
- `PYTHONPATH=... python -m pytest packages/datagate packages/ontology_forge packages/rag_engine packages/guard packages/model packages/trainer packages/neuro_efficiency apps/api -q`
- `python -m compileall ...`
- `npm --workspace apps/web run build`
- `git diff --check`
- `npx vercel --prod --yes`
- `npx vercel alias set web-ffvjjolxy-anthony-kims-projects-bc874109.vercel.app homage-alpha.vercel.app`
- `npx vercel alias set web-7784z7z4w-anthony-kims-projects-bc874109.vercel.app homage-alpha.vercel.app`
- Local hardware verification used FastAPI on `127.0.0.1:8002` and Next
  production server on `127.0.0.1:3025`.

## Test Results

- 60 Python tests passed with explicit package `PYTHONPATH`.
- Python compile passed.
- Frontend build passed.
- Local browser verification passed, including Neuro-Efficiency Rebalance and
  the sustained stability card with `최대` learning volume persisting after
  auto-refresh.
- Local browser verification passed for startup hardware benchmark adaptation:
  `Performance desktop`, `추천 최대`, `로컬 측정`, and Build Start at
  768 chunks / 420k chars.
- Local browser verification passed for structure answer generation and active
  node pulses with no path wording.
- Production API and browser verification passed for `네 구조 설명해봐`:
  native open-structure generation, no direct-evidence fallback copy,
  `external_llm: false`, and orange active-node pulses instead of path traces.
- Local browser verification passed for no-evidence external questions,
  `GraphRAG가 뭐야` without `읽힌 경로`, custom `1,200` target nodes, and dense
  graph rendering up to `358/360` representative nodes by DOM verification.
- Production API verification passed for no-evidence RAG and custom
  `target_nodes: 50000` Build Start scaling; production browser capture shows
  the new target-node input.
- Local API verification passed for infinite Build Start:
  `alpha-continuous-harvest`, 250,000 target nodes, 2,000 chunks, 600 visual
  node budget, and continuous Harvest/Ontology Forge states.
- Local browser verification passed for `∞` selection, continuous build start,
  cumulative elapsed learning time, candidate-node growth, 600-node render cap,
  and `학습 중지`.
- At 42 seconds, the browser showed 702 accumulated candidates while the visible
  graph stayed at `600/600`; after stopping, it preserved 1분 31초 elapsed time
  and 942 accumulated candidates.
- Production deploy succeeded and `https://homage-alpha.vercel.app` now points
  to the infinite learning version.
- Production API/browser verification passed for `∞` continuous learning:
  `alpha-continuous-harvest`, 2,000 chunks, 600 visual nodes, cumulative elapsed
  time, candidate-node growth, and stop control.
- Local actual telemetry verification passed:
  - system telemetry read 32 CPU threads, about 31.1GB RAM, about 165.5GB free
    disk, and `source: local-fastapi`
  - GPU telemetry read RTX 5080, about 15.9GB VRAM, and about 9GB VRAM currently
    used during verification
  - benchmark recommended `max`
  - 250,000-node stability plan used about 186.1GB storage reserve
  - infinite learning preflight was correctly blocked because RAM crossed the
    soft watermark
  - finite max build showed preserved anchors plus new `live-synapse-*` ids
  - responsive zoom-out reached camera distance `187.4` on a 358-node graph
- Production verification passed after redeploy:
  - system telemetry labels deployment values as `deployment-sandbox`
  - browser showed preserved anchors, visible new live nodes, summarized history,
    and Alpha boundary copy
  - zoom-out reached camera distance `134.7` on a 600-node graph
- Local FastAPI companion verification passed:
  - FastAPI factory route returned standard `visual_node_budget: 210`,
    `representative_node_count: 181`, and `target_realized: false`
  - local browser connected to `http://127.0.0.1:8000` from a separate Next
    production server
  - re-verification used fresh FastAPI on `127.0.0.1:8003` and Next production
    server on `127.0.0.1:3032`; FastAPI logs confirmed browser
    `OPTIONS/POST /api/factory/build/start` returned 200
  - standard Build Start showed `10,000` long-run target, `210/210`
    representative sample, `181` API anchors, and explicit copy explaining the
    render cap
  - screenshot: `docs/screenshots/117-local-fastapi-standard-sample-explained.png`
  - screenshot: `docs/screenshots/118-local-fastapi-connected-render-cap-fixed.png`
  - screenshot: `docs/screenshots/119-local-fastapi-target-sample-explanation.png`
  - screenshot: `docs/screenshots/120-production-local-http-boundary-message.png`
- Deployed browser verification passed, including Neuro-Efficiency Rebalance.

## Current Blockers

- None.

## Constraints / Non-goals

- No external paid APIs.
- No web crawling.
- No LLM judging.
- No pretrained weights.
- Homage Oven is a dry-run scaffold only.
- Neuro-Efficiency values are deterministic estimates until real traces and
  hardware profiles are persisted.
- Sustained stability is currently a planning/API/UI layer. The live ontology
  store still needs append-only graph events plus a SQLite WAL hot index before
  unattended multi-day runs.
- Infinite learning mode is currently a local/deployed Alpha runtime loop in the
  browser. It is not yet a durable background crawler and does not persist every
  live graph mutation across refreshes.
- With real local telemetry, infinite learning can refuse to start or stop
  itself before resource pressure kills the machine. In the latest verification,
  current RAM usage and disk reserve were already above safety thresholds for
  the 250,000-node workload.
- Hardware benchmark auto-apply requires local FastAPI. Deployed fallback cannot
  measure the viewer PC and returns `can_read_local_hardware: false`.
- Local UI can use real viewer hardware through the local FastAPI connector.
  Deployed UI remains a deterministic fallback when the browser blocks HTTPS to
  HTTP loopback calls.
- Finite Build Start modes currently fill a representative render sample rather
  than persisting the full long-run `target_nodes` budget. The append-only
  ontology event log and SQLite hot graph index are still required for true
  multi-thousand-node realization.
- No-direct-evidence architecture answers use internal Homage context for
  synthesis, but do not return it as retrieved document evidence.
- Unknown external facts are not guessed without memory evidence or Harvest
  input.

## Next 3 Actions

1. Implement the ontology event log and SQLite WAL hot graph index.
2. Persist live-synapse graph mutations and replay them as real learning events.
3. Add real Harvest source allowlists plus durable document provenance.

## What I Need From You

Review the deployed Alpha and choose whether to prioritize trace logging,
SNN experiments, or quantization calibration next.



