---
name: plan-sprint
description: Creates a new sprint from a stakeholder conversation — sprint document, branch, architecture update, review, and ticket creation
---

# Plan Sprint Skill

This skill creates a new sprint: capture goals, create the sprint document,
set up the branch, get architecture review, get stakeholder approval, and
create tickets.

## Agent Used

**project-manager** (orchestrates), **architecture-reviewer** (reviews plan),
**technical-lead** (creates tickets)

## Inputs

- Stakeholder conversation describing the work to be done
- `docs/plans/brief.md` or `docs/plans/overview.md` (must exist)
- `docs/plans/usecases.md` (must exist, or overview covers use cases)

## Critical Rule

**DO NOT create tickets** during steps 1–10 of this process. Tickets are
only created in step 12, after the sprint has advanced to the `ticketing`
phase. The `create_ticket` MCP tool will reject attempts to create tickets
before that phase. Follow the phases in order.

## Process

1. **Determine sprint number**: Check `docs/plans/sprints/` and
   `docs/plans/sprints/done/` for existing sprints. The new sprint gets the
   next sequential number (NNN format: 001, 002, ...).

2. **Mine the TODO directory**: Scan `docs/plans/todo/` for ideas relevant
   to the upcoming sprint. Discuss relevant TODOs with the stakeholder and
   incorporate selected items into the sprint scope. After the sprint
   branch is created (step 4), move consumed TODO files to
   `docs/plans/todo/done/` and commit the moves on the sprint branch.

3. **Create sprint directory**: Use the `create_sprint` MCP tool. This
   creates the directory structure and registers the sprint in the state
   database at phase `planning-docs`:
   - `sprint.md` — Sprint goals, scope, architecture notes, ticket list.
     Frontmatter: id, title, status: planning, branch, use-cases.
   - `usecases.md` — Sprint-level use cases (SUC-NNN).
   - `architecture.md` — Architecture document (copied from previous sprint's
     version, or created from template if none exists). The architect updates
     this to reflect the target end-of-sprint state and fills in the
     `## Sprint Changes` section.
   - `tickets/` — Empty directory for tickets (with `done/` subdirectory).

4. **Create sprint branch**: Run `git checkout -b sprint/NNN-slug` from main.

5. **Advance to architecture-review**: Call `advance_sprint_phase` to move
   from `planning-docs` to `architecture-review`.

6. **Architecture review**: Delegate to the architecture-reviewer agent.
   The reviewer reads the sprint plan, architecture document, and relevant
   existing code, then produces a review (APPROVE / APPROVE WITH CHANGES / REVISE).
   - If REVISE: update the sprint document and re-review.
   - If APPROVE WITH CHANGES: note the changes for ticket creation.
   - Call `record_gate_result` with gate `architecture_review` and result
     `passed` or `failed`.

7. **Advance to stakeholder-review**: If architecture review passed, call
   `advance_sprint_phase` to move to `stakeholder-review`.

8. **Breakpoint (conditional)**: Check the sprint's `architecture.md`
   for a `## Open Questions` section.
   - If open questions **exist**: skip this breakpoint and proceed directly
     to step 9 (which resolves them interactively via `AskUserQuestion`).
   - If **no open questions** exist (section is empty or absent): present
     an `AskUserQuestion` to confirm continuation:
     - "Continue to stakeholder review" (recommended)
     - "Review architecture feedback first"

     If the stakeholder chooses to review, present the architecture review
     findings and stop. Otherwise proceed.

9. **Resolve open questions**: Before presenting to the stakeholder, check
   the sprint's `architecture.md` for a `## Open Questions` section. If
   open questions exist:
   - Parse each numbered question into a separate `AskUserQuestion` call.
   - For each question, provide 2–4 concrete options where possible (infer
     reasonable choices from the architecture context). Include a brief
     description for each option explaining its trade-offs.
   - After all questions are answered, replace the `## Open Questions`
     section in the architecture document with a `## Decisions` section
     listing each question and the stakeholder's chosen answer.
   - Update any affected parts of the sprint plan or architecture to
     reflect the decisions (e.g. adjust scope, add/remove components).

10. **Stakeholder review gate**: Present the sprint plan and architecture
    review to the stakeholder. Use `AskUserQuestion`:
    - "Approve sprint plan" (recommended)
    - "Request changes"

    If the stakeholder requests changes, revise and re-present. Only proceed
    when approved.
    - Call `record_gate_result` with gate `stakeholder_approval` and result
      `passed` or `failed`.

11. **Advance to ticketing**: If stakeholder approved, call
    `advance_sprint_phase` to move to `ticketing`.

12. **Create tickets**: Delegate to the technical-lead to create tickets
    for this sprint. Tickets are created in the sprint's `tickets/` directory
    with per-sprint numbering (001, 002, ...). Update the sprint document's
    Tickets section with the list of created tickets.

13. **Acquire execution lock and advance to executing**: Call
    `acquire_execution_lock` to claim the lock for this sprint, then call
    `advance_sprint_phase` to move to `executing`. Only one sprint can hold
    the execution lock at a time.

14. **Set sprint status**: Update the sprint document status to `active`.

15. **Confirm before execution**: Present the list of tickets to the
    stakeholder. Use `AskUserQuestion`:
    - "Start executing tickets" (recommended)
    - "Review tickets first"

    If the stakeholder chooses to review, list the tickets with their
    descriptions and stop. Otherwise proceed to execute the first ticket.

    **Do NOT ask again between individual tickets** — once execution starts,
    tickets proceed without interruption until all are done.

## Output

- Sprint directory `docs/plans/sprints/NNN-slug/` with planning documents (sprint.md, usecases.md, architecture.md)
- Sprint `sprint.md` status set to `active`
- Sprint branch `sprint/NNN-slug` created
- Sprint phase advanced to `executing` in the state database
- Execution lock acquired for this sprint
- Tickets in the sprint's `tickets/` directory ready for execution
