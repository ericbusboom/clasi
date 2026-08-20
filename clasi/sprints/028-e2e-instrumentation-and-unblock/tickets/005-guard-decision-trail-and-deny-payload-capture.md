---
id: '005'
title: Guard decision trail and deny-payload capture
status: open
use-cases:
- SUC-005
depends-on: []
github-issue: ''
issue: guard-decision-trail-and-deny-payload-capture.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Guard decision trail and deny-payload capture

## Description

`hooks.log` answers *what* was decided but not *why*, and the failure
paths log nothing at all today. This ticket adds decision-trail tokens
to the existing log line, dumps a replayable payload for every denial,
and routes the plan-mode handlers through the shared logging helper so
their events stop being invisible. See sprint.md's Architecture, module
5 ("Guard Decision Trail") and SUC-005.

**Scope**: `src/clasi/hook_handlers.py` only. Independent of every other
ticket except ticket 006 (report assembly), which reads this ticket's
output but does not depend on its code.

**Hard scope boundary — read before starting**: this sprint is
observability-only. **Do not change what any guard allows or denies.**
In particular, the issue's "on guard-internal exceptions" clause must
NOT be implemented as a fail-closed fix — that is a *different*, larger
change (forcing a crashing guard to exit 2) that the reliability
review's Phase 1 (sprint 029, "fail-closed exception boundary") owns.
This ticket only makes a crash *observable*: catch, log + dump payload,
then **re-raise the original exception unchanged** so the program's
eventual exit code and stderr traceback are bit-for-bit identical to
today's behavior. Do not add `sys.exit(2)` or any new `_exit_hook(...,
2, ...)` call on the exception path — that belongs to sprint 029, not
this ticket. If you find yourself writing code that changes whether a
tool call proceeds after a guard crash, stop — you've drifted into
Phase 1's scope.

**Key source locations verified during sprint planning:**

- `src/clasi/hook_handlers.py:299-368` — `_log_hook_event(event_type,
  payload, exit_code, reason)`, the function that writes the single
  `hooks.log` line. Add an optional `decisions: list[str] | None =
  None` parameter; append the tokens (space-joined, matching the
  existing `key_fields` join style at line 363) after the existing
  fields on the line, so a call with no tokens produces exactly today's
  line shape.
- `src/clasi/hook_handlers.py:371-377` — `_exit_hook(event_type,
  payload, exit_code, reason)` calls `_log_hook_event` then
  `sys.exit(exit_code)`. Add the same optional `decisions` parameter,
  passed through.
- Deny-payload dump: inside `_log_hook_event`, when `exit_code == 2`,
  write the full `payload` dict as JSON to
  `.clasi/log/denied/<ts>-<hook>.json` (`<hook>` = `event_type`, `<ts>`
  matching the line's own timestamp format for correlation). The
  `denied/` directory needs the same `_ensure_log_gitignore` treatment
  already applied to `log_dir` at line 332 — call it for the `denied/`
  subdirectory too (it may contain live payload data, same sensitivity
  class as the transcripts the existing gitignore comment already
  flags).
- `src/clasi/hook_handlers.py:464-619` (`handle_role_guard`) — has a
  local `_exit(code, reason)` closure at lines 612-619 that every check
  in the function already calls to terminate. Add a `decisions:
  list[str] = []` local at the top of `handle_role_guard`, have each
  check append its own token as it evaluates (e.g. `tier=2(db)`,
  `match=clasi/issues/`, `gate=ticket-state:skipped(db-error)`,
  `missing=[file_path]` — match the informal style sprint.md's Design
  Rationale documents), and pass `decisions=decisions` through the local
  `_exit` closure to `_exit_hook`.
- `src/clasi/hook_handlers.py:926-990` (`handle_mcp_guard`) — no local
  `_exit` closure here; it calls `_exit_hook("mcp-guard", payload, ...)`
  directly at four call sites (934, 958, 978, 986). Thread a `decisions`
  list through the function body the same way, passed explicitly at each
  of those four call sites.
- **Plan handlers — the issue's `handle_plan_guard` name does not exist
  in the current codebase.** The actual two plan handlers are
  `handle_plan_to_issue` (`hook_handlers.py:1717-1765`, used for both
  `plan-to-issue` and its `plan-to-todo` alias) and
  `handle_codex_plan_to_issue` (`hook_handlers.py:1679-1710`, used for
  both `codex-plan-to-issue` and its `codex-plan-to-todo` alias). Both
  currently call raw `sys.exit(0)`/`sys.exit(2)` and never call
  `_log_hook_event`/`_exit_hook` — confirmed zero `plan-to-issue`-family
  lines exist in `hooks.log` today. Replace their raw `sys.exit(...)`
  calls with `_exit_hook("plan-to-issue", payload, <code>, <reason>)`
  (and the codex equivalent with its own event name), choosing short
  reason codes consistent with the module's existing 12-char convention
  (e.g. `no-plan-tag`, `saved`, `no-file`, `rewrite-req`). **Do not**
  touch `plan_to_issue.py`'s missing-`planFilePath` fallback logic (the
  "delete the newest file in `~/.claude/plans`" behavior) — that is a
  separate, already-filed issue
  (`hook-payload-typed-ingress-and-replay-corpus.md`) and out of scope
  here; this ticket only adds logging around the existing behavior.

## Acceptance Criteria

- [ ] `_log_hook_event`/`_exit_hook` accept an optional `decisions:
      list[str]` parameter; a call with none produces an unchanged log
      line (verify against a snapshot of today's line format).
- [ ] `handle_role_guard` accumulates decision tokens across its checks
      and passes them through on every exit path.
- [ ] `handle_mcp_guard` accumulates decision tokens across its checks
      and passes them through on every exit path.
- [ ] Every `hooks.log` line for a decision that has tokens carries those
      tokens; every guard decision line (allow or deny) is covered by at
      least one token.
- [ ] Every denial (`exit_code == 2`) writes the full hook payload to
      `.clasi/log/denied/<ts>-<hook>.json`.
- [ ] `.clasi/log/denied/` gets its own `.gitignore` via the existing
      `_ensure_log_gitignore` mechanism.
- [ ] `handle_plan_to_issue` and `handle_codex_plan_to_issue` are routed
      through `_exit_hook` (not raw `sys.exit`), so `plan-to-issue`/
      `codex-plan-to-issue` events appear in `hooks.log` for the first
      time.
- [ ] A guard-internal exception (in `handle_role_guard` or
      `handle_mcp_guard`) is caught, logged (with a payload dump, same
      as any other denial-class event), and **re-raised unchanged** —
      the program's final exit code and stderr traceback are identical
      to current (pre-ticket) behavior. No new fail-closed logic.
- [ ] No existing guard's allow/deny outcome changes for any payload
      that isn't a guard-internal crash.

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/test_hook_handlers.py`
  (scoped, foreground) — this is the module's largest test file and
  covers `handle_role_guard`/`handle_mcp_guard`'s existing allow/deny
  behavior; a regression here would mean this ticket accidentally
  changed guard behavior, which is the one thing it must not do.
- **New tests to write**:
  - Decision-token emission for at least one allow path and one deny
    path in `handle_role_guard`, and at least one in `handle_mcp_guard`
    (explicit acceptance criteria from the issue).
  - A denial writes a payload file to `.clasi/log/denied/` with the
    expected content, for at least one guard.
  - A guard-internal exception (inject one via a mock/monkeypatch) is
    logged with a payload dump, and the original exception still
    propagates with an unchanged exit code — assert this explicitly, it
    is the ticket's most important non-functional guarantee.
  - `handle_plan_to_issue`/`handle_codex_plan_to_issue` write a
    `hooks.log` line for both their success and no-op paths (previously
    zero lines existed for either).
- **Verification command**: `uv run pytest tests/unit/test_hook_handlers.py -v`
  (scoped, foreground — do not run the full suite for this ticket).
