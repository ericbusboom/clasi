---
name: software-engineering
description: Instructions for the software engineering process using overview, architecture, sprints, and tickets (each ticket carries its own Implementation Plan)
---

# Software Engineering Process

This project follows a structured software engineering workflow. All planning
artifacts live in `.clasi/`.

## Issues vs Tickets

Two distinct concepts govern how work is tracked:

- An **issue** is a proposed change to the system — an idea, bug report,
  enhancement request, or task captured before sprint planning. Issues live
  in `clasi/issues/`. They are the raw material that sprint planning draws
  from. A single issue may spawn one or more tickets, or be deferred
  indefinitely.

- A **ticket** is a concrete implementation step within a sprint. Tickets
  live in `clasi/sprints/<sprint-id>/tickets/`. A ticket is derived from
  (and often closes) an issue, but it is scoped to what can be done in a
  single sprint and carries acceptance criteria, a plan, and a status that
  the SE process enforces.

In short: issues propose; tickets implement.

## Agents

Three agents drive this process:

- **team-lead** — Top-level orchestrator, the agent the stakeholder talks
  to directly. Manages issues, dispatches planning and implementation,
  validates sprints, closes sprints. Never writes planning content or
  code itself. See `.claude/agents/team-lead/agent.md` for the full,
  authoritative process/routing detail — this file (and the
  plugin-source copy at `plugin/agents/team-lead/agent.md`, kept
  identical to it) is the canonical home for the team-lead's
  step-by-step; it is not repeated here.
- **sprint-planner** — Plans a sprint end-to-end in one dispatch: writes
  the sprint's Architecture and Use Cases sections (sized to the
  change — trivial/compact/substantial), records the
  `architecture_review` gate, and creates the sprint's tickets inline —
  all in a single dispatch, no separate ticket-materialization step.
  Folds in what earlier process generations split across separate
  architect, technical-lead, and architecture-reviewer agents. See the
  `plan-sprint` skill and `architecture-authoring`/`create-tickets`.
- **programmer** — Implements one ticket at a time: writes source code,
  tests, and documentation updates per the ticket's own Implementation
  Plan (embedded in the ticket file — there is no separate `-plan.md`
  file), runs the ticket's scoped tests in the foreground, and updates
  ticket frontmatter. Language-agnostic task worker. Folds in what
  earlier process generations split across python-expert/
  documentation-expert and a separate per-ticket code-reviewer agent —
  there is no mandatory per-ticket code-review gate in the current
  process (see `code-review` in Skills below for the on-demand skill).

Team-lead dispatches sprint-planner and programmer via the Agent tool.
Neither of the other two agents dispatches sub-agents itself.

## Skills

Reusable workflows that correspond to each stage:

- **project-initiation** — New project: spec → overview, specification, use cases
- **plan-sprint** — Roadmap (batch, lightweight) and Detail (full
  artifacts — architecture, review, tickets, all produced by one
  sprint-planner dispatch) sprint planning
- **execute-sprint** — Dispatches programmer agents one ticket at a time,
  in dependency order, on the sprint branch
- **close-sprint** — Validate and close a completed sprint
- **project-status** — Anytime: scan artifacts and report progress

Supporting skills used during ticket execution, sprint planning, or on demand:

- **create-tickets** — Ticket formatting, sequencing, and
  dependency-ordering conventions, used by sprint-planner inline during
  Detail Mode (not a separate dispatch or stage)
- **code-review** — Two-phase code review (correctness, then quality) —
  invoked on demand, not a mandatory per-ticket gate in the standard flow
- **tdd-cycle** — Optional red-green-refactor TDD workflow for implementation
- **systematic-debugging** — Structured four-phase debugging protocol with attempt cap
- **generate-documentation** — Create or update project documentation

## Artifacts

### 1. Project Overview (`overview.md` in the configured design directory) — Recommended

A single lightweight document created at project start. Replaces the separate
brief, use cases, and technical plan files for new projects. Detailed planning
lives in sprints.

The "configured design directory" is `Project.design_dir`: resolved
from `paths.design` in `.clasi/config.yaml` (the `paths:` map),
defaulting to `docs/design/` when unset. Never hardcode
`.clasi/design/` — that is not the default.

Contents:
- Project name
- Problem statement (what problem, who has it)
- Target users
- Key constraints (timeline, technology, budget)
- High-level requirements (key scenarios)
- Technology stack
- Sprint roadmap (rough plan of sprints)
- Out of scope

### 2. Architecture (`docs/architecture/`)

Each sprint's `sprint.md` contains an Architecture section, sized to the
change. This section is a **planning-time artifact**: the sprint-planner
authors it at the front of sprint planning, before any tickets are
created. It captures the structural intent for that sprint — what
components change, what design decisions are being made, and why.
Per-sprint Architecture sections accumulate as a chronological historical
record; they are never merged back into canonical design documents. Code
is the source of truth for current architecture; the per-sprint sections
are the record of structural intent over time. Canonical design documents
(`design/overview.md`, etc.) are project-initiation artifacts, frozen
after the project is initiated.

(Sprints planned before the single-doc rewrite — sprints 001-017 — carry
this content in a separate `architecture-update.md` file in the sprint
directory instead of a `sprint.md` section. Both forms coexist; read
whichever exists for a given sprint.)

The optional `docs/architecture/` directory holds **consolidated** architecture
documents produced by the `consolidate-architecture` skill. These merge
multiple sprints' Architecture sections into a single coherent view. They
are distinct from the per-sprint sections and are not required for every
project:

```
docs/architecture/
  architecture-014.md   # Consolidated architecture through sprint 014
  architecture-015.md   # Consolidated architecture through sprint 015
  ...
```

The sprint-planner produces each sprint's Architecture section and
performs its self-review during sprint planning (or records the review as
`skipped` for a trivial/small sprint). See
`instructions/architectural-quality.md` for document structure and quality
criteria.

Not every sprint requires architectural changes -- pure bug fixes and
refactors within existing boundaries can note "N/A — trivial" in the
sprint's Architecture section.

### Legacy: Brief, Use Cases, Technical Plan

For existing projects that predate the overview document, these separate
top-level files remain valid:

- **Brief** (`.clasi/brief.md`) — One-page project description.
- **Use Cases** (`.clasi/usecases.md`) — Enumerated use cases (UC-001, etc.)
  with actor, preconditions, main flow, postconditions, acceptance criteria.
- **Technical Plan** (`.clasi/technical-plan.md`) — Architecture, tech stack,
  component design, data model, APIs, deployment, security.

New projects should use the single `overview.md` in the configured
design directory instead of the three separate top-level files.

### Diagrams in Architecture Documents

Use Mermaid diagrams in architecture documents when they clarify structure
that is hard to convey in text alone. Diagrams should show the target state
at the end of the sprint.

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

### 4. Sprints (`clasi/sprints/NNN-slug/`)

Each sprint is a **directory** containing its planning documents and tickets.
Ticket numbering is per-sprint (starts at 001 within each sprint).

Directory structure:
```
clasi/sprints/NNN-slug/
├── sprint.md              # Sprint goals, scope, problem, solution, test
│                          # strategy, and Architecture + Use Cases sections
│                          # (right-sized to the change)
└── tickets/
    ├── 001-first-task.md  # Active ticket
    ├── 002-next-task.md   # Active ticket
    └── done/              # Completed tickets and plans
        └── ...
```

(Sprints planned before the single-doc rewrite — sprints 001-017 — have
separate `usecases.md` and `architecture-update.md` files alongside
`sprint.md` instead. Both forms coexist; new sprints use the single-doc
form above.)

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

Active sprints live in `clasi/sprints/`. Completed sprints live in
`clasi/sprints/done/`.

### 5. Tickets (within sprint: `tickets/NNN-slug.md`)

Numbered implementation tickets broken out from the architecture document.
Tickets are numbered per-sprint starting at 001.

File naming: `001-setup-project-skeleton.md`, `002-add-auth-endpoints.md`, etc.

Each ticket has YAML frontmatter:
```yaml
---
id: "NNN"
title: Short title
status: open | in-progress | done
use-cases: [SUC-001, SUC-002]
depends-on: ["NNN"]
github-issue: ""
issue: ""
completes_issue: true
---
```

Followed by: description, acceptance criteria (checkboxes), an
**Implementation Plan** (approach, files to create or modify, testing
plan, documentation updates), Process Notes, and a Testing section — all
embedded directly in the ticket file. There is no separate `-plan.md`
file: sprint-planner writes the plan in the same `create_ticket` call
that writes the description and acceptance criteria.

**Ticket frontmatter field reference:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Per-sprint ticket number (`"001"`, `"002"`, …). |
| `title` | string | Short human-readable title. |
| `status` | string | `open`, `in-progress`, or `done`. |
| `use-cases` | list | Sprint use-case IDs this ticket satisfies. |
| `depends-on` | list | Ticket IDs that must be done before this one starts. |
| `github-issue` | string | Linked GitHub issue number or URL, if any. |
| `issue` | string | Filename of the issue in `clasi/issues/` that this ticket addresses, if any. |
| `completes_issue` | bool or map | Controls whether linked issues are archived when this ticket is moved to done. **Default: `true`** — the issue is archived once all tickets that reference it are done. Set to `false` (scalar) to suppress archival for **all** issues linked to this ticket. Set to a mapping `{filename.md: false}` to suppress archival for specific issues by filename. Use `false` when this ticket only partially addresses a long-lived multi-sprint umbrella issue that should survive the sprint close. |

### 6. Issues Directory (`clasi/issues/`)

A lightweight capture area for proposed changes — ideas, bug reports,
enhancements, and tasks. Stakeholders and developers add issues here at any
time, especially when the AI agent is busy with other work.

**Issues vs Tickets** — An issue is a *proposed* change (lives in
`clasi/issues/`). A ticket is a *concrete implementation step* within a
sprint (lives in `clasi/sprints/<id>/tickets/`). Sprint planning converts
relevant issues into tickets; issues that are not yet scheduled remain open.

**File format:**
- One markdown file per idea (descriptive filename, e.g., `versioning.md`).
- Each file has a single level-1 heading (`# Title`) followed by description.

**Lifecycle:**
1. **Capture**: Create a `.md` file in `clasi/issues/` with the idea.
2. **Mine**: During sprint planning, the team-lead scans the issues
   directory and discusses relevant items with the stakeholder.
3. **Consume**: When an issue is incorporated into a sprint, it is closed
   via the MCP tool (frontmatter `status: done`).

### 7. Knowledge Directory (`docs/knowledge/`)

Captures hard-won technical understanding from difficult debugging sessions,
non-obvious fixes, and solutions that required significant trial and error.
Each file records what was broken, what was tried, what worked, why it works,
and actionable guidance for future agents.

This is distinct from reflections: reflections capture process failures (the
agent did something wrong), while knowledge captures technical victories
(the problem was genuinely hard and the solution should be preserved).

Knowledge files use the naming convention `YYYY-MM-DD-slug.md` and include
YAML frontmatter with date, tags, and related tickets. Use the
`project-knowledge` skill (`/se knowledge <description>`) to create entries.

## Workflow

### Project Setup (team-lead, via the project-initiation skill)

1. The stakeholder provides a written specification file.
2. Team-lead invokes the `project-initiation` skill with the spec path.
3. The skill processes the spec into structured documents:
   `overview.md`, `specification.md`, and `usecases.md`.
4. **Review gate**: Present the overview to the stakeholder. Wait for
   approval before proceeding. If the stakeholder requests changes, revise
   and re-present.

### Sprints (Default Working Mode)

After Stages 1a and 1b are complete, all work is organized into sprints.
A sprint is a focused batch of work with its own lifecycle, branch, and
ticket set.

**Sprint directories** live in `clasi/sprints/NNN-slug/`. Each sprint
directory contains `sprint.md` (with its Architecture and Use Cases
sections) and a `tickets/` subdirectory (see Artifacts §4 above).

**Sprint lifecycle** (skill: **plan-sprint**; agent: **sprint-planner**;
execution: **execute-sprint**; closing: **close-sprint**): a sprint moves
through phases `roadmap → planning-docs → architecture-review →
ticketing → executing → closing → done` (see Sprint State Database below
for the full phase/gate model). At a glance:

1. Stakeholder describes the next batch of work; team-lead captures any
   raw ideas as issues.
2. Team-lead calls `create_sprint` (directly, or via a sprint-planner
   Roadmap Mode dispatch) to create the sprint directory and a
   lightweight `sprint.md`.
3. Team-lead dispatches sprint-planner (Detail Mode) once: it writes the
   sprint's Architecture and Use Cases sections (or a `design/` overlay,
   if the project has opted in), records the `architecture_review` gate,
   and creates the sprint's tickets — all inline, in this one dispatch.
4. **Stakeholder review**: team-lead presents the completed plan *with
   its tickets already created* and records the `stakeholder_approval`
   gate.
5. Team-lead calls `acquire_execution_lock`, which grants the lock only
   if `stakeholder_approval` has passed and creates the sprint branch
   (`sprint/NNN-slug`).
6. Team-lead invokes **execute-sprint**, which dispatches programmer
   agents one ticket at a time, in dependency order, on the sprint
   branch.
7. When all tickets are done, team-lead invokes **close-sprint**, which
   atomically merges the branch to main, archives the sprint directory
   to `clasi/sprints/done/`, deletes the branch, and commits the
   closure. **Never merge the branch without also archiving the sprint
   directory.**

See `.claude/agents/team-lead/agent.md` for the full, authoritative
step-by-step (including the multi-sprint roadmap-arc variant) and
`schemas/se-process/instructions/sprint-plan.md` for the sprint-planner's
own Roadmap/Detail process — this summary is not repeated in either
direction.

Active sprints live in `clasi/sprints/`. Completed sprints live in
`clasi/sprints/done/`.

### Sprint State Database

A SQLite database at `.clasi/.clasi.db` tracks sprint lifecycle state.
AIs interact with it exclusively through MCP tools — never write to the
database directly.

**Seven-phase lifecycle model:**

```
roadmap → planning-docs → architecture-review → ticketing → executing → closing → done
```

Phase transitions are event-derived, not agent-driven (sprint 031 ticket
002): a sprint's *first* `create_ticket` call checks the
`architecture_review` gate directly and auto-advances the phase to
`ticketing`; a successful `acquire_execution_lock` call checks the
`stakeholder_approval` gate and auto-advances the phase to `executing`.
Neither requires a separate `advance_sprint_phase` call — no doc in the
standard flow instructs an agent to call it. `advance_sprint_phase` (the
MCP tool) still exists and remains usable for manual recovery from a
stranded phase value, but is not part of the standard flow.

**Review gates** (checked by the tool call that depends on them, not by
a phase-index comparison):

| Gate | Checked by | Recorded by |
|------|------------|-------------|
| `architecture_review` | `create_ticket` — sprint's first call; rejects (no ticket created) and the phase stays at `architecture-review` if not `passed`/`skipped` | `record_gate_result` (sprint-planner) |
| `stakeholder_approval` | `acquire_execution_lock` — rejects (no lock granted) if not `passed`/`skipped` | `record_gate_result` (team-lead, only after genuine stakeholder approval) |

**Execution lock:**

Only one sprint can be in the `executing` phase at a time. The
`stakeholder_approval` gate is checked *before* the lock is granted;
`acquire_execution_lock` then auto-advances the phase to `executing` and
creates the sprint branch. The lock is released when the sprint is closed
(`close_sprint` releases it automatically).

**MCP tools for state management:**

- `get_sprint_phase(sprint_id)` — Query current phase, gates, and lock status
- `record_gate_result(sprint_id, gate, result, notes?)` — Record a review gate outcome
- `acquire_execution_lock(sprint_id)` — Claim the execution lock; auto-advances the phase to `executing`
- `release_execution_lock(sprint_id)` — Release the execution lock
- `advance_sprint_phase(sprint_id)` — Manual single-hop recovery primitive; not used in the standard flow

**Ticket creation gate enforcement:**

`create_ticket` checks the `architecture_review` gate's recorded result
directly on a sprint's first call, and rejects if it is not
`passed`/`skipped`. Tickets are therefore created *before* the
stakeholder review, not after it: the sprint-planner authors the
architecture, records `architecture_review`, and creates tickets all in
one Detail Mode dispatch; the stakeholder then reviews the completed
plan *with its tickets already in place*.

### Ticketing (sprint-planner, inline within Detail Mode)

There is no separate ticketing stage or dispatch — sprint-planner creates
tickets as part of the same Detail Mode dispatch that writes the
Architecture section (see Sprint lifecycle above). For ticket formatting,
sequencing, and dependency-ordering conventions, see the `create-tickets`
skill:

1. Break the architecture's Sprint Changes into numbered tickets in dependency order.
2. Ensure every use case is covered by at least one ticket.
3. Ensure every ticket traces to at least one use case.

The stakeholder's review of the ticket list happens together with the
architecture review — the `stakeholder_approval` gate in Sprint lifecycle
step 4 above — not as a separate ticket-only review gate.

### Implementation (programmer, one ticket at a time)

Agent: **programmer**, dispatched once per ticket by team-lead via the
`execute-sprint` skill.

1. Team-lead dispatches the next `open` ticket whose dependencies are
   all `done`.
2. Programmer reads the ticket (description, acceptance criteria, and
   its Implementation Plan — already part of the ticket file; there is
   no separate `-plan.md` file) and sets its status to `in-progress`.
3. Programmer implements the ticket, writes tests, and updates docs per
   the ticket's own Implementation Plan.
4. Programmer runs the ticket's scoped tests in the foreground (never
   backgrounded) — not the full suite. **The full suite runs exactly
   once per sprint: inside `close_sprint` itself, as its own internal
   test-execution step (031/008).** No other point in the process
   re-runs it — `execute-sprint` does not run it before handing off to
   close, and `sprint-review` interprets `review_sprint_pre_close`'s
   result rather than re-running the suite itself. This sentence is
   the canonical statement of that fact; other docs that mention
   full-suite ownership (the programmer agent definition, the
   `source-code.md` rule, `close.md`) point back here rather than
   re-asserting a count of their own.
5. Programmer checks off all acceptance criteria, sets `status: done`,
   and commits, referencing the ticket ID.
6. Team-lead — not the programmer — calls `move_ticket_to_done(path)`.

There is no mandatory per-ticket code-review agent in the standard flow.
`code-review` is an on-demand skill, invoked when team-lead or the
stakeholder wants a second pass, not a gate between every ticket and
"done."

See `.claude/agents/programmer/agent.md` for the full, authoritative
workflow (error-recovery protocol, exception protocol, test-execution
rules) — not repeated here.

#### Definition of Done

A ticket is not done until ALL of the following are true:

- [ ] All acceptance criteria in the ticket are met and checked off
- [ ] Tests are written and passing, run in the foreground and scoped to
      the ticket (see `instructions/testing.md`)
- [ ] Documentation updated as specified in the ticket's own
      Implementation Plan
- [ ] Changes committed to git with a message referencing the ticket ID
- [ ] Ticket frontmatter `status` is `done`
- [ ] `move_ticket_to_done(path)` has been called (by team-lead)

Do not mark a ticket done if any item is incomplete. If an item cannot be
satisfied, document why in the ticket before completing.

Active tickets live in the sprint's `tickets/` directory. Completed
tickets live in `tickets/done/`, moved there atomically by
`move_ticket_to_done` — this separation makes it easy to see at a
glance what work remains versus what has finished.

#### Error Recovery

Things go wrong during implementation. Here is what to do.

**Test failures:**
1. Read the error output carefully. Diagnose the root cause.
2. Fix the code (not the test, unless the test is wrong).
3. Re-run the tests. Repeat until all pass.
4. If the failure reveals a flaw in the ticket's own Implementation Plan
   section, update it in place.
5. If simple diagnosis does not resolve the failure — especially after
   two consecutive failed fix attempts, or when a previously passing
   test breaks — invoke the `systematic-debugging` skill. This provides
   a structured four-phase protocol (evidence gathering, pattern analysis,
   hypothesis testing, root cause fix) and caps attempts at three before
   escalation (see Exception protocol below).

**Plan gaps** (the ticket's Implementation Plan missed something needed):
1. If the gap is small and local (e.g., a missing helper function), update
   the ticket's Implementation Plan section and continue.
2. If the gap is architectural (e.g., a missing component, wrong API
   design), stop implementation and throw a ticket exception (see
   Exception protocol below) rather than improvising a design decision.

**Ticket too large** (the ticket is taking much longer than expected):
1. Stop and assess what is done vs. what remains.
2. Split the ticket: complete and close the part that is done (with tests).
3. Create a new ticket for the remaining work. Update dependencies so the
   new ticket depends on the closed one.
4. Resume with the new ticket.

**Unresolvable blockers:**
1. If you cannot make progress despite trying the above patterns, stop.
2. Throw a ticket exception (see Exception protocol below), or — if the
   block is a guard/permission denial rather than a design conflict —
   report the block and stop; do not route around it.
3. Do not leave the ticket in an ambiguous state: `open` (not
   `in-progress`) unless an exception has been thrown, in which case its
   status is `exception` (see below).

## Exception protocol

Lower agents (programmer and sprint-planner) use the exception protocol to
escalate blocks that cannot be resolved within the agent's own authority.

### Threshold

Throw an exception when you cannot proceed without overriding an
upstream architecture decision or a use-case boundary — a structural
wall, not mere difficulty. Hard implementation work, even very hard
work, is not by itself a threshold for `throw_ticket_exception`.

Separately, after **three failed fix attempts** on the same problem
during normal debugging (see Error Recovery above and the
`systematic-debugging` skill), stop, revert partial or broken changes,
and escalate to team-lead with the evidence gathered. That escalation is
a report-and-stop, not automatically a `throw_ticket_exception` call —
call `throw_ticket_exception` only if the underlying blocker also turns
out to be the structural kind this section describes.

### Payload schema

The `throw_ticket_exception` MCP tool writes an `exception:` block to the
ticket frontmatter and sets `status: exception`:

```yaml
exception:
  thrown_by: programmer        # "programmer" or "sprint-planner"
  thrown_at: 2026-05-07T14:23:00Z
  attempted: |
    Summary of what was tried before concluding the wall is structural.
  conflict: |
    Exact description of what blocked progress — architecture decision,
    missing dependency, contradictory requirements, etc.
  surface: internal            # "internal" or "user-visible"
```

### Ticket as carrier

The ticket itself is the exception carrier. Its `status` is set to
`exception`; the `exception:` block records the full context. The ticket is
**not** moved to `done/` — it stays in `tickets/` so the team-lead can
inspect and route it.

### Team-lead routing

When the team-lead sees a ticket with `status: exception`, it chooses one of
the following routing branches:

| `surface` value | Routing |
|-----------------|---------|
| `internal`      | Team-lead resolves autonomously: dispatch sprint-planner to update the architecture or the ticket's Implementation Plan section, reopen with `reopen_ticket`, then continue. |
| `user-visible`  | Team-lead escalates to the stakeholder: present the conflict and wait for a decision before proceeding. |

### Revision naming convention

When reopening an exception ticket after resolution, add a `## Revision`
section or update the title to indicate what changed. Do not silently
re-execute the same plan that failed.

### Calibration signal

A sprint with more than one or two exception tickets signals a planning
problem. Escalate to the stakeholder for scope review rather than resolving
each exception in isolation.

### Stage 4: Maintenance

1. If a change alters scope, update the brief and affected use cases first.
2. If new work is needed, create new tickets following the numbering
   sequence.

## Directory Layout

```
.clasi/
├── brief.md                     # Top-level brief (legacy)
├── usecases.md                  # Top-level use cases (legacy)
├── technical-plan.md            # Top-level technical plan (legacy, pre-sprint 016)
docs/
├── design/                      # Configured design dir (paths.design), default shown
│   └── overview.md              # Project overview (recommended)
└── architecture/                # Versioned architecture documents
    ├── architecture-014.md      # Architecture at end of sprint 014
    ├── architecture-015.md      # Architecture at end of sprint 015
    └── ...
clasi/
├── issues/                      # Proposed changes (ideas, bugs, enhancements)
│   └── some-idea.md             # One issue per file
├── knowledge/                   # Hard-won technical understanding
│   └── YYYY-MM-DD-slug.md       # One knowledge entry per file
└── sprints/
    ├── 001-mcp-server/          # Active sprint directory
    │   ├── sprint.md            # Sprint goals, scope, notes, plus
    │   │                        # Architecture + Use Cases sections
    │   └── tickets/
    │       ├── 003-add-auth.md  # Active ticket (its Implementation
    │       │                    # Plan is a section inside this file,
    │       │                    # not a separate -plan.md file)
    │       └── done/            # Completed tickets
    │           └── 001-setup.md
    └── done/                    # Completed sprint directories
        └── 000-initial-setup/
            ├── sprint.md
            └── tickets/done/
                └── ...
```

## External Tooling

CLASI manages the SE process. Other operational concerns are handled by
dedicated tools — use them instead of ad hoc commands:

| Concern | Tool | How to learn more |
|---------|------|-------------------|
| Environment config, .env files, secrets, encryption keys | **dotconfig** | `dotconfig agent` or `instructions/dotconfig` |
| Deployments, Docker, databases, remote servers | **rundbat** | `rundbat mcp --help` or `instructions/rundbat` |
| GitHub issues (create, import, close) | **gh CLI** via CLASI MCP tools | `list_github_issues`, `close_github_issue`, `create_github_issue` |

When a project has these tools configured, prefer them over raw commands.
For example: use `dotconfig save` instead of editing files under `config/`
directly; use rundbat MCP tools instead of writing raw `docker run`
commands.

## Rules for AI Assistants

- The **team-lead** is the entry point for every session. It determines
  current state and dispatches sprint-planner/programmer as needed — see
  `.claude/agents/team-lead/agent.md`.
- After initial setup (overview, architecture), always work within a
  sprint. Use **plan-sprint** to start and **close-sprint** to finish.
- When asked to plan work, dispatch sprint-planner to produce or update
  the sprint's planning artifacts rather than jumping straight to code.
- When asked to implement, find the next unfinished ticket and dispatch
  a programmer agent to work from it.
- A ticket's Implementation Plan lives in the ticket file itself — there
  is no separate `-plan.md` file to create.
- A ticket is not done until it satisfies the **Definition of Done** (see
  above): acceptance criteria met, tests passing (scoped, foreground),
  documentation updated, changes committed to git, and
  `move_ticket_to_done` called.
- Code review is an on-demand skill (`code-review`), not a mandatory
  per-ticket gate — invoke it when team-lead or the stakeholder wants a
  second pass, not automatically between every ticket and "done."
- Sprint-planner performs its own architecture self-review during
  planning (see `architectural-quality.md`); there is no separate
  architecture-reviewer agent.
- Follow `instructions/coding-standards.md` when writing code.
- Follow `instructions/git-workflow.md` when committing changes.
- Follow `instructions/testing.md` when writing tests.
- Follow `instructions/architectural-quality.md` for architecture decisions.
- Do not create new artifacts without updating the existing ones to stay
  consistent.
- Use the **project-status** skill at any time to check where things stand.
