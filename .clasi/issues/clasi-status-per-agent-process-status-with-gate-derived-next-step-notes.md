---
status: pending
---

# `clasi status` — per-agent process status with gate-derived next-step notes

## Context

Today, agents (team-lead, sprint-planner, programmer) work out the
current state of the project by piecing together output from several
narrow MCP tools (`list_sprints`, `get_sprint_phase`, `list_tickets`,
`list_issues`, …). There is no single place that says *"here is where
you are, here is what you can do next, here is what is blocking you."*
That makes it easy for an agent to skip a gate, work on the wrong
sprint, or attempt a transition the schema doesn't allow.

We want one authoritative status surface — available as a CLI command,
an MCP tool, and an auto-injected context block — that:

- Reports the full set of sprints, tickets, and issues in one structured
  document.
- Tailors the view to the asking agent (team-lead = whole project;
  sprint-planner = a sprint; programmer = a ticket).
- Includes a **notes** section derived from the active process schema's
  `requires`, `gate`, and `lock` rules, telling the agent which
  transitions are currently legal and which are blocked.

The output should be structured (YAML by default, JSON via a flag), so
both humans and agents can consume it cleanly with no templating.

## Approach

### 1. New module: `clasi/status.py`

Pure aggregation logic. No I/O of its own — receives a `Project`
instance and returns a Python `dict`. Renderable to YAML or JSON.

Key function:

```python
def build_status(
    project: Project,
    agent: str = "team-lead",
    sprint_id: str | None = None,
    ticket_id: str | None = None,
) -> dict:
    ...
```

Output skeleton (team-lead view):

```yaml
agent: team-lead
process: solo            # from schema name
version: 0.20260510.49
issues:
  total: 7
  pending: 5
  assigned_to_sprint: 2
sprints:
  - id: "001"
    title: Routing and Hint Discoverability
    status: planning-docs    # frontmatter
    phase: planning-docs     # state DB
    branch: sprint/001-...
    issues: 3
    tickets:
      total: 0
      open: 0
      in_progress: 0
      done: 0
    lock: null
    next_phase: ticketing
    can_advance: false
    blockers:
      - "planning-docs artifact not yet generated"
notes:
  current_focus: "Sprint 001 is in planning-docs phase"
  allowed_actions:
    - "Run the planning-docs skill to produce sprint plan artifacts"
  blocked_actions:
    - action: "create tickets"
      reason: "planning-docs must be complete before ticketing"
```

For `--agent sprint-planner --sprint 001`, the response narrows to one
sprint and its planning artifacts; for `--agent programmer --ticket
<id>`, it narrows to one ticket plus its sprint context.

### 2. Gate evaluator — reuse what exists, add a thin wrapper

`clasi/state_db_class.py` already owns phase advancement
(`_GATE_REQUIREMENTS`, `advance_phase`). We don't duplicate that logic.
Instead, add a read-only helper:

```python
# in clasi/state_db_class.py (or a new clasi/gates.py)
def evaluate_advance(
    state_db: StateDB,
    graph: ArtifactGraph,
    sprint_id: str,
) -> dict:
    """Return {current_phase, next_phase, can_advance, blockers: [...]}
    without mutating state."""
```

This mirrors `advance_phase` but returns the verdict instead of
applying it. It consults:

- `ArtifactGraph.requires(next_phase)` for upstream artifacts that must
  be generated.
- `ArtifactGraph.gate_for(current_phase)` plus `_GATE_REQUIREMENTS` for
  recorded review-gate results.
- The lock table for `executing` (lock must be held).
- The per-ticket gate (all tickets `done`) before `executing → closing`.

Critical files for this evaluator:
- [clasi/state_db_class.py](clasi/state_db_class.py) — `_GATE_REQUIREMENTS`, `advance_phase`, lock queries
- [clasi/schemas/graph.py](clasi/schemas/graph.py) — `ArtifactGraph.requires`, `gate_for`, `instruction_for`
- [clasi/schemas/loader.py](clasi/schemas/loader.py) — schema loader

### 3. Per-agent views

Agent name maps to a "scope" projection over the full status dict.
Define in `clasi/status.py`:

```python
AGENT_SCOPES = {
    "team-lead":      {"shows": "all", "requires_arg": None},
    "sprint-planner": {"shows": "single_sprint", "requires_arg": "sprint_id"},
    "programmer":     {"shows": "single_ticket", "requires_arg": "ticket_id"},
}
```

If an agent is given without its required arg, fall back to the broadest
view that agent can legitimately see and emit a note explaining the
fallback. If `CLASI_AGENT_NAME` env var is set and matches one of the
keys, the CLI uses it as the default for `--agent`.

The notes block per agent:

- **team-lead** — every sprint's `next_phase` + `blockers`, plus a
  top-level "what to do next" (e.g. "Sprint 002 is ready to advance to
  ticketing; team-lead may dispatch sprint-planner").
- **sprint-planner** — the one sprint's next legal transition and the
  instruction file path from `ArtifactGraph.instruction_for(next_phase)`.
- **programmer** — the ticket's status, sprint phase (must be
  `executing`), execution-lock holder, and whether this ticket can be
  picked up.

### 4. CLI: `clasi status`

Add to [clasi/cli.py](clasi/cli.py) following the `mcp` command pattern
(around line 254):

```python
@cli.command()
@click.option("--agent",
              type=click.Choice(["team-lead", "sprint-planner", "programmer"]),
              default=None,
              help="Agent role. Defaults to $CLASI_AGENT_NAME or team-lead.")
@click.option("--sprint", "sprint_id", default=None)
@click.option("--ticket", "ticket_id", default=None)
@click.option("--format", "fmt",
              type=click.Choice(["yaml", "json"]),
              default="yaml")
def status(agent, sprint_id, ticket_id, fmt):
    """Report CLASI project status for the given agent role."""
    from clasi.status_command import run_status
    run_status(agent=agent, sprint_id=sprint_id,
               ticket_id=ticket_id, fmt=fmt)
```

A thin `clasi/status_command.py` wires the Click command to
`build_status()` and pretty-prints. Mirrors `init_command.py`.

### 5. MCP tool: `get_status`

Add to [clasi/tools/artifact_tools.py](clasi/tools/artifact_tools.py)
(after `list_issues()`):

```python
@server.tool()
def get_status(agent: str = "team-lead",
               sprint_id: Optional[str] = None,
               ticket_id: Optional[str] = None) -> str:
    """Aggregate CLASI process status for the given agent.

    Returns JSON. The CLI form (`clasi status`) is the same data
    rendered as YAML for terminal output.
    """
    project = _open_project()
    return json.dumps(build_status(project, agent, sprint_id, ticket_id),
                      indent=2)
```

Existing granular tools (`get_sprint_phase`, `get_sprint_status`,
`list_sprints`, `list_tickets`, `list_issues`) **stay as-is** — this is
purely additive.

### 6. Hooks: auto-inject status

Edit [.claude/settings.json](.claude/settings.json) to add two new
hook entries (the file already uses the `clasi hook <event>` pattern):

```json
"UserPromptSubmit": [
  { "matcher": ".*",
    "hooks": [ { "type": "command", "command": "clasi hook status" } ] }
],
"SubagentStart": [   // existing entry — extend, don't replace
  { "matcher": ".*",
    "hooks": [
      { "type": "command", "command": "clasi hook subagent-start" },
      { "type": "command", "command": "clasi hook status" }
    ] }
]
```

Add a `status` event handler in
[clasi/hook_handlers.py](clasi/hook_handlers.py) (existing module —
see `cli.py:302` `from clasi.hook_handlers import handle_hook`):

- Reads `$CLASI_AGENT_NAME` (fallback `team-lead`).
- Calls `build_status(...)`.
- Emits as a Claude Code hook `additionalContext` block (YAML body
  inside a fenced ` ```yaml ` block, prefixed with a heading like
  `## CLASI status`).
- Silently no-ops if the project is not CLASI-initialized
  (`.clasi/` missing) or `docs/clasi/oop` exists.

The hook MUST be cheap — `build_status` should complete in well under
100 ms on a project with a handful of sprints (SQLite reads + a few
directory walks). If it exceeds a soft budget, the hook should print a
truncated summary rather than block the user.

## Critical files to modify or create

- **NEW** [clasi/status.py](clasi/status.py) — `build_status()` aggregator, agent-scope projection, notes renderer.
- **NEW** [clasi/status_command.py](clasi/status_command.py) — CLI wiring, YAML/JSON rendering.
- **MODIFY** [clasi/cli.py](clasi/cli.py) — add `status` subcommand (~line 254).
- **MODIFY** [clasi/tools/artifact_tools.py](clasi/tools/artifact_tools.py) — add `get_status` MCP tool.
- **MODIFY** [clasi/state_db_class.py](clasi/state_db_class.py) *(or NEW `clasi/gates.py`)* — add `evaluate_advance()` read-only helper.
- **MODIFY** [clasi/hook_handlers.py](clasi/hook_handlers.py) — add `status` event handler.
- **MODIFY** [.claude/settings.json](.claude/settings.json) — register `UserPromptSubmit` + extend `SubagentStart` hooks.
- **REUSE** [clasi/schemas/graph.py](clasi/schemas/graph.py) — `ArtifactGraph.requires/gate_for/instruction_for`.
- **REUSE** [clasi/project.py](clasi/project.py) — `list_sprints`, `list_issues`, sprint/ticket walkers.

## Verification

1. **Unit tests** (mirror existing tests under `tests/`):
   - `build_status` against a fixture project with sprints in each
     phase (roadmap, planning-docs, ticketing, executing, closing).
   - `evaluate_advance` returns `can_advance=False` with the right
     blockers when (a) upstream artifact missing, (b) gate not
     recorded, (c) execution lock not held.
   - Per-agent scope projections drop irrelevant sprints/tickets.

2. **CLI smoke test**:
   - `clasi status` in this repo prints YAML with at least one sprint
     and a `notes` block.
   - `clasi status --format json` parses as valid JSON.
   - `clasi status --agent sprint-planner --sprint 022` narrows
     output to sprint 022.
   - `clasi status --agent programmer --ticket <id>` narrows to a
     single ticket plus its sprint context.

3. **MCP smoke test**:
   - `mcp__clasi__get_status()` returns the same shape as the CLI
     (JSON form).

4. **Hook smoke test**:
   - With a fresh user prompt in a CLASI-initialized project, the
     `## CLASI status` block appears as injected context.
   - In a repo with `docs/clasi/oop` present, the hook is silent.
   - In a non-CLASI repo, the hook is silent.

5. **Manual end-to-end**:
   - Start a sprint, observe `next_phase=planning-docs`,
     `can_advance=true`.
   - Record the planning-docs artifact, observe the notes update.
   - Try to skip ahead — `can_advance=false` with a useful blocker
     message.
