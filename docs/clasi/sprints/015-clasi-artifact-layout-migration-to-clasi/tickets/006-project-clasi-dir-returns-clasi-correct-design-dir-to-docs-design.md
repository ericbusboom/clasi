---
id: '006'
title: '`Project.clasi_dir` returns `.clasi/`; correct `design_dir` to `docs/design/`'
status: done
use-cases:
  - SUC-001
depends-on:
  - "005"
github-issue: ''
todo: move-clasi-artifact-root-from-docs-clasi-to-dot-clasi.md
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# `Project.clasi_dir` returns `.clasi/`; correct `design_dir` to `docs/design/`

## Description

The single most impactful change: update `clasi/project.py` so `clasi_dir` returns
`self._root / ".clasi"` instead of `self._root / "docs" / "clasi"`. All derived
properties (`sprints_dir`, `issues_dir`, `log_dir`, `architecture_dir`, `db`) inherit
the new root automatically.

Also correct `design_dir` which is currently broken (`docs/clasi/design/` does not exist
in the source repo). It becomes `self._root / "docs" / "design"`.

## Acceptance Criteria

- [x] `Project.clasi_dir` returns `<root>/.clasi`
- [x] `Project.design_dir` returns `<root>/docs/design`
- [x] `Project.sprints_dir`, `issues_dir`, `log_dir`, `architecture_dir`, `db` all
  inherit the new root automatically (verify by inspection or test)
- [x] `Project.docstrings` updated to reference `.clasi/`
- [x] Full test suite passes (tests using `tmp_path / "docs" / "clasi"` must be updated
  to `tmp_path / ".clasi"` — see test update tickets 025-027)

Note: test fixture updates are deferred to tickets 025-027. This ticket may
cause test failures in `test_project.py` which must also be updated here.

## Implementation Plan

### Files to modify
- `clasi/project.py` — two property changes
- `tests/unit/test_project.py` — path fixtures updated to `.clasi/`

### Testing plan
- `uv run pytest tests/unit/test_project.py`
- `uv run pytest` — note: other platform/hook tests may also break and need patching;
  coordinate with tickets 025-027 if needed, or patch inline here
