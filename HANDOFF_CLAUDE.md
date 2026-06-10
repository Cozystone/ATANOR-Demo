# Handoff: Claude

## Review Focus

Please review whether this skeleton matches the intended Phase 0 and Phase 1 boundaries from the PRD.

## Current Scope

- Repo operating system and shared docs.
- BakeBoard shell with mock stage status.
- FastAPI endpoint for pipeline status.
- Next.js dashboard cards.

## Non-goals

- No DataGate implementation yet.
- No ontology extraction yet.
- No model training yet.
- No GraphRAG retrieval beyond mock status.

## Questions

1. Should Phase 1 add websocket updates before DataGate MVP starts?
2. Should pipeline stage naming use `Homage Guard` or `Guardrail` in the dashboard contract?
3. Which document should own API schemas: `docs/ARCHITECTURE.md` or a future `docs/API.md`?
