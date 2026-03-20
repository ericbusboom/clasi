---
status: done
sprint: "024"
---

# E2E Guessing Game Test

Build end-to-end test infrastructure that validates the entire CLASI SE
process by having it build a real application from a spec. A test
harness sets up a temporary project, initializes CLASI, places a
guessing-game spec, dispatches a team-lead subagent to implement it
across 4 sprints, then verifies all artifacts are correct.

Implemented in sprint 024 (tickets 001, 002, 003):
- `tests/e2e/run_e2e.py` -- test harness
- `tests/e2e/verify.py` -- verification script
- `tests/e2e/README.md` -- documentation
