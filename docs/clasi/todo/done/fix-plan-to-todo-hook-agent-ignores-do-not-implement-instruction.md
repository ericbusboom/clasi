---
status: done
sprint: '006'
tickets:
- '001'
- '002'
---

# Fix plan-to-todo hook: agent ignores "Do NOT implement" instruction

## Context

The `handle_plan_to_todo` PostToolUse hook fires after `ExitPlanMode` and prints a "Do NOT implement" message to stdout with exit code 0. However, Claude Code only surfaces PostToolUse hook output to the model when:

- **Exit 0 + stdout**: plain text goes to debug log only, model never sees it
- **Exit 2 + stderr**: message is shown to the model as hook feedback

The agent sees `ExitPlanMode` return "User has approved your plan" but never sees the hook's stop instruction, so it proceeds to implement.

## Changes

### 1. Use `planFilePath` from payload instead of mtime heuristic

In `clasi/plan_to_todo.py`, the current code globs `plans_dir` and picks the newest file by mtime. The hook payload contains the exact path at `tool_input.planFilePath` -- use it directly.

- `handle_plan_to_todo` in `hook_handlers.py` should extract `payload.get("tool_input", {}).get("planFilePath")` and pass it to `plan_to_todo`
- `plan_to_todo` should accept an optional `plan_file: Optional[Path]` parameter; when provided, use it directly instead of globbing
- Fall back to the mtime heuristic only when `plan_file` is not provided (backward compat)

### 2. Fix hook output so the model actually sees it

In `clasi/hook_handlers.py`, function `handle_plan_to_todo` (line 852):

- Change the `print()` call to output a JSON object to **stderr** with `decision: "block"` and a `reason` field containing the stop instruction
- Change `sys.exit(0)` to `sys.exit(2)` so the message is surfaced to the model

**Before:**
```python
if result:
    print(
        f"CLASI: Plan saved as TODO: {result}\n"
        "This plan is now a pending TODO for future sprint planning. "
        "Do NOT implement it now. Confirm the TODO was created and stop."
    )
sys.exit(0)
```

**After:**
```python
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

When no plan file exists (`result` is None), exit 0 as before -- nothing to block.

## Test updates

In `tests/unit/test_hook_handlers.py`, class `TestHandlePlanToTodo`:

1. `test_prints_result_path_when_todo_created` -- assert exit code 2 (not 0), check stderr (not stdout) for the TODO path
2. `test_no_output_when_no_plan_file` -- unchanged (still exits 0, no output)
3. `test_calls_plan_to_todo_with_standard_dirs` -- update expected exit code to 0 when result is None (unchanged behavior), or 2 when result is not None

## Files to modify

- `clasi/plan_to_todo.py` -- add optional `plan_file` parameter, use it when provided
- `clasi/hook_handlers.py` (line ~858-871) -- extract `planFilePath`, pass to `plan_to_todo`, fix output to stderr + exit 2
- `tests/unit/test_plan_to_todo.py` -- add tests for explicit `plan_file` parameter
- `tests/unit/test_hook_handlers.py` (lines ~869-888) -- update exit codes and output assertions

## Verification

1. `uv run pytest tests/unit/test_hook_handlers.py tests/unit/test_plan_to_todo.py -v`
2. Manual: run `/se plan`, create a plan, call ExitPlanMode, verify the agent sees the block message and stops


---

## Hook Debug Info

```json
{
  "hook_payload": {
    "session_id": "7c8d156b-21d9-4b69-ba6d-7347f237f2e9",
    "transcript_path": "/Users/eric/.claude/projects/-Users-eric-proj-ai-project-clasi/7c8d156b-21d9-4b69-ba6d-7347f237f2e9.jsonl",
    "cwd": "/Users/eric/proj/ai-project/clasi",
    "permission_mode": "default",
    "hook_event_name": "PostToolUse",
    "tool_name": "ExitPlanMode",
    "tool_input": {
      "plan": "# Fix plan-to-todo hook: agent ignores \"Do NOT implement\" instruction\n\n## Context\n\nThe `handle_plan_to_todo` PostToolUse hook fires after `ExitPlanMode` and prints a \"Do NOT implement\" message to stdout with exit code 0. However, Claude Code only surfaces PostToolUse hook output to the model when:\n\n- **Exit 0 + stdout**: plain text goes to debug log only, model never sees it\n- **Exit 2 + stderr**: message is shown to the model as hook feedback\n\nThe agent sees `ExitPlanMode` return \"User has approved your plan\" but never sees the hook's stop instruction, so it proceeds to implement.\n\n## Change\n\nIn `clasi/hook_handlers.py`, function `handle_plan_to_todo` (line 852):\n\n- Change the `print()` call to output a JSON object to **stderr** with `decision: \"block\"` and a `reason` field containing the stop instruction\n- Change `sys.exit(0)` to `sys.exit(2)` so the message is surfaced to the model\n\n**Before:**\n```python\nif result:\n    print(\n        f\"CLASI: Plan saved as TODO: {result}\\n\"\n        \"This plan is now a pending TODO for future sprint planning. \"\n        \"Do NOT implement it now. Confirm the TODO was created and stop.\"\n    )\nsys.exit(0)\n```\n\n**After:**\n```python\nif result:\n    print(\n        json.dumps({\n            \"decision\": \"block\",\n            \"reason\": (\n                f\"CLASI: Plan saved as TODO: {result}. \"\n                \"This plan is now a pending TODO for future sprint planning. \"\n                \"Do NOT implement it now. Confirm the TODO was created and stop.\"\n            ),\n        }),\n        file=sys.stderr,\n    )\n    sys.exit(2)\nsys.exit(0)\n```\n\nWhen no plan file exists (`result` is None), exit 0 as before -- nothing to block.\n\n## Test updates\n\nIn `tests/unit/test_hook_handlers.py`, class `TestHandlePlanToTodo`:\n\n1. `test_prints_result_path_when_todo_created` -- assert exit code 2 (not 0), check stderr (not stdout) for the TODO path\n2. `test_no_output_when_no_plan_file` -- unchanged (still exits 0, no output)\n3. `test_calls_plan_to_todo_with_standard_dirs` -- update expected exit code to 0 when result is None (unchanged behavior), or 2 when result is not None\n\n## Files to modify\n\n- `clasi/hook_handlers.py` (line ~858-871)\n- `tests/unit/test_hook_handlers.py` (lines ~869-888)\n\n## Verification\n\n1. `uv run pytest tests/unit/test_hook_handlers.py tests/unit/test_plan_to_todo.py -v`\n2. Manual: run `/se plan`, create a plan, call ExitPlanMode, verify the agent sees the block message and stops\n",
      "planFilePath": "/Users/eric/.claude/plans/elegant-honking-firefly.md"
    },
    "tool_response": {
      "plan": "# Fix plan-to-todo hook: agent ignores \"Do NOT implement\" instruction\n\n## Context\n\nThe `handle_plan_to_todo` PostToolUse hook fires after `ExitPlanMode` and prints a \"Do NOT implement\" message to stdout with exit code 0. However, Claude Code only surfaces PostToolUse hook output to the model when:\n\n- **Exit 0 + stdout**: plain text goes to debug log only, model never sees it\n- **Exit 2 + stderr**: message is shown to the model as hook feedback\n\nThe agent sees `ExitPlanMode` return \"User has approved your plan\" but never sees the hook's stop instruction, so it proceeds to implement.\n\n## Change\n\nIn `clasi/hook_handlers.py`, function `handle_plan_to_todo` (line 852):\n\n- Change the `print()` call to output a JSON object to **stderr** with `decision: \"block\"` and a `reason` field containing the stop instruction\n- Change `sys.exit(0)` to `sys.exit(2)` so the message is surfaced to the model\n\n**Before:**\n```python\nif result:\n    print(\n        f\"CLASI: Plan saved as TODO: {result}\\n\"\n        \"This plan is now a pending TODO for future sprint planning. \"\n        \"Do NOT implement it now. Confirm the TODO was created and stop.\"\n    )\nsys.exit(0)\n```\n\n**After:**\n```python\nif result:\n    print(\n        json.dumps({\n            \"decision\": \"block\",\n            \"reason\": (\n                f\"CLASI: Plan saved as TODO: {result}. \"\n                \"This plan is now a pending TODO for future sprint planning. \"\n                \"Do NOT implement it now. Confirm the TODO was created and stop.\"\n            ),\n        }),\n        file=sys.stderr,\n    )\n    sys.exit(2)\nsys.exit(0)\n```\n\nWhen no plan file exists (`result` is None), exit 0 as before -- nothing to block.\n\n## Test updates\n\nIn `tests/unit/test_hook_handlers.py`, class `TestHandlePlanToTodo`:\n\n1. `test_prints_result_path_when_todo_created` -- assert exit code 2 (not 0), check stderr (not stdout) for the TODO path\n2. `test_no_output_when_no_plan_file` -- unchanged (still exits 0, no output)\n3. `test_calls_plan_to_todo_with_standard_dirs` -- update expected exit code to 0 when result is None (unchanged behavior), or 2 when result is not None\n\n## Files to modify\n\n- `clasi/hook_handlers.py` (line ~858-871)\n- `tests/unit/test_hook_handlers.py` (lines ~869-888)\n\n## Verification\n\n1. `uv run pytest tests/unit/test_hook_handlers.py tests/unit/test_plan_to_todo.py -v`\n2. Manual: run `/se plan`, create a plan, call ExitPlanMode, verify the agent sees the block message and stops\n",
      "isAgent": false,
      "filePath": "/Users/eric/.claude/plans/elegant-honking-firefly.md",
      "planWasEdited": true
    },
    "tool_use_id": "toolu_01Caj6k5a2Y4GGp9xye2LCvR"
  },
  "env": {
    "TOOL_INPUT": "",
    "TOOL_NAME": "",
    "SESSION_ID": "",
    "CLASI_AGENT_TIER": "",
    "CLASI_AGENT_NAME": "",
    "CLAUDE_PROJECT_DIR": "/Users/eric/proj/ai-project/clasi",
    "PWD": "/Users/eric/proj/ai-project/clasi",
    "CWD": ""
  },
  "plans_dir": "/Users/eric/.claude/plans",
  "plan_file": "/Users/eric/.claude/plans/elegant-honking-firefly.md",
  "cwd": "/Users/eric/proj/ai-project/clasi"
}
```
