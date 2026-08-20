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
- 028-002
---

# E2E: capture every subject exchange and run artifact into a per-run directory

## Description

A failed E2E run currently has no replayable record: subject `claude -p`
output exists only in the tester's terminal, container-side session JSONLs
die with `docker rm`, and `validate.sh` results go to stdout only. From the
reliability review (00-review.md C14; 05-e2e-test-infra.md findings 2-3,
instrumentation plan items 1, 2, 6).

## Acceptance criteria

- New `tests/e2e/run.sh` wrapper that the tester uses instead of raw
  `docker exec claude -p`; each call writes
  `e2e-project/.e2e-runs/<run-id>/<NN>-<slug>/{prompt.txt, output.jsonl,
  exit-code, duration}` using `--output-format stream-json --verbose`.
- `start.sh` mints the run id and records `claude --version`,
  `clasi --version`, and the image digest into the run directory.
- `stop.sh`, before removing the container, saves `docker logs` and copies
  the subject's `~/.claude/projects` session directory into the run dir.
- `tests/e2e/AGENTS.md` mandates run.sh for all subject sessions.
- `validate.sh` output is tee'd into the run directory, and checks read host
  paths where possible so validation works after the container is gone.
