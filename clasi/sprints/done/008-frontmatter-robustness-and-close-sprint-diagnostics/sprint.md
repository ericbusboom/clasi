---
id: 008
title: Frontmatter robustness and close_sprint diagnostics
status: done
branch: sprint/008-frontmatter-robustness-and-close-sprint-diagnostics
use-cases:
- SUC-001
- SUC-002
issues:
- frontmatter-silent-on-malformed-fence.md
- close-sprint-not-found-error-misleading.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 008: Frontmatter robustness and close_sprint diagnostics

## Goals

Fix two paired defects discovered during sprint 007 debugging that cause
misleading "Sprint not found" errors when a YAML frontmatter fence is corrupted.

1. `read_frontmatter` silently returns empty fields when the opening `---` fence
   is corrupted (e.g. `pwd---`). No warning or exception is raised, so callers
   operate on empty values and produce confusing downstream errors.
2. `_close_sprint_full`'s precondition catches any `ValueError` from
   `project.get_sprint` and reports "Sprint not found — create or restore the
   directory," even when the directory and `sprint.md` are present. The recovery
   instruction misdirects the operator.

## Problem

A single corrupted byte in the frontmatter fence of `sprint.md` renders a sprint
invisible to all callers that key off frontmatter fields (`get_sprint`,
`list_sprints`, etc.). The failure cascades silently until `close_sprint`
surfaces a misleading "not found" message with wrong recovery guidance.

## Solution

Fix the parser first (issue 1), then tighten the error discrimination downstream
(issue 2):

- Raise a typed `MalformedFrontmatterError` from `read_frontmatter` when a file
  has content but no recognizable opening fence. Callers that already catch
  frontmatter errors continue to work; callers that do not get a clear stack
  trace identifying the file.
- Update `project.get_sprint` (or `_close_sprint_full`'s precondition) to
  distinguish three failure sub-cases and produce specific, actionable messages.

## Success Criteria

- `read_frontmatter` emits a `WARNING` (or raises `MalformedFrontmatterError`)
  when a file has content but no recognizable opening fence.
- `close_sprint` names the file and parse failure — not "create the sprint
  directory" — when `sprint.md` is malformed.
- The recovery instruction is actionable for the actual fault.
- All existing tests continue to pass.

## Scope

### In Scope

- `clasi/frontmatter.py` — raise `MalformedFrontmatterError` on corrupted fence
- `clasi/project.py` — discriminate `get_sprint` failure sub-cases
- `clasi/tools/artifact_tools.py` — update `_close_sprint_full` precondition to
  surface specific error messages
- Unit tests for the new exception and the updated error paths

### Out of Scope

- CLI changes
- New MCP tool registration
- New modules
- Startup diagnostic scanner (noted in issue 1 as a possible future addition)

## Test Strategy

Unit tests covering:
- `read_frontmatter` raises `MalformedFrontmatterError` for a file with content
  but a corrupted first line (e.g. `pwd---`)
- `read_frontmatter` still returns `{}` for a file that genuinely has no
  frontmatter (no `---` at all — unchanged behaviour)
- `project.get_sprint` raises a typed exception with a message naming the file
  when frontmatter is malformed
- `close_sprint` precondition produces the correct sub-case error message when
  the sprint directory is present but frontmatter is corrupt

## Architecture Notes

- `MalformedFrontmatterError` is a new typed exception defined in
  `clasi/frontmatter.py`. It is a subclass of `ValueError` for backwards
  compatibility with callers that already catch `ValueError`.
- `project.get_sprint` raises typed exceptions distinguishing:
  1. No matching directory (current message is correct)
  2. Directory present, frontmatter missing or unparseable
  3. Directory present, frontmatter parsed, id mismatch or absent
- No circular imports: `frontmatter.py` has no project-level dependencies.

## GitHub Issues

(GitHub issues linked to this sprint's tickets. Format: `owner/repo#N`.)

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [ ] Sprint planning documents are complete (sprint.md, use cases, architecture)
- [ ] Architecture review passed
- [ ] Stakeholder has approved the sprint plan

## Tickets

| # | Title | Depends On |
|---|-------|------------|
| 001 | Raise MalformedFrontmatterError on corrupted frontmatter fence | — |
| 002 | Discriminate close_sprint precondition failure sub-cases | 001 |

Tickets execute serially in the order listed.
