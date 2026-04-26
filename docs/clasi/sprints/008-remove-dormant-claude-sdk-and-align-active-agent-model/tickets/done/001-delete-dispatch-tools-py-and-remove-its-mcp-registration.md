---
id: '001'
title: Delete dispatch_tools.py and remove its MCP registration
status: done
use-cases: ["SUC-001"]
depends-on: []
github-issue: ''
todo: remove-dormant-sdk.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Delete dispatch_tools.py and remove its MCP registration

## Description

`clasi/tools/dispatch_tools.py` contains 12 `dispatch_to_X` async functions that wrap
`Agent.dispatch()` / `claude_agent_sdk.query()`. These are imported in `mcp_server.py`
(line 140) and registered as MCP tools, but no active CLASI agent calls them — the
current skill-based model runs agents inline. Deleting this file and removing its import
from `mcp_server.py` eliminates the SDK from the server's import graph entirely.

## Acceptance Criteria

- [x] `clasi/tools/dispatch_tools.py` is deleted.
- [x] The line `import clasi.tools.dispatch_tools  # noqa: F401` is removed from `clasi/mcp_server.py`.
- [x] `uv run pytest tests/unit/test_mcp_server.py` passes.
- [x] Starting the MCP server no longer causes `claude_agent_sdk` to appear in `sys.modules`.

## Implementation Plan

### Approach

Pure deletion and a one-line edit. No logic changes elsewhere.

### Files to Create / Modify

- **Delete**: `clasi/tools/dispatch_tools.py`
- **Edit**: `clasi/mcp_server.py` — remove line `import clasi.tools.dispatch_tools  # noqa: F401`

### Testing Plan

- Run `uv run pytest tests/unit/test_mcp_server.py` to confirm server startup tests pass.
- `tests/unit/test_dispatch_tools.py` will fail after this ticket (module is gone) — skip
  it during this ticket's validation with `--ignore=tests/unit/test_dispatch_tools.py`.
  It is deleted in ticket 006.
- Run `grep -r "dispatch_tools" tests/ --include="*.py"` to confirm no other test file
  imports from the deleted module.

### Documentation Updates

None at this ticket. Architecture update is already written; README is addressed in ticket 007.
