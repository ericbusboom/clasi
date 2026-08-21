---
status: in-progress
sprint: '032'
tickets:
- 032-007
- 032-008
---

# Test-system improvements: real-app coverage from the e2e + a leaner, faster suite

## Context

The unit/integration suite has grown to about 2,342 tests and takes 6–10 min, which is too slow for
frequent runs, and we don't actually know how much of the *real application* (the `clasi` CLI and the
long-running `clasi mcp` server) our tests exercise. Separately, we have a genuine acceptance test:
the **agent-driven** e2e — Claude Code (print mode), inside Docker, runs the full CLASI SE process
(init → 4 sprints of plan/ticket/execute/close, building a guessing-game CLI) and is checked by
`validate.sh`. It works (see `clasi/issues/e2e-001-review.md`: 4/4 sprints, 12 tickets, 37 tests
passing). It's heavyweight (20–55 min) and run occasionally on demand — **not** to be automated/CI'd.

**Goal:** measure real-application coverage from that occasional e2e run, and use it to find dead
code and trim redundant tests — with the *developer driving every decision*.

### Control flow — what is automated vs developer-driven

This is deliberately **human-in-the-loop**. Do NOT automate pruning, issue creation, or sprinting.

- **Developer triggers** the e2e when they choose ("run the e2e now").
- **Automated (the "main things"):** the run installs the local tree under coverage, executes the
  full agent-driven SE process so `clasi` + the MCP server are exercised, emits coverage data, and
  the **e2e-running agent analyzes the coverage and writes a textual report** ranking which `src/clasi`
  code is most likely dead (never executed by either the e2e or the unit suite).
- **Developer-driven (NOT automated):** the developer reads that report and, *only when they say so*
  ("make an issue to remove this code"), an agent turns it into a CLASI removal issue. The developer
  then decides if/when that issue becomes a sprint. Nothing removes code or tests automatically.

Confirmed decisions: e2e stays an occasional, on-demand, agent-driven run (instrument it, don't
automate it); `clasr` is actively maintained (dedupe redundant tests, don't gut it); the e2e is the
primary acceptance test we can lean on to thin redundant integration/system tests. This document is
itself an analysis/recommendation issue → planned into a sprint when the developer chooses.

## Part A — Automated: run the e2e under coverage and produce a dead-code report

The subprocess coverage machinery is mostly already present: the venv has the `a1_coverage.pth`
startup hook, which auto-starts `coverage.process_startup()` whenever `COVERAGE_PROCESS_START` is set.
So every `clasi` CLI call **and** the Claude-spawned `clasi mcp` server get covered "for free" once
the env + a parallel-mode config are in place.

1. **Install the local working tree under coverage in the container.** [tests/e2e/Dockerfile](tests/e2e/Dockerfile) currently does `pip install git+https://github.com/...clasi.git` (non-editable, wrong version). Change to install the **local** checkout editable (`pip install -e .` over a copied/mounted `src/` tree) so coverage maps to `src/clasi`.
2. **Turn coverage on for all child processes.** In the container env / [tests/e2e/entrypoint.sh](tests/e2e/entrypoint.sh): export `COVERAGE_PROCESS_START=<path>/.coveragerc` and `COVERAGE_FILE=<bind-mounted coverage dir>/.coverage`, and ship a `.coveragerc` with `parallel = true`, `branch = true`, `source = clasi,clasr`. The `.pth` hook + this env cause each `clasi` invocation and the long-lived `clasi mcp` server (spawned via `.mcp.json`, which inherits the env) to emit `.coverage.<host>.<pid>.*` files.
3. **Extract + combine + report on the host.** After the run, the bind mount (`tests/e2e/project/`) holds the `.coverage.*` files; a script (extend [tests/e2e/validate.sh](tests/e2e/validate.sh) or a new `coverage.sh`) runs `coverage combine` + `coverage report`/`html` and writes machine-readable output (json/lcov).
4. **Map container paths back to source.** Add a `[tool.coverage.paths]` section to [pyproject.toml](pyproject.toml) remapping the container install path ↔ `src/clasi`/`src/clasr` so the combined report resolves to source.
5. **Un-omit the entry points for the real-app report.** [pyproject.toml](pyproject.toml) `[tool.coverage.run] omit` currently excludes `cli.py`, `hook_handlers.py`, `mcp_server.py` — exactly the real-app code the e2e exercises — plus a stale `role_guard.py` (no longer exists). Drop the stale entry; don't omit the three entry points from the e2e/real-app report (they may stay omitted in the *unit* gate if unit coverage of them is weak — decide once we see numbers).
6. **Automated dead-code report.** The e2e-running agent reads the combined coverage (real-app) and merges it conceptually with the unit-suite coverage, then writes a **textual report** (a markdown file in the run output) ranking `src/clasi` modules/functions/branches never executed by either — i.e. likely-dead code, with file:line and a short rationale per item. This report is the deliverable of a run; it makes **no changes**.

## Part B — Developer-driven: from report to issue to sprint (NOT automated)

This is explicitly manual / on-request — the report from Part A is an input, not an action.

- **On the developer's request only**, an agent converts selected items from the dead-code report into a CLASI **removal issue** (proposing specific code/feature deletions, with the coverage evidence). The developer decides what goes in and when this happens.
- **Thinning redundant tests** is handled the same way: where the e2e acceptance run fully exercises a path, the developer may ask for an issue proposing trims of the slow integration/system duplicates (keeping unit tests comprehensive). Prime candidates to call out in such a report: [tests/system/test_artifact_tools.py](tests/system/test_artifact_tools.py) (80 tests), [tests/integration/test_status_e2e.py](tests/integration/test_status_e2e.py) (41 tests).
- The developer drives whether/when any such issue becomes a sprint. No auto-pruning, no auto-issue, no auto-sprint.

## Part C — Immediate efficiency wins (ordinary cleanup, separate from the coverage loop)

Low-risk speedups that don't depend on coverage and aren't part of the automated run — normal
developer-scheduled sprint work:

- **Activate the `slow` marker.** The marker exists and `addopts` already has `-m 'not slow'`, but **no test is marked slow**, so every run is the full suite. Mark the heavy real-FS/real-CLI/fixture tests (most of `tests/system/`, `tests/integration/`, and the heaviest `tests/unit` fixture tests) `@pytest.mark.slow`. Default `uv run pytest` then runs the fast unit subset (dev speed); CI / pre-close runs full (`-m 'slow or not slow'`). Biggest single speed win.
- **Dedupe `clasr` (keep it — it's maintained).** Consolidate the roughly 117 `clasr` tests that duplicate `unit/` coverage — `tests/clasr/test_platform_{claude,codex,copilot,detect}.py`, `test_markers.py`, `test_links.py`, `test_frontmatter.py` — down to what genuinely tests `clasr`'s own code. **Keep** the clasr-unique suites: `test_multi_tenant.py`, `test_cli.py`, `test_merge.py`, `test_manifest.py`, `test_three_platform_roundtrip.py`, `test_integration_contract.py`.
- **Delete empty placeholder dirs:** `tests/dev/`, `tests/proj/`.

## Affected files (representative)

- [tests/e2e/Dockerfile](tests/e2e/Dockerfile), [tests/e2e/entrypoint.sh](tests/e2e/entrypoint.sh) — install local tree editable; set `COVERAGE_PROCESS_START`/`COVERAGE_FILE`; ship `.coveragerc`.
- [tests/e2e/validate.sh](tests/e2e/validate.sh) (+ a coverage extract/combine/report script and the dead-code-report step).
- [pyproject.toml](pyproject.toml) — `[tool.coverage.paths]` (new), `[tool.coverage.run] omit` (drop stale `role_guard.py`, reconsider entry-point omits), keep the `slow` marker + `-m 'not slow'`.
- `tests/clasr/test_platform_*.py`, `test_markers.py`, `test_links.py`, `test_frontmatter.py` — consolidate vs `tests/unit/`.
- Heavy tests in `tests/system/`, `tests/integration/`, `tests/unit/` — add `@pytest.mark.slow`.
- Delete `tests/dev/`, `tests/proj/`.

## Verification

1. **Coverage harness:** run the e2e once with instrumentation → confirm `.coverage.*` files exist for *both* CLI invocations and the `clasi mcp` process; `coverage combine` + report renders `src/clasi` line/branch coverage including `cli.py`/`mcp_server.py`/`hook_handlers.py`.
2. **Dead-code report:** the run produces a textual report listing never-executed `src/clasi` code with file:line — and makes no code/test changes on its own.
3. **Fast default:** `uv run pytest` (slow deselected) is materially faster; `uv run pytest -m 'slow or not slow'` (full) stays green.
4. **Dedup/cleanup:** suite count drops by the removed clasr dupes; no unique clasr coverage lost (clasr-only suites still pass); `tests/dev`/`tests/proj` gone; coverage gate (`fail_under`) still satisfied.

## Related

`clasi/issues/e2e-001-review.md` — process-quality review of an e2e run (planning heaviness, parallel dispatch, version-bump noise, close-report/reflection gaps). Separate concern; this issue is the test-system + coverage angle. Some overlap on "version-bump noise" and "unused issue/reflection fields" — coordinate when sprinting.
