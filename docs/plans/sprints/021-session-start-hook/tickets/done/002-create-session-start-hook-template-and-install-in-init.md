---
id: "002"
title: "Create session-start hook template and install in init"
status: done
use-cases: [SUC-001, SUC-002]
depends-on: ["001"]
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Create session-start hook template and install in init

## Description

Using the hook mechanism determined in ticket 001, implement the
session-start hook and integrate it into the `clasi init` command.

Tasks:

1. **Create the hook content** — Write the session-start hook that
   outputs a message triggering the agent to load the SE process (e.g.,
   calling `get_se_overview()`). The hook format must match the mechanism
   confirmed in ticket 001.
2. **Modify `init_command.py`** — Add logic to the init command that
   installs the hook configuration into the target project. This may
   involve writing to `.claude/settings.local.json`, creating files in
   `.claude/hooks/`, or whatever mechanism ticket 001 identified.
3. **Ensure idempotency** — Running `clasi init` twice must produce the
   same result as running it once. The hook must not be duplicated,
   corrupted, or removed on subsequent runs. Check for existing hook
   before writing; update in place if the content has changed.

The existing CLAUDE.md directive ("you MUST call `get_se_overview()`")
remains as a belt-and-suspenders backup. This hook adds mechanical
enforcement on top of the prose directive.

## Acceptance Criteria

- [x] Session-start hook is created during `clasi init`
- [x] Hook triggers SE process loading at session start (agent sees the trigger message)
- [x] Installation is idempotent — running init twice produces the same result, no duplication
- [x] Existing CLAUDE.md directive is preserved (not removed or modified)
- [x] Hook format matches the mechanism confirmed in ticket 001

## Testing

- **Existing tests to run**: `uv run pytest` (full suite — no regressions)
- **New tests to write**: Covered by ticket 003
- **Verification command**: `uv run pytest`
