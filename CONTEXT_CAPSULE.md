# Context Capsule

## Current Objective

Homage1.0 Alpha end-to-end MVP is implemented, verified, and deployed with a
research-backed Neuro-Efficiency Layer.

## Current Branch

`feature/datagate-v0`

## Last Commit

Latest local commit before this update: Build Homage Alpha MVP

## Deployment

- https://web-2ro6t5sdi-anthony-kims-projects-bc874109.vercel.app

## Relevant Files

- `apps/api/app/main.py`
- `apps/api/app/services/alpha_services.py`
- `apps/web/app/page.tsx`
- `apps/web/app/api/_alphaDemo.ts`
- `apps/api/app/routers/neuro.py`
- `apps/web/app/api/neuro/plan/route.ts`
- `packages/neuro_efficiency`
- `docs/RESEARCH_NEURO_EFFICIENCY.md`
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
- Added research note with SNN, neuromorphic, EWC, prototype, MAE, compression,
  and Loihi references.
- Deployed and browser-tested the production app.

## Commands Run

- `pytest packages/datagate packages/ontology_forge packages/rag_engine packages/guard packages/model packages/trainer packages/neuro_efficiency apps/api -q`
- `python -m compileall ...`
- `npm --workspace apps/web run build`
- `npx vercel deploy --prod --yes --cwd apps/web`

## Test Results

- 49 Python tests passed.
- Python compile passed.
- Frontend build passed.
- Local browser verification passed, including Neuro-Efficiency Rebalance.
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

## Next 3 Actions

1. Commit Neuro-Efficiency changes.
2. Log real event density from DataGate/GraphRAG traces.
3. Run a small SpikingJelly SNN experiment against Homage event traces.

## What I Need From You

Review the deployed Alpha and choose whether to prioritize trace logging,
SNN experiments, or quantization calibration next.



