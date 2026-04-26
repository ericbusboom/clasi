---
id: "003"
title: "Update ticket template and SE instruction to document completes_todo field"
status: done
use-cases:
  - SUC-005
depends-on:
  - 009-001
github-issue: ""
todo: ""
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Update ticket template and SE instruction to document completes_todo field

## Description

The `completes_todo` field added by ticket 001 is only useful if engineers know it exists. This ticket adds the field to the ticket template so it appears in every newly created ticket file, and documents it in the SE instruction so engineers understand when and how to use it for multi-sprint TODO planning.

This ticket is independent of 002 (no runtime dependency) but is sequenced after 001 since there is no point documenting a field before it is implemented.

## Acceptance Criteria

- [x] `clasi/templates/ticket.md` YAML frontmatter block includes `completes_todo` with a comment explaining its purpose and default
- [x] The template comment makes clear that `true` is the default and that `false` suppresses TODO archival when the ticket is moved to done
- [x] `clasi/plugin/instructions/software-engineering.md` documents the `completes_todo` field in the ticket frontmatter reference section (or adds one if absent)
- [x] The instruction text explains: the field, its three forms (absent/scalar/map), the default, and when to use `false` (multi-sprint umbrella TODOs)
- [x] No other template or instruction files require changes

## Implementation Plan

### Approach

Two targeted edits — one to the ticket template, one to the SE instruction. No code changes. No test additions needed (doc changes are verified by reading).

### Files to Modify

**`clasi/templates/ticket.md`** — add `completes_todo` to the YAML frontmatter block. Suggested addition after the `todo` field:

```yaml
# completes_todo: Controls whether linked TODOs are archived when this ticket
# is moved to done. Default: true (archive when all referencing tickets are done).
# Set to false (scalar) to suppress archival for ALL linked TODOs on this ticket.
# Set to a mapping {filename.md: false} to suppress archival per TODO filename.
# Use false for tickets that partially address a multi-sprint umbrella TODO.
completes_todo: true
```

**`clasi/plugin/instructions/software-engineering.md`** — locate the ticket frontmatter reference section (or the section describing the `todo` field) and add documentation for `completes_todo` immediately after `todo`. The documentation should cover:
- What it controls
- Default value and behavior
- Scalar `false`: suppress for all linked TODOs
- Map form: per-filename control
- Guidance: use `false` for tickets referencing a long-lived multi-sprint TODO that should survive the sprint close

### Testing Plan

- No automated tests for documentation changes.
- Manual verification: read both files after editing to confirm the additions are present and accurate.
- Run `uv run pytest` to confirm no existing tests are broken (template change should not affect any test that constructs ticket files programmatically unless they assert exact template content).

### Verification Command

`uv run pytest -x`
