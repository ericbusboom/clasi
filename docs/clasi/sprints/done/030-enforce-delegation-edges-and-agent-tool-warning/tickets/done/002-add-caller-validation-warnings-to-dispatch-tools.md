---
id: '002'
title: Add caller validation warnings to dispatch tools
status: done
use-cases: []
depends-on: []
github-issue: ''
todo: ''
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Add caller validation warnings to dispatch tools

## Description

All dispatch tools are exposed to all callers with no enforcement that the
calling agent is actually allowed to dispatch to the target agent. This ticket
adds caller validation warnings to each dispatch tool.

Each dispatch tool should read `CLASI_AGENT_NAME` from the environment (set by
`Agent.dispatch()`). If the caller is not in the expected set for that dispatch
edge, log a warning. This uses warnings rather than blocking because the
interactive session (team-lead without CLASI_AGENT_NAME set) must still work.

Example for `dispatch_to_code_monkey`:

```python
caller = os.environ.get("CLASI_AGENT_NAME", "team-lead")
allowed_callers = {"sprint-executor", "ad-hoc-executor"}
if caller not in allowed_callers:
    logger.warning(
        "DELEGATION VIOLATION: %s called dispatch_to_code_monkey "
        "(expected: %s)", caller, allowed_callers
    )
```

The allowed callers for each tool:
- `dispatch_to_code_monkey`: sprint-executor, ad-hoc-executor
- `dispatch_to_architect`: sprint-planner
- `dispatch_to_architecture_reviewer`: sprint-planner
- `dispatch_to_technical_lead`: sprint-planner
- `dispatch_to_code_reviewer`: ad-hoc-executor
- `dispatch_to_sprint_executor`: team-lead
- `dispatch_to_sprint_planner`: team-lead
- `dispatch_to_sprint_reviewer`: team-lead
- `dispatch_to_project_manager`: team-lead
- `dispatch_to_project_architect`: team-lead
- `dispatch_to_todo_worker`: team-lead
- `dispatch_to_ad_hoc_executor`: team-lead

## Acceptance Criteria

- [x] Each dispatch tool reads `CLASI_AGENT_NAME` from the environment
- [x] Each dispatch tool has a defined `allowed_callers` set
- [x] A warning is logged when the caller is not in `allowed_callers`
- [x] The warning message includes the caller name and the expected callers
- [x] The dispatch tool still proceeds after logging the warning (no blocking)
- [x] Tests verify that the warning is logged for unauthorized callers
- [x] Tests verify that no warning is logged for authorized callers
- [x] `uv run pytest` passes with no failures

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/`
- **New tests to write**: Tests for caller validation warnings in dispatch tools
- **Verification command**: `uv run pytest`
