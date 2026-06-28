# ATANOR Cloud Brain — VPS deployment (runs without your PC)

This runs the **real Python engine** (continuous public-web learning + relation
discovery + the graph/metrics API) on an always-on server, so the shared cloud
brain keeps learning and is viewable by everyone even when your PC is off.

## Architecture (what runs where)

```
                 ┌─────────────────── VPS (always on) ──────────────────┐
   public web →  │  ATANOR Cloud Brain (FastAPI, Docker)                │
   (Wikipedia)   │   • LEARN  : continuous loop ingests + verifies      │
                 │   • DISCOVER: random concept-pair relation checks    │
                 │   • STORE  : candidate graph on a Docker volume      │
                 │   • SERVE  : /api/cloud-brain/... graph + metrics     │
                 └───────────────▲──────────────────────────────────────┘
                                 │ HTTPS
        every user's frontend ───┘  (all see the SAME growing brain)
```

The graph (concepts / relations / constructions) accumulates on the `atanor-data`
Docker volume, so it survives restarts and redeploys — the brain only grows.

## Deploy (5 steps)

1. **Get a small VPS** (1–2 GB RAM is plenty: Hetzner, DigitalOcean, Vultr, Fly.io
   machine, etc.) and install Docker + the compose plugin.
2. **Copy this repo** to the VPS (or at minimum `apps/api/`, `packages/`, `deploy/`).
3. **Start it:**
   ```sh
   docker compose -f deploy/docker-compose.yml up -d --build
   ```
   The brain begins learning immediately. Check it:
   ```sh
   curl http://localhost:8500/api/cloud-brain/learning/continuous/metrics
   ```
4. **Put HTTPS in front** (the frontend needs an HTTPS endpoint). Easiest: point a
   domain's A record at the VPS, then enable the `caddy` service in
   `docker-compose.yml` (uncomment it + set `DOMAIN` in `Caddyfile`) and re-run
   `up -d`. Caddy fetches a real certificate automatically. Now the brain is at
   `https://cloud.yourdomain.com`.
5. **Point the frontend at it.** In the web app's environment set:
   ```
   API_BASE_URL=https://cloud.yourdomain.com
   ```
   (Vercel: Project → Settings → Environment Variables, then redeploy. Locally:
   `apps/web/.env.local`.) Every viewer now sees the same shared, growing brain.

## Optional — seed with what it has already learned

The container starts learning from scratch by default. To carry over the graph
your local instance already built, copy the candidate store into the volume
before/while the container runs, e.g.:

```sh
# from the local machine: tar the existing candidate store
tar czf store.tgz -C "<local>/data/cloud_brain" candidate_runs
# on the VPS: extract into the named volume
docker run --rm -v atanor-data:/app/data -v "$PWD":/in alpine \
  sh -c "mkdir -p /app/data/cloud_brain && tar xzf /in/store.tgz -C /app/data/cloud_brain"
docker compose -f deploy/docker-compose.yml restart atanor-cloud
```

## Notes
- Only **public** (Wikipedia-derived) knowledge lives in the cloud brain — no
  private/local data is sent here, by design.
- Federating many instances through a central broker is supported later via the
  `ATANOR_CLOUD_MODE=remote` env (see `.env.example`); not required for a single
  shared instance.
