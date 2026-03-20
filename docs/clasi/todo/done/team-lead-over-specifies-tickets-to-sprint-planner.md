---
status: done
sprint: '024'
tickets:
- '007'
---

# Team Lead Over-Specifies Tickets When Dispatching to Sprint Planner

## Problem

The team lead is doing the sprint planner's job. When dispatching to the
sprint planner, the team lead provides fully pre-digested ticket
specifications — exact titles, detailed descriptions, dependency lists,
acceptance criteria formats, and even YAML frontmatter instructions.
The sprint planner ends up as a transcription agent, not a planning agent.

Evidence: In sprint 024 (see `docs/clasi/log/sprints/024-e2e-guessing-game-test/sprint-planner-002.md`),
the team lead's dispatch message contained:

- Exact ticket titles ("Ticket 004: Team-lead identity binding")
- Specific implementation steps ("Update CLAUDE.md (inside CLASI block)
  to state: ...")
- Pre-decided dependency lists ("No deps")
- Pre-decided use-case mappings ("use-cases: []")
- Frontmatter format instructions ("Each ticket needs: YAML frontmatter
  (id, title, status: todo, use-cases, depends-on, todo: 'filename.md'),
  description, acceptance criteria, testing section.")

The sprint planner had no planning decisions to make. It received a
complete specification and just wrote it to files.

This is the same class of problem as the TODO delegation issue
(see `docs/clasi/todo/fix-todo-delegation.md`), but applied to the
team-lead-to-sprint-planner boundary instead of the team-lead-to-todo-worker
boundary.

## Desired Behavior

1. **Team lead identifies work** — reviews TODOs, stakeholder input, and
   sprint goals. Determines which TODOs belong in the sprint.
2. **Team lead dispatches to sprint planner with high-level goals** — the
   dispatch should contain:
   - The sprint's high-level goals and scope
   - References to relevant TODO files (by path) that should be addressed
   - Any stakeholder constraints or priorities
   - The sprint context (what came before, what's next)
3. **Sprint planner does the planning** — the sprint planner reads the
   referenced TODOs, understands the goals, and makes the planning
   decisions:
   - How to decompose goals into tickets
   - What each ticket's scope and acceptance criteria should be
   - What dependencies exist between tickets
   - How to sequence the work
   - What the right ticket titles and descriptions are

The team lead should say something like: "Plan sprint 024 for these
goals: get the E2E guessing game test passing, fix process issues. Include
these TODOs: `docs/clasi/todo/team-lead-identity-binding.md`,
`docs/clasi/todo/revise-architecture-process.md`,
`docs/clasi/todo/fix-todo-delegation.md`."

The team lead should NOT say: "Create ticket 004 with title X,
description Y, deps Z, acceptance criteria A, B, C."

## Changes Needed

1. **Team-lead agent definition** — Update instructions to state: when
   dispatching to the sprint planner, provide high-level goals and TODO
   references, not pre-digested ticket specifications. The team lead
   decides WHAT goes into a sprint; the sprint planner decides HOW to
   structure it into tickets.

2. **Sprint-planner agent definition** — Confirm the sprint planner's
   instructions make clear that it is responsible for all ticket
   decomposition, scoping, and specification. It should read the
   referenced TODOs and produce its own ticket breakdown.

3. **Dispatch protocol** — The team lead's dispatch to the sprint
   planner should look like: "Plan this sprint with these goals and
   these TODOs: [list of TODO paths]" — not "Create these specific
   tickets with these specific fields."
