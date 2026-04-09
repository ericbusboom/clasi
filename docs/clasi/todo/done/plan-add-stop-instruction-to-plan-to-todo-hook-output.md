---
status: done
sprint: '004'
tickets:
- 004-006
---

# Plan: Add stop instruction to plan-to-todo hook output

## Context

When ExitPlanMode fires, the `plan-to-todo` hook converts the plan to a
CLASI TODO. The intent is that the plan is captured for future sprint
planning — not immediate execution. But the hook currently only prints
the file path, giving no instruction to stop. The model treats plan
approval as a green light to implement.

Fix: change the hook's stdout message to include an explicit stop
instruction, which the model is bound to follow as hook feedback.

## File to modify

`clasi/hook_handlers.py` — `handle_plan_to_todo()` (line ~864)

**Current** (line 864-866):
```python
if result:
    print(result)
sys.exit(0)
```

**New**:
```python
if result:
    print(
        f"CLASI: Plan saved as TODO: {result}\n"
        "This plan is now a pending TODO for future sprint planning. "
        "Do NOT implement it now. Confirm the TODO was created and stop."
    )
sys.exit(0)
```

## Verification

1. Enter plan mode, write a plan, exit plan mode
2. Verify the hook output includes the stop instruction
3. Verify the model stops after confirming the TODO
4. `uv run pytest` passes
