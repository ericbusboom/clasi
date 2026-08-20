---
id: '002'
title: E2E stop.sh teardown safety
status: open
use-cases: [SUC-002]
depends-on: []
github-issue: ''
issue: stop-sh-teardown-gated-on-run-id.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# E2E stop.sh teardown safety

## Description

A failed early E2E run (before a run id is minted) currently leaves
`stop.sh` unable to do **any** cleanup — it aborts entirely on run-id
resolution failure, leaving the `clasi-e2e` container running and a
real copy of the host's Claude Code OAuth credentials staged at
`tests/e2e/.creds-stage/.credentials.json` on disk. Discovered
immediately after the mcp-2.0 crash during the sprint-028 baseline
shakedown — exactly the scenario where cleanup is most needed and
least available (the worse the failure, the earlier it happens, the
less likely a run id exists). This ticket splits `stop.sh` into an
always-runs teardown half (container removal, `.creds-stage` deletion)
and a best-effort capture half (log/session saving, skipped with a
clear message when no run id resolves).

**Scope**: `tests/e2e/stop.sh`, `tests/e2e/start.sh`. Pure test-harness
shell scripts — `tests/e2e/` is excluded from `protected_paths`/
role-guard scope (`.clasi/config.yaml`'s `excluded_paths:
[tests/e2e]`), so this ticket carries no enforcement/lockout risk and
is not mirrored to the `design/` overlay (not a `src/clasi` subsystem).

**Files to touch (verified during planning):**

- `tests/e2e/stop.sh` — currently `resolve_run_id` failure (no
  `--run-id`, no positional, no `.e2e-runs/current`) causes the whole
  script to `exit 1` before any teardown runs (see the `ERROR: could
  not resolve a run id` message in the script). Restructure so
  container removal and `.creds-stage` deletion happen unconditionally
  (ideally via a `trap`-based cleanup, matching `start.sh`'s existing
  `cleanup()` pattern at line 81), and only the log/session **capture**
  step is skipped — with a clear stderr message — when no run id
  resolves.
- `tests/e2e/start.sh` — `cleanup()` (lines 81-86) currently only
  removes `$ENV_FILE`. Extend it to also remove `CREDS_STAGE_DIR`
  (`$SCRIPT_DIR/.creds-stage`, already defined at line 29) so
  credentials staged before an early failure don't survive an aborted
  `start.sh` run either.

## Acceptance Criteria

- [ ] `stop.sh` always performs teardown (container removal,
      `.creds-stage` deletion) regardless of whether a run id resolves
- [ ] When no run id resolves, `stop.sh` skips only the capture step,
      reporting clearly that artifacts could not be saved and why — it
      does not abort
- [ ] Credential staging is removed even when the container never
      started, and even when `docker` itself errors — a `trap`-based
      cleanup or an unconditional final step, not a happy-path line
- [ ] `start.sh`'s `cleanup()` trap also removes `.creds-stage`, not
      just `$ENV_FILE`
- [ ] Exercised by a test (or a documented manual check) that runs
      `stop.sh` with no `.e2e-runs/current` present and asserts the
      container and `.creds-stage` are both gone afterward
- [ ] The existing `guarded_wipe` safety check (refuses to wipe
      anything not ending in `/e2e-project`) is preserved unchanged —
      this ticket must not weaken that guard while restructuring the
      rest of the script

## Testing

- **Existing tests to run**: none — shell script, not importable
  Python; this module has no existing unit test file.
- **New tests to write**: a documented manual check (or a shell-level
  test harness if one already exists under `tests/e2e/`) that runs
  `./tests/e2e/stop.sh` with no `.e2e-runs/current` present and no
  container running, and asserts exit succeeds, the container is
  absent, and `.creds-stage` is absent.
- **Verification command**: manual —
  `rm -f tests/e2e/e2e-project/.e2e-runs/current && ./tests/e2e/stop.sh`
  from a clean state, then confirm `docker ps -a | grep clasi-e2e` and
  `ls tests/e2e/.creds-stage` both come up empty. No `uv run pytest`
  scope for this ticket — shell-only change.
