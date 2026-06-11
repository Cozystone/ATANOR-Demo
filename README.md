# Homage1.0

Homage1.0 is a transparent neuro-symbolic AI factory. This skeleton starts Phase 0 and Phase 1 from the PRD: a FastAPI backend, a Next.js BakeBoard frontend, shared repo documents, and a mock pipeline status API.

## Repository Layout

```text
apps/
  api/    FastAPI backend
  web/    Next.js BakeBoard dashboard
docs/     PRD, architecture notes, ADRs, and shared docs
```

## Start Backend

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r apps/api/requirements.txt
pip install -e "packages/datagate[dev]"
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --app-dir apps/api
```

Backend health:

- http://127.0.0.1:8000/health
- http://127.0.0.1:8000/api/pipeline/status
- http://127.0.0.1:8000/api/datagate/status

## Start Frontend

In a second terminal:

```bash
cd apps/web
npm install
npm run dev
```

Open http://localhost:3000.

The frontend calls its own Next.js proxy route by default: `/api/pipeline/status`.
That proxy forwards to the backend at `http://127.0.0.1:8000`.

Optional environment overrides:

- `API_BASE_URL`: backend URL used by the Next.js proxy
- `NEXT_PUBLIC_API_BASE_URL`: browser-visible API base URL, only needed if you want to bypass the proxy

## Run DataGate

1. Add local `.txt` or `.md` files under `data/raw`.
2. Start the backend and frontend.
3. Open BakeBoard and click **Run** in the DataGate panel.

Outputs are rewritten on each run:

- `data/cleaned/{doc_id}.txt`
- `data/rejected/{doc_id}.txt`
- `data/metadata/documents.jsonl`

DataGate is also available through:

- `POST http://127.0.0.1:8000/api/datagate/run`
- `GET http://127.0.0.1:8000/api/datagate/status`

## Development Notes

- Source of truth PRD: `docs/Homage1.0_PRD.md`
- Project state: `PROJECT_STATE.md`
- Task tracking: `TASK_BOARD.md`
- Cross-agent handoff: `HANDOFF_CODEX.md`, `HANDOFF_CLAUDE.md`, `CONTEXT_CAPSULE.md`
