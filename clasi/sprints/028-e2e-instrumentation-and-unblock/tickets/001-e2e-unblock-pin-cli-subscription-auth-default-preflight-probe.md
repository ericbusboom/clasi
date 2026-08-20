---
id: '001'
title: 'E2E unblock: pin CLI, subscription-auth default, preflight probe'
status: done
use-cases:
- SUC-001
depends-on: []
github-issue: ''
issue: e2e-pin-cli-preflight-subscription-auth.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# E2E unblock: pin CLI, subscription-auth default, preflight probe

## Description

The E2E harness cannot complete a run on its default path today: the CLI
is installed unpinned, the default `--auth=openrouter` path is dead (the
CLI rejects every model through the base-URL redirect — parked in
`clasi/issues/later/claude-cli-rejects-models-through-openrouter-redirect-in-e2e.md`,
not this ticket's concern), and `start.sh`'s readiness check is
tmux-only, so a dead model path is discovered only after a full image
build, at the first driven milestone. This ticket is the sprint's
unblock: nothing else in sprint 028 is measurable until a subject
session can reliably start. See sprint.md's Architecture, module 1 ("E2E
Unblock") and SUC-001 for the full context; this ticket implements that
module.

**Scope**: `tests/e2e/Dockerfile` and `tests/e2e/start.sh` only. Does not
touch run capture (`run.sh`, `stop.sh`, ticket 002), does not attempt to
fix the openrouter model-gate rejection itself (parked, out of scope for
the whole sprint per sprint.md's Out of Scope).

**Key source locations verified during sprint planning:**

- `tests/e2e/Dockerfile:22` — `RUN npm install -g @anthropic-ai/claude-code
  && claude --version` installs the CLI unpinned. Pin to a specific
  version (`@anthropic-ai/claude-code@<version>`) — choose the newest
  version available at implementation time and record it in the commit
  message; the existing `&& claude --version` line already self-verifies
  the pin at build time (build fails if the version string doesn't
  resolve), so no additional Dockerfile-level check is needed.
- `tests/e2e/start.sh` — `E2E_AUTH="${E2E_AUTH:-openrouter}"` (near the
  top, alongside the `--auth=*` flag parser a few lines below) sets the
  default. Flip the default to `subscription`. When the resolved auth is
  `openrouter` (explicit `--auth=openrouter` or `E2E_AUTH=openrouter`),
  print a warning to stderr referencing
  `clasi/issues/later/claude-cli-rejects-models-through-openrouter-redirect-in-e2e.md`
  before proceeding — openrouter must remain reachable for whoever
  eventually revisits that parked issue, just not be the silent default.
- `tests/e2e/start.sh` — the readiness wait loop near the end of the
  script (`for i in $(seq 1 30); do if docker exec "$CONTAINER_NAME"
  tmux has-session -t claude ...`) currently treats "tmux session exists"
  as the only readiness signal. After that loop succeeds, add the
  preflight: `docker exec "$CONTAINER_NAME" claude -p --max-turns 1
  "Reply READY"` and `docker exec "$CONTAINER_NAME" clasi --version`.
  Abort loudly (non-zero exit, clear stderr message naming which probe
  failed) if either command fails or the `claude` probe's output doesn't
  look like a completed reply — match the script's existing fail-fast
  style (`set -euo pipefail`, the explicit checks in `guarded_wipe`/
  `probe_bind`).

**Run-directory coordination note (read before starting):** the issue's
acceptance criterion says preflight output is "written to the run
directory," but the full run-id/version/digest-recording scheme is
ticket 002's job (`e2e-run-capture-and-artifact-collection.md`), and
ticket 002 depends on this one. Since this ticket has no dependency and
must land first, create the minimal run directory this preflight needs
(a timestamp- or PID-based `.e2e-runs/<id>/` directory is sufficient —
it does not need to match ticket 002's eventual full scheme). Ticket
002's programmer will read what this ticket actually built and extend or
supersede it — by the end of ticket 002, `start.sh` must have exactly
one run-id-minting code path, not two competing ones. Don't over-build
this; a directory and a `preflight.txt` file are enough for this ticket.

## Acceptance Criteria

- [x] Dockerfile pins a known-good `@anthropic-ai/claude-code` version
      (not `npm install -g @anthropic-ai/claude-code` unpinned).
- [x] `start.sh` defaults to `--auth=subscription`.
- [x] Openrouter remains available behind the existing explicit
      `--auth=openrouter` flag, now with a warning to stderr referencing
      the parked issue file.
- [x] `start.sh` runs the preflight (`claude -p --max-turns 1 "Reply
      READY"` + `clasi --version`) after the container reaches its
      tmux-ready state.
- [x] Preflight output (both commands') is written to a run directory
      under `.e2e-runs/`.
- [x] Preflight failure (either command) aborts `start.sh` loudly: clear
      stderr message, non-zero exit — not a silent continue into a dead
      milestone 20 minutes later.

## Testing

- **Existing tests to run**: none — `tests/e2e/*.sh` are shell scripts,
  not pytest-collected (`pyproject.toml`'s `testpaths = ["tests"]` /
  `norecursedirs` excludes the E2E fixture project, and shell scripts
  aren't Python test modules regardless). No unit-test regression risk
  from this ticket.
- **New tests to write**: none in the pytest sense. Lint the two changed
  shell-editing sites with `shellcheck tests/e2e/start.sh` (available on
  this machine at `/opt/homebrew/bin/shellcheck`) and fix any new
  warnings the preflight/auth-default edit introduces. The Dockerfile
  change self-verifies at `docker build` time via the existing `&&
  claude --version` line.
- **Verification command**: `shellcheck tests/e2e/start.sh` (scoped,
  foreground — this ticket touches no Python, so there is no `uv run
  pytest` scope for it). Full functional verification is the manual
  end-to-end run described in sprint.md's Test Strategy (`start.sh` →
  driven session → `stop.sh` → `report.sh`), which is this sprint's own
  success criterion, not a per-ticket automated test — do not attempt to
  script a full container run as part of this ticket's own testing.
