---
status: pending
---

# Process Compliance Enforcement — Mechanical Over Instructional

**Do not implement yet — needs design discussion.**

## Problem

Agents persistently ignore the CLASI SE process despite 12 documented
reflections, two dedicated hardening sprints (015, 017), and increasingly
explicit mandatory directives. The failure pattern is identical every
time: agents have access to the instructions but don't consult them at
decision points. They rely on stored knowledge, which is incomplete and
decays across context shifts.

### What's been tried and failed

| Attempt | Sprint | Why it didn't work |
|---------|--------|-------------------|
| Mandatory prose directives in AGENTS.md | 015 | Agents read them once, then ignore at decision points |
| "CLASI Skills First" mandatory gate | 015 | Instruction, not enforcement — agents skip it |
| "Stop and report on failure" rule | 015 | Agents optimize for completion, not correctness |
| Inline CLASI block into CLAUDE.md | 017 | Reduces indirection but still relies on compliance |
| HTML reminder comments in templates | 017 | Agents likely don't notice HTML comments |
| Sprint review MCP tools | 015 | Tools exist but agents don't call them |
| Session-start hook | 021 | Fires a reminder but agent can still ignore it |

The common thread: **all fixes are instructional (prose telling the
agent what to do) rather than mechanical (systems that prevent the agent
from doing the wrong thing).**

### The five failure modes (from 12 reflections)

1. **Decision-point consultation failure** — Agent faces a decision,
   doesn't check the documented procedure, relies on memory instead.
2. **Process bypass** — Agent skips mandatory entry points entirely
   (never calls `get_se_overview()`, jumps to code).
3. **Wrong tool selection** — Agent uses generic tools (TodoWrite,
   superpowers skills) when CLASI tools exist for the same task.
4. **Completion bias** — When blocked, agent improvises a workaround
   instead of stopping and reporting.
5. **Shortcut misinterpretation** — "Auto-approve" means skip
   confirmations, but agents interpret it as skip the process.

## Proposed Direction: Mechanical Enforcement

The insight from the state database is instructive: sprint phase
transitions work because they're mechanically enforced — you literally
cannot create tickets before the ticketing phase. The agent doesn't need
to remember the rule because the system rejects the action.

Extend this principle to more failure points:

### 1. Pre-execution hooks that block, not remind

The session-start hook currently echoes a reminder. Instead, it could
check whether `get_se_overview()` has been called in this session and
refuse to allow tool use until it has. Research whether Claude Code
hooks can block execution (return non-zero exit code to prevent the
tool call).

### 2. MCP tool guards

Add validation to key MCP tools:
- `create_ticket` already blocks before ticketing phase — extend this
  pattern
- `move_ticket_to_done` could verify tests were mentioned in the commit
- `close_sprint` could verify all review gates were recorded
- New tools could refuse to operate if `get_se_overview()` hasn't been
  called in the current session (track via a session flag in the MCP
  server)

### 3. Pre-commit validation

A `PreToolUse` hook on `Bash(git commit:*)` that runs a lightweight
check: are we on a sprint branch? Does the sprint have an active
execution lock? Is the ticket in-progress? This catches process bypass
at the point of no return (committing code).

### 4. Ritual checklists at phase transitions

Instead of trusting the agent to remember what happens at each phase
transition, the MCP tools could return a checklist of required next
steps when advancing phases. The agent sees the list immediately after
the tool call, not buried in a document it might not read.

### 5. Reduce the surface area for mistakes

Some failures come from having too many ways to do the same thing.
If `TodoWrite` exists alongside CLASI `todo`, agents will sometimes
pick the wrong one. Consider:
- A hook that intercepts `TodoWrite` and redirects to CLASI `todo`
- Clearer routing in the `/se` dispatcher

### 6. Context-shift resilience

The 2026-03-10 reflection showed that knowledge fades across context
shifts. Consider:
- Periodic context refreshes (hook that re-injects key rules every N
  tool calls)
- Shorter, more targeted instructions that fit in active context rather
  than long documents that get compacted away

## Proposed Direction: Path-Scoped Rules (.claude/rules/)

Claude Code supports `.claude/rules/*.md` files with `paths` frontmatter
that scope instructions to specific directories. These rules load
**on demand when the agent accesses files matching the path pattern**.
This is the right mechanism because:

- Rules fire at the moment the agent is about to do something, not at
  session start when context is fresh but the work hasn't started.
- They're short and targeted — a few sentences per rule, not a long
  document that gets compacted away.
- They're centralized in `.claude/rules/` — easy to audit, unlike
  scattered CLAUDE.md files.
- They re-inject on every file access in the matching path, providing
  the context-shift resilience that long documents lack.

### Rule Design Principles

1. **Short** — 3-5 sentences max. If it's longer, the agent will skim it.
2. **Actionable** — Tell the agent exactly what to do, not what to think.
3. **Specific to the directory** — Don't repeat root-level instructions.
   Only state what's relevant to files in this path.
4. **Checklist over prose** — Numbered steps > paragraphs.

### Proposed Rules

#### Rule 1: Planning artifacts (docs/clasi/)

```markdown
<!-- .claude/rules/clasi-artifacts.md -->
---
paths:
  - docs/clasi/**
---

You are modifying CLASI planning artifacts. Before making changes:

1. Confirm you have an active sprint (`list_sprints(status="active")`),
   or the stakeholder said "out of process" / "direct change".
2. If creating or modifying tickets, the sprint must be in `ticketing`
   or `executing` phase (`get_sprint_phase(sprint_id)`).
3. Use CLASI MCP tools for all artifact operations — do not create
   sprint/ticket/TODO files manually.
```

**Targets failure modes**: Process bypass (#2), wrong tool selection (#3)

#### Rule 2: Source code changes

```markdown
<!-- .claude/rules/source-code.md -->
---
paths:
  - claude_agent_skills/**
  - tests/**
---

You are modifying source code or tests. Before writing code:

1. You must have a ticket in `in-progress` status, or the stakeholder
   said "out of process".
2. If you have a ticket, follow the execute-ticket skill — call
   `get_skill_definition("execute-ticket")` if unsure of the steps.
3. Run tests after changes: `uv run pytest`.
```

**Targets failure modes**: Process bypass (#2), decision-point
consultation (#1)

#### Rule 3: TODO directory

```markdown
<!-- .claude/rules/todo-dir.md -->
---
paths:
  - docs/clasi/todo/**
---

Use the CLASI `todo` skill or `move_todo_to_done` MCP tool for TODO
operations. Do not use the generic TodoWrite tool for CLASI TODOs.
```

**Targets failure modes**: Wrong tool selection (#3)

#### Rule 4: Git commits

```markdown
<!-- .claude/rules/git-commits.md -->
---
paths:
  - "**"
globs:
  - "*.py"
  - "*.md"
---

Before committing, verify:
1. All tests pass (`uv run pytest`).
2. If on a sprint branch, the sprint has an execution lock.
3. Commit message references the ticket ID if working on a ticket.
See `instructions/git-workflow` for full rules.
```

**Targets failure modes**: Process bypass (#2), completion bias (#4)

### Coverage Analysis

| Failure Mode | Which rules catch it | Mechanism |
|---|---|---|
| Decision-point consultation | Rule 2 (link to execute-ticket skill) | Re-reads skill at code-change time |
| Process bypass | Rules 1, 2, 4 (require sprint/ticket check) | Can't touch artifacts or code without seeing the reminder |
| Wrong tool selection | Rules 1, 3 (explicit tool routing) | Fires when touching the directory where mistakes happen |
| Completion bias | Rule 4 (verify before commit) | Last-chance check before permanent action |
| Shortcut misinterpretation | Rule 2 ("out of process" is the only escape) | Names the exact phrase needed to skip |

### What rules don't cover

- **Blocking enforcement** — Rules are still instructional. The agent
  can read the rule and ignore it. But rules have two advantages over
  AGENTS.md: (a) they fire at the decision point, not at session start,
  and (b) they're short enough to stay in active context.
- **Cross-session memory** — Rules don't know what happened in a
  previous conversation.

### Implementation as clasi init output

The rules should be created by `clasi init` alongside the other
artifacts. This means:
- Add a `_create_rules()` function to `init_command.py`
- Rules are written to `.claude/rules/` in the target project
- Idempotent — re-running init updates rules without duplicating
- The rules content is bundled in the CLASI package (like templates)

### Interaction with other proposals

Rules work alongside the other proposals in this TODO:
- **Hooks** (proposals 1, 3, 5) provide blocking enforcement
- **MCP tool guards** (proposal 2) provide server-side rejection
- **Rules** provide context-sensitive reminders at the file level
- **Ritual checklists** (proposal 4) provide post-action guidance

The recommended implementation order:
1. **Rules first** — highest value, lowest risk, no code changes needed
   to test (just create the files)
2. **MCP tool guards** — extend existing patterns in artifact_tools.py
3. **Hooks** — research blocking capability, then implement

## Open Questions

- Can Claude Code hooks actually block tool execution (not just warn)?
- How much MCP server state can persist across tool calls within a
  session? Can we track "has loaded SE overview" as a session flag?
- Would intercepting generic tools (TodoWrite, Bash commits) via hooks
  create too much friction for legitimate use?
- Should rules be checked into the CLASI package and installed by init,
  or should each project maintain its own rules?
- What's the right level of specificity? Too vague and agents ignore
  the rule; too specific and it becomes stale when the process changes.

## Related

- Sprint 015: Agent Process Compliance (docs/clasi/sprints/done/015-agent-process-compliance/)
- Sprint 017: Process Compliance Reinforcement (docs/clasi/sprints/done/017-process-compliance-reinforcement/)
- 12 reflections in docs/clasi/reflections/ and docs/clasi/reflections/done/
