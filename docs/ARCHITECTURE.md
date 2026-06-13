# ATANOR Architecture

## Phase 1 Skeleton

```text
apps/web BakeBoard dashboard
        |
        | HTTP GET /api/pipeline/status
        v
apps/web Next.js proxy route
        |
        | HTTP GET http://127.0.0.1:8000/api/pipeline/status
        v
apps/api FastAPI mock pipeline API
```

## Backend

- Framework: FastAPI
- Current responsibility: expose health and mock pipeline status endpoints.
- Future responsibilities: DataGate, Ontology Forge, ATANOR Oven, GraphRAG, Guardrail, GPU monitoring, and event streaming.

## Frontend

- Framework: Next.js and React
- Current responsibility: render the BakeBoard factory overview as pipeline stage cards.
- Current proxy route: `GET /api/pipeline/status`, forwarding to FastAPI.
- Future responsibilities: live event updates, charts, graph views, trace panels, guardrail inspection, and final answer inspection.

## API Contract

`GET /api/pipeline/status` returns:

```json
{
  "generated_at": "2026-06-11T00:00:00Z",
  "system_state": "mock",
  "stages": [
    {
      "id": "harvest",
      "name": "Harvest",
      "state": "running",
      "progress": 42,
      "summary": "Collecting source documents and recording provenance.",
      "metric_label": "documents",
      "metric_value": "128 queued"
    }
  ]
}
```
