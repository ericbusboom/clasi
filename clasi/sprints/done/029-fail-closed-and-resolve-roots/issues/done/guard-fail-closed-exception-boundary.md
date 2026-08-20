---
status: done
type: bug
tags:
- reliability-campaign
- phase-1
- hooks
- enforcement
sprint: 029
tickets:
- 029-009
---

# Guards: fail-closed exception boundary — a crash must never be a silent allow

## Description

The Claude Code harness blocks a tool call only on hook exit code 2; a
crash, timeout, or spawn failure is an allow. CLASI's guard handlers have no
top-level exception boundary, so every unanticipated bug in a guard is an
unlogged allow. hooks.log contains 876 historical events from when
role-guard ran fail-open this way for weeks. From the reliability review
(00-review.md C1; 03-hooks-guards.md F1, F9, inventory rows 1, 2, 6, 10).

1. In `handle_hook` (`src/clasi/hook_handlers.py:1800-1835`), wrap the
   `role-guard`/`mcp-guard` dispatch in `try/except Exception`: log the
   traceback, then `_exit_hook(event, payload, 2, "guard-crash")`.
2. `isinstance(tool_input, dict)` check at the role-guard ingress.
3. mcp-guard tier check becomes an allowlist (`in ("1", "2")`) instead of
   `not in ("", "0")`.
4. Log a `bad-payload` token when stdin was non-empty but unparseable.

## Acceptance criteria

- A guard handler that raises produces exit 2 and a `guard-crash` log line
  with traceback — verified by a test that injects a fault.
- Malformed payload shapes (null tool_input, missing keys) deny rather than
  crash-allow, with distinct logged reasons.
- Unknown tier strings do not allow.
