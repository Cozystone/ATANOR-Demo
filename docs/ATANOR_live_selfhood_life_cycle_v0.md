# ATANOR Live Selfhood Life Cycle v0

Status: proof-only lifecycle engine.

Live Selfhood Life Cycle v0 makes ATANOR able to self-initiate safe local cycles:
observe state, detect needs, rank impulses, prepare proposals, deliberate
locally, generate briefs, and ask the user for approval. It does not apply
irreversible actions.

## Purpose

ATANOR should not only wait for prompts. In this proof slice it can run bounded
internal cycles and produce reviewable output:

- observations
- needs
- ranked impulses
- proposed actions
- local deliberation summaries
- morning, evening, and status briefs
- user-attention requests

## Autonomy Levels

- `LEVEL_0_OFF`: no autonomous cycle; user prompt only.
- `LEVEL_1_OBSERVE`: read-only periodic observations.
- `LEVEL_2_PROACTIVE_BRIEF`: briefs and non-mutating suggestions.
- `LEVEL_3_SANDBOX_PLANNER`: deterministic local deliberation, review packets,
  and sandbox plans only.
- `LEVEL_4_GATED_OPERATOR`: operator confirmation request preparation only.

Higher autonomy levels do not bypass safety gates. Real apply remains false.

## Local Life Clock

The deterministic life clock supports:

- startup
- periodic tick
- morning
- afternoon
- evening
- idle timeout
- user returned
- pre-sleep
- post-sleep
- manual ping

Tests use a simulated clock so lifecycle behavior is reproducible.

## Sensors

The lifecycle includes read-only sensors for:

- Git worktree state
- candidate backlog
- promotion review backlog
- memory approval backlog
- Selfhood Runtime status
- voice readiness
- Logical Sphere status
- disk resources
- dirty worktree signal

Sensors handle missing inputs gracefully and do not start learning jobs.

## Needs And Impulses

Observations are converted into needs such as:

- memory review needed
- promotion review needed
- repo hygiene needed
- morning brief needed
- quality audit needed
- voice setup needed
- operator confirmation needed
- user attention needed

Needs become impulses with urgency, importance, reversibility, user value, cost,
and safety scores. ATANOR may choose top safe impulses to prepare proposals or
briefs. It cannot apply the proposals.

## Scheduler

The scheduler can propose:

- observe status
- prepare morning or evening brief
- run deterministic local deliberation
- prepare memory review
- prepare promotion review
- prepare operator confirmation request
- recommend repo hygiene
- ask for user attention

The default limit is three actions per tick.

## Action Queue

The action queue is non-mutating. Queue items may be proposed, waiting for user,
approved for a future gate, rejected, deferred, or blocked. Even approved items
have `can_apply_now=false`.

## Briefs

Morning briefs include:

- What I noticed
- What changed
- What needs review
- What I propose
- What I blocked for safety
- What requires your approval

Evening briefs include:

- What I did not change
- Open proposals
- Memory candidates
- Promotion candidates
- Risks
- Suggested next step

The default tone is concise Korean. The proof limitation is visible but not
repeated as noise.

## Safety Gates

These invariants remain fixed:

- `real_local_brain_write=false`
- `real_local_brain_mutated=false`
- `production_store_mutated=false`
- `candidate_store_mutated=false`
- `candidate_promotion=false`
- `actual_promotion_performed=false`
- `external_llm_used=false`
- `real_p2p_used=false`
- `real_cloud_upload=false`
- `generated_code_executed=false`
- `real_hot_swap_performed=false`
- `always_listening_enabled=false`
- `raw_voice_saved=false`
- `memory_apply_enabled=false`
- `requires_user_approval=true`
- `text_input_supported=true`
- `voice_optional=true`

## What ATANOR Can Self-Initiate

ATANOR can self-initiate read-only observation, safe need detection, impulse
ranking, proposal creation, brief generation, sandbox planning, deterministic
local deliberation, and user-attention requests.

## What Still Requires Approval

Local Brain writes, production mutation, candidate promotion, real P2P, cloud
upload, generated-code execution, hot-swap, durable memory changes, and any
operator-confirmed write preparation require explicit review gates.

## Text And Voice

Text input remains primary because it is inspectable and reviewable. Voice is
optional. This slice does not enable always-on microphone capture and does not
save raw voice transcripts automatically.

## Not AGI Or Consciousness

This is a long-term AGI-oriented architecture component, not AGI. It is an
autonomous self-model loop, not real consciousness. Any IIT-like or selfhood
language is proof-kernel terminology, not a claim of sentience.

## Future Route

- Live Selfhood Cycle Lab UI route
- background service with explicit user opt-in
- user-configurable autonomy level
- notification system
- real memory gate after operator confirmation
- real promotion apply after signed manifest and rollback
