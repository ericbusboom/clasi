---
id: '001'
title: Remove finalize_sprint alias
status: done
use-cases:
- SUC-015-003
depends-on: []
github-issue: ''
issue: remove-finalize-sprint-alias.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Remove finalize_sprint alias

## Description

The `finalize_sprint` MCP tool was added in sprint 007 as a diagnostic alias for `close_sprint`,
to isolate whether the VS Code extension was dropping parameters based on the tool name. Sprint 011
fixed the root cause. The alias is now dead weight: it duplicates the MCP surface, confuses the
tool registry, and requires a test file that exists solely to verify an alias.

Remove the alias and all associated test/registry entries.

## Acceptance Criteria

- [x] The `finalize_sprint` function (lines ~1014–1030 in `clasi/tools/artifact_tools.py`) is deleted.
- [x] `tests/unit/test_finalize_sprint_alias.py` is deleted entirely.
- [x] `tests/unit/test_mcp_server.py`: `"finalize_sprint"` is removed from `EXPECTED_ARTIFACT_TOOLS` and the expected tool count is decremented accordingly.
- [x] `clasi/plugin/skills/close-sprint/SKILL.md` contains no references to `finalize_sprint`.
- [x] `uv run pytest -q` passes with no regressions.
- [x] `close_sprint` behavior is unchanged.

## Implementation Plan

### Approach

Pure subtraction: delete the function, delete the test file, update the tool registry test,
scan for any remaining doc references.

### Files to modify

1. **`clasi/tools/artifact_tools.py`**: Delete the `finalize_sprint` function block
   (`@server.tool()` decorator + function body). It appears immediately after `close_sprint`,
   currently around line 1014–1030. Do not touch `close_sprint` itself.

2. **`tests/unit/test_finalize_sprint_alias.py`**: Delete this file entirely.

3. **`tests/unit/test_mcp_server.py`**: In `EXPECTED_ARTIFACT_TOOLS`, remove `"finalize_sprint"`.
   Also update `test_tool_count` if it has a hardcoded count assertion.

4. **`clasi/plugin/skills/close-sprint/SKILL.md`**: Check for and remove any `finalize_sprint`
   references (the current file has none — verify before touching).

5. **Scan for stray references**: `grep -rn finalize_sprint clasi/ tests/` — remove or update
   any remaining references found.

### Testing plan

- Run `uv run pytest -q` after each file change to catch regressions early.
- Confirm `test_mcp_server.py::test_no_unexpected_tools` and `test_all_expected_tools_registered`
  both pass.
- Confirm `test_close_sprint_*` tests still pass.

### Documentation updates

No documentation changes beyond the SKILL.md scan above.
