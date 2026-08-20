---
id: 009
title: Guard fail-closed exception boundary
status: open
use-cases: [SUC-009]
depends-on: ["003", "007", "008"]
github-issue: ''
issue: guard-fail-closed-exception-boundary.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Guard fail-closed exception boundary

## Description

The Claude Code harness only blocks a tool call on hook exit code 2 —
any crash, timeout, or spawn failure inside a CLASI guard is currently
an unlogged allow (876 historical `hooks.log` events prove the class is
real). Sprint 028's ticket 005 added observability around this (catch,
log a `guard-crash` line, dump the payload) but deliberately did
**not** change the outcome — it re-raises the original exception
unchanged, by explicit design, because installing the fail-closed fix
was this sprint's job (see that ticket's own "Hard scope boundary"
note, and `git show 5b3079b` for the exact committed code). This ticket
converts that re-raise into a hard block.

**This ticket arms a hard block in a repo that enforces its own
guards. Read this before starting.** Today, a bug in
`handle_role_guard`/`handle_mcp_guard` that raises an exception is
silently allowed — annoying in principle, invisible in practice. After
this ticket lands, the identical bug becomes `exit 2`: every subsequent
`Edit`/`Write`/`MultiEdit` call that trips it is **hard-blocked**,
including calls made by the agent trying to fix it.

This ticket is sequenced last in the sprint (009 of 9) and its
`depends-on` (`003`, `007`, `008`) is not a formality — it reflects a
**verified** finding from the architecture self-review, not a general
"land everything else first" guess. Only three tickets have code that
executes *unprotected* inside the exact `handle_role_guard`/
`handle_mcp_guard` call chain this ticket's boundary wraps:
- **003** — `get_project()` is the first line of substantive logic in
  `handle_role_guard`, resolved outside any local `try/except`.
- **007** — `check_staleness` is called directly with no local
  exception handler in either guard function
  (`hook_handlers.py:798-806`, `1004-1012`).
- **008** — rewrites the payload-parsing code path itself.

(Tickets 004-006 are good general hardening and are sequenced earlier
in the ticket table too, but verified inspection during planning showed
their own DB/frontmatter reads inside the guard chain are already
locally swallowed by pre-existing `except Exception:` blocks —
`hook_handlers.py:645, 654, 707, 769` — so they don't change what this
boundary newly catches. Full reasoning in sprint.md's Architecture
Design Rationale, including the self-review correction.) **Do not
start this ticket until 003, 007, and 008 all show `status: done`.**

**If this ticket's own change misfires** — if you find yourself blocked
from editing `hook_handlers.py` (or anything else) by a guard crash
this change caused — run `clasi oop on --reason "guard-crash boundary
ticket 009 misfired"` (or create the emergency file `.clasi/oop`
directly if `clasi` itself is unusable) to bypass CLASI enforcement for
the session, fix the regression, then `clasi oop off`. `.clasi/oop`'s
file check is unconditional and runs before any of this ticket's own
logic in every guard handler, so it is unaffected by anything this
ticket changes.

**Scope**: `src/clasi/hook_handlers.py` — `handle_hook`,
`handle_role_guard`, `handle_mcp_guard`, `read_payload`.

**Files to touch (verified during planning — this is the exact code
sprint 028 ticket 005 left in place, confirmed via `git show
5b3079b`):**

- `hook_handlers.py:1915-1934` (`handle_hook`'s dispatch for
  `role-guard`/`mcp-guard` events) — currently:
  ```python
  try:
      handler(payload)
  except Exception:
      _log_hook_event(event, payload, 2, "guard-crash")
      raise
  ```
  becomes:
  ```python
  try:
      handler(payload)
  except Exception:
      _exit_hook(event, payload, 2, "guard-crash")
  ```
  (drop the bare `raise` — `_exit_hook` already calls `_log_hook_event`
  then `sys.exit(exit_code)`, so calling it supersedes the separate
  `_log_hook_event` + `raise` pair). Update the large explanatory
  comment immediately above this block (currently describing the
  sprint-028-ticket-005 "deliberately NOT a fail-closed fix" rationale)
  to describe the new fail-closed behavior instead — do not leave stale
  comments claiming this is still observability-only.
- `handle_role_guard`'s payload ingress (near `hook_handlers.py:570-576`,
  or wherever ticket 008's `HookPayload.from_stdin` now performs this
  resolution — coordinate with that ticket's landed state, it lands
  first) — add an `isinstance(tool_input, dict)` check so a non-dict
  `tool_input` (e.g. `null`) denies with a clear reason instead of
  raising `AttributeError` on `.get()`.
- `handle_mcp_guard`'s tier check (`hook_handlers.py:977`, `agent_tier
  not in ("", "0")`) — becomes an explicit allowlist: `agent_tier in
  ("1", "2")`. Any unrecognized tier string (`"3"`, `"junk"`, a future
  tier that doesn't exist yet) now denies instead of allowing.
- `read_payload` (`hook_handlers.py:62-72`) — when stdin was non-empty
  but failed to parse as JSON, log a `bad-payload` decision token (via
  the same `decisions` mechanism ticket 008 threads through) before
  falling through to the existing `{}` default, so a malformed-JSON
  case is distinguishable in `hooks.log` from a legitimately empty
  payload.

## Acceptance Criteria

- [ ] A guard handler that raises produces exit 2 and a `guard-crash`
      log line with traceback — verified by a test that injects a
      fault (e.g. monkeypatch a handler internal to raise, assert
      `sys.exit(2)` and the log line)
- [ ] Malformed payload shapes (null `tool_input`, missing keys) deny
      rather than crash-allow, with distinct logged reasons
- [ ] Unknown tier strings do not allow (mcp-guard's allowlist change)
- [ ] A non-empty, unparseable stdin payload logs a `bad-payload` token
- [ ] No existing guard's allow/deny outcome changes for any payload
      that isn't one of the above new-denial cases — run the full
      existing `test_hook_handlers.py` file and confirm every
      previously-passing allow/deny assertion still passes
- [ ] The stale explanatory comment above `handle_hook`'s try/except
      (describing sprint 028 ticket 005's deliberate non-fail-closed
      scope) is updated to describe this ticket's actual behavior

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/test_hook_handlers.py`
  (scoped, foreground — this is the definitive regression check for
  this ticket; it must show zero changes to any pre-existing allow/deny
  test)
- **New tests to write**: the fault-injection test for the
  guard-crash exit-2 path (assert both the exit code and the log line);
  the `isinstance(tool_input, dict)` deny test; the mcp-guard
  tier-allowlist test; the `bad-payload` token test.
- **Verification command**: `uv run pytest tests/unit/test_hook_handlers.py -v`
  (scoped, foreground — do not run the full suite for this ticket).
  **Before considering this ticket done, also do a live sanity check**:
  make a trivial, reversible edit to a non-protected file (e.g. this
  ticket file itself) via the normal Edit path, and confirm role-guard
  still allows it — a fast, cheap confirmation that the armed boundary
  hasn't blocked ordinary work.
