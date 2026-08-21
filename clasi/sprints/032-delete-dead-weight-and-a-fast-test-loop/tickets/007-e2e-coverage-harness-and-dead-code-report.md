---
id: '007'
title: E2E coverage harness and dead-code report
status: open
use-cases: ["SUC-006"]
depends-on: ["002"]
github-issue: ''
issue: test-system-improvements-real-app-coverage-from-the-e2e-a-leaner-faster-suite.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# E2E coverage harness and dead-code report

## Description

Part A of `test-system-improvements-real-app-coverage-from-the-e2e-a-leaner-faster-suite.md`:
build the coverage-instrumentation harness for the occasional,
developer-triggered e2e run, so it measures real `src/clasi` coverage
(the `clasi` CLI and the long-lived `clasi mcp` server, both currently
excluded from any coverage signal) and produces a textual dead-code
report. **This ticket is explicitly human-in-the-loop on the output
side**: the e2e run is developer-triggered (not automated/CI'd, per the
issue's own confirmed decisions), and the report this ticket's harness
produces is a deliverable, not an action — this ticket makes **zero**
code or test deletions based on the report's contents. That boundary is
a hard acceptance criterion below, not a suggestion.

This ticket **depends on ticket 002** (clasr archival): the `.coveragerc`
`source =` list and the combine/report step should cover `src/clasi`
only, not `src/clasi,src/clasr` — by the time this ticket executes,
`src/clasr` no longer exists in the tree it's instrumenting.

**Two separate coverage configs, deliberately** (see sprint.md's Design
Rationale, "Decision: two separate coverage configs for the unit gate
vs. the e2e/real-app report"): the unit gate's `pyproject.toml`
`[tool.coverage.run].omit` currently excludes `cli.py`,
`hook_handlers.py`, `mcp_server.py` — exactly the real-app code the e2e
exercises — and the issue explicitly says these "may stay omitted in
the unit gate... don't omit [them] from the e2e/real-app report." This
ticket ships a **separate** `.coveragerc` (or equivalent config) under
`tests/e2e/` for the container's coverage collection and combine/report
step, rather than changing `pyproject.toml`'s own `[tool.coverage.run].omit`
list — the two configs serve genuinely different audiences (this repo's
contributors running `just test-all`, vs. an occasional e2e run
measuring the real application). The only shared-config change this
ticket makes to `pyproject.toml` is dropping the stale `role_guard.py`
entry from `[tool.coverage.run].omit` (the file no longer exists,
verified) — that's dead regardless of audience.

## Acceptance Criteria

- [ ] `tests/e2e/Dockerfile` installs the **local working tree**
      editable (`pip install -e .` over a copied/mounted `src/`), not
      the current `pip install git+https://github.com/...clasi.git`
      (non-editable, wrong version) — coverage must map to `src/clasi`
      as it exists on this branch, not a published release.
- [ ] `tests/e2e/entrypoint.sh` (or the container env) exports
      `COVERAGE_PROCESS_START=<path>/.coveragerc` and `COVERAGE_FILE=<bind-mounted
      coverage dir>/.coverage`, so the venv's existing
      `a1_coverage.pth` startup hook (already present — verified no new
      subprocess-coverage machinery is needed) auto-starts
      `coverage.process_startup()` for every `clasi` CLI invocation and
      the long-lived `clasi mcp` server (spawned via `.mcp.json`, which
      inherits the env).
- [ ] A new `.coveragerc` (under `tests/e2e/`) sets `parallel = true`,
      `branch = true`, `source = clasi` (not `clasi,clasr` — see
      Description's dependency-on-002 note), and does **not** omit
      `cli.py`/`hook_handlers.py`/`mcp_server.py` (unlike the unit
      gate's `pyproject.toml` config, which may keep omitting them).
- [ ] A combine/report script (extend `tests/e2e/validate.sh` or add a
      new `tests/e2e/coverage.sh`) runs `coverage combine` +
      `coverage report`/`coverage html` after a run, writing
      machine-readable output (json and/or lcov) in addition to the
      human-readable report.
- [ ] `pyproject.toml` gains a `[tool.coverage.paths]` section
      remapping the container's install path to `src/clasi` (and to
      `src/clasr`'s old path is **not** needed, since ticket 002 has
      already removed `src/clasr` from the tree by the time this ticket
      runs), so the combined report resolves to real source paths, not
      container-internal ones.
- [ ] `pyproject.toml`'s `[tool.coverage.run].omit` drops the stale
      `*/clasi/plugin/hooks/role_guard.py` entry — verified during
      planning that this file no longer exists in the tree. This is the
      one `pyproject.toml` coverage-config change this ticket makes;
      everything else coverage-config-related lives in the new
      `tests/e2e/`-scoped `.coveragerc`.
- [ ] After a run, `.coverage.*` files exist for **both** CLI
      invocations and the `clasi mcp` process (verify by inspecting
      file count/names, not just that the combine step doesn't error).
- [ ] The combined report, once generated, includes
      `cli.py`/`mcp_server.py`/`hook_handlers.py` coverage — the
      concrete proof the two-config split (previous bullet) actually
      works as intended, not just that it's configured correctly on
      paper.
- [ ] **The e2e-running agent (the tester session driving the e2e, per
      `tests/e2e/AGENTS.md`) writes a textual markdown dead-code
      report** into the run's output directory, ranking `src/clasi`
      modules/functions/branches never executed by either the e2e or
      the unit suite, each with file:line and a short rationale.
      Wiring this in means: extending `tests/e2e/AGENTS.md`'s
      milestone/report instructions (or `report.sh`, if sprint 028's
      instrumentation work already established one — check before
      creating a new mechanism) to include this step at run end,
      pointed at the combined coverage output this ticket produces.
- [ ] **Hard boundary**: this ticket makes no code or test deletions
      based on the dead-code report's contents. If, during
      implementation, a genuinely dead piece of code is discovered
      incidentally (not through the report — through normal reading),
      it is not deleted here; note it for a future developer-triggered
      pass instead.
- [ ] Full suite (unit/integration/system tier) passes unaffected — this
      ticket's changes are scoped to `tests/e2e/` and `pyproject.toml`'s
      coverage config; it should not change unit-gate behavior beyond
      the stale `role_guard.py` omit removal.

## Implementation Plan

### Approach

1. Confirm ticket 002 has landed (clasr gone) before starting — the
   `.coveragerc` `source =` value and any lingering `src/clasr`
   references in `tests/e2e/` assume this.
2. Dockerfile/entrypoint changes: switch to editable local install;
   wire `COVERAGE_PROCESS_START`/`COVERAGE_FILE`; ship the new
   `.coveragerc`.
3. `pyproject.toml`: add `[tool.coverage.paths]`; drop the stale
   `role_guard.py` omit entry. Nothing else in `pyproject.toml` changes
   here (the default-`addopts`/`slow`-marker work is ticket 008's, not
   this one's, even though both touch `pyproject.toml`).
4. Combine/report script: extend `validate.sh` or add `coverage.sh`.
5. Wire the dead-code-report step into the e2e agent's own
   instructions (`AGENTS.md` or `report.sh`).
6. **Validate with an actual on-demand e2e run** — this ticket's
   acceptance criteria cannot be verified by a unit test; the developer
   (or this ticket's implementer, if authorized to trigger a run) must
   actually run the e2e once with instrumentation and confirm
   `.coverage.*` files, the combined report, and the dead-code report
   all materialize as specified. If running the full e2e isn't
   practical within this ticket's execution context, say so explicitly
   in the ticket's completion notes and flag the harness as
   implemented-but-not-yet-validated-end-to-end, rather than silently
   marking this criterion satisfied without having run it.

### Files to Modify

- `tests/e2e/Dockerfile`
- `tests/e2e/entrypoint.sh`
- New: `tests/e2e/.coveragerc` (or wherever the e2e-scoped config is
  placed — under `tests/e2e/` so it's clearly separate from the root
  `pyproject.toml` config)
- `tests/e2e/validate.sh` (extend) or new `tests/e2e/coverage.sh`
- `pyproject.toml` (`[tool.coverage.paths]`, `omit` list's stale entry)
- `tests/e2e/AGENTS.md` (or `report.sh`, whichever already carries
  per-run reporting instructions from sprint 028's instrumentation
  work — check first)

### Testing Plan

- **Existing tests to run**: none directly — this ticket's surface is
  Docker/e2e infrastructure and `pyproject.toml` config, not unit-testable
  Python logic. Run `uv run pytest tests/unit/ -k "coverage" -v` (or
  similar) only as a sanity check that nothing in the unit tier reads
  `pyproject.toml`'s coverage config in a way this ticket's changes
  would break — expect this to turn up nothing, since it shouldn't.
- **New tests to write**: none in the unit-test sense. The real
  validation is the on-demand e2e run described in Approach step 6.
- **Verification command**: `uv run pytest` (confirms the
  `pyproject.toml` edits didn't break the unit-gate config) plus an
  actual e2e run, if practical within this ticket's execution context.

### Documentation Updates

- `tests/e2e/AGENTS.md` (or `report.sh`) — the dead-code-report step.
- Consider a short note in `tests/e2e/README.md` (if one exists) or a
  comment in the new `.coveragerc` explaining the two-config split, so
  a future contributor doesn't "simplify" it back into one shared
  config and reintroduce the audience conflict this ticket avoided.

## Process Notes

- Guards fail closed. If a role-guard or mcp-guard block is hit while
  working this ticket, **STOP and report it** — do not route around it.
  Reporting a block is a successful outcome of this ticket's work, not
  a failure.
- Tier-2 (in-progress-ticket) write scope covers this ticket's own file
  under the locked sprint's `tickets/` tree, plus `tests/` and root-level
  `pyproject.toml` (verify tier clearance for root-level config files —
  this sprint's `protected_paths` is `[src, tests]`; `tests/e2e/` is
  under `tests/` but is separately listed in `.clasi/config.yaml`'s
  `excluded_paths: [tests/e2e]` for a different purpose — path
  protection and test-collection exclusion are independent settings;
  confirm which applies before assuming either blocks or permits this
  ticket's edits).
- **Do not automate any part of Part B** (report → issue → sprint) —
  that stays permanently developer-triggered, regardless of how good
  this ticket's report output turns out to be. This is a repeated
  constraint across this sprint's dispatch and sprint.md; it bears
  repeating here since this is the one ticket that produces the report
  Part B would consume.
- `completes_issue: false` in this ticket's frontmatter is deliberate —
  ticket 008 also references the same issue
  (`test-system-improvements-...`) and is the one that should trigger
  its archival to `issues/done/` once both are complete.
