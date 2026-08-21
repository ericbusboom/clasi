---
id: '032'
title: Delete dead weight and a fast test loop
status: ticketing
branch: sprint/032-delete-dead-weight-and-a-fast-test-loop
worktree: false
use-cases: []
issues:
- retire-worktree-parallel-path.md
- installers-must-merge-not-overwrite.md
- clasi-init-reverts-this-repos-own-mcp-config-to-the-consumer-default.md
- test-system-improvements-real-app-coverage-from-the-e2e-a-leaner-faster-suite.md
- test-suite-predicate-registry-pollution.md
- close-sprint-timeout-orphans-the-test-process.md
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

The 6 issues claimed by this sprint, plus the two now-resolved Part 6
archival decisions (see "Stakeholder Decisions Needed" below):

- `retire-worktree-parallel-path.md` — delete the unreachable worktree
  parallel-execution lifecycle (~1,700 lines including tests and docs);
  keep reconcile/cleanup/audit intact. Detail planning resolves the
  ticket-scoped delete-vs-archive sub-question as **delete** (Design
  Rationale below) — the review's own Phase 4 plan and top structural
  recommendation both say "delete," and the module's own docstring
  already documents parallel execution as deliberately, not
  provisionally, disabled.
- `installers-must-merge-not-overwrite.md` — the four destructive
  installer behaviors (F1-F4, F13): `.mcp.json` overwrite, CLAUDE.md
  deletion on uninstall, hooks clobber, multi-platform skill stomping,
  `_create_rules` docstring mismatch. F4 (multi-platform skill stomping)
  is scoped down by the Codex/Copilot archival decision below — see
  ticket 004's notes.
- `clasi-init-reverts-this-repos-own-mcp-config-to-the-consumer-default.md`
  — the specific, previously-observed instance of the `.mcp.json`
  finding above; combined into the same ticket as
  `installers-must-merge-not-overwrite.md` rather than duplicating the
  fix (see ticket 004).
- `test-system-improvements-real-app-coverage-from-the-e2e-a-leaner-faster-suite.md`
  — Part A (coverage harness, automated dead-code report) and Part C
  (slow-marker activation, unweld coverage from `addopts`, `just`
  recipes, delete empty test dirs, relocate `tests/asr/`) are in scope.
  Part C's originally-scoped "dedupe clasr" item is superseded by the
  clasr archival decision below — archiving the whole tree removes the
  duplication outright, so no separate dedup pass is ticketed. Part B
  (report → issue → sprint) remains explicitly developer-triggered and
  stays out of this sprint's automated work.
- `test-suite-predicate-registry-pollution.md` — fix the registry-leak
  bug and add an order-shuffle regression check.
- `close-sprint-timeout-orphans-the-test-process.md` — process-group
  kill on test-command timeout; rework `test_close_sprint_worktrees.py`'s
  mocking so no unit test can spawn a real pytest subprocess.
- **Codex/Copilot adapter archival** (Part 6 decision 2, now answered —
  see below): remove `src/clasi/platforms/codex.py`, `copilot.py` and
  their tests from master, preserved on a branch.
- **clasi/clasr fork resolution** (Part 6 decision 1, now answered — see
  below): freeze `src/clasr/` and archive it out of this repo onto its
  own branch; `src/clasi/platforms` is authoritative going forward.

### Out of Scope

Phases 0-3 of the campaign (instrumentation, fail-closed guards,
one-truth state, honest process/leaner flow) are already delivered by
sprints 028-031. Automated conversion of the dead-code report into
removal issues or sprints (Part B of the test-system issue) is
permanently out of scope for automation — that stays a developer-only
action regardless of which sprint is current. Thinning the four-layer
status tests and `test_artifact_tools.py`'s 96 tests (also Part B-style,
coverage-report-driven) stays out of this sprint — the developer has not
requested it during this detail-planning pass. Porting clasr's
manifest-based uninstall model into `clasi.platforms` (the option the
freeze-and-archive decision below explicitly gives up) is out of scope
here — recorded as a follow-up issue instead (see Design Rationale).

## Stakeholder Decisions Needed

**Both decisions below were open when this sprint was written in
Roadmap Mode; Eric answered both on 2026-08-21, before this Detail Mode
pass began.** Recorded verbatim for the record, then folded into Scope
above and into ticket 001/002's acceptance criteria — detail planning
does not re-litigate either one:

1. **Codex/Copilot adapters** (`src/clasi/platforms/codex.py`,
   `copilot.py` + their tests — 1,126 source lines, 1,762 test lines,
   never dogfooded, carrying live bugs per finding F4). **Decided:
   archive to a branch.** Removed from master; preserved on a branch so
   they are recoverable if multi-platform becomes real. Rationale
   (Eric): never dogfooded, reachable only via explicit `--codex`/
   `--copilot` flags, and carry the live F4 bug where running the Codex
   installer after Claude overwrites Claude's resolved skill bodies.
2. **The clasi/clasr fork** (`src/clasi/platforms/` 2,531 lines vs
   `src/clasr/` 2,432 lines, two complete platform-adapter stacks with
   incompatible marker/uninstall models — finding F7). **Decided:
   freeze clasr and archive it out.** `src/clasi/platforms` is
   authoritative; clasr moves to its own branch/repo, ending the
   two-tree-change tax. Rationale (Eric): this knowingly gives up
   clasr's manifest-based uninstall model, which is better than
   clasi's name-based one — recorded as a tradeoff, with a follow-up
   issue filed to consider porting manifest-based uninstall into clasi
   later (see Design Rationale below).

Note: this is distinct from the smaller, already-decided question inside
`retire-worktree-parallel-path.md` (delete vs. archive the ~550 dead
worktree lines) — that decision is scoped to ticket 003's acceptance
criteria (resolved above as **delete**) and never blocked ticketing the
rest of this sprint.

## Test Strategy

No new product surface is added — every ticket in this sprint either
deletes code, fixes a merge/process bug, or builds test infrastructure —
so the testing approach is: (1) each ticket runs its own scoped test
subset in the foreground per `.claude/rules/source-code.md`, targeting
the modules it touches; (2) three tickets (003 worktree, 004 installers,
005 predicate-registry) each add or fix a *regression* test that encodes
the specific failure mode from their issue (worktree-flag-absent
execution path, this-repo's-own-`.mcp.json`-survives-init, shuffled
module-collection-order); (3) ticket 007's coverage harness is validated
by an actual on-demand e2e run producing `.coverage.*` files and a
combined report — not by a unit test, since it is Docker/e2e
infrastructure; (4) ticket 008's speed work is validated by timing
`pytest`/`just test` before and after; (5) the sprint's one full-suite
run, owned by `close_sprint` per sprint 031's flow, is the final gate —
it must stay green, and `just test-all` must still satisfy the 84%
`fail_under` coverage gate after coverage moves out of default
`addopts`. No ticket in this sprint deletes a test based on coverage
data; the human-in-the-loop constraint on Part B applies throughout.

## Architecture

**Substantial** — eight tickets touching at least nine distinct areas
(`worktree.py` + `execution.md` + the close-sprint skill's two
git-tracked copies; `platforms/claude.py` + `init_command.py` +
`migrate_command.py`; `platforms/codex.py`/`copilot.py` plus roughly a
dozen dependent files across `cli.py`, `hook_handlers.py`,
`plan_to_issue.py`, `skill_resolve.py`, `platforms/detect.py`,
`_rules.py`, `_markers.py`, `_links.py`, `__init__.py`, and their unit
tests; `src/clasr/` and `tests/clasr/` in their entirety; the
`state_machine` predicate-registry test fixtures; `close.py` +
`test_close_sprint_worktrees.py`; `tests/e2e/Dockerfile` +
`entrypoint.sh` + `pyproject.toml`'s coverage tables; `pyproject.toml`'s
`addopts`/`markers` + a new `justfile` recipe set + slow-marking across
`tests/system/`, `tests/integration/`, and heavy `tests/unit/` fixtures)
— module count alone clears the substantial-tier bar several times
over. Two tickets (001, 002) also remove a cross-module dependency
outright rather than changing one: `cli.py`/`init_command.py` currently
depend on `clasi.platforms.codex`/`.copilot`, and the package ships
`src/clasr` as a second, complete platform-adapter stack alongside
`src/clasi/platforms` — both dependencies are deleted, not refactored.
No dependency-direction change anywhere, and no data-model change: no
ticket adds a SQLite column, and the one frontmatter-shaped change (the
sprint `worktree:` flag) is a field being retired/documented-inert, not
a new or restructured one — the same shape sprints 030 and 031 each
used to justify skipping an entity-relationship diagram, and for the
same reason here.

### 1. Understand the Problem

This is the closing sprint of the reliability campaign
(`docs/reviews/2026-08-reliability/00-review.md`), covering Part 5's
Phase 4 (Delete and decompose) and Phase 5 (A test suite you'll
actually run). Sprints 028-031 already delivered instrumentation,
fail-closed guards, one-truth state, and the gate-order/tier-0 process
fixes; this sprint spends the stability those bought on the campaign's
highest-volume, lowest-risk-per-line work: deleting code and
documentation that no longer describes anything real, fixing four
installer behaviors that overwrite instead of merge, and unwelding the
test suite's speed from a coverage gate that was never meant to run on
every invocation.

Three independent problems (see sprint.md's own Problem section above
for the full narrative and file:line evidence):

1. Dead code stays *referenced* — `worktree.py`'s unreachable parallel
   lifecycle, `execution.md`'s Parallel Path instructions, and the
   close-sprint skill's inaccurate `acquire_execution_lock` claim are
   three descriptions of one thing that isn't true.
2. Four installer behaviors share one root cause — write-wholesale
   instead of merge-or-compare — and one of the four has already caused
   a real incident in this repo (the 2026-07-16 stale-pipx session).
3. The test suite is slow for a reason nobody chose (dead `slow`-marker
   config, coverage welded into `addopts`) and has one real latent bug
   (predicate-registry pollution across module collection order).

Two additional decisions, unresolved when this sprint was written in
Roadmap Mode, were answered by the stakeholder before this Detail Mode
pass began (see "Stakeholder Decisions Needed" above) and are folded in
as first-class scope: archive Codex/Copilot to a branch, and freeze
and archive `clasr` to its own branch. Both are deletions of an entire
existing module tree, not new work — they extend problem 1's shape
("dead or near-dead code that keeps costing maintenance") to two more
subsystems the review's Part 6 had flagged but left for a stakeholder
call.

Verified against the live codebase during this planning pass (not
assumed from the issue text alone): `worktree.py` is 1,042 lines (the
issue's "1,035" is close enough to be the same measurement at a
slightly different commit); `reconcile_worktrees`, `cleanup_worktree`,
`write_audit_record`, and `read_audit_record` are the only worktree.py
symbols called from `close.py`/`artifact_tools.py`; `check_independence`
has zero callers outside `worktree.py` itself and its own tests;
`_create_rules`'s docstring already claims "compares content before
writing and skips unchanged files" while its body unconditionally
writes every rule file with no comparison, confirming F13 exactly;
`claude.py`'s uninstall path calls `_links.unlink_alias(target /
"CLAUDE.md")` for CLAUDE.md but `strip_section(target / "AGENTS.md")`
two lines later, confirming F2's asymmetry exactly; the predicate-registry
pollution traces to three `_clean_registry` autouse fixtures
(`tests/unit/test_state_machine/test_registry.py`, `test_evaluator.py`,
`test_predicates.py`) whose teardown calls a bare `clear_registry()`
with nothing to re-populate it for whichever test module runs next in
the same process; `tests/asr/`'s own `justfile` and `README.md` confirm
it is `clasr`-only demonstration fixture data (a `clasr install
--provider ... --claude --codex --copilot` demo), consumed by no
current test, and not the general-purpose fixture the review's Part C
bullet assumed it might be.

### 2. Identify Responsibilities

Ten responsibilities, each changing for an independent reason, mapped
onto this sprint's eight tickets (three of them combine two or three
closely-related responsibilities that share one root cause or one
"make the docs and the code agree" story — noted below):

1. **Shrink the platform-adapter surface to what's dogfooded** —
   changes because Codex/Copilot were never a real second consumer, not
   because Claude's adapter itself is wrong. (Ticket 001)
2. **End the clasi/clasr fork** — changes because two complete
   platform-adapter stacks is a standing "fix everything twice" tax, not
   because either implementation is individually broken. (Ticket 002)
3. **Shrink `worktree.py` to only what's live** — changes because the
   parallel-execution half was deliberately, not provisionally,
   abandoned. (Ticket 003, part A)
4. **Make `execution.md` describe one path** — changes because the
   Parallel Path prose is instructions for functions that responsibility
   3 deletes. (Ticket 003, part B — same ticket as 3, since the doc
   change and the code change must land atomically or the spec
   re-orphans the code, exactly the failure this ticket exists to
   prevent)
5. **Correct the close-sprint skill's worktree claim** — changes because
   it currently asserts something `acquire_execution_lock` doesn't do;
   folded into ticket 003 because it's the same "make the doc match
   reality" story as 3/4, just in a different file.
6. **Installer config merge semantics** — `.mcp.json`, CLAUDE.md
   uninstall, hooks, `_create_rules`, and `clasi migrate`'s
   platform-refresh scope all change for the same reason (overwrite →
   merge/compare), not five independent reasons. (Ticket 004)
7. **Test-suite tiering (fast default, full gate on demand)** — changes
   because the `slow` marker was specified but never activated, not
   because any individual test is wrong. (Ticket 008)
8. **Predicate-registry test isolation** — changes because three test
   files' teardown behavior is order-dependent, not because the
   production registry itself has a bug. (Ticket 005)
9. **`close_sprint` subprocess robustness** — changes because a timeout
   kills the wrong process in the tree, not because the test-running
   logic itself is wrong. (Ticket 006)
10. **Real-application coverage measurement** — changes because nothing
    today measures what the e2e run actually exercises in `src/clasi`,
    not because the e2e harness itself is broken. (Ticket 007)

### 3. Define Subsystems and Modules

For each ticket, the module(s) touched, purpose (one sentence, no
"and"), boundary, and use cases served:

- **Ticket 001 — Codex/Copilot archival.** Touches
  `src/clasi/platforms/{codex,copilot}.py`, `cli.py`, `init_command.py`,
  `uninstall_command.py`, `platforms/detect.py`, `plan_to_issue.py`,
  `hook_handlers.py`'s `codex-plan-to-issue`/`codex-plan-to-todo` hook
  subcommands, and roughly a dozen dependent unit tests. Purpose:
  remove the never-dogfooded second and third platform adapters from
  master's live surface. Boundary: `platforms/claude.py` and the shared
  leaf utilities (`_links.py`, `_markers.py`, `_rules.py`) are
  untouched in content — only Codex/Copilot-specific branches and CLI
  flags are removed. Serves SUC-007.
- **Ticket 002 — clasr archival.** Touches `src/clasr/` (entire),
  `tests/clasr/` (entire), `tests/asr/` (entire — see Step 1's finding
  that it is clasr-only fixture data), and `pyproject.toml`'s
  `clasr` script entry, `packages.find` include, and coverage
  source/addopts references. Purpose: remove the second,
  independently-maintained platform-adapter stack from master. Boundary:
  nothing in `src/clasi` imports `clasr` today (verified), so this is a
  pure subtraction with no import-graph repair needed inside
  `src/clasi` itself. Serves SUC-007.
- **Ticket 003 — Worktree parallel-path retirement.** Touches
  `worktree.py` (delete `create_worktree`, `create_ticket_branch`,
  `validate_worktree`, `merge_ticket_branch` — lines 48-295 — and
  `check_independence` plus its seven parsing/topo-sort helpers — lines
  743-1042 — roughly 548 of 1,042 lines total, matching the issue's
  estimate), `schemas/se-process/instructions/execution.md` (delete the
  `## Parallel Path` section, lines 55-230, and simplify `§0. Mode
  Selection`), `src/clasi/plugin/skills/close-sprint/SKILL.md` **and**
  `.agents/skills/close-sprint/SKILL.md` (both git-tracked copies — see
  this sprint's layer-trap note), `docs/design/worktree-process.md`
  (retire, not delete — see Design Rationale), `templates/sprint.md`
  (drop the `worktree:` field from the template for new sprints), and
  `tests/clasi/test_worktree.py` +
  `tests/system/test_worktree_and_planning_integration.py` (trim to
  match). Purpose: make the code and the docs agree that only
  reconcile/cleanup/audit is live. Boundary: `reconcile_worktrees`,
  `cleanup_worktree`, `write_audit_record`, `read_audit_record`, and
  their two live parsing helpers (`_parse_ticket_worktrees`,
  `_ticket_id_from_branch`) are untouched. Serves SUC-002.
- **Ticket 004 — Installer merge-not-overwrite.** Touches
  `init_command.py`'s `_detect_mcp_command`/`_update_mcp_json`,
  `platforms/claude.py`'s uninstall path (CLAUDE.md), install path
  (hooks merge, `_create_rules`), and `migrate_command.py`'s
  `run_migrate`. Purpose: replace five write-wholesale call sites with
  merge-or-compare. Boundary: this ticket does not touch
  `platforms/codex.py`/`copilot.py` at all — depends on ticket 001, see
  Design Rationale for why F4's original three-way shared-writer
  requirement is dropped. Serves SUC-001.
- **Ticket 005 — Predicate-registry isolation.** Touches
  `tests/unit/test_state_machine/{test_registry,test_evaluator,
  test_predicates}.py`'s `_clean_registry` fixtures (and/or a shared
  `conftest.py` fixture, implementer's choice), plus a new
  shuffled/reversed-order regression check. Purpose: make registry
  teardown restore what it found, not leave it empty for the next
  module. Boundary: `state_machine/registry.py`'s production code is
  untouched — this is a test-isolation-only fix. Serves SUC-004.
- **Ticket 006 — close_sprint subprocess robustness.** Touches
  `close.py`'s `_run_test_command`, and
  `tests/unit/test_close_sprint_worktrees.py`'s `@patch("subprocess.run")`
  mocking (reworked to match whatever invocation mechanism the fix
  uses). Purpose: a timed-out or aborted test run leaves no surviving
  process in its process tree. Boundary: `close.py`'s other nine steps
  are untouched. Serves SUC-005.
- **Ticket 007 — E2E coverage harness.** Touches `tests/e2e/Dockerfile`,
  `entrypoint.sh`, a new combine/report script (extending `validate.sh`
  or a new `coverage.sh`), and `pyproject.toml`'s `[tool.coverage.paths]`
  (new) and `[tool.coverage.run].omit` (drop the stale `role_guard.py`
  entry). Purpose: make the occasional e2e run measure real
  `src/clasi` coverage and produce a textual dead-code report. Boundary:
  this ticket makes zero code deletions from that report's findings —
  see the Human-in-the-Loop constraint in Design Rationale. Depends on
  ticket 002 (the `.coveragerc` `source=` list drops `clasr`, since it
  no longer exists in the tree this ticket instruments). Serves SUC-006.
- **Ticket 008 — Test-suite speed.** Touches `pyproject.toml`'s
  `addopts` (remove `--cov=...` flags from the default invocation),
  `justfile` (add `test`/`test-all` recipes), `@pytest.mark.slow`
  annotations across `tests/system/`, `tests/integration/`, and the
  heaviest `tests/unit/` fixture tests, and deletes `tests/dev/`,
  `tests/proj/`. Purpose: make the default developer loop fast without
  deleting any test. Boundary: does not touch `tests/clasr/`/`tests/asr/`
  (gone via ticket 002) or `tests/e2e/` (already excluded from
  collection). Depends on tickets 001 and 002 (fewer test files to
  audit for slow-marking once the archived platform tests are gone).
  Serves SUC-003.

### 4. Diagrams

**No component diagram.** Every change above is a deletion, an
archival, or an independent bugfix at an *existing* module boundary —
nothing new is composed, and the net effect on the dependency graph is
negative (two platform-adapter dependencies removed outright in tickets
001/002, one dead in-process lifecycle removed in ticket 003). A
diagram would only reproduce `docs/design/design.md`'s existing
Subsystem Map with a few boxes shrunk or erased; it would not show
anything the prose above and the overlay edits (this document's
companion `design/` files) don't already say directly. This is the same
reasoning sprint 020 used for the same shape of sprint (many independent
fixes across existing modules, no new composition).

No entity-relationship diagram (no data-model change) and no dependency
graph (no dependency-direction change; the two dependency removals are
straightforward subtractions with nothing to diagram).

### 5. What Changed / Why / Impact on Existing Components / Migration Concerns

**What Changed**: See Step 3 above for the full per-ticket module list.
At the system level: `src/clasi/platforms` loses two of its three
platform adapters; `src/clasr` and `tests/clasr` leave the tree
entirely; `worktree.py` shrinks from 1,042 to roughly 494 lines;
`execution.md` shrinks from 334 to roughly 160 lines with a single
execution path; four installer write sites become merge-or-compare;
`pyproject.toml`'s default `pytest` invocation drops coverage
collection; a new e2e-side coverage harness and dead-code-report
capability is added (net-new, not a replacement of anything).

**Why**: Per Step 1 — three independent problems (dead-but-referenced
code, overwrite-not-merge installers, an unchosen-slow test loop) plus
two now-decided archival questions, all converging on the same
underlying discipline: delete what nothing runs, and don't let
"something writes a file" stand in for "something merges into what's
already there."

**Impact on Existing Components**:
- `clasi.platforms` (co-located `DESIGN.md`): orientation changes from
  "three near-identical instantiations" to "Claude only, in master" —
  see this sprint's overlay edit to `src/clasi/platforms/DESIGN.md`.
- `clasi-core`'s `worktree.py` narrative in `docs/design/design.md`:
  updated from "currently unused" (implying provisional) to "retired;
  only reconcile/cleanup/audit remains live" — see this sprint's
  overlay edit to `design.md`.
- `clasi.tools` (`artifact_tools.py`, `close.py`): unaffected in
  contract — `reconcile_worktrees` and `close_sprint`'s worktree-pruning
  step call exactly the same surviving functions with exactly the same
  signatures; only the unreachable half of their callee module is gone.
- Every existing sprint's `sprint.md` frontmatter that still carries
  `worktree: false` (022-032) is left as-is — `Sprint.worktree` keeps
  reading the field and returning it (now permanently `False`/inert in
  practice), so no mass migration of 30+ historical sprint files is
  needed. Only the *template* for new sprints drops the field.
- `pyproject.toml`'s coverage `fail_under = 84` gate is unaffected in
  value — it moves from being paid on every `pytest` invocation to
  being paid only on the explicit `just test-all` / close-sprint gate
  invocation. Nothing about what counts as "covered" changes.

**Migration Concerns**: None requiring data migration — no SQLite
schema change, no frontmatter migration beyond the sprint template
noted above (existing sprint files are untouched). The two archival
tickets (001, 002) are the closest thing to a migration concern in this
sprint, and their concern is *recoverability*, not data integrity — see
Design Rationale for the archive-branch mechanics that make each
reversible.

### 6. Design Rationale

**Decision: delete (not archive) the dead half of `worktree.py`.**
- Context: the issue leaves delete-vs-archive as a ticket-scoped choice
  ("the stakeholder decides which, but the docs get cut either way").
- Alternatives considered: (a) archive to a branch, symmetric with the
  Codex/Copilot and clasr treatment; (b) delete outright.
- Why this choice: Codex/Copilot and clasr are archived because a real
  future consumer is plausible (multi-platform adoption, a manifest-
  uninstall port) and the stakeholder said so explicitly. The worktree
  parallel path has no such story — it was deliberately abandoned
  because worktrees accumulated in practice (see project memory), the
  module's own docstring already frames it as a settled decision rather
  than a pause, and the review's own Phase 4 plan and top structural
  recommendation both say "delete" without hedging. Git history is the
  recovery path if this is ever revisited — no branch bookkeeping is
  needed for code this unlikely to return.
- Consequences: if multi-worktree parallel execution is ever wanted
  again, it is reconstructed from git history (`git log -- worktree.py`
  at this sprint's tag) rather than checked out from a maintained
  branch. Recorded here so that choice is legible later, not just a
  fact about what happened to disappear.

**Decision: combine `installers-must-merge-not-overwrite.md` and
`clasi-init-reverts-this-repos-own-mcp-config-to-the-consumer-default.md`
into one ticket (004).**
- Context: both issues name the same function
  (`init_command._update_mcp_json`/`_detect_mcp_command`) and the same
  fix; the standalone issue is explicitly "the specific, previously-
  observed instance" of the combined issue's F1.
- Alternatives considered: two tickets, one per issue.
- Why this choice: fixing F1 once satisfies both issues' acceptance
  criteria — the standalone issue's own "Proposed fix" section
  recommends the dogfood-detection approach that the combined issue's
  F1 fix also implements. Two tickets would either duplicate the fix or
  create an artificial ordering dependency for no benefit.
- Consequences: one ticket's acceptance criteria must satisfy both
  issues' verification sections; `create_ticket` is called with both
  filenames in `issue=[...]` so both issues carry the same ticket
  back-reference.

**Decision: drop F4's three-way shared canonical-skill writer
requirement from ticket 004; do not build it.**
- Context: `installers-must-merge-not-overwrite.md`'s F4 acceptance
  criterion asks for "one shared canonical-skill writer used by all
  three installers... a test installs two platforms in both orders and
  asserts identical output."
- Alternatives considered: (a) build the three-way shared writer as
  specified, ordering ticket 004 independent of ticket 001; (b) sequence
  ticket 004 after ticket 001 and drop the multi-platform-order
  requirement, since only one installer remains.
- Why this choice: once Codex/Copilot are archived (ticket 001), there
  is no second platform installer left in master to stomp Claude's
  resolved skill canonical — F4's failure mode requires two installers
  writing the same file. Building a three-way abstraction for a
  scenario that can no longer occur in master is exactly the
  speculative-generality anti-pattern this campaign is trying to
  reduce, not add. Ticket 004 still fixes `_create_rules`'s
  compare-before-write gap (F13, independent of platform count).
- Consequences: if Codex/Copilot are ever un-archived, F4's shared-writer
  work becomes live again and should be ticketed at that time, not
  built speculatively now. Ticket 001's acceptance criteria note this
  explicitly so a future re-introduction has a pointer back here.

**Decision: `test-system...`'s Part C "dedupe clasr" item is superseded
by full clasr archival (ticket 002); no separate dedup ticket.**
- Context: Part C originally asked for a manual dedup of the roughly
  117 tests duplicated between `tests/unit/test_platform_*.py` and
  `tests/clasr/test_platform_*.py`, written before the clasr
  freeze-and-archive decision existed.
- Why this choice: archiving all of `tests/clasr/` removes those
  duplicates outright — a strict superset of what the dedup pass would
  have achieved, at lower risk (no need to distinguish "duplicate" from
  "clasr-unique" test-by-test, since the whole tree leaves together by
  stakeholder decision, not by a coverage-driven pruning judgment call
  that would have needed the developer's sign-off per the issue's
  human-in-the-loop constraint).
- Consequences: tests/unit/test_platform_codex.py and
  test_platform_copilot.py (which test `clasi`'s own now-archived
  adapters, not clasr's) are removed by ticket 001, not ticket 002 —
  the two archival tickets each clean up their own tier's tests.

**Decision: `tests/asr/` moves to the clasr archive branch (ticket 002),
not "relocated" within master (dropped from ticket 008/Part C).**
- Context: `05-e2e-test-infra.md` finding 11 recommended relocating
  `tests/asr/` under `tests/clasr/fixtures/` or `examples/`, written
  before the clasr archival decision existed.
- Why this choice: verified during this planning pass that `tests/asr/`
  is exclusively `clasr` demonstration fixture data (its own
  `justfile`'s `demo`/`demo-single` recipes shell out to `clasr
  install`/`clasr uninstall`; its `README.md` states its purpose is to
  "demonstrate `clasr` and exercise multi-tenant install behavior") and
  is consumed by no current automated test (`tests/clasr/conftest.py`'s
  `make_asr_dir` fixture generates its own synthetic `asr/` tree at
  test time and does not read the on-disk `tests/asr/` directory at
  all). Once clasr leaves the tree, nothing in master has any use for
  this directory; moving it anywhere inside master would just relocate
  dead weight instead of removing it.
- Consequences: ticket 008's scope (Part C) drops the "relocate
  tests/asr/" line item; ticket 002 absorbs it into its own deletion
  list instead.

**Decision: two separate coverage configs for the unit gate vs. the
e2e/real-app report (ticket 007).**
- Context: the issue itself flags this tension — the unit gate's
  `[tool.coverage.run].omit` currently excludes `cli.py`,
  `hook_handlers.py`, `mcp_server.py` (exactly the real-app code the
  e2e exercises), and the issue says these "may stay omitted in the
  unit gate if unit coverage of them is weak... don't omit [them] from
  the e2e/real-app report."
- Alternatives considered: (a) one shared `[tool.coverage.run]` table,
  toggling `omit` per invocation via a CLI flag; (b) a second,
  dedicated `.coveragerc` for the e2e container's coverage collection
  and its combine/report step, independent of `pyproject.toml`'s table.
- Why this choice: (b) avoids a footgun where changing the unit gate's
  omit list to serve the e2e report accidentally changes what the unit
  `fail_under` gate measures (or vice versa) — the two configs serve
  genuinely different audiences (this repo's own contributors running
  `just test-all`, versus an occasional e2e run measuring the *real
  application's* coverage). `[tool.coverage.paths]` (the container-path
  remap) belongs in the e2e-specific config since only the e2e's
  container path needs remapping.
- Consequences: ticket 007 ships a new `.coveragerc` (or equivalent)
  under `tests/e2e/`, not a change to `pyproject.toml`'s
  `[tool.coverage.run].omit` list's entry-point exclusions — only the
  stale `role_guard.py` entry (dead regardless of audience, since the
  file no longer exists) is dropped from the shared `pyproject.toml`
  table.

**Decision: archive-to-branch mechanics for tickets 001 and 002.**
- Context: "archive to a branch" needs to mean something concrete and
  independently verifiable before the deletion is safe to land.
- Mechanics (identical shape for both tickets): (1) before any deletion
  commit, create a branch at current `HEAD`
  (`archive/codex-copilot-adapters` for ticket 001,
  `archive/clasr` for ticket 002) with `git branch <name>`; (2) verify
  the branch by checking out a scratch worktree or `git show
  <branch>:<path>` for a handful of the files about to be deleted,
  confirming the content matches what's on `master` pre-deletion; (3)
  push the branch to `origin` so it survives a local-clone loss, not
  just a local ref (`git push origin <name>`); (4) only then proceed
  with the deletion commit on the sprint branch. This is a ticket-level
  git operation, not an MCP tool call — no CLASI tool creates or pushes
  arbitrary branches, so the ticket's implementation plan spells out
  the exact `git` commands rather than delegating to a tool.
- Open question flagged below on whether `close_sprint`'s own tag-push
  step is expected to also verify these archive branches are on
  `origin`, or whether that verification is solely the ticket's own
  acceptance-criteria responsibility.

**Decision: `docs/design/worktree-process.md` is retired in place, not
deleted, and not run through the `design/` overlay lifecycle.**
- Context: this doc is one of the "frozen project-level docs" `design.md`
  itself lists as coexisting alongside the co-located `DESIGN.md` set;
  it is also worktree.py's own module docstring's cited "Authoritative
  specification."
- Why this choice: deleting it would leave `worktree.py`'s pre-sprint
  docstring (before ticket 003 rewrites it) as the only historical
  pointer to where the design intent used to live, and it has genuine
  historical value (the independence-check algorithm and audit-format
  rationale it documents were real design work, now superseded rather
  than wrong). Retiring in place — a `status: draft` → `status:
  retired` frontmatter change plus a one-paragraph note at the top
  pointing at this sprint and the delete decision above — preserves
  that history without leaving an "authoritative" doc for deleted code
  (the exact RC-5 pattern this campaign exists to eliminate).
- Correction made during this planning pass: this doc was initially
  seeded through the `design/` overlay (bare-filename form) alongside
  `design.md`, but `validate_design`'s canonical-doc-set check
  (`clasi.design.validator._canonical_doc_paths`) only recognizes the
  system doc (`design.md`) and subsystem `DESIGN.md` files as valid
  overlay/apply targets — the other frozen project-level docs
  (`overview.md`, `specification.md`, `state-machines.md`,
  `usecases.md`, `worktree-process.md`) are deliberately excluded from
  that set, confirmed by running `validate_design`, which rejected the
  seeded manifest entry as "not a known canonical design doc," even
  though `seed_sprint_design_overlay`'s own docstring describes a
  bare-filename form for exactly this doc set. The overlay/apply
  lifecycle is therefore not the right mechanism for this doc; it was
  removed from the sprint's `design/` overlay (`_sources.json` updated
  to drop the entry, `worktree-process.md`/`.diff.md` deleted from the
  overlay dir) and re-scoped as a normal ticket-scoped docs edit
  instead — ticket 003 edits `docs/design/worktree-process.md` directly,
  the same way it edits `execution.md` and the close-sprint skill files,
  with the exact retirement text this planning pass drafted included in
  the ticket's implementation plan. Worth flagging for future sprints:
  seed-overlaying any of the four other frozen `docs/design/` files will
  hit the same rejection and should route through a direct edit from
  the start instead.

**Decision: file a follow-up issue for porting clasr's manifest-based
uninstall model into `clasi.platforms`, rather than scoping it into this
sprint.**
- Context: the stakeholder's own recorded rationale for freezing clasr
  says this is a real tradeoff worth revisiting, not a closed question.
- Why this choice: porting a manifest-based uninstall model is a
  substantial design change to `clasi.platforms`'s own uninstall
  contract (F14's fix direction) — it is out of this sprint's scope by
  the same reasoning that keeps Part B of the test-system issue
  developer-triggered: a real design decision deserves its own sprint,
  not a rider on an archival ticket. A `clasi/issues/` file (not a
  GitHub issue, matching this project's own issue-file convention)
  records the idea with a pointer to `clasr`'s archive branch so the
  design reference isn't lost.
- Consequences: this issue is filed as part of ticket 002's own
  acceptance criteria (see ticket 002), not as a separate planning step
  here.

**Decision (reaffirmed, not new): no automated conversion of the
coverage report into removal issues.**
- Context: repeated explicitly in the dispatch's constraints and
  already correctly scoped out of this sprint's Solution/Scope sections
  above; restated here because ticket 007 is the one ticket that
  produces the report and it would be easy for an implementer to
  over-scope it.
- Consequences: ticket 007's acceptance criteria explicitly state "the
  report is the deliverable; the ticket makes no code or test deletions
  from its contents" as a hard boundary, not a suggestion.

### 7. Open Questions

1. **Should the archive branches (`archive/codex-copilot-adapters`,
   `archive/clasr`) be pushed to `origin` as part of ticket
   001/002's own work, or does that wait for a human with push
   authority to confirm the destination remote?** This sprint's Design
   Rationale above assumes the ticket pushes them directly (same
   credentials the sprint branch itself pushes with), but if `origin`
   access differs from what the executing agent has, this needs a
   human step inserted before the deletion commit lands. Flagging for
   team-lead to confirm at execution time, not blocking ticket creation
   now, since it's readily checked (`git remote -v` degrees of
   freedom) at whichever point it turns out to matter.
2. **Does `clasi migrate`'s new "refresh only installed platforms"
   behavior (ticket 004, from F11) need a platform-detection helper
   that doesn't already exist**, or can it reuse `platforms/detect.py`'s
   existing signal-scoring as-is? Left to ticket 004's implementer to
   resolve by reading `detect.py` directly — not architecturally
   significant either way, since both paths stay inside the same
   module boundary.
3. **Exactly which `tests/unit/` fixture tests count as "heavy" for
   ticket 008's slow-marking pass** (beyond the clearly real-FS/
   real-git/subprocess ones) is left to that ticket's implementer to
   determine empirically (time each test file, mark the tail) rather
   than enumerated here — enumerating it now would require re-running
   the full suite with per-test timing, which is exactly the kind of
   measurement ticket 008 itself is supposed to produce as part of its
   own work, not a precondition for ticketing it.

## Use Cases

No numbered use case in `docs/design/usecases.md` (UC-001 through
UC-013) covers CLASI's own installer/test-infrastructure engineering —
those UCs describe how a stakeholder uses the SE process on *their*
project, not how CLASI's own codebase is kept reliable. This sprint
follows sprint 031's precedent of naming a `UC — Reliability / <Theme>`
parent for each SUC instead of a numbered UC.

### SUC-001: `clasi init`/`uninstall`/`migrate` merge instead of overwrite
Parent: UC — Reliability / Installer Integrity

- **Actor**: `clasi init`, `clasi uninstall`, `clasi migrate`, run
  against this repo (dogfooding) or any consumer repo
- **Preconditions**: A target repo already has a `.mcp.json` `clasi`
  server entry, CLAUDE.md content from another tool, or user-defined
  hooks in `.claude/settings.json`
- **Main Flow**:
  1. `clasi init` runs against this repo, whose `.mcp.json` carries the
     `uv run clasi mcp` dogfooding form
  2. `_detect_mcp_command`/`_update_mcp_json` recognize the existing
     entry (via dogfood detection or a "never overwrite a differing
     entry" rule) and leave it untouched
  3. A separate scratch consumer project with no `uv`/no `[project]`
     table runs `clasi init` and still receives the bare `clasi mcp`
     default
  4. `clasi uninstall --claude` runs against a repo whose CLAUDE.md has
     other-tool content outside CLASI's marker block; only the marker
     block is stripped
  5. A second `clasi init` on a repo with user-defined hooks in
     `.claude/settings.json` leaves those hooks present alongside
     CLASI's own
  6. `clasi migrate` on a Codex-only-installed repo does not also force
     an unrequested Claude install
- **Postconditions**: Every one of the four installer behaviors (F1-F4
  minus the archived F4 half, F13) merges or compares instead of
  overwriting; this repo's own `.mcp.json` survives repeated `clasi
  init`/`migrate` calls
- **Acceptance Criteria**:
  - [ ] A regression test runs `clasi init` against a checkout carrying
        the `uv run` `.mcp.json` form and asserts it survives
  - [ ] A regression test runs `clasi init` against a scratch project
        with no `uv`/no `[project]` table and asserts the bare `clasi`
        default is still produced
  - [ ] A regression test asserts `clasi uninstall` on a repo with
        other-tool CLAUDE.md content preserves that content
  - [ ] A regression test asserts user-defined hooks survive `clasi init`
  - [ ] `_create_rules` skips writing a rule file whose on-disk content
        already matches the canonical body
  - [ ] `clasi migrate` refreshes only currently-installed platforms

### SUC-002: One documented sprint-execution path, no dead worktree machinery
Parent: UC — Reliability / Process Docs

- **Actor**: Any agent (team-lead, sprint-planner, programmer) reading
  `execution.md` or the close-sprint skill during a normal sprint
- **Preconditions**: A sprint is in `executing` phase
- **Main Flow**:
  1. The agent reads `execution.md` and finds exactly one execution
     path described (no `worktree` flag branch, no reference to
     `create_worktree`/`check_independence`/functions with no MCP
     surface)
  2. The agent reads the close-sprint skill and finds an accurate
     description of what `close_sprint`'s worktree-pruning step and
     `acquire_execution_lock` actually do
  3. `close_sprint` still prunes any git worktrees left over from other
     tooling via `reconcile_worktrees`/`cleanup_worktree`, unaffected by
     the deletion
- **Postconditions**: No agent can be instructed by the docs to call a
  Python function with no MCP tool behind it; `worktree.py` contains
  only the reconcile/cleanup/audit core plus its two live parsing
  helpers
- **Acceptance Criteria**:
  - [ ] `create_worktree`, `create_ticket_branch`, `validate_worktree`,
        `merge_ticket_branch`, `check_independence`, and their seven
        now-orphaned parsing/topo-sort helpers are deleted from
        `worktree.py`
  - [ ] `execution.md`'s `## Parallel Path` section and the `worktree`-flag
        branch of `§0. Mode Selection` are removed
  - [ ] `src/clasi/plugin/skills/close-sprint/SKILL.md` **and**
        `.agents/skills/close-sprint/SKILL.md` (both git-tracked copies)
        no longer claim `acquire_execution_lock` creates one worktree
        per ticket
  - [ ] `docs/design/worktree-process.md`'s frontmatter `status:` moves
        from `draft` to `retired`, with a note pointing at this sprint
  - [ ] `templates/sprint.md` no longer includes a `worktree:` field in
        its frontmatter template
  - [ ] `worktree.py:351-360`'s already-deleted-worktree case uses `git
        worktree prune` instead of re-running `git worktree remove` and
        swallowing the error
  - [ ] `tests/clasi/test_worktree.py` and
        `tests/system/test_worktree_and_planning_integration.py` are
        trimmed to match; reconcile/audit tests remain green
  - [ ] The full suite passes with the deletion in place

### SUC-003: Sub-minute default developer test loop; full gate unchanged
Parent: UC — Reliability / Developer Loop

- **Actor**: Any developer (or agent) running `pytest`/`just test`
  during normal iteration
- **Preconditions**: None — this is the default invocation
- **Main Flow**:
  1. Developer runs `just test` (or bare `pytest`)
  2. Only the fast tier collects and runs — no coverage collection, no
     real-FS/real-git/subprocess tests
  3. The run completes in well under 60 seconds
  4. Later, developer or `close_sprint` runs `just test-all`
  5. The full suite (fast + slow) runs with coverage collection and
     still satisfies the 84% `fail_under` gate
- **Postconditions**: A single-test dev run can never trip the coverage
  gate, because coverage is no longer collected by default
- **Acceptance Criteria**:
  - [ ] `@pytest.mark.slow` is applied to the real-FS/real-git/subprocess
        tiers (most of `tests/system/`, `tests/integration/`, and the
        heaviest `tests/unit/` fixture tests)
  - [ ] `pyproject.toml`'s default `addopts` no longer includes `--cov=...`
        flags
  - [ ] `justfile` gains `test` (fast, no coverage) and `test-all`
        (`-m 'slow or not slow'` plus coverage) recipes
  - [ ] `tests/dev/` and `tests/proj/` (empty placeholders) are deleted
  - [ ] Timed: default `pytest`/`just test` completes in under 60
        seconds; `just test-all` stays green and still meets
        `fail_under = 84`

### SUC-004: The predicate registry survives any test-module collection order
Parent: UC — Reliability / Regression Coverage

- **Actor**: `pytest`, collecting `tests/unit/test_state_machine/` and
  `tests/integration/test_state_machine_smoke.py` in a non-default
  (shuffled or reversed) order
- **Preconditions**: A prior test module's `_clean_registry` autouse
  fixture has run and torn down
- **Main Flow**:
  1. `tests/unit/test_state_machine/test_registry.py` (or
     `test_evaluator.py`, or `test_predicates.py`) runs and tears down
  2. Its fixture restores the registry to what it held before that
     module ran (a snapshot/restore or an explicit re-import of the
     production predicate modules), instead of leaving it empty
  3. `tests/integration/test_state_machine_smoke.py` runs next in the
     same process and finds a fully-populated registry
- **Postconditions**: `UnknownPredicateError: Registered predicates: []`
  cannot occur as a consequence of test order, in any collection order
- **Acceptance Criteria**:
  - [ ] The three `_clean_registry` fixtures in `test_registry.py`,
        `test_evaluator.py`, and `test_predicates.py` restore real
        registrations on teardown rather than leaving the registry empty
  - [ ] A new check runs the suite (or the affected subset) under a
        deliberately shuffled or reversed module collection order and
        passes
  - [ ] The existing, order-independent test suite is unaffected

### SUC-005: A timed-out or aborted `close_sprint` test run leaves no orphaned process
Parent: UC — Reliability / Sprint Ceremony

- **Actor**: `close_sprint`'s test-running step, and whatever spawns
  underneath the configured test command (`uv run pytest`, `npm test`,
  etc.)
- **Preconditions**: The test command times out, or the MCP call itself
  is aborted client-side
- **Main Flow**:
  1. `close_sprint` starts the configured test command
  2. The command's wrapper (`uv run`, `npm`, ...) forks a grandchild
     that does the real work
  3. The timeout fires (or the client aborts the call)
  4. The entire process group — not just the direct child — is
     terminated
- **Postconditions**: No test-runner process survives past the timeout;
  `ps` shows nothing still consuming CPU for the aborted run
- **Acceptance Criteria**:
  - [ ] A timed-out test command that deliberately spawns a grandchild
        outliving its direct-child parent leaves no surviving process
        (verified with a command constructed for exactly this)
  - [ ] `tests/unit/test_close_sprint_worktrees.py`'s
        `@patch("subprocess.run")` mocking is reworked to match
        whatever invocation mechanism the fix uses, so no unit test can
        spawn a real `pytest` subprocess (the exact defect that let
        031-008's Popen attempt surface as a 32-minute-orphan hazard
        instead of a clean revert)
  - [ ] The existing 031/008 stdin-closed behavior
        (`stdin=subprocess.DEVNULL`) is preserved

### SUC-006: An on-demand e2e run measures real `src/clasi` coverage and writes a dead-code report
Parent: UC — Reliability / Test Evidence

- **Actor**: The developer (triggers the run) and the e2e-running agent
  (produces the report)
- **Preconditions**: Developer runs the e2e harness (`tests/e2e/start.sh`
  or equivalent) with coverage instrumentation wired in
- **Main Flow**:
  1. The container installs the local working tree editable, not the
     published package
  2. `COVERAGE_PROCESS_START`/`COVERAGE_FILE` are set so every `clasi`
     CLI invocation and the long-lived `clasi mcp` server emit
     `.coverage.*` parallel-mode files
  3. After the run, a combine/report step on the host produces a
     line/branch coverage report mapped back to `src/clasi` via
     `[tool.coverage.paths]`
  4. The e2e-running agent reads the combined coverage and writes a
     textual markdown report ranking never-executed `src/clasi` code
     with file:line and a short rationale per item
  5. The run makes zero code or test changes as a consequence of the
     report
- **Postconditions**: A `.coverage.*`-backed combined report exists for
  the run; no code has been deleted; the developer decides, separately
  and later, whether any of the report's findings become a removal
  issue
- **Acceptance Criteria**:
  - [ ] `.coverage.*` files exist after a run for both CLI invocations
        and the `clasi mcp` process
  - [ ] `coverage combine` + report renders `src/clasi` coverage
        including `cli.py`/`mcp_server.py`/`hook_handlers.py` (not
        omitted from the e2e/real-app report, per this sprint's
        two-config Design Rationale)
  - [ ] The stale `role_guard.py` entry is dropped from
        `pyproject.toml`'s `[tool.coverage.run].omit`
  - [ ] The dead-code report is a markdown file in the run's output
        directory, ranking likely-dead code with file:line and rationale
  - [ ] The ticket that builds this harness makes no code or test
        deletions from the report's contents — this is a hard
        acceptance boundary, not a suggestion

### SUC-007: Unused platform-adapter surface is archived, not merely deleted
Parent: UC — Reliability / Codebase Shrinkage

- **Actor**: A maintainer removing `src/clasi/platforms/{codex,copilot}.py`
  or all of `src/clasr`/`tests/clasr`/`tests/asr` from master
- **Preconditions**: Stakeholder has decided (recorded above, 2026-08-21)
  to archive both rather than keep or delete outright
- **Main Flow**:
  1. Before any deletion commit, a branch is cut at current `HEAD`
     preserving the full pre-deletion content
     (`archive/codex-copilot-adapters`, `archive/clasr`)
  2. The branch's content is verified against master pre-deletion (spot
     `git show <branch>:<path>` checks)
  3. The branch is pushed to `origin`
  4. Only then does the deletion commit land on the sprint branch
  5. `cli.py`'s `--codex`/`--copilot` flags and `pyproject.toml`'s
     `clasr` script entry/package inclusion/coverage references are
     removed alongside the source, so no dead CLI surface points at
     deleted code
- **Postconditions**: `master` no longer builds, tests, or ships
  Codex/Copilot or clasr; both are fully recoverable via `git checkout
  archive/<name>` without git-log archaeology; a follow-up issue records
  the manifest-based-uninstall-porting idea clasr's archival gives up
- **Acceptance Criteria**:
  - [ ] `archive/codex-copilot-adapters` and `archive/clasr` branches
        exist on `origin`, each containing the pre-deletion content of
        their respective trees
  - [ ] `src/clasi/platforms/codex.py`, `copilot.py`, and their unit
        tests are gone from master; `cli.py`'s `--codex`/`--copilot`
        flags and the Codex hook subcommands are removed or clearly
        error as unavailable
  - [ ] A consumer repo that already has Codex/Copilot content installed
        by a pre-archival `clasi` (from an earlier `clasi init --codex`)
        is not silently broken by this change: running `clasi
        init`/`uninstall` with no platform flag still succeeds against
        Claude-managed content, and passing `--codex`/`--copilot`
        explicitly produces a clear "not available in this build — see
        `archive/codex-copilot-adapters`" message rather than a stack
        trace or a silent no-op (added during architecture review —
        this is the one real backward-compatibility risk this ticket's
        original acceptance criteria didn't name explicitly)
  - [ ] `src/clasr/`, `tests/clasr/`, `tests/asr/` are gone from master;
        `pyproject.toml`'s `clasr` script entry, `packages.find`
        include, and coverage `source`/`addopts` references to
        `src/clasr` are removed
  - [ ] A `clasi/issues/` file records the manifest-based-uninstall
        porting idea, pointing at the `archive/clasr` branch
  - [ ] The full suite passes with both deletions in place

## GitHub Issues

None. All six of this sprint's issues are CLASI issue files
(`clasi/issues/`), not GitHub-tracked; none of the 8 tickets carries a
`github-issue:` frontmatter value.

## Definition of Ready

Note: this checklist predates sprint 031's gate-order fix, which moved
stakeholder approval to gate `acquire_execution_lock` rather than
ticket creation (the stakeholder-review phase was deleted; `create_ticket`
now gates on the recorded `architecture_review` result alone). The first
two items below are the actual preconditions this sprint's ticket
creation satisfied; the third remains a real precondition for
*executing* the sprint, just not for planning it.

- [x] Sprint planning document is complete (sprint.md, including its
      Architecture and Use Cases sections)
- [x] Architecture review passed (recorded `passed`, APPROVE WITH
      CHANGES applied inline before recording — see
      `record_gate_result` notes)
- [ ] Stakeholder has approved the sprint plan (pending — gates
      `acquire_execution_lock`, not ticket creation, per the current
      gate order; not yet sought as of this planning pass)

## Tickets

| # | Title | Depends On |
|---|-------|------------|
| 001 | Archive Codex/Copilot platform adapters to a branch; remove from master | — |
| 002 | Freeze and archive the clasr fork to its own branch | — |
| 003 | Retire the worktree parallel-execution path | — |
| 004 | Fix installers to merge, not overwrite (.mcp.json, CLAUDE.md, hooks, rules, migrate) | 001 |
| 005 | Fix predicate-registry test-order pollution | — |
| 006 | close_sprint's test timeout must kill the whole process group, not just the direct child | — |
| 007 | E2E coverage harness and dead-code report | 002 |
| 008 | Fast default test loop: activate slow marker, unweld coverage, add just recipes | 001, 002 |

Tickets execute serially in the order listed (this sprint carries
`worktree: false` — no parallel-worktree execution opt-in). The
dependency column is a hard ordering constraint for tickets 004, 007,
and 008 specifically (each ticket's own Process Notes repeats "do not
start before its dependency is done" as a stop-and-report condition,
not just a suggestion); tickets 001, 002, 003, 005, and 006 have no
cross-ticket dependency and could in principle execute in any relative
order, but the numbered/table order above is still the recommended
execution sequence for this serial sprint.
