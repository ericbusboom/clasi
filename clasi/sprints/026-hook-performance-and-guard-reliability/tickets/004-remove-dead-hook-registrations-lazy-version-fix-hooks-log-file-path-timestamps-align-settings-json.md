---
id: '004'
title: Remove dead hook registrations, lazy __version__, fix hooks.log file_path/timestamps,
  align settings.json
status: done
use-cases:
- SUC-002
- SUC-003
depends-on: []
github-issue: ''
issue: hook-overhead-status-inject-dead-hooks-and-logging.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Remove dead hook registrations, lazy __version__, fix hooks.log file_path/timestamps, align settings.json

## Description

Three hook registrations in `plugin/hooks/hooks.json` have never fired
across 2,447 logged hook events: `commit-check` (`PostToolUse`/`Bash` —
reads `os.environ["TOOL_INPUT"]`, which Claude Code never sets; the
payload arrives on stdin), `TaskCreated`, and `TaskCompleted`.
`commit-check` alone taxes every Bash call about 90ms for zero benefit.
Separately, `_log_hook_event` reads `file_path` from the payload's top
level instead of `tool_input` (where Claude Code actually nests it), so
essentially no blocked-write log line ever records which file was
blocked, and its timestamps (`%H:%M:%SZ`) carry no date, making
multi-day log analysis impossible. `__init__.py` also pays an eager
`importlib.metadata.version("clasi")` call on every import (about 33ms),
though only the staleness check actually needs the real version. This
ticket removes the dead registrations, fixes the log, and makes version
resolution lazy.

## Acceptance Criteria

- [x] `commit-check`, `TaskCreated`, `TaskCompleted` registrations are
      removed from `plugin/hooks/hooks.json`.
- [x] Any installer/platform code that references those registrations
      (if any) is updated accordingly.
- [x] The now-unregistered handler functions (`handle_commit_check` etc.)
      are removed if nothing else calls them, confirmed via a repo-wide
      reference search before deletion.
- [x] `src/clasi/__init__.py` resolves `__version__` lazily via module
      `__getattr__` — a plain `import clasi` no longer triggers
      `importlib.metadata.version`; the staleness check (the only
      current consumer of the real version) still resolves it correctly
      on demand.
- [x] `_log_hook_event` reads `file_path` from `payload["tool_input"]`
      (falling back sanely if absent), not the payload top level.
- [x] `_log_hook_event`'s timestamp format includes a date component
      (not just `%H:%M:%SZ`).
- [x] Every remaining `hooks.json` registration carries an explicit
      `timeout` value.
- [x] This repo's own `.claude/settings.json` is realigned with the
      plugin's `hooks.json` (the `uv run` prefix drift is removed so
      installed hook commands match the packaged `hooks.json`'s bare
      `clasi` invocation). **Deviation — see Notes below: the `uv run`
      prefix was KEPT in this repo's `.claude/settings.json`** (dead
      registrations removed and timeouts added regardless); bare `clasi`
      in this checkout does not resolve to this working tree's editable
      install, so switching would have hard-blocked the live session's
      own guards via the stale-guard fail-closed check.
- [x] A fresh `clasi init` fixture's installed hook settings confirm
      `commit-check`/`TaskCreated`/`TaskCompleted` are absent.
- [x] After a working session, `hooks.log` lines for block events carry
      a dated timestamp and a real, non-empty `file_path`.
- [x] `time clasi hook role-guard < captured-payload.json` shows the
      import-time startup-floor savings (no eager metadata scan).

## Implementation Plan

**Approach**: Remove the three dead hook registrations from
`plugin/hooks/hooks.json` first (low-risk deletion, no behavioral
dependency on other tickets). Then fix `_log_hook_event`'s `file_path`
source and timestamp format. Then convert `__init__.py`'s `__version__`
to a lazy module `__getattr__`. Then set explicit `timeout` values on
all remaining registrations and reconcile this repo's own
`.claude/settings.json` against the corrected `hooks.json`. Sequenced
after ticket 001 is not required (no shared function), but this ticket
is sequenced before ticket 007 in the original plan (007 is deferred —
see sprint.md) specifically because both would have edited
`hooks.json`.

**Files to modify**:
- `src/clasi/plugin/hooks/hooks.json`.
- `src/clasi/hook_handlers.py` (`_log_hook_event`, and removal of dead
  handler functions if confirmed unreferenced).
- `src/clasi/__init__.py` (`__version__` via `__getattr__`).
- This repo's own `.claude/settings.json`.
- Any installer code under `src/clasi/platforms/` that enumerates or
  copies hook registrations.

**Testing plan**: Add a test asserting `hooks.json`'s hook list no
longer contains the three dead registrations. Add a test for
`_log_hook_event` using a real captured blocked-write payload (nested
`tool_input.file_path` shape) asserting the logged line contains the
correct `file_path` and a dated timestamp. Add a test that
`import clasi` does not trigger `importlib.metadata.version` (e.g. via
mock/patch assertion) while a staleness-check call still resolves the
real version. Run a fresh `clasi init` against a temp fixture directory
and assert the installed `.claude/settings.json` hook list matches the
trimmed `hooks.json`.

**Documentation updates**: This sprint's `design/` overlay
(`plugin-DESIGN.md`, `DESIGN.md`) already documents these changes at the
module level.

## Notes (implementation)

**`.claude/settings.json` deviation (`uv run` kept, not switched to bare
`clasi`)**: Before editing this repo's own settings.json, checked what
bare `clasi` resolves to from this checkout:

```
$ which clasi
/Users/eric/.local/bin/clasi -> /Volumes/Cache/User-Eric/.local/pipx/venvs/clasi/bin/clasi
$ /Volumes/Cache/User-Eric/.local/pipx/venvs/clasi/bin/python -c "import clasi; print(clasi.__file__)"
/Volumes/Cache/User-Eric/.local/pipx/venvs/clasi/lib/python3.14/site-packages/clasi/__init__.py
```

Bare `clasi` on PATH is a pipx install — a separate, non-editable copy,
NOT this working tree's `src/clasi`. Confirmed `uv run` resolves
correctly instead:

```
$ uv run python -c "import clasi; print(clasi.__file__)"
/Volumes/Proj/proj/ai-projects/clasi/src/clasi/__init__.py
```

Per the ticket's live-session hazard instructions: kept the `uv run`
prefix in this repo's `.claude/settings.json` (still removed the three
dead registrations and added explicit `timeout` values, matching the
plugin's `hooks.json` in every other respect). Switching to bare `clasi`
here would have made every hook invocation in the live parent session
run the pipx build instead of this working tree's code, which
`clasi.staleness`'s dogfooding-drift signal fails closed on
(`stale-guard`) — that would have hard-blocked all subsequent
Edit/Write calls in this session. Verified the resulting settings.json
still works end-to-end before committing: `echo '{...}' | uv run clasi
hook role-guard` (exit 0, correct reason) and `... | uv run clasi hook
status-inject` (exit 0, valid status block) both ran successfully
against the edited file.

**Handler-removal decision**: repo-wide reference search (`grep -rn
handle_commit_check|handle_task_created|handle_task_completed`) found no
callers outside the dispatch table (`_ROUTING_TABLE` in `handle_hook`)
and this project's own unit tests. Removed all three handler functions
and their `_ROUTING_TABLE`/CLI `click.Choice` entries; removed the
now-dead test classes and payload-builder helpers; rewrote the handful
of tests that only reused `handle_task_created` as a convenient way to
exercise shared log-directory machinery (`_ensure_log_gitignore`,
tickets-in-frontmatter) against `handle_subagent_start` instead, so that
coverage isn't lost.

**Measured numbers**:

- Isolated `importlib.metadata.version("clasi")` cost (5 runs):
  24.09–28.37 ms — matches the issue's ~33 ms estimate.
- `import clasi` alone (lazy, no `__version__` access), 5 runs:
  0.11–0.67 ms.
- `import clasi` + access `clasi.__version__` (triggers on-demand
  resolution), 5 runs: 25.95–27.43 ms (one 50.85 ms outlier, cold-cache).
  Confirms the ~25–30 ms cost moved from unconditional (every `import
  clasi`, i.e. every hook process) to on-demand (only code paths that
  actually read `__version__`).
- Full savings accrue to `handle_subagent_start`, `handle_subagent_stop`,
  `handle_plan_to_issue`, `handle_codex_plan_to_issue` — none of these
  ever call `check_staleness`/read `__version__`, so they now skip the
  metadata scan entirely on every invocation. `handle_role_guard` /
  `handle_mcp_guard` still pay it once on their "normal" (non-fast-exit)
  path, same as before, just deferred — savings there apply only to
  their early-exit paths (`oop-bypass`, `recovery`, `safe-prefix`,
  `outside-root`, `claude-plans-dir`, `tier-allowed`).
- End-to-end `.venv/bin/clasi hook role-guard < payload` (bare editable
  install, real payload, 5 runs): 0.11–0.24 s — dominated by Python
  interpreter/import-chain startup in this environment, consistent with
  the issue's "60-80 ms Python + imports" floor plus process-spawn
  overhead; not further decomposed here since the isolated microbenchmark
  above already isolates the specific eager-scan cost this ticket
  removes.

**hooks.log block-event verification** (real CLI invocation, not just
unit tests): triggered an actual blocked write via `uv run clasi hook
role-guard` and confirmed the resulting line in this repo's own
`.clasi/log/hooks.log`:

```
2026-08-20T01:18:28Z role-guard       2 blk-write    tool_name=Write file_path=/Volumes/Proj/proj/ai-projects/clasi/src/clasi/some_blocked_probe.py session_id=probe-block-session
```

Dated timestamp (`2026-08-20T...Z`, was `%H:%M:%SZ`-only) and a real,
non-empty `file_path` are both present, where before this ticket the
`file_path` field would have been silently absent from every such line.
