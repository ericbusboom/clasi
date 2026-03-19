---
version: "001"
status: draft
sprint: "001"
description: Architecture update for sprint 001 — path-scoped rules and directory-scoped subagent dispatch
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Architecture 001: Process Compliance via Rules and Scoped Subagents

This document extends the CLASI architecture with two new enforcement
layers: path-scoped rules that inject process reminders at the point
of file access, and directory-scoped subagent dispatch that restricts
what each subagent can modify.

## The Compliance Problem

CLASI has three existing enforcement mechanisms:

1. **Instructional** — CLAUDE.md, AGENTS.md, skill definitions telling
   agents what to do. Loads at session start, fades from context.
2. **Mechanical (state machine)** — SQLite phase transitions, review
   gates, execution locks. Cannot be bypassed — tools reject invalid
   operations.
3. **Hooks** — Session-start hook that echoes a reminder. Fires once,
   agent can ignore.

12 documented reflections show that mechanism 1 fails consistently.
Mechanism 2 works perfectly but only covers sprint lifecycle transitions.
Mechanism 3 is too weak.

This sprint adds two new mechanisms:

4. **Path-scoped rules** — `.claude/rules/` files with `paths` frontmatter.
   Claude Code loads these on demand when the agent accesses files
   matching the path pattern. Short, targeted, re-injected on every
   file access.
5. **Directory-scoped subagents** — Subagents dispatched with an explicit
   working-directory constraint. Controller validates output stays in
   scope.

## Enforcement Layer Model

```mermaid
flowchart TB
    subgraph L1["Layer 1: Instructional (weakest)"]
        claude["CLAUDE.md / AGENTS.md"]
        skills["Skill definitions"]
        instr["Instruction files"]
    end

    subgraph L2["Layer 2: Contextual (new)"]
        rules["Path-scoped rules<br/>(.claude/rules/)"]
        scope["Directory scope<br/>in subagent prompt"]
    end

    subgraph L3["Layer 3: Mechanical (strongest)"]
        statedb["State DB phase gates"]
        locks["Execution locks"]
        guards["MCP tool guards"]
    end

    subgraph L4["Layer 4: Validation (post-hoc)"]
        review["Controller reviews<br/>subagent output"]
        scopecheck["Directory scope<br/>validation"]
        sprintreview["Sprint review<br/>MCP tools"]
    end

    L1 -->|"loads at session start<br/>fades from context"| agent["Agent"]
    L2 -->|"loads on file access<br/>re-injects at decision point"| agent
    L3 -->|"rejects invalid operations<br/>cannot be bypassed"| agent
    agent -->|"produces output"| L4
    L4 -->|"reject + re-dispatch<br/>if out of scope"| agent

    style L1 fill:#ffe0e0,stroke:#c00
    style L2 fill:#fff3e0,stroke:#f90
    style L3 fill:#e0f0e0,stroke:#090
    style L4 fill:#e0e8f0,stroke:#069
```

## Path-Scoped Rules

### How Claude Code loads rules

Rules live in `.claude/rules/*.md`. Each file has YAML frontmatter
with a `paths` field — a list of glob patterns. When the agent reads
or writes a file matching any pattern, Claude Code loads the rule into
context. Rules are:

- **On-demand** — not loaded at session start; loaded when a matching
  file is accessed
- **Re-injected** — loaded again if the agent accesses the path after
  context compaction
- **Additive** — multiple matching rules all load; they don't override
  each other

### Rule inventory

```
.claude/rules/
├── clasi-artifacts.md    # paths: docs/clasi/**
├── source-code.md        # paths: claude_agent_skills/**, tests/**
├── todo-dir.md           # paths: docs/clasi/todo/**
└── git-commits.md        # paths: **/*.py, **/*.md
```

### Rule: clasi-artifacts

```yaml
paths:
  - docs/clasi/**
```

Fires when: agent touches any planning artifact (sprints, tickets,
TODOs, architecture, overview).

Content: Verify active sprint or OOP. Use CLASI MCP tools, not manual
file operations.

### Rule: source-code

```yaml
paths:
  - claude_agent_skills/**
  - tests/**
```

Fires when: agent modifies source code or tests.

Content: Verify in-progress ticket or OOP. Follow execute-ticket skill.
Run tests after changes.

### Rule: todo-dir

```yaml
paths:
  - docs/clasi/todo/**
```

Fires when: agent works in the TODO directory. More specific than
clasi-artifacts — both fire, but this one adds the tool-routing rule.

Content: Use CLASI `todo` skill or `move_todo_to_done` MCP tool. Do
not use generic TodoWrite.

### Rule: git-commits

```yaml
paths:
  - "**/*.py"
  - "**/*.md"
```

Fires when: agent touches any Python or Markdown file (which is nearly
always when committing).

Content: Run tests before committing. Verify sprint branch and
execution lock if on a sprint. Reference ticket ID in commit message.

### Coverage matrix

| Failure Mode | Which rules fire |
|---|---|
| Process bypass (no sprint) | clasi-artifacts, source-code |
| Wrong tool (TodoWrite) | todo-dir |
| No tests before commit | git-commits, source-code |
| Decision-point consultation | source-code (links to execute-ticket) |
| Completion bias | git-commits (verify before commit) |

## Directory-Scoped Subagent Dispatch

### Current model

The `dispatch-subagent` skill defines a controller/worker pattern:
controller curates context, dispatches via the Agent tool, reviews
results. But the subagent has no directory restriction — it can modify
any file it can access.

### New model

The controller specifies a **scope directory** for each subagent. This
is the directory the subagent is allowed to modify. The constraint
operates at two levels, with a third reserved for future implementation:

```mermaid
flowchart LR
    subgraph Dispatch["Controller dispatches"]
        prompt["Subagent prompt includes:<br/>scope_directory constraint"]
    end

    subgraph Execute["Subagent executes"]
        work["Reads context files<br/>(any location)"]
        write["Writes to<br/>scoped directory"]
        rules2["Path-scoped rules<br/>reinforce the constraint"]
    end

    Dispatch --> Execute

    style Dispatch fill:#e8f4fd
    style Execute fill:#f0f8e8
```

### Scope enforcement levels

1. **Prompt-level** (active) — The subagent prompt says "You may only
   create or modify files under `<scope_directory>`." The subagent can
   still read files anywhere (it needs to for context).

2. **Rule-level** (active) — If the subagent accesses files outside its
   scope, the path-scoped rules for those directories fire and remind
   it of the process requirements. This creates friction for out-of-scope
   writes.

3. **Validation-level** (future) — Post-hoc validation where the
   controller checks which files were modified. Deferred — the four-tier
   hierarchy with prompt + rules provides sufficient guidance, and
   OS-level file watching may handle this more reliably in the future.

### Subagent scope examples

| Task | Subagent type | Scope directory | Can read |
|---|---|---|---|
| Create TODOs from GitHub issues | todo-worker | `docs/clasi/todo/` | issue data, existing TODOs |
| Implement ticket code | python-expert | `claude_agent_skills/`, `tests/` | ticket, architecture, instructions |
| Write sprint planning docs | planner | `docs/clasi/sprints/NNN-slug/` | overview, previous architecture, TODOs |
| Update documentation | doc-writer | `docs/`, `README.md` | source code, existing docs |
| Code review | reviewer | (read-only, no writes) | changed files, ticket, standards |

### Dispatch-subagent skill changes

The skill gains:
- `scope_directory` parameter in the dispatch prompt template
- Context logging (see below) — every dispatch is recorded

### Subagent-protocol instruction changes

The instruction gains a new section: **Directory Scope**
- When dispatching, always specify the scope directory
- Subagents may read files from any location (needed for context)
- Subagents may only write/create/modify files within their scope
- If the task requires writing outside the scope, the subagent should
  return a request to the controller asking for expanded scope

## Subagent Hierarchy

The agent model has four tiers. Each tier delegates downward and
validates upward. No tier reaches past its immediate children.

### Hierarchy Diagram

```mermaid
flowchart TB
    user["Stakeholder"]

    subgraph T0["Tier 0: Main Controller"]
        mc["main-controller<br/>Knows: requirements, planning, execution<br/>Writes: nothing (dispatches only)"]
    end

    subgraph T1["Tier 1: Domain Controllers"]
        rn["requirements-narrator<br/>Scope: docs/clasi/overview.md"]
        tw["todo-worker<br/>Scope: docs/clasi/todo/"]
        sp["sprint-planner<br/>Scope: docs/clasi/sprints/NNN/<br/>Receives: TODO IDs<br/>Returns: sprint with tickets"]
        se["sprint-executor<br/>Scope: docs/clasi/sprints/NNN/<br/>Receives: sprint + tickets<br/>Returns: completed sprint"]
        ah["ad-hoc-executor<br/>Scope: per-task<br/>No sprint ceremony"]
        sr["sprint-reviewer<br/>Scope: read-only<br/>Post-sprint validation"]
    end

    subgraph T2["Tier 2: Task Workers"]
        arch["architect<br/>Scope: architecture.md"]
        ar["architecture-reviewer<br/>Scope: read-only"]
        tl["technical-lead<br/>Scope: tickets/"]
        cm["code-monkey<br/>Scope: source + tests + docs<br/>Receives: one ticket + plan<br/>Returns: implemented ticket"]
        cr["code-reviewer<br/>Scope: read-only"]
    end

    user --> mc

    mc --> rn
    mc --> tw
    mc --> sp
    mc --> se
    mc --> ah
    mc --> sr

    sp --> arch
    sp --> ar
    sp --> tl

    se --> cm

    ah --> cm
    ah --> cr

    style T0 fill:#e8f4fd,stroke:#069
    style T1 fill:#f0f8e8,stroke:#393
    style T2 fill:#fff3e0,stroke:#f90
```

### Tier Descriptions

| Tier | Agent | Receives | Returns | Write Scope | Delegates to |
|------|-------|----------|---------|-------------|-------------|
| 0 | **main-controller** | Stakeholder input | Status reports | None | T1 agents. Validates sprint frontmatter on return. |
| 1 | **requirements-narrator** | Stakeholder narrative | Overview doc | `docs/clasi/overview.md` | None |
| 1 | **todo-worker** | Ideas, GitHub issues | TODO files | `docs/clasi/todo/` | None |
| 1 | **sprint-planner** | TODO IDs, goals | Sprint with tickets | `docs/clasi/sprints/NNN/` | architect, arch-reviewer, technical-lead |
| 1 | **sprint-executor** | Sprint + ticket list | Completed sprint | `docs/clasi/sprints/NNN/` | code-monkey. Validates ticket frontmatter after each return. Updates sprint frontmatter to done when all tickets complete. |
| 1 | **ad-hoc-executor** | Change request | Completed change | Per-task | code-monkey, code-reviewer |
| 1 | **sprint-reviewer** | Completed sprint | Review verdict | Read-only | None |
| 2 | **architect** | Sprint goals, prev arch | Updated architecture.md | `architecture.md` | None |
| 2 | **architecture-reviewer** | Architecture doc | Review verdict | Read-only | None |
| 2 | **technical-lead** | Architecture, use cases | Numbered tickets | `tickets/` | None |
| 2 | **code-monkey** | One ticket + plan | Implemented code, updated ticket frontmatter | Source + tests + docs | None. Gets language-specific instructions per project. |
| 2 | **code-reviewer** | Changed files, ticket | Pass/fail verdict | Read-only | None |

### Data Flow: TODO Through the Tiers

```mermaid
sequenceDiagram
    participant S as Stakeholder
    participant MC as Main Controller
    participant TW as TODO Worker
    participant SP as Sprint Planner
    participant SE as Sprint Executor
    participant CM as Code Monkey
    participant CR as Code Reviewer

    S->>MC: "Import issues and plan a sprint"
    MC->>TW: Import GitHub issues as TODOs
    TW-->>MC: Created TODO-001, TODO-002, TODO-003

    MC->>SP: Plan sprint with TODO-001, TODO-002
    SP->>SP: Create sprint docs, architecture
    SP->>SP: Run architecture review
    SP->>SP: Create tickets from TODOs
    SP-->>MC: Sprint 001 ready (3 tickets)

    MC->>SE: Execute sprint 001
    SE->>CM: Execute ticket 001
    CM->>CM: Implement, test, update frontmatter
    CM-->>SE: Ticket 001 changes
    SE->>SE: Validate ticket 001 frontmatter (status=done, criteria checked)
    Note over SE: If frontmatter incomplete, send back to code-monkey

    SE->>CM: Execute ticket 002
    CM-->>SE: Ticket 002 changes
    SE->>SE: Validate ticket 002 frontmatter

    SE->>CM: Execute ticket 003
    CM-->>SE: Ticket 003 changes
    SE->>SE: Validate ticket 003 frontmatter

    SE->>SE: All tickets done — update sprint frontmatter to done
    SE-->>MC: Sprint 001 complete (sprint.md status=done)

    MC->>MC: Validate sprint frontmatter (status=done)
    MC->>MC: Close sprint, version bump
    MC-->>S: Sprint 001 closed
```

### Context Logging

Every dispatch records what context was sent to the subagent. This
creates an audit trail for debugging why a subagent made a specific
decision.

**What is logged per dispatch:**

Each dispatch is logged as a markdown file with YAML frontmatter for
the structured metadata and the full prompt text as the body. This
means you can search the logs, read them as documents, and parse the
frontmatter programmatically.

**Log directory structure:**

```
docs/clasi/log/
├── sprints/
│   ├── 001-my-sprint/
│   │   ├── sprint-planner-001.md  # first planning dispatch
│   │   ├── sprint-planner-002.md  # second planning dispatch
│   │   ├── ticket-001-001.md      # first dispatch for ticket 001
│   │   ├── ticket-001-002.md      # code review for ticket 001
│   │   ├── ticket-002-001.md
│   │   └── ticket-003-001.md
│   └── 002-next-sprint/
│       └── ...
└── adhoc/
    ├── 001.md                     # first ad-hoc change
    ├── 002.md                     # second ad-hoc change
    └── ...                        # monotonic counter
```

**Routing rules:**
- **Sprint planning dispatches**: `docs/clasi/log/sprints/<sprint-name>/sprint-planner-NNN.md`
- **Ticket dispatches**: `docs/clasi/log/sprints/<sprint-name>/ticket-NNN-NNN.md`
  (ticket number + dispatch sequence)
- **Ad-hoc dispatches**: `docs/clasi/log/adhoc/<N>.md`

**Log format:**

```markdown
---
timestamp: "2026-03-19T14:30:00"
parent: sprint-executor
child: code-monkey
scope: claude_agent_skills/
ticket: "001"
sprint: "001-my-sprint"
result: success
files_modified:
  - claude_agent_skills/artifact_tools.py
  - tests/unit/test_artifact_tools.py
---

# Dispatch: sprint-executor → code-monkey

<full prompt text sent to the subagent, including all context
curation, scope constraints, ticket description, acceptance
criteria, file contents — everything the subagent received>
```

The frontmatter gives you structured data for filtering and reporting.
The body is the complete prompt — the exact text the subagent saw.
Nothing is summarized or truncated.

### Mapping to Existing Agents

| New hierarchy role | Current agent file | Status |
|---|---|---|
| main-controller | `project-manager.md` | Refactor to pure dispatcher |
| requirements-narrator | `requirements-analyst.md` + `product-manager.md` | Merge or keep both |
| todo-worker | (new) | New agent definition |
| sprint-planner | (new) | Extracted from project-manager |
| sprint-executor | (new) | Extracted from project-manager. Validates ticket frontmatter, updates sprint frontmatter. |
| ad-hoc-executor | (new) | Formalize OOP pattern |
| sprint-reviewer | (new, or extract from close-sprint) | Post-sprint validation |
| architect | `architect.md` | Unchanged |
| architecture-reviewer | `architecture-reviewer.md` | Unchanged |
| technical-lead | `technical-lead.md` | Unchanged |
| code-monkey | `python-expert.md` | Renamed. Absorbs ticket-implementer + documentation-expert. Language-agnostic — gets language-specific instructions per project. |
| code-reviewer | `code-reviewer.md` | Unchanged |

**Removed agents:**
- `python-expert.md` — replaced by code-monkey (no Python-specific behavior)
- `documentation-expert.md` — absorbed into code-monkey (docs are part of ticket implementation)

## Agent Directory Structure

The code directory structure mirrors the agent hierarchy. Each agent
gets its own directory containing `agent.md` plus any skills,
instructions, or rules specific to that agent.

### New layout

```
agents/
├── main-controller/
│   └── main-controller/
│       ├── agent.md              # was project-manager.md
│       ├── next.md               # skill: determine next step
│       └── project-status.md     # skill: report project state
│
├── domain-controllers/
│   ├── requirements-narrator/
│   │   ├── agent.md              # was requirements-analyst.md + product-manager.md
│   │   ├── elicit-requirements.md    # skill
│   │   └── project-initiation.md     # skill
│   │
│   ├── todo-worker/
│   │   ├── agent.md              # new
│   │   ├── todo.md               # skill: create TODO
│   │   └── gh-import.md          # skill: import GitHub issues
│   │
│   ├── sprint-planner/
│   │   ├── agent.md              # new (extracted from project-manager)
│   │   ├── plan-sprint.md        # skill
│   │   └── create-tickets.md     # skill
│   │
│   ├── sprint-executor/
│   │   ├── agent.md              # new (extracted from project-manager)
│   │   ├── execute-ticket.md     # skill
│   │   └── close-sprint.md       # skill
│   │
│   ├── ad-hoc-executor/
│   │   ├── agent.md              # new (formalized OOP)
│   │   └── oop.md                # skill
│   │
│   └── sprint-reviewer/
│       └── agent.md              # new
│
└── task-workers/
    ├── architect/
    │   ├── agent.md              # was architect.md
    │   └── architectural-quality.md  # instruction (specific to architect)
    │
    ├── architecture-reviewer/
    │   └── agent.md              # was architecture-reviewer.md
    │
    ├── technical-lead/
    │   └── agent.md              # was technical-lead.md
    │
    ├── code-monkey/
    │   ├── agent.md              # was python-expert.md (renamed, expanded)
    │   ├── tdd-cycle.md          # skill (optional)
    │   ├── systematic-debugging.md   # skill
    │   └── python-code-review.md     # skill (language-specific)
    │
    └── code-reviewer/
        └── agent.md              # was code-reviewer.md
```

### What stays global

Some content is not agent-specific and remains at the top level:

```
skills/
├── se.md                 # /se dispatcher (entry point)
├── auto-approve.md       # cross-cutting mode
├── self-reflect.md       # cross-cutting behavior
├── dispatch-subagent.md  # dispatch protocol (used by all controllers)
├── parallel-execution.md # cross-cutting optimization
├── report.md             # bug reporting
├── ghtodo.md             # create GitHub issues
└── generate-documentation.md  # standalone doc generation

instructions/
├── software-engineering.md    # overall process
├── coding-standards.md        # all code
├── git-workflow.md            # all commits
├── testing.md                 # all tests
├── subagent-protocol.md       # all dispatchers
├── worktree-protocol.md       # parallel execution
├── dotconfig.md               # external tool
├── rundbat.md                 # external tool
└── languages/                 # per-language coding standards
    └── ...
```

### Migration from current layout

| Current file | New location |
|---|---|
| `agents/project-manager.md` | `agents/main-controller/main-controller/agent.md` |
| `agents/requirements-analyst.md` | `agents/domain-controllers/requirements-narrator/agent.md` (merge with product-manager) |
| `agents/product-manager.md` | merged into requirements-narrator |
| `agents/architect.md` | `agents/task-workers/architect/agent.md` |
| `agents/architecture-reviewer.md` | `agents/task-workers/architecture-reviewer/agent.md` |
| `agents/technical-lead.md` | `agents/task-workers/technical-lead/agent.md` |
| `agents/python-expert.md` | `agents/task-workers/code-monkey/agent.md` (renamed) |
| `agents/code-reviewer.md` | `agents/task-workers/code-reviewer/agent.md` |
| `agents/documentation-expert.md` | absorbed into code-monkey |
| `skills/plan-sprint.md` | `agents/domain-controllers/sprint-planner/plan-sprint.md` |
| `skills/create-tickets.md` | `agents/domain-controllers/sprint-planner/create-tickets.md` |
| `skills/execute-ticket.md` | `agents/domain-controllers/sprint-executor/execute-ticket.md` |
| `skills/close-sprint.md` | `agents/domain-controllers/sprint-executor/close-sprint.md` |
| `skills/oop.md` | `agents/domain-controllers/ad-hoc-executor/oop.md` |
| `skills/todo.md` | `agents/domain-controllers/todo-worker/todo.md` |
| `skills/gh-import.md` | `agents/domain-controllers/todo-worker/gh-import.md` |
| `skills/elicit-requirements.md` | `agents/domain-controllers/requirements-narrator/elicit-requirements.md` |
| `skills/project-initiation.md` | `agents/domain-controllers/requirements-narrator/project-initiation.md` |
| `skills/next.md` | `agents/main-controller/main-controller/next.md` |
| `skills/project-status.md` | `agents/main-controller/main-controller/project-status.md` |
| `skills/tdd-cycle.md` | `agents/task-workers/code-monkey/tdd-cycle.md` |
| `skills/systematic-debugging.md` | `agents/task-workers/code-monkey/systematic-debugging.md` |
| `skills/python-code-review.md` | `agents/task-workers/code-monkey/python-code-review.md` |
| `instructions/architectural-quality.md` | `agents/task-workers/architect/architectural-quality.md` |

### Process tools impact

The MCP `process_tools.py` currently serves agents, skills, and
instructions from flat directories. This needs updating:
- `list_agents()` should walk the new directory tree
- `get_agent_definition(name)` should find `agent.md` in the matching
  subdirectory
- Agent-specific skills/instructions could be returned alongside the
  agent definition, or via a new `get_agent_context(name)` tool that
  returns the agent definition plus all files in its directory

## Init Command Changes

`init_command.py` gains a `_create_rules()` function that:

1. Creates `.claude/rules/` directory
2. Writes each rule file (4 files)
3. Is idempotent: compares content before writing, skips unchanged files
4. Preserves any custom rules the developer has added

The rules content is bundled with the CLASI package (in a new
`init/rules/` directory or as string constants in `init_command.py`).

## Open Questions

None.

## Sprint Changes

Changes planned for sprint 001:

### New Components

**Path-scoped rules** (`.claude/rules/`) — Four rule files installed by
`clasi init`. Not Python code — static markdown with YAML frontmatter.

### Changed Components

**Init Command (`init_command.py`)** — New `_create_rules()` function
to install rule files during init. Follows the same idempotent pattern
as `_write_se_skill` and `_update_hooks_config`.

**Skill: `dispatch-subagent`** — Updated with `scope_directory` parameter
and context logging.

**Instruction: `subagent-protocol`** — New "Directory Scope" section
defining the read-anywhere/write-in-scope constraint.

**Log directory** (`docs/clasi/log/`) — New directory for dispatch
context logs. Sprint logs in `log/sprints/<name>/`, ad-hoc logs in
`log/adhoc/<N>.md`.

### Migration Concerns

Non-breaking. Rules are new files that don't affect existing behavior.
Running `clasi init` on existing projects adds the rules without
modifying other artifacts. The dispatch skill changes are additive —
subagents dispatched without a scope directory work as before.
