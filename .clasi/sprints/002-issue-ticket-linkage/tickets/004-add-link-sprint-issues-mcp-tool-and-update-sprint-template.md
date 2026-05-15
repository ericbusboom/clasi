---
id: '004'
title: Add link_sprint_issues MCP tool and update sprint template
status: done
use-cases:
- SUC-005
depends-on: []
github-issue: ''
issue:
- sprint-todo-bidirectional-links.md
completes_issue:
  sprint-todo-bidirectional-links.md: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Add link_sprint_issues MCP tool and update sprint template

## Description

Add a `link_sprint_issues(sprint_id, issue_filenames)` MCP tool that
establishes bidirectional sprint↔issue links during the roadmap phase: the
`sprint.md` frontmatter gains (or appends to) an `issues:` list, and each
referenced issue gains a `sprint:` back-reference.

Also add `issues: []` to the sprint.md YAML template so all new sprints
created by `create_sprint` or `insert_sprint` include the field pre-populated.

This formalizes the convention that was manually applied by the sprint-planner
in sprint 002's own roadmap phase, making it a first-class tool call.

## Acceptance Criteria

- [x] `link_sprint_issues(sprint_id: str, issue_filenames: list[str])` is a
      new `@server.tool()` in `clasi/tools/artifact_tools.py`, placed near
      `create_sprint` and `insert_sprint`.
- [x] For each filename in `issue_filenames`:
      - If the issue cannot be found via `project.get_issue`, adds to
        `not_found` list and continues.
      - If the issue's `sprint:` frontmatter already equals `sprint_id`, adds
        to `already_linked` list and continues.
      - Otherwise writes `sprint: <sprint_id>` to the issue's frontmatter and
        adds to `linked` list.
- [x] Ensures the sprint's `sprint.md` frontmatter has an `issues:` list
      that includes all successfully linked filenames (no duplicates).
- [x] Returns JSON `{sprint_id, linked, already_linked, not_found}`.
- [x] Idempotent: calling twice with the same arguments produces the same
      result; no duplicate entries in either direction.
- [x] `clasi/templates/sprint.md` gains `issues: []` in the YAML frontmatter
      block, so new sprints include the field.
- [x] `create_sprint` and `insert_sprint` require no code changes — they
      benefit automatically from the template update.

## Implementation Plan

### Approach

New `@server.tool()` placed in `artifact_tools.py` after `insert_sprint`.

For the issue back-ref write: `issue._artifact.update_frontmatter(sprint=sprint_id)`.

For the sprint `issues:` write: read current `sprint.sprint_doc.frontmatter.get("issues", [])`,
merge with newly linked filenames (skip duplicates), write back via
`sprint.sprint_doc._artifact.update_frontmatter(issues=merged_list)` — or
via the `Artifact` API directly on `sprint.sprint_md`.

Template update: add `issues: []` to the YAML block in
`clasi/templates/sprint.md` between `use-cases: []` and the closing `---`.

### Files to modify

- `clasi/tools/artifact_tools.py` — add `link_sprint_issues` tool.
- `clasi/templates/sprint.md` — add `issues: []` field.

### Testing plan

- **Existing tests to run**: `uv run pytest tests/unit/` (full suite — template
  change may affect snapshot tests).
- **New tests to write** (in `tests/unit/test_issue_tools.py` or a new file):
  - `link_sprint_issues` with two valid issue filenames → both get
    `sprint: <id>`, sprint.md `issues:` contains both filenames.
  - Idempotent: calling again with same filenames → all in `already_linked`,
    no duplicate entries in `issues:`.
  - Unknown filename → in `not_found`, does not error.
  - Mix: one valid, one already linked, one not found → correct categorization.
  - Sprint template test: `create_sprint` produces a `sprint.md` with
    `issues: []` in frontmatter.
- **Verification command**: `uv run pytest`

### Documentation updates

- This ticket does not update the `sprint-roadmap` skill guidance (see Open
  Questions in `architecture-update.md`). If the team-lead decides that update
  belongs in sprint 002, it can be added here or as a follow-on ticket.
