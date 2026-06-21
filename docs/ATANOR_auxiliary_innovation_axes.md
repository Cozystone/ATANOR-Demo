# ATANOR Auxiliary Innovation Axes

This document introduces five auxiliary innovation axes for ATANOR. They are
supporting layers, not replacements for Cloud Brain, CGSR, RHFC, Local Brain, or
the candidate learning spine.

The active 24h candidate-only learning run was not touched by this work. No
current production path imports or uses these auxiliary axes yet.

## Current Order

1. Dijkstra Trust Router
2. Tabularis Privacy Shield
3. MiroFish Deliberation Lab
4. Turbovec Compression Layer
5. AirLLM Offload Sandbox

## 1. Dijkstra Trust Router

Status: proof-only implementation in `packages/atlas_router`.

Purpose: find the safest and cheapest temporary path to public knowledge
fragments, graph cartridges, Atlas peers, Graph Hub entries, or Cloud Brain
sources. The cost model includes latency, bandwidth, compute cost, stale data
risk, failure risk, trust penalty, license risk, and privacy risk.

Dijkstra Trust Router is first because it directly supports future Graph Hub,
Atlas Network, cartridge selection, and peer/source routing. It only selects
temporary Working Memory attach paths. It never approves permanent Local Brain
writes.

## 2. Tabularis Privacy Shield

Status: descriptor only.

Purpose: transform private structured data into safe synthetic, anonymized, or
redacted representations before any Cloud, Atlas, or deliberation layer can see
it. Tabularis should be built second because privacy boundaries must exist
before broader source routing or multi-agent deliberation.

## 3. MiroFish Deliberation Lab

Status: deferred descriptor only.

Purpose: future swarm-style deliberation over public or candidate knowledge.
MiroFish must not be built before candidate promotion gates exist, because a
deliberation layer without promotion discipline would amplify unreviewed
candidate artifacts.

## 4. Turbovec Compression Layer

Status: deferred descriptor only.

Purpose: future vector and graph compression plus hot/cold memory acceleration.
Turbovec should wait until graph scale and access patterns prove that
compression is the bottleneck.

## 5. AirLLM Offload Sandbox

Status: deferred descriptor only.

Purpose: future optional local or offloaded large-model reviewer/helper. It must
not become ATANOR's main engine, must not use external APIs by default, and must
remain behind explicit review boundaries.

## Protection Note

The 24h candidate-only learning run remains a protected experiment. This
document and the isolated `packages/atlas_router` proof package do not modify
the active daemon, Cloud Brain, API routes, Cloud Lab UI, candidate stores,
production stores, Local Brain, approved payloads, or runtime status files.

