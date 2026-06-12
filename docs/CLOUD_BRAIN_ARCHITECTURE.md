# Cloud Brain Architecture

## One-Line Definition

Cloud Brain is the shared public ontology layer for Homage1.0: a governed,
continuously updated web knowledge graph that can lend verified graph fragments
to each user's local private brain without turning Homage into an external LLM
wrapper.

## Why This Exists

Homage separates knowledge from generation. The local private brain stores the
user's durable personal graph, while the generation layer remains a native
graph-token / syntax-assembly research engine. Cloud Brain extends this design
with a shared public memory:

- public web facts become candidate nodes and edges
- repeated, source-supported edges gain strength
- weak or stale edges decay
- only small verified graph fragments are pulled into the lab when needed
- local promotion requires evidence, repeated use, and resource safety

The goal is not to guarantee perfect truth. The goal is to make unsupported
claims inspectable, bounded, and rejectable instead of hiding them inside opaque
model weights.

## Three Brain Layers

### 1. Local Private Brain

The local private brain is the user's secure, persistent knowledge graph.

- Storage: `data/memory/homage.db`, SQLite WAL, append-only JSONL events.
- Scope: private documents, accepted local memories, user's repeated concepts.
- Runtime: local FastAPI + Knowledge Bakery worker.
- Rule: never upload private nodes to Cloud Brain unless a future explicit
  sharing workflow is added.

### 2. Cloud Brain

Cloud Brain is the public/shared ontology memory.

- Input: governed web harvest, public documents, search/news/wiki snippets,
  public research references, and community-contributed graph fragments.
- State: public node ids, typed edges, source evidence, confidence, frequency,
  decay state, and freshness windows.
- Output: small signed ontology fragments, not natural-language model answers.
- UI role: deployed Homage shows Cloud Brain as a viewer; local Homage can run
  an actual worker and checkpoint its state.

### 3. Lab Working Memory

The lab working memory is the short-lived context used during a query or build.

- It can bind local nodes, fresh web snippets, and Cloud Brain fragments.
- It should garbage-collect temporary edges after the query unless promotion
  conditions are met.
- It must label where each edge came from: local, web, Cloud Brain, or mixed.

## Query Flow

```text
User question
  -> Local Private Brain retrieval
  -> If confidence is weak, run governed web search
  -> If web search is unavailable, rate-limited, too shallow, or lacks context:
       request Cloud Brain fragments by topic/node ids
  -> Build temporary working graph
  -> Generate with Homage native graph-token/syntax engine
  -> Guardrail checks unsupported claims against evidence/edges
  -> If useful and repeated, promote candidate edges into local memory
```

Cloud Brain does not replace web search. It is a public graph cache that reduces
repeated web crawling and gives the lab a structured fallback when raw search
results are too noisy or unavailable.

## Synaptic Lifecycle

### 1. Virtual Edge

New web or Cloud Brain evidence enters as a virtual edge:

```json
{
  "source": "rtx-5080",
  "relation": "uses_architecture",
  "target": "blackwell",
  "scope": "working",
  "weight": 0.12,
  "evidence_count": 1,
  "last_seen_at": "..."
}
```

### 2. Potentiation

Each repeated verified co-occurrence raises the edge:

```text
weight = min(1.0, weight + alpha * source_quality * user_reuse)
evidence_count += 1
last_seen_at = now
```

Useful signals:

- repeated user questions
- repeated independent sources
- high-source quality
- successful Guardrail support
- appearance in final accepted answers

### 3. Consolidation

When an edge passes the threshold, it moves from working memory to long-term
memory:

```text
if weight >= consolidation_threshold
and evidence_count >= minimum_sources
and guardrail_state == "supported"
and resource_envelope == "safe":
    persist edge as long-term synapse
```

Consolidation writes the edge to the local graph or, for public facts, to a
Cloud Brain candidate queue.

### 4. Decay

Unused edges lose strength:

```text
weight = weight * decay_lambda
```

Decay is slower for:

- local user-approved memories
- high-quality public sources
- frequently used domain anchors

Decay is faster for:

- single-source web snippets
- old news
- low-confidence extraction
- unsupported generated claims

### 5. Pruning

Edges below the pruning threshold are dropped or compacted into summary stats:

```text
if weight < prune_threshold and age > minimum_age:
    delete edge or archive as cold evidence
```

This is how Homage can learn continuously without allowing the graph to grow
without bound.

## Resource Strategy

Cloud Brain must be designed around hot windows, not full graph loads.

- RAM keeps only indexes, active frontier nodes, and short-lived working memory.
- SSD keeps durable event logs and graph tables.
- mmap/lazy loading maps only the selected subgraph for the current query.
- UI renders only active frontier, anchor nodes, and community summaries.
- GPU is reserved for compact native training/generation experiments, not for
  storing the world in parameters.

For the target workstation class:

- CPU: graph traversal, parsing, extraction, decay/pruning jobs.
- RAM: hot graph window and query context bundles.
- SSD: append-only event log, SQLite WAL hot index, compacted snapshots.
- GPU: future independent syntax assembler / native decoder experiments.

## Cloud Brain API Contract

Alpha facade implemented now:

- `GET /api/cloud-brain/status`
  - exposes the Cloud Brain contract over the current local daemon state.
- `POST /api/cloud-brain/query`
  - returns local Cloud Brain candidate fragments from the memory activation
    graph without calling an external LLM.
- `POST /api/cloud-brain/ingest`
  - alpha endpoint is honest dry-run/planned metadata until the shared public
    backend exists.
- `POST /api/cloud-brain/consolidate`
  - maps to the local daemon tick/consolidation path.
- `POST /api/cloud-brain/prune`
  - alpha endpoint returns a pruning plan; mutating decay/prune is still a
    research task.

The existing `/api/learning/daemon/*` routes remain as internal local-worker
controls. `/api/cloud-brain/*` is the public-facing contract. In Alpha it is a
local facade; a later milestone can replace its storage layer with a governed
shared graph protocol.

## Lab Integration

The lab should use Cloud Brain only as a structured fallback:

1. Try local private memory.
2. Try governed web search if freshness is needed.
3. If web search is limited or too noisy, pull Cloud Brain fragments.
4. Keep fragments temporary unless consolidation gates pass.
5. Display source labels so users can tell local memory, fresh web, and Cloud
   Brain apart.

This keeps the lab honest. The deployed UI can show Cloud Brain as a viewer, but
it must not pretend a public worker is running unless it is actually connected.

## Research Boundary

Cloud Brain is a graph-memory architecture, not a proof that the final native
decoder is solved. Homage Alpha still exposes weak generation when the graph is
weak. The right engineering behavior is:

- show weak output when the graph-token predictor is weak
- improve extraction, edge scoring, consolidation, and pruning
- avoid rule-based prose that makes the system look smarter than it is
- never route answer generation to an external LLM while claiming native output
