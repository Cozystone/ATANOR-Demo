# ATANOR SPLATRA Imagination Field v1

Status: proof-only procedural renderer.

SPLATRA Imagination Field v1 gives ATANOR a bounded particle visualization layer for the dashboard and Agentic Micro-OS lab. It is designed to show internal state and creative exploration as procedural particle forms without treating those forms as verified knowledge.

Stage v1 makes the product surface visibly legible: the central hologram orb remains ATANOR's body, while the surrounding dashboard space becomes a particle imagination stage that can form recognizable procedural objects around and behind the orb.

## Scope

- Generates procedural particle objects from deterministic seeds.
- Supports archetypes: `orb`, `tower`, `tree`, `creature`, `circuit`, `city_block`, `constellation`, `machine_core`, and `abstract_memory_cloud`.
- Product mode excludes `orb` from the surrounding imagination cycle because the orb is the central body. The visible field cycles through `constellation`, `city_block`, `circuit`, `tree`, `machine_core`, `tower`, `abstract_memory_cloud`, and `creature`.
- Each generated object reports visible projection metadata: `visible_object=true`, `product_visible=true`, `active_archetype`, `particle_count`, `compression_ratio`, `lod_levels`, `visual_intensity`, and `clear_radius`.
- Maps bounded visual controls from state-like inputs: valence, arousal, curiosity, speaking energy, and resting.
- Connects to the existing Turbovec proof package for compression metrics, LOD summaries, and client budget hints.
- Exposes proof-only API routes under `/api/agentic-os/splatra/imagination/*`.
- Renders a low-budget product dashboard loop and a controllable Lab preview.

## Safety Boundary

The imagination field is not a knowledge source and does not write memory.

- `external_llm=false`
- `external_sllm=false`
- `image_model_used=false`
- `local_brain_write=false`
- `production_store_mutated=false`
- `candidate_promotion=false`
- `generated_scene_committed=false`
- `is_verified_knowledge=false`

The values named valence, arousal, curiosity, and speaking energy are bounded renderer controls. They are not claims of real emotion or consciousness.

## Agentic Micro-OS Actions

The SPLATRA Cosmos Cell may:

- generate a procedural imagination frame
- evaluate the proof-only archetype set
- compress an imagination object through the Turbovec bridge
- propose a review-only SPLATRA patch

It may not execute generated code, mutate production stores, write Local Brain memory, promote candidates, commit, or push.

## Product vs Lab

Product home uses a bounded particle budget and rotates through recognizable archetypes without exposing internal controls. It preserves a clear radius around the central orb and input bar so the conversation surface remains readable.

Lab mode exposes archetype selection, switch/random controls, particle count, compression ratio, LOD summary, visual intensity, clear radius, and a warning when the object is too subtle for product use.

## Future Gates

- WebGL/WebGPU SPL3 decoder for client-side quantized data textures.
- Fish 2 audio envelope to speaking-energy mapping.
- User-approved character/persona-shaped hologram generation.
- Strict review queue for any generated SPLATRA patch before source changes.
