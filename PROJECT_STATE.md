# Project State

## Current Status

Homage1.0 Phase 0/1 skeleton is complete. Phase 2 DataGate is wired end-to-end
for MVP local use: the standalone `packages/datagate` core is implemented and
tested, FastAPI exposes run/status endpoints, and BakeBoard can start a run and
display summary status.

## Completed: DataGate Core

- Created `packages/datagate`, a standalone installable Python package.
- Kept DataGate FastAPI-free and deterministic.
- Implemented Pydantic models, hashing, IO, fail-fast filters, scoring, and
  `PipelineRunner`.
- Runner writes full-batch outputs:
  - `data/cleaned/{doc_id}.txt`
  - `data/rejected/{doc_id}.txt`
  - `data/metadata/documents.jsonl`
- Core suite covers model validation, filters, scoring, runner behavior, and
  repeated-run determinism.

## Completed: DataGate API/UI Wiring

- Added `apps/api/app/services/datagate_service.py` with in-memory run state,
  a thread-safe running guard, default `data/raw` creation, and thin
  `PipelineRunner` execution.
- Added `apps/api/app/routers/datagate.py`:
  - `POST /api/datagate/run`
  - `GET /api/datagate/status`
- Updated `GET /api/pipeline/status` so DataGate reflects real run state while
  Harvest, Ontology Forge, Homage Oven, GraphRAG, Guardrail, and GPU Monitor
  remain mocked.
- Added Next.js proxy routes:
  - `apps/web/app/api/datagate/run/route.ts`
  - `apps/web/app/api/datagate/status/route.ts`
- Added a BakeBoard DataGate panel with Run button, 2s polling while running,
  state badge, run id, totals, accept rate, rejection breakdown, timestamp, and
  error display.
- Added API tests for idle status, completed fixture run, 409 running guard, and
  the seven-stage pipeline status contract.

## Current Apps

- Backend: `apps/api`, FastAPI on `http://127.0.0.1:8000`
- Frontend: `apps/web`, Next.js on `http://localhost:3000`

## Verification

- `.venv\Scripts\pip.exe install -r apps\api\requirements.txt -e "packages/datagate[dev]"` passed.
- `.venv\Scripts\python.exe -m compileall apps\api packages\datagate\datagate` passed.
- `.venv\Scripts\python.exe -m pytest packages\datagate apps\api -q` passed: 40 tests.
- `npm --workspace apps/web run build` passed.
- Local smoke on alternate ports passed:
  - backend `http://127.0.0.1:8001`
  - frontend `http://127.0.0.1:3001`
  - `POST /api/datagate/run` returned `202`
  - `GET /api/datagate/status` returned `completed`
  - `GET /api/pipeline/status` returned 7 stages
  - Next proxy `/api/datagate/status` returned `completed`
  - BakeBoard browser verification found the DataGate panel and Run button

## Next Priorities

1. Review whether API-generated run ids and core-generated report run ids
   should be unified in a future DataGate core extension.
2. Add document-level metadata browsing after MVP, if desired.
3. Add persistent run history or a SQLite/file run registry after single-process
   local dev is no longer enough.

## Known Constraints

- Pipeline data is mock-only outside DataGate.
- No database, queue, graph store, vector store, or training loop is wired yet.
- DataGate run state is in-memory and single-process only.
- DataGate is full-batch overwrite only; no incremental runs or run history.
- DataGate input is local `.txt` / `.md` under `data/raw` only.
- No crawling, PDF/HTML parsing, LLM judging, or document-level browsing UI.
- `npm install` reported dependency audit findings: 2 moderate and 2 critical.
  No automatic audit fix was applied because it may introduce breaking
  dependency changes. Tracked debt: revisit at the next Next.js minor bump.
