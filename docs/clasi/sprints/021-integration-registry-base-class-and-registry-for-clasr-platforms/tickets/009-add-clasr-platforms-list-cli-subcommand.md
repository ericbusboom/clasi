---
id: "009"
title: "Add clasr platforms list CLI subcommand"
status: todo
use-cases: [SUC-009]
depends-on: ["008"]
github-issue: ""
todo: ""
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Add clasr platforms list CLI subcommand

## Description

Add a `platforms` subcommand group to `clasr/cli.py` with a `list` subcommand:

```
clasr platforms list
```

Iterates `sorted(INTEGRATION_REGISTRY.keys())` and prints one ID per line to stdout. Exit code 0. Example output with four platforms registered:

```
claude
codex
copilot
cursor
```

The `platforms` group is extensible for future subcommands (`clasr platforms info <id>`, `clasr platforms detect`, etc.) but only `list` is implemented in this sprint.

## Acceptance Criteria

- [ ] `clasr platforms list` prints registered platform IDs, one per line, sorted, to stdout.
- [ ] Exit code is 0.
- [ ] `clasr platforms` (no subcommand) prints help and exits 0.
- [ ] `clasr platforms list` output includes `cursor` after ticket 008 is done.
- [ ] `uv run pytest tests/clasr/test_cli.py` passes (updated for new subcommand).
- [ ] `uv run pytest` green.

## Implementation Plan

### Files to Modify

- `clasr/cli.py` — add `platforms` subparser group with `list` subcommand.

### Testing Plan

- Add test to `tests/clasr/test_cli.py` asserting `clasr platforms list` output.
- `uv run pytest tests/clasr/test_cli.py` — passes.
- `uv run pytest` — full suite green.

### Documentation Updates

Update `clasr/instructions.md` to document the new `platforms list` subcommand.
