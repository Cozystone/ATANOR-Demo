# RAG Reference Notes

## External References Checked

- Microsoft GraphRAG: graph-first RAG pipeline that extracts structured data
  from unstructured text, builds graph/community context, and uses that context
  during retrieval.
- Haystack: modular AI orchestration framework with explicit control over
  retrieval, routing, memory, and generation.
- MiroFish: inspected for console layout and GraphRAG process visualization.
  No source code was copied because the repository is AGPL-3.0.

## Homage Alpha Decision

Homage Alpha keeps a local deterministic RAG engine instead of vendoring a
large external framework. The implementation now follows a compact hybrid
GraphRAG shape:

1. Chunk accepted DataGate documents.
2. Tokenize query and chunks with Unicode-safe lexical tokens.
3. Match query terms against Ontology Forge nodes.
4. Expand retrieval terms through one-hop graph edges.
5. Rank document chunks with BM25-style lexical scoring, coverage, phrase
   bonus, and graph boost.
6. Return answer text, evidence docs, citations, graph paths, follow-up
   questions, and a retrieval trace.

## Why This Is Better Than The Previous Alpha RAG

The previous version returned matched documents and graph nodes only. The new
version exposes enough structure for a real product loop:

- `answer` for chat UI rendering.
- `citations` for source grounding.
- `retrieval_trace` for debugging and visualization.
- `retrieval_signals` on evidence chunks so the UI can show lexical and graph
  contributions.
- Stable API compatibility with the old `evidence_docs`, `matched_nodes`, and
  `confidence` fields.

## Next Upgrade Path

- Add persistent embeddings and vector search for semantic retrieval.
- Add graph community summaries once Ontology Forge has enough edges.
- Store retrieval traces per session for evaluation.
- Add reranking and Guardrail-supported answer revision.
