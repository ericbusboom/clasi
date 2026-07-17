---
id: '005'
title: Fix overlay.apply to resolve co-located per-subsystem targets
status: open
use-cases: [SUC-004]
depends-on: ['001', '002']
github-issue: ''
issue: co-locate-design-docs-as-design-md-in-source-replacing-readme.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Fix overlay.apply to resolve co-located per-subsystem targets

## Description

`src/clasi/design/overlay.py`'s `_resolve_apply_plan`/`apply` currently
assume every overlay file's canonical target is
`canonical_design_dir / overlay_file.name` — a flat, single-directory
mapping. That assumption breaks the moment canonical docs live at N
different per-subsystem paths (`<subsystem>/DESIGN.md`) instead of all
being siblings under `docs/design/`, and `DESIGN.md` is not even a
unique filename across subsystems the way `docs/design/<slug>.md` was.

Fix `apply`'s target resolution so it can map an overlay file back to
its correct per-subsystem `DESIGN.md`, not just the one remaining flat
case (`docs/design/design.md`, unmoved). Recommended mechanism: record
each overlay file's source (canonical) path at seed time — either as a
small sidecar/frontmatter marker written by `seed_and_commit`, or by
having the caller (whatever invokes `apply`, i.e.
`tools/artifact_tools.py`'s `design_overlay_apply` step) pass the
seed's original canonical-path list alongside the overlay directory
rather than re-deriving it from filenames. Do not reintroduce a
slug/filename-based lookup (ticket 001 removed that mechanism
deliberately) — resolve by recorded path, not by name matching.

`seed_and_commit`, `generate_diffs`, and `commit_edits` are
**unchanged** — they already operate on whatever paths they're given
and have no flat-directory assumption baked in (confirmed by reading
`overlay.py`: `_overlay_md_files` just lists `.md` files in the given
directory; `_pristine_content` walks git history by path, not by
directory-relative name). Only `apply`'s target-resolution logic
changes.

Preserve `apply`'s existing fail-fast contract: resolve the full
overlay-file -> canonical-target mapping before writing anything;
raise `OverlayApplyError` and write nothing if any file's target can't
be resolved.

## Acceptance Criteria

- [ ] `apply` correctly resolves a co-located subsystem `DESIGN.md`
      target from an overlay file, given a multi-subsystem fixture
      tree with 2+ subsystems whose overlay files share the same
      basename (`DESIGN.md`) but different canonical targets — this is
      the concrete regression case a name-based lookup would get wrong.
- [ ] `apply` still correctly resolves `docs/design/design.md`'s
      unmoved flat target (the case this sprint's own close exercises).
- [ ] No partial apply on a resolution failure — verified by a test
      that makes one of several overlay files unresolvable and asserts
      zero canonical files were written.
- [ ] `tools/artifact_tools.py`'s `design_overlay_apply` call site
      (`close_sprint`, around line 1665-1696) and the `commit_edits`
      call site (around line 2754-2772) are updated if their calling
      convention needs to change to supply the new resolution
      information (e.g. passing seed source paths through).

## Testing

- **Existing tests to run**: `tests/design/test_overlay.py` (or
  equivalent).
- **New tests to write**: multi-subsystem fixture with colliding
  `DESIGN.md` basenames resolving to distinct targets; fail-fast/
  no-partial-write test; regression test for the single flat-target
  case (`design.md`).
- **Verification command**: `uv run pytest tests/ -k overlay`

Note: per sprint.md's Process Notes / self-hosting resolution, this
ticket's new `apply` behavior is validated against a throwaway fixture
tree, not exercised by this sprint's own close — this sprint's close
only applies `docs/design/design.md` through the still-flat path.
