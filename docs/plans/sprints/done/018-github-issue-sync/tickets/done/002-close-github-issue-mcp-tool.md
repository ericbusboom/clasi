---
id: "002"
title: "close_github_issue MCP tool"
status: done
use-cases:
  - SUC-003
depends-on:
  - "001"
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# close_github_issue MCP tool

## Description

Add a new `close_github_issue` MCP tool that wraps `gh issue close` to
close a specific GitHub issue. Used by the close-sprint skill to close
all linked issues when a sprint completes.

### Implementation

In `artifact_tools.py`:

**`close_github_issue` MCP tool** — Registered with `@server.tool()`.
Parameters: `repo` (optional str, defaults to current repo),
`issue_number` (int).

Validation: `issue_number` must be a positive integer. Return error
JSON immediately if not.

Calls `gh issue close <number> --repo <repo>`. Returns JSON with
`{issue_number, repo, closed: true}` on success or
`{issue_number, repo, closed: false, error: "..."}` on failure.

Uses `_check_gh_access` from ticket #001 before attempting the close.

## Acceptance Criteria

- [x] `close_github_issue` validates `issue_number` is a positive integer
- [x] `close_github_issue` closes the issue via `gh issue close`
- [x] Returns success JSON on successful close
- [x] Returns error JSON (without raising) on failure
- [x] Checks `gh` access before attempting close
- [x] Subprocess calls use list-form arguments

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/test_github_issue.py`
- **New tests to write**: Add to `tests/unit/test_gh_import.py` — mock
  `subprocess.run` to test `close_github_issue` (success, failure,
  invalid issue number, access failure)
- **Verification command**: `uv run pytest`
