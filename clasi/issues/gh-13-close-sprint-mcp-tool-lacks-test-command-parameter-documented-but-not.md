---
status: pending
github-issue: ericbusboom/clasi#13
sprint: '014'
---

# close_sprint MCP tool lacks test_command parameter (documented but not exposed in schema)

> Imported from [ericbusboom/clasi#13](https://github.com/ericbusboom/clasi/issues/13)
## Summary

The `close_sprint` MCP tool in CLASI v0.20260410.1 (server) / clasi CLI v0.20260417.1 has a mismatch between its documented and actual interface that blocks closing sprints in projects without `pytest` installed globally.

## Observed behavior

- `close_sprint` runs `pytest` directly during the tests step.
- When `pytest` isn't on PATH (e.g., a Python project that runs tests via `uv run pytest`, or a project with no pytest installed at all), the step fails with `error: Failed to spawn: pytest` and `Caused by: No such file or directory (os error 2)`.
- The sprint cannot be closed until the failure is cleared, even when the sprint made zero changes to runnable code (e.g., an analysis-only sprint that only wrote markdown and JSON fixtures).

## Documented vs actual interface

The close-sprint skill at `.claude/skills/close-sprint/SKILL.md` documents:

```
close_sprint(
    sprint_id="NNN",
    branch_name="sprint/NNN-slug",
    main_branch="master",
    push_tags=True,
    delete_branch=True,
    test_command="uv run pytest",  # or "" to skip tests
)
```

But the MCP tool's JSON schema does **not** expose a `test_command` parameter — only `sprint_id`, `branch_name`, `main_branch`, `push_tags`, `delete_branch`. So the documented workaround (`test_command=""` to skip, or `test_command="uv run pytest"` to use uv) is not callable.

## Impact

Any project that doesn't have a bare `pytest` binary available is blocked from closing sprints via the MCP. Common cases:
- `uv`-managed projects (pytest only in `.venv`, invoked via `uv run pytest`).
- Projects without a test suite (non-Python projects, or repos where tests live elsewhere).
- Analysis-only sprints where no production code changed.

## Request

Either (a) add the `test_command` parameter to the MCP tool schema so the documented interface matches, or (b) auto-detect `uv` / `poetry` / the project's configured runner, or (c) document an alternative mechanism for configuring the test command (config file, env var) and update the skill doc to match.

## Repro

1. In a `uv`-managed Python project with no global pytest, run an analysis-only sprint.
2. Attempt `close_sprint(sprint_id, branch_name, main_branch="master", push_tags=False, delete_branch=True)`.
3. Step `tests` fails with the spawn error above. Recovery state is recorded; no schema parameter lets you retry with a different test command.
