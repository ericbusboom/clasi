---
id: "011"
title: "Missing sub-dispatch logs in e2e output"
status: done
use-cases: [SUC-003]
depends-on: ["009"]
github-issue: ""
todo: "missing-sub-dispatch-logs-in-e2e-output.md"
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Missing sub-dispatch logs in e2e output

## Description

The e2e test output (`tests/e2e/project/docs/clasi/log/`) proves that
sub-dispatches from sprint-executor and sprint-planner are not being
logged despite ticket 009 adding logging instructions to their agent
definitions. Only team-lead-level dispatches appear. Across four sprints
with ~6 tickets, there are zero `ticket-*` log files (sprint-executor ->
code-monkey) and no distinguishable sprint-planner sub-dispatch logs
(sprint-planner -> architect/reviewer/technical-lead).

This ticket addresses the gap with two complementary fixes: strengthening
e2e verification to detect missing logs, and fixing the dispatch log
routing so planner sub-dispatches get distinct filenames.

### Changes

#### 1. Strengthen e2e verification

Update `tests/e2e/verify.py` `_check_dispatch_logs` to assert:

- For each sprint, at least one `ticket-*` log file exists (proving
  sprint-executor logged code-monkey dispatches).
- For each sprint, log files exist for planner sub-dispatches beyond the
  two team-lead -> sprint-planner entries.

This turns the gap from invisible to a test failure.

#### 2. Fix log routing for planner sub-dispatches

Update `dispatch_log.py` `log_dispatch` routing so that when
`sprint_name` is set and `ticket_id` is not, the filename prefix uses
the child agent name instead of hardcoding `sprint-planner`. Examples:

- team-lead -> sprint-planner: `sprint-planner-001.md`
- sprint-planner -> architect: `architect-001.md`
- sprint-planner -> architecture-reviewer: `architecture-reviewer-001.md`
- sprint-planner -> technical-lead: `technical-lead-001.md`

This is a one-line change: replace `prefix = "sprint-planner"` with
`prefix = child`.

#### 3. Consider programmatic enforcement

If agent-definition-level instructions continue to be ignored after
these changes, consider making `log_subagent_dispatch` a required step
in the dispatch skill itself, or adding a wrapper that automatically
logs before and after any subagent invocation.

## Acceptance Criteria

- [x] `_check_dispatch_logs` in `verify.py` asserts ticket-level log files exist per sprint
- [x] `_check_dispatch_logs` asserts planner sub-dispatch log files exist per sprint
- [x] `dispatch_log.py` uses child agent name as filename prefix for sprint-level (non-ticket) dispatches
- [x] Planner sub-dispatches produce distinctly-named log files (e.g., `architect-001.md`)
- [x] Existing team-lead -> sprint-planner logs continue to work correctly
- [x] `uv run pytest` passes with no regressions

## Testing

- **Existing tests to run**: `uv run pytest` -- no regressions to existing test suite
- **New tests to write**:
  - Unit test: `log_dispatch` with `sprint_name` and no `ticket_id` uses child agent name as prefix
  - Unit test: `_check_dispatch_logs` fails when ticket-level logs are missing
  - Unit test: `_check_dispatch_logs` fails when planner sub-dispatch logs are missing
  - Manual: Run e2e and confirm sub-dispatch logs appear at all levels
- **Verification command**: `uv run pytest`
