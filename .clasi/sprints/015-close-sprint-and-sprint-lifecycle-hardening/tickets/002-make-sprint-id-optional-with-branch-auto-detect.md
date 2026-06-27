---
id: '002'
title: Make sprint_id optional with branch auto-detect
status: in-progress
use-cases:
- SUC-015-001
depends-on:
- 015-001
github-issue: ''
issue: close-sprint-auto-detect-sprint-id-from-branch.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Make sprint_id optional with branch auto-detect

## Description

`close_sprint` currently requires `sprint_id: str` — a hard requirement that causes failures
when the caller omits it (empty-args bug, missing copy-paste). The sprint being closed is always
deterministic from the current git branch (`sprint/NNN-slug` → `NNN`). Making `sprint_id`
optional allows `close_sprint()` with no args to work seamlessly when the model is already on the
correct sprint branch.

## Acceptance Criteria

- [ ] `close_sprint` signature changes to `sprint_id: Optional[str] = None`.
- [ ] When `sprint_id` is `None` or empty string, the function calls `git branch --show-current`
  and parses the output against `sprint/NNN-*` to extract `sprint_id` and `branch_name`.
- [ ] When auto-detect succeeds, behavior is identical to passing `sprint_id` and `branch_name`
  explicitly.
- [ ] When not on a sprint branch, `close_sprint()` returns a structured error JSON:
  ```json
  {
    "status": "error",
    "error": {
      "step": "auto-detect",
      "message": "Not on a sprint branch. Provide sprint_id explicitly or check out the sprint branch.",
      "current_branch": "<branch>"
    }
  }
  ```
- [ ] When `sprint_id` is provided explicitly, behavior is identical to pre-sprint-015 behavior.
- [ ] `uv run pytest -q` passes with no regressions.

## Implementation Plan

### Approach

Add a private `_detect_sprint_from_branch() -> tuple[str, str] | None` helper that:
1. Runs `subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True)`.
2. Strips the output and matches against regex `^sprint/(\d+)-(.+)$`.
3. Returns `(sprint_id, branch_name)` on match, or `None` if no match (including empty output
   for detached HEAD).

Modify `close_sprint` to call this helper when `sprint_id` is absent, and return the structured
error if detection fails.

### Files to modify

1. **`clasi/tools/artifact_tools.py`**:
   - Change `sprint_id: str` to `sprint_id: Optional[str] = None` in `close_sprint` signature.
   - Add `_detect_sprint_from_branch()` helper (private, not registered as MCP tool).
   - In `close_sprint` body, before the `if branch_name is not None:` dispatch, insert:
     ```python
     if not sprint_id:
         detected = _detect_sprint_from_branch()
         if detected is None:
             # return structured error JSON
             ...
         sprint_id, branch_name = detected
     ```
   - Regex pattern: `re.match(r"^sprint/(\d+)-", branch)` to extract NNN; full branch name
     becomes the `branch_name` value.

### Testing plan

- New test class `TestCloseSSprintAutoDetect` in `tests/unit/test_cli_sprint.py` or a new
  `tests/unit/test_close_sprint_auto_detect.py`:
  - Mock `subprocess.run` to return `sprint/015-my-sprint`; assert auto-detect derives
    `sprint_id="015"` and `branch_name="sprint/015-my-sprint"`.
  - Mock `subprocess.run` to return `master`; assert returns structured error with `step: auto-detect`.
  - Mock `subprocess.run` to return empty string (detached HEAD); assert returns structured error.
  - Existing `test_close_calls_close_sprint_with_sprint_id` must still pass unchanged (explicit
    sprint_id path is unaffected).

### Documentation updates

Update `clasi/plugin/skills/close-sprint/SKILL.md` to document the new optional `sprint_id`
parameter and the auto-detect behavior. Add a one-liner note that `close_sprint()` with no args
auto-detects from the current branch.
