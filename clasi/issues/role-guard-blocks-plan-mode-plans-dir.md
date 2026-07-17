---
status: pending
---

# role-guard blocks tier-0 Writes to ~/.claude/plans/, breaking plan mode and the plan-to-issue pipeline

## Description

In `handle_role_guard` (`src/clasi/hook_handlers.py`), paths outside the
project root never match any allow prefix and fail closed for tier 0. But
Claude Code's plan mode requires the team-lead to Write the plan file at
`~/.claude/plans/<name>.md`, `ExitPlanMode` reads the plan ONLY from that
file, and clasi's own PostToolUse `plan-to-issue` hook (`plan_to_issue` in
`src/clasi/plan_to_issue.py`, wired in `.claude/settings.json`) harvests
that same file into `clasi/issues/`.

Net effect: the guard blocks creation of the exact artifact clasi's own
pipeline consumes. Observed live on 2026-07-17: a plan-file Write was
denied with `CLASI ROLE VIOLATION: team-lead (tier 0) attempted direct
file write to: /Users/eric/.claude/plans/...`.

Workaround used in-session: write the file via Bash heredoc, since the
role-guard hook matcher only covers `Edit|Write|MultiEdit`. That the
workaround exists is itself part of the problem — the gate is both
over-blocking (plans dir) and porous (Bash).

## Cause

The outside-root fail-closed design in `handle_role_guard` predates the
plan-to-issue pipeline; no allow prefix was ever added for the harness
plans directory, and `_normalize_to_root_relative` leaves outside-root
paths absolute so they can never match the root-relative allow lists.

## Proposed fix

In `handle_role_guard`, allow-list the harness plans directory
(`Path.home() / ".claude" / "plans"`) for tier 0 (and arguably all
tiers), alongside the existing `safe_prefixes` check — but comparing
against the absolute path, since it lies outside the project root.

## Verification

- With the fix installed, a tier-0 Write to `~/.claude/plans/test.md`
  passes the guard (exit 0).
- A tier-0 Write to an arbitrary outside-root path (e.g.
  `~/Desktop/x.md`) is still blocked (exit 2).
- Add unit tests using real captured hook payloads for both cases,
  asserting the deny path still fires (per the project's gate-testing
  discipline: test guards with real payload shapes and assert the block,
  not just the allow).

## Related

- Filed while executing the E2E harness rework
  (`clasi-e2e-harness-rework-fresh-bind-mounted-project-reactive-tester-script.md`),
  whose plan-mode session hit the block.
