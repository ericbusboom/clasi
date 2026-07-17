---
id: '006'
title: Update bootstrap-design, architecture-authoring, create-tickets skills and
  packaged template
status: open
use-cases: [SUC-001, SUC-003]
depends-on: ['003', '004', '005']
github-issue: ''
issue: co-locate-design-docs-as-design-md-in-source-replacing-readme.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Update bootstrap-design, architecture-authoring, create-tickets skills and packaged template

## Description

Update every skill/template that describes the old central-doc +
paired-README model in prose, so the next agent that reads them gets
correct guidance:

- **`bootstrap-design` skill**: "Identify Subsystems" / "Derive
  Filenames and Write via the Design Store" sections currently describe
  `design_doc_slug`, `write_readme`, README-linking frontmatter. Update
  to describe writing `<subsystem>/DESIGN.md` only, via the retargeted
  `write_design_doc` (ticket 002), no README step. Update the "Output"
  section's file list.
- **`architecture-authoring` skill, Mode 2a**: "Identify affected
  canonical docs" currently names `docs/design/` filenames as the
  output of that judgment call (e.g. `["design.md",
  "clasi-tools.md"]`). Update the worked example to name a mix of
  `design.md` and `<subsystem>/DESIGN.md` paths, and add a short note
  (cross-referencing this sprint's own Design Rationale) that a sprint
  relocating a doc's *location* should not run it through the overlay
  — only content-only changes to a stable-location doc are
  overlay-appropriate; a relocation is a direct ticket-scoped file
  operation. Also update "Revising in place" if it names a
  `docs/design/`-specific path assumption.
- **`create-tickets` skill**: check for any `docs/design/`- or
  README-specific prose (a light pass — this skill is mostly
  format-agnostic already; confirm no worked example embeds the old
  path shape).
- **Packaged template** (`src/clasi/design/templates/subsystem-design.md`):
  remove the frontmatter placeholder block (`source_paths`,
  `readme_path` — lines 14-18 of the current file) entirely, since
  `DESIGN.md` requires no frontmatter. Keep the body content and
  section-guidance HTML comments as-is (the template's own opening
  comment already says "Place one copy of this file in each subsystem's
  subdirectory (e.g. DESIGN.md)" — it already anticipated this
  direction; only the frontmatter block needs to change).
- **`clasi.design.store.subsystem_template()`**: no code change needed
  (still reads the packaged file via `importlib.resources`) — verify
  its docstring's description of "placeholder YAML frontmatter" is
  updated to match the template's new no-frontmatter shape.

## Acceptance Criteria

- [ ] `bootstrap-design` skill's Process section describes only
      `DESIGN.md` writing, no `write_readme` step, no slug derivation.
- [ ] `architecture-authoring` skill's Mode 2a worked example names
      both `design.md`-style and co-located `<subsystem>/DESIGN.md`-style
      targets, and states the relocation-vs-content-change distinction.
- [ ] Packaged `subsystem-design.md` template has no frontmatter block;
      `bootstrap-design`'s Step 3 prose no longer references
      "replace the placeholders with the subsystem's real
      `source_paths`/`readme_path` values."
- [ ] `grep -r "readme_path\|design_doc_slug\|write_readme" src/clasi/plugin/skills/`
      returns no matches after this ticket.

## Testing

- **Existing tests to run**: any test that snapshot-checks skill/
  template file content (grep for tests referencing
  `subsystem-design.md` or skill file paths).
- **New tests to write**: none typically required for prose-only
  changes; if a test asserts the template has no frontmatter delimiter,
  add it.
- **Verification command**: `uv run pytest` (full suite, since this
  ticket touches packaged data that installed-package tests may read)
