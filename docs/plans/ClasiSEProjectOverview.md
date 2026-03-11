---
status: draft
created: "2026-03-10"
audience: "LLM researcher performing comparative software-process analysis"
---

# CLASI Software Engineering Process — Complete Reference

*Current as of: 2026-03-10*

## 1. Executive Summary

CLASI (Claude Agent Skills Instructions) is a software engineering process
designed for AI coding agents — specifically LLMs operating as autonomous
software engineers inside a code editor. It provides a pip-installable
Python package that stores canonical agent definitions, skill workflows,
coding instructions, and an MCP (Model Context Protocol) server that
exposes 30 tools for managing sprints, tickets, architecture documents,
and lifecycle enforcement.

The CLASI code is [available at https://github.com/ericbusboom/claude-agent-skills](https://github.com/ericbusboom/claude-agent-skills)

The fundamental insight behind CLASI is that **LLM agents do not reliably
follow behavioral instructions alone**. Over 15 sprints and 8 formal
reflections, every single process failure was categorized as
`ignored-instruction` — the agent knew the rules and violated them
anyway. CLASI responds by encoding as much of the process as possible into
mechanical enforcement: a SQLite state machine with phase transitions,
review gates, and execution locks that physically prevent agents from
skipping steps.

This document is written for another language model that will perform
deeper comparative research against established software processes (Scrum,
RUP, SAFe, DSDM, Spiral Model, and emerging AI agent frameworks). It
provides complete detail on every component, enforcement mechanism, and
known inconsistency.

---

## 2. Motivations and Design Philosophy

### 2.1 The Core Problem

AI coding agents — even highly capable ones — exhibit three systematic
failure modes when operating under a defined software process:

1. **Process bypass**: The agent skips the process entirely and jumps
   straight to writing code. When told to plan first, it plans in its
   head and starts coding. When told to create a sprint, it creates files
   directly.

2. **Wrong tool selection**: The agent uses generic tools (e.g., the
   built-in `TodoWrite` tool or ad-hoc `git` commands) instead of the
   process-specific tools designed to enforce lifecycle rules. This
   bypasses all enforcement.

3. **Completion bias**: The agent reports work as "done" before
   completing all required steps. Code is written but the ticket isn't
   moved. The sprint branch is merged but the directory isn't archived.
   Status fields say "done" but the file is in the wrong location.

These are not occasional errors. They are the default behavior. Without
active countermeasures, agents fail at process compliance more often than
they succeed.

### 2.2 Evidence: The Reflection Corpus

CLASI maintains a formal reflection mechanism. When a stakeholder corrects
an agent's behavior, the agent produces a structured reflection document.
All 8 reflections in this project share the same category:

| Date | Sprint | Failure |
|------|--------|---------|
| 2026-02-11 | 001 | Failed to detect two stakeholder scoldings; did not run self-reflect |
| 2026-02-11 | 001 | Skipped all interactive review gates — no stakeholder interaction |
| 2026-02-11 | 002 | Closed sprint without asking stakeholder for confirmation |
| 2026-02-13 | 011 | Used wrong skill (`finishing-a-development-branch` instead of `close-sprint`) |
| 2026-03-05 | 004 | Merged and closed sprint without stakeholder approval, then started ad-hoc work |
| 2026-03-06 | — | MCP server was down; agent created a rogue `backlog.md` instead of reporting failure |
| 2026-03-08 | — | Jumped into editing files without following SE process; used `TodoWrite` instead of CLASI skill |
| 2026-03-08 | — | Rewrote 27 files for TypeScript strict mode instead of fixing a build config issue (scope explosion) |

Every reflection is `category: ignored-instruction`. The pattern is
clear: agents know what to do and do not do it.

### 2.3 Design Response

CLASI addresses these failures through three interlocking strategies:

**Mechanical enforcement (process-as-code)**: The SQLite state database
enforces a linear phase progression. Sprints cannot skip phases. Tickets
cannot be created before the ticketing phase. Only one sprint can execute
at a time (singleton execution lock). Review gates must be explicitly
recorded before phase transitions are allowed. These constraints exist in
code, not in instructions the agent can ignore.

**Behavioral scaffolding (process-as-instructions)**: The `AGENTS.md`
file — injected into every conversation — contains mandatory rules with
specific decision trees: a pre-flight check before writing any code, a
CLASI-first routing rule for tool selection, and a stop-and-report rule
when tools fail. These are the "soft" layer — they depend on agent
compliance, but they're structured as binary decision points rather than
vague guidelines.

**Agent specialization (divide and conquer)**: Nine specialized agents
with hard boundaries on what each can and cannot do. The project manager
delegates but never writes code. The python expert writes code but never
creates sprints. This reduces the cognitive load at each decision point
and limits the blast radius of a single agent's process violation.

### 2.4 Philosophical Position

CLASI takes the position that for AI agents, **process documentation is
insufficient — the process must be the code**. The dual-truth model
reflects this:

- **Filesystem-as-truth**: Markdown artifacts (sprint docs, tickets,
  architecture documents) are the human-readable record. They live in
  `docs/plans/` and are committed to git.
- **Database-as-enforcement**: The SQLite state machine (`.clasi.db`)
  enforces lifecycle rules programmatically. It is `.gitignored` and
  reconstructed from the filesystem state when needed.

When the database is unavailable, the system degrades gracefully — all
enforcement disappears. This is a deliberate tradeoff favoring backward
compatibility over strict correctness, and it is one of the system's known
weaknesses (see Section 12).

---

## 3. System Architecture Overview

### 3.1 Component Diagram

```mermaid
graph TB
    subgraph "User / IDE"
        CC[Claude Code / IDE]
    end

    subgraph "CLASI Package"
        CLI[CLI Layer<br/>clasi init / clasi mcp / clasi todo-split]
        MCP[MCP Server<br/>FastMCP stdio transport]

        subgraph "Tool Layer"
            PT[Process Tools<br/>10 tools — read-only]
            AT[Artifact Tools<br/>20 tools — read-write]
        end

        subgraph "Content Assets"
            AG[9 Agent Definitions]
            SK[18 Skill Definitions]
            IN[5 Instructions +<br/>1 Language Instruction]
            TM[6 Templates]
        end

        subgraph "Data Layer"
            FM[Frontmatter Utils]
            SDB[State Database<br/>SQLite — phases, gates, locks]
            VER[Versioning<br/>CalVer tag_version]
        end
    end

    subgraph "Project Filesystem"
        DP["docs/plans/<br/>sprints/ tickets/ todo/<br/>architecture/ reflections/"]
        DB[".clasi.db<br/>(gitignored)"]
    end

    CC -->|stdio| MCP
    CC -->|shell| CLI
    MCP --> PT
    MCP --> AT
    PT --> AG
    PT --> SK
    PT --> IN
    AT --> FM
    AT --> SDB
    AT --> TM
    AT --> VER
    SDB --> DB
    AT --> DP
    FM --> DP
```

### 3.2 Two Tool Categories

| Category | Module | Count | Access | Purpose |
|----------|--------|-------|--------|---------|
| Process Tools | `process_tools.py` | 10 | Read-only | Serve agent definitions, skill workflows, instructions, and curated process guides |
| Artifact Tools | `artifact_tools.py` | 20 | Read-write | Create/modify/move sprints, tickets, TODOs; enforce lifecycle via state DB |

### 3.3 Content Asset Inventory

| Asset Type | Count | Location | Format |
|------------|-------|----------|--------|
| Agent definitions | 9 | `agents/*.md` | YAML frontmatter + markdown |
| Skill definitions | 18 | `skills/*.md` | YAML frontmatter + markdown |
| Instructions | 5 | `instructions/*.md` | YAML frontmatter + markdown |
| Language instructions | 1 | `instructions/languages/*.md` | YAML frontmatter + markdown |
| Templates | 6 | `templates/*.md` | Markdown with `{placeholders}` |

---

## 4. The Agent Model

### 4.1 Agent Delegation Hierarchy

```mermaid
graph TD
    PM[project-manager<br/>Orchestrator — delegates everything]
    PM --> ARC[architect<br/>Architecture docs + technical plans]
    PM --> AR[architecture-reviewer<br/>Reviews architecture quality]
    PM --> RA[requirements-analyst<br/>Elicits requirements + use cases]
    PM --> TL[technical-lead<br/>Creates tickets + ticket plans]
    PM --> PE[python-expert<br/>Writes code + tests]
    PM --> CR[code-reviewer<br/>Reviews code quality]
    PM --> DE[documentation-expert<br/>Generates documentation]
    PM --> ProdM[product-manager<br/>Stakeholder interviews]
```

### 4.2 Agent Definitions

#### project-manager
- **Role**: Top-level orchestrator. Never writes code or tests directly.
  Delegates all work to specialist agents.
- **Boundaries**: Does NOT write code, tests, or architecture. Does NOT
  perform code review. Only creates plans, coordinates, and delegates.
- **Key behavior**: Follows an explicit decision tree: check for active
  sprint → check ticket status → delegate to appropriate agent. Uses
  `AskUserQuestion` for every stakeholder-facing decision.
- **Tools**: All tools (full access for coordination)

#### architect
- **Role**: Maintains versioned architecture documents and produces sprint
  technical plans.
- **Two modes**: (1) Initial architecture — takes brief + use cases and
  produces the first architecture doc. (2) Sprint architecture — takes
  sprint goals and produces a technical plan describing changes.
- **Boundaries**: Does NOT write code, tests, or tickets. Does NOT make
  product decisions.
- **Tools**: Read, Write, Edit, Bash, Grep, Glob

#### architecture-reviewer
- **Role**: Reviews architecture quality against the architectural quality
  instruction. Produces structured verdicts (APPROVED / REVISE).
- **Review criteria**: Cohesion, coupling, module boundaries, abstraction
  levels, dependency direction, design rationale, versioning compliance,
  diagram quality.
- **Boundaries**: Does NOT write architecture. Does NOT write code. Only
  reviews.
- **Tools**: Read, Bash, Grep, Glob

#### requirements-analyst
- **Role**: Elicits requirements through stakeholder interviews. Produces
  use cases, the project brief, or the project overview.
- **Boundaries**: Does NOT design architecture. Does NOT write code.
- **Tools**: Read, Write, Edit, Bash, Grep, Glob

#### technical-lead
- **Role**: Creates tickets from sprint technical plans. Produces ticket
  plans (implementation approach, file lists, test plans).
- **Key behavior**: Decomposes technical plans into ordered tickets with
  dependency chains. Follows the rule: foundation before features,
  critical path first, smallest ticket as tiebreaker.
- **Boundaries**: Does NOT write production code during ticket creation.
  Does NOT create sprints or architecture.
- **Tools**: Read, Write, Edit, Bash, Grep, Glob

#### python-expert
- **Role**: Writes Python code and tests. The primary implementation
  agent.
- **Key behavior**: Follows coding-standards, testing, and python language
  instructions. Runs tests after every change.
- **Boundaries**: Does NOT create sprints, tickets, or architecture. Does
  NOT review code (that's the code-reviewer).
- **Tools**: Read, Write, Edit, Bash, Grep, Glob

#### code-reviewer
- **Role**: Reviews code changes for correctness, style, test coverage,
  and adherence to coding standards.
- **Output**: Structured review with APPROVE / REQUEST CHANGES verdict.
- **Boundaries**: Does NOT write code. Does NOT fix issues (only
  identifies them).
- **Tools**: Read, Bash, Grep, Glob

#### documentation-expert
- **Role**: Generates and updates documentation (README, API docs, guides).
- **Boundaries**: Does NOT write application code or tests.
- **Tools**: Read, Write, Edit, Bash, Grep, Glob

#### product-manager
- **Role**: Conducts stakeholder interviews during project initiation.
  Translates business goals into structured requirements.
- **Key behavior**: Asks open-ended questions, synthesizes answers into
  the overview document. Uses narrative mode (the stakeholder describes
  the project in free-form text) or interview mode (structured Q&A).
- **Boundaries**: Does NOT write technical specifications, architecture,
  or code.
- **Tools**: Read, Write, Edit, Bash, Grep, Glob

### 4.3 Agent-to-Instruction Binding

| Agent | Instructions Used |
|-------|-------------------|
| architect | software-engineering, architectural-quality |
| architecture-reviewer | architectural-quality |
| code-reviewer | coding-standards, python, testing |
| python-expert | software-engineering, coding-standards, python, testing |
| technical-lead | software-engineering, coding-standards |
| project-manager | software-engineering, git-workflow |
| requirements-analyst | software-engineering |
| documentation-expert | software-engineering |
| product-manager | software-engineering |

---

## 5. The Sprint Lifecycle

This is the core process. Every code change flows through a sprint (unless
explicitly designated "out of process" by the stakeholder).

### 5.1 Phase State Machine

```mermaid
stateDiagram-v2
    [*] --> PlanningDocs: create_sprint()
    PlanningDocs --> ArchReview: advance_sprint_phase()
    ArchReview --> StakeholderReview: advance_sprint_phase()
    StakeholderReview --> Ticketing: advance_sprint_phase()
    Ticketing --> Executing: advance_sprint_phase()
    Executing --> Closing: advance_sprint_phase()
    Closing --> Done: close_sprint()

    state PlanningDocs {
        [*] --> WriteSprint: sprint.md
        WriteSprint --> WriteUseCases: usecases.md
        WriteUseCases --> WriteTechPlan: technical-plan.md
    }

    state ArchReview {
        [*] --> DelegateArchReviewer
        DelegateArchReviewer --> RecordGate: record_gate_result()
    }

    state StakeholderReview {
        [*] --> PresentToStakeholder
        PresentToStakeholder --> RecordApproval: record_gate_result()
    }

    state Ticketing {
        [*] --> CreateTickets: create_ticket()
        CreateTickets --> WriteTicketPlans
    }

    state Executing {
        [*] --> AcquireLock: acquire_execution_lock()
        AcquireLock --> ExecuteTickets
        ExecuteTickets --> AllDone
    }
```

### 5.2 Phase Details

#### Phase 1: planning-docs

| | |
|---|---|
| **Purpose** | Author the three planning documents that define what the sprint will accomplish |
| **Entry conditions** | `create_sprint(title)` called. Sprint directory exists. State DB row created with `phase = "planning-docs"`. Git branch `sprint/NNN-slug` created. |
| **Activities** | Fill in `sprint.md` (goals, problem, solution, scope, test strategy). Fill in `usecases.md` (sprint use cases with parent UC references). Fill in `technical-plan.md` (architecture version from/to, component designs, open questions). |
| **Exit conditions** | All three documents contain real content (not template placeholders). `advance_sprint_phase()` called successfully. |
| **Enforcement** | `review_sprint_pre_execution` checks for template placeholders (≥3 placeholder markers = still a template). Phase advance is unconditional — no gate required. |
| **Active agents** | architect (technical plan), requirements-analyst (use cases), project-manager (coordination) |
| **Active skills** | `plan-sprint`, `create-technical-plan`, `elicit-requirements` |

#### Phase 2: architecture-review

| | |
|---|---|
| **Purpose** | Independent review of the technical plan's architectural quality |
| **Entry conditions** | Phase advanced from `planning-docs`. |
| **Activities** | Delegate to architecture-reviewer agent. Reviewer evaluates against `architectural-quality` instruction (cohesion, coupling, boundaries, abstraction, dependency direction, versioning). Produces APPROVED or REVISE verdict. |
| **Exit conditions** | `record_gate_result(sprint_id, "architecture_review", "passed")` called. |
| **Enforcement** | `advance_sprint_phase()` checks that `architecture_review` gate has result `"passed"`. Transition blocked if gate is missing or `"failed"`. |
| **Active agents** | architecture-reviewer |
| **Active skills** | None (direct agent delegation) |

#### Phase 3: stakeholder-review

| | |
|---|---|
| **Purpose** | Human stakeholder reviews and approves the sprint plan |
| **Entry conditions** | Architecture review gate passed. |
| **Activities** | Present sprint plan to stakeholder via `AskUserQuestion`. Stakeholder provides feedback or approval. |
| **Exit conditions** | `record_gate_result(sprint_id, "stakeholder_approval", "passed")` called. |
| **Enforcement** | `advance_sprint_phase()` checks that `stakeholder_approval` gate has result `"passed"`. Transition blocked if gate is missing or `"failed"`. |
| **Active agents** | project-manager |
| **Active skills** | None (human interaction via `AskUserQuestion`) |

#### Phase 4: ticketing

| | |
|---|---|
| **Purpose** | Decompose the technical plan into executable tickets |
| **Entry conditions** | Stakeholder approval gate passed. |
| **Activities** | Create tickets via `create_ticket(sprint_id, title)`. Write ticket plans (approach, files affected, test plan). Order tickets by dependency. |
| **Exit conditions** | All planned tickets exist with content. `advance_sprint_phase()` called. |
| **Enforcement** | `create_ticket()` checks that sprint is in `ticketing` phase or later (blocks ticket creation during earlier phases). Phase advance requires execution lock. |
| **Active agents** | technical-lead |
| **Active skills** | `create-tickets` |

#### Phase 5: executing

| | |
|---|---|
| **Purpose** | Implement the tickets — write code, tests, documentation |
| **Entry conditions** | Execution lock acquired via `acquire_execution_lock(sprint_id)`. Only one sprint can hold the lock at a time across the entire repository. |
| **Activities** | For each ticket: write code, run tests, check off acceptance criteria, set status to `done`, move to `tickets/done/`, commit. |
| **Exit conditions** | All tickets are `status: done` and located in `tickets/done/`. |
| **Enforcement** | Execution lock prevents concurrent sprint execution (singleton table pattern in SQLite). `review_sprint_pre_execution` validates pre-conditions. `review_sprint_pre_close` validates post-conditions. |
| **Active agents** | python-expert (code), code-reviewer (review), technical-lead (coordination) |
| **Active skills** | `execute-ticket` |

#### Phase 6: closing

| | |
|---|---|
| **Purpose** | Merge, archive, tag, and clean up |
| **Entry conditions** | All tickets done. Phase advanced from `executing`. |
| **Activities** | Merge sprint branch into main. Archive sprint directory to `sprints/done/`. Create version tag. Release execution lock. Delete sprint branch. |
| **Exit conditions** | Sprint directory in `sprints/done/`. On main/master branch. Execution lock released. Git tag created. Sprint branch deleted. |
| **Enforcement** | `review_sprint_post_close` validates the final state. `close_sprint()` handles archiving + state DB update. |
| **Active agents** | project-manager |
| **Active skills** | `close-sprint` |

#### Phase 7: done

| | |
|---|---|
| **Purpose** | Terminal state — sprint is complete |
| **Entry conditions** | `close_sprint()` completed successfully. |
| **Enforcement** | `advance_sprint_phase()` raises `ValueError` if called on a `done` sprint. |

### 5.3 Review Gates Detail

The state machine enforces two named gates:

```mermaid
graph LR
    A[architecture-review phase] -->|record_gate_result<br/>gate=architecture_review<br/>result=passed| B[stakeholder-review phase]
    C[stakeholder-review phase] -->|record_gate_result<br/>gate=stakeholder_approval<br/>result=passed| D[ticketing phase]

    style A fill:#f9f,stroke:#333
    style C fill:#f9f,stroke:#333
```

- Gates are stored in the `sprint_gates` table with `UNIQUE(sprint_id, gate_name)`.
- Recording uses upsert semantics: a `failed` gate can be overwritten
  with `passed` after issues are addressed.
- Valid gate names: `architecture_review`, `stakeholder_approval`.
- Valid results: `passed`, `failed`.
- Gates are checked by `advance_sprint_phase()` before allowing the
  transition. If the gate is missing or failed, the transition is blocked
  with a descriptive error.

### 5.4 Execution Lock Detail

```mermaid
graph TD
    A[Sprint requests lock] --> B{Lock table<br/>has a row?}
    B -->|No| C[Insert row<br/>sprint_id + timestamp]
    C --> D[Lock acquired<br/>reentrant = false]
    B -->|Yes| E{Same sprint?}
    E -->|Yes| F[Lock re-acquired<br/>reentrant = true]
    E -->|No| G[BLOCKED<br/>ValueError: sprint X<br/>holds the lock]
```

- The `execution_locks` table has `CHECK (id = 1)` — a singleton table
  pattern. Only one row can ever exist.
- This means only one sprint can execute at a time across the entire
  repository, preventing concurrent development conflicts.
- The lock is re-entrant: if the same sprint requests it again (e.g.,
  after a context switch), it succeeds.
- `release_execution_lock()` verifies the requesting sprint actually
  holds the lock before releasing.

---

## 6. The Ticket Lifecycle

### 6.1 Ticket State Flow

```mermaid
stateDiagram-v2
    [*] --> Todo: create_ticket()
    Todo --> InProgress: update_ticket_status(status="in-progress")
    InProgress --> Done_WrongPlace: update_ticket_status(status="done")
    Done_WrongPlace --> Done_Correct: move_ticket_to_done()
    Done_Correct --> [*]

    Done_Correct --> Todo: reopen_ticket()

    state "todo (in tickets/)" as Todo
    state "in-progress (in tickets/)" as InProgress
    state "done (in tickets/) ⚠️" as Done_WrongPlace
    state "done (in tickets/done/) ✓" as Done_Correct
```

### 6.2 Definition of Done (6 Mandatory Steps)

A ticket is NOT done until ALL of the following are complete:

1. ✅ Run the full test suite — all tests pass
2. ✅ Set ticket `status` to `done` in YAML frontmatter
3. ✅ Check off all acceptance criteria (`- [x]`)
4. ✅ Move ticket file to `tickets/done/` via `move_ticket_to_done`
5. ✅ Move ticket plan file to `tickets/done/` if it exists
6. ✅ Commit the moves: `chore: move ticket #NNN to done`

**This is the most frequently violated rule in the process.** Agents
consistently report tickets as "done" after writing code but before
completing steps 2–6. Sprint 015 introduced the three review tools
specifically to catch this failure.

### 6.3 Ticket Plan Structure

Each ticket optionally has a companion `*-plan.md` file containing:

- **Approach**: Implementation strategy
- **Files to modify**: List of files that will be changed
- **New files**: List of files that will be created
- **Testing plan**: What tests to write, how to verify
- **Documentation updates**: What docs need to change

### 6.4 Ticket Dependency Ordering

The technical-lead creates tickets following this priority:

1. Foundation before features (infrastructure tickets first)
2. Critical path first (blocking tickets before parallel work)
3. Smallest ticket as tiebreaker (reduces risk of scope explosion)

Dependencies are declared in ticket frontmatter: `depends-on: ["001", "003"]`

---

## 7. Project Initiation Flow

### 7.1 Initiation Flowchart

```mermaid
graph TD
    A[Stakeholder arrives<br/>with project idea] --> B{overview.md<br/>exists?}
    B -->|Yes| C[Skip to sprint<br/>planning]
    B -->|No| D{Initiation mode?}
    D -->|Narrative| E[Stakeholder writes<br/>free-form description]
    D -->|Interview| F[product-manager asks<br/>structured questions]
    E --> G[product-manager<br/>synthesizes overview.md]
    F --> G
    G --> H{Stakeholder<br/>approves?}
    H -->|No| I[Revise overview]
    I --> H
    H -->|Yes| C
    C --> J[plan-sprint skill]
```

### 7.2 Entry and Exit Conditions

| | |
|---|---|
| **Entry conditions** | No `docs/plans/overview.md` exists (or legacy: no `brief.md`). Stakeholder has a project idea. |
| **Activities** | Stakeholder interview (narrative or structured). Synthesis into overview document. Stakeholder review and approval. |
| **Exit conditions** | Approved `overview.md` with: problem statement, target users, key constraints, high-level requirements, technology stack, sprint roadmap, out-of-scope items. |
| **Artifacts produced** | `docs/plans/overview.md` |

### 7.3 Legacy Path

Older projects may use the three-document model:
- `docs/plans/brief.md` — problem + solution + constraints
- `docs/plans/usecases.md` — top-level use cases (UC-NNN)
- `docs/plans/technical-plan.md` — initial architecture

The `next` skill's state detection checks for `brief.md` first, then
`overview.md`. Both paths are valid.

---

## 8. The Artifact Model

### 8.1 Directory Layout

```
docs/plans/
├── overview.md                    # Project overview (new path)
├── brief.md                       # Project brief (legacy path)
├── usecases.md                    # Top-level use cases (legacy path)
├── technical-plan.md              # Top-level tech plan (legacy)
├── .clasi.db                      # SQLite state DB (gitignored)
├── architecture/
│   └── architecture-NNN.md        # Versioned architecture docs
├── reflections/
│   └── done/
│       └── YYYY-MM-DD-slug.md     # Completed reflections
├── todo/
│   ├── some-idea.md               # Active TODOs
│   └── done/
│       └── consumed-todo.md       # Consumed TODOs (with traceability)
└── sprints/
    ├── NNN-slug/                   # Active sprint
    │   ├── sprint.md               # Sprint definition
    │   ├── usecases.md             # Sprint use cases
    │   ├── technical-plan.md       # Sprint technical plan
    │   └── tickets/
    │       ├── NNN-slug.md         # Active tickets
    │       ├── NNN-slug-plan.md    # Ticket plans
    │       └── done/
    │           └── NNN-slug.md     # Completed tickets
    └── done/
        └── NNN-slug/               # Archived sprints
```

### 8.2 Artifact Types and Lifecycle

| Artifact | Created By | Lives In | Archived To | Frontmatter Fields |
|----------|-----------|----------|-------------|-------------------|
| Overview | `create_overview()` | `docs/plans/` | N/A | status |
| Architecture | architect agent | `architecture/` | N/A (versioned in place) | version, status, sprint, description |
| Sprint | `create_sprint()` | `sprints/NNN-slug/` | `sprints/done/NNN-slug/` | id, title, status, branch, use-cases |
| Technical plan | architect agent | `sprints/NNN-slug/` | (moves with sprint) | status, from-architecture-version, to-architecture-version |
| Use cases | requirements-analyst | `sprints/NNN-slug/` | (moves with sprint) | status, sprint |
| Ticket | `create_ticket()` | `tickets/` | `tickets/done/` | id, title, status, use-cases, depends-on |
| Ticket plan | technical-lead | `tickets/` | `tickets/done/` | (no frontmatter) |
| TODO | stakeholder / agent | `todo/` | `todo/done/` | status, sprint, tickets |
| Reflection | `self-reflect` skill | `reflections/` | `reflections/done/` | category, sprint, date |

### 8.3 Architecture Versioning

Architecture documents follow a sprint-aligned versioning scheme:

- Each architecture document is named `architecture-NNN.md` where NNN
  corresponds to the sprint that produced it.
- The sprint technical plan declares `from-architecture-version` (the
  starting baseline) and `to-architecture-version` (the target).
- After a sprint completes, the new architecture document becomes the
  `status: current` baseline; the previous version is updated to
  `status: superseded`.
- This creates a complete architectural history that can be diffed
  across sprints.

### 8.4 Release Versioning

Releases use CalVer: `<major>.<YYYYMMDD>.<build>`

- `major` defaults to 0 and is manually incremented for breaking changes.
- `YYYYMMDD` is the current date.
- `build` auto-increments within the same date, resets to 1 on a new date.
- The `tag_version()` tool scans existing git tags to determine the next
  build number.
- Version is written to `pyproject.toml` (or `package.json` for Node
  projects) and a git tag is created.

---

## 9. The Skill Model

Skills are structured workflows — step-by-step procedures that agents
follow. They are the primary mechanism for ensuring consistent execution.

### 9.1 Skill Inventory

| Skill | Trigger | Primary Agent | Purpose |
|-------|---------|---------------|---------|
| `plan-sprint` | Start of sprint planning | project-manager | Full sprint creation workflow: mine TODOs, create sprint, write planning docs, gate reviews, create tickets |
| `execute-ticket` | During sprint execution | technical-lead, python-expert | Ticket implementation workflow: read plan, implement, test, review, complete |
| `close-sprint` | After all tickets done | project-manager | Sprint closure workflow: validate, merge, archive, tag, clean up |
| `create-tickets` | During ticketing phase | technical-lead | Ticket creation workflow: decompose tech plan, order dependencies, create ticket files |
| `create-technical-plan` | During planning phase | architect | Technical plan creation: analyze goals, design changes, document component designs |
| `elicit-requirements` | During project initiation | requirements-analyst | Requirements elicitation: interview or synthesize use cases, brief, overview |
| `project-initiation` | New project start | product-manager | Stakeholder interview workflow: narrative or structured mode |
| `project-status` | On demand | project-manager | Status report: sprint state, ticket progress, blockers, next steps |
| `next` | When agent is unsure | project-manager | State detection: examine project, determine correct next action |
| `se` | `/se` command | (dispatcher) | Thin router to other skills: `/se plan`, `/se execute`, `/se close`, etc. |
| `todo` | Capture an idea | (any) | Create a TODO file in `docs/plans/todo/` |
| `ghtodo` | Capture idea as GitHub issue | (any) | Create a GitHub issue + local TODO file |
| `report` | Sprint summary needed | project-manager | Generate a sprint summary report |
| `oop` | `/oop` command | (any) | Out-of-process escape hatch: skip the SE process for a quick fix |
| `self-reflect` | Stakeholder correction | (any) | Structured self-reflection after a process failure |
| `auto-approve` | Batch operations | (any) | Toggle auto-approval for tool permissions |
| `generate-documentation` | Documentation needed | documentation-expert | Generate README, API docs, or guides |
| `python-code-review` | Code review needed | code-reviewer | Structured Python code review |

### 9.2 Skill Categories

```mermaid
graph TD
    subgraph "Lifecycle Skills"
        PS[plan-sprint]
        ET[execute-ticket]
        CS[close-sprint]
        CT[create-tickets]
        CTP[create-technical-plan]
        ER[elicit-requirements]
        PI[project-initiation]
    end

    subgraph "Navigation Skills"
        ST[project-status]
        NX[next]
        SE[se — dispatcher]
    end

    subgraph "Capture Skills"
        TD[todo]
        GH[ghtodo]
        RP[report]
    end

    subgraph "Meta Skills"
        AA[auto-approve]
        SR[self-reflect]
        OOP[oop]
    end

    subgraph "Quality Skills"
        GD[generate-documentation]
        PCR[python-code-review]
    end

    SE -.->|routes to| PS
    SE -.->|routes to| ET
    SE -.->|routes to| CS
    SE -.->|routes to| ST
```

---

## 10. The Instruction Model

Instructions are reference documents that agents consult while working.
They define standards, conventions, and rules.

### 10.1 Instruction Inventory

#### software-engineering (Master Instruction)
The most comprehensive instruction. Defines:
- All 9 agents and their boundaries
- All skills and their triggers
- All artifact types with required content and lifecycle
- The complete sprint workflow with phase descriptions
- The directory layout
- Rules for AI assistants (11 numbered rules covering process compliance,
  tool usage, stakeholder interaction, and error handling)

#### architectural-quality
Quality guide for architecture documents:
- Versioning rules (sprint-aligned, from/to versions)
- Core principles: high cohesion, loose coupling, clear boundaries,
  appropriate abstraction, dependency direction
- Required document structure: overview, component designs, data model,
  design rationale
- Anti-patterns to flag: God components, circular dependencies,
  abstraction inversion, shotgun surgery, deep nesting

#### coding-standards
Coding conventions:
- Error handling (use exceptions, don't swallow errors, always log)
- Dependency management (minimal dependencies, pin versions)
- Naming (descriptive names, avoid abbreviations, consistent casing)

#### git-workflow
Git conventions:
- Core rule: one branch per sprint (`sprint/NNN-slug`)
- Commit message format (type: description, body, footer)
- Branch strategy: main/master is always deployable, sprint branches
  are short-lived
- Sprint branch closing: merge into main, delete branch
- Safety rules: never force-push to main, never rebase shared branches

#### testing
Testing standards:
- Core rule: every ticket must include tests
- Test placement: `tests/` directory mirrors `src/` structure
- Test types: unit (isolated), integration (component interaction),
  end-to-end (full system)
- Design for testability: dependency injection, pure functions,
  small interfaces
- Verification strategies: boundary testing, error path testing,
  regression testing

#### python (Language Instruction)
Python-specific conventions:
- Virtual environments via `uv`
- `pyproject.toml` configuration
- Naming conventions (snake_case for functions/variables, PascalCase
  for classes)
- Import ordering (stdlib, third-party, local)
- Logging (use `logging` module, structured logging)
- Type hints (use for public APIs, avoid for trivial internals)
- pytest patterns and fixtures

---

## 11. Enforcement Mechanisms — Summary

| Mechanism | What It Prevents | Implementation | Layer |
|-----------|-----------------|----------------|-------|
| Phase transitions | Skipping lifecycle stages | SQLite state machine, `advance_sprint_phase()` | Mechanical |
| Architecture review gate | Proceeding without arch review | `record_gate_result()` + phase check | Mechanical |
| Stakeholder approval gate | Proceeding without human approval | `record_gate_result()` + phase check | Mechanical |
| Execution lock | Concurrent sprint execution | Singleton table `CHECK (id = 1)` | Mechanical |
| Ticket creation gate | Creating tickets too early | Phase check in `create_ticket()` | Mechanical |
| Pre-execution review | Starting execution with incomplete plans | `review_sprint_pre_execution()` | Advisory |
| Pre-close review | Closing sprint with incomplete tickets | `review_sprint_pre_close()` | Advisory |
| Post-close review | Incomplete sprint closure | `review_sprint_post_close()` | Advisory |
| Pre-flight check | Writing code without a sprint | AGENTS.md decision tree | Behavioral |
| CLASI-first routing | Using wrong tools | AGENTS.md routing rule | Behavioral |
| Stop-and-report | Silent workarounds on failure | AGENTS.md stop rule | Behavioral |
| Definition of Done | Premature ticket completion | AGENTS.md 6-point checklist | Behavioral |
| Self-reflection | Repeating process failures | `self-reflect` skill | Behavioral |
| Agent boundaries | Overstepping role limits | Agent definition `What You Do Not Do` sections | Behavioral |

Note the distinction between **mechanical** enforcement (code prevents
the violation), **advisory** enforcement (code detects and reports the
violation), and **behavioral** enforcement (instructions tell the agent
not to do it, but nothing stops it).

---

## 12. Inconsistencies and Gaps

This section documents concrete inconsistencies, enforcement gaps, and
design tensions discovered during this analysis. These are presented as
findings for comparative research, not as bugs to fix.

### 12.1 AGENTS.md Out of Sync with Template

**Finding**: The project's own `AGENTS.md` does not contain all the
sections that were added to `init/agents-section.md` in sprint 015.
Specifically, the Pre-Flight Check, CLASI-first routing, and
Stop-and-Report sections exist in the template but not in the project's
own instruction file.

**Impact**: The project that defines the process does not fully enforce it
on itself.

**Status**: Ticket #006 in sprint 015 exists to fix this but remains
`status: todo`.

### 12.2 Unenforced Phase Transitions

**Finding**: The `executing → closing` and `closing → done` transitions
have no programmatic enforcement. `advance_sprint_phase()` allows them
unconditionally. The `close_sprint()` function compensates by
force-advancing through all remaining phases in a loop.

**Impact**: An agent can advance past executing without all tickets being
done. The review tools (`review_sprint_pre_close`) are advisory only —
they report issues but don't block the transition.

**Recommendation**: Consider making `review_sprint_pre_close` a required
gate (like architecture review) rather than an advisory check.

### 12.3 Graceful Degradation Undermines Enforcement

**Finding**: All state DB operations are wrapped in `try/except: pass`.
If the database is missing, corrupt, or inaccessible, all lifecycle
enforcement silently disappears. Sprints can be created, tickets can be
added, and phases can be skipped without any error.

**Impact**: The mechanical enforcement layer — the system's primary
defense against agent process violations — can be entirely absent without
anyone noticing.

**Design tension**: This is deliberate. It enables backward compatibility
with projects that don't have a state DB yet, and prevents the process
from blocking work if the DB is corrupted. But it means the strongest
enforcement guarantees are also the most fragile.

**Recommendation**: Consider at minimum logging a warning when the DB is
unavailable, so the condition is visible even if not blocking.

### 12.4 Live Ticket Completion Violation

**Finding**: In the current active sprint (015), ticket #005 has
`status: done` and all acceptance criteria checked, but the file is still
in `tickets/` rather than `tickets/done/`. This is exactly the failure
mode the Definition of Done rules are designed to prevent.

**Impact**: Demonstrates that the behavioral enforcement (AGENTS.md rules)
is insufficient on its own. The review tools would catch this, but they
must be actively invoked.

### 12.5 No Mechanical Enforcement of Definition of Done

**Finding**: The 6-point Definition of Done checklist is entirely
behavioral. No tool checks whether tests pass, acceptance criteria are
checked, or documentation is updated before `move_ticket_to_done()`
succeeds. The tool will happily move a ticket with `status: todo` and
unchecked criteria.

**Recommendation**: Consider adding pre-conditions to
`move_ticket_to_done()` — at minimum verifying `status: done` in
frontmatter and that acceptance criteria checkboxes are checked.

### 12.6 Architecture Version Gaps

**Finding**: Sprint 015's technical plan declares
`to-architecture-version: "015"` but no `architecture-015.md` has been
created. There is no enforcement that architectural sprints actually
produce their declared version document.

**Recommendation**: The `review_sprint_pre_close` tool could check whether
the sprint's technical plan declares a `to-architecture-version` and
verify the corresponding architecture document exists.

### 12.7 Cross-Project Reflection Contamination

**Finding**: Some reflections reference sprint "025" which does not exist
in this project's sprint history (which goes up to 015). This suggests
reflections were generated from experiences in other projects using CLASI
and were copied in.

**Impact**: Minor — the reflections are still valid as evidence of agent
failure patterns. But it reduces traceability.

### 12.8 Two Paths to Project Initiation

**Finding**: Two skills produce overlapping artifacts:
- `project-initiation` → `overview.md` (single document)
- `elicit-requirements` → `brief.md` + `usecases.md` (two documents)

The `next` skill checks for `brief.md` first, then `overview.md`. The
`plan-sprint` skill references "the project brief or overview." The
relationship between these paths is ambiguous.

**Recommendation**: Clarify whether these are alternatives (pick one) or
sequential stages. If alternatives, document when to use which. If the
overview path is the preferred future direction, deprecate the
brief+usecases path explicitly.

### 12.9 Review Tools Are Advisory, Not Blocking

**Finding**: The three sprint review tools (`review_sprint_pre_execution`,
`review_sprint_pre_close`, `review_sprint_post_close`) return `{passed,
issues}` but do not actually block any operation. An agent can call
`review_sprint_pre_close()`, see that it failed, and call
`close_sprint()` anyway.

**Design tension**: Making them blocking would require integrating them
into the state machine (as additional gates). This adds process overhead.
Keeping them advisory relies on the agent actually checking the result —
which is exactly the kind of behavioral compliance agents routinely fail
at.

### 12.10 Gate Upsert Allows Silent Failure Overwrite

**Finding**: `record_gate_result()` uses upsert semantics. If a gate was
previously recorded as `"failed"`, recording `"passed"` silently
overwrites it. There is no audit trail of failed-then-passed gates.

**Impact**: An agent could record a gate as failed, then immediately
record it as passed without addressing the issues. The previous failure
is lost.

**Recommendation**: Consider keeping a history of gate results rather
than overwriting, or requiring explicit acknowledgment when overwriting a
failed gate.

---

## 13. Comparison to Established Processes and Recommendations

This section maps CLASI's characteristics to established software
engineering processes to provide a framework for deeper comparative
research.

### 13.1 Process Comparison Matrix

| Characteristic | CLASI | Scrum | RUP | DSDM | Spiral | SAFe |
|---------------|-------|-------|-----|------|--------|------|
| Iteration model | Sprint-based | Sprint-based | Phase-based | Timebox-based | Risk-driven cycles | Sprint + PI planning |
| Phase gates | 2 mandatory gates | None (ceremonies instead) | Milestone reviews | MoSCoW prioritization | Risk review | PI planning review |
| Roles | 9 specialized agents | 3 roles (PO, SM, Dev) | 6+ roles | 7+ roles | Variable | Many (RTE, PO, SA, etc.) |
| Mechanical enforcement | SQLite state machine | None (human discipline) | None (tool-supported) | None | None | Tool-supported (Jira/Rally) |
| Documentation weight | Medium (structured markdown) | Low (user stories) | Heavy (formal artifacts) | Medium (prioritized requirements) | Medium (risk analysis) | Heavy (formal SAFe artifacts) |
| Architecture treatment | Versioned, reviewed, gated | Emergent | Formal architecture phase | Architecture baseline | Risk-driven | Intentional architecture |
| Human oversight | 1 gate (stakeholder review) | Daily standup + sprint review | Multiple reviews | Workshops | Risk assessment meetings | Multiple ceremonies |
| Feedback mechanism | Reflections (post-hoc) | Retrospectives | Lessons learned | Retrospectives | Risk reassessment | Inspect & Adapt |

### 13.2 What CLASI Borrows

- **From Scrum**: Sprint-based iteration, backlog management (TODOs),
  definition of done, the concept of a sprint goal.
- **From RUP**: Gated phase transitions, formal architecture treatment,
  role-based work distribution, artifact-driven process.
- **From Spiral Model**: The idea that process enforcement should be
  proportional to risk. The reflection mechanism serves as a lightweight
  risk identification loop.
- **From Stage-Gate**: The explicit gate model where advancement requires
  a recorded verdict.

### 13.3 What's Novel

1. **Process enforcement via state machine for non-human agents**: No
   established process includes mechanical enforcement because human
   teams can be trusted to follow process (or face consequences). AI
   agents have no consequences — only constraints. CLASI's state machine
   is a novel response to this.

2. **Self-reflection as formal artifact**: Reflections are not
   retrospectives (team discussions) — they are structured, individual
   failure analyses produced by the agent that failed. They create a
   corpus that directly informs process hardening.

3. **Dual-truth model**: Filesystem-as-truth for humans,
   database-as-enforcement for agents. No established process needs this
   because humans can read markdown and comply voluntarily.

4. **Agent specialization as process enforcement**: Using role boundaries
   to limit blast radius is similar to RUP's roles but taken further —
   each agent literally cannot access tools outside its scope.

5. **Behavioral scaffolding**: The AGENTS.md decision trees (pre-flight
   check, CLASI-first routing) are a novel form of process embedding
   that targets the specific failure modes of LLM agents.

### 13.4 Recommendations for Further Research

The following areas would benefit from deeper comparative analysis by a
researcher with access to the full literature:

1. **Formal state machine verification**: Is the 7-phase state machine
   complete? Are all paths reachable? Are there deadlock conditions?
   Compare with Petri net analysis used in workflow verification.

2. **Gate model extension**: Should `review_sprint_pre_close` become a
   mandatory gate? What is the optimal number of gates — too few allows
   process bypass, too many creates ceremony overhead. Compare with
   Stage-Gate literature on gate density.

3. **Mechanical vs. behavioral enforcement ratio**: CLASI has 6
   mechanical, 3 advisory, and 5+ behavioral enforcement mechanisms.
   Is this the right balance? Compare with compliance-heavy industries
   (medical device software, avionics) that use formal process
   enforcement.

4. **Graceful degradation vs. strict enforcement**: CLASI's silent
   degradation when the DB is unavailable is analogous to the "process
   tailoring" concept in CMMI. Is there a middle ground? Compare with
   CMMI's maturity levels and their enforcement expectations.

5. **Reflection corpus as process improvement input**: The reflection
   mechanism is similar to DSDM's "learn from experience" principle but
   formalized. Compare with Causal Analysis and Resolution (CAR) in
   CMMI Level 5 and Toyota's A3 problem-solving methodology.

6. **Agent framework comparison**: How does CLASI's agent model compare
   with AutoGPT's agent loops, CrewAI's crew model, LangChain's agent
   chains, and the Claude Agent SDK's native delegation? These frameworks
   solve similar problems (agent coordination) but with different
   assumptions about process compliance.

7. **Scaling**: CLASI enforces a single-sprint execution model (one lock).
   How would it need to change for parallel sprints? Compare with SAFe's
   PI planning for coordinating multiple teams/sprints.

8. **Definition of Done enforcement**: Should the DoD be mechanically
   enforced? Compare with "quality gates" in CI/CD pipelines (automated
   test gates, coverage thresholds, linting) and whether CLASI should
   integrate with these.

9. **Architecture versioning as architectural decision records**: CLASI's
   versioned architecture documents serve a similar purpose to ADRs
   (Architecture Decision Records). Compare with the ADR literature
   (Michael Nygard's original proposal, the adr-tools ecosystem) and
   whether CLASI should adopt ADR conventions.

10. **Cycle time analysis**: With 15 completed sprints, there is enough
    data to analyze sprint duration, ticket throughput, and rework rates.
    Compare with lean software development metrics (lead time, cycle time,
    throughput, WIP limits).

---

## 14. Appendices

### Appendix A: MCP Tool Reference

#### Process Tools (Read-Only)

| Tool | Parameters | Returns |
|------|-----------|---------|
| `get_se_overview()` | — | Curated process overview with agents, skills, instructions, and tool reference |
| `list_agents()` | — | JSON array of `{name, description}` |
| `get_agent_definition(name)` | name: string | Full agent markdown |
| `list_skills()` | — | JSON array of `{name, description}` |
| `get_skill_definition(name)` | name: string | Full skill markdown |
| `list_instructions()` | — | JSON array of `{name, description}` |
| `get_instruction(name)` | name: string | Full instruction markdown |
| `list_language_instructions()` | — | JSON array of `{name, description}` |
| `get_language_instruction(language)` | language: string | Full language instruction markdown |
| `get_activity_guide(activity)` | activity: string | Combined agent + skill + instruction content for an activity |
| `get_use_case_coverage()` | — | Traceability report: which UCs are covered by which sprints |
| `get_version()` | — | `{version: "..."}` |

#### Artifact Tools (Read-Write)

| Tool | Parameters | Returns |
|------|-----------|---------|
| `create_sprint(title)` | title: string | `{id, path, branch, files, phase}` |
| `insert_sprint(after_sprint_id, title)` | after_sprint_id: string, title: string | `{id, path, branch, renumbered: [...]}` |
| `create_ticket(sprint_id, title)` | sprint_id: string, title: string | `{id, path}` |
| `create_overview()` | — | `{path}` |
| `list_sprints(status?)` | status: optional string | JSON array of sprint metadata |
| `list_tickets(sprint_id?, status?)` | sprint_id: optional, status: optional | JSON array of ticket metadata |
| `get_sprint_status(sprint_id)` | sprint_id: string | `{id, title, status, tickets: {todo, in_progress, done}}` |
| `update_ticket_status(path, status)` | path: string, status: string | `{path, old_status, new_status}` |
| `move_ticket_to_done(path)` | path: string | `{old_path, new_path}` |
| `reopen_ticket(path)` | path: string | `{old_path, new_path, old_status, new_status}` |
| `close_sprint(sprint_id)` | sprint_id: string | `{old_path, new_path, version?, tag?}` |
| `get_sprint_phase(sprint_id)` | sprint_id: string | `{id, phase, gates, lock}` |
| `advance_sprint_phase(sprint_id)` | sprint_id: string | `{sprint_id, old_phase, new_phase}` |
| `record_gate_result(sprint_id, gate, result, notes?)` | sprint_id, gate, result: strings; notes: optional | `{sprint_id, gate_name, result, recorded_at}` |
| `acquire_execution_lock(sprint_id)` | sprint_id: string | `{sprint_id, acquired_at, reentrant}` |
| `release_execution_lock(sprint_id)` | sprint_id: string | `{sprint_id, released}` |
| `list_todos()` | — | JSON array of `{filename, title}` |
| `move_todo_to_done(filename, sprint_id?, ticket_ids?)` | filename: string; others optional | `{old_path, new_path}` |
| `create_github_issue(title, body, labels?)` | title, body: strings; labels: optional | `{issue_number, url, title}` |
| `read_artifact_frontmatter(path)` | path: string | JSON dict of frontmatter fields |
| `write_artifact_frontmatter(path, updates)` | path: string, updates: JSON string | `{path, updated_fields}` |
| `tag_version(major?)` | major: optional int (default 0) | `{version, tag}` |
| `review_sprint_pre_execution(sprint_id)` | sprint_id: string | `{passed, issues: [...]}` |
| `review_sprint_pre_close(sprint_id)` | sprint_id: string | `{passed, issues: [...]}` |
| `review_sprint_post_close(sprint_id)` | sprint_id: string | `{passed, issues: [...]}` |

### Appendix B: Agent Definition Index

| Agent | Tools Available | Delegates To | Delegated From |
|-------|----------------|-------------|----------------|
| project-manager | All | All other agents | (top-level) |
| architect | Read, Write, Edit, Bash, Grep, Glob | — | project-manager |
| architecture-reviewer | Read, Bash, Grep, Glob | — | project-manager |
| requirements-analyst | Read, Write, Edit, Bash, Grep, Glob | — | project-manager |
| technical-lead | Read, Write, Edit, Bash, Grep, Glob | python-expert, code-reviewer | project-manager |
| python-expert | Read, Write, Edit, Bash, Grep, Glob | — | technical-lead |
| code-reviewer | Read, Bash, Grep, Glob | — | technical-lead, project-manager |
| documentation-expert | Read, Write, Edit, Bash, Grep, Glob | — | project-manager |
| product-manager | Read, Write, Edit, Bash, Grep, Glob | — | project-manager |

### Appendix C: Sprint History Summary

| Sprint | Title | Tickets | Key Contribution |
|--------|-------|---------|-----------------|
| 000 | Initial Setup | 34 | Retroactive sprint for all pre-sprint-model work |
| 001 | MCP Server | 13 | Frontmatter parser, templates, CLI, init, MCP server, tools |
| 002 | Process Hardening | 10 | State DB, phase transitions, gates, locks, traceability |
| 003 | Document Restructuring | 7 | TODOs, overview template, Mermaid preference, language instructions |
| 004 | MCP Tools and Process Refinements | 7 | Done-path resolution, init fix, frontmatter tools, versioning |
| 005 | Process Refinements and Project Initiation | 6 | Rename, deprecations, product manager agent, TODO frontmatter |
| 006 | Commit After Artifact Moves | 1 | Explicit commit steps after file moves |
| 007 | Package Content and Init Hardening | 3 | Move content into package, MCP permissions, smoke test |
| 008 | Ticket Testing and Interactive Breakpoints | 5 | Testing templates, breakpoints, version tag push |
| 009 | Move Breakpoints Into Skills | 4 | Thin skill dispatcher, skill breakpoints, explicit AskUserQuestion |
| 010 | Process Hygiene and Tooling | 4 | Scold detection, auto-approve, version detection, VS Code |
| 011 | Todo Backlog Cleanup | 3 | CLASI default, GitHub API, VS Code Copilot |
| 012 | Multi-Platform and Cleanup | 5 | AGENTS.md generation, Copilot removal, Codex symlink, gitignore |
| 013 | Audit Test Suite and Add Coverage | 6 | pytest-cov, test rewrites, 85% coverage threshold |
| 014 | Re-architect Init and File Ownership | 6 | Architectural quality guide, versioned architecture baseline |
| 015 | Agent Process Compliance | 6 | Behavioral rules, sprint review tools, /oop skill, narrative mode |

### Appendix D: Activity Guide Mapping

The `get_activity_guide()` tool combines agents, skills, and instructions
for each activity:

| Activity | Agents | Skills | Instructions |
|----------|--------|--------|-------------|
| requirements | requirements-analyst | elicit-requirements | software-engineering |
| architecture | architect | create-technical-plan | software-engineering |
| ticketing | technical-lead | create-tickets | software-engineering |
| implementation | python-expert, technical-lead | execute-ticket | software-engineering, coding-standards, python, testing, git-workflow |
| testing | python-expert | execute-ticket | testing, coding-standards, python |
| code-review | code-reviewer | execute-ticket | coding-standards, python, testing |
| sprint-planning | project-manager, architecture-reviewer | plan-sprint | software-engineering, git-workflow |
| sprint-closing | project-manager | close-sprint | software-engineering, git-workflow |

### Appendix E: State Database Schema

```sql
-- Sprint lifecycle tracking
CREATE TABLE IF NOT EXISTS sprints (
    id TEXT PRIMARY KEY,
    slug TEXT NOT NULL,
    phase TEXT NOT NULL DEFAULT 'planning-docs',
    branch TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Review gate results
CREATE TABLE IF NOT EXISTS sprint_gates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sprint_id TEXT NOT NULL REFERENCES sprints(id),
    gate_name TEXT NOT NULL,
    result TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    notes TEXT,
    UNIQUE(sprint_id, gate_name)
);

-- Singleton execution lock
CREATE TABLE IF NOT EXISTS execution_locks (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    sprint_id TEXT NOT NULL REFERENCES sprints(id),
    acquired_at TEXT NOT NULL
);
```

**Valid phases** (in order):
`planning-docs` → `architecture-review` → `stakeholder-review` → `ticketing` → `executing` → `closing` → `done`

**Valid gate names**: `architecture_review`, `stakeholder_approval`

**Valid gate results**: `passed`, `failed`

**Valid ticket statuses**: `todo`, `in-progress`, `done`

**Connection settings**: WAL mode enabled, foreign keys enforced.
