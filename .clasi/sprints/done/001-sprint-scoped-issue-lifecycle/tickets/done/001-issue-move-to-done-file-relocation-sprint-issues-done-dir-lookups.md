---
id: '001'
title: Issue.move_to_done file relocation + Sprint.issues_done_dir + lookups
status: done
use-cases:
- SUC-001
- SUC-002
depends-on: []
github-issue: ''
issue: plan-sprint-scoped-issue-lifecycle-sprint-issues-done-split-close-gate.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Issue.move_to_done file relocation + Sprint.issues_done_dir + lookups

## Description

Rewrite `Issue.move_to_done` to physically relocate the issue file into a `done/` subdirectory (mirroring `Ticket.move_to_done`). Add `Sprint.issues_done_dir` property. Update `Sprint.list_issues` and `Project.get_issue` to look in both `issues/` and `issues/done/`. Relax the location guard in the `move_issue_to_done` MCP tool to accept both directories (idempotent case). Update and extend tests.

This is the foundational ticket. T2, T3, and T4 depend on it.

## Acceptance Criteria

- [x] `Issue.move_to_done()` on a sprint-scoped issue renames the file from `<sprint>/issues/<f>` to `<sprint>/issues/done/<f>`, creating `done/` if needed.
- [x] `Issue.move_to_done()` is idempotent: calling it a second time when the file is already in `done/` (parent dir name is `"done"`) is a no-op — no error, no second rename.
- [x] `Issue.move_to_done()` on a pending-pool issue moves it to `.clasi/issues/done/<f>`.
- [x] After `move_to_done`, `issue.path` reflects the new location and `issue.status == "done"`.
- [x] `Sprint.issues_done_dir` property returns `sprint._path / "issues" / "done"`.
- [x] `Sprint.list_issues()` returns `Issue` objects from both `issues/` and `issues/done/`, in sorted order.
- [x] `Project.get_issue(filename)` resolves filenames in `<sprint>/issues/done/` (after checking pending pool and `<sprint>/issues/`).
- [x] `move_issue_to_done` MCP tool: when `sprint_id` is given and the issue is already in `<sprint>/issues/done/`, the call succeeds rather than raising a location mismatch error.
- [x] Tests in `TestIssueMoveToDone` updated: `test_move_to_done_file_location_unchanged` → asserts file moves to `done/`; `test_move_to_done_no_done_dir_created` → removed; `test_move_to_done_sprint_in_issues_dir` → asserts file moves to `<sprint>/issues/done/`.
- [x] New tests added: idempotent `move_to_done`, pool-issue `move_to_done`, `issues_done_dir` property, `list_issues` scanning both dirs, `get_issue` resolving done-dir.
- [x] `uv run pytest tests/unit/test_issue.py tests/unit/test_issue_lifecycle.py` passes.
- [x] `uv run pytest` (full suite) passes.

## Implementation Plan

### clasi/issue.py — rewrite `move_to_done` (lines 86-105)

Model: `Ticket.move_to_done` at `clasi/ticket.py:127-141`.

New implementation:
```python
def move_to_done(
    self,
    sprint_id: str | None = None,
    ticket_ids: list[str] | None = None,
) -> None:
    """Move issue file to done/ subdirectory and update frontmatter.

    If the file is already in a directory named 'done', this is
    idempotent: frontmatter is updated but the file is not moved again.
    """
    if self.path.parent.name != "done":
        done_dir = self.path.parent / "done"
        done_dir.mkdir(parents=True, exist_ok=True)
        new_path = done_dir / self.path.name
        self.path.rename(new_path)
        self._artifact = Artifact(new_path)

    if sprint_id is not None:
        self._artifact.update_frontmatter(sprint=sprint_id)
    if ticket_ids is not None:
        self._artifact.update_frontmatter(tickets=ticket_ids)
    self._artifact.update_frontmatter(status="done")
```

### clasi/sprint.py — add `issues_done_dir`, extend `list_issues`

After the `issues_dir` property (line 143-146), add:
```python
@property
def issues_done_dir(self) -> Path:
    """Path to the issues/done/ directory within this sprint."""
    return self._path / "issues" / "done"
```

Replace `list_issues` (lines 168-182) with:
```python
def list_issues(self) -> list:
    """List Issue objects from issues/ and issues/done/ directories."""
    from clasi.issue import Issue

    results: list = []
    for location in [self.issues_dir, self.issues_done_dir]:
        if not location.exists():
            continue
        for f in sorted(location.glob("*.md")):
            results.append(Issue(f, self._project))
    return results
```

### clasi/project.py — extend `get_issue` (lines 225-229)

In the per-sprint loop, add `issues/done/` check:
```python
for sprint in self.list_sprints():
    path = sprint.path / "issues" / filename
    if path.exists():
        return Issue(path, self)
    path = sprint.path / "issues" / "done" / filename
    if path.exists():
        return Issue(path, self)
```

### clasi/tools/artifact_tools.py — relax location guard in `move_issue_to_done`

Change the `expected_dir` check (lines 1519-1526) from:
```python
expected_dir = sprint.path / "issues"
if todo.path.parent.resolve() != expected_dir.resolve():
    raise ValueError(...)
```
To:
```python
expected_dirs = {
    (sprint.path / "issues").resolve(),
    (sprint.path / "issues" / "done").resolve(),
}
if todo.path.parent.resolve() not in expected_dirs:
    raise ValueError(
        f"Issue '{filename}' is not in the expected sprint issues "
        f"directory or its done/ subdirectory. "
        f"Current location: '{todo.path.parent}'. "
        "Run move_todo_to_in_progress first."
    )
```

### tests/unit/test_issue.py — update `TestIssueMoveToDone`

- Remove `test_move_to_done_file_location_unchanged` (asserted old behavior).
- Remove `test_move_to_done_no_done_dir_created` (done dir is now created).
- Update `test_move_to_done_sprint_in_issues_dir`: assert `t.path.parent == sprint_dir / "issues" / "done"`.
- Add `test_move_to_done_moves_to_done_dir`: issue in pool; after `move_to_done()`, asserts `t.path.parent.name == "done"` and file exists.
- Add `test_move_to_done_idempotent`: call `move_to_done()` twice; no error, `t.path.parent.name == "done"`, `t.status == "done"`.
- Add `test_move_to_done_pool_issue`: issue in `.clasi/issues/`; after `move_to_done()`, file is in `.clasi/issues/done/`.

### tests/unit/test_issue_lifecycle.py — extend end-to-end

After the final `move_ticket_to_done` call, assert:
```python
# Issue should have been auto-completed and moved to done/
issue = project.get_issue(issue_filename)
assert issue.path.parent.name == "done"
assert issue.status == "done"
```

## Testing

- **Files to run**: `tests/unit/test_issue.py`, `tests/unit/test_issue_lifecycle.py`
- **Verification command**: `uv run pytest tests/unit/test_issue.py tests/unit/test_issue_lifecycle.py -x` then `uv run pytest`
