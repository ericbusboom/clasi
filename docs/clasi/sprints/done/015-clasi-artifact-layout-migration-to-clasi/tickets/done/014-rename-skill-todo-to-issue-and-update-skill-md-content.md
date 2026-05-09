---
id: '014'
title: Rename skill `/todo` to `/issue` and update SKILL.md content
status: done
use-cases:
  - SUC-001
depends-on:
  - "013"
github-issue: ''
todo: rename-clasi-todos-to-issues.md
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Rename skill `/todo` to `/issue` and update SKILL.md content

## Description

Rename `clasi/plugin/skills/todo/` to `clasi/plugin/skills/issue/`. Update `SKILL.md`
inside the directory to use "issue" terminology (`name: issue`, description updated).
Update any platform installer or init command that references the old skill directory name.

## Acceptance Criteria

- [x] `clasi/plugin/skills/issue/` exists; `clasi/plugin/skills/todo/` is deleted
- [x] `SKILL.md` has `name: issue` and updated description
- [x] Any platform installer reference to `skills/todo` updated to `skills/issue`
- [x] `init_command.py` reference updated if it copies the skill
- [x] `clasi install` installs the skill as `/issue` not `/todo`
- [x] Full test suite passes

## Implementation Plan

### Files to modify
- `clasi/plugin/skills/todo/SKILL.md` (rename directory, update content)
- `clasi/init_command.py` — any skill directory reference
- Platform installers if they enumerate skill directories

### Testing plan
- Install to a temp dir and verify `.claude/skills/issue/` is created
- `uv run pytest` — full suite
