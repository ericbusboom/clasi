---
name: software-engineering
description: Instructions for the software engineering process using brief, use cases, technical plan, tickets, and ticket plans
---

# Software Engineering Process

This project follows a structured software engineering workflow. All planning
artifacts live in `docs/plans/`.

## Agents

Seven specialized agents drive this process, orchestrated by the
project-manager:

- **project-manager** — Top-level orchestrator. Delegates to the other
  agents, tracks project state, and coordinates sprints and ticket execution.
  Does not implement code or write documents itself.
- **product-manager** — Guides project initiation interviews. Takes a
  stakeholder narration and produces the project overview document.
- **requirements-analyst** — Elicits detailed requirements from stakeholder
  narratives. Produces the brief and use cases for complex projects.
- **architect** — Maintains the versioned system architecture. Produces
  `docs/plans/architecture/architecture-NNN.md` documents and sprint
  technical plans. Two modes: initial architecture and sprint update.
  See `instructions/architectural-quality.md` for quality criteria.
- **technical-lead** — Breaks the technical plan into sequenced, numbered
  tickets. Creates ticket plans before implementation begins.
- **architecture-reviewer** — Reviews sprint plans and architecture updates
  for consistency, quality, and risk. Evaluates against the architectural
  quality guide. Produces verdicts with Design Quality Assessment.
- **code-reviewer** — Reviews code changes during ticket execution for
  quality, standards compliance, and security. Produces pass/fail verdicts.

Supporting agents used during implementation:
- **python-expert** — Implements Python code during ticket execution.
- **documentation-expert** — Updates documentation during ticket execution.

## Skills

Reusable workflows that correspond to each stage:

- **project-initiation** — New project: narration → project overview
- **elicit-requirements** — Stage 1a: narrative → brief → use cases (detailed)
- **create-technical-plan** — Stage 1b: brief + use cases → technical plan
- **create-tickets** — Stage 2: technical plan → numbered tickets
- **execute-ticket** — Stage 3: ticket → plan → implement → test → done
- **project-status** — Anytime: scan artifacts and report progress
- **plan-sprint** — Plan and set up a new sprint
- **close-sprint** — Validate and close a completed sprint

Supporting skills used during ticket execution:

- **python-code-review** — Code review against coding standards and security
- **generate-documentation** — Create or update project documentation

## Artifacts

### 1. Project Overview (`docs/plans/overview.md`) — Recommended

A single lightweight document created at project start. Replaces the separate
brief, use cases, and technical plan files for new projects. Detailed planning
lives in sprints.

Contents:
- Project name
- Problem statement (what problem, who has it)
- Target users
- Key constraints (timeline, technology, budget)
- High-level requirements (key scenarios)
- Technology stack
- Sprint roadmap (rough plan of sprints)
- Out of scope

### 2. Architecture (`docs/plans/architecture/`)

Versioned architecture documents describing the system's structure. Each
version represents the target state after a sprint completes:

```
docs/plans/architecture/
  architecture-014.md   # Architecture at end of sprint 014
  architecture-015.md   # Architecture at end of sprint 015
  ...
```

The architect produces these documents; the architecture-reviewer evaluates
them. See `instructions/architectural-quality.md` for versioning rules,
document structure, and quality criteria.

Not every sprint requires a new architecture version — pure bug fixes and
refactors within existing boundaries skip it. The sprint technical plan
references which architecture version it targets.

### Legacy: Brief, Use Cases, Technical Plan

For existing projects that predate the overview document, these separate
top-level files remain valid:

- **Brief** (`docs/plans/brief.md`) — One-page project description.
- **Use Cases** (`docs/plans/usecases.md`) — Enumerated use cases (UC-001, etc.)
  with actor, preconditions, main flow, postconditions, acceptance criteria.
- **Technical Plan** (`docs/plans/technical-plan.md`) — Architecture, tech stack,
  component design, data model, APIs, deployment, security.

New projects should use `create_overview` instead of the three separate tools.

### Diagrams in Technical Plans

Use Mermaid diagrams in technical plans when they clarify structure that is
hard to convey in text alone. Diagrams should show the target state at the
end of the sprint.

**When to use diagrams:**
- Subsystem/component interaction diagrams (flowchart or C4-style)
- Module dependency diagrams showing how packages relate
- Data flow diagrams for complex pipelines

**When NOT to use diagrams:**
- Swim lane / sequence diagrams unless multi-system sequencing is involved
- Exhaustive class diagrams (too detailed, go stale quickly)
- Diagrams that merely restate what the text already says

**Best practices:**
- Keep diagrams small: 5-10 nodes maximum
- Use Mermaid syntax (renders in GitHub, VS Code, most markdown viewers)
- Label edges with the relationship (calls, depends-on, produces)
- One diagram per concern; do not overload a single diagram

### 4. Sprints (`docs/plans/sprints/NNN-slug/`)

Each sprint is a **directory** containing its planning documents and tickets.
Ticket numbering is per-sprint (starts at 001 within each sprint).

Directory structure:
```
docs/plans/sprints/NNN-slug/
├── sprint.md              # Sprint goals, scope, problem, solution, test strategy
├── usecases.md            # Sprint-level use cases (SUC-NNN)
├── technical-plan.md      # Sprint-level technical plan
└── tickets/
    ├── 001-first-task.md  # Active ticket
    ├── 002-next-task.md   # Active ticket
    └── done/              # Completed tickets and plans
        └── ...
```

Sprint frontmatter (`sprint.md`):
```yaml
---
id: "NNN"
title: Sprint title
status: planning | active | done
branch: sprint/NNN-slug
use-cases: [UC-XXX, ...]
---
```

Active sprints live in `docs/plans/sprints/`. Completed sprints live in
`docs/plans/sprints/done/`.

### 5. Tickets (within sprint: `tickets/NNN-slug.md`)

Numbered implementation tickets broken out from the technical plan.
Tickets are numbered per-sprint starting at 001.

File naming: `001-setup-project-skeleton.md`, `002-add-auth-endpoints.md`, etc.

Each ticket has YAML frontmatter:
```yaml
---
id: "NNN"
title: Short title
status: todo | in-progress | done
use-cases: [SUC-001, SUC-002]
depends-on: ["NNN"]
---
```

Followed by: description, acceptance criteria (checkboxes), and
implementation notes.

### 6. Ticket Plans (`tickets/NNN-slug-plan.md`)

Before starting work on a ticket, create a plan file with the same number
and slug, ending in `-plan`. For example, ticket `003-add-auth.md` gets a
plan file `003-add-auth-plan.md`. The plan lives in the same `tickets/`
directory as the ticket.

Every ticket plan must include:
1. **Approach** — How the work will be done, key decisions.
2. **Files to create or modify** — What will be touched.
3. **Testing plan** — What tests will be written, what type (unit, system,
   dev), what verification strategy.
4. **Documentation updates** — What docs need updating when the ticket is
   complete.

A ticket plan without a testing section and a documentation section is
incomplete.

### 7. TODO Directory (`docs/plans/todo/`)

A lightweight capture area for ideas, improvements, and future work items.
Stakeholders and developers add ideas here at any time — especially when the
AI agent is busy with other work.

**File format:**
- One markdown file per idea (descriptive filename, e.g., `versioning.md`).
- Each file has a single level-1 heading (`# Title`) followed by description.
- Files with multiple level-1 headings should be split using `clasi todo-split`.

**Lifecycle:**
1. **Capture**: Create a `.md` file in `docs/plans/todo/` with the idea.
2. **Mine**: During sprint planning, the project-manager scans the TODO
   directory and discusses relevant items with the stakeholder.
3. **Consume**: When a TODO is incorporated into a sprint, move the file
   to `docs/plans/todo/done/`.

Files in `todo/` are unordered and unprioritized — sprint planning is when
prioritization happens. The `done/` subdirectory preserves consumed TODOs
for reference.

## Workflow

### Project Setup (requirements-analyst)

Skill: **elicit-requirements**

1. Take the stakeholder's narrative about the project.
2. Ask clarifying questions about stakeholders, components, requirements,
   constraints, and success criteria.
3. Write the project overview (`docs/plans/overview.md`) using the
   `create_overview` MCP tool. The overview covers problem, users,
   constraints, high-level requirements, tech stack, and sprint roadmap.
4. **Review gate**: Present the overview to the stakeholder. Wait for
   approval before proceeding. If the stakeholder requests changes, revise
   and re-present.

### Sprints (Default Working Mode)

After Stages 1a and 1b are complete, all work is organized into sprints.
A sprint is a focused batch of work with its own lifecycle, branch, and
ticket set.

**Sprint directories** live in `docs/plans/sprints/NNN-slug/`. Each sprint
directory contains `sprint.md`, `brief.md`, `usecases.md`,
`technical-plan.md`, and a `tickets/` subdirectory (see Artifacts §4 above).

**Sprint lifecycle** (skills: **plan-sprint**, **close-sprint**):
1. Stakeholder describes the next batch of work.
2. Create sprint directory with planning documents (brief, use cases,
   technical plan) and a `tickets/` subdirectory.
3. Create sprint branch (`sprint/NNN-slug`).
4. **Architecture review**: Delegate to the **architecture-reviewer** to
   validate the plan against the existing codebase and technical plan.
5. **Review gate**: Present the sprint plan and architecture review to the
   stakeholder. Wait for approval.
6. Create tickets for the sprint in `tickets/` (Stage 2 below).
7. Execute tickets on the sprint branch (Stage 3 below).
8. When all tickets are done, close the sprint (**close-sprint** skill).
   This is an atomic operation — all steps must be completed together:
   a. Merge the sprint branch to main.
   b. Update sprint status to `done` in `sprint.md` frontmatter.
   c. Move the sprint directory to `docs/plans/sprints/done/`.
   d. Delete the sprint branch.
   e. Commit the closure.
   **Never merge the branch without also archiving the sprint directory.**

Active sprints live in `docs/plans/sprints/`. Completed sprints live in
`docs/plans/sprints/done/`.

### Sprint State Database

A SQLite database at `docs/plans/.clasi.db` tracks sprint lifecycle state.
AIs interact with it exclusively through MCP tools — never write to the
database directly.

**Seven-phase lifecycle model:**

```
planning-docs → architecture-review → stakeholder-review → ticketing → executing → closing → done
```

Phase transitions are enforced: `advance_sprint_phase` validates that exit
conditions for the current phase are met before allowing the transition.

**Review gates** (required to advance past certain phases):

| Gate | Required to advance from | Recorded by |
|------|--------------------------|-------------|
| `architecture_review` | `architecture-review` → `stakeholder-review` | `record_gate_result` |
| `stakeholder_approval` | `stakeholder-review` → `ticketing` | `record_gate_result` |

Each gate must be recorded as `passed` before the phase can advance.

**Execution lock:**

Only one sprint can be in the `executing` phase at a time. Before advancing
from `ticketing` to `executing`, the sprint must acquire the execution lock
via `acquire_execution_lock`. The lock is released when the sprint is closed
(`close_sprint` releases it automatically).

**MCP tools for state management:**

- `get_sprint_phase(sprint_id)` — Query current phase, gates, and lock status
- `advance_sprint_phase(sprint_id)` — Move to the next phase (validates conditions)
- `record_gate_result(sprint_id, gate, result, notes?)` — Record a review gate outcome
- `acquire_execution_lock(sprint_id)` — Claim the execution lock
- `release_execution_lock(sprint_id)` — Release the execution lock

**Ticket creation gate enforcement:**

**IMPORTANT: DO NOT create tickets until the sprint reaches the `ticketing`
phase.** The `create_ticket` tool checks the state database and blocks ticket
creation if the sprint is before the `ticketing` phase. This prevents tickets
from being created before architecture and stakeholder reviews are complete.
Always follow the phase order: populate planning docs first, pass architecture
review, pass stakeholder review, then and only then create tickets.

### Stage 2: Ticketing (technical-lead)

Skill: **create-tickets**

1. Break the technical plan into numbered tickets in dependency order.
2. Ensure every use case is covered by at least one ticket.
3. Ensure every ticket traces to at least one use case.
4. **Review gate**: Present the ticket list to the stakeholder. Walk
   through the sequencing and coverage. Wait for approval before starting
   implementation. If the stakeholder requests changes, revise and re-present.

### Stage 3: Implementation (project-manager coordinates)

Skill: **execute-ticket** (repeated for each ticket)

1. Pick the next `todo` ticket whose dependencies are all `done`.
2. Create the ticket plan (`NNN-slug-plan.md`).
3. Set the ticket status to `in-progress` in its YAML frontmatter.
4. Implement the ticket following its plan (python-expert or appropriate
   dev agent).
5. Write tests as specified in the plan.
6. Delegate code review to the **code-reviewer** agent. The reviewer checks
   coding standards, security, test coverage, and acceptance criteria. If
   the review fails, fix the findings and re-review.
7. Update documentation as specified in the plan (documentation-expert).
8. Verify all acceptance criteria are met and check them off (`[x]`).
9. Complete the ticket (see **Completing a Ticket** below).

#### Definition of Done

A ticket is not done until ALL of the following are true:

- [ ] All acceptance criteria in the ticket are met and checked off
- [ ] Tests are written and passing (see `instructions/testing.md`)
- [ ] Code review passed by **code-reviewer** (coding standards, security, test coverage)
- [ ] Documentation updated as specified in the ticket plan
- [ ] Changes committed to git with a message referencing the ticket ID
- [ ] Ticket and plan moved to the sprint's `tickets/done/` directory

Do not mark a ticket done if any item is incomplete. If an item cannot be
satisfied, document why in the ticket before completing.

#### Completing a Ticket

When a ticket satisfies the Definition of Done:

1. Set the ticket's `status` to `done` in its YAML frontmatter.
2. Check off all acceptance criteria (`- [x]`).
3. Commit all changes following `instructions/git-workflow.md`. The commit
   message must reference the ticket ID and sprint number if applicable
   (e.g., `feat: add auth endpoint (#003, sprint 001)`).
4. Move the ticket file to the sprint's `tickets/done/` directory.
5. Move the ticket plan file to the sprint's `tickets/done/` directory.

Active tickets live in the sprint's `tickets/` directory. Completed tickets
live in `tickets/done/`. This separation makes it easy to see at a glance
what work remains (active directory) versus what has been finished (done
directory).

#### Error Recovery

Things go wrong during implementation. Here is what to do.

**Test failures:**
1. Read the error output carefully. Diagnose the root cause.
2. Fix the code (not the test, unless the test is wrong).
3. Re-run the tests. Repeat until all pass.
4. If the failure reveals a flaw in the ticket plan, update the plan.

**Plan gaps** (the plan missed something needed for implementation):
1. If the gap is small and local (e.g., a missing helper function), update
   the ticket plan and continue.
2. If the gap is architectural (e.g., a missing component, wrong API design),
   stop implementation. Flag the gap to the architect. Update the technical
   plan first, then update the ticket plan, then resume.

**Ticket too large** (the ticket is taking much longer than expected):
1. Stop and assess what is done vs. what remains.
2. Split the ticket: complete and close the part that is done (with tests).
3. Create a new ticket for the remaining work. Update dependencies so the
   new ticket depends on the closed one.
4. Resume with the new ticket.

**Unresolvable blockers:**
1. If you cannot make progress despite trying the above patterns, stop.
2. Document what you tried and what blocked you in the ticket.
3. Set the ticket status back to `todo` (not `in-progress` — it is not
   being actively worked).
4. Escalate to the human: explain the blocker and ask for guidance.

### Stage 4: Maintenance

1. If a change alters scope, update the brief and affected use cases first.
2. If new work is needed, create new tickets following the numbering
   sequence.

## Directory Layout

```
docs/plans/
├── overview.md                  # Project overview (recommended)
├── brief.md                     # Top-level brief (legacy)
├── usecases.md                  # Top-level use cases (legacy)
├── technical-plan.md            # Top-level technical plan (legacy)
├── architecture/                # Versioned architecture documents
│   ├── architecture-014.md      # Architecture at end of sprint 014
│   ├── architecture-015.md      # Architecture at end of sprint 015
│   └── ...
├── todo/                        # Ideas and future work
│   ├── some-idea.md             # One idea per file
│   └── done/                    # Consumed TODOs (archived)
│       └── ...
└── sprints/
    ├── 001-mcp-server/          # Active sprint directory
    │   ├── sprint.md            # Sprint goals, scope, notes
    │   ├── brief.md             # Sprint-level brief
    │   ├── usecases.md          # Sprint-level use cases
    │   ├── technical-plan.md    # Sprint-level technical plan
    │   └── tickets/
    │       ├── 003-add-auth.md      # Active ticket
    │       ├── 003-add-auth-plan.md # Its plan
    │       └── done/                # Completed tickets
    │           ├── 001-setup.md
    │           └── 001-setup-plan.md
    └── done/                    # Completed sprint directories
        └── 000-initial-setup/
            ├── sprint.md
            └── tickets/done/
                └── ...
```

## Rules for AI Assistants

- The **project-manager** is the entry point for new projects. It determines
  current state and delegates to the right agent/skill.
- After initial setup (brief, use cases, technical plan), always work within
  a sprint. Use **plan-sprint** to start and **close-sprint** to finish.
- When asked to plan work, produce or update these artifacts rather than
  jumping straight to code.
- When asked to implement, find the next unfinished ticket and work from it.
- Always create a ticket plan before starting implementation.
- A ticket is not done until it satisfies the **Definition of Done** (see
  above): acceptance criteria met, tests passing, code review passed,
  documentation updated, changes committed to git.
- Delegate code review to the **code-reviewer** agent, not self-review.
- Delegate architecture review to the **architecture-reviewer** agent during
  sprint planning.
- Follow `instructions/coding-standards.md` when writing code.
- Follow `instructions/git-workflow.md` when committing changes.
- Follow `instructions/testing.md` when writing tests.
- Follow `instructions/architectural-quality.md` for architecture decisions.
- When a ticket is completed, follow the **Completing a Ticket** steps
  immediately — do not batch completions.
- Do not create new artifacts without updating the existing ones to stay
  consistent.
- If a change alters scope, update the brief and affected use cases first.
- Use the **project-status** skill at any time to check where things stand.
