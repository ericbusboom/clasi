---
id: '001'
title: Retarget clasi.design.paths for co-located DESIGN.md
status: open
use-cases: [SUC-001]
depends-on: []
github-issue: ''
issue: co-locate-design-docs-as-design-md-in-source-replacing-readme.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Retarget clasi.design.paths for co-located DESIGN.md

## Description

Foundation ticket. `src/clasi/design/paths.py` currently derives a
flat `docs/design/<slug>.md` filename via `design_doc_slug` (with
multi-root disambiguation and a system-doc-name collision fallback) and
a separate `readme_path_for(subsystem_path) -> subsystem_path /
"README.md"`. Replace both with a single function,
`design_doc_path_for(subsystem_path: Path) -> Path`, returning
`subsystem_path / "DESIGN.md"`. No slugification, no source-root
disambiguation, no collision handling is needed — the doc's identity is
its own path, so two subsystems can never collide on a name the way two
`docs/design/<slug>.md` files could.

Keep `system_doc_name()` (still returns `"design.md"`, still resolved
under `project.design_dir`, unchanged by this sprint — see sprint.md's
Migration Concerns). Remove `design_doc_slug`, `readme_path_for`,
`DesignPathError`'s collision-specific cases, and `_find_containing_root`
if it becomes unused after the multi-root disambiguation logic is
deleted (multi-root disambiguation no longer applies once the slug
concept is gone — a subsystem's `DESIGN.md` path is simply
`<subsystem_path>/DESIGN.md>` regardless of how many `sources:` roots
are configured).

## Acceptance Criteria

- [ ] `design_doc_path_for(subsystem_path)` returns
      `subsystem_path / "DESIGN.md"`.
- [ ] `design_doc_slug` and `readme_path_for` are removed (not
      deprecated-and-kept) — no caller should be able to construct the
      old flat-slug shape.
- [ ] `system_doc_name()` is unchanged (`"design.md"`) and has no new
      dependency on `sources:` count or collision handling.
- [ ] Module docstring updated to describe the new single-function
      contract; the old naming-convention prose (single-root/multi-root
      disambiguation, collision fallback) is removed, not left stale.

## Testing

- **Existing tests to run**: `tests/design/test_paths.py` (or
  equivalent — locate via `uv run pytest --collect-only -q | grep
  design`).
- **New tests to write**: replace slug/collision/multi-root tests with
  direct `design_doc_path_for` tests (single subsystem, nested source
  root, subsystem path equal to a source root edge case if one existed
  previously).
- **Verification command**: `uv run pytest tests/ -k design`
