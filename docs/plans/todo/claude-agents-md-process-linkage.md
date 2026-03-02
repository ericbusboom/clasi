---
status: todo
---

# Ensure CLAUDE.md and AGENTS.md link the CLASI process

## Context

Recent completed work notes that `clasi init` should install `AGENTS.md` and
provide agent-facing process guidance, plus update/create `CLAUDE.md` to point
at the software engineering process.

## Requirements

- `clasi init` creates or updates `CLAUDE.md` with an explicit @reference to
  `AGENTS.md` when `CLAUDE.md` is missing.
- `AGENTS.md` starts with a strong, explicit warning that any code-changing
  work must follow the CLASI software engineering process.
- `AGENTS.md` includes a replaceable, delimited block for the process
  overview (so later updates can safely replace the block).
- The process block instructs the agent to start by running `/se` to
  understand the process, then gives a short overview of the stages and
  points to the relevant activity commands for details (requirements,
  architecture, ticketing, sprint/implementation).
- The overview is brief and directive (not a full process description),
  emphasizing when to reference the process (new projects, planning work,
  ticket execution).

## Acceptance Criteria

- Running `clasi init` on a project without `CLAUDE.md` creates it with a
  reference to `AGENTS.md`.
- `AGENTS.md` includes the explicit process warning at the very top.
- `AGENTS.md` contains a clearly delimited block containing the short process
  overview and `/se` instructions.
- The block explicitly calls out which kinds of work should reference the
  process (project initiation, planning, executing tickets).
