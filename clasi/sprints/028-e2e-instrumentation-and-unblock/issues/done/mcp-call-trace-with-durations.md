---
status: done
type: feature
tags:
- reliability-campaign
- phase-0
- mcp
- observability
sprint: 028
tickets:
- 028-003
---

# MCP server: machine-readable per-call trace with durations

## Description

`mcp-server.log` records CALL/OK/FAIL lines but no durations and no
machine-readable form, so "which tool call was slow or failed" requires log
archaeology. From the reliability review (05-e2e-test-infra.md
instrumentation plan item 3).

In `_logged_call_tool` (`src/clasi/mcp_server.py:237-257`): wrap the await
in `time.monotonic()`, log `OK name (NNNms)`, and append one JSON line per
call to `.clasi/log/mcp-calls.jsonl` with
`ts, agent, tool, args, ok, ms, result_len`.

Note: this touches the same monkey-patched call path that the Phase 2
uniform-tool-envelope issue replaces; keep the trace emission in a helper
that survives that refactor.

## Acceptance criteria

- Every MCP tool call appends one JSONL record with the fields above.
- The human-readable log line includes the duration.
- The JSONL file is covered by the existing log-dir gitignore mechanism.
- A unit test asserts the record shape for one success and one failure.
