---
id: '007'
title: Reshape plan-to-issue hook output into house issue format instead of verbatim
  plan copy
status: open
use-cases: [SUC-007]
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

- [ ] Entering plan mode with a plan containing a "## Scope of this plan"
      section that says "do not implement," then exiting plan mode,
      produces a `clasi/issues/*.md` with none of: "Scope of this plan",
      "Deliverable", "Files to touch", or an instruction to create the
      file that already exists.
- [ ] The resulting file contains `## Description` and `## Proposed fix`
      headings (house format).
- [ ] The resulting filename has no redundant `issue-` prefix.
- [ ] Regression: `_unique_path` still suffixes `-2`/`-3` on collision;
      `status: pending` frontmatter still present; the source plan file
      is still unlinked after processing.
- [ ] The Codex path (`plan_to_issue_from_text`) is covered by the same
      shape check, not just the Claude Code `ExitPlanMode` path.

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
