# Homage1.0 Alpha

Homage1.0 is a transparent neuro-symbolic AI factory MVP. Alpha includes a
FastAPI backend, a Next.js BakeBoard dashboard, deterministic local pipeline
packages, and a deployed interactive BakeBoard demo.

Production demo:

- https://web-2sdqapqzo-anthony-kims-projects-bc874109.vercel.app

## Repository Layout

```text
apps/
  api/    FastAPI backend and Alpha routers
  web/    Next.js BakeBoard dashboard and deployable API fallbacks
packages/
  datagate/
  ontology_forge/
  rag_engine/
  guard/
  model/
  trainer/
data/
  raw/             local input documents
  train_sample/    safe dry-run training sample
docs/
```

## Start Backend

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r apps/api/requirements.txt
pip install -e "packages/datagate[dev]"
pip install -e "packages/ontology_forge[dev]"
pip install -e "packages/rag_engine[dev]"
pip install -e "packages/guard[dev]"
pip install -e "packages/model[dev]"
pip install -e "packages/trainer[dev]"
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --app-dir apps/api
```

## Start Frontend

In another terminal:

```bash
cd apps/web
npm install
npm run dev
```

Open http://localhost:3000.

The frontend uses same-origin Next.js API routes. Locally those routes proxy to
FastAPI at `API_BASE_URL` or `http://127.0.0.1:8000`; on Vercel they use a
deterministic Alpha demo fallback so the deployed app is directly testable.

## Alpha Flow

1. Put `.txt` or `.md` files in `data/raw`.
2. Run DataGate from BakeBoard.
3. Run Ontology Forge.
4. Query GraphRAG.
5. Check a draft in Guardrail.
6. Inspect GPU telemetry or fallback.
7. Run the Homage Oven dry-run scaffold.

Outputs:

- `data/cleaned/{doc_id}.txt`
- `data/rejected/{doc_id}.txt`
- `data/metadata/documents.jsonl`
- `data/ontology/nodes.json`
- `data/ontology/edges.json`
- `data/ontology/ontology_report.json`
- `checkpoints/homage-core-30m-dev/manifest.json`

## Main APIs

- `GET /api/pipeline/status`
- `POST /api/datagate/run`
- `GET /api/datagate/status`
- `POST /api/ontology/run`
- `GET /api/ontology/status`
- `GET /api/ontology/graph`
- `POST /api/graphrag/query`
- `GET /api/graphrag/status`
- `POST /api/guard/check`
- `GET /api/guard/status`
- `GET /api/telemetry/gpu`
- `GET /api/telemetry/system`
- `POST /api/oven/dry-run`
- `GET /api/oven/status`

## Verify

```bash
.venv\Scripts\python.exe -m pytest packages\datagate packages\ontology_forge packages\rag_engine packages\guard packages\model packages\trainer apps\api -q
.venv\Scripts\python.exe -m compileall apps\api packages\datagate\datagate packages\ontology_forge\ontology_forge packages\rag_engine\rag_engine packages\guard\guard packages\model\model packages\trainer\trainer
npm --workspace apps/web run build
```

## Notes

- No external paid APIs.
- No web crawling.
- No LLM judging.
- No pretrained model weights.
- Homage Oven is a safe dry-run scaffold, not real long training.
