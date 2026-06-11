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
