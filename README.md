# Homage1.0 Alpha

Homage1.0 is a transparent neuro-symbolic AI factory MVP. Alpha includes a
FastAPI backend, a Next.js BakeBoard dashboard, deterministic local pipeline
packages, and a deployed interactive BakeBoard demo.

Production demo:

- https://homage-alpha.vercel.app

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
  neuro_efficiency/
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
pip install -e "packages/neuro_efficiency[dev]"
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

## Use Local FastAPI For Real PC Measurement

The deployed Vercel app cannot measure the viewer's PC by itself. The reliable
way for any user to run real CPU/RAM/GPU/disk telemetry and the local FastAPI
factory route on their own machine is:

1. Start FastAPI on that machine with the backend command above.
2. Start the frontend locally with the frontend command above.
3. Open http://localhost:3000.
4. In the local FastAPI control, enter `http://127.0.0.1:8000`.
5. Click connect.

After connection, BakeBoard calls the user's local FastAPI directly for
benchmark, telemetry, stability, and Build Start APIs. The Vercel fallback
remains available when no local backend is connected.

The production URL still exposes the same connector, but modern browsers may
block `https://homage-alpha.vercel.app` from calling an `http://localhost` API.
Use the local frontend for real hardware measurement unless you have an HTTPS
local companion configured.

## Alpha Flow

1. Click `Build 시작` in BakeBoard to start the Alpha factory flow.
2. Harvest reference web sources into evidence snippets.
3. Grow a typed ontology/RAG memory graph with deduped concepts and relations.
4. Watch the 3D GraphRAG traversal view expand, zoom, pan, and rotate.
5. When the graph passes the Alpha gate, prepare the Homage Oven dry-run.
6. Query GraphRAG from the RAG chat workbench.
7. Check a draft in Guardrail.
8. Inspect GPU telemetry or fallback.
9. Inspect the Neuro-Efficiency Layer for event sparsity, active specialists,
   continual/few-shot/self-supervised settings, and compression levers.

For local file ingestion, put `.txt` or `.md` files in `data/raw`, then run
DataGate and Ontology Forge from BakeBoard.

Outputs:

- `data/cleaned/{doc_id}.txt`
- `data/rejected/{doc_id}.txt`
- `data/metadata/documents.jsonl`
- `data/ontology/nodes.json`
- `data/ontology/edges.json`
- `data/ontology/ontology_report.json`
- `checkpoints/homage-core-30m-dev/manifest.json`

GraphRAG responses include synthesized `answer` text, `citations`,
`retrieval_trace`, graph paths, and per-evidence retrieval signals in addition
to matched nodes and evidence documents.

## Main APIs

- `GET /api/pipeline/status`
- `POST /api/factory/build/start`
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
- `GET /api/neuro/plan`
- `POST /api/neuro/plan`

## Verify

```bash
.venv\Scripts\python.exe -m pytest packages\datagate packages\ontology_forge packages\rag_engine packages\guard packages\model packages\trainer packages\neuro_efficiency apps\api -q
.venv\Scripts\python.exe -m compileall apps\api packages\datagate\datagate packages\ontology_forge\ontology_forge packages\rag_engine\rag_engine packages\guard\guard packages\model\model packages\trainer\trainer packages\neuro_efficiency\neuro_efficiency
npm --workspace apps/web run build
```

## Notes

- No external paid APIs.
- No web crawling.
- `Build 시작` fetches a small allowlisted reference set and stores source
  signals for visualization; it is not an open-ended crawler.
- `target_nodes` is a long-run storage/training budget. `graph_3d` is a bounded
  representative browser sample. Standard runs now use a 480-node render window,
  and max/infinite runs can target 500,000 nodes while rendering a 2,000-node
  rolling frontier plus summary nodes.
- No LLM judging.
- No pretrained model weights.
- Homage Oven is a safe dry-run scaffold, not real long training.
- Neuro-Efficiency uses deterministic estimates until real event traces and
  hardware profiles are added.
- `docs/RAG_REFERENCE.md` records the Microsoft GraphRAG, Haystack, and
  MiroFish references used for the Alpha RAG/UI structure.
- `docs/BUILD_FLOW_3D_RAG.md` records the Build Start, live harvest, typed
  ontology growth, 3D GraphRAG traversal, and training-gate design.
- `docs/PRD_ENGINE_AUDIT.md` records what is implemented versus still missing
  against the original PRD.
- The BakeBoard UI now follows a MiroFish-inspired console structure: left
  ontology memory graph, right learning/RAG workbench, and bottom system log.
- The ontology memory graph supports node search, zoom, pan, drag, reset, and
  graph/split/workbench layout modes.
- The 3D GraphRAG view uses Three.js and supports drag rotation, wheel zoom,
  node selection, traversal highlighting, and staged graph growth.
