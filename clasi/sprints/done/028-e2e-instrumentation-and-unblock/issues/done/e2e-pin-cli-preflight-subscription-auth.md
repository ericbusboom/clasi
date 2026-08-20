---
status: done
type: bug
tags:
- reliability-campaign
- phase-0
- e2e
sprint: 028
tickets:
- 028-001
---

# E2E: pin the claude CLI, add a preflight probe, default to subscription auth

## Description

The E2E harness cannot currently complete a run on its default path, and
failures surface only after a full image build, at the first milestone.
From the reliability review (docs/reviews/2026-08-reliability/00-review.md,
C13; detail in 05-e2e-test-infra.md finding 1):

1. `tests/e2e/Dockerfile:22` installs `@anthropic-ai/claude-code` unpinned,
   so CLI gate behavior drifts per image build.
2. The default `--auth=openrouter` path is known-broken: the CLI rejects
   every model through the base-URL redirect (see
   `clasi/issues/later/claude-cli-rejects-models-through-openrouter-redirect-in-e2e.md`,
   which stays parked — the decision is to route around it, not fix it now).
3. `start.sh`'s readiness check is tmux-only; a dead model path is
   discovered 20 minutes in.

## Acceptance criteria

- Dockerfile pins a known-good `@anthropic-ai/claude-code` version.
- `start.sh` defaults to `--auth=subscription`; openrouter remains available
  behind an explicit flag with a warning referencing the parked issue.
- `start.sh` runs a preflight after container start: an in-container
  `claude -p --max-turns 1 "Reply READY"` and `clasi --version`, written to
  the run directory, aborting loudly on failure.
