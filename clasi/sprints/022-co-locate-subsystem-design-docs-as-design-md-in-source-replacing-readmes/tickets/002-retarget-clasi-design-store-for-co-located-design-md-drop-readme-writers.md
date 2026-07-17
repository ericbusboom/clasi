---
id: '002'
title: Retarget clasi.design.store for co-located DESIGN.md, drop README writers
status: open
use-cases: [SUC-001]
depends-on: ['001']
github-issue: ''
issue: co-locate-design-docs-as-design-md-in-source-replacing-readme.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Retarget clasi.design.store for co-located DESIGN.md, drop README writers

## Description

`src/clasi/design/store.py` currently writes/reads two files per
subsystem (`docs/design/<slug>.md` + `<subsystem>/README.md`) with
cross-linking frontmatter (`source_paths`, `readme_path` on the design
doc; `subsystem`, `description`, `design_doc_path` on the README).
Retarget to write/read a single `<subsystem_path>/DESIGN.md` with no
required frontmatter:

- `write_design_doc(project, subsystem_path, content, *,
  extra_frontmatter=None)`: writes to
  `design_doc_path_for(subsystem_path)` (ticket 001). Do not set
  `source_paths`/`readme_path` automatically — there is nothing to
  backlink. If `extra_frontmatter` is given, write it as-is (optional
  metadata is still permitted; it's just no longer required or
  auto-populated).
- `read_design_doc(project, subsystem_path)`: reads from the same path.
- Remove `write_readme`, `read_readme` entirely.
- Remove `write_system_doc`'s `readme_path: None` frontmatter field
  (the system doc never had a README pairing; that field was always a
  vestige of the general write path, not meaningful for the system
  doc). Keep `write_system_doc` writing to `project.design_dir /
  system_doc_name()` — unchanged location.
- `DesignDocSet` (the dataclass returned by `read_doc_set`): remove the
  `readmes: dict[Path, Artifact]` field. `subsystem_docs` now maps
  subsystem path -> `DESIGN.md` `Artifact`.
- `subsystem_template()`: unchanged mechanism (`importlib.resources`
  packaged read) — the template file's own content changes in ticket
  006, not here.

## Acceptance Criteria

- [ ] `write_design_doc`/`read_design_doc` operate on
      `<subsystem_path>/DESIGN.md`.
- [ ] No required frontmatter is written by `write_design_doc` — a
      `DESIGN.md` with a bare markdown body (no `---` block) is a valid
      write/read round-trip.
- [ ] `write_readme`/`read_readme` are removed; no remaining caller
      imports them (grep confirms zero references outside this
      ticket's own diff).
- [ ] `DesignDocSet.readmes` is removed; `read_doc_set` no longer
      enumerates README paths.
- [ ] Module docstring's "Frontmatter contract" section rewritten to
      state DESIGN.md requires no frontmatter (matching sprint.md's
      Design Rationale).

## Testing

- **Existing tests to run**: `tests/design/test_store.py` (or
  equivalent).
- **New tests to write**: `write_design_doc`/`read_design_doc`
  round-trip with no frontmatter; `write_readme` removal verified by a
  test asserting `AttributeError`/`ImportError` is no longer applicable
  (i.e. delete the old README-specific tests rather than leave them
  skipped).
- **Verification command**: `uv run pytest tests/ -k design`
