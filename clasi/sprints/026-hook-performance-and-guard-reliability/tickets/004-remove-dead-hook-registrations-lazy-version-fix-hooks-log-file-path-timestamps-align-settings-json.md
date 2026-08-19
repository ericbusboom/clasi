---
id: '004'
title: Remove dead hook registrations, lazy __version__, fix hooks.log file_path/timestamps,
  align settings.json
status: open
use-cases: [SUC-002, SUC-003]
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

- [ ] `commit-check`, `TaskCreated`, `TaskCompleted` registrations are
      removed from `plugin/hooks/hooks.json`.
- [ ] Any installer/platform code that references those registrations
      (if any) is updated accordingly.
- [ ] The now-unregistered handler functions (`handle_commit_check` etc.)
      are removed if nothing else calls them, confirmed via a repo-wide
      reference search before deletion.
- [ ] `src/clasi/__init__.py` resolves `__version__` lazily via module
      `__getattr__` — a plain `import clasi` no longer triggers
      `importlib.metadata.version`; the staleness check (the only
      current consumer of the real version) still resolves it correctly
      on demand.
- [ ] `_log_hook_event` reads `file_path` from `payload["tool_input"]`
      (falling back sanely if absent), not the payload top level.
- [ ] `_log_hook_event`'s timestamp format includes a date component
      (not just `%H:%M:%SZ`).
- [ ] Every remaining `hooks.json` registration carries an explicit
      `timeout` value.
- [ ] This repo's own `.claude/settings.json` is realigned with the
      plugin's `hooks.json` (the `uv run` prefix drift is removed so
      installed hook commands match the packaged `hooks.json`'s bare
      `clasi` invocation).
- [ ] A fresh `clasi init` fixture's installed hook settings confirm
      `commit-check`/`TaskCreated`/`TaskCompleted` are absent.
- [ ] After a working session, `hooks.log` lines for block events carry
      a dated timestamp and a real, non-empty `file_path`.
- [ ] `time clasi hook role-guard < captured-payload.json` shows the
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
