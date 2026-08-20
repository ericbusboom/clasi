---
status: done
type: feature
tags:
- reliability-campaign
- phase-0
- e2e
- observability
sprint: 028
tickets:
- 028-006
---

# E2E: assemble a single run report per run

## Description

An E2E run currently "returns" nothing — evidence is scattered across the
tester's terminal, container logs, and `.clasi/log/`. From the reliability
review (05-e2e-test-infra.md instrumentation plan item 7).

New `tests/e2e/report.sh` (validate.sh stays a pure checker) assembling
`.e2e-runs/<run-id>/run-report.md` from:

- validate.sh output (tee'd by the run-capture issue)
- run.sh per-milestone durations and exit codes
- phase timings from the phase-transition history table
- mcp-calls.jsonl top-N slowest calls and all failures
- hooks.log deny count and reasons histogram
- dispatch inventory from `.clasi/log/NNN-*.md` frontmatter durations
- a scan of mcp-server.log for `input_value={}` validation errors (the
  empty-args bug signature)

## Acceptance criteria

- One command produces the report from a finished run's directory.
- The report is self-contained markdown a human can read top to bottom.
- Depends on: e2e-run-capture-and-artifact-collection,
  mcp-call-trace-with-durations, sprint-phase-transition-history,
  guard-decision-trail-and-deny-payload-capture.
