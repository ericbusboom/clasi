---
id: '002'
title: 'close_sprint: recovery-state writes on frontmatter-fence and id-mismatch branches'
status: done
use-cases:
- SUC-005
depends-on: []
github-issue: ''
issue: guard-dead-ends-no-ticket-gate-scope-and-close-sprint-recovery.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# close_sprint: recovery-state writes on frontmatter-fence and id-mismatch branches

## Description

`_close_sprint_full` (`src/clasi/tools/artifact_tools.py`) has three
precondition-failure branches that each hand out a recovery instruction
("edit this file and retry"), but only one of them (the ticket-not-done
branch, around line 1533-1552) actually calls `db.write_recovery_state`
to record that recovery state. The other two — the frontmatter-fence
error branch and the sprint-id-mismatch branch (around lines 1467-1517)
— return `recovery: {recorded: False, allowed_paths: []}`, so the
role-guard recovery bypass can never fire for the exact file the
instruction just told the caller to edit. This ticket makes those two
branches write recovery state the same way the third already does.

## Acceptance Criteria

- [x] The frontmatter-fence-error branch calls
      `db.write_recovery_state(sprint_id, "precondition", [<sprint.md path>],
      <error message>)` before returning, matching the pattern already
      used at `artifact_tools.py:1533-1552`.
- [x] The sprint-id-mismatch branch does the same.
- [x] `close_sprint` against a `sprint.md` with a broken frontmatter
      fence → the JSON response's `recovery.recorded` is `True` and
      `recovery.allowed_paths` contains the offending file's path.
- [x] A follow-up guarded `Edit` of that exact file passes with reason
      `recovery`.
- [x] Same behavior verified for the sprint-id-mismatch branch.
- [x] The existing ticket-not-done branch's recovery behavior is
      unchanged (no regression).
- [x] Tests use real `close_sprint` invocations against fixture sprints
      with each malformed-frontmatter condition, not mocked responses.

## Implementation Plan

**Approach**: Mirror the ticket-not-done branch's existing
`db.write_recovery_state(...)` call into the two branches identified
above. Keep the `step` argument as `"precondition"` for both, matching
the existing convention. No new recovery-state schema or DB migration
is needed — the `recovery_state` table's shape is unchanged; this
ticket adds two more call sites using it.

**Files to modify**:
- `src/clasi/tools/artifact_tools.py` (`_close_sprint_full`'s
  `SprintFrontmatterError` and `SprintIdMismatchError` except branches).
- The corresponding test module for `close_sprint` (e.g.
  `tests/unit/test_artifact_tools.py` or wherever `close_sprint`'s
  precondition tests live).

**Testing plan**: Construct fixture sprints with (a) a broken opening
`---` frontmatter fence and (b) a missing/incorrect `id:` field, call
`close_sprint` against each, and assert the JSON response's `recovery`
block is populated. Then simulate the follow-up guarded `Edit` (either
by calling `handle_role_guard` directly with a payload targeting the
named file, or via the existing recovery-state test harness pattern
used by the ticket-not-done branch's own tests) and assert it passes
with reason `recovery`.

**Documentation updates**: This sprint's `design/` overlay
(`clasi/sprints/026-hook-performance-and-guard-reliability/design/tools-DESIGN.md`)
already documents this change at the module level.
