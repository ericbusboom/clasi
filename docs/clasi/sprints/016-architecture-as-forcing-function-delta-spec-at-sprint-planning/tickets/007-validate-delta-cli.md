---
id: "016-007"
title: "CLI subcommand: clasi sprint validate-delta"
status: todo
use-cases: [SUC-003]
depends-on: ["016-002"]
---

# 016-007: CLI subcommand — clasi sprint validate-delta

## Description

Add `clasi sprint validate-delta <sprint-id>` as a new subcommand under the
existing `sprint` CLI group. This is the user-facing entry point for format
validation; it is also called by the PostToolUse hook and referenced by
the architecture-review skill.

## Acceptance Criteria

- [ ] `clasi sprint validate-delta <sprint-id>` exists as a CLI subcommand.
- [ ] Resolves the sprint directory via `Project.get_sprint(sprint_id)`.
- [ ] On valid delta:
  - Exit code 0.
  - Stdout reports item counts, e.g.:
    "ADDED Components: 2, MODIFIED Scenarios: 1" (or similar).
- [ ] On `DeltaParseError`:
  - Exit code 1.
  - Stderr (or stdout) reports: line number, rule name, and message.
  - Format: `Line N: [rule] message`.
- [ ] On missing `architecture-delta.md`:
  - Exit code 1.
  - Error message explains the file is missing and notes that
    validate-delta only applies to delta-format sprints (not old
    architecture-update.md sprints).
- [ ] `--help` for the subcommand is informative.
- [ ] All tests pass.

## Implementation Plan

### Approach

Add a `validate_delta_command` function in `clasi/cli.py` (or a new
`clasi/validate_delta_command.py` module). Wire into the `sprint` Click group.
The command reads the delta file and calls `clasi.delta.parse.parse()`.

### Files to Create/Modify

- `clasi/cli.py` (modify: add subcommand to `sprint` group)
- `clasi/validate_delta_command.py` (create if extracting into own module)
- `tests/unit/test_validate_delta_command.py` (create)

### Testing Plan

- Test with a valid delta: assert exit code 0, check stdout for item count.
- Test with an invalid delta (item outside section): assert exit code 1,
  check stderr for line number.
- Test with missing delta file: assert exit code 1, check error message.
- Test via Click's `CliRunner` for clean isolation.

### Documentation Updates

None — the `--help` text IS the documentation for this subcommand.
