---
id: "012-005"
title: git mv design artifact triad and update stale doc/skill references to .clasi/design/
status: open
use-cases: [SUC-004, SUC-005]
depends-on: ["012-001"]
issue:
- fix-clasi-overview-path-mismatch-project-reads-as-uninitialized.md
- gh-17-initialize-gate-checks-docs-clasi-overview-md-but-skill-writes-clasi.md
---

# 012-005: git mv design artifact triad and update stale doc/skill references to .clasi/design/

## Description

After `Project.design_dir` is fixed (ticket 001), the clasi repo itself still has its
design artifact triad at `docs/design/`, not `.clasi/design/`. Until these files are
moved, `overview_exists()` returns False for the clasi repo and `get_status` continues
to report `uninitialized`.

This ticket performs the `git mv` of the three CLASI artifact files and updates the
stale references in docs and plugin skills that still point to the old paths.

Note: the `git mv` must happen on the sprint branch, as a committed change, so the
repo state matches what the predicate expects after the fix is merged.

## Acceptance Criteria

- [ ] `docs/design/overview.md` has been `git mv`'d to `.clasi/design/overview.md`.
- [ ] `docs/design/specification.md` has been `git mv`'d to `.clasi/design/specification.md`.
- [ ] `docs/design/usecases.md` has been `git mv`'d to `.clasi/design/usecases.md`.
- [ ] `docs/design/state-machines.md` and `docs/design/worktree-process.md` remain in place (not CLASI artifact triad).
- [ ] `clasi/plugin/skills/plan-sprint/SKILL.md` lines 24, 71: `docs/clasi/design/` → `.clasi/design/` (and any other stale occurrences).
- [ ] `docs/design/state-machines.md` lines 148-150, 166: `docs/clasi/overview.md` → `.clasi/design/overview.md`.
- [ ] `README.md` line ~300: `docs/design/overview.md` → `.clasi/design/overview.md`.
- [ ] After these changes, `get_status` on the clasi repo returns project state `planning` or later (not `uninitialized`).
- [ ] `pytest` passes (no regressions from any path references in tests).

## Implementation Plan

### Approach

`git mv` for the three files, then a targeted search-and-replace for stale path strings
in the identified docs. Verify with `get_status` after committing.

### Files to Move

```bash
mkdir -p .clasi/design
git mv docs/design/overview.md .clasi/design/overview.md
git mv docs/design/specification.md .clasi/design/specification.md
git mv docs/design/usecases.md .clasi/design/usecases.md
```

### Files to Modify

**`clasi/plugin/skills/plan-sprint/SKILL.md`**:
- Search for `docs/clasi/design/` and replace with `.clasi/design/`.
- Also check for `docs/design/` references that should be `.clasi/design/`.

**`docs/design/state-machines.md`** (stays in place, only content updates):
- Lines 148-150, 166: `docs/clasi/overview.md` → `.clasi/design/overview.md`
- Also update any other stale `docs/clasi/` overview references in this file.

**`README.md`**:
- Line ~300: `docs/design/overview.md` → `.clasi/design/overview.md`
- Do a broader search for `docs/design/overview` and `docs/clasi/overview` to catch any other stale references.

### Verification Steps

After committing, run:
```bash
python3 -c "
from clasi.project import Project
from clasi.status.reader import ClasiStateReader
p = Project('.')
r = ClasiStateReader(p)
print('overview_exists:', r.overview_exists())
"
```
Expected: `overview_exists: True`

Also run `clasi status` (or MCP `get_status`) and confirm project state is `planning` or later,
not `uninitialized`.

### Testing Plan

Run `pytest` to confirm no regressions. No new tests needed — coverage for
`overview_exists` is provided by tickets 001 and 006.

Also run:
```bash
grep -r "docs/clasi/overview\|docs/design/overview" . --include="*.md" --include="*.py" --include="*.yaml" | grep -v ".clasi/sprints"
```
Should return no matches except legacy schema references that are explicitly out of scope.

### Documentation Updates

The doc file edits in this ticket ARE the documentation updates. The `git mv` also
updates the canonical artifact locations visible to any tool reading `.clasi/design/`.
