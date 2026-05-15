---
id: '004'
title: Rename documentation references from todo to issue
status: done
use-cases:
- SUC-004
depends-on:
- '003'
issue: finish-the-todo-issue-rename.md
---

## Description

Update user-facing documentation files to use the current vocabulary. This
covers the `software-engineering.md` frontmatter schema example and field
reference table, `README.md` prose, and the `se/SKILL.md` command table.

Files in scope (exact locations from the issue audit):
- `clasi/plugin/instructions/software-engineering.md:211-212, 229-230`
- `README.md:44, 117, 142, 162`
- `clasi/plugin/skills/se/SKILL.md:22, 25`

## Acceptance Criteria

- [x] `software-engineering.md:211-212`: frontmatter example block updated — `todo: ""` → `issue: ""` and `completes_todo: true` → `completes_issue: true`
- [x] `software-engineering.md:229-230`: field reference table rows for `todo` and `completes_todo` renamed to `issue` and `completes_issue`; description prose "Controls whether linked TODOs are archived" updated to "Controls whether linked issues are archived"
- [x] `README.md:44`: `/todo` skill stub reference updated to `/issue`
- [x] `README.md:117`: `/todo <description>` command entry updated to `/issue <description>`
- [x] `README.md:142`: `codex-plan-to-todo` hook reference updated to `codex-plan-to-issue`; if the line documents the deprecated alias explicitly, it is marked as deprecated rather than removed
- [x] `README.md:162`: `plan-to-todo` prose updated to `plan-to-issue`
- [x] `se/SKILL.md:22`: "Import GitHub issues as TODOs" → "Import GitHub issues as issues"
- [x] `se/SKILL.md:25`: "Enter plan mode for a discussed TODO" → "Enter plan mode for a discussed issue"
- [x] No other lines in these files are modified
- [x] Full test suite passes

## Implementation Plan

### Approach

Read each file at the listed line numbers. Make targeted replacements.
For `README.md:142`, determine whether the line documents the deprecated
alias for users — if so, add a "(deprecated)" or similar marker rather
than removing the reference.

### Files to Modify

- `clasi/plugin/instructions/software-engineering.md`
- `README.md`
- `clasi/plugin/skills/se/SKILL.md`

### Testing Plan

- Run `pytest tests/unit/` — no test coverage for docs, but confirm suite
  stays green.
- Review diff carefully for `README.md:142`: the deprecated alias line
  should be preserved with a deprecation note, not silently deleted.

### Documentation Updates

These files are themselves the documentation being updated.
