---
status: pending
source: consolidation of 6 related TODOs
components:
  - sdk-based-orchestration.md
  - absorb-git-close-into-close-sprint.md
  - pretooluse-role-guard-hook.md
  - team-lead-parallel-sprint-planning.md
  - todo-lifecycle-in-progress-directory.md
  - agent-contracts-as-process-description.md
---

# SDK-Based Orchestration and Enforcement Hardening

## Summary

This cluster groups six TODOs that collectively move CLASI from
instruction-based dispatch to structurally enforced SDK-based
orchestration. The central change is that `dispatch_to_*` MCP tools
stop returning a prompt for the team-lead to forward and instead own the
full subagent lifecycle: render prompt, log, execute via Agent SDK
`query()`, validate result, log result, return output.

Every other TODO in this cluster either depends on that change or becomes
substantially simpler once it's in place.

## Dependency Ordering

```
agent-contracts              (0. design input — defines what dispatch tools
    │                             need to pass and validate; informs all others)
    │
sdk-based-orchestration      (1. foundation — must land first;
    │                             reads agent contracts to configure query())
    │
    ├── absorb-git-close     (2. first tool to adopt full-lifecycle pattern)
    │       │
    │       └── todo-lifecycle (3. in-progress state feeds close-sprint verification)
    │
    ├── pretooluse-role-guard (2. belt-and-suspenders once SDK dispatch removes
    │                              the Agent tool from team-lead's vocabulary)
    │
    └── parallel-sprint-planning (3. dispatch topology change; depends on SDK
                                     dispatch being the only dispatch path)
```

### 1. SDK-Based Orchestration (foundation)

**What changes**: `dispatch_to_sprint_planner`, `dispatch_to_sprint_executor`,
and `dispatch_to_code_monkey` become `async def` tools that call
`claude_agent_sdk.query()` internally. The team-lead never invokes
Claude's built-in `Agent` tool. Logging is structurally guaranteed
because the log call lives in the same function body as the `query()`
call.

**Architectural impact**: The MCP server gains a fifth responsibility —
**subagent orchestration** — on top of process content delivery, artifact
management, project initialization, and compliance enforcement. Each
agent definition becomes a typed contract: inputs, outputs, allowed
tools, MCP access, and return validation.

**Open design decisions**:
- Subagent MCP access: same server instance or new instance per subagent?
- Concurrent SQLite access under parallel dispatch.
- Authentication: inherit Claude Code session vs. `ANTHROPIC_API_KEY`.

### 2. Absorb Git Close into close_sprint

**What changes**: `close_sprint` MCP tool absorbs all git operations
(merge, tag, push, branch delete) that the agent currently does manually
after calling the tool. Pre-condition verification with self-repair.
Structured error with recovery state for partial failures.

**Why it's second**: It's the template for how every dispatch tool should
work post-SDK — the MCP tool owns the full lifecycle, the agent just
calls it and reports. Landing this before or alongside SDK dispatch
establishes the pattern.

**Dependency on SDK orchestration**: The recovery state mechanism
(allowed_paths in state DB, PreToolUse hook checking before blocking)
works independently, but the close-sprint skill simplification (from 15
steps to 3) only makes sense when the tool owns execution.

### 3. PreToolUse Role Guard

**What changes**: A `PreToolUse` hook blocks `Edit`/`Write`/`MultiEdit`
from the team-lead session. Hard stop, not a reminder.

**Relationship to SDK dispatch**: Once the team-lead can't call `Agent`
directly (because SDK dispatch tools are the only dispatch path), the
role guard becomes defense-in-depth rather than primary enforcement.
Still worth having — catches edge cases, out-of-process work,
user-directed writes that should be delegated.

**Design note**: Needs a bypass mechanism for OOP work (`.clasi-oop`
flag file or similar). The recovery state mechanism from close-sprint
also needs to interact with this hook — if a recovery record exists,
the hook must allow writes to the specific paths in the record.

### 4. TODO Lifecycle (in-progress directory)

**What changes**: TODOs gain a three-state lifecycle: `pending` →
`in-progress` → `done`, with a physical `todo/in-progress/` directory.
TODOs move to in-progress when incorporated into a sprint, and to done
individually when their referencing tickets close (not bulk-moved at
sprint close).

**Dependency on close-sprint changes**: close_sprint's pre-condition
verification step checks that all in-progress TODOs for the sprint have
been addressed. The three-state lifecycle gives it something concrete to
verify against.

### 5. Parallel Sprint Planning

**What changes**: The team-lead can plan multiple sprints in one pass.
Batch planning is high-level only — it produces sprint.md files with
goals, feature scope, and TODO references. No architecture docs, no
use cases, no tickets at this stage. Detailed planning (full artifacts)
happens one sprint at a time, immediately before execution.

**Late branching**: Sprint branches are created by `acquire_execution_lock`,
not during planning. Only one branch exists at a time. Because detailed
planning runs against the latest main, staleness is a non-issue — the
high-level roadmap items don't go stale, and the detailed artifacts are
always fresh.

**Execution is serial**: No parallel sprint execution. The execution
lock enforces this. The parallelism is only in Phase 1 roadmap planning.

**Dependency on SDK dispatch**: Once dispatch goes through `query()`,
the dispatch tool can accept a `mode` parameter (`roadmap` vs `detail`)
and validate accordingly. The team-lead's instruction to "plan multiple
sprints" becomes a parameter to the dispatch tool rather than a
behavioral instruction the team-lead may or may not follow.

### 6. Agent Contracts as Process Description

**What changes**: Each agent gets a `contract.yaml` alongside its
`agent.md`. The contract declares inputs (required and optional
documents), output files, a return JSON schema, delegation edges
(with informal `when` conditions), allowed tools, and MCP access.

**Three consumers.** The contract serves the dispatch tool (Python
code that configures `query()`, passes inputs, and validates outputs
and return JSON), the agent itself (reads the contract to know what
it's receiving, what to produce, and what JSON shape to return), and
humans/tools that want to understand the process flow.

**Inputs are documents, not prompt text.** The dispatch prompt is thin.
The substance comes from documents declared in the contract. Optional
documents allow callers to provide guidance or constraints.

**Returns are structured JSON.** The agent reads the `returns` schema
from its contract and formats its final response as JSON matching that
shape. The dispatch tool validates the JSON before passing it to the
caller. This closes the loop — the contract defines what goes in
(inputs), what gets created on disk (outputs), and what comes back
to the caller (returns).

**The contracts ARE the process description.** Walk `delegates_to`
edges from team-lead and you get the full process. Changes to process
flow are changes to contract.yaml files.

**Dependency on SDK dispatch**: The dispatch tools read contract.yaml
to configure `ClaudeAgentOptions`, resolve inputs, include the contract
in the agent's prompt, and validate returns. This TODO is the design
input for the SDK dispatch implementation.

## What This Sprint Does NOT Include

The remaining TODOs in `todo/` are intentionally excluded:

- **add-applicability-conditions-to-project-knowledge.md** — Independent
  improvement to the knowledge skill. No dependency on orchestration.
- **use-case-review-and-developer-engagement.md** — Explicitly marked
  "do not implement yet." New agent/skill for use-case review. Could
  benefit from SDK dispatch eventually but is a separate design effort.

## Architectural Questions to Resolve Before Ticketing

1. **MCP server as orchestrator**: Does the server process remain a
   single FastMCP instance that also spawns subagents? Or does
   orchestration move to a separate process/layer? Single instance is
   simpler but means a long-running `query()` call blocks the MCP
   tool from returning until the subagent finishes.

2. **Subagent MCP access**: Subagents need CLASI tools (create_ticket,
   list_todos, etc.). Options: (a) pass MCP server config in
   `ClaudeAgentOptions` pointing at the same running instance,
   (b) start a scoped instance per subagent, (c) have the orchestrating
   tool pre-fetch what the subagent needs and pass it as context.

3. **Concurrency model**: Execution is serial (one sprint at a time),
   but subagents spawned via `query()` may themselves spawn nested
   subagents (sprint-planner → architect). If multiple MCP server
   instances exist (parent + child), SQLite needs WAL mode for safe
   concurrent access. This is a modest concern, not a parallel
   execution problem.

4. **Recovery state and role guard interaction**: The PreToolUse hook
   needs to check recovery_state before blocking. This means the hook
   must be able to read the state DB. Currently hooks are bash scripts —
   reading SQLite from bash is possible but ugly. Consider making the
   hook call a lightweight MCP tool (`check_write_permission(path)`)
   instead of querying the DB directly.

5. **Agent contract formalization**: Each agent.md needs to declare its
   SDK contract (allowed_tools, MCP access, return schema). Where does
   this live — in the agent.md frontmatter, in a separate manifest, or
   in the dispatch tool's Python code? Frontmatter is readable by both
   humans and tools. Python code is enforceable but not visible to the
   agent reading its own definition.
