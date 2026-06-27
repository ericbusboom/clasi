---
status: done
---

# `clasi status` — per-agent process status, computed from the state machines

## Context

Today, agents (team-lead, sprint-planner, programmer) work out the
current state of the project by piecing together output from several
narrow MCP tools (`list_sprints`, `get_sprint_phase`, `list_tickets`,
`list_issues`, …). There is no single place that says *"here is where
you are, here is what you can do next, here is what is blocking you."*
That makes it easy for an agent to skip a gate, work on the wrong
sprint, or attempt an action the process does not allow.

This feature depends on the model in
[docs/design/state-machines.md](docs/design/state-machines.md): three
state machines (project, sprint, ticket), each state with named
**invariants**, each transition with named **conditions** and an
**action**. Predicates are `is_*` functions. The state machine is the
source of truth for what is legal.

The point of `clasi status` is to *report the output of the state
machines* in a form agents and humans can act on:

- For each context (project / sprint / ticket), report the current
  state — the state whose invariants are all true.
- For each outbound transition from that state, report whether it is
  currently fireable, and if not, which predicates failed.
- Tailor the view to the asking agent (team-lead = whole project;
  sprint-planner = a sprint; programmer = a ticket).

## Interface

### Surfaces

The same content is reachable three ways:

- **CLI:** `clasi status [--agent ROLE] [--sprint ID] [--ticket ID] [--format yaml|json]`
- **MCP tool:** `get_status(agent, sprint_id, ticket_id) -> JSON`
- **Auto-injected hook context** on `UserPromptSubmit` and
  `SubagentStart`: a `## CLASI status` block containing the same data
  as the CLI, in YAML. Silently no-ops if the project is not
  CLASI-initialized or `.clasi/oop` exists.

The agent role defaults to `$CLASI_AGENT_NAME`, then `team-lead`. CLI
output defaults to YAML; the MCP and hook surfaces are structured
data.

### Agent scopes

| Agent           | Scope                                       | Required arg |
|-----------------|---------------------------------------------|--------------|
| `team-lead`     | All three machines, all sprints             | none         |
| `sprint-planner`| Project + one sprint (tickets summarized)   | sprint id    |
| `programmer`    | One ticket plus parent sprint and project   | ticket id    |

If an agent is given without its required arg, fall back to the
broadest view that agent can legitimately see and include a note
explaining the fallback.

### Output shape (team-lead view)

```yaml
agent: team-lead
project:
  state: planning                  # computed from invariants
  available_transitions:
    - name: enter-sprint
      to: in-sprint
      fireable: false
      blocked_by:
        - is_any_sprint_ticketed
sprints:
  - id: "001"
    state: planned
    available_transitions:
      - name: architecture-review
        to: pre-flight
        fireable: true
        action: record_architecture_review
    tickets:
      total: 0
  - id: "022"
    state: executing
    available_transitions:
      - name: complete
        to: review
        fireable: false
        blocked_by:
          - is_all_tickets_done
    tickets:
      total: 4
      by_state:
        open: 0
        in-progress: 1
        done: 3
        exception: 0
      details:
        - id: "022-03"
          state: in-progress
          available_transitions:
            - name: finish
              to: done
              fireable: false
              blocked_by:
                - is_tests_passing
            - name: throw
              to: exception
              fireable: false
              blocked_by:
                - is_blocker_identified
issues:
  total: 7
  pending: 5
  assigned_to_sprint: 2
notes:
  current_focus: "Ticket 022-03 is in-progress; tests are failing"
  allowed_next_actions:
    - "Fire `architecture-review` on sprint 001"
  blocked_actions:
    - "Fire `complete` on sprint 022 — blocked by is_all_tickets_done"
    - "Fire `finish` on ticket 022-03 — blocked by is_tests_passing"
inconsistencies: []                # see Consistency below
```

### Narrowed views

`--agent sprint-planner --sprint 022` keeps the `project:` block,
keeps the matching entry under `sprints:`, summarizes its `tickets:`
without `details:`, and removes other sprints. The `notes:` block is
recomputed against the narrowed scope.

`--agent programmer --ticket 022-03` keeps the `project:` block as
read-only context, replaces `sprints:` with the single parent sprint
in summary form (state + name only), and shows one ticket under
`tickets.details`. The `notes:` block focuses on that ticket's
transitions.

### State computation rule

`state:` is the state whose invariants all evaluate true. If frontmatter
`status:` disagrees with the computed state, status does not silently
prefer one — it reports the disagreement under `inconsistencies:`:

```yaml
inconsistencies:
  - kind: state_drift
    machine: sprint
    id: "001"
    declared: planned
    computed: open
    explanation: |
      sprint.md declares status=planned but is_architecture_present
      is False.
```

There is no `next_phase` or `can_advance` field. The set of
`available_transitions` is the answer to both questions: a transition
with `fireable: true` is what you can do next; one with
`fireable: false` lists the predicates that block it.

### Format

`--format yaml` (default for CLI / hook) produces the YAML above
verbatim. `--format json` (default for MCP) produces the same shape
serialized as JSON. The hook injects YAML inside a fenced block under
a `## CLASI status` heading.

## Out of scope

- The state-machine engine itself (predicate / action registries,
  state-machine YAML loader, transition firing) — that is its own
  feature. This feature consumes those APIs read-only.
- Reconciling
  [clasi/schemas/se-process/schema.yaml](clasi/schemas/se-process/schema.yaml)
  (the 8-phase legacy model) with the new state-machine YAML.
- Rewriting the existing granular MCP tools (`get_sprint_phase`,
  `list_sprints`, etc.) on top of the engine. This feature is purely
  additive.

## Verification

1. `clasi status` in this repo prints YAML matching the output shape
   above, with the three machines populated.
2. `clasi status --format json` parses as valid JSON with the same
   shape.
3. `clasi status --agent sprint-planner --sprint 022` narrows output
   to that sprint with summarized tickets.
4. `clasi status --agent programmer --ticket <id>` narrows to one
   ticket plus parent context.
5. `mcp__clasi__get_status()` returns the JSON form of the same data.
6. With a fresh user prompt in a CLASI-initialized project, a
   `## CLASI status` block is auto-injected; in a repo with
   `.clasi/oop` present, the hook is silent.
7. A sprint whose `sprint.md` declares `status: planned` while
   `is_architecture_present` is false produces an `inconsistencies:`
   entry of kind `state_drift`.
8. A ticket mid-execution with failing tests reports
   `available_transitions[finish].fireable=false` with
   `blocked_by: [is_tests_passing]`.
