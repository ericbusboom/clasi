---
id: '011'
title: Add optional MCP tool wrapping reconcile_worktrees
status: done
use-cases:
- SUC-003
depends-on:
- '007'
github-issue: ''
issue: plan-re-enable-git-worktree-based-parallel-ticket-execution-in-clasi.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Add optional MCP tool wrapping reconcile_worktrees

## Description

Issue A Chunk 6 — optional but recommended; depends only on ticket 007
(the function it wraps). Independent of tickets 009/010 (execution.md) —
this is a standalone on-demand entry point, not part of the automated
controller flow, so it can be implemented in parallel with 009/010 once
007 is done.

Add a thin MCP tool to `src/clasi/tools/artifact_tools.py` (co-locate
near `_prune_sprint_worktrees` / `close_sprint` for discoverability,
consistent with where other sprint-lifecycle tools live) wrapping
`clasi.worktree.reconcile_worktrees`:

```python
@server.tool()
def reconcile_worktrees(sprint_id: str) -> str:
    """Reconcile worktree state for a sprint on demand.

    Resolves the sprint's directory and repo root, calls
    clasi.worktree.reconcile_worktrees, and returns the
    cleaned/escalated/rogue summary as JSON. Read-mostly: auto-cleans
    the two safe classes (merged-not-cleaned, clean-but-abandoned) and
    returns ambiguous cases for the caller to act on. Safe to call at
    any time, from any session — not only from within execute-sprint.
    """
```

Resolve `sprint_dir` via `get_project().get_sprint(sprint_id).path` and
`repo_root` via the project root (consistent with how other tools in
this file resolve these paths — check `close_sprint`/
`review_sprint_pre_close` for the established pattern before writing new
resolution logic). Do not add any new permission/role-guard exemption
beyond what other read-mostly MCP tools already have — this tool is
available to whichever tier already calls MCP tools in this file (tier 0
via the general MCP surface, since it's a read-mostly diagnostic/cleanup
tool comparable to `get_sprint_phase`, not an artifact-creation tool
gated by `handle_mcp_guard`). Confirm `handle_mcp_guard`'s tool-name list
(if any) does not need to add this — it currently blocks only
artifact-creation tools like `create_sprint`/`create_ticket`.

Name confusion note (per architecture-update.md Open Question #2):
naming this MCP tool identically to the module-level function
(`reconcile_worktrees`) is acceptable — MCP tool names and Python
function names live in different namespaces already throughout this
codebase (e.g. `create_sprint` the MCP tool vs. `Project.create_sprint`
the method). No disambiguating rename is required.

## Acceptance Criteria

- [x] A new `@server.tool()` function `reconcile_worktrees(sprint_id)`
      exists in `artifact_tools.py`, returning JSON with `cleaned`,
      `escalated`, `rogue` keys (the same shape as the underlying
      `worktree.reconcile_worktrees`).
- [x] The tool correctly resolves `sprint_dir`/`repo_root` for a given
      `sprint_id` using the existing project/sprint resolution pattern.
- [x] The tool is callable from a plain team-lead/interactive session
      (not blocked by `handle_mcp_guard`) — confirm by inspecting
      `handle_mcp_guard`'s routing/tool-name checks and adding this tool
      name to any allow-list only if the guard is allow-list-based (it
      currently appears to be tier-based, not tool-name-based, for the
      role it blocks — verify before assuming a change is needed).
- [x] Calling the tool on a sprint with a stale, clean, abandoned
      worktree cleans it and reports it in the response.
- [x] Calling the tool on a sprint with an ambiguous (dirty/failed)
      worktree does not touch it and reports it in `escalated`.

## Files to create or modify

- `src/clasi/tools/artifact_tools.py` — add the `reconcile_worktrees`
  MCP tool.

## Testing

- **Existing tests to run**: `tests/system/test_artifact_tools.py`, full
  `uv run pytest`.
- **New tests to write**: an MCP-tool-level test (matching the style of
  existing tool tests in `tests/system/test_artifact_tools.py`) calling
  the new `reconcile_worktrees` tool against a fixture sprint with a
  mix of safe-to-clean and ambiguous worktrees, asserting the JSON
  response shape and that only the safe ones were cleaned.
- **Verification command**: `uv run pytest`
