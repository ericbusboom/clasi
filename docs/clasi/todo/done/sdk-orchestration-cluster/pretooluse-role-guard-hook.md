---
status: in-progress
source: https://github.com/ericbusboom/clasi/issues/10
sprint: '001'
tickets:
- 001-004
---

# PreToolUse Hook to Enforce Team-Lead Role Boundary

## Problem

The team-lead agent definition says: "Pure dispatcher. Never write code,
documentation, or planning artifacts yourself." But nothing mechanically
enforces this. When the user says "write the sprint docs," the fastest
response is to write them directly. The dispatch overhead (compose prompt,
curate context, call Agent tool, validate result) is 5x more steps, and
Claude optimizes for responsiveness.

Thirteen reflections document this failure pattern under the category
`ignored-instruction`. The root cause is consistent: instructional constraints
do not reliably bind behavior under user pressure. The reflection
`2026-03-19-main-controller-not-dispatching.md` explicitly identifies a
`PreToolUse` hook as the required fix.

The current `HOOKS_CONFIG` in `init_command.py` has `UserPromptSubmit` (a
reminder to call `get_se_overview()`) and `PostToolUse` (a git-on-main
warning). There is no `PreToolUse` hook. All enforcement is after the fact
or instructional.

## Desired Behavior

A `PreToolUse` hook fires before any `Edit`, `Write`, or `MultiEdit` tool
call. It checks whether the file being modified is inside the team-lead's
write scope. The team-lead's write scope is: nothing. It dispatches; it does
not write.

If the team-lead attempts to write a file directly, the hook returns a
blocking error message that names the violation and the correct action:

```
CLASI ROLE VIOLATION: team-lead attempted direct file write to <path>.
The team-lead does not write files. Dispatch to the appropriate subagent:
- sprint-planner for sprint/architecture/ticket artifacts
- code-monkey for source code and tests
- todo-worker for TODOs
- ad-hoc-executor for out-of-process changes
Call get_agent_definition("team-lead") to review your delegation map.
```

This is not a reminder — it is a hard stop. The tool call does not proceed.

## Proposed Implementation

### 1. Add a `clasi-role-guard` script

Create `claude_agent_skills/hooks/role_guard.sh`, installed by `clasi init`
to `.claude/hooks/role_guard.sh`.

The script reads the `TOOL_INPUT` environment variable (provided by Claude
Code to all hooks), extracts the file path being written, and checks it
against a known-safe list. If the path is a CLASI planning artifact or
source file, it emits the blocking error and exits non-zero.

```bash
#!/bin/bash
# CLASI role guard: blocks team-lead from writing files directly.
# Fires on PreToolUse for Edit, Write, MultiEdit.
#
# TOOL_INPUT is a JSON object with the tool arguments.
# For Write/Edit/MultiEdit, it contains a "path" or "file_path" field.

FILE_PATH=$(echo "$TOOL_INPUT" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(data.get('path') or data.get('file_path') or data.get('new_path') or '')
" 2>/dev/null)

if [ -z "$FILE_PATH" ]; then
  exit 0  # Can't determine path, let it through
fi

# Paths the team-lead must never write directly
BLOCKED_PATTERNS=(
  "docs/clasi/"
  "claude_agent_skills/"
  "tests/"
  "src/"
  "*.py"
  "*.ts"
  "*.js"
)

for pattern in "${BLOCKED_PATTERNS[@]}"; do
  if [[ "$FILE_PATH" == $pattern ]] || [[ "$FILE_PATH" == *"$pattern"* ]]; then
    echo "CLASI ROLE VIOLATION: team-lead attempted direct file write to: $FILE_PATH"
    echo "The team-lead does not write files. Dispatch to the appropriate subagent."
    echo "Review your delegation map: get_agent_definition(\"team-lead\")"
    exit 1
  fi
done

exit 0
```

### 2. Register the hook in `HOOKS_CONFIG`

Add a `PreToolUse` entry to `HOOKS_CONFIG` in `init_command.py`:

```python
HOOKS_CONFIG = {
    "UserPromptSubmit": [ ... ],  # existing
    "PreToolUse": [
        {
            "matcher": "Edit|Write|MultiEdit",
            "hooks": [
                {
                    "type": "command",
                    "command": "bash .claude/hooks/role_guard.sh",
                }
            ],
        }
    ],
    "PostToolUse": [ ... ],  # existing
}
```

### 3. Install the hook script in `clasi init`

Add a step in `init_command.py` that copies `role_guard.sh` from the package
to `.claude/hooks/role_guard.sh` in the target repo, with execute permissions.
Follow the same idempotent pattern used for other init artifacts: write only
if content differs.

### 4. Add the hooks directory to `.gitignore` or check it in

`role_guard.sh` should be checked in — it is a process enforcement artifact,
not a local configuration. Add `.claude/hooks/` to the files that `clasi init`
creates and that the project should commit.

## Scope Boundaries

The hook enforces the team-lead boundary only. Sub-agents (sprint-planner,
sprint-executor, code-monkey) run as separate Agent tool invocations with
their own context — the hook does not interfere with them because they are
not the top-level session. The hook fires in the session where CLAUDE.md
declares the session to be the team-lead.

The hook should NOT block writes to:
- `docs/clasi/log/` — the team-lead legitimately reads log paths returned
  by dispatch tools (though it does not write them directly, the hook
  need not be that precise)
- `.claude/` directory itself — settings and hooks are meta-configuration
- `CLAUDE.md`, `AGENTS.md` — process documents, not sprint artifacts

Refinement of the blocked path list is expected; start conservative (block
`docs/clasi/` and source directories) and expand based on observed false
positives.

## Open Questions

- **Hook exit code semantics**: Verify that a non-zero exit from a
  `PreToolUse` hook actually blocks the tool call in the current Claude Code
  version. If it only emits a warning, the enforcement value is reduced (but
  still better than nothing).
- **TOOL_INPUT format**: Confirm the JSON field name for the file path across
  `Write`, `Edit`, and `MultiEdit` — they may differ. The script should handle
  all three.
- **False positives during OOP**: When the stakeholder says "out of process,"
  the team-lead may legitimately need to write something directly. Consider
  a bypass mechanism — e.g., the presence of a `.clasi-oop` flag file that
  the hook checks before blocking, set and cleared by the ad-hoc-executor
  dispatch tool.
