---
name: se
description: CLASI Software Engineering process dispatcher
---

# /se

Dispatch to the CLASI SE process. Parse the argument after `/se` and
invoke the matching skill from the table below.

If `/se` is called with **no arguments**, display this help listing
to the user and stop — do not execute any skill.

## Available commands

| Command | Description | Action |
|---------|-------------|--------|
| `/se status` | Show project status — sprints, tickets, next actions | Invoke the `project-status` skill |
| `/se todo <text>` | Create a TODO file from the description | Invoke the `todo` skill |
| `/se init` | Start a new project with a guided interview | Invoke the `project-initiation` skill |
| `/se report` | Report a bug with the CLASI tools | Invoke the `report` skill |
| `/se gh-import [repo] [--labels L]` | Import GitHub issues as TODOs | Invoke the `gh-import` skill |
| `/se knowledge <description>` | Capture hard-won technical understanding | Invoke the `project-knowledge` skill |
| `/se oop` | Make a quick out-of-process change | Invoke the `oop` skill |

Pass any remaining text after the subcommand as the argument to the
skill (e.g., `/se todo fix the login bug` passes "fix the login bug"
to the todo skill).
