---
status: pending
---

# create_ticket auto-links ALL sprint issues to every ticket (multi-issue sprints)

## Description

When a sprint is linked to more than one issue, every ticket created without an
explicit `issue=` parameter is born referencing **all** of the sprint's issues —
including ones it has nothing to do with. The `issue:` frontmatter and the
issues' `tickets:` backlinks both end up wrong.

Observed while ticketing sprint 019, which is linked to two unrelated issues
(`enforcement-guards-fail-open-...` and
`remove-leftover-architecture-update-018-transition-artifact`). Tickets 002-006
concern only the enforcement work, but were created carrying a ref to the
stray-file issue as well, and that issue's `tickets:` backlink accumulated them.

## Cause

`src/clasi/tools/artifact_tools.py:586-589`, in `create_ticket`:

```python
# Auto-link to sprint issues when no explicit issue parameter given
if issue is None:
    sprint_issues = (
        sprint.sprint_doc.frontmatter.get("issues") ...
```

This is a deliberate convenience — auto-link a ticket to the sprint's issue —
and it is correct for the common single-issue sprint. It degrades badly for a
multi-issue sprint: "the sprint's issues" is not a sensible default for "this
ticket's issue" once there is more than one.

**NOT a bug in `add_issue_ref`.** A sprint-planner dispatch initially reported
this as `add_issue_ref` "cross-contaminating tickets ... bidirectional update
logic". That diagnosis is wrong and should not be propagated. `add_issue_ref`
(`artifact_tools.py:625`) was read end-to-end: it appends only the
`issue_filename` it is passed, handles absent/string/list correctly, and is
idempotent in each case. It has no mechanism to write issue B into a ticket
while being called for issue A. The refs were already there at creation;
`add_issue_ref` simply didn't remove the extra one.

## Proposed fix

Pick one:

1. **Don't auto-link when the sprint has multiple issues.** Auto-link only in
   the unambiguous single-issue case; otherwise leave `issue:` empty and let the
   caller set it. Least surprising.
2. **Require an explicit `issue=`** when the sprint has >1 issue (error if
   omitted), so the ambiguity is surfaced rather than guessed.
3. Keep current behavior but document it loudly in the `create_ticket`
   docstring and the create-tickets skill, so planners pass `issue=` per ticket.

Option 1 or 2 preferred — a default that is silently wrong is the failure mode
this project is currently spending a whole sprint fixing.

## Verification

- Create a sprint linked to two issues; create a ticket with no `issue=` param.
- Assert the ticket's `issue:` frontmatter is empty (option 1) or the call
  errors (option 2) — not "both issues".
- Assert neither issue's `tickets:` backlink gained the ticket.
- Regression: a single-issue sprint still auto-links as before.

## Related

- Found during sprint 019 ticketing. Sprint 019's ticket frontmatter was
  hand-corrected by the planner, so the sprint itself is fine; this is about the
  tool's default behavior for future multi-issue sprints.
