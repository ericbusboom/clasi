---
status: done
type: bug
tags:
- reliability-campaign
- phase-1
- mcp
- git
sprint: 029
tickets:
- 029-005
---

# Tools layer: one root-anchored git helper; artifact paths resolve against project root

## Description

Most git subprocesses in the tools layer run with no `cwd=`, silently
operating on whatever directory the MCP server process happens to sit in;
`_close_sprint_full` is internally inconsistent (some calls pass
`cwd=project.root`, branch detection/merge/tag-push/prune do not). Relative
artifact paths in `resolve_artifact_path` resolve against process cwd, so a
root-relative ticket path can produce "Ticket not found" for a file that
exists. Bare `git commit -m` also sweeps whatever the user had staged into
CLASI's chore commits. From the reliability review (00-review.md C6;
02-mcp-tools.md F3, F4, F7; 04-cli-install-platforms.md F15 cwd note).

## Acceptance criteria

- One `run_git(args, cwd=project.root)` helper used by every git call in
  the tools layer, `sprint.py`, and `design/overlay.py`; no bare
  `subprocess` git invocations remain there.
- CLASI commits use explicit pathspecs (`git commit -m msg -- <paths>`) so
  a user's pre-staged files are never swept in.
- `resolve_artifact_path` anchors relative paths to `project.root`.
- Versioning helpers (`compute_next_version`, `_get_existing_tags`) take an
  explicit `project_root` instead of implicit cwd.
- A test runs a representative tool with cwd set elsewhere and asserts
  correct behavior.
