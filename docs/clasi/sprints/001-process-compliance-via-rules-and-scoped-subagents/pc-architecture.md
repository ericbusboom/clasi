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
operates at three levels:

```mermaid
flowchart LR
    subgraph Dispatch["Controller dispatches"]
        prompt["Subagent prompt includes:<br/>'Only modify files under<br/>docs/clasi/todo/'"]
        scope["scope_directory:<br/>docs/clasi/todo/"]
    end

    subgraph Execute["Subagent executes"]
        work["Reads context files<br/>(any location)"]
        write["Writes only to<br/>scoped directory"]
        rules2["Rules for that directory<br/>reinforce the constraint"]
    end

    subgraph Validate["Controller validates"]
        check["Check: did subagent<br/>only modify files in<br/>scope_directory?"]
        accept["Accept output"]
        reject["Reject + re-dispatch<br/>with feedback"]
    end

    Dispatch --> Execute --> Validate
    check -->|yes| accept
    check -->|no| reject
    reject -->|"feedback: you modified<br/>files outside scope"| Execute

    style Dispatch fill:#e8f4fd
    style Execute fill:#f0f8e8
    style Validate fill:#fff3e0
```

### Three levels of scope enforcement

1. **Prompt-level** (instructional) — The subagent prompt says "You may
   only create or modify files under `<scope_directory>`." This is the
   weakest but most flexible level. The subagent can still read files
   anywhere (it needs to for context).

2. **Rule-level** (contextual) — If the subagent accesses files outside
   its scope, the rules for those directories fire and remind it of the
   process requirements. This creates friction for out-of-scope writes.

3. **Validation-level** (post-hoc) — The controller reviews the
   subagent's output and checks which files were modified. If any file
   is outside the scope directory, the controller rejects the output
   and re-dispatches with feedback explaining the violation.

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
- A post-dispatch validation step that lists modified files and checks
  each against the scope
- Rejection flow: if validation fails, compose a new prompt with the
  violation details and re-dispatch (max 2 retries, then escalate)

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
        ti["ticket-implementer<br/>Scope: per-ticket files<br/>Receives: one ticket + plan<br/>Returns: implemented ticket"]
    end

    subgraph T3["Tier 3: Leaf Workers"]
        py["python-expert<br/>Scope: source + tests"]
        cr["code-reviewer<br/>Scope: read-only"]
        doc["documentation-expert<br/>Scope: docs/"]
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

    se --> ti

    ah --> py
    ah --> cr

    ti --> py
    ti --> cr
    ti --> doc

    style T0 fill:#e8f4fd,stroke:#069
    style T1 fill:#f0f8e8,stroke:#393
    style T2 fill:#fff3e0,stroke:#f90
    style T3 fill:#fef0f0,stroke:#c66
```

### Tier Descriptions

| Tier | Agent | Receives | Returns | Write Scope | Delegates to |
|------|-------|----------|---------|-------------|-------------|
| 0 | **main-controller** | Stakeholder input | Status reports | None | T1 agents |
| 1 | **requirements-narrator** | Stakeholder narrative | Overview doc | `docs/clasi/overview.md` | None |
| 1 | **todo-worker** | Ideas, GitHub issues | TODO files | `docs/clasi/todo/` | None |
| 1 | **sprint-planner** | TODO IDs, goals | Sprint with tickets | `docs/clasi/sprints/NNN/` | architect, arch-reviewer, technical-lead |
| 1 | **sprint-executor** | Sprint + ticket list | Completed sprint | `docs/clasi/sprints/NNN/` | ticket-implementer |
| 1 | **ad-hoc-executor** | Change request | Completed change | Per-task | python-expert, code-reviewer |
| 1 | **sprint-reviewer** | Completed sprint | Review verdict | Read-only | None |
| 2 | **architect** | Sprint goals, prev arch | Updated architecture.md | `architecture.md` | None |
| 2 | **architecture-reviewer** | Architecture doc | Review verdict | Read-only | None |
| 2 | **technical-lead** | Architecture, use cases | Numbered tickets | `tickets/` | None |
| 2 | **ticket-implementer** | One ticket + plan | Implemented code | Source + tests | python-expert, code-reviewer, doc-expert |
| 3 | **python-expert** | Ticket plan, source files | Code changes | Source + tests | None |
| 3 | **code-reviewer** | Changed files, ticket | Pass/fail verdict | Read-only | None |
| 3 | **documentation-expert** | Ticket plan, source | Doc updates | `docs/`, `README` | None |

### Data Flow: TODO Through the Tiers

```mermaid
sequenceDiagram
    participant S as Stakeholder
    participant MC as Main Controller
    participant TW as TODO Worker
    participant SP as Sprint Planner
    participant SE as Sprint Executor
    participant TI as Ticket Implementer
    participant PY as Python Expert

    S->>MC: "Import issues and plan a sprint"
    MC->>TW: Import GitHub issues as TODOs
    TW-->>MC: Created TODO-001, TODO-002, TODO-003

    MC->>SP: Plan sprint with TODO-001, TODO-002
    SP->>SP: Create sprint docs, architecture
    SP->>SP: Run architecture review
    SP->>SP: Create tickets from TODOs
    SP-->>MC: Sprint 001 ready (3 tickets)

    MC->>SE: Execute sprint 001
    SE->>TI: Execute ticket 001
    TI->>PY: Implement code
    PY-->>TI: Code changes
    TI->>TI: Run tests, code review
    TI-->>SE: Ticket 001 done

    SE->>TI: Execute ticket 002
    TI-->>SE: Ticket 002 done

    SE->>TI: Execute ticket 003
    TI-->>SE: Ticket 003 done

    SE-->>MC: Sprint 001 complete
    MC->>MC: Close sprint, version bump
    MC-->>S: Sprint 001 closed
```

### Context Logging

Every dispatch records what context was sent to the subagent. This
creates an audit trail for debugging why a subagent made a specific
decision.

**What is logged per dispatch:**
- Timestamp
- Dispatching agent (parent) and receiving agent (child)
- Scope directory
- List of files included in context (paths only, not content)
- Prompt summary (first 200 chars)
- Result summary (success/failure, files modified)

**Where logs are stored:**
- **Ticket-level dispatches** (ticket-implementer, python-expert,
  code-reviewer): Logged to `tickets/NNN-slug-context.md` alongside
  the ticket plan.
- **Sprint-level dispatches** (architect, technical-lead, sprint-planner):
  Logged to `sprint-context-log.md` in the sprint directory.
- **Ad-hoc dispatches**: Logged to `docs/clasi/ad-hoc-context-log.md`.

### Mapping to Existing Agents

| New hierarchy role | Current agent file | Status |
|---|---|---|
| main-controller | `project-manager.md` | Refactor to pure dispatcher |
| requirements-narrator | `requirements-analyst.md` + `product-manager.md` | Merge or keep both |
| todo-worker | (new) | New agent definition |
| sprint-planner | (new) | Extracted from project-manager |
| sprint-executor | (new) | Extracted from project-manager |
| ad-hoc-executor | (new) | Formalize OOP pattern |
| sprint-reviewer | (new, or extract from close-sprint) | Post-sprint validation |
| architect | `architect.md` | Unchanged |
| architecture-reviewer | `architecture-reviewer.md` | Unchanged |
| technical-lead | `technical-lead.md` | Unchanged |
| ticket-implementer | (new) | Extracted from execute-ticket |
| python-expert | `python-expert.md` | Unchanged (leaf) |
| code-reviewer | `code-reviewer.md` | Unchanged (leaf) |
| documentation-expert | `documentation-expert.md` | Unchanged (leaf) |

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

**Skill: `dispatch-subagent`** — Updated with `scope_directory` parameter,
post-dispatch validation step, and rejection/re-dispatch flow.

**Instruction: `subagent-protocol`** — New "Directory Scope" section
defining the read-anywhere/write-in-scope constraint.

### Migration Concerns

Non-breaking. Rules are new files that don't affect existing behavior.
Running `clasi init` on existing projects adds the rules without
modifying other artifacts. The dispatch skill changes are additive —
subagents dispatched without a scope directory work as before.
