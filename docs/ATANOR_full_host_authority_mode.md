# ATANOR Full Host Authority Mode

Status: v0 permission layer only. No dangerous demo commands are implemented.

Full Host Authority is an explicit operator-root mode for the owner's local machine. It exists so ATANOR can be granted broad local capability on purpose, while preventing accidental, silent, remote, or model-only escalation.

## What Tier 4 Can Represent

With explicit activation and matching sub-switches, Tier 4 can authorize:

- PC-wide file reads
- PC-wide file writes
- host shell actions
- code modification
- git commit or push
- Local Brain writes
- Cloud production writes
- browser control
- MCP tools
- code execution

## What Tier 4 Does Not Bypass

Tier 4 does not allow:

- credential exfiltration
- private data upload without exact operator approval
- hidden persistence or autostart installation
- stealth behavior
- destructive delete without secondary confirmation
- disabled audit logs
- OS security prompt bypass
- malware-like replication
- external LLM or sLLM API calls

## v0 Execution Boundary

The v0 implementation verifies permission and records audit events. It includes only harmless test helpers for `echo`, `git status`, and temp-file writes in test-controlled paths. It does not expose an arbitrary shell execution API.

This preserves the design principle: full host authority can exist, but it must be operator-confirmed, scoped by sub-switch, visible, logged, and stoppable.
