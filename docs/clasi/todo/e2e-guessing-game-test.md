---
status: pending
---

# End-to-End Test: Guessing Game via CLASI Process

## Goal

Create an end-to-end test that exercises the entire CLASI SE process
from spec to working code. This validates that the three-tier agent
hierarchy, dispatch logging, path-scoped rules, and sprint lifecycle
all work together.

## The Test Application

A Python CLI guessing game with three games (number, color, city).
Menu-driven, 3 guesses per game, stdlib only. See
`tests/e2e/guessing-game-spec.md` for the full specification.

The spec prescribes 4 sprints:
1. Project structure + menu (games stub "Coming soon!")
2. Number guessing game
3. Color guessing game
4. City guessing game

## What the Test Does

1. Create a temp directory
2. Initialize CLASI in it (`clasi init`)
3. Place the guessing game spec as the project overview
4. Dispatch a main-controller subagent with the spec
5. The subagent runs the full CLASI process: plan 4 sprints, execute
   them, close them
6. After completion, verify:
   - The game works (`python -m guessing_game` starts, all 3 games
     function correctly)
   - All 4 sprints are in `docs/clasi/sprints/done/`
   - Each sprint has tickets in `tickets/done/`
   - State DB has all sprints in `done` phase
   - Dispatch logs exist in `docs/clasi/log/` with full prompt content
   - Tests exist and pass

## Implementation Approach

Use the Claude Agent SDK or the Agent tool to dispatch a subagent
into the temp directory. The subagent gets:
- The spec file
- Instructions to act as main-controller
- The CLASI MCP server connection

Alternatively, use `subprocess` to run `claude` CLI with the spec as
input — this tests the real user experience.

## Test Location

`tests/e2e/` directory. The spec is already at
`tests/e2e/guessing-game-spec.md`.

## Open Questions

- Best mechanism to drive Claude programmatically (Agent tool vs
  claude CLI subprocess vs Claude Agent SDK)?
- How long should the test timeout be (4 sprints could take a while)?
- Should this run in CI or be manual-only?
