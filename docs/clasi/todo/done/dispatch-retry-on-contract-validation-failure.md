---
status: done
sprint: 029
tickets:
- 029-001
---

# Retry or Reject When Subagent Return Fails Contract Validation

## Problem

When a subagent returns prose instead of the JSON format required
by its contract, the dispatch tool logs "status: error" and passes
the prose through to the caller. The contract validation catches
the problem but doesn't enforce it — the work proceeds as if
nothing went wrong.

In ticket 028-007, the code-monkey returned a prose summary instead
of the structured JSON its contract requires. The dispatch tool
returned `"No valid JSON found in agent result text"` in the
validations field, but the caller (team-lead) accepted it and
moved the ticket to done anyway.

## Expected Behavior

When contract validation fails on the return value:

1. The dispatch tool should retry the subagent with an additional
   prompt: "Your response did not include valid JSON matching the
   contract schema. Please return your result as JSON: {schema}".
   One retry, max.

2. If the retry also fails validation, return a clear error to the
   caller with `"fatal": true` so the caller knows the dispatch
   did not complete successfully.

3. The caller (team-lead or sprint-executor) should NOT mark the
   ticket as done when the dispatch returned a validation error.

## Implementation

In `Agent.dispatch()` (clasi/agent.py), after step 5 (VALIDATE):
- If validation fails and the error is "No valid JSON found",
  retry query() with an appended prompt asking for JSON.
- If retry also fails, return with `"fatal": true`.

Also: the code-monkey's agent.md and contract need to be more
explicit about the required return format. Include the JSON schema
in the dispatch template so the agent sees it.
