---
id: "001"
title: "Inline CLASI block into CLAUDE.md in init command"
status: todo
use-cases:
  - SUC-017-001
depends-on: []
---

# Inline CLASI block into CLAUDE.md in init command

## Description

Modify `init_command.py` so that `clasi init` writes the CLASI process
block directly into CLAUDE.md instead of creating an `@AGENTS.md`
reference and writing to AGENTS.md.

Changes:
1. Replace `_update_agents_md()` with `_update_claude_md()` — same
   marker-based replacement logic, targeting CLAUDE.md instead.
2. Remove `_create_claude_md()` — its role is absorbed by `_update_claude_md`.
3. Delete `claude_agent_skills/init/claude-md.md` (the `@AGENTS.md` template).
4. Keep `agents-section.md` as the content source (it has the CLASI block
   with markers).
5. Update `run_init()` to call `_update_claude_md` instead of
   `_create_claude_md` + `_update_agents_md`.
6. Update module docstring and echo messages.

## Acceptance Criteria

- [ ] Fresh `clasi init` creates CLAUDE.md with full CLASI block inline
- [ ] Re-init on CLAUDE.md with existing CLASI markers replaces section
- [ ] Re-init on CLAUDE.md without markers appends CLASI block
- [ ] AGENTS.md is not created or modified
- [ ] `claude-md.md` template file is deleted
- [ ] All existing init tests pass (updated as needed)

## Testing

- **Existing tests to run**: `tests/unit/test_init_command.py`
- **New tests to write**: Update existing tests to verify CLAUDE.md
  contains the CLASI block inline, not `@AGENTS.md`. Verify AGENTS.md
  is untouched.
- **Verification command**: `uv run pytest`
