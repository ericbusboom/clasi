---
id: '032'
title: Delete dead weight and a fast test loop
status: roadmap
branch: sprint/032-delete-dead-weight-and-a-fast-test-loop
worktree: false
use-cases: []
issues:
- retire-worktree-parallel-path.md
- installers-must-merge-not-overwrite.md
- clasi-init-reverts-this-repos-own-mcp-config-to-the-consumer-default.md
- test-system-improvements-real-app-coverage-from-the-e2e-a-leaner-faster-suite.md
- test-suite-predicate-registry-pollution.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 032: Delete dead weight and a fast test loop

## Goals

Shrink the codebase to what actually runs, stop the installers from
destroying user data, and turn the default developer test loop from
10-20 minutes into under a minute — without deleting coverage, and with
the developer driving every pruning decision. This sprint is Part 5's
**Phase 4 (Delete and decompose) and Phase 5 (A test suite you'll
actually run) combined**, from `docs/reviews/2026-08-reliability/00-review.md`.
Sprints 028-030 delivered Phases 0-2 (instrumentation, fail-closed
guards, one-truth state); sprint 031 covers Phase 3 (honest process,
leaner flow); this is the final sprint of the two-sprint closing arc and
completes the reliability campaign.

## Problem

Three independent problems, each with file:line evidence in the review:

1. **Dead code that stays referenced isn't inert.** About 550 of
   `worktree.py`'s 1,035 lines implement a parallel-execution lifecycle
   that has never run — no MCP tool exposes it, every real sprint
   (022-030) carries `worktree: false` — yet `execution.md` spends about
   175 lines instructing agents to drive it, and `close-sprint`'s skill
   text makes a claim about `acquire_execution_lock` creating worktrees
   that isn't true. An agent following the docs literally can only
   comply by improvising shell-outs. (`04-cli-install-platforms.md` F5
   and its deletion table; issue `retire-worktree-parallel-path.md`.)

2. **The installers overwrite instead of merging, and it's already bitten
   this repo.** Four destructive behaviors share one root cause: `clasi
   init` unconditionally rewrites `.mcp.json`'s `clasi` server entry
   (reverting this repo's own `uv run clasi mcp` dogfooding config to the
   consumer default on every init/migrate — observed 2026-07-16, silently
   pointed a session at a stale pipx build missing nine tools);
   `uninstall` deletes the whole CLAUDE.md instead of stripping CLASI's
   marker block; `init` replaces the entire hooks object, silently
   deleting user-defined hooks; and installing multiple platforms in
   sequence lets Codex/Copilot stomp the resolved Claude skill canonical.
   (`04-cli-install-platforms.md` F1-F4, F13; issues
   `installers-must-merge-not-overwrite.md` and
   `clasi-init-reverts-this-repos-own-mcp-config-to-the-consumer-default.md`
   — the second is the specific, previously-observed instance of the
   first's finding F1; they are closely related enough that ticketing may
   combine them into one ticket rather than fixing F1 twice.)

3. **The default test loop is slow for a reason nobody chose.** Measured
   across this campaign's own gate runs: 19m41s, 9m30s, 12m40s, 10m41s
   for a full suite run. `-m 'not slow'` is dead config — zero
   `@pytest.mark.slow` marks exist anywhere in `tests/`, so every
   invocation, including a single-test dev run, runs the full about-2,850-test
   suite. Coverage is welded into `addopts`, so that single-test run also
   pays for coverage collection and can trip the 84% `fail_under` gate on
   a partial run that was never meant to be a coverage gate.
   Separately, a real test-order-dependent bug exists: some unit-tier test
   clears the global predicate registry without repopulating it, so
   concatenating modules in a non-default order raises
   `UnknownPredicateError: Registered predicates: []`. (`05-e2e-test-infra.md`
   findings 8-11; issues
   `test-system-improvements-real-app-coverage-from-the-e2e-a-leaner-faster-suite.md`
   and `test-suite-predicate-registry-pollution.md`.)

## Solution

High-level shape, per Part 5 Phases 4-5 of the review:

- **Retire the worktree parallel path**: delete (or archive, per
  stakeholder call on that narrower question) the unreachable ~550-line
  lifecycle in `worktree.py`, its dead tests, and the Parallel Path
  sections of `execution.md`; keep the ~350-line reconcile/cleanup/audit
  core that `close_sprint` and `reconcile_worktrees` actually use intact;
  fix the `git worktree prune` vs re-`remove` bug while in the file;
  correct `close-sprint`'s inaccurate claim about
  `acquire_execution_lock`.
- **Fix the installers to merge, not overwrite**: `.mcp.json` leaves an
  existing `clasi` entry untouched; `uninstall` strips CLAUDE.md's marker
  block instead of deleting the file; hooks merge per event type; one
  shared canonical-skill writer removes install-order dependence;
  `_create_rules` compares before writing; `clasi migrate` refreshes only
  installed platforms. A regression test proves this repo's own `uv run`
  config survives `clasi init`.
- **Build the coverage harness and activate the fast/slow split** (the
  automatable half of the test-system issue): install the local tree
  editable under coverage in the e2e container, wire
  `COVERAGE_PROCESS_START`/`.coveragerc`, combine + report on the host,
  fix the `[tool.coverage.paths]` remap and the stale `role_guard.py`
  omit; mark the real-FS/real-git/subprocess test tiers `@pytest.mark.slow`;
  unweld coverage from default `addopts` into an explicit gate invocation;
  add `just test` (fast) / `just test-all` (slow + coverage) recipes; the
  e2e-running agent writes a textual dead-code report from combined
  coverage — the report is the deliverable, nothing is deleted
  automatically.
- **Fix the predicate-registry pollution bug**: find the test that clears
  the registry without restoring it, fix via fixture teardown or an
  autouse re-register, and add a shuffled/reversed collection-order check
  so this class of pollution is caught instead of rediscovered.
- **Immediate low-risk cleanup**: delete the empty `tests/dev/`,
  `tests/proj/` placeholder directories; relocate `tests/asr/` fixtures.
- **Explicitly out of this sprint's automation**: converting the dead-code
  report into removal issues, and thinning duplicated test tiers
  (`clasr` dupes, the four-layer status tests, `test_artifact_tools.py`'s
  96 tests) — both stay strictly developer-triggered, per the issue's
  Part B. This sprint may still ticket those thinning passes if the
  developer requests them during detail planning, but must not plan them
  as automatic consequences of the coverage report.

## Success Criteria

- Default `pytest` / `just test` completes in under 60 seconds; `just
  test-all` (full suite + coverage) stays green and still satisfies the
  84% `fail_under` gate.
- Coverage collection is no longer in default `addopts` — a single-test
  run no longer risks tripping the coverage gate.
- `clasi init` in this repo leaves (or restores) the `uv run clasi mcp`
  form in `.mcp.json`; a scratch consumer project (no uv, no `[project]`
  table) still gets the bare `clasi` default. `clasi uninstall` on a repo
  with other-tool content in CLAUDE.md preserves that content.
- The unreachable worktree lifecycle is gone or archived (stakeholder's
  call on that narrower question, per the issue); `execution.md` no
  longer instructs agents to call functions with no MCP surface.
- The predicate-registry bug is fixed; the suite passes under a
  deliberately shuffled/reversed module collection order.
- The e2e coverage harness runs end-to-end and the e2e-running agent
  produces a dead-code report from real combined coverage — and the
  sprint's own tickets make zero code deletions based on that report's
  contents; only the harness, the marking, the addopts change, and the
  `just` recipes are delivered as code changes here.

## Scope

### In Scope

The 5 issues claimed by this sprint:

- `retire-worktree-parallel-path.md` — delete/archive the unreachable
  worktree parallel-execution lifecycle (~1,700 lines including tests and
  docs); keep reconcile/cleanup/audit intact.
- `installers-must-merge-not-overwrite.md` — the four destructive
  installer behaviors (F1-F4, F13): `.mcp.json` overwrite, CLAUDE.md
  deletion on uninstall, hooks clobber, multi-platform skill stomping,
  `_create_rules` docstring mismatch.
- `clasi-init-reverts-this-repos-own-mcp-config-to-the-consumer-default.md`
  — the specific, previously-observed instance of the `.mcp.json`
  finding above; closely related enough to
  `installers-must-merge-not-overwrite.md` that detail planning may
  combine them into a single ticket rather than duplicate the fix.
- `test-system-improvements-real-app-coverage-from-the-e2e-a-leaner-faster-suite.md`
  — Part A (coverage harness, automated dead-code report) and Part C
  (slow-marker activation, unweld coverage from `addopts`, `just` recipes,
  `clasr` test dedup, delete empty test dirs) are in scope. Part B
  (report → issue → sprint) is explicitly developer-triggered and stays
  out of this sprint's automated work.
- `test-suite-predicate-registry-pollution.md` — fix the registry-leak
  bug and add an order-shuffle regression check.

### Out of Scope

Phases 0-3 of the campaign (instrumentation, fail-closed guards,
one-truth state, honest process/leaner flow) are already delivered by
sprints 028-031. Automated conversion of the dead-code report into
removal issues or sprints (Part B of the test-system issue) is
permanently out of scope for automation — that stays a developer-only
action regardless of which sprint is current. The Codex/Copilot adapter
and clasi/clasr fork questions from the review's Part 6 are out of scope
until the stakeholder decides — see "Stakeholder Decisions Needed" below;
detail planning must not assume an answer.

## Stakeholder Decisions Needed

Two decisions from the review's Part 6 are unresolved and materially
change this sprint's deletion scope. Detail planning cannot proceed on
the parts they touch until the team-lead has put these to the
stakeholder and recorded an answer:

1. **Codex/Copilot adapters** (`src/clasi/platforms/codex.py`,
   `copilot.py` + their tests — 1,126 source lines, 1,762 test lines,
   never dogfooded, carrying live bugs per finding F4). Keep as-is,
   archive to a branch until there's a real consumer, or fix and keep?
   The review's recommendation is archive; this sprint does not act on
   that recommendation without stakeholder sign-off.
2. **The clasi/clasr fork** (`src/clasi/platforms/` 2,531 lines vs
   `src/clasr/` 2,432 lines, two complete platform-adapter stacks with
   incompatible marker/uninstall models — finding F7). Freeze clasr and
   archive it out of the repo (loses the manifest-based uninstall model,
   faster), or port `clasi init` onto clasr's manifest engine (better end
   state, but clasr's Codex output is broken and needs work first per F9)?
   The review's recommendation is freeze-and-archive now; this sprint
   does not act on that recommendation without stakeholder sign-off.

Note: this is distinct from the smaller, already-decided question inside
`retire-worktree-parallel-path.md` (delete vs. archive the ~550 dead
worktree lines) — that decision is scoped to a single ticket's acceptance
criteria and does not block ticketing the rest of this sprint. The two
decisions above are the ones that determine whether entire tickets
(Codex/Copilot removal, clasr consolidation/archival) exist at all, so
they block finalizing this sprint's ticket scope, not just one ticket's
detail.

## Test Strategy

(Describe the overall testing approach for this sprint: what types of tests,
what areas need coverage, any integration or system-level testing needed.)

## Architecture

(Architecture for this sprint's change, sized to the change — a
one-paragraph note for a trivial sprint, a fuller write-up with
component/data-model detail for a substantial one. May read "N/A —
trivial" when the change has no architectural impact.)

### Architecture Overview

(High-level structure and component relationships, if applicable.)

### Design Rationale

(Significant decisions with alternatives considered and reasoning, if
applicable.)

### Migration Concerns

(Data migration, backward compatibility, deployment sequencing — or
"None" if not applicable.)

## Use Cases

(Use cases sized to the change — may read "N/A — trivial" for small
sprints that don't warrant new or updated use cases.)

### SUC-001: (Title)
Parent: UC-XXX

- **Actor**: (Who)
- **Preconditions**: (What must be true before)
- **Main Flow**:
  1. (Step)
- **Postconditions**: (What is true after)
- **Acceptance Criteria**:
  - [ ] (Criterion)

## GitHub Issues

(GitHub issues linked to this sprint's tickets. Format: `owner/repo#N`.)

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [ ] Sprint planning document is complete (sprint.md, including its
      Architecture and Use Cases sections)
- [ ] Architecture review passed (or skipped, for changes with no
      architectural impact)
- [ ] Stakeholder has approved the sprint plan

## Tickets

| # | Title | Depends On |
|---|-------|------------|

Tickets execute serially in the order listed.
