---
id: '001'
title: Eager top-level imports in artifact_tools.py and preflight check
status: done
use-cases:
- SUC-001
depends-on: []
github-issue: ''
todo: fix-mcp-lazy-import-failures.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Eager top-level imports in artifact_tools.py and preflight check

## Description

When the CLASI MCP server starts from an older source snapshot, Python's
negative import cache causes `list_sprints`, `list_tickets`, and `list_todos`
to fail with `ModuleNotFoundError` for the life of the process. This happens
because `artifact_tools.py` imports `clasi.sprint`, `clasi.todo`, etc. lazily
inside function bodies rather than at module level.

This ticket moves all lazy imports in `artifact_tools.py` and `process_tools.py`
to the top of those modules so import failures surface at server startup. It also
adds a preflight check in `mcp_server.py` `run()` that catches import errors
before tool registration and prints a clear error banner. Finally, it enriches
`get_version` to return `metadata_version` and `source_path` so staleness is
detectable from a single call.

No functional changes to any tool's behavior. This is a structural refactor.

## Acceptance Criteria

- [ ] All `from clasi.{sprint,todo,artifact,ticket,versioning}` imports in
  `artifact_tools.py` are at the top of the module, not inside function bodies.
- [ ] The lazy `from clasi.frontmatter import read_frontmatter` in
  `process_tools.py` (around line 447) is moved to the top of that module.
- [ ] `mcp_server.py` `run()` includes a preflight block that attempts to import
  all required submodules before calling `self.server.run()`. On failure, it
  prints a clear error to stderr and aborts startup.
- [ ] `get_version` JSON response includes `metadata_version` (from
  `importlib.metadata`) and `source_path` (resolved path of the installed
  package) alongside the existing `version` field.
- [ ] All existing tests continue to pass.
- [ ] New unit test verifies `get_version` response contains the new keys.

## Implementation Plan

### Approach

Structural import promotion — no logic changes to existing tool behavior.

1. Use Grep to find all `from clasi.` lines inside function bodies in
   `artifact_tools.py`. Move each to the module-level imports block,
   deduplicating as needed.
2. Find the lazy `from clasi.frontmatter` import in `process_tools.py`
   and move it to the top of that file.
3. Add a preflight block in `mcp_server.py` `run()` — before
   `self.server.run(transport="stdio")` — that tries importing each required
   submodule and raises `SystemExit` with a clear message if any fail.
4. Update `get_version` in `process_tools.py` to call
   `importlib.metadata.version("clasi")` and use `importlib.util.find_spec`
   to resolve `source_path`.

### Files to modify

- `clasi/tools/artifact_tools.py` — promote ~15 lazy import sites to top-level
- `clasi/tools/process_tools.py` — promote frontmatter lazy import; enrich
  `get_version` return value
- `clasi/mcp_server.py` — add preflight import check in `run()`

### Files to create

None.

## Testing

- **Existing tests to run**: `uv run pytest tests/` — verify no regressions
  from import promotion.
- **New tests to write**:
  - In `tests/unit/test_process_tools.py` (or equivalent): call `get_version()`
    and assert the response JSON contains `version`, `metadata_version`, and
    `source_path` keys.
- **Verification command**: `uv run pytest`
