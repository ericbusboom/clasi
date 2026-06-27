---
id: '002'
title: Fix _close_sprint_full to be non-blocking on unresolved issues
status: done
use-cases:
- SUC-002
depends-on: []
github-issue: ''
issue: ''
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Fix _close_sprint_full to be non-blocking on unresolved issues

## Description

`_close_sprint_full` (the git-path sprint close used in VS Code) hard-fails with
an error JSON when any sprint-scoped issue remains `in-progress` and is not
marked as deferred. `_close_sprint_legacy` already handles this case
non-blocking: it collects issue filenames into `unresolved_issues` and continues
to close the sprint, adding `unresolved_issues` to the success result.

The two paths diverged. This ticket fixes `_close_sprint_full` to mirror the
legacy path: collect unresolved issue filenames, add them to the success result,
and continue. The `_issue_is_deferred` guard is preserved — deferred issues still
pass cleanly as before.

## Acceptance Criteria

- [x] `_close_sprint_full` does not return an error JSON when in-progress (non-deferred) sprint issues are present.
- [x] The success result includes `unresolved_issues: [...]` with the filenames of any unresolved issues.
- [x] Deferred issues (where `_issue_is_deferred` returns true) still pass cleanly — no change to that path.
- [x] Resolved issues (status: done/complete/completed) are still moved to `done/` via the self-repair path.
- [x] `_close_sprint_full` and `_close_sprint_legacy` exhibit identical behavior for unresolved issues.

## Implementation Plan

### Approach

Locate `_close_sprint_full` in `clasi/tools/artifact_tools.py`. Find the block
that currently does:

```python
# Issue is unresolved and not deferred — unrepairable
error_msg = f"Issue {issue_file.name} is still in-progress for sprint {sprint_id}"
if db.path.exists():
    db.write_recovery_state(...)
return json.dumps({"status": "error", ...})
```

Replace the hard-fail block with the collect-and-continue pattern from
`_close_sprint_legacy`. Declare `unresolved_issues: list[str] = []` before the
issue-scanning loop (if not already present in `_close_sprint_full`), then
substitute:

```python
# Issue is unresolved and not deferred — collect, do not block
unresolved_issues.append(issue_file.name)
```

After the scanning loop, add `unresolved_issues` to the result dict (mirroring
how `_close_sprint_legacy` does it):

```python
if unresolved_issues:
    result["unresolved_issues"] = unresolved_issues
```

Remove the `db.write_recovery_state` call for this case (it was only written to
enable recovery from the error, which no longer occurs).

Do NOT use line numbers to locate the code — locate by function name
`def _close_sprint_full(` and the comment `# Issue is unresolved and not deferred`.

### Files to Modify

- `clasi/tools/artifact_tools.py` — inside `_close_sprint_full`, the
  unresolved-issue hard-fail block.

### Testing Plan

- Run existing suite after the change:
  `pytest tests/unit/test_sweep_done_issues.py tests/unit/test_issue_lifecycle.py tests/unit/test_issue_tools.py tests/unit/test_mcp_server.py -q`
- New test cases are added in ticket 003.

### Documentation Updates

None for this ticket. Plugin doc changes are in tickets 004 and 005.
