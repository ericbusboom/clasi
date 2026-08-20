---
id: '002'
title: 'E2E run capture: run.sh, stop.sh, validate.sh tee'
status: done
use-cases:
- SUC-002
depends-on:
- '001'
github-issue: ''
issue: e2e-run-capture-and-artifact-collection.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# E2E run capture: run.sh, stop.sh, validate.sh tee

## Description

A failed E2E run today has no replayable record: subject `claude -p`
output exists only in the tester's terminal, container-side session
JSONLs (`/home/agent/.claude/projects/`) die with `docker rm`, and
`validate.sh` results go to stdout only — every check needs the running
container even though the artifacts it inspects are on the host bind
mount. This ticket makes the run durable: a wrapper the tester must use
instead of raw `docker exec`, container-log/session capture before
teardown, and validator output that survives the container. See
sprint.md's Architecture, module 2 ("E2E Run Capture") and SUC-002.

**Scope**: new `tests/e2e/run.sh`; `tests/e2e/start.sh` (run-id minting
and version/digest recording — extends ticket 001's minimal run
directory, see below); `tests/e2e/stop.sh`; `tests/e2e/validate.sh`;
`tests/e2e/AGENTS.md`. Does not touch the preflight probe (ticket 001,
already done) or report assembly (ticket 006, depends on this ticket).

**Depends on ticket 001**: ticket 001 built a minimal `.e2e-runs/<id>/`
directory just for its preflight output. Read what ticket 001 actually
committed to `start.sh` before starting — this ticket's run-id minting
either extends that scheme (adding version/digest recording to the
directory ticket 001 already creates) or, if ticket 001's scheme is
awkward to extend, supersedes it cleanly. Either way, by the end of this
ticket `start.sh` must have exactly one run-id-minting code path — no
leftover, unused directory-creation logic from ticket 001.

**Key source locations verified during sprint planning:**

- `tests/e2e/AGENTS.md:140-156` — the tester currently fires
  `docker exec clasi-e2e claude -p --dangerously-skip-permissions
  --output-format text --max-turns <N> "<prompt>"` directly per
  milestone. This is the call site `run.sh` wraps and `AGENTS.md` must
  be edited to mandate instead of the raw form.
- `tests/e2e/stop.sh` — currently: stop container, remove container,
  remove the legacy `clasi-data` volume, remove the staged subscription
  credentials, optional `--wipe`. Capture (`docker logs` and the
  session-directory copy) must happen **before** the `docker stop`/
  `docker rm` calls near the top of the script, not after — the
  container and its filesystem are gone once those run.
- `tests/e2e/validate.sh:11-37,130-140` — 29 mechanical checks via
  `docker exec`, results only to stdout, `exit 1` on any FAIL. Needs (a)
  a `tee` of its full output into the run directory, (b) checks
  rewritten to read host-mounted paths (the bind-mounted project dir)
  where possible instead of `docker exec`, so validation still works
  after `stop.sh` has already removed the container.

**Run-ID handoff contract (the one piece of this pipeline nobody had
written down — specify and implement exactly this):** `start.sh` mints
the run id and is the only script that *decides* it. Every other script
that needs it (`run.sh`, `validate.sh`, `stop.sh`, and ticket 006's
`report.sh`) must be able to discover the current run id without the
tester passing it around by hand on every invocation. Mechanism:

- `start.sh`, after minting `<run-id>`, writes it as the sole line of
  `e2e-project/.e2e-runs/current` (plain text, no trailing metadata —
  just the id, so `cat .e2e-runs/current` is the whole read path).
- `run.sh`, `validate.sh`, `stop.sh`, and (for ticket 006) `report.sh`
  each resolve the run id the same way: an optional explicit `--run-id
  <id>` (or first positional) argument, if given, wins; otherwise read
  `.e2e-runs/current`. If neither is available (no argument and no
  `current` file), fail loudly with a clear error rather than silently
  operating on the wrong or a nonexistent run directory.
- `.e2e-runs/current` is overwritten (not appended) on every `start.sh`
  run, including `--resume` — a resumed run's captured milestones should
  append to the *same* run directory `--resume` is resuming, not mint a
  second one, so `--resume` must re-derive or preserve the existing run
  id rather than minting a fresh one. Confirm this explicitly against
  `start.sh`'s existing `--resume`/`E2E_RESUME` handling before writing
  the minting logic — don't let `--resume` silently orphan the previous
  run's `current` pointer.
- This contract reconciles with the ticket-001 coordination note above:
  whatever minimal run-directory/id scheme ticket 001 built for its
  preflight output must speak this same `current`-file contract by the
  time this ticket is done — one run-id-minting path, one discovery
  mechanism, used by every script that touches a run directory.

## Acceptance Criteria

- [x] New `tests/e2e/run.sh` wrapper exists; the tester uses it instead
      of raw `docker exec claude -p`.
- [x] Each `run.sh` call writes
      `e2e-project/.e2e-runs/<run-id>/<NN>-<slug>/{prompt.txt,
      output.jsonl, exit-code, duration}`.
- [x] `run.sh` invokes the subject with `--output-format stream-json
      --verbose` (not `--output-format text`) so tool calls and turn
      counts land in `output.jsonl`.
- [x] `start.sh` mints the run id (reconciled with ticket 001's minimal
      directory per the coordination note above) and records `claude
      --version`, `clasi --version`, and the image digest into the run
      directory.
- [x] `start.sh` writes the minted run id to `e2e-project/.e2e-runs/current`
      per the Run-ID handoff contract above, and re-derives/preserves the
      existing run id on `--resume` instead of minting a new one.
- [x] `run.sh`, `validate.sh`, and `stop.sh` all resolve the run id via
      the same contract (explicit `--run-id`/positional argument first,
      `.e2e-runs/current` otherwise) and fail loudly if neither
      resolves. Deliberate, documented deviation: `run.sh`'s two
      positionals are already `<slug>` and `<prompt>`, so unlike
      `stop.sh`/`validate.sh` it does not also accept a bare positional
      as a run-id override — only `--run-id <id>` or `.e2e-runs/current`.
      Explained in `run.sh`'s header comment and in `AGENTS.md`.
- [x] `stop.sh`, before removing the container, saves `docker logs
      clasi-e2e` and copies the subject's `~/.claude/projects` session
      directory into the run dir.
- [x] `tests/e2e/AGENTS.md` is edited to mandate `run.sh` for all subject
      sessions, replacing the raw `docker exec claude -p` instruction.
- [x] `validate.sh` output is tee'd into the run directory.
- [x] `validate.sh` checks read host bind-mount paths where possible, so
      validation works after `stop.sh` has already removed the
      container.
- [x] When the run directory is minted, `.e2e-runs/` is added to the
      **subject** project's own `.gitignore`
      (`tests/e2e/e2e-project/.gitignore`, inside the bind-mounted
      project the subject team-lead operates on) — not just this repo's
      gitignore. Without this, the subject team-lead (running `git add`/
      `git status` inside its own project during a driven session) can
      see and potentially sweep `.e2e-runs/` artifacts into its own
      sprint commits mid-run, contaminating both the subject's git
      history and the evidence this sprint is trying to capture cleanly.

## Testing

- **Existing tests to run**: none — shell scripts, not pytest-collected
  (same reasoning as ticket 001).
- **New tests to write**: none in the pytest sense. Lint every changed
  or new shell file: `shellcheck tests/e2e/run.sh tests/e2e/start.sh
  tests/e2e/stop.sh tests/e2e/validate.sh`, fix new warnings.
- **Verification command**: `shellcheck tests/e2e/run.sh tests/e2e/start.sh
  tests/e2e/stop.sh tests/e2e/validate.sh` (scoped, foreground). Full
  functional verification — a run directory that actually reconstructs a
  session after `stop.sh` — happens in the sprint's own end-to-end
  validation (sprint.md Test Strategy), not as part of this ticket.
