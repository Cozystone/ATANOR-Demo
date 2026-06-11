# Handoff: Codex

## Change Report

### Implemented

- Added Alpha packages:
  - `packages/ontology_forge`
  - `packages/rag_engine`
  - `packages/guard`
  - `packages/model`
  - `packages/trainer`
- Added FastAPI routers:
  - `/api/ontology/*`
  - `/api/graphrag/*`
  - `/api/guard/*`
  - `/api/telemetry/*`
  - `/api/oven/*`
- Updated `/api/pipeline/status` to reflect real Alpha stage states.
- Rebuilt BakeBoard as a unified Alpha dashboard.
- Added training loss visualization for Homage Oven dry-run.
- Added Next.js API fallback routes so the Vercel deployment is interactive.
- Added sample local raw docs and training sample text.
- Added Vercel config for `apps/web`.

### Deployment

- Production URL: https://web-2sdqapqzo-anthony-kims-projects-bc874109.vercel.app
- Vercel deployment id: `dpl_EtPEikV8mzw1kyA55uhdj1R7YEUZ`
- Target: production
- Status: READY

### Commands Run

- `pip install -e "packages/datagate[dev]" -e "packages/ontology_forge[dev]" -e "packages/rag_engine[dev]" -e "packages/guard[dev]" -e "packages/model[dev]" -e "packages/trainer[dev]"`
- `python -m pytest packages/datagate packages/ontology_forge packages/rag_engine packages/guard packages/model packages/trainer apps/api -q`
- `python -m compileall apps/api packages/datagate/datagate packages/ontology_forge/ontology_forge packages/rag_engine/rag_engine packages/guard/guard packages/model/model packages/trainer/trainer`
- `npm --workspace apps/web run build`
- `npx vercel deploy --prod --yes --cwd apps/web`

### Test Results

- Python tests: 46 passed.
- Python compile: passed.
- Frontend build: passed.
- Local runtime smoke: passed.
- Local browser verification: passed.
- Deployed browser verification: passed.

### Remaining Review Questions

- Whether to persist pipeline state with SQLite.
- Whether Vercel demo fallback should remain separate from local FastAPI state.
- How much document-level browsing belongs in Alpha versus Beta.
- Whether to replace the dry-run scaffold with a real local tokenizer/training loop next.
