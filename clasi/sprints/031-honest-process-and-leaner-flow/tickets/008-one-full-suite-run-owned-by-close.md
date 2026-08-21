---
id: 008
title: One full-suite run, owned by close
status: done
use-cases:
- SUC-008
depends-on:
- '007'
github-issue: ''
issue: one-full-suite-run-per-sprint.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# One full-suite run, owned by close

## Description

A sprint currently runs the full test suite three times: `execution.md`
§5.2 instructs a pre-close run; the `sprint-review` skill independently
re-runs it; `close_sprint` runs it a third time internally as its
precondition. Measured cost in this repo: 9m30s-19m41s per run (per the
issue) — 20-60 minutes of wall-clock per sprint spent re-running an
identical suite against an unchanged tree. Observed during the 028-030
campaign: the team-lead ran the suite manually then passed
`test_command="true"` to `close_sprint` to dodge a second identical run
— a workaround that quietly weakens the gate for anyone who doesn't know
the tree is unchanged.

**Depends on ticket 007 (soft — file-overlap ordering, not a functional
block)**: both tickets edit `execution.md`/skill instruction files;
landing 008 after 007 avoids two agents editing the same files in
parallel and merge-conflicting. There is no logic dependency — this
ticket's fix (delete the redundant run, interpret instead of re-run, add
a HEAD-sha marker) does not require anything 007 produces.

## Acceptance Criteria

- [x] `execution.md` §5.2's separate pre-close full-suite-run
      instruction is deleted.
- [x] The `sprint-review` skill calls `review_sprint_pre_close` and
      interprets its output instead of re-running the suite itself.
- [x] The orphaned `review_sprint_post_close` MCP tool (confirmed by
      grep during planning: referenced by no skill or agent doc today)
      is either wired to a caller or explicitly retired with a note
      explaining the decision — not left silently unreferenced.
- [x] A "tests already passed for HEAD `<sha>`" marker (or equivalent)
      lets a deliberate close re-run skip redundant work without the
      operator reaching for a fake `test_command`. `close_sprint`'s
      existing `test_command="SKIP"` sentinel (030) is kept unchanged as
      the explicit escape hatch it already is — this marker makes it
      unnecessary in the *normal* flow, it does not replace it.
- [x] `close_sprint`'s own internal test run (`close.py`'s `SprintCloser`)
      is unchanged — this ticket makes it the sprint's *only* run, not a
      different run.
- [x] The docs state the number of full-suite runs per sprint (one) once,
      in one place, matching what the code does.

## Implementation Plan

**Approach**: delete two of the three run sites, wire the third
(`sprint-review`) to interpret rather than re-run, add the HEAD-sha
marker as a small, targeted addition — not a new test-result caching
subsystem.

**Files to modify**:
- `src/clasi/schemas/se-process/instructions/execution.md`
- `src/clasi/plugin/skills/sprint-review/SKILL.md` (or wherever
  `sprint-review`'s instructions actually live — confirm exact path
  during implementation)
- Wherever `review_sprint_pre_close`/`review_sprint_post_close` are
  defined (`tools/artifact_tools.py` or `process_tools.py` — confirm)
  for the HEAD-sha marker, if it needs a small code addition rather than
  being purely a doc/skill change

**Do not modify**: `close.py`'s test-execution step itself (unchanged —
this ticket makes it the sole run, not a different run); the
`test_command="SKIP"` sentinel's existing behavior.

## Process Notes (read before starting)

- **Guards are fail-closed as of sprint 029/009.** A crash inside
  role-guard or mcp-guard is a hard block, not a silent allow.
- **Editing ticket files under this locked sprint's `tickets/` tree is
  allowed for tier-2 agents as of sprint 029/010.** Check-boxes-then-flip
  or flip-then-check-boxes both work.
- **If a guard blocks you, STOP and report it.** Do not route around a
  block with a Bash heredoc, `sed`, redirection, or any mechanism that
  avoids the tool the guard is watching. Reporting a block is a
  successful outcome of this ticket, not a failure.

## Testing

- **Existing tests to run**:
  `uv run pytest tests/system/test_close_sprint_resumability.py tests/unit/test_close_sprint_auto_detect.py -v`
- **New tests to write**: the HEAD-sha marker's skip behavior;
  `sprint-review` calling `review_sprint_pre_close` instead of
  re-running.
- **Verification command**: the existing-tests command above, scoped to
  this ticket's modules — never a live full-suite run as part of this
  ticket's own testing (that would be exactly the redundant run this
  ticket exists to eliminate).
