---
id: '001'
title: Retarget clasi.design.paths for co-located DESIGN.md
status: done
use-cases:
- SUC-001
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

- [x] `design_doc_path_for(subsystem_path)` returns
      `subsystem_path / "DESIGN.md"`.
- [x] `design_doc_slug` and `readme_path_for` are removed (not
      deprecated-and-kept) — no caller should be able to construct the
      old flat-slug shape.
- [x] `system_doc_name()` is unchanged (`"design.md"`) and has no new
      dependency on `sources:` count or collision handling.
- [x] Module docstring updated to describe the new single-function
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

## Implementation Notes

`paths.py` now exposes only `design_doc_path_for` and `system_doc_name`;
`design_doc_slug`, `readme_path_for`, `DesignPathError`, and
`_find_containing_root` are deleted. `tests/unit/test_design_paths.py`
was rewritten to test `design_doc_path_for` directly (single subsystem,
nested source root, subsystem-path-equal-to-a-former-root edge case, the
"design"-named-subsystem non-collision case, purity, no filesystem
access, no cross-subsystem collision).

As expected per sprint.md's Deployment Sequencing note, this leaves
`clasi/design/store.py`, `clasi/design/validator.py`,
`clasi/design/__init__.py`, and `clasi/tools/design_tools.py` importing
now-removed names (`design_doc_slug`, `readme_path_for`,
`DesignPathError`) — those are ticket 002 (store) and 004 (validator)'s
scope, not this ticket's. This currently breaks collection (not just
execution) of `tests/clasi/test_cli_design.py`,
`tests/system/test_design_overlay_lifecycle.py`,
`tests/unit/test_design_store.py`, `tests/unit/test_design_tools.py`,
`tests/unit/test_design_validator.py`, and `tests/unit/test_mcp_server.py`
(all `ImportError: cannot import name 'DesignPathError'`), and transitively
blocks `tests/unit/test_design_paths.py` itself from collecting via
pytest (importing `clasi.design.paths` triggers `clasi.design.__init__`,
which re-exports the removed names) — verified instead via a standalone
`importlib.util.spec_from_file_location` exec of `paths.py` in isolation,
confirming `design_doc_path_for` and `system_doc_name` behave correctly.
Full-suite baseline (`git stash`) collects 2720 tests cleanly; with this
ticket's change, `uv run pytest --continue-on-collection-errors` reports
2611 passed, 4 failed (pre-existing, `TestRealDoneArchiveBackwardCompat`
in `tests/unit/test_sprint.py`, confirmed identical on the stashed
baseline), 6 errors (the import-error files above, expected until
ticket 002/004 land).
