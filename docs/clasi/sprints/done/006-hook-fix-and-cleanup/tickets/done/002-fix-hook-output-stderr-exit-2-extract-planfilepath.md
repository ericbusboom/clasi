---
id: '002'
title: 'Fix hook output: stderr + exit 2, extract planFilePath'
status: done
use-cases:
- SUC-001
- SUC-002
depends-on:
- '001'
github-issue: ''
todo: plan-rebase-sprint-branch-before-merge-on-close.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Fix hook output: stderr + exit 2, extract planFilePath

## Description

Fix `handle_plan_to_todo()` in `clasi/hook_handlers.py` so the model actually sees the stop instruction after a plan is saved as a TODO:

1. Extract `planFilePath` from the hook payload and pass it as `plan_file` to `plan_to_todo()` (uses ticket 001's new parameter).
2. When a TODO is created, write a JSON block to **stderr** with `decision: block` and a reason string, then call `sys.exit(2)` so Claude Code surfaces it to the model.
3. When no plan file exists (`result` is None), exit 0 with no output (unchanged).

Also: move `plan-rebase-sprint-branch-before-merge-on-close.md` TODO to done -- that work was fully completed in Sprint 005 (the rebase code, tests, and `artifact_tools.py` string are already in place).

## Acceptance Criteria

- [x] `handle_plan_to_todo()` extracts `payload.get("tool_input", {}).get("planFilePath")` and passes it as `plan_file` to `plan_to_todo()`.
- [x] When `plan_to_todo()` returns a path: stderr contains valid JSON with `"decision": "block"` and the TODO path in `"reason"`; stdout is empty; exit code is 2.
- [x] When `plan_to_todo()` returns None: no output; exit code is 0.
- [x] `uv run pytest tests/unit/test_hook_handlers.py tests/unit/test_plan_to_todo.py -v` passes.
- [x] TODO `plan-rebase-sprint-branch-before-merge-on-close.md` is in done status.

## Implementation Plan

### Approach

Modify `handle_plan_to_todo()` in `clasi/hook_handlers.py`. The change is 10-15 lines.

### Files to Modify

**`clasi/hook_handlers.py`** (lines ~852-871):

Replace the current implementation:
```python
def handle_plan_to_todo(payload: dict) -> None:
    from clasi.plan_to_todo import plan_to_todo

    result = plan_to_todo(
        Path.home() / ".claude" / "plans",
        Path("docs/clasi/todo"),
        hook_payload=payload,
    )
    if result:
        print(
            f"CLASI: Plan saved as TODO: {result}\n"
            "This plan is now a pending TODO for future sprint planning. "
            "Do NOT implement it now. Confirm the TODO was created and stop."
        )
    sys.exit(0)
```

With:
```python
def handle_plan_to_todo(payload: dict) -> None:
    from clasi.plan_to_todo import plan_to_todo

    plan_file_str = payload.get("tool_input", {}).get("planFilePath")
    plan_file = Path(plan_file_str) if plan_file_str else None

    result = plan_to_todo(
        Path.home() / ".claude" / "plans",
        Path("docs/clasi/todo"),
        hook_payload=payload,
        plan_file=plan_file,
    )
    if result:
        print(
            json.dumps({
                "decision": "block",
                "reason": (
                    f"CLASI: Plan saved as TODO: {result}. "
                    "This plan is now a pending TODO for future sprint planning. "
                    "Do NOT implement it now. Confirm the TODO was created and stop."
                ),
            }),
            file=sys.stderr,
        )
        sys.exit(2)
    sys.exit(0)
```

Verify that `import json` is already at the top of `hook_handlers.py` (it is -- json is used elsewhere in the file).

**`tests/unit/test_hook_handlers.py`** (class `TestHandlePlanToTodo`):

Update three existing tests:

1. `test_calls_plan_to_todo_with_standard_dirs`: The mock returns None (no result). Assert exit code 0. Also assert `plan_to_todo` was called with `plan_file=None` (because the payload `{}` has no `planFilePath`). The `hook_payload={}` kwarg assertion stays.

2. `test_prints_result_path_when_todo_created`: Change `assert exc.value.code == 0` to `assert exc.value.code == 2`. Change `assert "001-my-plan.md" in captured.out` to check `captured.err` instead (and verify it parses as JSON with `decision: block`).

3. `test_no_output_when_no_plan_file`: No change needed -- still exits 0 with no output.

Add one new test:

4. `test_passes_plan_file_path_from_payload` -- create a payload with `tool_input.planFilePath = "/tmp/my-plan.md"`; mock `plan_to_todo` to return None; assert it was called with `plan_file=Path("/tmp/my-plan.md")`.

### Cleanup: Move Rebase TODO to Done

After code changes and tests pass, move `plan-rebase-sprint-branch-before-merge-on-close.md` to done using the `move_todo_to_done` MCP tool. The rebase feature was implemented in Sprint 005 (commits cf3e375 and 5a9c94c); this step closes the administrative gap.

### Testing Plan

```
uv run pytest tests/unit/test_hook_handlers.py tests/unit/test_plan_to_todo.py -v
uv run pytest  # full suite, verify no regressions
```

### Documentation Updates

None required. Architecture update already documents the changes.
