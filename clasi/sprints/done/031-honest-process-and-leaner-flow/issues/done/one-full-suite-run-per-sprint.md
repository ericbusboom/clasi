---
status: done
type: task
tags:
- reliability-campaign
- phase-3
- speed
sprint: '031'
tickets:
- 031-008
---

# One full-suite run per sprint, owned by close_sprint

## Description

From docs/reviews/2026-08-reliability/06-process-flow.md finding 6. A
sprint currently runs the full test suite **three** times, while the docs
themselves assert that two is the total:

1. `schemas/se-process/instructions/execution.md` §5.2 tells the
   team-lead to run it before close.
2. The `sprint-review` skill's checklist independently re-runs it.
3. `close_sprint` runs it again internally as a precondition.

Measured cost in this repo: 9m30s to 19m41s per run. That is 20-60
minutes of a sprint's wall-clock spent re-running an identical suite
against an unchanged tree.

Observed during the 028-030 campaign: the team-lead ran the suite
manually and then passed `test_command="true"` to `close_sprint` to avoid
a second identical 20-minute run — a workaround that only works because
the operator knows the tree is unchanged, and which quietly weakens the
gate for anyone who does not.

## Acceptance criteria

- [ ] `close_sprint`'s internal run is the sprint's single full-suite
      gate. Delete execution.md §5.2's separate run.
- [ ] `sprint-review` reads results rather than re-running: it becomes
      "call `review_sprint_pre_close`, interpret the output."
- [ ] The orphaned `review_sprint_pre_close` / `review_sprint_post_close`
      MCP tools are either referenced by the skill that should call them
      or deleted — today no skill or agent doc mentions either.
- [ ] A "tests already passed for HEAD `<sha>`" marker (or equivalent)
      lets a deliberate re-run skip redundant work without the operator
      having to pass a fake test command. Note `close_sprint` gained a
      real `test_command="SKIP"` sentinel in sprint 030 — the marker
      should make even that unnecessary in the normal flow.
- [ ] The docs state the number of full-suite runs per sprint once, in
      one place, and it matches what the code does.
