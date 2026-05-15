---
id: '003'
title: split_issue MCP tool
status: done
use-cases:
- SUC-004
depends-on:
- '001'
github-issue: ''
issue: ''
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# split_issue MCP tool

## Description

Add a new `split_issue` MCP tool to `clasi/tools/artifact_tools.py`. This tool enables sprint planners to split an issue when only part of its scope fits in the current sprint. The tool creates a sibling file in the same directory as the original and adds mutual cross-link frontmatter (`split_from` / `split_into`).

Depends on T1 because `project.get_issue` must be able to resolve issues in `<sprint>/issues/done/` (in case the original was already completed and the planner wants to split retrospectively — unlikely but correct).

## Acceptance Criteria

- [x] `split_issue` tool is registered via `@server.tool()` and appears in the MCP tool list.
- [x] `split_issue(filename, new_filename, new_title, new_body)` resolves the original via `project.get_issue`.
- [x] New file is created as a sibling of the original (same directory).
- [x] New file frontmatter: `status: in-progress` and `sprint: <sprint_id>` if original is sprint-scoped and `in-progress`; otherwise `status: pending` with no `sprint`.
- [x] New file frontmatter: `source` copied from original if present.
- [x] New file frontmatter: `split_from: <original-filename>`.
- [x] Original file frontmatter: `split_into` list is created (or appended to if already present) with `<new-filename>`.
- [x] If `updated_body` is provided, the original file's body content is replaced with `updated_body`.
- [x] Returns `{original_path, new_path}` as JSON.
- [x] Splitting a pending-pool issue creates a sibling in `.clasi/issues/`.
- [x] Splitting a sprint-scoped `in-progress` issue creates a sibling in `<sprint>/issues/`.
- [x] Splitting the same issue twice appends to the `split_into` list (does not overwrite).
- [x] `uv run pytest tests/unit/test_issue_tools.py -x` passes (new tests).
- [x] `uv run pytest` (full suite) passes.

## Implementation Plan

### clasi/tools/artifact_tools.py — add `split_issue` tool

Place the new tool after the `move_issue_to_done` function (around line 1534).

```python
@server.tool()
def split_issue(
    filename: str,
    new_filename: str,
    new_title: str,
    new_body: str,
    updated_body: str | None = None,
) -> str:
    """Split an issue into two sibling files with cross-link frontmatter.

    Creates a new issue file as a sibling of the original (same directory).
    Adds split_from to the new file and split_into to the original.

    When splitting a sprint-scoped in-progress issue, the new file inherits
    the sprint context. Otherwise the new file starts as pending in the pool.

    Args:
        filename: The original issue filename (resolved via project.get_issue).
        new_filename: Filename for the new split-off issue (e.g., 'my-idea-part2.md').
        new_title: Title heading for the new issue.
        new_body: Body content for the new issue (after the heading).
        updated_body: Optional replacement body for the original issue.

    Returns JSON with {original_path, new_path}.
    """
    project = get_project()
    try:
        original = project.get_issue(filename)
    except ValueError:
        raise ValueError(f"Issue not found: {filename}")

    new_path = original.path.parent / new_filename
    if new_path.exists():
        raise ValueError(f"Target file already exists: {new_path}")

    # Determine frontmatter for the new file
    new_fm: dict = {"status": "pending"}
    if original.status == "in-progress" and original.sprint:
        new_fm["status"] = "in-progress"
        new_fm["sprint"] = original.sprint
    if original.source:
        new_fm["source"] = original.source
    new_fm["split_from"] = filename

    # Write the new file
    import yaml
    fm_str = yaml.dump(new_fm, default_flow_style=False).strip()
    new_content = f"---\n{fm_str}\n---\n\n# {new_title}\n\n{new_body}"
    new_path.write_text(new_content, encoding="utf-8")

    # Update the original's split_into list
    orig_fm, orig_body = original._artifact.read_document()
    existing_split_into = orig_fm.get("split_into", [])
    if isinstance(existing_split_into, str):
        existing_split_into = [existing_split_into] if existing_split_into else []
    if new_filename not in existing_split_into:
        existing_split_into.append(new_filename)
    orig_fm["split_into"] = existing_split_into

    # Optionally replace the original body
    if updated_body is not None:
        orig_body = updated_body

    original._artifact.write(orig_fm, orig_body)

    return json.dumps({
        "original_path": str(original.path),
        "new_path": str(new_path),
    }, indent=2)
```

Note: `Artifact.read_document()` returns `(frontmatter_dict, body_str)`. `Artifact.write(fm, body)` writes both back. This pattern is used in `Issue.add_ticket_ref` at issue.py:109-116.

### tests/unit/test_issue_tools.py — new test file (or section)

If `test_issue_tools.py` already exists, add a `TestSplitIssue` class. Otherwise create the file.

Tests:
- `test_split_pending_pool_issue`: create issue in `.clasi/issues/`; call `split_issue`; assert new file in `.clasi/issues/` with `split_from`, original has `split_into`, status of new is `pending`.
- `test_split_sprint_scoped_issue`: create sprint, move issue to sprint via `move_to_in_progress`; call `split_issue`; assert new file in `<sprint>/issues/` with `status: in-progress`, `sprint` set.
- `test_split_copies_source`: issue has `source: https://example.com`; after split, new file has same `source`.
- `test_split_no_source`: issue has no `source`; new file has no `source` key.
- `test_split_updated_body`: pass `updated_body`; assert original body replaced.
- `test_split_twice_appends`: split same issue twice; assert `split_into` has two entries.
- `test_split_target_exists_raises`: call `split_issue` with a `new_filename` that already exists; assert `ValueError`.
- `test_split_returns_paths`: assert return value contains `original_path` and `new_path` as strings.

## Testing

- **Files to run**: `tests/unit/test_issue_tools.py`
- **Verification command**: `uv run pytest tests/unit/test_issue_tools.py -x` then `uv run pytest`
