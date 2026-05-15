---
id: '004'
title: 'Skill doc updates: issue lifecycle and split_issue'
status: done
use-cases:
- SUC-005
depends-on:
- '003'
github-issue: ''
issue: ''
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Skill doc updates: issue lifecycle and split_issue

## Description

Update four skill documentation files to describe the sprint-scoped issue lifecycle introduced in this sprint. No code changes. Pure documentation.

Depends on T3 so the `split_issue` tool exists before it is documented.

## Files to Modify

- `clasi/plugin/skills/issue/SKILL.md`
- `.claude/skills/plan-sprint/SKILL.md`
- `.claude/skills/create-tickets/SKILL.md`
- `.claude/skills/close-sprint/SKILL.md`

## Acceptance Criteria

- [x] `clasi/plugin/skills/issue/SKILL.md` has a "Splitting an Issue" section describing when and how to call `split_issue`.
- [x] `.claude/skills/plan-sprint/SKILL.md` Phase 2 / detail steps include: "For issues where only part of the scope fits this sprint, call `split_issue` to create a focused sibling issue before calling `create_ticket`."
- [x] `.claude/skills/create-tickets/SKILL.md` explains that `create_ticket(todo=<filename>)` calls `Issue.move_to_in_progress`, moving the issue into `<sprint>/issues/`, and that the issue moves to `<sprint>/issues/done/` automatically when all its tickets complete.
- [x] `.claude/skills/close-sprint/SKILL.md` states that close will hard-fail if any `<sprint>/issues/*.md` (top-level, not in `done/`) remains with `status: in-progress`, and describes two resolution paths: (a) complete the remaining tickets, (b) call `split_issue` and defer the new piece.
- [x] All four files are coherent with each other (no contradictions).
- [x] `uv run pytest` (full suite) passes (no code changed, but confirm no doc-parsing tests broke).

## Implementation Plan

### clasi/plugin/skills/issue/SKILL.md

Add a new section after "When to use this skill vs plan mode":

```markdown
## Splitting an Issue

When a sprint planner discovers that only part of an issue fits in the
current sprint, use the `split_issue` MCP tool:

1. Call `split_issue(filename, new_filename, new_title, new_body)`.
   - `filename`: the original issue file.
   - `new_filename`: a new slug for the split-off piece.
   - `new_title`, `new_body`: content for the new file.
   - `updated_body` (optional): replacement body for the original.
2. The new file is created as a sibling of the original in the same
   directory. If the original is sprint-scoped and in-progress, the
   new file inherits the sprint context; otherwise it starts as pending
   in the pool.
3. Both files get mutual cross-link frontmatter (`split_from` /
   `split_into`).
4. Then call `create_ticket(todo=<new_filename>)` if you want the new
   piece in the current sprint, or leave it in the pool for a future
   sprint.
```

### .claude/skills/plan-sprint/SKILL.md

In Phase 2: Detail Mode → Process, after step 2 (verify sprint exists), add before ticket creation:

```markdown
   2a. **Split partial-scope issues**: If any issue in scope covers work
       that cannot all fit in this sprint, call `split_issue` first to
       carve out the in-scope piece as a separate issue file. The split
       issue will be a sibling of the original in the same directory.
       Then call `create_ticket(todo=<split-filename>)` to bring the
       in-scope piece into the sprint. The remainder stays in the pool
       or sprint for a future sprint.
```

### .claude/skills/create-tickets/SKILL.md

Add a note in the section describing `create_ticket`:

```markdown
**Issue lifecycle:** When you call `create_ticket(sprint_id, title,
todo=<filename>)`, the referenced issue file is physically moved from
`.clasi/issues/` into `<sprint>/issues/` and its frontmatter is updated
to `status: in-progress`. When all tickets referencing that issue are
moved to done, `Issue.move_to_done()` is called automatically, which
moves the file into `<sprint>/issues/done/`. No manual `move_issue_to_done`
call is needed in the happy path.
```

### .claude/skills/close-sprint/SKILL.md

Add a section on issue preconditions:

```markdown
## Issue Preconditions

Close-sprint hard-fails if any `<sprint>/issues/<filename>` (at the top
level, not in `done/`) still has `status: in-progress`. Self-repair
handles done-tagged files automatically, but in-progress issues require
explicit resolution.

**Resolution paths:**
- **Tickets are done but issue not marked done**: this should not happen
  in the happy path. Call `move_issue_to_done` explicitly.
- **Issue has work remaining**: call `split_issue` to split the remaining
  work into a new issue, then either defer it (it stays in the pool for
  the next sprint) or call `create_ticket` to bring it into the current
  sprint before closing.
- **Issue is intentionally deferred**: set `completes_issue: false` on
  the ticket(s) referencing this issue. Close-sprint will then skip the
  hard-fail for that issue.
```

## Testing

- **No new tests** (documentation only).
- **Verification command**: `uv run pytest` to confirm no regressions.
