# Context Capsule

## Current Objective

Homage1.0 Alpha end-to-end MVP is implemented, verified, and deployed with a
research-backed Neuro-Efficiency Layer and a sustained-learning stability
profile.

## Current Branch

`feature/datagate-v0`

## Last Commit

Latest local commit before this update: Add native Homage utterance engine

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
- `packages/neuro_efficiency`
- `docs/RESEARCH_NEURO_EFFICIENCY.md`
- `docs/LONG_RUN_STABILITY_PLAN.md`
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
- Added research note with SNN, neuromorphic, EWC, prototype, MAE, compression,
  and Loihi references.
- Added long-run stability note.
- Deployed and browser-tested the production app.

## Commands Run

- `pytest packages/datagate packages/ontology_forge packages/rag_engine packages/guard packages/model packages/trainer packages/neuro_efficiency apps/api -q`
- `PYTHONPATH=... python -m pytest packages/datagate packages/ontology_forge packages/rag_engine packages/guard packages/model packages/trainer packages/neuro_efficiency apps/api -q`
- `python -m compileall ...`
- `npm --workspace apps/web run build`
- `npx vercel deploy --prod --yes --cwd apps/web`

## Test Results

- 55 Python tests passed with explicit package `PYTHONPATH`.
- Python compile passed.
- Frontend build passed.
- Local browser verification passed, including Neuro-Efficiency Rebalance and
  the sustained stability card with `최대` learning volume persisting after
  auto-refresh.
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

## Next 3 Actions

1. Commit sustained-learning stability changes.
2. Implement the ontology event log and SQLite WAL hot graph index.
3. Log real event density from DataGate/GraphRAG traces.

## What I Need From You

Review the deployed Alpha and choose whether to prioritize trace logging,
SNN experiments, or quantization calibration next.



