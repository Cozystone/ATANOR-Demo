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
cd apps/api
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Backend health:

- http://127.0.0.1:8000/health
- http://127.0.0.1:8000/api/pipeline/status

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

## Development Notes

- Source of truth PRD: `docs/Homage1.0_PRD.md`
- Project state: `PROJECT_STATE.md`
- Task tracking: `TASK_BOARD.md`
- Cross-agent handoff: `HANDOFF_CODEX.md`, `HANDOFF_CLAUDE.md`, `CONTEXT_CAPSULE.md`
