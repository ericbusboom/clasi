---
id: "002"
title: "Strip Agent.dispatch() and SDK methods from agent.py"
status: done
use-cases: ["SUC-002"]
depends-on: ["001"]
github-issue: ""
todo: ""
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Strip Agent.dispatch() and SDK methods from agent.py

## Description

`clasi/agent.py` contains `Agent.dispatch()` (~line 313), `_build_role_guard_hooks()`
(~line 188), and `_build_retry_prompt()` (~line 242). All three wrap `claude_agent_sdk`
functionality. With `dispatch_tools.py` gone (ticket 001), these methods have no callers.
Removing them makes `agent.py` a pure content-loading and template-rendering module.

The class hierarchy (`Agent`, `MainController`, `DomainController`, `TaskWorker`) and all
read-only properties (`name`, `tier`, `model`, `definition`, `contract`, `allowed_tools`,
`delegates_to`, `has_dispatch_template`, `render_prompt()`) are retained intact.

The module-level docstring describes the 7-step dispatch lifecycle and must be replaced
with a concise description of the module's remaining purpose.

## Acceptance Criteria

- [x] `Agent.dispatch()` method is removed from `clasi/agent.py`.
- [x] `Agent._build_role_guard_hooks()` method is removed.
- [x] `Agent._build_retry_prompt()` method is removed.
- [x] No import of `claude_agent_sdk` remains anywhere in `agent.py` (including lazy/conditional imports inside removed methods).
- [x] The module-level docstring is updated to describe the content-loading purpose only.
- [x] `render_prompt()`, `definition`, `contract`, `tier`, `model`, and all other read-only properties continue to function correctly.
- [x] `uv run pytest tests/unit/test_agent.py -k "not sdk and not dispatch and not role_guard and not retry"` passes.

## Implementation Plan

### Approach

Edit `clasi/agent.py`:
1. Replace the module-level docstring (lines 1-85) with a short description: module loads
   agent definitions, contracts, and dispatch templates; no dispatch execution.
2. Remove the `_build_role_guard_hooks()` method (~lines 188-240) including its nested
   `role_guard_hook` async function.
3. Remove the `_build_retry_prompt()` method (~lines 242-311).
4. Remove the `dispatch()` method (~lines 313-567).
5. Remove any top-level imports used only by the removed methods. Check: `os` (used by
   `dispatch()` env building — can be removed), `logging` (still used by `logger` —
   retain if `logger` is used elsewhere; otherwise remove).
6. Verify `TYPE_CHECKING` import block still compiles cleanly.

### Files to Create / Modify

- **Edit**: `clasi/agent.py`

### Testing Plan

- `uv run pytest tests/unit/test_agent.py -k "not sdk and not dispatch and not role_guard and not retry"` — passes.
- Manual: `python -c "from clasi.agent import Agent; print('ok')"` — no import errors.
- SDK-mock tests in `test_agent.py` will fail until ticket 006 removes them — expected.

### Documentation Updates

Module docstring updated inline. No other documentation changes at this ticket.
