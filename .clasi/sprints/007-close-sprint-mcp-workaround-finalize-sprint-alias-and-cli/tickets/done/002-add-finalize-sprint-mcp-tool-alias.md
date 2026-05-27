---
id: '002'
title: Add finalize_sprint MCP tool alias
status: done
use-cases:
- SUC-002
depends-on: []
github-issue: ''
issue: ''
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Add finalize_sprint MCP tool alias

## Description

Register a second `@server.tool()` named `finalize_sprint` in
`clasi/tools/artifact_tools.py` that delegates to `close_sprint` with an
identical Python signature. The alias is a diagnostic tool: by changing only
the tool name and keeping every other property constant (param count, types,
defaults, boolean presence, docstring structure), the test result from an
affected VS Code extension session cleanly isolates whether the tool name
is the trigger for the MCP param-stripping bug.

The alias must not reimplement any logic. Its body is a single `return
close_sprint(...)` call.

TODO reference: `/Volumes/Proj/proj/code-projects/dotconfig/docs/clasi/todo/vscode-extension-close-sprint-empty-params.md` (Action 2)

## Acceptance Criteria

- [x] `finalize_sprint` is decorated with `@server.tool()` and registered in
      the MCP server
- [x] `finalize_sprint` has an **identical Python signature** to `close_sprint`:
      - Same parameter names: `sprint_id`, `branch_name`, `main_branch`,
        `push_tags`, `delete_branch`, `test_command`
      - Same types: `str`, `Optional[str]`, `str`, `bool`, `bool`, `Optional[str]`
      - Same defaults: `None`, `"master"`, `True`, `True`, `None`
      - Same order
  - A test using `inspect.signature` must assert this equality
- [x] `finalize_sprint` body contains only `return close_sprint(...)` — no
      reimplemented logic
- [x] `finalize_sprint` is placed immediately after `close_sprint` in the file
- [x] `close_sprint` is unchanged in signature, behavior, and docstring
- [x] All existing tests pass (`uv run pytest`)

## Implementation Plan

### Approach

Add `finalize_sprint` directly after the `close_sprint` function in
`clasi/tools/artifact_tools.py`. No imports are needed beyond what `close_sprint`
already uses (`Optional` is already imported).

### Files to Modify

- `clasi/tools/artifact_tools.py` — add `finalize_sprint` immediately after
  `close_sprint` (after line ~1007)

### Code (reference — must match exactly)

```python
@server.tool()
def finalize_sprint(
    sprint_id: str,
    branch_name: Optional[str] = None,
    main_branch: str = "master",
    push_tags: bool = True,
    delete_branch: bool = True,
    test_command: Optional[str] = None,
) -> str:
    """Alias for close_sprint. See close_sprint for full documentation.

    This alias exists to isolate the tool name as a diagnostic variable
    for a VS Code extension bug where close_sprint params are dropped.
    If this tool succeeds where close_sprint fails, the name is the trigger.
    """
    return close_sprint(sprint_id, branch_name, main_branch,
                        push_tags, delete_branch, test_command)
```

### Testing Plan

Write a unit test (new file `tests/unit/test_finalize_sprint_alias.py` or
alongside existing artifact tool tests):

- **Signature equality test**: Use `inspect.signature` to assert that
  `finalize_sprint` and `close_sprint` have identical parameters (names,
  kinds, defaults, annotations). This is the critical acceptance criterion.

  ```python
  import inspect
  from clasi.tools.artifact_tools import close_sprint, finalize_sprint

  def test_finalize_sprint_signature_matches_close_sprint():
      cs_params = inspect.signature(close_sprint).parameters
      fs_params = inspect.signature(finalize_sprint).parameters
      assert list(cs_params.keys()) == list(fs_params.keys())
      for name in cs_params:
          assert cs_params[name].default == fs_params[name].default
          assert cs_params[name].annotation == fs_params[name].annotation
  ```

- **Delegation test**: Mock `close_sprint` and assert `finalize_sprint`
  calls it with the correct arguments and returns its result.

- **Registration test**: Assert `finalize_sprint` appears in the MCP server's
  tool registry (check `server._tool_manager._tools` or use the MCP list
  tools endpoint if available in tests).

- Run full suite: `uv run pytest`

### Documentation Updates

No documentation updates required. The alias's docstring is intentionally
minimal — it references `close_sprint` rather than duplicating its content.
