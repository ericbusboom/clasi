---
id: 019
title: "Enforcement guards fail open \u2014 role-guard payload, tier resolution, ticket\
  \ gate, and status noise"
status: planning-docs
branch: sprint/019-enforcement-guards-fail-open-role-guard-payload-tier-resolution-ticket-gate-and-status-noise
use-cases: []
issues:
- enforcement-guards-fail-open-role-guard-payload-and-tier-resolution.md
- remove-leftover-architecture-update-018-transition-artifact.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 019: Enforcement guards fail open — role-guard payload, tier resolution, ticket gate, and status noise

## Goals

CLASI's enforcement guards currently fail OPEN — they permit everything
while logging success. Repair them so process rules are actually
enforced, and make guard failures loud instead of silent.

## Problem

Investigation of a process-bypass incident in a downstream project
(`radio-robot-elite` sprint 101: eight commits landed with the tracker
frozen at `roadmap`, no tickets moved, no lock acquired) found that every
guard meant to stop it was already installed and silently failing open.
This is a cluster of defects sharing one shape: a guard that cannot
resolve its input, and treats the unresolved case as ALLOW, while logging
a confident-looking success line. Full details, verified with commands
and live log/DB inspection:
`clasi/issues/enforcement-guards-fail-open-role-guard-payload-and-tier-resolution.md`.

Two smaller issues fold in because they are entangled with this repair:

- `e2e-001-review.md` item 7 (`done` vs `closed` terminology drift) — the
  direct cause of 18 bogus `state_drift` warnings that the status-block
  fix (defect 7) must eliminate anyway.
- `remove-leftover-architecture-update-018-transition-artifact.md` — a
  one-line stray-file deletion, folded in as housekeeping.

## Solution

Fix each of the 7 verified defects at its root cause, in dependency
order (payload fix unblocks meaningful testing of everything else):

1. `role-guard` reads `file_path` from the payload root instead of
   `payload["tool_input"]` — always exits `0 no-path` (allow). Fix the
   read path; make the no-path branch fail CLOSED for Edit/Write at
   tier 0/1 instead of allowing.
2. `StateDB.get_active_tier` runs `SELECT tier FROM active_agents LIMIT 1`
   with no `WHERE agent_id = ?` — returns an arbitrary agent's tier.
   Key the lookup on the calling agent; fail CLOSED on unresolvable tier.
   Purge stale rows with BOTH mechanisms, not either/or:
   `SubagentStop`-triggered unregister as the precise, immediate primary
   path, plus the existing `clear_stale_agents` TTL sweep (currently
   never called) as the backstop for agents that die without firing Stop
   — a crash/kill/timeout, which is exactly how the current ghosts
   accumulated. A purge relying solely on clean exit will silently
   re-accumulate; that is the failure being fixed. Call the TTL sweep
   from a cheap, frequently-hit path (e.g. `subagent-start`). Also drop
   the TTL well below the current 24h default — a 24-hour-old "active"
   agent is not a real thing. (Table is currently empty in this repo —
   ghosts were manually cleared during triage; do not write a test or
   migration that assumes stale rows are present.)
3. No gate checks ticket state at all. Add a ticket-state gate: block
   source writes when no ticket is `in-progress` and no OOP flag —
   applying to tier 2 as well (a programmer writing with no in-progress
   ticket is exactly the sprint-101 failure).
4. OOP flag is split-brain: guards check `.clasi-oop`, status-inject and
   docs promise `.clasi/oop`. Unify behind one `_oop_active()` helper:
   canonical `.clasi/oop`, accept legacy `.clasi-oop`.
5. `clasi init` stamps CLASI's own source layout (`src/clasi/**`,
   `src/clasr/**`) into `source-code.md`'s `paths:` — and Claude Code's
   rules engine has **no `exclude:` key and no negated globs** (verified
   against official docs). A rule only fires when Claude *reads a file
   matching one of its `paths:` patterns* — not on every tool use. So in
   any project without a `src/clasi/` or `src/clasr/` directory (i.e.
   every downstream project), `source-code.md` was not merely narrow, it
   was **unreachable**: it could never fire, for any file, ever. This is
   a third independent enforcement layer that was silently dead — same
   disease as defects 1-3, different layer. Fix: drop `paths:` from
   `source-code.md` entirely so it loads unconditionally at launch (same
   priority as CLAUDE.md), and state the path exclusions in prose in the
   rule body instead of trying to encode them as a glob. This rule is
   advisory backup to the hard block in defect 3's ticket gate, so
   always-loaded is an acceptable, cheap cost (see architecture-update.md
   Design Rationale).
5b. **NEW, same root cause, found while verifying defect 5**: two more of
   the five generated rules are unreachable or drifted in this very repo.
   `clasi-artifacts.md` is scoped to `.clasi/**`, but artifacts moved to
   visible `clasi/**` (no dot) in sprint 013 — `.clasi/` now holds only
   state files (config.yaml, log/, .clasi.db). The rule that says "use
   MCP tools, don't hand-edit sprint files" **never fires** on an edit to
   `clasi/sprints/**`. `todo-dir.md` has the same bug in the *generator*
   (`platforms/claude.py:58` still emits `.clasi/issues/**`) but the
   on-disk copy in this repo has been hand-corrected to
   `clasi/issues/**` — generator and disk have silently diverged. Fix the
   generator for both rules; add a test that every generated rule's
   `paths:` (where present) matches at least one real path in a
   freshly-`init`'d project — the check that would have caught all three
   dead/drifted rules before they shipped.
6. The status block is 34KB on every prompt: includes all `done/`
   archives, drives 18 bogus `state_drift` warnings from the `done`/
   `closed` mismatch, never narrows (called without `sprint_id`/
   `ticket_id`), carries no imperative, and swallows all errors silently.
   Fix all of the above; target well under 5KB. ~~Also bulk-correct the 18
   existing `clasi/sprints/done/*/sprint.md` files from `status: done` to
   `status: closed`~~ — **cut during execution; only the
   `Sprint.archive()` writer was fixed.** The original reasoning follows,
   and was reversed: `done` is not a state the sprint machine defines,
   so leaving them keeps `detect_inconsistencies` permanently
   correct-but-ignored and is a landmine for any future code that reads
   archived sprint status. Mechanical, low-risk, one ticket.
7. Delete the stray `docs/architecture/architecture-update-018.md`
   transition artifact (sprint 018 predates the single-doc architecture
   model; `Sprint.archive()` no longer copies there).

**Verified NOT a regression** (checked so the payload fix doesn't unmask
a new bug): `handle_role_guard`'s allow-list (`_allow_prefixes`, built
from `Project.issues_dir` / `reflections_dir` / `design_dir` /
`clasi_dir` / `log_dir`) resolves live from `ARTIFACT_PATH_DEFAULTS`,
which already correctly point at `clasi/issues`, `clasi/reflections`,
`clasi/sprints` (no dot) — only `clasi_dir`/`log_dir` stay under `.clasi/`
by design (state anchor). Once the payload fix makes role-guard live for
the first time, team-lead is NOT newly blocked from writing legitimate
artifact dirs. The drift is confined to the two *generated rule files*
above (5b), which are advisory context, not the enforcement path.

The most important part of this sprint is the test strategy, not the
code fix — the reason a dead gate survived for months is that the test
fixture hand-built a payload shape that never occurs in production. See
Test Strategy below.

## Success Criteria

- `echo '{"tool_name":"Write","tool_input":{"file_path":"source/main.cpp"}}' | clasi hook role-guard` exits 2 (was 0).
- `clasi hook status-inject | wc -c` is under 5KB (was 34,467 bytes).
- `grep role-guard .clasi/log/hooks.log` shows reasons other than `no-path`.
- `touch .clasi/oop` bypasses guards; `touch .clasi-oop` (legacy) also bypasses; both verified independently.
- A programmer (tier 2) with zero in-progress tickets in an executing sprint is blocked from writing source; with a ticket in-progress, allowed.
- `clasi init` into a scratch repo with code under `source/` produces a `source-code.md` rule that demonstrably fires (loads unconditionally, no `paths:` key) and its prose names `source/` as in scope.
- `clasi-artifacts.md` and `todo-dir.md`, freshly generated by `clasi init`, have `paths:` values that match at least one real path in the initialized project (test added; catches future drift between generator and reality).
- ~~`grep -c "^status: done" clasi/sprints/done/*/sprint.md` returns 0 across all 18 archived sprints.~~ **CUT** — the bulk-correction was dropped mid-sprint by stakeholder decision (see ticket 007 and Design Rationale in `architecture-update.md`). The 18 archived files deliberately still declare `status: done`; that grep returning 18, not 0, is now the correct outcome. `Sprint.archive()` writes `closed` going forward.
- The new guard-deny tests fail when the line-140 payload fix is reverted (proves the tests actually exercise the fix, not just restate it).
- `docs/architecture/architecture-update-018.md` and the resulting empty `docs/architecture/` directory no longer exist.

## Scope

### In Scope

- All 7 defects in `enforcement-guards-fail-open-role-guard-payload-and-tier-resolution.md`.
- The rule-generator drift found while verifying defect 5: `source-code.md`
  (unreachable outside CLASI's own layout), `clasi-artifacts.md`
  (unreachable — scoped to `.clasi/**`, artifacts live at `clasi/**`), and
  `todo-dir.md`'s **generator** (`platforms/claude.py:58` /
  `copilot.py` still emit `.clasi/issues/**`; this repo's on-disk copy was
  hand-corrected to `clasi/issues/**` and the generator never caught up).
  All three fixed in `platforms/_rules.py` / `platforms/claude.py` /
  `platforms/copilot.py`, plus a test that every generated rule's
  `paths:` matches at least one real path in a freshly-initialized
  project.
- ~~Bulk-correcting the 18 existing `clasi/sprints/done/*/sprint.md` files
  from `status: done` to `status: closed`.~~ **CUT during execution** —
  see ticket 007. Only the `Sprint.archive()` writer was fixed; the
  archive is left as the historical record it is.
- `e2e-001-review.md` item 7 only (done/closed terminology drift).
- Deleting `docs/architecture/architecture-update-018.md`.
- Archiving `e2e-001-review.md` to `clasi/review/` (new, non-CLASI-tracked
  directory) and pruning it down to its two remaining live items (3 and 7),
  noting items 2/8 shipped in sprint 018 and items 5/6 are stale.
- Test suite rework for role-guard, tier resolution, ticket gate, OOP,
  rule-path reachability, and status-block size — this is sprint-critical,
  not incidental.

### Out of Scope

- `test-system-improvements-real-app-coverage-...` — its own future sprint.
- `e2e-001-review.md` item 3 (version-bump noise) — stays pending.
- The `commit-check` handler — a real issue, but it did not cause the
  sprint-101 incident (PostToolUse cannot block anyway).
- Re-deriving whether `todo-dir.md`'s on-disk `clasi/issues/**` path is
  itself correct — verified correct in this sprint (it matches
  `Project.issues_dir`'s live default); only the generator that produced
  the stale `.clasi/issues/**` value is in scope.

## Test Strategy

This is the most important part of the sprint:

- Replace `_role_guard_payload()` in `tests/unit/test_hook_handlers.py`
  (hand-builds a flat `{"file_path": ...}` payload that never occurs in
  production) with a real captured nested payload
  (`{"tool_name": ..., "tool_input": {"file_path": ...}}`), ideally sourced
  from an actual `.clasi/log/hooks.log` capture. No hand-built fixtures for
  guard input, ever again.
- Assert the DENY path explicitly: nested real payload + tier 0 + source
  path → exit 2. A guard whose block branch is never exercised end-to-end
  is untested.
- Ticket-gate tests: sprint executing + zero in-progress tickets + tier 2 +
  source write → exit 2; with a ticket in-progress → exit 0.
- Tier-resolution tests with CONCURRENT agent registrations (a single-agent
  test passes trivially — that is why this bug survived).
- OOP tests for both `.clasi/oop` and legacy `.clasi-oop`.
- Rule-reachability test: after a fresh `clasi init` into a scratch
  project, for every generated rule file that carries a `paths:` key,
  assert `paths:` matches at least one real path that exists in the
  initialized project. This is the check that would have caught
  `source-code.md`, `clasi-artifacts.md`, and `todo-dir.md`'s generator
  bug before any of them shipped — the single most valuable new test in
  this sprint, since it catches the *class* of defect, not just each
  instance.
- A size assertion on the REAL, unmocked status block (existing tests all
  mock `_build_status_block` and so never saw 34KB).
- Acceptance criterion, explicit and non-negotiable: the new deny tests
  MUST fail when the line-140 payload fix is reverted. A guard test that
  passes against the bug is worthless.

## Architecture Notes

No new modules or subsystems — this sprint repairs existing enforcement
components (`hook_handlers.py`, `state_db_class.py`, `platforms/claude.py`,
`platforms/copilot.py`, `platforms/_rules.py`, `status/reporter.py`,
`status/inconsistency.py`, `sprint.py`) in place. See
`architecture-update.md` for the fail-open → fail-closed policy change and
its component-level impact.

## GitHub Issues

(None — this sprint is sourced from local CLASI issue files, not GitHub issues.)

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [ ] Sprint planning documents are complete (sprint.md, use cases, architecture)
- [ ] Architecture review passed
- [ ] Stakeholder has approved the sprint plan

## Tickets

| # | Title | Depends On |
|---|-------|------------|
| 001 | Fix role-guard payload parsing and fail-closed no-path handling | — |
| 002 | Unify OOP bypass behind one `_oop_active()` helper | 001 |
| 003 | Fix tier resolution to key on caller identity, with dual-mechanism stale-agent purge | 001 |
| 004 | Add ticket-in-progress gate to role-guard (applies to tier 2) — **flips role-guard fully live for the first time; see ticket's bootstrap-risk note** | 001, 002, 003 |
| 005 | Fix unreachable/drifted rule paths and add rule-reachability test | 004 |
| 006 | Shrink and fix the per-prompt status block (exclude done/, real narrowing, imperative, logged errors) | 002, 004 |
| 007 | Fix Sprint.archive() done/closed terminology and bulk-correct 18 archived sprints | 004 |
| 008 | Delete stray docs/architecture/architecture-update-018.md | 004 |
| 009 | Archive and prune e2e-001-review.md to its live items | 007 |

Tickets execute serially in the order listed. Ticket 004 is the pivot
point: it is the ticket that, combined with ticket 001, makes
`role-guard`'s ticket-state gate fully enforcing against tier 2 for the
first time in this repo's history. Every ticket after 004 (005-009) runs
under that live gate — this is flagged explicitly in ticket 004 itself
so a programmer executing a later ticket recognizes an unexpected block
as the documented, expected consequence of 004 landing, not a new bug.
