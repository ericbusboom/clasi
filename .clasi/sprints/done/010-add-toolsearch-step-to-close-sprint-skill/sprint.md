---
id: '010'
title: Add ToolSearch step to close-sprint skill
status: done
branch: sprint/010-add-toolsearch-step-to-close-sprint-skill
use-cases: []
issues: []
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 010: Add ToolSearch step to close-sprint skill

## Goals

Add a `ToolSearch` schema-loading step to the `close-sprint` skill so that agents
calling `close_sprint` receive the tool's full parameter schema before invoking it.
This prevents the silent parameter-drop that causes `sprint_id: Field required,
input_value={}` failures in foreign repos.

## Problem

CLASI MCP tools are deferred — their schemas are not loaded at session start. The
harness silently drops all parameters when an agent calls a deferred tool without
first fetching its schema via `ToolSearch`. The `close-sprint` skill has no
`ToolSearch` step, so every agent that follows it hits this drop and the
`close_sprint` call fails with a validation error.

## Solution

Insert one instruction step in `clasi/schemas/se-process/instructions/close.md`
(the file loaded by the `close-sprint` skill) that calls `ToolSearch` with
`select:mcp__clasi__close_sprint` immediately before the `close_sprint` invocation.
No logic, no new modules, no configuration — one line of skill text.

## Success Criteria

- The `close.md` instruction file contains a ToolSearch step before the
  `close_sprint` call.
- An agent following the updated skill loads the tool schema and can pass
  `sprint_id` (and other parameters) without them being dropped.

## Scope

### In Scope

- `clasi/schemas/se-process/instructions/close.md` — add ToolSearch step.

### Out of Scope

- Auditing other skills for the same problem (tracked in the issue as a
  follow-on recommendation, not part of this sprint).
- Redistribution to installed foreign repos — handled manually by the user
  after this sprint closes.

## Test Strategy

Manual verification: after the ticket is applied, read the updated `close.md`
and confirm the ToolSearch step appears before the `close_sprint` call block.
No automated test changes required — this is a documentation/skill file change.

## Architecture Notes

No architectural change. The skill file is a static instruction document consumed
by agents at runtime. The fix is additive — one new step in an existing numbered
list.

## GitHub Issues

(None linked.)

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [x] Sprint planning documents are complete (sprint.md, use cases, architecture)
- [x] Architecture review passed
- [x] Stakeholder has approved the sprint plan

## Tickets

| # | Title | Depends On |
|---|-------|------------|
| 001 | Add ToolSearch step to close.md | — |

Tickets execute serially in the order listed.
