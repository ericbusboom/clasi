---
sprint: "006"
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Use Cases -- Sprint 006: Hook Fix and Cleanup

## SUC-001: Hook Blocks Model After Plan Capture

**Actor**: Developer using Claude Code with the CLASI hook active.

**Trigger**: Developer accepts a plan in plan mode (`ExitPlanMode`).

**Preconditions**:
- The PostToolUse hook for `ExitPlanMode` is configured in `settings.json`.
- A plan file exists in `~/.claude/plans/`.

**Main Flow**:
1. Developer reviews a plan in plan mode and approves it.
2. Claude Code calls `ExitPlanMode` and invokes the PostToolUse hook.
3. The hook reads `planFilePath` from the payload to locate the exact plan file.
4. The hook calls `plan_to_todo()` with the plan file path; the plan is saved as a CLASI TODO.
5. The hook writes a JSON block with `decision: block` and a stop reason to stderr, exits with code 2.
6. Claude Code surfaces the hook message as feedback to the model.
7. The model sees the block message and confirms the TODO was created, then stops without implementing.

**Postconditions**:
- A new TODO file exists in `docs/clasi/todo/`.
- The plan file has been deleted from `~/.claude/plans/`.
- The model does not proceed to write code.

**Alternate Flow -- No Plan File**:
- If no plan file exists, `plan_to_todo()` returns None.
- The hook exits with code 0 and no output (unchanged from Sprint 005 behavior).

**Acceptance Criteria**:
- [ ] After `ExitPlanMode`, the model receives hook feedback containing `decision: block`.
- [ ] The model stops without writing code.
- [ ] Exit code 2 is returned when a TODO was created, exit code 0 when no plan file existed.

---

## SUC-002: Plan-to-TODO Uses Payload Path Instead of Mtime Heuristic

**Actor**: The `handle_plan_to_todo` hook handler.

**Trigger**: Hook fires after `ExitPlanMode` with a payload containing `tool_input.planFilePath`.

**Preconditions**:
- `planFilePath` is present and non-empty in the hook payload.
- The referenced plan file exists.

**Main Flow**:
1. `handle_plan_to_todo()` extracts `planFilePath` from `payload["tool_input"]["planFilePath"]`.
2. It converts the string to a `Path` and passes it as `plan_file` to `plan_to_todo()`.
3. `plan_to_todo()` reads that specific file directly, without scanning `plans_dir`.
4. The file is converted to a TODO and the original is deleted.

**Postconditions**:
- The exact plan file referenced in the payload is converted, not a different file that happened to be newer.

**Alternate Flow -- No `planFilePath` in Payload**:
- `handle_plan_to_todo()` passes `plan_file=None`.
- `plan_to_todo()` falls back to scanning `plans_dir` for the newest `.md` (mtime heuristic).
- Behavior is identical to Sprint 005.

**Acceptance Criteria**:
- [ ] When `plan_file` is passed to `plan_to_todo()`, that specific file is read and deleted.
- [ ] When `plan_file=None`, the mtime-newest file is used as before.
- [ ] `handle_plan_to_todo()` extracts `planFilePath` from `payload["tool_input"]` and passes it as `plan_file`.
