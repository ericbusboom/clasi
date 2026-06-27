---
id: '001'
title: Add clasi sprint close CLI subcommand
status: done
use-cases:
- SUC-001
depends-on: []
github-issue: ''
issue: ''
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Add clasi sprint close CLI subcommand

## Description

The `clasi` CLI has no way to close a sprint from the shell. This ticket adds
a `clasi sprint` click group with a `close` subcommand that wraps the existing
`close_sprint` function in `clasi/tools/artifact_tools.py`. This provides an
MCP-independent escape hatch for users affected by the VS Code extension bug
that drops params from `mcp__clasi__close_sprint` calls.

The existing `tool` and `schema` groups in `cli.py` provide the pattern to
follow. The command is a thin wrapper — no business logic, no duplicated
implementation.

TODO reference: `/Volumes/Proj/proj/code-projects/dotconfig/docs/clasi/todo/vscode-extension-close-sprint-empty-params.md` (Action 1)

## Acceptance Criteria

- [x] `clasi sprint` is a registered click group with docstring "Sprint lifecycle commands."
- [x] `clasi sprint close` is a subcommand of `clasi sprint`
- [x] `clasi sprint close <sprint_id>` is a required positional argument
- [x] The following options are present with correct defaults and names:
  - `--branch` / `branch_name` (default: None)
  - `--main-branch` / `main_branch` (default: "master")
  - `--push-tags/--no-push-tags` / `push_tags` (default: True)
  - `--delete-branch/--no-delete-branch` / `delete_branch` (default: True)
  - `--test-command` / `test_command` (default: None)
- [x] The command calls `close_sprint` from `clasi.tools.artifact_tools` with all arguments
- [x] The result of `close_sprint` is echoed to stdout via `click.echo`
- [x] `clasi sprint close --help` displays correct usage and all options
- [x] `clasi sprint --help` lists `close` as a subcommand
- [x] All existing tests pass (`uv run pytest`)

## Implementation Plan

### Approach

Add a `sprint` group and `close` subcommand to `clasi/cli.py`, following the
exact pattern of the existing `tool` group. Use a lazy import inside the
command body (consistent with all other commands in the file). The `close_sprint`
function signature drives the option definitions directly.

### Files to Modify

- `clasi/cli.py` — add `sprint` group and `close` subcommand after the existing
  `schema` group definition; update the module docstring to list the new command

### Code shape (reference)

```python
@cli.group()
def sprint() -> None:
    """Sprint lifecycle commands."""


@sprint.command("close")
@click.argument("sprint_id")
@click.option("--branch", "branch_name", default=None,
              help="Sprint branch name. When provided, enables full lifecycle with git operations.")
@click.option("--main-branch", default="master", show_default=True,
              help="Target branch for merge.")
@click.option("--push-tags/--no-push-tags", default=True, show_default=True,
              help="Whether to push tags after tagging.")
@click.option("--delete-branch/--no-delete-branch", default=True, show_default=True,
              help="Whether to delete the sprint branch after merge.")
@click.option("--test-command", default=None,
              help="Shell command to run tests. Pass empty string to skip.")
def sprint_close(
    sprint_id: str,
    branch_name: str | None,
    main_branch: str,
    push_tags: bool,
    delete_branch: bool,
    test_command: str | None,
) -> None:
    """Close a sprint, running tests and git lifecycle operations."""
    from clasi.tools.artifact_tools import close_sprint
    click.echo(close_sprint(sprint_id, branch_name, main_branch,
                            push_tags, delete_branch, test_command))
```

### Testing Plan

Write unit tests using `click.testing.CliRunner`:
- Test `clasi sprint --help` exits 0 and mentions `close`
- Test `clasi sprint close --help` exits 0 and lists all options with correct defaults
- Test `clasi sprint close 007 --branch sprint/007-foo` invokes `close_sprint`
  with correct positional and keyword arguments (mock `close_sprint` at
  `clasi.tools.artifact_tools.close_sprint`)
- Test that the return value of `close_sprint` is echoed to stdout
- Run full suite: `uv run pytest`

Place tests in `tests/unit/test_cli_sprint.py` (new file) or alongside
existing CLI tests if that file already exists.

### Documentation Updates

Update the module docstring in `clasi/cli.py` to add the new subcommand:
```
    clasi sprint close <sprint_id>     — Close a sprint
```
