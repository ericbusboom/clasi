---
id: '003'
title: Upward project-root discovery in get_project()
status: done
use-cases:
- SUC-003
depends-on: []
github-issue: ''
issue: get-project-has-no-upward-root-discovery.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Upward project-root discovery in get_project()

## Description

`get_project()` (`src/clasi/hook_handlers.py:25-27`) is
`Project(Path.cwd())` with no upward search for `.clasi/`. Every hook
handler calls it and inherits whatever root it resolves — a hook fired
from a subdirectory silently gets every `Project` property
(`issues_dir`, `db_path`, `protected_paths`, etc.) resolved against the
wrong root. This ticket makes `get_project()` use the same upward-walk
helper `_oop_active()` already uses successfully (`_find_project_root`,
`hook_handlers.py:75`), closing the structural gap a narrower fix
already patched for the OOP-flag case alone.

**Scope**: `src/clasi/hook_handlers.py` only — `get_project()`.

**Dogfooding note (read before starting)**: this repo enforces its own
guards. `get_project()` is the single most centrally-called function in
`hook_handlers.py` — the reliability review calls it "the
highest-leverage single fix." Make this change in one small, isolated
step — do not combine it with unrelated cleanup in the same file — and
verify the module still imports cleanly
(`uv run python -c "import clasi.hook_handlers"`) before running the
scoped test suite below. `.clasi/oop` (`clasi oop on --reason '...'`)
remains available as an escape hatch if something in this file goes
wrong mid-ticket and you need to keep editing without role-guard
fighting you.

**Files to touch (verified during planning):**

- `src/clasi/hook_handlers.py:25-27` — `get_project()`:
  ```python
  def get_project() -> Project:
      """Return a Project instance rooted at the current working directory."""
      return Project(Path.cwd())
  ```
  becomes a call using `_find_project_root(Path.cwd())` (defined at
  `hook_handlers.py:75`, already used by `_oop_active()` and
  `cli.py:352`'s `oop` command), falling back to `Path.cwd()` unchanged
  when no `.clasi/` is found in any ancestor — matching
  `_find_project_root`'s existing documented fallback behavior exactly,
  so no other caller's behavior changes for a legitimate non-project
  cwd (e.g. an isolated `tmp_path` test fixture).
- No other file changes — every other handler already calls
  `get_project()` and inherits the fix with zero call-site changes.

## Acceptance Criteria

- [x] `get_project()` resolves the correct project root when invoked
      from a subdirectory of the project (test simulating cwd several
      levels below `.clasi/`)
- [x] No regression for legitimate non-project cwds — an isolated
      `tmp_path` fixture with no ancestor `.clasi/` still returns
      `Project(tmp_path)` unchanged
- [x] Test coverage spans multiple hook handlers that call
      `get_project()` (role-guard, mcp-guard, at minimum), not just
      `_oop_active()` (already covered by the earlier narrower fix)
- [x] `uv run python -c "import clasi.hook_handlers"` succeeds after
      the change (module still imports cleanly)

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/test_hook_handlers.py`
  (scoped, foreground — this is the module's largest test file and
  covers role-guard/mcp-guard's existing allow/deny behavior; a
  regression here means this ticket accidentally changed guard behavior
  beyond root resolution)
- **New tests to write**: `get_project()` called from a simulated
  subdirectory cwd resolves the real root; the same for at least
  role-guard's and mcp-guard's own invocation paths; the `tmp_path`
  non-regression case above.
- **Verification command**: `uv run pytest tests/unit/test_hook_handlers.py -v`
  (scoped, foreground — do not run the full suite for this ticket)
