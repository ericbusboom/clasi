---
status: done
sprint: '015'
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 015 Use Cases

## SUC-001: Single canonical artifact root

- **Actor**: Developer or operator running `clasi install` or `clasi init` on a target project.
- **Preconditions**: CLASI is installed and the target project does not yet have a `.clasi/`
  directory.
- **Main Flow**:
  1. Operator runs `clasi install` (or `clasi init`) against the target project.
  2. CLASI creates `.clasi/` at the project root and populates it with the artifact
     subdirectory layout (`sprints/`, `issues/`, `architecture/`, `log/`, `reflections/`).
  3. CLASI writes `.clasi/clasi-version` with the installed version string.
  4. Platform-specific rule files are rendered with paths referencing `.clasi/` (not `docs/clasi/`).
  5. All CLASI CLI subcommands, MCP tools, and hook handlers resolve artifact paths
     through `Project.clasi_dir` → `.clasi/`.
  6. There is no `docs/clasi/` directory created.
- **Postconditions**:
  - `.clasi/` exists and is the sole root for CLASI process artifacts.
  - No `docs/clasi/` directory is present.
  - `clasi project-status` reports the correct `.clasi/` path.
  - `grep -rn "docs/clasi" clasi/ tests/ .claude/ .github/` returns zero hits
    (historical done-sprint archives are exempt).
- **Acceptance Criteria**:
  - [ ] `clasi install` on a fresh target creates `.clasi/` with the correct layout.
  - [ ] `clasi init` creates `.clasi/issues/` and no `in-progress/` or `done/` subdirs at root level.
  - [ ] `.clasi/clasi-version` is written once per install, regardless of how many platforms are selected.
  - [ ] All platform rule files reference `.clasi/**` and `.clasi/issues/**` globs.
  - [ ] CLI subcommands use `plan-to-issue` and `--issues-dir`; skill is `/issue`.
  - [ ] MCP tools exposed as `list_issues` and `move_issue_to_done`.
  - [ ] Ticket frontmatter uses `issue:` and `completes_issue:` fields.
  - [ ] Ticket status starts as `open` (not `todo`).
  - [ ] Full test suite passes with no `docs/clasi` path references in source or fixtures.

---

## SUC-002: Sprint-scoped issue lifecycle

- **Actor**: Team-lead running a sprint that claims one or more issues.
- **Preconditions**: Sprint 015 is landed; `.clasi/issues/<filename>.md` exists for at least one pending issue.
- **Main Flow**:
  1. Team-lead creates a ticket for sprint N that references an issue file.
  2. The MCP tool calls `Issue.move_to_in_progress(sprint_id, ticket_id)`.
  3. The issue file moves from `.clasi/issues/<filename>.md` to
     `.clasi/sprints/<sprint-N>/issues/<filename>.md`.
  4. The issue's frontmatter is updated: `status: in-progress`, `sprint: N`, `ticket: NNN`.
  5. Work proceeds. On ticket completion, `Issue.move_to_done` sets `status: done` in
     frontmatter only — no directory move.
  6. Team-lead closes the sprint via `close_sprint`.
  7. The sprint directory (including its `issues/` subdir) moves to
     `.clasi/sprints/done/<sprint-N>/`.
  8. The issue file is now at `.clasi/sprints/done/<sprint-N>/issues/<filename>.md`.
- **Postconditions**:
  - The issue file has traveled with the sprint into `done/` — co-located with its tickets
    and architecture update.
  - There is no `.clasi/issues/in-progress/` or `.clasi/issues/done/` directory.
  - `Project.list_issues()` returns only the union of pending issues
    (`.clasi/issues/*.md`) and in-progress sprint issues (sprint `issues/*.md` where
    `status != done`).
- **Acceptance Criteria**:
  - [ ] After claiming, the issue file is at `<sprint>/issues/<filename>` (not in a
    global `in-progress/` dir).
  - [ ] After `move_to_done`, the file remains at `<sprint>/issues/<filename>` with
    `status: done` in frontmatter (no move).
  - [ ] After `close_sprint`, the issue file is at
    `.clasi/sprints/done/<sprint>/issues/<filename>`.
  - [ ] No `.clasi/issues/in-progress/` or `.clasi/issues/done/` directory is created
    by `clasi init`, `clasi install`, or any issue lifecycle call.
  - [ ] `Project.list_issues()` returns pending issues plus in-progress sprint issues,
    but not done issues.
  - [ ] `Sprint.issues_dir` and `Sprint.list_issues()` work correctly.
  - [ ] Integration test passes: install → create issue → claim → close sprint → verify
    paths at each stage.
