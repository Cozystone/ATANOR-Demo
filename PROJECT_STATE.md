# Project State

## Current Status

Homage1.0 Alpha is implemented and deployed as an interactive MVP with a
research-backed Neuro-Efficiency Layer.

Deployment:

- https://web-2ro6t5sdi-anthony-kims-projects-bc874109.vercel.app

## Completed Alpha Scope

- DataGate API and BakeBoard integration.
- Ontology Forge deterministic concept/edge extraction.
- GraphRAG deterministic keyword + graph retrieval.
- Guardrail deterministic claim support and overclaim detection.
- GPU/system telemetry with graceful fallback.
- Homage-Core-30M model scaffold and safe training dry-run trace.
- Neuro-Efficiency Layer for event sparsity, modular routing, continual
  learning policy, few-shot prototypes, self-supervised masking, compression,
  and estimated compute reduction.
- Unified BakeBoard with seven pipeline cards and control panels.
- Next.js API fallback layer so deployed BakeBoard works without local FastAPI.
- Research note: `docs/RESEARCH_NEURO_EFFICIENCY.md`.

## Verification

- Python editable package install passed for all Alpha packages including
  `packages/neuro_efficiency`.
- `pytest packages/datagate packages/ontology_forge packages/rag_engine packages/guard packages/model packages/trainer packages/neuro_efficiency apps/api -q` passed: 49 tests.
- Python compile check passed for backend and packages.
- `npm --workspace apps/web run build` passed.
- Local API smoke passed:
  - DataGate completed on sample raw docs.
  - Ontology Forge created 11 nodes and 4 edges.
  - GraphRAG returned evidence with confidence.
  - Guardrail returned claim support and guard score.
  - GPU telemetry returned real data or fallback.
  - Homage Oven dry-run returned loss trace and checkpoint manifest.
  - `/api/neuro/plan` returned the Homage Neuro-Efficiency Layer plan.
  - `/api/pipeline/status` returned 7 stages.
- Local browser verification passed for BakeBoard, training loss chart, and
  Neuro-Efficiency Rebalance action.
- Vercel production deploy succeeded.
- Deployed browser verification passed for BakeBoard, Neuro-Efficiency panel,
  Rebalance action, and `/api/neuro/plan`.

## Known Limitations

- Alpha uses deterministic rules; no LLM or pretrained model is used.
- Deployed Vercel app uses deterministic demo fallback API routes.
- Local FastAPI run state is in-memory and single-process.
- DataGate is full-batch overwrite only.
- Ontology extraction is regex/rule-based and intentionally simple.
- Homage Oven dry-run is a scaffold, not production training.
- Neuro-Efficiency values are deterministic estimates until real event traces,
  model update logs, and hardware profiles are persisted.
- npm audit still reports dependency advisories; no force fix applied.

## Next Recommended Milestone

1. Persist Alpha run history with SQLite.
2. Log real event density from DataGate and GraphRAG traces.
3. Run a small SpikingJelly SNN experiment against Homage event traces.
4. Calibrate 8-bit quantization for Guardrail and GraphRAG outputs.
5. Add document-level metadata browsing.
