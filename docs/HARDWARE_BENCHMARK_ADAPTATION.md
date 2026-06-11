# Hardware Benchmark Adaptation

Homage1.0 now runs a short hardware benchmark at the beginning of a BakeBoard
session. The benchmark exists to prevent the ontology builder and training
scaffold from choosing one fixed workload for every machine.

## What It Reads

When the local FastAPI backend is connected, `POST /api/neuro/benchmark` reads:

- CPU model and logical thread count
- Total RAM
- NVIDIA GPU name and VRAM through `nvidia-smi`
- Workspace disk size/free space
- A short CPU loop probe
- A short disk write probe

The probe is intentionally small. It is not a stress test and should complete in
well under a second on the target desktop.

## What It Adjusts

The benchmark returns:

- `recommended_learning_volume`: `lite`, `standard`, `deep`, or `max`
- `recommended_stability_payload`: target nodes, target edges, and duration
- `ontology_tuning`: DataGate batch size, ontology chunk batch size, node/edge
  write batches, hot graph window, and UI render budget
- `training_tuning`: precision preference, microbatch tokens, gradient
  accumulation, RAG concurrency, and checkpoint cadence

BakeBoard applies the recommendation automatically only when
`can_read_local_hardware` is `true`. This prevents the deployed Vercel fallback
from pretending it has measured the viewer's actual PC.

## Target Desktop Result

On the current target machine, the local benchmark verified:

- Profile: `Performance desktop`
- Recommendation: `max`
- Target: 500,000 nodes / 2,400,000 edges / 168h
- CPU threads: 32
- RAM reported by OS: about 31.1GB
- GPU: NVIDIA GeForce RTX 5080
- VRAM reported by driver: about 15.9GB
- Disk probe: around 900MB/s to 1GB/s during local verification

The scorer treats 30GB+ RAM and 15GB+ VRAM as the 32GB/16GB class because
Windows and GPU drivers report usable capacity slightly below the marketing
number.

## Fallback Behavior

In deployed mode, `apps/web/app/api/neuro/benchmark` can only inspect the server
sandbox. It returns:

- `source: server-fallback`
- `can_read_local_hardware: false`
- a conservative recommendation
- a note telling the operator to run the local FastAPI backend for a real PC
  benchmark

## Next Steps

1. Persist benchmark results by `machine_id` and `run_id`.
2. Feed the benchmark payload directly into the Ontology Forge writer once the
   SQLite WAL hot index is implemented.
3. Use benchmark deltas to lower workload automatically when disk free space,
   VRAM pressure, or thermal readings degrade during a long run.
