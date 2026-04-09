---
status: done
sprint: '004'
tickets:
- '001'
---

# ExitPlanMode -> CLASI TODO Integration

## Context

Plan mode stores plan files at `~/.claude/plans/<random-name>.md`. These files are ephemeral and disconnected from the CLASI TODO system. We want approving out of plan mode to automatically create a TODO in `docs/clasi/todo/`, then delete the original plan file.

## Approach: PostToolUse Hook on ExitPlanMode

Add a PostToolUse hook that fires after `ExitPlanMode` and copies the plan content into the CLASI TODO directory with proper frontmatter.

### Files to Create

1. **`.claude/hooks/plan_to_todo.py`** — thin dispatcher (matches existing pattern)
2. **New handler in `clasi/hook_handlers.py`** — `handle_plan_to_todo(payload)`

### Handler Logic (`handle_plan_to_todo`)

1. Find the plan file: scan `~/.claude/plans/` for the most recently modified `.md` file
2. Read the plan content
3. Extract the title from the first `# ` heading (fall back to plan filename if none)
4. Slugify the title using existing `clasi.templates.slugify()`
5. Build TODO content: frontmatter `status: pending` + full plan content as-is
6. Handle filename collisions: append `-2`, `-3`, etc.
7. Write the file to `docs/clasi/todo/{slug}.md`
8. Delete the original plan file from `~/.claude/plans/`
9. Print confirmation: `CLASI: Plan saved as TODO: docs/clasi/todo/{slug}.md`
10. Exit 0

### Edge Cases

- No `.md` files in `~/.claude/plans/` -> exit 0 silently
- Plan file has no `# ` heading -> use the plan filename as slug
- `docs/clasi/todo/` doesn't exist -> create it
- Plan file is empty -> skip, exit 0
