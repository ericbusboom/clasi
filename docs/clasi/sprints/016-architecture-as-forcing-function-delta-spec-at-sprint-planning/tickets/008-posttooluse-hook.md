---
id: "016-008"
title: "PostToolUse hook: validate-on-write for architecture-delta.md"
status: todo
use-cases: [SUC-004]
depends-on: ["016-002"]
---

# 016-008: PostToolUse hook — validate-on-write for architecture-delta.md

## Description

Add a PostToolUse hook in `clasi/hook_handlers.py` that fires when the Write
or Edit tool produces a file matching `**/architecture-delta.md`. The hook
calls the parser and surfaces any errors as hook output — it does NOT block
the write (report-only).

Register this hook in the Claude platform installer so it is active in all
CLASI-enabled Claude Code sessions.

## Acceptance Criteria

- [ ] A PostToolUse handler exists in `clasi/hook_handlers.py` that:
  - Fires when the output file path matches `**/architecture-delta.md`.
  - Calls `clasi.delta.parse.parse(file_content)`.
  - On success: prints `"architecture-delta.md validation: OK — N items parsed."`.
  - On `DeltaParseError`: prints
    `"architecture-delta.md validation: ERROR — Line N: [rule] message"`.
  - Does NOT block the write (exits 0 in either case; validation errors go
    to stdout, not a non-zero exit code that would interrupt the agent).
- [ ] The hook is registered in `clasi/platforms/claude.py` as a PostToolUse
  hook for the Write and Edit tools, scoped to `**/architecture-delta.md`.
- [ ] After `clasi install` is run on a project, the installed
  `.claude/settings.json` (or hook config) includes this hook.
- [ ] All tests pass (hook handler unit tests).

## Implementation Plan

### Approach

Add `handle_architecture_delta_validate(event: dict) -> None` to
`clasi/hook_handlers.py`. The handler extracts the file path from the event,
reads the file content, and calls `parse()`. Register in `claude.py` settings
template.

### Files to Create/Modify

- `clasi/hook_handlers.py` (modify: add handler)
- `clasi/platforms/claude.py` (modify: register PostToolUse hook)
- `tests/unit/test_hook_handlers.py` (modify: add tests for new handler)

### Testing Plan

- Test handler with a valid delta string: assert output contains "OK".
- Test handler with an invalid delta: assert output contains "ERROR".
- Test that a non-`architecture-delta.md` path does not trigger the handler.

### Documentation Updates

None — behavior is self-evident from the hook output.
