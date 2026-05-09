---
id: "016-012"
title: "Integration test: delta authoring, validate, and archive as historical record"
status: todo
use-cases: [SUC-001, SUC-002, SUC-003, SUC-004]
depends-on: ["016-007", "016-008"]
---

# 016-012: Integration test — delta authoring, validate, and archive as historical record

## Description

Write an end-to-end integration test that exercises the full delta pipeline
without a merge step: write a valid delta, validate it via the CLI subcommand,
confirm the hook fires correctly, and verify the delta file survives into the
done/ directory (as the historical record) when the sprint is closed.

The test does NOT call `Sprint.archive()` merge logic — there is no merge.
The source-of-truth docs (`docs/design/specification.md`,
`docs/design/usecases.md`) are project-init artifacts that do not change at
sprint close. The delta accumulates as history under `sprints/done/<id>/`.

## Acceptance Criteria

- [ ] `tests/integration/test_delta_pipeline.py` exists.
- [ ] Happy-path scenario:
  1. Creates a temporary project directory with a sprint directory containing
     a valid `architecture-delta.md` (at least one ADDED Component and one
     MODIFIED Scenario with prose body).
  2. Runs `clasi sprint validate-delta <id>` via Click's `CliRunner`.
     Asserts exit code 0 and stdout reports item counts.
  3. Simulates the PostToolUse hook firing on the same file. Asserts hook
     output contains "OK — N items parsed."
  4. Verifies no source-of-truth docs are written or modified (the delta is
     planning-time-only; it is the historical record, not a merge input).
- [ ] Invalid delta scenario:
  1. Creates a temporary project directory with an invalid `architecture-delta.md`
     (item heading outside any section).
  2. Runs `clasi sprint validate-delta <id>`. Asserts exit code 1 and error
     message contains the line number.
  3. Simulates PostToolUse hook firing. Asserts hook output contains "ERROR".
- [ ] All tests pass.

## Implementation Plan

### Approach

Use `pytest` with `tmp_path` fixtures. For the CLI subcommand, use Click's
`CliRunner` to avoid subprocess overhead. For the hook, call the handler
function directly with a synthetic event dict.

### Files to Create/Modify

- `tests/integration/test_delta_pipeline.py` (create)

### Testing Plan

The tests ARE the deliverable. Run with
`uv run pytest tests/integration/test_delta_pipeline.py`.

### Documentation Updates

None.
