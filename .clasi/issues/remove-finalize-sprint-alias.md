---
status: pending
---

# Remove finalize_sprint MCP tool alias

The `finalize_sprint` tool was added in sprint 007 as a workaround for a suspected VS Code extension bug where `close_sprint` parameters were being dropped. Sprint 011 identified and fixed the actual root cause (pytest exit code 5 treated as test failure), making the alias obsolete.

## What to remove

- `finalize_sprint` function from `clasi/tools/artifact_tools.py`
- Any references to `finalize_sprint` in the close-sprint skill (`clasi/schemas/se-process/instructions/close.md`)
- Any documentation or comments referencing the alias as a workaround
- The `finalize_sprint` alias test added in sprint 007 (if it only tests the alias exists)

## What to keep

- The `close_sprint` tool itself
- The test for exit code 5 behavior added in sprint 011
- The ToolSearch step added in sprint 010 (still valid for deferred-tool schema loading)
