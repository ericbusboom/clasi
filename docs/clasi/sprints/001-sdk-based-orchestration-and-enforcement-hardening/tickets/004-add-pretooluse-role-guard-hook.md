---
id: '004'
title: Add PreToolUse role guard hook
status: todo
use-cases:
  - SUC-005
  - SUC-006
depends-on:
  - '003'
github-issue: ''
todo: sdk-orchestration-cluster/pretooluse-role-guard-hook.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Add PreToolUse role guard hook

## Description

Create a PreToolUse hook script that enforces the team-lead's delegation
role by blocking direct file writes to CLASI artifacts and source code.
This is the structural enforcement layer -- it makes role violations
impossible rather than relying on instructional compliance.

### hooks/role_guard.py

Create `role_guard.py` as a Python script in the CLASI package's
`init/hooks/` directory. It fires on PreToolUse events for the Edit,
Write, and MultiEdit tools. The script reads tool input JSON from stdin,
extracts the target file path, and applies the following decision logic:

1. **OOP bypass check** -- If a `.clasi-oop` flag file exists in the
   project root, exit 0 (allow all writes). This supports out-of-process
   work where the stakeholder has explicitly bypassed the SE process.

2. **Recovery state check** -- Query the state DB for an active
   `recovery_state` record. If one exists and the target file path is
   in the record's `allowed_paths` list, exit 0 (allow the write).
   This supports targeted recovery edits after `close_sprint` failures
   (SUC-006).

3. **Safe list check** -- If the target path matches the safe list
   (`.claude/`, `CLAUDE.md`, `AGENTS.md`), exit 0. These are
   configuration files that the team-lead legitimately manages.

4. **Block** -- For all other paths, output a descriptive error message
   naming the violation and suggesting the correct dispatch agent, then
   exit 1.

### init_command.py Updates

- Register the PreToolUse hook in the HOOKS_CONFIG for Edit, Write, and
  MultiEdit tools.
- Install `role_guard.py` to `.claude/hooks/` during `clasi init`.

### State DB Integration

The script imports from `state_db.py` to check for active recovery
state. This creates a dependency on ticket 003 (recovery_state table).

## Acceptance Criteria

- [ ] `hooks/role_guard.py` exists in the CLASI package
- [ ] Script reads tool input JSON from stdin and extracts the file path
- [ ] Checks OOP bypass (`.clasi-oop` flag file)
- [ ] Checks `recovery_state` `allowed_paths` via state_db
- [ ] Checks safe list (`.claude/`, `CLAUDE.md`, `AGENTS.md`)
- [ ] Blocks with descriptive error naming the violation and suggesting the correct agent
- [ ] Exits 0 to allow, exits 1 to block
- [ ] `init_command.py` registers PreToolUse hook for Edit, Write, and MultiEdit
- [ ] `init_command.py` installs `role_guard.py` to `.claude/hooks/`
- [ ] Unit tests for all decision paths (block, allow-safe, allow-recovery, allow-oop)

## Testing

- **Existing tests to run**: `tests/test_init_command.py` (verify init still works with new hook registration)
- **New tests to write**: `tests/test_role_guard.py` -- tests for each decision path: block non-safe path, allow safe list path, allow recovery state path, allow OOP bypass, block non-allowed path during recovery
- **Verification command**: `uv run pytest`
