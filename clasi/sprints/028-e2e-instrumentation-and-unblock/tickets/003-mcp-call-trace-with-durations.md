---
id: '003'
title: MCP call trace with durations
status: open
use-cases:
- SUC-003
depends-on: []
github-issue: ''
issue: mcp-call-trace-with-durations.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# MCP call trace with durations

## Description

`mcp-server.log` records `CALL`/`OK`/`FAIL` lines but no durations and
no machine-readable form, so "which tool call was slow or failed"
requires log archaeology. This ticket adds per-call timing to the
existing human log line and a parallel machine-readable JSONL trace. See
sprint.md's Architecture, module 3 ("MCP Call Trace") and SUC-003.

**Scope**: `src/clasi/mcp_server.py` only. Independent of every other
ticket in this sprint except ticket 006 (report assembly), which reads
this ticket's output but does not depend on its code.

**Key source location verified during sprint planning:**

`src/clasi/mcp_server.py:233-257` — `_logged_call_tool`, the wrapped
`_tm.call_tool` closure installed over `_tool_manager.call_tool`:

```python
async def _logged_call_tool(name, arguments, **kwargs):
    arguments = _strip_none_sentinel(arguments)
    args_summary = {...}
    logger.info("[%s] CALL %s(%s)", agent_name, name, json.dumps(args_summary))
    try:
        result = await _original_call_tool(name, arguments, **kwargs)
        result_str = str(result)
        ...
        logger.info("[%s]   OK %s -> %s", agent_name, name, result_str)
        return result
    except Exception as e:
        logger.error("[%s]   FAIL %s -> %s: %s", agent_name, name, type(e).__name__, e)
        raise
```

Wrap the `await _original_call_tool(...)` call in `time.monotonic()`
(start before the `try`, or immediately inside it before the `await`;
end in both the success and exception paths). Append the duration in ms
to the existing `OK`/`FAIL` log lines (`OK name (NNNms) -> ...`, `FAIL
name (NNNms) -> ...`). Append one JSON line per call — success and
failure alike — to `.clasi/log/mcp-calls.jsonl` with fields `ts, agent,
tool, args, ok, ms, result_len`:

- `ts`: ISO 8601 UTC timestamp (match the format `_log_hook_event` uses
  elsewhere in the codebase — `%Y-%m-%dT%H:%M:%SZ` — for consistency
  across CLASI's own logs).
- `agent`: the existing `agent_name` local variable this closure already
  captures.
- `tool`: the `name` parameter.
- `args`: reuse the existing `args_summary` dict already built for the
  human log line — no need to build a second summary.
- `ok`: `True`/`False`.
- `ms`: the measured duration, integer milliseconds.
- `result_len`: `len(result_str)` on success (already computed for the
  human log line); a sentinel (e.g. `0` or `null`) on failure, since
  there is no result string.

Reuse `_ensure_log_gitignore`-style handling — actually, `.clasi/log/`
already has an auto-gitignore mechanism established elsewhere in the
codebase (`hook_handlers._ensure_log_gitignore`); confirm at
implementation time whether `mcp_server.py`'s log directory setup
already benefits from it (it writes into the same `.clasi/log/`
directory) or needs its own call — do not duplicate the gitignore-write
logic if the directory is already covered.

## Acceptance Criteria

- [ ] Every MCP tool call (success and failure) appends one JSONL record
      to `.clasi/log/mcp-calls.jsonl` with `ts, agent, tool, args, ok,
      ms, result_len`.
- [ ] The existing human-readable `mcp-server.log` `OK`/`FAIL` lines
      include the call duration.
- [ ] `.clasi/log/mcp-calls.jsonl` is covered by the existing log-dir
      gitignore mechanism (verify, don't assume — add the call if it
      isn't already covered for this file).
- [ ] A unit test asserts the JSONL record shape for one successful call
      and one failing call.

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/test_mcp_server.py`
  (scoped, foreground) — confirms the wrap doesn't change
  `_logged_call_tool`'s existing success/failure/exception-propagation
  behavior.
- **New tests to write**: two tests in `tests/unit/test_mcp_server.py`
  (or a new file if that module's fixtures don't fit) — one asserting
  the JSONL record shape and field values for a successful call, one for
  a failing call (asserting `ok: False`, the exception still propagates
  to the caller unchanged, and `ms`/`result_len` are sane). Assert the
  human log line contains a duration substring (e.g. a regex on `\(\d+ms\)`).
- **Verification command**: `uv run pytest tests/unit/test_mcp_server.py -v`
  (scoped, foreground — do not run the full suite for this ticket).
