# ATANOR Agentic Micro-OS

Status: proof-only bounded agent OS.

The Agentic Micro-OS gives ATANOR a capability-gated execution model. It is not
an infinite autonomous daemon and it does not have unrestricted tools.

## Kernel

- `CapabilityToken` scopes every permitted action.
- Forbidden capabilities include unrestricted shell, arbitrary JS, Local Brain
  direct write, production store direct write, candidate promotion, git commit,
  git push, microphone enable, unscoped private file read, and private upload.
- Allowed proof capabilities include dashboard action, mocked browser/API/MCP
  calls, Cloud verified read summaries, candidate draft writes, Local Brain
  redacted summaries, and human approval requests.

## Loop

`BoundedAgentLoop` stops at budget, records redacted observations, drafts skills,
and writes proposal-only patch manifests. It never auto-promotes skills, commits,
pushes, or mutates memory.
