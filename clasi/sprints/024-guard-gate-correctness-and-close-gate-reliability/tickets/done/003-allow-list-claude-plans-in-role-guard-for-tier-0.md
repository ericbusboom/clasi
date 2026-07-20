---
id: '003'
title: Allow-list ~/.claude/plans/ in role-guard for tier 0
status: done
use-cases:
- SUC-003
depends-on: []
github-issue: ''
issue: role-guard-blocks-plan-mode-plans-dir.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Allow-list ~/.claude/plans/ in role-guard for tier 0

## Description

`handle_role_guard` fails closed on all tier-0 writes outside the project
root. This blocks Claude Code's own plan-mode plan file
(`~/.claude/plans/<name>.md`), which is the exact artifact clasi's own
`plan_to_issue` PostToolUse hook consumes to harvest plans into
`clasi/issues/`. Today, exiting plan mode as team-lead either fails the
guard or requires a Bash-heredoc workaround.

Fix: allow-list `~/.claude/plans/` for tier 0 specifically, via absolute-
path comparison against the raw incoming path — not the general
root-relative `safe_prefixes`/`allow_prefixes` machinery, since
`~/.claude/plans/` lies outside the project root and can't be expressed
relative to it. This must not become a general outside-root escape: only
this one absolute prefix is allow-listed, and every other outside-root
path stays blocked.

## Acceptance Criteria

- [x] A tier-0 Write to `~/.claude/plans/test.md` passes the guard (exit
      0).
- [x] A tier-0 Write to an arbitrary outside-root path (e.g.
      `~/Desktop/x.md`) is still blocked (exit 2) — confirming the
      allow-list is narrow and not a general outside-root escape.
- [x] Unit tests use real captured hook payloads (per this project's gate-
      testing discipline) for both the allow case and the deny case, not
      synthetic/minimal payload shapes.
- [x] The comparison is done against the raw incoming path from the hook
      payload, before `_normalize_to_root_relative` runs — since that
      normalization assumes a root-relative path and would not correctly
      handle an absolute outside-root path.
- [ ] Walking the full plan-mode-to-issue flow live (write plan file via
      `ExitPlanMode`, confirm `plan_to_issue` harvests it) produces no
      guard denial.
      NOTE: Not exercised live in this dispatch — only verified via unit
      tests (5 passing, TestRoleGuardClaudePlansDirAllowList). Live
      plan-mode-to-issue walkthrough remains outstanding.

## Implementation Plan

**Approach**: In `handle_role_guard` (`src/clasi/hook_handlers.py`), before
(or alongside) the existing root-relative `safe_prefixes`/`allow_prefixes`
check, add a check that compares the raw incoming path against
`Path.home() / ".claude" / "plans"` as an absolute-path prefix comparison.
If the incoming path resolves under that prefix, allow it for tier 0
regardless of the outside-root fail-closed default. This check must run
on the path as received (before any root-relative normalization), since
`_normalize_to_root_relative` is designed for paths that are expected to
be inside the project root and would mishandle or reject an absolute
outside-root path before the allow-list check ever got a chance to run.

**Files to modify**:
- `src/clasi/hook_handlers.py` — `handle_role_guard`, adding the
  plans-dir absolute-path allow-list check for tier 0.

**Testing plan**:
- New unit test, real captured hook payload shape, tier 0, path
  `~/.claude/plans/test.md` (or the equivalent absolute path form the real
  hook payload uses) → assert exit 0.
- New unit test, real captured hook payload shape, tier 0, path
  `~/Desktop/x.md` (or similar outside-root, non-allow-listed path) →
  assert exit 2 (confirms no general escape was opened).
- Existing role-guard tests for in-root tier-0 paths continue to pass
  unmodified (regression check that the new check is additive, not a
  replacement of the existing logic).
- Manual/live verification: enter plan mode, write a plan, exit plan mode,
  confirm no guard denial and confirm `plan_to_issue` still harvests the
  file as before.

**Documentation updates**:
- None required beyond the ticket and code comments — this is a narrow,
  self-explanatory guard fix with no operator-facing workflow change.
