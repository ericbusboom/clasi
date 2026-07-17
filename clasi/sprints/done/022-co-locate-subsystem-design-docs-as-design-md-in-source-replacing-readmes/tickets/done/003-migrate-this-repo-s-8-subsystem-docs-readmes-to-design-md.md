---
id: '003'
title: Migrate this repo's 8 subsystem docs + READMEs to DESIGN.md
status: done
use-cases:
- SUC-001
depends-on:
- '002'
github-issue: ''
issue: co-locate-design-docs-as-design-md-in-source-replacing-readme.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Migrate this repo's 8 subsystem docs + READMEs to DESIGN.md

## Description

Direct, ticket-scoped file migration — **not** run through the
`design/` overlay lifecycle (see sprint.md's self-hosting resolution:
the overlay is reserved this sprint for `docs/design/design.md` only,
whose location doesn't move; these 8 docs' location is exactly what's
changing). For each of the 8 subsystems (`design`, `platforms`,
`plugin`, `schemas`, `state_machine`, `status`, `templates`, `tools`)
under `src/clasi/`:

1. Read the existing `docs/design/<slug>.md` body (drop its
   `source_paths`/`readme_path` frontmatter — content is preserved
   as-is; this is a location + frontmatter migration, not a rewrite).
2. Write it as `src/clasi/<subsystem>/DESIGN.md` via the retargeted
   `clasi.design.store.write_design_doc` (ticket 002) — do not
   hand-write the file; use the store function so any future frontmatter
   convention stays centralized.
3. Delete `docs/design/<slug>.md` and `src/clasi/<subsystem>/README.md`.
4. Do not touch `docs/design/design.md` (system doc — handled via the
   overlay, ticket 007) or the 5 project-level docs (`overview.md`,
   `specification.md`, `state-machines.md`, `usecases.md`,
   `worktree-process.md` — stay in `docs/design/` unmoved, per
   sprint.md's Migration Concerns).

Note: `src/clasi/design/DESIGN.md` migrates from
`docs/design/clasi-design.md` (the collision-fallback-named doc under
021's scheme) — under the new scheme there is no collision to avoid, so
this is a normal migration despite the old file's unusual name.

## Acceptance Criteria

- [x] All 8 subsystems have a `DESIGN.md` in their source directory
      with content equivalent to (not rewritten from) their prior
      `docs/design/<slug>.md` body, minus frontmatter.
- [x] All 8 corresponding `docs/design/<slug>.md` files are deleted.
- [x] All 8 corresponding `<subsystem>/README.md` files are deleted.
- [x] `docs/design/design.md` and the 5 project-level docs are
      untouched by this ticket.
- [x] Internal cross-references inside the migrated `DESIGN.md` bodies
      that pointed at old `docs/design/<slug>.md` paths (e.g. any
      subsystem doc that linked to a sibling subsystem's doc) are
      updated to point at the sibling's new `<subsystem>/DESIGN.md`
      path. (No sibling-to-sibling `docs/design/<slug>.md` links were
      found in any of the 8 docs — grepped for all 8 slug filenames
      across all 8 docs, zero matches. The two `docs/design/` mentions
      that do exist point at `design.md` and `state-machines.md`,
      both project-level docs that stay in place, so no rewrite was
      needed.)
- [x] `git status` shows the migration as file moves/deletes/adds
      scoped to this ticket's commit — no unrelated files touched.

## Testing

- **Existing tests to run**: any test asserting on `docs/design/`
  directory contents or subsystem README existence (grep test suite
  for `docs/design` and `README.md` path assertions).
- **New tests to write**: none required beyond what ticket 008's
  end-to-end validation covers — this ticket is primarily a content
  migration, verified by `clasi design validate` (ticket 004's
  retargeted validator) passing against the migrated tree.
- **Verification command**: `uv run clasi design validate`
