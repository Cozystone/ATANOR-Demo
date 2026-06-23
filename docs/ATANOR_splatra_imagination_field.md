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

Product home renders generative visual elements as particles. The surrounding dashboard field uses short particle strokes in a deterministic flow field instead of hard connector lines, inspired by the CodePen particle-swarm reference. Speech and self narration remain ordinary accessible text with a typewriter reveal; text is not converted into particles because the particle system is reserved for generated visual matter.

Lab mode exposes archetype selection, switch/random controls, particle count, compression ratio, LOD summary, visual intensity, clear radius, and a warning when the object is too subtle for product use.

## SPLATRA Command Adapter

The updated Cozystone/SPLATRA repository was reviewed at commit `3f5156e`. Its runtime contract is:

- user/agent command enters `POST /v1/chat` or a direct tool endpoint;
- tool calls such as `generate_3d_object`, `render_knowledge_hologram`, and scene actions create or morph a Gaussian field;
- raw 3D buffers are not sent through the agent/LLM context;
- the viewer pulls the binary cartridge through `/v1/cartridge` and performs the assemble/reassemble animation locally.

ATANOR now mirrors that boundary with `compile_splatra_command()` and `POST /api/agentic-os/splatra/imagination/command`.

This endpoint compiles a visual command into:

- a SPLATRA-style `scene_action` such as `spawn_object`, `morph`, or `render_knowledge_hologram`;
- a procedural proof-only particle frame for the current dashboard;
- a side-channel contract that says the future full SPLATRA viewer should fetch cartridges separately.

It does not call external LLMs, sLLMs, image models, Local Brain writes, Cloud production writes, candidate promotion, arbitrary JavaScript, git, or shell execution.

Product mode no longer draws constellation guide lines around the central orb. Those guide lines are kept for Lab inspection only because they were visually distracting on the user-facing dashboard.

The command path is intended to let ATANOR use SPLATRA as a bounded dashboard manipulator: move, morph, or recompose particles inside the UI surface without shell execution, production mutation, or hidden model calls.

## Scene Choreography Boundary

`POST /api/agentic-os/splatra/imagination/choreography` accepts an agent-authored scene plan and validates it into bounded beats such as `spawn_object`, `morph`, `move`, `focus_camera`, `label`, and `despawn`.

This layer does not invent topic-specific scenes. For example, it does not hard-code that a gravity question should become Newton, an apple, or a tree. The conversation/scene planner must author those beats from ATANOR's own non-LLM conversation stack, and this adapter only clamps timing, positions, object ids, archetypes, and layout.

When a plan asks for `scene_focus`, the dashboard can move the central orb toward the lower-right side and reserve the center of the product surface for SPLATRA particles. The input bar stays visible, and spoken text remains normal text rather than particle glyphs.

## Future Gates

- WebGL/WebGPU SPL3 decoder for client-side quantized data textures.
- Fish 2 audio envelope to speaking-energy mapping.
- User-approved character/persona-shaped hologram generation.
- Strict review queue for any generated SPLATRA patch before source changes.
