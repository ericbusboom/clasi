---
id: 008
title: 'Fast default test loop: activate slow marker, unweld coverage, add just recipes'
status: done
use-cases:
- SUC-003
depends-on:
- '001'
- '002'
github-issue: ''
issue: test-system-improvements-real-app-coverage-from-the-e2e-a-leaner-faster-suite.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Fast default test loop: activate slow marker, unweld coverage, add just recipes

## Description

Part C of `test-system-improvements-real-app-coverage-from-the-e2e-a-leaner-faster-suite.md`
(minus the "dedupe clasr" item — superseded by ticket 002's full clasr
archival, see sprint.md's Design Rationale). Measured across this
campaign's own gate runs: 19m41s, 9m30s, 12m40s, 10m41s, 11m54s for a
full suite run. Verified during planning: `pyproject.toml`'s `addopts`
already has `-m 'not slow'`, and a `slow` marker is already registered
— but **zero** `@pytest.mark.slow` marks exist anywhere in `tests/`, so
that filter is dead config and every invocation, including a
single-test dev run, collects and runs the full roughly-2,850-test
suite. Coverage (`--cov=src/clasi --cov=src/clasr ...`) is welded into
`addopts` too, so that same single-test run pays for coverage
collection and can trip the 84% `fail_under` gate on a partial run that
was never meant to be a coverage gate.

**This ticket depends on tickets 001 and 002**: after their archivals,
there are fewer test files to audit for slow-marking
(`tests/unit/test_platform_codex.py`/`test_platform_copilot.py` and all
of `tests/clasr/`/`tests/asr/` are gone), and the `addopts` coverage
flags this ticket removes currently reference `src/clasr`
(`--cov=src/clasr`), which ticket 002 has already stopped shipping by
the time this ticket runs — auditing/removing that flag after 002 has
landed avoids editing a flag that points at a directory ticket 002 just
deleted.

**No test is deleted by this ticket.** Every currently-collected test
keeps running — under `just test-all`, not under the new default `just
test`/`pytest`.

## Acceptance Criteria

- [x] `@pytest.mark.slow` is applied to the real-FS/real-git/subprocess
      tiers: most of `tests/system/`, most of `tests/integration/`, and
      the heaviest `tests/unit/` fixture tests (identify these
      empirically by timing — see Implementation Plan — not by
      guessing from directory name alone; some `tests/unit/` tests may
      be genuinely fast despite living in a directory with slow
      siblings, and some `tests/integration/` tests may already be
      fast enough not to need the mark). **Empirical result diverged
      from the "most of tests/system/" prior**: a per-directory
      `--durations=0` audit found `tests/system/` (228 tests) already
      fast end-to-end (max single test 2.08s, whole dir 19.77s) — only
      2 tests there do genuine real-subprocess work
      (`TestCloseSprintTestTimeout`'s two `test_command="sleep 30"`
      tests) and got marked. `tests/integration/` was the real
      hotspot: `test_status_cli.py`/`test_status_e2e.py`/
      `test_status_mcp.py` averaged 9-23s/test (640s of the dir's
      650s) driving the real `.clasi/` status stack — marked whole-file.
      `tests/unit/` real-fs/real-git files/classes marked: full files
      `test_status/test_reader.py`, `test_design_overlay.py`,
      `test_gitutil.py`; classes/tests in `test_status/test_hook_injection.py`
      (`TestGitCallAndLoadMachineCountCollapse`,
      `TestGitSpawnCollapseInRealRepo`, `TestRealNarrowing`),
      `test_hook_handlers.py` (`TestRoleGuardRealCliInvocationPath`),
      `test_sprint.py` (`test_merge_branch_rebase_produces_linear_history`,
      `TestRealDoneArchiveBackwardCompat`), `test_migrate_command.py`
      (8 individual tests using `_init_git_repo`). Criterion applied:
      real git/filesystem/subprocess fixture use (isolation, per the
      ticket's own rationale), not just raw duration — a few tests
      under 300ms were marked anyway because they spin up a real repo
      or real CLI subprocess; conversely nothing in `tests/unit/` was
      marked on duration alone. 206 tests marked slow total (up from
      the 1 ticket 006 already added).
- [x] `pyproject.toml`'s default `addopts` no longer includes any
      `--cov=...`/`--cov-report=...` flag. The `-m 'not slow'` filter
      stays (now meaningful, since slow marks exist).
- [x] `justfile` gains a `test` recipe (fast tier only, no coverage —
      effectively today's bare `pytest` invocation once slow-marking
      and the addopts change land) and a `test-all` recipe (`pytest -m
      'slow or not slow'` **plus** explicit `--cov=src/clasi
      --cov-report=term-missing --cov-report=lcov:lcov.info` — the
      coverage flags this ticket removed from default `addopts` move
      here instead of disappearing). Note: `--cov=src/clasr` is not
      part of `test-all`'s coverage flags either — ticket 002 has
      already removed `src/clasr` from the tree.
- [x] `tests/dev/` and `tests/proj/` (verified empty placeholders — one
      file each, a `.gitkeep`/`.gitignore`) are deleted.
- [x] Timed proof: default `pytest`/`just test` completes in under 60
      seconds (measure and record the actual number in this ticket's
      completion notes, not just "it felt fast"); `just test-all` stays
      green and still satisfies `fail_under = 84`. **Measured**: `just
      test` = 44.80s pytest-reported / 47.51s real wall-clock (2607
      passed, 206 deselected). `just test-all` = 881.03s (14m41s)
      pytest-reported / 14m43s real wall-clock (2813 passed, 0 failed,
      coverage 89.99%, `fail_under = 84.0` satisfied).
- [x] Full suite (`just test-all` or equivalent) passes. 2813 passed,
      0 failed, 12 warnings — same total (2813) as collected before
      any change in this ticket, confirming no test was lost.

## Implementation Plan

### Approach

1. Confirm tickets 001 and 002 have landed before starting (fewer test
   files to audit; `--cov=src/clasr` already gone from the tree it
   would otherwise reference).
2. **Time the current suite per-file** to find the real slow tier
   empirically, rather than assuming "system + integration = slow,
   unit = fast" without checking:
   ```
   uv run pytest --durations=0 -q > /tmp/durations.txt
   ```
   (or per-directory timing if a single run is impractical). Mark
   everything above a reasonable threshold (a few hundred ms per test,
   or any test doing real filesystem/git/subprocess work regardless of
   raw duration, since those are the ones this fix is really about —
   isolation, not just speed) `@pytest.mark.slow`. This can be applied
   file-by-file via `pytestmark = [pytest.mark.slow]` at module level
   for files that are entirely slow, or per-test for mixed files.
3. Remove the `--cov=...`/`--cov-report=...` flags from
   `pyproject.toml`'s `addopts`.
4. Add `justfile`'s `test`/`test-all` recipes, moving the removed
   coverage flags into `test-all`.
5. Delete `tests/dev/`, `tests/proj/`.
6. Time the result: run bare `pytest`/`just test` and record the
   wall-clock; run `just test-all` and confirm it's still green and
   still meets `fail_under = 84`.

### Files to Modify

- `pyproject.toml` (`addopts`, and marking is per-test-file so this
  file doesn't itself carry the marks, but its `markers` list already
  documents `slow` — verify the docstring there stays accurate)
- Every file identified by the durations audit as needing
  `@pytest.mark.slow` — expect this to be dozens of files across
  `tests/system/`, `tests/integration/`, and some of `tests/unit/`;
  this is the bulk of this ticket's line-count, even though it's
  mechanically simple (add a mark, don't change test logic)
- `justfile`
- Delete: `tests/dev/`, `tests/proj/`

### Testing Plan

- **Existing tests to run**: this ticket's own verification *is* running
  the suite, twice — once fast (`just test`) and once full
  (`just test-all`) — timed both times. There's no smaller scoped
  subset that proves this ticket's marking work is correct; the whole
  point is suite-wide default-invocation behavior.
- **New tests to write**: none — this ticket adds marks and config, it
  doesn't add new test logic.
- **Verification command**: `time uv run pytest` (must be under 60s)
  and `time uv run pytest -m 'slow or not slow' --cov=src/clasi
  --cov-report=term-missing` (must stay green, `fail_under = 84` met).

### Documentation Updates

- If a `README.md`/`CONTRIBUTING.md` documents the current bare
  `pytest` invocation as "the way to run tests," update it to mention
  `just test`/`just test-all`. Check for one; this planning pass did
  not find a top-level `CONTRIBUTING.md` but did not exhaustively
  search every doc for a "how to run tests" mention.

## Process Notes

- Guards fail closed. If a role-guard or mcp-guard block is hit while
  working this ticket, **STOP and report it** — do not route around it.
  Reporting a block is a successful outcome of this ticket's work, not
  a failure.
- Tier-2 (in-progress-ticket) write scope covers this ticket's own file
  under the locked sprint's `tickets/` tree, plus `tests/` and
  root-level `pyproject.toml`/`justfile` (verify tier clearance for
  root-level files not under `protected_paths: [src, tests]` — same
  caveat as ticket 007's).
- **Do not start this ticket before tickets 001 and 002 are `done`.**
  If you find yourself starting this ticket while either is still
  `open`/`in-progress`, stop and report to team-lead rather than
  proceeding out of dependency order.
- This ticket is the one that should trigger archival of
  `test-system-improvements-real-app-coverage-from-the-e2e-a-leaner-faster-suite.md`
  to `issues/done/` (its `completes_issue: true`, unlike ticket 007's
  `completes_issue: false`) — only move it to done once **both** this
  ticket and ticket 007 are complete, since the issue's Part A and Part
  C are split across them.

## Completion Notes

**close_sprint default reconciliation (the part most likely to be checked
closely).** Decision: **close_sprint's default command changes**, not the
gate invocation being made explicit at call sites. Concretely:

- `src/clasi/close.py`, `SprintCloser.run()`'s test-command resolution
  (`self.test_command is None` branch) no longer resolves to
  `["uv", "run", "pytest"]`. It now resolves to the exact same argv list
  as the `just test-all` recipe:
  `["uv", "run", "pytest", "-m", "slow or not slow", "--cov=src/clasi",
  "--cov-report=term-missing", "--cov-report=lcov:lcov.info"]`.
- Why this direction and not "make callers pass the full command
  explicitly": `close_sprint`'s own docstring and `close.md` both already
  document omitting `test_command` (or passing the `"NONE"` sentinel) as
  the normal, recommended path — rewiring every call site to pass an
  explicit long invocation would be a bigger, riskier, more error-prone
  change than fixing the one place that manufactures the default, and
  would reintroduce exactly the footgun this reconciliation is about:
  a stakeholder or agent typing `test_command="uv run pytest"` by hand
  (matching the *old* default) would now silently get the fast/no-coverage
  loop instead of the full gate. Changing the internal default keeps
  "omit test_command" == "the sprint's one full-suite gate" true, which is
  the property `test_one_full_suite_run_docs.py` (031/008) already
  enforces at the doc layer.
- Docs updated to match: `close_sprint`'s tool docstring
  (`src/clasi/tools/artifact_tools.py`) and
  `src/clasi/schemas/se-process/instructions/close.md` no longer claim the
  default is `uv run pytest` — both now state the default is the full
  suite with coverage, matching `just test-all` verbatim, and no longer
  show `test_command="uv run pytest"` as an example (that string, passed
  explicitly, now *would* hit the fast path — the docs must not model
  that as the recommended close_sprint call). `.agents/skills/close-sprint/SKILL.md`
  (the installed copy `resolve_skill_body()` generates from close.md) was
  regenerated from the edited source so it doesn't drift — verified via
  `tests/system/test_one_full_suite_run_docs.py::TestInstalledSkillCopiesAreInSync::test_close_sprint_in_sync`,
  which passed (10/10 in that file).
- Verified the gate still collects everything: the `just test-all` run
  reported below collected and ran all 2813 tests (same total as
  pre-change full collection), not the 2607 the fast loop collects.
- `justfile`'s `test-all` recipe carries a comment pointing back at
  `close.py`'s default and vice versa, so a future edit to one without
  the other is at least flagged in both places (a full mechanical
  guarantee — e.g. a test asserting the two literal strings match — was
  judged out of scope for this ticket; noting it here in case a follow-up
  wants to add one).

**Tiers marked slow and criterion.** Two criteria applied jointly: (1)
per-test/per-file timing via `uv run pytest --durations=0 -q --no-cov -m ''`,
run per top-level test directory; (2) real filesystem/git/subprocess
fixture use, marked regardless of raw duration (per the ticket's own
Implementation Plan step 2 — "isolation, not just speed"). Empirical
findings, which drove the actual marking and diverged from the ticket's
prior "most of tests/system/" assumption:

- `tests/unit/` (2402 tests): overall fast (43.37s), but three whole
  files are real-git/real-fs by construction and got module-level
  `pytestmark = [pytest.mark.slow]`: `test_status/test_reader.py` (real
  `git init` fixture per test, 10.92s of the file's own time),
  `test_design_overlay.py` (real git-anchored overlay lifecycle, 4.83s),
  `test_gitutil.py` (the git-subprocess helper's own test suite, 1.12s).
  Plus targeted class/test-level marks: `test_status/test_hook_injection.py`
  (`TestGitCallAndLoadMachineCountCollapse`, `TestGitSpawnCollapseInRealRepo`,
  `TestRealNarrowing` — real multi-sprint fixture/real git repo),
  `test_hook_handlers.py` (`TestRoleGuardRealCliInvocationPath` — real
  `clasi hook role-guard` CLI subprocess), `test_sprint.py`
  (`test_merge_branch_rebase_produces_linear_history` — real git rebase;
  `TestRealDoneArchiveBackwardCompat` — real scan of
  `clasi/sprints/done/001-017`), `test_migrate_command.py` (8 individual
  tests using the `_init_git_repo` real-git fixture, across
  `TestIsGitRepo`/`TestIsTracked`/`TestFindUntrackedSources`/
  `TestExecuteMovesPerformsMove`).
- `tests/integration/` (74 tests, 639.97s total): the real hotspot.
  `test_status_cli.py`, `test_status_e2e.py`, `test_status_mcp.py` (62
  tests) each run `clasi status`/`get_status()` against this repo's real,
  full-history `.clasi/` directory through the real reader/reporter/
  narrowing stack — 9-23s per test, ~640s of the directory's 650s.
  Marked whole-file. `test_state_machine_smoke.py` (fast, all under 5ms)
  and the already-slow-marked (032/006) `test_close_run_test_command_grandchild.py`
  were left as-is.
- `tests/system/` (228 tests, 19.77s total): came back almost entirely
  fast — the single biggest test was 2.08s. Only
  `TestCloseSprintTestTimeout`'s two tests that use a real
  `test_command="sleep 30"` subprocess to exercise genuine timeout
  behavior got marked; nothing else in the directory qualified by either
  criterion. This directly contradicts the acceptance criterion's "most
  of `tests/system/`" prior — the ticket's own Implementation Plan
  explicitly instructs trusting the empirical audit over that guess
  ("not by guessing from directory name alone"), so no additional
  `tests/system/` files were marked to force a "most of" outcome the
  data doesn't support.
- `tests/clasi/`, `tests/docs/` (109 tests, 4.78s total): left unmarked —
  small contribution, not material to the 60s budget.

206 tests carry `@pytest.mark.slow` after this ticket (up from the 1
ticket 006 already added); `-m 'slow or not slow'` still collects all
2813.

**Measured times.**
- Fast loop: `just test` → `2607 passed, 206 deselected in 44.80s`
  (pytest-reported); `47.512s` real wall-clock (`time` around the `just`
  invocation, includes `uv`/interpreter startup). Under the 60s bar.
- Full suite: `just test-all` → `2813 passed, 12 warnings in 881.03s
  (0:14:41)` (pytest-reported); `14m43.462s` real wall-clock. Coverage:
  `Required test coverage of 84.0% reached. Total coverage: 89.99%.`
  Both runs executed in the foreground and observed to completion this
  turn (the second one via a manual blocking `while kill -0 <pid>` wait
  after the harness's own 600s-per-call cap auto-backgrounded the
  `time just test-all` invocation partway through).

**Test counts proving nothing was lost.** Full collection before any
change in this ticket: `2812/2813 tests collected (1 deselected)` (the
one pre-existing 032/006 slow mark). Full collection after this ticket,
forcing every marker on: `uv run pytest -m 'slow or not slow'
--collect-only -q` → `2813 tests collected`. `just test-all`'s real run
confirms the same 2813 all pass. Default (`just test`) collection:
`2607/2813 tests collected (206 deselected)` — the 206 are exactly the
newly-slow-marked tests, all still reachable and run under `test-all`.

**Files touched beyond the ticket's listed "Files to Modify."** The
close_sprint reconciliation (above) required editing
`src/clasi/close.py` (the default resolution itself),
`src/clasi/tools/artifact_tools.py` (tool docstring), and
`src/clasi/schemas/se-process/instructions/close.md` +
`.agents/skills/close-sprint/SKILL.md` (installed copy, regenerated via
`resolve_skill_body`) — none of these were itemized in the ticket's
"Files to Modify" list, but the ticket's own goal section explicitly
asked for this reconciliation ("decide deliberately... and SAY what you
chose"), so it's treated as in-scope rather than a deviation. No other
files outside the ticket's scope were touched. `tests/dev/`/`tests/proj/`
deletion was checked against `src/clasi/plugin/instructions/testing.md`
(which documents a `tests/dev/` *workflow*, not the directory's
persistent existence) — that doc stays accurate since the directory is
recreated automatically the next time someone follows the workflow it
describes, so it was not touched. No `README.md`/`CONTRIBUTING.md`
mentions of the bare `pytest` invocation were found (no top-level
`CONTRIBUTING.md` exists; `README.md` has zero `pytest` mentions).

**Guard/process notes.** No role-guard or mcp-guard block was
encountered at any point in this ticket. `dotconfig version bump` was
not run (per instructions — `close_sprint` bumps once per sprint).
`move_ticket_to_done`/`update_ticket_status` were not called for this
ticket's own status transition — frontmatter `status: done` was set by
direct file edit per this ticket's own Process Notes and the dispatch
instructions, leaving the done-directory move to the team-lead.
