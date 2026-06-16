# ATANOR

**A graph-native, local-first AI architecture for transparent memory, verifiable reasoning, and installable knowledge.**

ATANOR is an experimental AI system that treats knowledge as a living graph instead of hiding it inside opaque model weights. It separates private local memory from public cloud fragments, renders the active reasoning surface, and lets graph cartridges attach read-only into working memory.

![ATANOR graph-native workspace](docs/media/atanor-graph-workspace.png)

## Why ATANOR Exists

Most AI products ask users to trust a remote black box. ATANOR explores a different direction:

- **Local Brain:** private memory stays on the user's machine.
- **Cloud Brain:** public knowledge grows as content-addressed graph fragments.
- **Graph Hub:** useful graph packs can be installed, audited, and attached read-only.
- **Surface Brain:** answer quality and repair rules become reviewable artifacts.
- **CORTEX-G2 / Q-Cortex:** planning, salience, and optimization are explicit subsystems.
- **Proof-first development:** core claims are backed by tests and proof artifacts.

The goal is not to pretend that a small alpha system is a frontier LLM. The goal is to build the missing architecture around AI: memory that can be inspected, provenance that can be audited, and knowledge packages that can move without surrendering private data.

## What Is In This Repository

| Layer | Purpose | Representative paths |
| --- | --- | --- |
| Web lab | Interactive ATANOR workspace, Graph Hub, Atlas, Cloud Brain panels | `apps/web` |
| API runtime | FastAPI routers for graph, memory, cloud, repair, quality, Graph Hub | `apps/api` |
| Local Brain | Local graph memory, retrieval, synthesis, alpha services | `packages/rag_engine`, `packages/knowledge_bakery` |
| Cloud Brain | Semantic growth, cloud-attached nodes, contributor fragments | `packages/cloud_brain` |
| Brain Graph | Tab-aware graph rendering and materialization | `packages/brain_graph` |
| Base Brain | Seed/base knowledge packs and zero-user answer proof | `packages/base_brain` |
| Graph Hub | Graph cartridge catalog, entitlement, install, attach, sandbox, audit | `packages/graph_hub` |
| Surface Brain | Production rule review, repair queue, discourse/style graph | `packages/surface_brain` |
| Q-Cortex | Planning, evidence, salience, and QUBO-style optimization | `packages/q_cortex` |
| CORTEX-G2 | Activation, dream loop, predictive engine, verbalization routing | `packages/cortex_g2` |
| Proofs | Public proof snapshots and sample catalog artifacts | `data/*/proofs`, `data/*/catalog` |
| Infra | Cloudflare and AWS broker prototypes | `infra` |

## Product Screenshots

### Graph-Native Workspace

The main workspace renders the active system as a navigable graph surface, with Local Brain, Cloud Brain, Atlas, Graph Hub, and control panels in one interface.

![ATANOR workspace](docs/media/atanor-graph-workspace.png)

### Graph Hub

Graph Hub is not a prompt marketplace. It is a cartridge system for graph data: catalog, install, entitlement state, read-only attachment, export, and audit.

![ATANOR Graph Hub](docs/media/atanor-graph-hub.png)

### Cloud Brain / Atlas

Cloud Brain and Atlas visualize public graph-fragment state without claiming private local memory as shared cloud intelligence.

![ATANOR Cloud Brain Atlas](docs/media/atanor-cloud-atlas.png)

## Architecture In One Picture

```text
Local documents / user input / public fragments
        |
        v
Harvest + DataGate
  clean, filter, deduplicate, gate
        |
        v
Ontology + Base Brain
  concepts, aliases, seed packs, surface packs
        |
        v
Local Brain                     Cloud Brain
private graph memory            public graph fragments
SQLite / local traces           semantic proof store
        |                       |
        +----------+------------+
                   v
Working Memory Overlay
temporary attachment, provenance, no silent local writes
                   |
                   v
Brain Graph Renderer + Graph Hub
tab-aware views, graph cartridges, audit trail
                   |
                   v
Surface Brain + Q-Cortex + CORTEX-G2
answer quality, repair review, salience, planning
```

Read the fuller technical overview in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Verified Alpha State

Current publication validation:

- `python -m pytest apps/api/tests packages/rag_engine/tests packages/cloud_brain/tests packages/seed_research/tests packages/cortex_g2/tests packages/q_cortex/tests packages/surface_brain/tests packages/answer_quality/tests packages/base_brain/tests packages/brain_graph/tests packages/graph_hub/tests -q`
- `npm --workspace apps/web run build`
- Browser smoke checks against the local ATANOR web workspace
- Secret/path scan over staged publication files

Key proof artifacts are committed under `data/*/proofs` and the sample Graph Hub catalog is committed under `data/graph_hub/catalog`.

## Quickstart

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r apps/api/requirements.txt
npm install
```

Start the API:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8500 --app-dir apps/api
```

Start the web workspace:

```powershell
npm --workspace apps/web run dev -- --hostname 127.0.0.1 --port 3022
```

Open:

```text
http://127.0.0.1:3022/?lang=ko
```

## Public Positioning

ATANOR is for people who believe AI needs more than bigger prompts:

- transparent memory instead of hidden state
- local ownership instead of default data surrender
- graph-native reasoning instead of one-shot text generation
- installable knowledge instead of prompt packs
- proof artifacts instead of hand-wavy architecture claims

See [docs/LAUNCH_KIT.md](docs/LAUNCH_KIT.md) for public launch copy, short posts, and messaging angles.

## Long-Term Vision

ATANOR is a bet that personal AI will need a different substrate from today's chat-first products.

The long-term vision is a workstation-native intelligence system where:

- private memory can be owned, inspected, pruned, exported, and repaired by the user
- public knowledge can circulate as graph fragments rather than opaque model checkpoints
- useful expertise can ship as graph cartridges with auditable provenance
- reasoning paths can be displayed as active graph state, not only as polished text
- answer improvement can happen through reviewable repair loops instead of invisible prompt edits
- local and cloud intelligence can cooperate without erasing the privacy boundary

In that future, an AI system is not just a model endpoint. It is a living memory architecture: local where it must be private, networked where it can be public, and transparent enough to be corrected.

Read the public vision in [docs/VISION.md](docs/VISION.md).

## Honest Boundaries

ATANOR is an alpha research platform. It does **not** currently claim:

- GPT-level answer quality
- a global web-scale Cloud Brain
- production marketplace billing
- production DRM or legal commercial licensing
- perfect semantic parsing
- private data sharing by default
- external LLM/sLLM proof-path generation

Those boundaries matter. The architecture is interesting precisely because it keeps private and public knowledge separate, observable, and testable.

## License

See [LICENSE](LICENSE).
