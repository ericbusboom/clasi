---
id: '006'
title: E2E single run report
status: done
use-cases:
- SUC-006
depends-on:
- '002'
- '003'
- '004'
- '005'
github-issue: ''
issue: e2e-single-run-report.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# E2E single run report

## Description

An E2E run currently "returns" nothing: evidence is scattered across the
tester's terminal, container logs, and `.clasi/log/`. This ticket adds
`report.sh`, a new script that reads everything tickets 002-005 produced
for one run and assembles it into a single markdown file.
`validate.sh` stays a pure checker — it does not gain report-writing
logic; `report.sh` reads its (already tee'd, per ticket 002) output.
See sprint.md's Architecture, module 6 ("E2E Run Report") and SUC-006.

**Scope**: new `tests/e2e/report.sh` only. This is the sprint's last
ticket by construction — it is a pure reader of tickets 002 (run
capture + validate.sh tee), 003 (`mcp-calls.jsonl`), 004
(phase-transition history), and 005 (`hooks.log` tokens + `denied/`
payloads). Do not start this ticket until all four are done; the run
directory shape, the JSONL schema, and the `hooks.log` line format this
script parses are exactly what those tickets actually built, not a
speculative shape — read each one's final `sprint.md`/ticket diff before
writing the parser for its section.

**Sources to assemble, one section each (per the issue's own list):**

1. `validate.sh` output — tee'd into the run directory by ticket 002.
2. `run.sh` per-milestone durations and exit codes — from the
   `.e2e-runs/<run-id>/<NN>-<slug>/{exit-code,duration}` files ticket
   002 writes.
3. Phase timings — from ticket 004's `phase_transitions` history, **for
   the subject sprint under test, not sprint 028 itself.** `report.sh`
   runs on the host from `tests/e2e/`, reporting on a run of the E2E
   harness — the sprint whose phase history it must read is whatever
   sprint the *subject* team-lead (running inside the container, driven
   against the bind-mounted `e2e-project/`) created and advanced during
   that run. That sprint's state lives in the **subject's own** state
   database at `tests/e2e/e2e-project/.clasi/.clasi.db` — a completely
   separate SQLite file from this repo's own `.clasi/.clasi.db` (which
   tracks sprint 028's own planning, including this very ticket, and has
   nothing to do with the subject session being reported on). Since
   `report.sh` is a shell script with no MCP client and the subject's
   `clasi` CLI lives inside the (by report-time, likely already-removed)
   container rather than on the host, the practical read path is a
   direct host-side `sqlite3` query against that file, e.g.:
   `sqlite3 tests/e2e/e2e-project/.clasi/.clasi.db "SELECT sprint_id,
   from_phase, to_phase, at FROM phase_transitions ORDER BY at"` — this
   is the sanctioned approach for this ticket (see sprint.md's Design
   Rationale, decision 2, and Open Question 1: the CLI-vs-direct-read
   choice was left to implementation time, and a direct read is
   explicitly one of the two acceptable answers). Do not attempt to
   query the running container's MCP server or `clasi` CLI from
   `report.sh` — by the time a report is assembled, the container may
   already be gone (`stop.sh` has run), but the bind-mounted
   `e2e-project/` directory, including its `.clasi/.clasi.db`, persists
   on the host regardless.
4. `mcp-calls.jsonl` top-N slowest calls and all failures — ticket 003's
   output, one JSON object per line; use `jq` (already a reasonable
   dependency for a JSONL-processing shell script) or equivalent to sort
   by `ms` descending and filter `ok: false`.
5. `hooks.log` deny count and reasons histogram — count lines with exit
   code `2`, histogram by the `reason` field (the existing fixed-width
   reason-code column, unaffected in position by ticket 005's trailing
   `decisions` tokens).
6. Dispatch inventory from `.clasi/log/NNN-*.md` frontmatter durations —
   these files already exist independent of this sprint
   (`dispatch_log.py`'s transcripts, `duration_seconds` frontmatter per
   the reliability review's own inventory); parse their YAML frontmatter
   for `duration_seconds` and list them.
7. A scan of `mcp-server.log` for `input_value={}` validation-error
   signatures (the empty-args-sentinel bug's signature, per this
   project's own `.claude/rules/tool-call-empty-args.md`) — a simple
   `grep -c 'input_value={}' mcp-server.log`, reported as a count with
   surrounding context lines for each match.

## Acceptance Criteria

- [x] One command (`tests/e2e/report.sh <run-id>` or equivalent) produces
      `.e2e-runs/<run-id>/run-report.md` from a finished run's directory.
- [x] The report includes all seven sources listed above, each in its
      own clearly headed section.
- [x] The report is self-contained markdown a human can read top to
      bottom — no other artifact needed to interpret it (each section
      states what it's summarizing, not just raw dumped data).
- [x] `validate.sh` itself is unmodified by this ticket (it already
      gained the tee behavior in ticket 002); `report.sh` only reads
      `validate.sh`'s tee'd output file.
- [x] Running `report.sh` against a run directory that is missing one of
      the five upstream sources (e.g. a run predating this sprint) fails
      gracefully — a clear "section unavailable" note in that part of the
      report, not a hard crash that loses the rest of the report.

## Testing

- **Existing tests to run**: none — new shell script, not pytest-
  collected (same reasoning as tickets 001/002).
- **New tests to write**: none in the pytest sense. Lint the new script:
  `shellcheck tests/e2e/report.sh`.
- **Verification command**: `shellcheck tests/e2e/report.sh` (scoped,
  foreground). Full functional verification is running `report.sh`
  against a real run directory produced by an actual `start.sh` →
  driven session → `stop.sh` sequence — this is the sprint's own
  end-to-end success criterion (sprint.md Test Strategy), and since this
  ticket is last by dependency, it is the natural point at which that
  full validation run happens for the sprint as a whole.
