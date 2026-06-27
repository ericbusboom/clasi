---
id: "004"
title: "Update sprint-roadmap and plan-sprint skill docs with linkage instructions"
status: open
use-cases: [SUC-003]
depends-on: ["003"]
github-issue: ""
issue: ""
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Update sprint-roadmap and plan-sprint skill docs with linkage instructions

## Description

The `sprint-roadmap` and `plan-sprint` skill documents never instruct agents
to call the issue linkage tools. This ticket updates both source documents in
`clasi/plugin/` so that agents are directed to call `link_sprint_issues` at the
right lifecycle step.

Note: all edits target `clasi/plugin/` only. The `.claude/` copies are
installer-generated mirrors — do not edit them directly. After this sprint
merges, the installer regenerates the `.claude/` copies.

## Acceptance Criteria

- [ ] `clasi/plugin/skills/sprint-roadmap/SKILL.md` step 4 instructs calling `link_sprint_issues(sprint_id, [filenames])` for every issue claimed in the roadmap, replacing the old "Update TODOs: set sprint: NNN" instruction.
- [ ] `clasi/plugin/skills/plan-sprint/SKILL.md` (or the instruction source it delegates to) instructs calling `link_sprint_issues` explicitly during the planning-docs phase — not writing `issues:` manually via `write_artifact_frontmatter`.
- [ ] The instructions specify the correct tool signature: `link_sprint_issues(sprint_id, issue_filenames)`.
- [ ] No references to setting `todos:` frontmatter remain in these two files.

## Implementation Plan

### Approach

**B1 — `clasi/plugin/skills/sprint-roadmap/SKILL.md`**

Read the file first. Locate step 4 (currently "Update TODOs: For each TODO
claimed by a sprint, set `sprint: "NNN"` in the TODO's frontmatter").

Replace with an instruction to call `link_sprint_issues`:

```
4. **Link issues to sprint**: For each issue claimed by this sprint, call
   `link_sprint_issues(sprint_id, [filenames])`. This writes the `issues:`
   list in the sprint's frontmatter and updates each issue file's `sprint:`
   field. Do not write issue or sprint frontmatter manually.
```

**B2 — `clasi/plugin/skills/plan-sprint/SKILL.md`**

Read the file. It currently delegates to a schema instructions file. Determine
whether to extend the SKILL.md stub or the delegated source. Prefer extending
the stub if the delegated source is not clearly related to linkage. Add a note:

```
## Issue Linkage

During the planning-docs phase, call `link_sprint_issues(sprint_id,
issue_filenames)` to associate issues with the sprint. Do not write the
`issues:` field manually via `write_artifact_frontmatter`.
```

If the SKILL.md delegates entirely to an instruction file, add the linkage note
to that file instead.

### Files to Modify

- `clasi/plugin/skills/sprint-roadmap/SKILL.md` — replace step 4.
- `clasi/plugin/skills/plan-sprint/SKILL.md` — add linkage instruction (or
  update the delegated instruction source if the stub delegates entirely).

### Testing Plan

- No automated tests for doc changes. Verify by reading the updated files and
  confirming the instructions are clear and unambiguous.
- Run `pytest -q` to confirm no code regressions from doc-only changes.

### Documentation Updates

This ticket IS the documentation update. No code changes.
