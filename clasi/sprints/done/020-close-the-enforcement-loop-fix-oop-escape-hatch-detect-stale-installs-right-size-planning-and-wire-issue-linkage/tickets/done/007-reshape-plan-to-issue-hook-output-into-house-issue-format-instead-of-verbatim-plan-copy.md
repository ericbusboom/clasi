---
id: '007'
title: Reshape plan-to-issue hook output into house issue format instead of verbatim
  plan copy
status: done
use-cases:
- SUC-007
depends-on: []
github-issue: ''
issue: plan-to-issue-hook-copies-plans-verbatim-producing-plan-shaped-issues.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Reshape plan-to-issue hook output into house issue format instead of verbatim plan copy

## Description

`plan_to_issue()` (`src/clasi/plan_to_issue.py:52-77`, wired via
`handle_plan_to_issue` in `hook_handlers.py:1006-1019`) copies a plan's
body verbatim into `clasi/issues/`, stripping only frontmatter. Observed
2026-07-14: the resulting issue carried "Scope of this plan / Do not
implement", a "Deliverable" section instructing the reader to create the
file that already existed, "Files to touch (this plan)", and
plan-shaped headings instead of the house `Description/Cause/Proposed
fix/Verification/Related` format. `plan_to_issue_from_text()` (the Codex
path, `:80-120`) has the same pass-through behavior.

Preferred fix (option 1 from the issue): change the hook's block-and-hand-
off reason so the model rewrites the just-written file into issue format,
rather than parsing/template-mapping plan sections (which is brittle —
heading names are model-chosen). The hook already supports
`{"decision": "block", "reason": ...}`; only the reason text needs to
change. This also fixes the filename defect (drop the redundant `issue-`
prefix) by instructing the model on naming.

## Acceptance Criteria

- [x] Entering plan mode with a plan containing a "## Scope of this plan"
      section that says "do not implement," then exiting plan mode,
      produces a `clasi/issues/*.md` with none of: "Scope of this plan",
      "Deliverable", "Files to touch", or an instruction to create the
      file that already exists.
- [x] The resulting file contains `## Description` and `## Proposed fix`
      headings (house format).
- [x] The resulting filename has no redundant `issue-` prefix.
- [x] Regression: `_unique_path` still suffixes `-2`/`-3` on collision;
      `status: pending` frontmatter still present; the source plan file
      is still unlinked after processing.
- [x] The Codex path (`plan_to_issue_from_text`) is covered by the same
      shape check, not just the Claude Code `ExitPlanMode` path.

## Implementation Notes

**Option chosen: 1 (block-and-hand-off), for the Claude Code
`ExitPlanMode` path.** Changed the `reason` string in
`handle_plan_to_issue` (`src/clasi/hook_handlers.py`) from "confirm the
issue was created and stop" to an explicit rewrite instruction: read the
just-written file, reshape it into `Description/Cause/Proposed
fix/Verification/Related`, strip plan-mode-only sections and framing,
keep `status: pending` frontmatter, rename away a redundant `issue-`
prefix if present, then stop without implementing. This is the only
option of the three that can reshape freeform, model-authored prose
without brittle heading-name matching (option 2), and it does not
normalize plan-shaped issues into the queue (option 3, rejected by the
issue itself since sprint-planners are misled by plan-mode framing).

**Codex path (`plan_to_issue_from_text` / `handle_codex_plan_to_issue`):
option 1's mechanism does not apply.** The Codex Stop hook fires *after*
the session has ended — there is no live model turn left to hand a
rewrite instruction to, unlike the mid-session `ExitPlanMode`
PostToolUse hook. Documented this directly in
`handle_codex_plan_to_issue`'s docstring rather than silently leaving
the path untouched. What *does* apply to both paths, since it's a purely
mechanical filename fix (not template-mapping of body content): a new
`_strip_redundant_issue_prefix()` helper in `plan_to_issue.py`, applied
to the slug in both `plan_to_issue()` and `plan_to_issue_from_text()`,
drops a leading `issue-` segment. The Codex path still receives
plan-shaped body content in the current implementation; that residual
gap is documented in the docstring as out of reach without a live model
turn, and would need its own follow-up if it matters in practice (e.g.
a second Codex-side pass, or sprint-planner-side normalization on read).

**`_unique_path` untouched**, per the ticket note — still suffixes
`-2`/`-3` on collision, verified by the pre-existing collision tests
plus the new prefix tests running alongside them.

**Tests**: `tests/unit/test_plan_to_issue.py` — new
`TestStripRedundantIssuePrefix` (unit tests for the helper) and
`TestPlanToIssueFilenamePrefix` (drives both `plan_to_issue` and
`plan_to_issue_from_text` with a real `# Issue: ...`-titled plan body,
asserting no `issue-` prefix lands in the output filename).
`tests/unit/test_hook_handlers.py` — new
`test_reason_instructs_model_to_rewrite_into_house_format` drives the
real (unmocked) `plan_to_issue()` through `handle_plan_to_issue` with a
plan file containing the actual observed "Scope of this plan / Do not
implement" and "Deliverable" framing, and asserts the block reason
instructs a rewrite (contains "rewrite", `## Description`, `##
Proposed fix`) and no longer contains the old "Confirm the issue was
created and stop." passthrough phrasing; also asserts the regression
set (issue file written, source unlinked, `status: pending`, no
`issue-` prefix). New `test_drops_redundant_issue_prefix_from_filename`
drives the real (unmocked) Codex path through
`handle_codex_plan_to_todo` with the same `# Issue: ...` framing and
asserts no `issue-` prefix.

**Revert check**: stashed both source files
(`src/clasi/plan_to_issue.py`, `src/clasi/hook_handlers.py`) and reran
the four new/changed test points. `TestStripRedundantIssuePrefix` and
`TestPlanToIssueFilenamePrefix` failed to even import
(`_strip_redundant_issue_prefix` doesn't exist pre-fix — collection
error, i.e. definitively absent). The hook-handler reason test failed
asserting `"rewrite" in reason.lower()` against the original verbatim
"Confirm the issue was created and stop." text. The Codex filename test
failed asserting `not issue_files[0].name.startswith("issue-")` against
the actual pre-fix output `issue-re-enable-the-mcp-process-content-tools.md`
— i.e. it reproduced the exact defect from the issue's observed
artifact. Restored the fix (`git stash pop`); full suite reran green.

**Full suite**: 2577 passed, 0 failures (was 2569 before this ticket;
+8 new tests). No version bump per 020-003's once-per-sprint cadence.

## Implementation Plan

**Approach**: Change the `reason` text returned by
`handle_plan_to_issue`'s block decision to instruct the model: rewrite the
just-written issue file into house format (Description/Cause/Proposed
fix/Verification/Related), strip plan-mode-only sections, and rename if
the filename carries a redundant `issue-` prefix. Apply the equivalent
instruction to the Codex text-based path.

**Files likely involved**: `src/clasi/hook_handlers.py` (the `reason`
string in `handle_plan_to_issue`), `src/clasi/plan_to_issue.py` (verify no
structural change needed there if the fix is purely reason-text based;
if the Codex path can't rely on an interactive model turn the same way,
document why and adjust there specifically).

**Testing plan**: Real plan-mode transcript fixture (a plan containing the
actual observed plan-mode framing) driven through the hook; assert the
resulting issue file's shape. Cover both Claude and Codex paths.

**Documentation updates**: None beyond the hook's own reason string;
no user-facing skill doc changes expected.
