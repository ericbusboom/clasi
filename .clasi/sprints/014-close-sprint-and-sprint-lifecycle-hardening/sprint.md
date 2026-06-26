---
id: '014'
title: close_sprint and sprint-lifecycle hardening
status: roadmap
branch: sprint/014-close-sprint-and-sprint-lifecycle-hardening
use-cases: []
issues:
- gh-13-close-sprint-mcp-tool-lacks-test-command-parameter-documented-but-not.md
- gh-14-cleanup-work-trees-after-sprint.md
- close-sprint-auto-detect-sprint-id-from-branch.md
- remove-finalize-sprint-alias.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 014: close_sprint and sprint-lifecycle hardening

## Goals

Round out `close_sprint` ergonomics and lifecycle completeness: expose the documented
`test_command` parameter, auto-detect `sprint_id` from the current git branch when
omitted, clean up git worktrees after a sprint closes, and remove the deprecated
`finalize_sprint` alias.

## Problem

Four related gaps in the sprint-close lifecycle:

1. **`test_command` not exposed.** The close-sprint skill documents `test_command` as a
   parameter (e.g., `"uv run pytest"` or `""` to skip), but the MCP tool's JSON schema
   does not expose it. Projects without a global `pytest` binary (uv-managed, no-test
   sprints) cannot close sprints via the MCP.
2. **`sprint_id` required when it's deterministic.** If the model omits `sprint_id`
   (empty-args bug or deliberate omission), validation fails. The sprint being closed is
   always deterministic from the current git branch (`sprint/NNN-slug` → `NNN`).
3. **Worktrees are never cleaned up.** Git worktrees created during sprint execution
   (one per ticket) are never removed, accumulating stale checkouts.
4. **`finalize_sprint` alias is obsolete.** Added in sprint 007 as a workaround for a
   suspected VS Code bug; sprint 011 fixed the actual root cause, making the alias dead
   weight.

## Solution

1. **Expose `test_command` parameter** in the `close_sprint` MCP tool schema with a
   default of `"pytest"` (current behavior) and support for `""` to skip tests or any
   custom runner string.
2. **Make `sprint_id` optional** in `close_sprint`: if `None` or empty, detect from
   `git branch --show-current` by parsing `sprint/NNN-*` → `NNN`; raise a clear error
   if not on a sprint branch.
3. **Clean up worktrees at close:** after merge, enumerate and prune all git worktrees
   associated with the closing sprint (any worktree whose branch matches `sprint/NNN-*`
   for the sprint being closed).
4. **Remove `finalize_sprint` alias:** delete the function from
   `clasi/tools/artifact_tools.py`, remove references in close skill docs and any alias
   tests from sprint 007. Preserve the `close_sprint` tool and sprint 011 exit-code-5
   behavior.

## Success Criteria

- `close_sprint(sprint_id="014", test_command="uv run pytest")` runs tests with uv.
- `close_sprint(sprint_id="014", test_command="")` skips tests and closes successfully.
- `close_sprint()` (no args) auto-detects sprint from current branch; fails with a clear
  error if not on a sprint branch.
- `finalize_sprint` no longer exists as an MCP tool.
- After `close_sprint`, `git worktree list` shows no worktrees for the closed sprint.
- `pytest -q` green with no regressions; existing sprint 011 exit-code-5 test passes.

## Scope

### In Scope

- `clasi/tools/artifact_tools.py` — `close_sprint` parameter changes, `finalize_sprint` removal, worktree cleanup
- MCP schema/server for `close_sprint` updated parameters
- `clasi/plugin/skills/close-sprint/SKILL.md` — remove `finalize_sprint` references, document new parameters
- Any `finalize_sprint` alias tests from sprint 007 (remove only the alias test, not the close behavior tests)

### Out of Scope

- Changes to sprint-planner or ticket lifecycle (covered in 012/013)
- `close_sprint` pre-review / post-close review gating (separate concern)

## Dependencies

After sprint 012. (Phase-gate checks need correct predicate paths before close-sprint
lifecycle can be reliably exercised end-to-end.)

## Issues Addressed

- `gh-13-close-sprint-mcp-tool-lacks-test-command-parameter-documented-but-not.md`
- `gh-14-cleanup-work-trees-after-sprint.md`
- `close-sprint-auto-detect-sprint-id-from-branch.md`
- `remove-finalize-sprint-alias.md`

## Architecture Notes

All four changes are contained within `close_sprint` and the MCP tool schema — no new
modules, no cross-cutting changes. The worktree cleanup step runs after merge to avoid
interfering with an in-flight execution. Auto-detection is a defensive convenience, not
a replacement for explicit `sprint_id` in normal operation.

## Tickets

| # | Title | Depends On |
|---|-------|------------|

Tickets execute serially in the order listed.
