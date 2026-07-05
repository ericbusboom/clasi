---
id: 009
title: Rewrite execution.md for flag-gated parallel execution with serial fallback
status: done
use-cases:
- SUC-001
- SUC-002
depends-on:
- '001'
- '006'
github-issue: ''
issue: plan-re-enable-git-worktree-based-parallel-ticket-execution-in-clasi.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Rewrite execution.md for flag-gated parallel execution with serial fallback

## Description

Issue A Chunk 4. Depends on ticket 001 (`Sprint.worktree` flag must
exist to read) and ticket 006 (the worktree.py functions this controller
prose calls must be real, not stubs, for the instructions to make sense
and for any accompanying smoke/doc tests to exercise real behavior).
This ticket does NOT depend on ticket 007 (`reconcile_worktrees`) or
ticket 010 (wiring the reaper in) — this ticket produces the mode
selection and grouping/dispatch/merge prose; ticket 010 layers the
reaper trigger points on top in a follow-up edit to the same file (kept
as a separate ticket per the issue's own chunk breakdown, so review is
tractable file-region by file-region).

Rewrite `src/clasi/schemas/se-process/instructions/execution.md` per the
issue's outline:

1. **Header**: replace the "strictly serial / no worktree usage" framing
   (currently lines 1-12) with: parallel worktree execution when the
   sprint's `worktree` frontmatter flag is `true`, else the existing
   serial path (preserved verbatim as fallback).
2. **§0 Mode selection**: read `Sprint.worktree` (or the equivalent
   surfaced field from `get_sprint_status`, per ticket 001) → branch to
   the parallel path or the serial path. The **entire existing §1-§5
   serial process must be preserved verbatim** as the fallback section —
   do not summarize or paraphrase it away; sprints without the flag must
   see byte-for-byte the same instructions they see today.
3. **Parallel preconditions** (adapts the spec's §2, substituting the
   frontmatter flag for the spec's sentinel file): phase is `executing`;
   execution lock held by this sprint (re-entrant, singleton preserved —
   state explicitly that this is NOT relaxed); no ticket is currently
   `in-progress`; `worktree: true`. Any failed precondition → serial
   fallback for the affected tickets (not a hard error).
4. **Grouping**: read all open tickets + their plan files; call
   `check_independence` (ticket 006) to produce ordered groups. Groups
   run serially; tickets within a group run in parallel.
5. **Per-group loop**: for each group — create a worktree + ticket
   branch + audit record + set ticket `in-progress` for every ticket in
   the group; dispatch one programmer agent per ticket **concurrently**
   (concurrent background Agent tool calls) into each ticket's worktree
   directory; wait for all dispatches in the group to return; then,
   **sequentially per ticket** (never concurrently — this is the
   single-HEAD merge serialization constraint): `validate_worktree`
   (retry re-dispatch up to 3 attempts on failure, else mark audit
   `failed`, `cleanup_worktree(keep_branch=True)`, and escalate) →
   `merge_ticket_branch` (on `MergeConflictError`: audit `conflict`,
   retain the worktree, escalate to the stakeholder with the conflicting
   files and worktree path; on success: audit `merged`,
   `move_ticket_to_done`, **immediately**
   `cleanup_worktree(keep_branch=False)`, audit `cleaned_up` — no
   deferral to sprint close). Advance to the next group only when the
   current group is fully merged/cleaned or explicitly escalated.
6. **Serial fallback**: the preserved current §3 (from step 2). Also
   explicitly used when `check_independence` returns all-singleton
   groups (no parallelism opportunity even with the flag on).
7. **Close**: invoke `close-sprint` as today; note that its safety net
   (ticket 008) is the final reconcile pass.
8. **Concurrency invariant callout**: explicitly state, near the top of
   the parallel section, that the execution lock remains a project-wide
   singleton (untouched by this sprint) and that ALL controller git
   operations (create/validate/merge/cleanup) run sequentially on the
   controller — only the programmer agents' implementation work runs
   concurrently. This must be unambiguous prose; it is the single most
   important invariant preventing this feature from becoming a
   concurrent-sprint-execution feature by accident.

Also update `src/clasi/plugin/skills/execute-sprint/SKILL.md`'s
description line to reflect "parallel when opted in" instead of the
current "strictly serial" framing.

The reaper trigger points (preflight sweep, per-creation gate) are
explicitly OUT of scope for this ticket — see ticket 010, which edits
this same file next and adds those sections without touching the mode
selection / grouping / per-group loop prose this ticket writes.

## Acceptance Criteria

- [x] `execution.md` no longer states "strictly serial" / "no worktree
      usage" as an unconditional rule; it now describes mode selection
      based on the `worktree` flag.
- [x] The existing serial process (current §1-§5) is preserved verbatim
      as the fallback path — diff the old and new files to confirm no
      unintended wording changes in the serial section.
- [x] The parallel path explicitly states the execution lock remains a
      singleton and that only programmer implementation work runs
      concurrently — all controller git operations are sequential.
- [x] The parallel path describes: preconditions, grouping via
      `check_independence`, concurrent per-group dispatch, sequential
      per-ticket validate→merge→cleanup, and per-group advancement gating.
- [x] Successful-merge cleanup is described as immediate (not deferred to
      sprint close).
- [x] `execute-sprint/SKILL.md`'s description line no longer says
      "strictly serial" unconditionally.
- [x] No mention of the reaper's preflight sweep or per-creation gate is
      added by this ticket (reserved for ticket 010) — keep the two
      tickets' diffs to this file non-overlapping in section scope.

## Completion Notes

- Verified via `diff` that the block from `### 1. Read Tickets` through
  the end of the file (§1-§5 plus `## Output`) is byte-for-byte
  identical between the old and new `execution.md` — confirmed with
  `diff` returning exit code 0 / no output on the extracted serial
  sections.
- Searched `tests/` for any convention of asserting required
  headings/sections *inside* se-process instruction `.md` files'
  content (as opposed to asserting the file exists or that a SKILL.md
  stub's `Load from:` directive points at it). No such convention
  exists: `test_skill_stub_loader.py`'s `_STUB_SKILLS` tuple carries an
  unused `heading_fragment` parametrize field that no test method
  actually asserts against instruction-file content, and no other test
  in `tests/unit`, `tests/clasi`, `tests/integration`, `tests/system`,
  or `tests/dev` checks instruction-file body headings. Per the
  ticket's testing guidance, no such test was invented speculatively.
  Ran the full `uv run pytest` suite instead to confirm no regressions.
- `tests/e2e/project/.agents/skills/execute-sprint/SKILL.md` is a
  standalone e2e fixture (not generated from source, not in this
  ticket's file list, not asserted against by any test) and was
  intentionally left untouched — it still describes the old
  strictly-serial behavior and will need its own update if/when the
  e2e fixture project adopts the flag, which is out of this ticket's
  scope.

## Files to create or modify

- `src/clasi/schemas/se-process/instructions/execution.md`
- `src/clasi/plugin/skills/execute-sprint/SKILL.md`

## Testing

- **Existing tests to run**: any test that asserts on the literal content
  of `execution.md` or `execute-sprint/SKILL.md` (grep `tests/` first),
  full `uv run pytest`.
- **New tests to write**: this ticket is primarily a documentation/
  instruction change with no importable code; if the repo has a
  convention for testing instruction-file content (e.g. asserting
  required headings/sections exist, as seen for other schema
  instructions), add an equivalent test for the new §0 Mode selection
  and parallel-path sections. If no such convention exists, note that in
  the ticket completion and do not invent one speculatively.
- **Verification command**: `uv run pytest`
