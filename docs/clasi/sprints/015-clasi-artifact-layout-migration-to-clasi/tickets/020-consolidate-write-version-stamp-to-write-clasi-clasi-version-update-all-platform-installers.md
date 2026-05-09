---
id: '020'
title: Consolidate `write_version_stamp` to write `.clasi/clasi-version`; update all
  platform installers
status: todo
use-cases:
  - SUC-001
depends-on:
  - "006"
github-issue: ''
todo: consolidate-the-clasi-version-marker-into-clasi-clasi-version.md
completes_todo: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Consolidate `write_version_stamp` to write `.clasi/clasi-version`; update all platform installers

## Description

Replace `write_version_stamp(target, subdir)` in `clasi/platforms/_markers.py` with
`write_version_stamp(target: Path)` that writes a single file at
`<target>/.clasi/clasi-version`.

Update `claude.py`, `codex.py`, `copilot.py` to call `write_version_stamp(target)` once
each (removing the two-call pattern that wrote separate per-platform stamp files).

Uninstall: if any platform's `uninstall()` currently removes a per-platform stamp file,
update it to remove `.clasi/clasi-version` (and `.clasi/` if it becomes empty).

## Acceptance Criteria

- [ ] `write_version_stamp(target)` writes only `<target>/.clasi/clasi-version`
- [ ] No per-platform `.clasi-version` files written (`.claude/.clasi-version` etc. gone)
- [ ] Each platform installer calls `write_version_stamp(target)` exactly once
- [ ] Re-running install on same target overwrites the file safely (same content)
- [ ] E2E: `clasi install --platform claude` on a temp dir → only `.clasi/clasi-version`
  exists; no `.claude/.clasi-version` or `.agents/.clasi-version`
- [ ] Full test suite passes

## Implementation Plan

### Files to modify
- `clasi/platforms/_markers.py` — function signature and body
- `clasi/platforms/claude.py` — replace two calls with one
- `clasi/platforms/codex.py` — replace two calls with one
- `clasi/platforms/copilot.py` — replace two calls with one

### Testing plan
- E2E test with temp dir
- `uv run pytest` — full suite (no tests currently exercise `write_version_stamp`
  directly per the TODO; add one)
