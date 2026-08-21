---
id: "008"
title: 'Fast default test loop: activate slow marker, unweld coverage, add just recipes'
status: open
use-cases: ["SUC-003"]
depends-on: ["001", "002"]
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

- [ ] `@pytest.mark.slow` is applied to the real-FS/real-git/subprocess
      tiers: most of `tests/system/`, most of `tests/integration/`, and
      the heaviest `tests/unit/` fixture tests (identify these
      empirically by timing — see Implementation Plan — not by
      guessing from directory name alone; some `tests/unit/` tests may
      be genuinely fast despite living in a directory with slow
      siblings, and some `tests/integration/` tests may already be
      fast enough not to need the mark).
- [ ] `pyproject.toml`'s default `addopts` no longer includes any
      `--cov=...`/`--cov-report=...` flag. The `-m 'not slow'` filter
      stays (now meaningful, since slow marks exist).
- [ ] `justfile` gains a `test` recipe (fast tier only, no coverage —
      effectively today's bare `pytest` invocation once slow-marking
      and the addopts change land) and a `test-all` recipe (`pytest -m
      'slow or not slow'` **plus** explicit `--cov=src/clasi
      --cov-report=term-missing --cov-report=lcov:lcov.info` — the
      coverage flags this ticket removed from default `addopts` move
      here instead of disappearing). Note: `--cov=src/clasr` is not
      part of `test-all`'s coverage flags either — ticket 002 has
      already removed `src/clasr` from the tree.
- [ ] `tests/dev/` and `tests/proj/` (verified empty placeholders — one
      file each, a `.gitkeep`/`.gitignore`) are deleted.
- [ ] Timed proof: default `pytest`/`just test` completes in under 60
      seconds (measure and record the actual number in this ticket's
      completion notes, not just "it felt fast"); `just test-all` stays
      green and still satisfies `fail_under = 84`.
- [ ] Full suite (`just test-all` or equivalent) passes.

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
