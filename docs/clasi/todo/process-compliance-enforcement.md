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

## Open Questions

- Can Claude Code hooks actually block tool execution (not just warn)?
- How much MCP server state can persist across tool calls within a
  session? Can we track "has loaded SE overview" as a session flag?
- Would intercepting generic tools (TodoWrite, Bash commits) via hooks
  create too much friction for legitimate use?
- Is there a way to make instructions "sticky" across context
  compaction — e.g., injecting them as system-level rather than
  conversation-level content?

## Related

- Sprint 015: Agent Process Compliance (docs/clasi/sprints/done/015-agent-process-compliance/)
- Sprint 017: Process Compliance Reinforcement (docs/clasi/sprints/done/017-process-compliance-reinforcement/)
- 12 reflections in docs/clasi/reflections/ and docs/clasi/reflections/done/
