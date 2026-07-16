---
status: in-progress
type: bug
source: e2e-test-run-003
clasi_version: 0.20260715.2
tags:
- planning
- sprint-planner
- e2e
sprint: '020'
tickets:
- 020-006
---

# Sprint-planner produces excessively heavy plans for simple projects

## Description

For a trivial 3-game stdlib Python CLI (the guessing-game e2e), the sprint-planner consistently produces 1,300–2,300 word sprint plans with Mermaid architecture diagrams in every sprint. Sprint 018's right-sizing reduced plan volume by ~30% (from 1,866–2,958 words down to 1,317–2,278), but the plans are still wildly disproportionate to the project's complexity.

## Evidence (e2e run 003, clasi 0.20260715.2)

| Sprint | Words | Mermaid diagrams |
|--------|-------|-----------------|
| 001 — Project structure & menu | 1,317 | 1 |
| 002 — Number guessing game | 1,957 | 1 |
| 003 — Color guessing game | 2,020 | 1 |
| 004 — City guessing game | 2,278 | 1 |

Each sprint adds one ~60-line Python module and corresponding tests. A sprint plan for this should be ~300–500 words of structured bullet points, not 2,000+ words with architecture diagrams.

## Impact

- Claude Code turn consumption: planning alone burns 5–8 turns per sprint on a project that needs maybe 2 turns of planning
- Context pollution: the plan content is injected into every programmer agent's context, adding noise
- Sprint 018's single-document model and right-sizing were supposed to fix this; the improvement is measurable but insufficient

## Related

- Sprint 018: right-sized sprint planning (collapsed 3-document model into single sprint.md)
- `clasi/issues/done/e2e-test-plan-002-guessing-game.md` — observation #2