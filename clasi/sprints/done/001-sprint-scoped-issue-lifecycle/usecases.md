---
status: draft
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 001 Use Cases

## SUC-001: Issue file physically moves to done/ on completion

- **Actor**: Sprint executor / MCP tool caller
- **Preconditions**: An issue exists in `<sprint>/issues/<filename>` with `status: in-progress`.
- **Main Flow**:
  1. All tickets referencing the issue complete (`move_ticket_to_done` or explicit `move_issue_to_done` call).
  2. `Issue.move_to_done()` is called.
  3. System creates `<sprint>/issues/done/` if it does not exist.
  4. System renames the file from `<sprint>/issues/<filename>` to `<sprint>/issues/done/<filename>`.
  5. Frontmatter is updated: `status: done`.
- **Postconditions**: File exists at `<sprint>/issues/done/<filename>`. `issues/` top-level no longer contains the file.
- **Acceptance Criteria**:
  - [ ] `issue.path` reflects the new location after `move_to_done()`.
  - [ ] `issue.status == "done"`.
  - [ ] Calling `move_to_done()` a second time is a no-op (file stays in `done/`, no error).

## SUC-002: Sprint and project lookups include issues/done/

- **Actor**: Any agent or MCP tool querying sprint issues or resolving an issue by filename.
- **Preconditions**: One or more issues exist in `<sprint>/issues/done/`.
- **Main Flow**:
  1. Caller invokes `Sprint.list_issues()` or `Project.get_issue(filename)`.
  2. System scans both `<sprint>/issues/` and `<sprint>/issues/done/`.
  3. Results include issues from both directories.
- **Postconditions**: Done issues are visible to callers without knowing their sub-directory.
- **Acceptance Criteria**:
  - [ ] `Sprint.list_issues()` returns issues from both `issues/` and `issues/done/`.
  - [ ] `Project.get_issue(filename)` resolves filenames in `<sprint>/issues/done/`.
  - [ ] `Sprint.issues_done_dir` property returns `<sprint>/issues/done`.

## SUC-003: close_sprint handles legacy done-file layouts

- **Actor**: Sprint closer calling `close_sprint`.
- **Preconditions**: Sprint has issues in various legacy states: (a) done-tagged file still at `issues/` top-level, (b) done-tagged file in the pending pool with `sprint` frontmatter pointing at the closing sprint.
- **Main Flow**:
  1. `close_sprint` precondition pass walks `<sprint>/issues/` and `<sprint>/issues/done/`.
  2. For files at `issues/` top level with `status: done`: self-repair by calling `move_to_done()` which moves them to `issues/done/`.
  3. For files in the pending pool with `sprint == sprint_id` and `status: done`: self-repair by moving into `<sprint>/issues/done/` directly.
  4. Issues already in `issues/done/` pass cleanly with no action.
  5. Close proceeds if no unresolved in-progress issues remain.
- **Postconditions**: All done issues end up in `<sprint>/issues/done/`. Close succeeds or hard-fails only on truly unresolved in-progress issues.
- **Acceptance Criteria**:
  - [ ] Legacy top-level done file is migrated to `done/` by self-repair without error.
  - [ ] Pending-pool done-tagged issue for the sprint is relocated to `<sprint>/issues/done/`.
  - [ ] Issues already in `done/` pass cleanly.
  - [ ] Close hard-fails if an issue is still `in-progress` and not deferred.

## SUC-004: Planner splits a partial-scope issue

- **Actor**: Sprint planner discovering that only part of an issue's scope fits in the current sprint.
- **Preconditions**: An issue exists (in pending pool or sprint-scoped).
- **Main Flow**:
  1. Planner calls `split_issue(filename, new_filename, new_title, new_body)`.
  2. System resolves the original issue via `project.get_issue`.
  3. System creates a new file as a sibling of the original (same directory).
  4. New file gets frontmatter: `status` inherited if original is sprint-scoped in-progress, else `pending`; `split_from: <original-filename>`; `source` copied from original.
  5. Original file gets `split_into: [<new-filename>]` appended to frontmatter.
  6. If `updated_body` is provided, original body is rewritten.
- **Postconditions**: Two issue files exist with mutual cross-link frontmatter. No tickets are touched.
- **Acceptance Criteria**:
  - [ ] `split_issue` on a pending-pool issue creates a sibling in `.clasi/issues/`.
  - [ ] `split_issue` on a sprint-scoped issue creates a sibling in `<sprint>/issues/`.
  - [ ] New file has `split_from` pointing at original filename.
  - [ ] Original file has `split_into` list containing new filename.
  - [ ] `source` frontmatter is copied from original to new file.
  - [ ] `split_issue` returns `{original_path, new_path}`.

## SUC-005: Skill docs describe the sprint-scoped issue lifecycle

- **Actor**: Sprint planner or sprint closer reading skill documentation.
- **Preconditions**: Agent reads `issue`, `plan-sprint`, `create-tickets`, or `close-sprint` skill docs.
- **Main Flow**:
  1. `issue` SKILL.md explains when to use `split_issue` and how.
  2. `plan-sprint` SKILL.md instructs planner to call `split_issue` for partial-scope issues before creating tickets.
  3. `create-tickets` SKILL.md notes that `create_ticket(todo=...)` moves issues into `<sprint>/issues/` and they land in `<sprint>/issues/done/` automatically when tickets complete.
  4. `close-sprint` SKILL.md notes that close hard-fails if any `<sprint>/issues/*.md` (top-level) remains in-progress, and describes split/done options for resolution.
- **Postconditions**: Agents reading the skill docs understand the full issue lifecycle.
- **Acceptance Criteria**:
  - [ ] `issue` SKILL.md has a section on splitting.
  - [ ] `plan-sprint` SKILL.md mentions `split_issue` in the detail phase steps.
  - [ ] `create-tickets` SKILL.md explains the issue move-to-in-progress and auto-done behavior.
  - [ ] `close-sprint` SKILL.md describes the hard-fail condition for in-progress issues.
