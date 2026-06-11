# Project State

## Current Status

Homage1.0 Phase 0 repo skeleton and Phase 1 BakeBoard shell are initialized.
Phase 2 (DataGate) is **in progress**: the `packages/datagate` core library is
implemented and fully tested. API and frontend wiring for DataGate are **not**
started yet (intentionally deferred).

## Completed (DataGate core — Milestone 2, partial)

- Created `packages/datagate`, a standalone installable Python package
  (`pyproject.toml`, name `datagate`, deps: `pydantic>=2` only, requires Python
  >=3.11). No FastAPI / web imports — verified.
- Pydantic v2 models (`Document`, `DocumentMetadata`, `FilterResult`,
  `RunReport`) with enforced invariants: rejected ⇒ `rejection_reason` +
  `rejected_by`; accepted ⇒ `quality_score`; failed `FilterResult` ⇒ `reason`.
- Deterministic hashing: `normalize_text` (NFC → strip → collapse whitespace),
  `content_hash` (sha256), `doc_id = hash[:16]`.
- Ordered fail-fast filter chain: `min_length`, `duplicate_hash` (stateful,
  reset per run), `special_char_ratio` (Unicode/Korean aware), `link_density`
  (bare + markdown URLs, coverage-mask union).
- `QualityScorer` — deterministic, documented, monotonic, clamped to [0, 100].
- `PipelineRunner.run()` — sorted discovery, fail-fast filtering, scoring,
  full-batch overwrite of `data/cleaned/`, `data/rejected/`,
  `data/metadata/documents.jsonl`; unreadable files become `read_error`
  rejections; returns a `RunReport`.
- 36 pytest tests covering model validation, every filter, scoring, end-to-end
  runner behavior, and repeated-run determinism. All passing.

## Completed

- Created monorepo layout with `apps/api`, `apps/web`, and `docs`.
- Copied the PRD into `docs/Homage1.0_PRD.md` as the source-of-truth path requested for future work.
- Added FastAPI backend with:
  - `GET /health`
  - `GET /api/pipeline/status`
- Added mock pipeline statuses for Harvest, DataGate, Ontology Forge, Homage Oven, GraphRAG, Guardrail, and GPU Monitor.
- Added Next.js BakeBoard dashboard that renders the pipeline stages as cards.
- Added a Next.js proxy route so the dashboard can call `/api/pipeline/status` during local dev.
- Added operating documents for task tracking, handoff, session logging, and context capsules.
- Added README instructions for running backend and frontend locally.
- Verified backend and frontend run locally.

## Current Apps

- Backend: `apps/api`, FastAPI on `http://127.0.0.1:8000`
- Frontend: `apps/web`, Next.js on `http://localhost:3000`

## Verification

- `python -m compileall apps/api` passed.
- `npm --workspace apps/web run build` passed.
- `GET http://127.0.0.1:8000/api/pipeline/status` returned all seven mock pipeline stages.
- `GET http://127.0.0.1:3000` returned HTTP 200.
- In-app browser verification passed: BakeBoard rendered all seven stage cards via the Next.js proxy route.

## Next Priorities

1. Wire DataGate into `apps/api`: `datagate_service.py` (in-memory RunState +
   thread-safe guard) and `routers/datagate.py` (`POST /run` with 409 guard,
   `GET /status`); mount under `/api/datagate`. (Not started — deferred.)
2. Make pipeline status stage 1 reflect real DataGate state.
3. Add the BakeBoard DataGate panel + Next.js proxy routes with 2s polling.
4. Add automated API tests for `GET /api/pipeline/status`.

## Known Constraints

- Pipeline data is mock-only outside DataGate; `apps/api` and BakeBoard do not
  yet call DataGate (API/frontend wiring deferred per this milestone's scope).
- No database, queue, graph store, vector store, or training loop is wired yet.
- DataGate is full-batch overwrite only — no incremental runs or run history.
- DataGate input is local `.txt` / `.md` under `data/raw` only (no crawling,
  no PDF/HTML, no LLM judging).
- `npm install` reported dependency audit findings: 2 moderate and 2 critical.
  No automatic audit fix was applied because it may introduce breaking
  dependency changes. **Tracked debt — revisit at the next Next.js minor bump.**
  (Run `npm audit` in repo root to re-list the four advisory IDs.)
