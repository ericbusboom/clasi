---
id: '001'
title: gh CLI helpers and list_github_issues MCP tool
status: done
use-cases:
- SUC-001
depends-on: []
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# gh CLI helpers and list_github_issues MCP tool

## Description

Add the foundation for GitHub issue sync: a private helper to verify
`gh` CLI access to a repo, and a new `list_github_issues` MCP tool that
wraps `gh issue list` to fetch open issues.

### Implementation

In `artifact_tools.py`:

1. **`_check_gh_access(repo: str | None) -> tuple[bool, str]`** — Runs
   `gh issue list --repo <repo> --limit 1 --json number` (or without
   `--repo` for the current repo). Returns `(True, repo_name)` on
   success or `(False, error_message)` on failure. The error message
   should include remediation steps (e.g., "Run `gh auth login`" or
   "Run `gh auth status` to check your authentication").

2. **`list_github_issues` MCP tool** — Registered with `@server.tool()`.
   Parameters: `repo` (optional str, defaults to current repo),
   `labels` (optional str, comma-separated), `state` (optional str,
   default "open"), `limit` (optional int, default 30).
   Calls `gh issue list --json number,title,body,labels,url` with
   appropriate flags. Returns JSON array of issue objects.
   Uses `_check_gh_access` first; returns an error result if access
   fails.

All `subprocess.run` calls must use list-form arguments (no `shell=True`).

## Acceptance Criteria

- [x] `_check_gh_access` returns success/failure with helpful messages
- [x] `_check_gh_access` handles missing `gh` binary (FileNotFoundError)
- [x] `list_github_issues` returns JSON array of `{number, title, body, labels, url}`
- [x] `list_github_issues` supports optional `repo`, `labels`, `state`, `limit` params
- [x] `list_github_issues` defaults to current repo when `repo` is omitted
- [x] `list_github_issues` returns error JSON when access check fails
- [x] All subprocess calls use list-form arguments

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/test_github_issue.py`
- **New tests to write**: `tests/unit/test_gh_import.py` — mock `subprocess.run`
  to test `_check_gh_access` (success, auth failure, missing binary) and
  `list_github_issues` (successful listing, filtering, access failure)
- **Verification command**: `uv run pytest`
