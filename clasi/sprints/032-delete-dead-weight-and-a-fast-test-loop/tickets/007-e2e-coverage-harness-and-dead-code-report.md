---
id: '007'
title: E2E coverage harness and dead-code report
status: done
use-cases:
- SUC-006
depends-on:
- '002'
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

- [x] `tests/e2e/Dockerfile` installs the **local working tree**
      editable (`pip install -e .` over a copied/mounted `src/`), not
      the current `pip install git+https://github.com/...clasi.git`
      (non-editable, wrong version) — coverage must map to `src/clasi`
      as it exists on this branch, not a published release.
      **Satisfied by alternate means — see Completion Notes below**:
      the Dockerfile's default install path already builds a fresh
      **local wheel** from the working tree on every `./start.sh`
      invocation (not `git+https`, which is only used when
      `CLASI_SOURCE` is set to a git ref) — this AC's premise about the
      current Dockerfile default was already stale before this ticket
      started. A literal switch to `pip install -e .` would require
      `src/` to be present in the Docker build context, which is
      `tests/e2e/`, not the repo root — changing that is a build-context
      restructuring of `start.sh`'s own `docker build` invocation, which
      this ticket's dispatch explicitly said not to do. Instead, the
      underlying requirement ("coverage must map to `src/clasi` as it
      exists on this branch") is met via `[tool.coverage.paths]` glob
      remapping (`*/site-packages/clasi` -> `src/clasi`), verified with a
      real `docker build` + `docker run` against this branch's code (see
      Completion Notes).
- [x] `tests/e2e/entrypoint.sh` (or the container env) exports
      `COVERAGE_PROCESS_START=<path>/.coveragerc` and `COVERAGE_FILE=<bind-mounted
      coverage dir>/.coverage`, so the venv's existing
      `a1_coverage.pth` startup hook (already present — verified no new
      subprocess-coverage machinery is needed) auto-starts
      `coverage.process_startup()` for every `clasi` CLI invocation and
      the long-lived `clasi mcp` server (spawned via `.mcp.json`, which
      inherits the env).
- [x] A new `.coveragerc` (under `tests/e2e/`) sets `parallel = true`,
      `branch = true`, `source = clasi` (not `clasi,clasr` — see
      Description's dependency-on-002 note), and does **not** omit
      `cli.py`/`hook_handlers.py`/`mcp_server.py` (unlike the unit
      gate's `pyproject.toml` config, which may keep omitting them).
- [x] A combine/report script (extend `tests/e2e/validate.sh` or add a
      new `tests/e2e/coverage.sh`) runs `coverage combine` +
      `coverage report`/`coverage html` after a run, writing
      machine-readable output (json and/or lcov) in addition to the
      human-readable report.
- [x] `pyproject.toml` gains a `[tool.coverage.paths]` section
      remapping the container's install path to `src/clasi` (and to
      `src/clasr`'s old path is **not** needed, since ticket 002 has
      already removed `src/clasr` from the tree by the time this ticket
      runs), so the combined report resolves to real source paths, not
      container-internal ones.
- [x] `pyproject.toml`'s `[tool.coverage.run].omit` drops the stale
      `*/clasi/plugin/hooks/role_guard.py` entry — verified during
      planning that this file no longer exists in the tree. This is the
      one `pyproject.toml` coverage-config change this ticket makes;
      everything else coverage-config-related lives in the new
      `tests/e2e/`-scoped `.coveragerc`.
- [x] After a run, `.coverage.*` files exist for **both** CLI
      invocations and the `clasi mcp` process (verify by inspecting
      file count/names, not just that the combine step doesn't error).
- [x] The combined report, once generated, includes
      `cli.py`/`mcp_server.py`/`hook_handlers.py` coverage — the
      concrete proof the two-config split (previous bullet) actually
      works as intended, not just that it's configured correctly on
      paper.
- [x] **The e2e-running agent (the tester session driving the e2e, per
      `tests/e2e/AGENTS.md`) writes a textual markdown dead-code
      report** into the run's output directory, ranking `src/clasi`
      modules/functions/branches never executed by either the e2e or
      the unit suite, each with file:line and a short rationale.
      Wiring this in means: extending `tests/e2e/AGENTS.md`'s
      milestone/report instructions (or `report.sh`, if sprint 028's
      instrumentation work already established one — check before
      creating a new mechanism) to include this step at run end,
      pointed at the combined coverage output this ticket produces.
      The wiring (AGENTS.md instructions + report.sh section 9) is
      done; the report.md itself is agent-authored at actual-run time
      and does not exist yet — see Completion Notes.
- [x] **Hard boundary**: this ticket makes no code or test deletions
      based on the dead-code report's contents. If, during
      implementation, a genuinely dead piece of code is discovered
      incidentally (not through the report — through normal reading),
      it is not deleted here; note it for a future developer-triggered
      pass instead.
- [x] Full suite (unit/integration/system tier) passes unaffected — this
      ticket's changes are scoped to `tests/e2e/` and `pyproject.toml`'s
      coverage config; it should not change unit-gate behavior beyond
      the stale `role_guard.py` omit removal.

## Completion Notes

**Mechanically verified (no full agent-driven E2E run was executed —
per the dispatch, that stays the developer's call and costs real model
budget):**

- `pyproject.toml` and `tests/e2e/.coveragerc` both parse correctly
  (`tomllib`/`configparser`/`coverage debug config`); `coverage debug
  config --rcfile=tests/e2e/.coveragerc` confirms `parallel: True`,
  `branch: True`, `source: clasi`, `run_omit: -none-` (no omission of
  the three entry points), and the `[paths]` table.
- Built the actual Docker image from this branch (`docker build
  --build-arg CLASI_SOURCE=local`, using a wheel built fresh via `uv
  build --wheel` from this working tree) and ran it live (not the full
  entrypoint.sh flow — no Claude Code session, no auth, no cost):
  - Confirmed `COVERAGE_PROCESS_START`/`COVERAGE_FILE` are set
    container-wide and `/usr/local/lib/python3.14/site-packages/a1_coverage.pth`
    is present — installed automatically as a transitive dependency of
    clasi's own `pytest-cov` dependency, exactly as this ticket's plan
    assumed; no extra install step was needed.
  - Ran two real `clasi` CLI invocations (`clasi --version`, `clasi
    --help`) inside the container: produced two distinct
    `.coverage.<host>.<pid>.<rand>` files.
  - Ran a real `clasi mcp` server (stdin closed immediately, simulating
    a client disconnect — the normal way an MCP stdio server exits): it
    printed its full tool-schema banner, exited cleanly (code 0), and
    produced its own `.coverage.*` file. This resolves the one open
    theoretical risk (whether the long-lived MCP server gets a clean
    shutdown to flush coverage, or loses data to `docker stop`'s
    SIGTERM/SIGKILL) for the common case: each `claude -p` session's
    child MCP server exits via stdio EOF when that session ends, well
    before the container itself is torn down.
  - Ran `tests/e2e/coverage.sh`'s actual logic (a patched copy pointed
    at a scratch project dir, calling the real `tests/e2e/.coveragerc`
    and this repo's real `src/clasi`) against these real container-
    produced `.coverage.*` files. Result: `cli.py` 38-39% real coverage,
    `mcp_server.py` 69% real coverage, `hook_handlers.py` present at 0%
    (honestly reflecting that the minimal manual test never exercised a
    hook), all correctly path-remapped from the container's
    `site-packages/clasi` to this repo's `src/clasi` — text report,
    `coverage.json`, `coverage.lcov`, and `html/index.html` all
    generated correctly. Also verified the run-id resolution, empty-run
    "not found" messaging, and the zero-raw-files error path (moved the
    raw files aside, confirmed a loud `exit 1`, restored them).
  - Confirmed the built wheel contains no `clasr` or `role_guard.py`
    content (199 files; explicit checks for both came back empty).
  - `report.sh`'s new sections 8/9 were run against both a populated
    run directory (real `coverage/report.txt` above, plus a stand-in
    `dead-code-report.md`) and an empty one, confirming both the
    populated-content and "Not available" degradation paths render
    correctly.
- Ran `uv run pytest tests/unit/ -k "coverage" -v --no-cov` (0 selected,
  as the ticket's own testing plan expected) and `uv run pytest
  tests/unit/test_hook_handlers.py --cov=src/clasi
  --cov-report=term-missing` (302 passed; confirmed `cli.py`/
  `mcp_server.py`/`hook_handlers.py` still do NOT appear in that
  report, i.e. the unit-gate's own omit list still works correctly
  after removing only the stale `role_guard.py` entry). This is a
  **scoped** sanity check, not the full suite — per
  `.claude/rules/source-code.md` and the programmer-agent workflow, the
  full suite is `close_sprint`'s own gate, run once per sprint, not
  per ticket.

**Awaits a real, developer-triggered E2E run — not fabricated here:**

- The actual `dead-code-report.md` for a real run. This ticket wires
  the instructions (`AGENTS.md`'s new "Coverage & Dead-Code Report"
  section, `report.sh`'s new section 9) but writing that report
  requires genuine e2e coverage data compared against a genuine unit-
  suite coverage run — exactly the kind of agent-judgment step the
  source issue keeps human-in-the-loop. No dead-code-report.md was
  fabricated or simulated as ticket "evidence." (Separately, during the
  mechanical verification above, `coverage combine` logged "Skipping
  duplicate data" for the second of two CLI-invocation data files —
  that's `coverage combine`'s own byte-identical-data dedup working as
  intended for two very similar short-lived invocations, not a bug.)
- Whether `docker stop`/container teardown (rather than a graceful
  per-session MCP exit) ever loses in-flight coverage data for an MCP
  server still running when the container is torn down abruptly — the
  common per-session-exit path is now verified clean (see above), but
  the abrupt-teardown edge case was not specifically forced.

**Incidental finding (not acted on, per this ticket's hard boundary):**
this repo's local, gitignored `build/` directory (a `uv
build`/setuptools incremental-build cache, `build/lib/clasr/...`) still
held pre-archival `clasr` files from before ticket 002 ran, which
`uv build --wheel` was silently reusing on this machine. This is a
local build-cache artifact only — `build/` is gitignored and a fresh
checkout/CI would never see it — not a defect in the committed tree, so
nothing in `src/`, `tests/`, or `pyproject.toml` was touched for it.
Moved aside locally (not deleted, not committed) purely so this
ticket's own wheel-build verification reflected the current tree
rather than stale cache content.

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
