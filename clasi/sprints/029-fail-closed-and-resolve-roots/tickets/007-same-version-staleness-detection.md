---
id: '007'
title: Same-version staleness detection
status: open
use-cases: [SUC-007]
depends-on: []
github-issue: ''
issue: staleness-detect-same-version-drift.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Same-version staleness detection

## Description

`check_staleness` cannot see the most common real drift: an editable
install whose source changed after the long-lived MCP server imported
it, with no version bump. This ticket adds a third signal: record
import time, compare it against the newest source file's mtime.

**Dogfooding note (read before starting) — this is one of the three
tickets ticket 009 has a verified dependency on**: `check_staleness` is
called directly, with no local exception handling, inside both
`handle_role_guard` (`hook_handlers.py:798-806`) and `handle_mcp_guard`
(`hook_handlers.py:1004-1012`) — confirmed during architecture
planning: the nearest preceding local `except Exception:` block in
`handle_role_guard` closes at line 770, well before the staleness gate
begins at line 774/798. Any exception your new signal can raise (a
`PermissionError` walking an unusual symlink, an `OSError` on a broken
install layout, anything from `Path.rglob`) will propagate straight
into the guard dispatch. Ticket 009 (landing later in this sprint)
converts an uncaught exception there into a hard block — so this
ticket's own new code must not raise on any real-world filesystem
layout. Test it against at least: a normal editable install, a
read-only install, and a path containing a broken symlink. `.clasi/oop`
remains available as an escape hatch if something still goes wrong
after 009 lands.

**Scope**: `src/clasi/staleness.py`, `src/clasi/__init__.py`.

**Files to touch (verified during planning):**

- `src/clasi/__init__.py` — record `_IMPORT_TIME = time.time()` at
  module import time (the module currently only defines a lazy
  `__version__` resolver via `__getattr__`; add the import-time
  constant alongside it, not inside the lazy getter).
- `src/clasi/staleness.py:100` (`check_staleness`) — add a third
  signal: compare `_IMPORT_TIME` against the newest `.py` file mtime
  under `Path(clasi.__file__).parent.rglob("*.py")`; if any file is
  newer, flag `stale: true` with a reason naming that file. Wrap the
  filesystem scan itself in a try/except that degrades to "signal not
  available" on any error (matching the module's own existing pattern
  for signals 1/2, per the reliability review's fail-open inventory row
  13: "OPEN — warn-only by design for signal 1... Acceptable;
  document") — this is the specific hardening the dogfooding note above
  requires.

## Acceptance Criteria

- [ ] Touching a source file after import makes `get_version()` report
      `stale: true` with a reason naming the newer file
- [ ] The existing two signals are unchanged; the new signal has its
      own unit test
- [ ] The new signal's filesystem scan cannot raise an uncaught
      exception into a caller — verified with a test against a
      read-only path and a path containing a broken symlink
- [ ] The E2E stale-server scenario (rebuild wheel mid-run) trips the
      guard (validated in the sprint's E2E run, not a unit test)

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/test_staleness.py`
  (scoped, foreground)
- **New tests to write**: the mtime-vs-import-time positive case; the
  read-only/broken-symlink non-raising cases described above; a
  regression test that the existing two signals' behavior is
  byte-for-byte unchanged.
- **Verification command**: `uv run pytest tests/unit/test_staleness.py -v`
