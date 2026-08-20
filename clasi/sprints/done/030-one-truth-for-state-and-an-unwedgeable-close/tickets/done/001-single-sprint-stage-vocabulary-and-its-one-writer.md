---
id: '001'
title: Single sprint-stage vocabulary and its one writer
status: done
use-cases:
- SUC-001
depends-on: []
github-issue: ''
issue: single-sprint-stage-vocabulary.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Single sprint-stage vocabulary and its one writer

## Description

A sprint's lifecycle stage currently lives in three independently-written
places: DB `sprints.phase` (8 values, `roadmap`→`done`), frontmatter
`status:` (historically only 3 of those — `roadmap`/`planning-docs`/
`closed`), and a fifth, undocumented vocabulary (`"planning, active,
done"`) that `list_sprints`'s docstring and `.claude/rules/clasi-
artifacts.md` advertise but nothing ever writes. Because frontmatter's
own vocabulary and the *computed* sprint-machine state name (a fourth,
genuinely different concept — see ticket 002 and sprint.md's Design
Rationale) share only the string `"closed"`, `detect_inconsistencies`
flags essentially every healthy active sprint as drift.

This ticket makes DB phase the single recorded-stage vocabulary and adds
one writer, `Sprint.set_sprint_stage()`, that updates DB phase and
frontmatter `status:` together. See `sprint.md`'s Architecture section
(M1) and Design Rationale ("DB phase is the single sprint-stage
vocabulary...") for the full reasoning, including *why* the computed
sprint-machine vocabulary is kept, not deleted — it answers a different
question ("what can happen next," not "what stage is recorded") and is
simply no longer compared against frontmatter.

**Verified evidence** (checked against this repo's own code and DB
during planning, not assumed):
- `detect_inconsistencies` compares frontmatter `status:` against the
  computed sprint-machine state name at `status/inconsistency.py:112-137`
  (`_check_sprint`) — two vocabularies disjoint except for `"closed"`.
- `Sprint.detail_promote()` writes frontmatter then calls
  `self.advance_phase()` as two independent, non-transactional steps
  (`sprint.py:469-473`).
- `Sprint.archive()` writes `status: "closed"` (`sprint.py:504`), a
  *different* string than the DB phase vocabulary's own terminal value
  (`"done"`) — this is itself an instance of the four-vocabulary problem,
  introduced by sprint 019.
- This repo's own live DB has sprint `012` (archived under
  `sprints/done/`, frontmatter `status: done`) sitting at DB phase
  `"ticketing"` — a real, present three-way divergence. Confirm with
  `sqlite3 .clasi/.clasi.db "SELECT phase FROM sprints WHERE id='012'"`.
  This ticket's design (directory-location-based terminal exemption)
  resolves this with **zero data edits** — do not "fix" sprint 012's DB
  row or its frontmatter as part of this ticket; that would contradict
  the ticket's own no-historical-rewrite acceptance criterion below.

## Acceptance Criteria

- [x] `Sprint.set_sprint_stage(phase)` (new method on `Sprint` in
      `sprint.py`) writes the DB `sprints.phase` value and the sprint's
      frontmatter `status:` field together, in one call, and raises
      loudly (not `except: pass`) if either half fails.
- [x] `Sprint.detail_promote()` and `Sprint.advance_phase()` (the method
      `advance_sprint_phase` the MCP tool calls) route through
      `set_sprint_stage()` instead of each writing frontmatter and
      calling `self._project.db.advance_phase(...)` as two independent
      steps.
- [x] `Sprint.archive()` writes `status: "done"` instead of
      `status: "closed"`. This is a **value change only** — do not
      reorder `archive()`'s position within `close_sprint`'s step
      sequence in `tools/artifact_tools.py`'s `_close_sprint_full`; that
      reordering is ticket 004's scope, not this one's. `archive()` still
      does not touch DB phase directly (unchanged from today — DB phase
      advancement during close remains a separate step, redesigned by
      ticket 004).
- [x] The `"planning, active, done"` vocabulary is deleted from
      `list_sprints`'s docstring in `tools/artifact_tools.py` (currently:
      `status: Optional filter by status (planning, active, done)`) and
      from `.claude/rules/clasi-artifacts.md` (currently instructs
      `list_sprints(status="active")`, a call that always returns `[]`
      since nothing writes that value).
- [x] `status/inconsistency.py`'s sprint-level check
      (`_check_sprint`/`_explain_sprint_drift`) no longer compares
      frontmatter `status:` against the computed sprint-machine state
      name. It instead compares DB phase
      (`project.db.get_sprint_state(sprint_id)["phase"]`) against
      frontmatter `status:` — the same 8-value vocabulary on both sides,
      since `set_sprint_stage()` is now the sole writer of both.
- [x] `_sprint_terminal_states()`'s exemption (`status/inconsistency.py`,
      currently `load_machine("sprint").terminal_states()`) is replaced
      with a directory-location check: a sprint physically under
      `sprints/done/` is exempt from stage-drift checking regardless of
      which `status:` string it carries. Reuse the pattern
      `status/reporter.py`'s `_is_terminal_sprint` already established
      (declared-status match OR physical location) rather than inventing
      a second, differently-shaped check.
- [x] `list_sprints(status=...)` (`Project.list_sprints`) is exercised by
      a new test against the 8-value DB-phase vocabulary now written to
      frontmatter.
- [x] A new test (in `tests/unit/test_status/test_inconsistency.py` or
      equivalent) asserts a healthy active sprint, created via real
      writers, produces zero `state_drift` entries.
- [x] **No file under `clasi/sprints/done/` is edited by this ticket.**
      Run `git status` before committing; if any `sprints/done/` path
      appears in the diff, revert it. Sprint 012's DB-row/frontmatter
      mismatch is left exactly as-is — the design tolerates it, it does
      not require repairing it.

## Implementation Plan

**Approach**: Add the single writer, route the three existing frontmatter
writers through it, then redesign `inconsistency.py`'s comparison target
and terminal exemption to match. Do not touch `close_sprint`'s step
ordering or any `state_machine/` predicate file — those belong to
tickets 004 and 002 respectively; keep this ticket's diff scoped to
stage-vocabulary plumbing only.

**Files to modify**:
- `src/clasi/sprint.py` — new `set_sprint_stage()`; update
  `detail_promote()`, `advance_phase()`, `archive()`
- `src/clasi/status/inconsistency.py` — `_check_sprint`,
  `_explain_sprint_drift`, `_sprint_terminal_states`
- `src/clasi/tools/artifact_tools.py` — `list_sprints`'s docstring only
  (no logic change expected)
- `.claude/rules/clasi-artifacts.md` — drop the dead vocabulary
  reference and the `status="active"` instruction

**Do not modify**: any file under `state_machine/` (ticket 002),
`ticket.py`/ticket-status tool functions (ticket 003), or
`_close_sprint_full`'s step sequence (ticket 004).

## Process Notes (read before starting)

- **Guards are fail-closed as of sprint 029/009.** A crash inside
  role-guard or mcp-guard is now a hard block (exit 2, logged
  `guard-crash`), not a silent allow.
- **Editing ticket files under this locked sprint's `tickets/` tree is
  allowed for tier-2 agents as of sprint 029/010.** You do not need to
  check this ticket's acceptance-criteria boxes before flipping its
  `status` to `done`, or vice versa — either order works; the old trap
  where checking boxes after the status flip could get blocked no longer
  applies.
- **If a guard blocks you, STOP and report it.** Do not route around a
  block with a Bash heredoc, `sed`, output redirection, or any mechanism
  that avoids the tool the guard is watching. Reporting a block to the
  team-lead is a successful outcome of this ticket, not a failure — the
  stakeholder raised this explicitly for this sprint.
- **This ticket changes code the running MCP server also reads** (sprint
  stage writes/reads, `detect_inconsistencies`). Sprint 029 landed
  same-version staleness detection (`check_staleness`'s third signal),
  so drift between a server's loaded code and this ticket's changes is
  now *visible* via `get_version()`'s `stale` field — but the MCP server
  in the driving session for this sprint is already stale relative to
  this ticket's changes and will not pick them up mid-sprint. Do not
  expect `list_sprints`/`get_sprint_status` calls made through the
  current session's MCP connection to reflect this ticket's fix while
  you are still implementing it; that is expected, not a bug in your
  change. Verify via the test suite, not via live MCP calls against a
  server that hasn't restarted.

## Testing

- **Existing tests to run**:
  `uv run pytest tests/unit/test_sprint.py tests/unit/test_state_db_class.py tests/unit/test_status/test_inconsistency.py tests/unit/test_status/test_reporter.py tests/system/test_artifact_tools.py -v`
- **New tests to write**: a `set_sprint_stage()` unit test asserting
  DB+frontmatter agreement and loud failure on a partial-write injection;
  a `detect_inconsistencies` test asserting zero drift for a healthy
  active sprint built through real writers; a terminal-exemption test
  using a sprint whose DB phase is deliberately behind its archived
  directory location (modeling the live sprint-012 case) and asserting
  it produces no drift entry.
- **Verification command**: the existing-tests command above, scoped —
  do not run the full suite for this ticket (per `source-code.md`, a
  per-ticket run is scoped to the modules touched; the full-suite gate is
  owned by sprint close).
