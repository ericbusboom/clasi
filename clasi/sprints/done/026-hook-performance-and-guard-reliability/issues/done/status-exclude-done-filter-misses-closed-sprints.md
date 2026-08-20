---
status: done
sprint: '026'
tickets:
- 026-007
---

# Status sweep's exclude_done filter misses status:'closed' sprints — archived sprints re-evaluated on every prompt

## Description

Found during sprint 026 ticket 003 (status-inject performance). After the
ticket's memoization/trim work, `clasi hook status-inject` measures a
median ~0.78 s in this repo — above the sprint's <200 ms success
criterion. The dominant remaining cost is pre-existing and out of ticket
003's scope: `_build_sprints_block`'s `exclude_done` filter only matches
`sprint.status == "done"`, but the six archived sprints under
`clasi/sprints/done/` (020-025) carry frontmatter `status: closed`. They
leak past the filter and are fully re-evaluated on every status-inject
invocation: captured output confirms 7 sprints evaluated instead of the 1
truly active one — 137 `get_sprint()` calls and 1,816 `read_frontmatter()`
calls per prompt.

Full measurement detail is recorded in ticket 003's Measurement Notes
(clasi/sprints/026-hook-performance-and-guard-reliability/tickets/done/003-*.md).

## Cause

`exclude_done` compares against the literal status string "done";
archived sprints declare "closed". The filter predates the closed status
convention (the same declared-vs-recognized drift shows up in
`detect_inconsistencies`, which flags these sprints' status as
unrecognized).

## Proposed fix

Widen the exclusion to terminal states ("done" AND "closed"), or better,
compare against the sprint machine's computed terminal state instead of a
string literal. Also consider skipping sprints under the `done/`
directory entirely — their location already declares them archived.

## Verification

- Status-inject against this repo's fixture layout evaluates only
  non-archived sprints (get_sprint/read_frontmatter call-count assertion).
- `time clasi hook status-inject < captured-payload.json` under 200 ms in
  this repo (the sprint 026 success criterion this issue completes).
- Archived-sprint entries absent from (or inert in) the injected YAML,
  unchanged `clasi status` CLI behavior.

## Related

- hook-overhead-status-inject-dead-hooks-and-logging.md (sprint 026) —
  parent investigation; ticket 003 delivered the memoization/trim work.
