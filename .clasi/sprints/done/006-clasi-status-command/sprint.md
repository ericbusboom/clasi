---
id: '006'
title: clasi status Command
status: done
branch: sprint/006-clasi-status-command
use-cases: []
issues:
- clasi-status-per-agent-process-status-with-gate-derived-next-step-notes.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 006: clasi status Command

## Goal

Give agents and humans a single unified command that says "here is where you are, here is what you can do next, and here is what is blocking you." Today, an agent must piece together output from multiple narrow MCP tools to understand project state — making it easy to skip a gate, work on the wrong sprint, or attempt a disallowed action. This sprint adds `clasi status` as a CLI command, `get_status` as an MCP tool, and a `## CLASI status` block auto-injected into agent context on `UserPromptSubmit` and `SubagentStart`. All three surfaces compute their output from the three state machines defined in `docs/design/state-machines.md` (Project, Sprint, Ticket), reporting current state, available transitions, and which predicates block non-fireable transitions.

## Issues in scope

- `issues/clasi-status-per-agent-process-status-with-gate-derived-next-step-notes.md` — implement CLI, MCP tool, and auto-injected hook context for `clasi status`; output shape is defined in the issue; agent-scoped narrowing (team-lead, sprint-planner, programmer) and inconsistency detection are both required.

## Out of scope

- The state-machine engine itself (predicate/action registries, state-machine YAML loader, transition firing logic) — this sprint consumes those APIs read-only and assumes the engine exists. If it does not yet exist, this sprint is blocked.
- Reconciling `clasi/schemas/se-process/schema.yaml` (the 8-phase legacy model) with the new state-machine YAML in `docs/design/state-machines.md`.
- Rewriting existing granular MCP tools (`get_sprint_phase`, `list_sprints`, etc.) on top of the engine — this sprint is purely additive.

## Notes / open questions

- **BLOCKING: State-machine engine prerequisite.** `docs/design/state-machines.md` exists and defines the target model, but there is no runnable engine in the codebase (no `clasi/state_machine*.py` or equivalent). This sprint cannot be detailed until the engine (predicate registry, YAML loader, transition evaluator) is implemented. Before dispatching sprint-planner in detail mode, confirm whether a prior sprint delivers the engine, or whether the engine work must be folded into this sprint's scope.
- **Agent role detection.** The issue specifies defaulting to `$CLASI_AGENT_NAME` then `team-lead`. The hook injection mechanism for `SubagentStart` needs to be designed — confirm the hook event name and available context variables at detail time.

## Tickets

| # | Title | Depends On |
|---|-------|------------|
| 001 | Implement ClasiStateReader against filesystem, git, and StateDB | — |
| 002 | Build StatusReporter to assemble the output shape | 001 |
| 003 | Agent-scope narrowing for sprint-planner and programmer views | 002 |
| 004 | Inconsistency detection for declared vs computed state drift | 002 |
| 005 | CLI command: clasi status with all flags | 003, 004 |
| 006 | MCP tool: get_status with agent scoping | 003, 004 |
| 007 | Hook injection: UserPromptSubmit and SubagentStart auto-inject status block | 003, 004 |
| 008 | End-to-end verification and documentation | 005, 006, 007 |

Tickets execute serially in the order listed.
