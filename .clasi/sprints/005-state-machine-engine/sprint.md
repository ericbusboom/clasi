---
id: "005"
title: "State Machine Engine"
status: roadmap
branch: sprint/005-state-machine-engine
use-cases: []
issues: []
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 005: State Machine Engine

## Goal

Build the state-machine engine that sprint 006 (clasi status Command)
consumes read-only. The design is fully specified in
`docs/design/state-machines.md` — three machines (Project, Sprint,
Ticket), each with named states, `is_*` invariant predicates, and named
transitions carrying `conditions:` predicates and an `action:`.

The engine delivers four surfaces:

1. **YAML loader** — reads machine definitions from
   `clasi/schemas/state-machines/*.yaml` and produces in-memory machine
   objects.
2. **Predicate registry** — maps `is_*` names to Python callables;
   supports a decorator-based registration pattern. Predicates are
   pure/read-only and receive a typed context object
   (`ProjectContext | SprintContext | TicketContext`).
3. **State evaluator** — given a machine and a context, walks the state
   list and returns the first state whose invariants all hold; raises if
   none or multiple match.
4. **Transition inspector** — given the current state and machine,
   returns each outbound transition annotated with `fireable: bool` and,
   when false, the list of blocking predicate names.

Action invocation and transition firing are OUT OF SCOPE. Sprint 006
calls the evaluator and inspector read-only; it does not fire
transitions.

## Issues in scope

None. This is a structural sprint delivering engine infrastructure only.
No tracked issues are claimed here.

## Out of scope

- Transition firing and action invocation.
- Rewriting existing MCP tools (`get_sprint_phase`, `list_sprints`,
  etc.) on top of the engine.
- Reconciling `clasi/schemas/se-process/schema.yaml` (the 8-phase
  legacy model) with the new state-machine YAML.
- Replacing `advance_sprint_phase`, `record_gate_result`, or any
  other MCP tools.

## Notes / open questions

1. **Where do the YAML machine files live?** Probably
   `clasi/schemas/state-machines/*.yaml` (one file per machine). Confirm
   at detail time.
2. **Predicate registry pattern.** Decorator-based
   (`@predicate("is_architecture_present")`) vs. explicit
   register-on-import. The decorator pattern is cleaner; confirm at
   detail time before committing to an API.
3. **State reader for predicates.** Does the engine read project state
   via existing MCP query tools (calling the MCP server from within the
   predicate), or does each predicate access the filesystem and state DB
   directly? The answer determines whether predicates are testable in
   isolation without a running MCP server.

## Tickets

| # | Title | Depends On |
|---|-------|------------|
| 001 | Define in-memory data model (Machine, State, Transition dataclasses) | — |
| 002 | YAML loader — read state-machine YAML files into Machine objects | 001 |
| 003 | Predicate registry — @predicate decorator, lookup, and listing | 001 |
| 004 | Context dataclasses and StateReader protocol | 001 |
| 005 | Implement all is_* predicates for project, sprint, and ticket machines | 003, 004 |
| 006 | State evaluator — evaluate_state, inspect_transitions, evaluate_predicates | 002, 003, 004, 005 |
| 007 | Public engine API — clasi/state_machine/__init__.py entry points | 006 |

Tickets execute serially in the order listed.
