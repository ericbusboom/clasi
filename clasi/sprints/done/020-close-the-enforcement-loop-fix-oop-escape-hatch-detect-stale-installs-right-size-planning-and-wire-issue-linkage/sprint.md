---
id: '020'
title: 'Close the enforcement loop: fix OOP escape hatch, detect stale installs, right-size
  planning, and wire issue linkage'
status: closed
branch: sprint/020-close-the-enforcement-loop-fix-oop-escape-hatch-detect-stale-installs-right-size-planning-and-wire-issue-linkage
use-cases: []
issues:
- oop-bypass-broken-role-guard-blocks-team-lead.md
- issue-linkage-never-fires-all-sprints-empty.md
- sprint-planner-excessive-plans-for-simple-projects.md
- version-bump-noise-one-per-ticket-not-per-sprint.md
- mcp-server-runs-stale-pipx-build-not-the-working-tree.md
- detect-inconsistencies-drift-checks-terminal-archived-sprints.md
- issue-re-enable-the-mcp-process-content-tools.md
- plan-to-issue-hook-copies-plans-verbatim-producing-plan-shaped-issues.md
- create-ticket-auto-links-all-sprint-issues-to-every-ticket.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 020: Close the enforcement loop: fix OOP escape hatch, detect stale installs, right-size planning, and wire issue linkage

## Goals

Clear the 9-issue backlog from e2e run 003 and same-session findings. Two
threads dominate: (1) a live regression — the OOP escape hatch that sprint
019 was supposed to leave working — and (2) the mechanism that likely
*caused* that regression and silently voided sprint 019's verification: the
MCP server and hooks resolve to an 18-day-stale pipx build, not the working
tree.

**Planning-time finding, load-bearing for sequencing**: `_oop_active()`
already exists in the working tree (`src/clasi/hook_handlers.py:43`,
introduced in `019-002`) and is already correct — it checks `.clasi/oop`
then legacy `.clasi-oop`, exactly as issue 1 expects. But `which clasi`
resolves to pipx build `0.20260627.14` (pre-019, no `_oop_active`, no
ticket-gate, no fail-closed payload fix), while the working tree is
`0.20260715.3`. Every hook in `.claude/settings.json` invokes bare `clasi
hook ...`, and `.mcp.json` invokes bare `clasi mcp` — both hit the stale
build. **Issue 1 is very likely a symptom of issue 5, not an independent
logic bug.** Ticket 001 verifies this directly before writing any
`hook_handlers.py` fix, and ticket 002 (stale-install detection) is
sequenced immediately after so the rest of the sprint's own verification
can be trusted.

## Problem

Sprint 019 fixed the enforcement guards' fail-open behavior but shipped two
compounding gaps: the tool used to verify the fix (bare `clasi`, invoked by
every hook and by the MCP server) silently runs a stale build with no
detection, and the escape hatch meant to keep the guards from being a
one-way ratchet appears broken. Independently, four smaller process gaps
surfaced: issue linkage never fires despite existing tooling, sprint plans
are disproportionate to trivial projects (this plan included, hence
right-sizing it), a multi-issue sprint's ticket creation cross-links
unrelated issues, and the plan-to-issue hook produces plan-shaped, not
issue-shaped, files.

## Solution

Nine tickets, sequenced so foundation-and-regression work lands before
process-quality work, and so nothing later in the sprint has to trust an
unverified install:

1. Verify/fix the OOP bypass end-to-end against the actual invocation path
   (bare `clasi`, not `uv run clasi`), confirming or ruling out the
   stale-build hypothesis first.
2. Add stale-install detection (and this repo's own dogfooding fix) so
   every subsequent ticket's own verification is trustworthy.
3. Reconcile the version-bump-per-commit rule with the bump-noise
   complaint — these two issues are two views of the same tension and are
   fixed together.
4. Wire issue-to-sprint/ticket linkage into the skills/tools chain that
   already exists but is never invoked.
5. Fix `create_ticket`'s multi-issue auto-link default (hit directly while
   ticketing this very sprint, since it has 9 linked issues).
6. Right-size sprint-planner's plan output for small projects.
7. Reshape the plan-to-issue hook's output into issue format instead of
   verbatim plan copy.
8. Re-enable the 9 disabled MCP process-content tools (step 1 of that
   issue's staged plan only — not the discovery measurement, not the
   installer shrink).
9. Fix `detect_inconsistencies` to stop drift-checking terminal, archived
   sprints (low priority, no visible symptom, done last).

## Success Criteria

- A team-lead session with `.clasi/oop` set and the actual (non-stale)
  build installed can Write/Edit source directly; a captured real
  role-guard payload proves it, and a revert-check proves the fix (not a
  pre-existing pass) closes the gap.
- Starting the MCP server (or invoking a hook) against a deliberately
  stale install produces a visible, named-version warning; this repo's own
  `.mcp.json`/hook invocation is corrected so it runs the working tree.
- `git log` for a multi-ticket sprint shows at most one version-bump commit
  per sprint (or the reconciled policy this sprint lands on), consistent
  with what `.claude/rules/git-commits.md` now says.
- A test sprint linked to 2+ issues, planned with explicit `issue=` per
  ticket, produces correct bidirectional linkage end to end (sprint →
  issue → ticket → done).
- `create_ticket` on a multi-issue sprint without explicit `issue=` no
  longer cross-links every ticket to every issue.
- A trivial single-module sprint plan lands in the roughly 300-500 word
  range with no Mermaid diagram, not 1,300+.
- Exiting plan mode produces a `clasi/issues/*.md` file in house issue
  format (Description/Cause/Proposed fix/Verification/Related), no
  plan-mode scaffolding, no redundant `issue-` filename prefix.
- `clasi mcp` exposes the 9 re-enabled process-content tools;
  `test_no_unexpected_tools`/`test_tool_count` pass against the new count.
- `detect_inconsistencies` reports zero `state_drift` for archived/terminal
  sprints while still reporting genuine drift on non-terminal sprints.

## Scope

### In Scope

All 9 linked issues above.

### Out of Scope

- `clasi/issues/later/test-system-improvements-...md` — parked by the
  stakeholder, not part of this sprint.
- Issue 7's discovery-reliability measurement and any installer
  file-count shrink — explicitly gated behind that measurement per the
  issue's own staged plan; only step 1 (re-enable) is in scope here.
- Bulk-rewriting the 18 archived sprints' `status: done` frontmatter —
  explicitly rejected by the stakeholder during sprint 019 and not
  reopened here (issue 6 fixes the checker, not the data).
- The positive-list alternative for `source-code.md` rule scoping
  (mentioned as a live open item in the 019 architecture doc) — unrelated
  to this sprint's 9 issues, left for whenever it's actually needed.

## Test Strategy

House standards carried forward from sprint 019, restated because they
were repeatedly load-bearing there:

- Tests exercise the real code path, not mocks of the thing under test.
  Every 019 defect that shipped anyway did so because a test asserted the
  bug or mocked past it.
- Every guard/enforcement fix ships with a revert-check: the new test must
  fail when the fix is reverted. This caught two bad tests in 019.
- No hand-built fixtures that bypass real logic — use real captured
  payloads and real directory structures (e.g. a real role-guard PreToolUse
  payload, a real multi-issue sprint directory, not synthesized shapes).
- `uv run clasi` is the only trustworthy CLI check until ticket 002 lands;
  tickets before it must not verify against bare `clasi`. Tickets after it
  should additionally verify bare `clasi` now resolves correctly (or warns).

## Architecture Notes

No new subsystems. This sprint corrects behavior inside existing modules
(`hook_handlers.py`, `init_command.py`, `mcp_server.py`, `artifact_tools.py`,
`process_tools.py`, `status/inconsistency.py`, `plan_to_issue.py`, and the
sprint-planner/create-tickets skill docs) and adds one small new piece of
logic (staleness comparison at server/hook startup). See
`architecture-update.md` for the module-level detail — kept short
deliberately, per issue 3's own complaint about disproportionate planning
artifacts.

## GitHub Issues

(None linked yet.)

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [x] Sprint planning documents are complete (sprint.md, use cases, architecture)
- [x] Architecture review passed
- [x] Stakeholder has approved the sprint plan

## Tickets

| # | Title | Depends On |
|---|-------|------------|
| 001 | Verify OOP bypass against the real invocation path; fix only if the stale-build hypothesis is ruled out | (none) |
| 002 | Detect stale CLASI installs at MCP/hook startup; point this repo's own config at the editable install | 001 |
| 003 | Reconcile version-bump policy: fewer bumps without losing live-build signal | 002 |
| 004 | Wire issue-to-sprint/ticket linkage calls into planning skills so they actually fire | (none) |
| 005 | Fix create_ticket's multi-issue auto-link default | (none) |
| 006 | Right-size sprint-planner's plan output for small-scope sprints | (none) |
| 007 | Reshape plan-to-issue hook output into house issue format instead of verbatim plan copy | (none) |
| 008 | Re-enable the 9 disabled MCP process-content tools (step 1 only) | 002 |
| 009 | Skip drift-checking terminal/archived sprints in detect_inconsistencies | (none) |

Tickets execute serially in the order listed. Only 002, 003, and 008 have
real dependencies (on 001 and 002 respectively); 004, 005, 006, 007, and
009 are independent process-quality fixes and could in principle be
reordered or parallelized, but serial execution in the listed order keeps
the regression/staleness thread (001 to 002 to 003, 008) resolved before
the smaller process fixes, per the sprint's own sequencing guidance.
