---
status: pending
---

# claude CLI rejects every model when routed through the OpenRouter base-URL redirect — blocks e2e subject sessions

## Description

The e2e harness drives the subject (in-container Claude Code) via
`docker exec clasi-e2e claude -p ...` with `ANTHROPIC_BASE_URL`
redirected to `https://openrouter.ai/api/v1`. During sprint 023's smoke
verification (2026-07-17), the one live model round-trip
(`claude -p --max-turns 1 "Reply READY"`) could not complete: the
`claude` CLI (v2.1.210, installed unpinned in the Dockerfile via
`npm install -g @anthropic-ai/claude-code`) rejects **every** model
string tried — including current, non-retired ids — with a client-side
"may not exist or you may not have access" gate before any request
leaves the container.

This is not a harness-script defect (all `tests/e2e/*.sh` mechanics
passed), and not an OpenRouter/credential problem: direct `curl` to
OpenRouter's `/models` and `/chat/completions` with the same
`OPENROUTER_API_KEY` confirmed `anthropic/claude-opus-4.8` is available
and answers correctly. The gate is inside the `claude` binary's own
model-name validation, which does not account for the base-URL redirect.

Impact: as it stands, the full 4-sprint e2e run cannot drive the subject
through OpenRouter — every subject `claude -p` invocation would hit this
gate. The harness rework (sprint 023) is otherwise complete and correct;
this is the remaining blocker to an actual end-to-end run.

## Cause

Not fully diagnosed. The `claude` CLI appears to validate the model
identifier against a built-in allow-list / capability probe that assumes
the real Anthropic API, and fails closed when the base URL points at
OpenRouter (whose model ids and `/models` shape differ). Because the
image installs `@anthropic-ai/claude-code` unpinned, the exact gate
behavior can also drift between image builds.

## Proposed fix

Investigate and pick a viable subject-driving path; candidates:

- Find the CLI flag/env that disables client-side model validation (or
  the correct `ANTHROPIC_MODEL` / auth-header combination) that lets the
  OpenRouter redirect through, and bake it into the container env /
  `claude -p` invocation documented in `tests/e2e/AGENTS.md`.
- Pin `@anthropic-ai/claude-code` to a known-working version in the
  Dockerfile so the gate behavior is reproducible, and record which
  version works.
- If OpenRouter can't be made to work with the CLI, switch the subject
  to a direct Anthropic API key (drop the base-URL redirect) — changes
  the cost/routing story the harness was built around, so treat as a
  fallback.

## Verification

- `docker exec clasi-e2e claude -p --max-turns 1 "Reply READY"` returns a
  reply with no model-access error.
- A minimal 1-sprint subject run completes end-to-end without the gate
  firing.

## Related

- Surfaced by sprint 023 ticket 003 (smoke verification) — recorded as
  the one BLOCKED row in that ticket's `## Smoke Results`.
- The harness itself (`clasi-e2e-harness-rework-...`) is done and merged;
  this is the follow-on blocker to a real run.
