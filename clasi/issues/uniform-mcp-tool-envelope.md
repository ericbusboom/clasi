---
status: pending
type: task
tags:
- reliability-campaign
- phase-2
- mcp
sprint: '030'
---

# MCP tools: one result envelope, owned NONE-sentinel stripping

## Description

The 34 artifact tools have a three-way inconsistent error contract: some
raise (surfacing as MCP tool errors), some return `{"error": ...}` inside a
success shape, `close_sprint` has its own third format, and `list_tickets`
returns `[]` for a typo'd sprint id. An agent cannot learn one rule for
"did it work". Separately, the `"NONE"` empty-args mitigation is installed
by monkey-patching three private MCP-library internals inside `run()` — a
library upgrade silently disables it, after which `"NONE"` strings flow
into frontmatter and `test_command="NONE"` becomes a literal command whose
failure silently skips the close test gate. From the reliability review
(02-mcp-tools.md F5, F6, F15).

## Acceptance criteria

- A `@clasi_tool` decorator wrapping `server.tool()` that (a) strips the
  `"NONE"` sentinel per-call in owned code, (b) anchors relative paths to
  `project.root` (shared with the Phase 1 path work), and (c) converts
  domain exceptions into a single `{"ok": false, "error": {...}}` shape.
- Every tool returns the uniform envelope; the monkey-patches are removed
  (the mcp-calls.jsonl trace from Phase 0 moves into the decorator).
- `list_tickets` on an unknown sprint id returns an error, not `[]`.
- `close_sprint` gains an explicit, working test-skip (`"SKIP"` sentinel or
  boolean), replacing the unreachable empty-string mechanism.
- Sentinel stripping is exercised by unit tests (no longer only reachable
  through the live server path).
