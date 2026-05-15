---
id: 004-005
title: Update MCP hot-reload list and verify close_sprint end-to-end JSON shape
status: done
use-cases:
- SUC-005
- SUC-002
depends-on:
- 004-002
- 004-004
issue:
- migrate-clasi-versioning-to-depend-on-dotconfig.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# 004-005: Update MCP hot-reload list and verify close_sprint end-to-end JSON shape

## Description

After the shim lands (ticket 002) and tests are migrated (ticket 004), this ticket
confirms the MCP server hot-reload list is correct and that the `close_sprint` tool
produces the same JSON shape as before the refactor. The hot-reload list entry for
`clasi.versioning` should stay because the shim module still exists. If anything
in the shim's import chain breaks the preflight, it is caught here.

## Acceptance Criteria

- [x] `clasi/mcp_server.py` preflight list at line 126 still contains `"clasi.versioning"`.
- [x] Starting the MCP server (`python -m clasi.mcp_server` or via `clasi` CLI) 
      produces no preflight import errors.
- [x] `close_sprint` returns JSON with `version` and `tag` fields populated
      (verified by reading `_close_sprint_full` return shape in the source or via
      an existing integration test).
- [x] Full test suite passes (`pytest`).
- [x] No version regression: the format scheme `0.YYYYMMDD.R+` produces the
      same output for the same inputs via the shim as it did before.

## Implementation Plan

### Approach

This ticket is primarily verification, with a small targeted code change only if
the preflight fails.

**Step 1: Verify MCP preflight**

Read `clasi/mcp_server.py` lines 124-138. Confirm `"clasi.versioning"` is in the
`_required` list. Since the shim module still exists at the same import path, no
change should be needed. If the preflight import fails (e.g., because the shim
has an import-time error), fix the shim.

**Step 2: Confirm hot-reload entry**

If `clasi.versioning` is in the preflight list and the module is importable, the
hot-reload behavior is unchanged. No code edit needed.

**Step 3: Verify `close_sprint` JSON shape**

Locate `_close_sprint_full` in `artifact_tools.py`. Read the `version_bump` step
(lines ~1391-1411). Confirm the result dict includes:
- `"version"` — populated by `compute_next_version()`
- `"tag"` — populated by `create_version_tag()`

These should be unchanged since `artifact_tools.py` is not modified. The check
is a reading exercise, not a code change — unless the shim introduced a regression.

**Step 4: Run the full test suite**

`pytest` — all tests must pass. This is the final integration gate for the sprint.

**Step 5: Version format smoke test**

If an integration test environment is available (git repo with tags):
```python
from clasi.versioning import compute_next_version
v = compute_next_version()
# Should match 0.YYYYMMDD.N pattern
import re
assert re.match(r"^\d+\.\d{8}\.\d+$", v), f"Bad version: {v}"
```

### Files to Modify

- `clasi/mcp_server.py` — only if preflight entry needs adjustment (expected: no change)

### Testing Plan

1. `pytest` — full suite, no failures.
2. Manual MCP server startup check (if test environment allows).
3. Version format smoke test above.

### Documentation Updates

None.
