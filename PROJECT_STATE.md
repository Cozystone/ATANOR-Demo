# Project State

## Current Status

Homage1.0 Alpha is implemented and deployed as an interactive MVP.

Deployment:

- https://web-2sdqapqzo-anthony-kims-projects-bc874109.vercel.app

## Completed Alpha Scope

- DataGate API and BakeBoard integration.
- Ontology Forge deterministic concept/edge extraction.
- GraphRAG deterministic keyword + graph retrieval.
- Guardrail deterministic claim support and overclaim detection.
- GPU/system telemetry with graceful fallback.
- Homage-Core-30M model scaffold and safe training dry-run trace.
- Unified BakeBoard with seven pipeline cards and control panels.
- Next.js API fallback layer so deployed BakeBoard works without local FastAPI.

## Verification

- Python editable package install passed for all Alpha packages.
- `pytest packages/datagate packages/ontology_forge packages/rag_engine packages/guard packages/model packages/trainer apps/api -q` passed: 46 tests.
- Python compile check passed for backend and packages.
- `npm --workspace apps/web run build` passed.
- Local API smoke passed:
  - DataGate completed on sample raw docs.
  - Ontology Forge created 11 nodes and 4 edges.
  - GraphRAG returned evidence with confidence.
  - Guardrail returned claim support and guard score.
  - GPU telemetry returned real data or fallback.
  - Homage Oven dry-run returned loss trace and checkpoint manifest.
  - `/api/pipeline/status` returned 7 stages.
- Local browser verification passed for BakeBoard and training loss chart.
- Vercel production deploy succeeded.
- Deployed browser verification passed for BakeBoard, GraphRAG query, Guardrail check, and training visualization.

## Known Limitations

- Alpha uses deterministic rules; no LLM or pretrained model is used.
- Deployed Vercel app uses deterministic demo fallback API routes.
- Local FastAPI run state is in-memory and single-process.
- DataGate is full-batch overwrite only.
- Ontology extraction is regex/rule-based and intentionally simple.
- Homage Oven dry-run is a scaffold, not production training.
- npm audit still reports dependency advisories; no force fix applied.

## Next Recommended Milestone

1. Persist Alpha run history with SQLite.
2. Add document-level metadata browsing.
3. Improve ontology extraction precision and graph visualization.
4. Add a real tokenizer trainer behind an explicit local-only command.
