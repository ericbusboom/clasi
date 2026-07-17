---
id: '005'
title: 'Overlay lifecycle: clasi.design.overlay (copy/commit, diff generation, apply)'
status: done
use-cases:
- SUC-004
- SUC-005
depends-on:
- '002'
- '003'
- '004'
github-issue: ''
issue: persistent-per-subsystem-architecture-docs-with-sprint-update-overlays.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Overlay lifecycle: clasi.design.overlay (copy/commit, diff generation, apply)

## Description

Implement `clasi.design.overlay`, the module that performs the
git-anchored overlay copy lifecycle for a sprint's `design/` directory:

1. **Seed + commit pristine copies**: copy specified canonical
   `docs/design/*.md` files into `clasi/sprints/NNN-slug/design/` and
   commit immediately, before any edits (on `main`, at sprint creation —
   see sprint.md Open Question 3's resolution).
2. **Diff generation**: given a sprint's `design/` directory with edited
   copies, produce a human-readable `<name>.diff.md` per edited file by
   comparing it against the pristine (committed) version — fenced
   ```diff blocks or section-grouped before/after, not raw `patch(1)`
   syntax.
3. **Commit edited copies**: at pre-execution approval, commit the
   working-tree changes in the sprint's `design/` directory.
4. **Apply**: at sprint close, copy each overlay file over its
   corresponding canonical `docs/design/` doc.

This module is the only one in the new `clasi.design` package that
shells out to git for design-doc purposes. It composes `paths` (002),
`store` (003), and `validator` (004) but does not itself decide *when*
in the sprint lifecycle these steps run — that wiring is ticket 006.

## Acceptance Criteria

- [x] Seed step: given a list of canonical doc paths and a sprint
      directory, copies each into `<sprint>/design/<name>.md` verbatim
      (byte-identical to the canonical source at copy time) and commits
      them in a single commit before returning.
- [x] Diff step: given a sprint's `design/` directory, for each `.md` file
      that differs from its last-committed (pristine) version, writes
      `<name>.diff.md` in the same directory. Re-running diff generation
      after no further edits is idempotent (regenerating produces the
      same content, satisfying the validator's staleness check from
      ticket 004).
- [x] Diff step correctly identifies "pristine" as the state at the seed
      commit, not merely "previous file content" — verified via a test
      that edits twice and confirms the diff still compares against the
      original seed, not the first edit.
- [x] Commit-edits step: commits exactly the sprint's `design/` directory
      changes (not an unrelated `git add -A`) in a single commit, leaving
      the rest of the working tree's dirty state (if any) untouched.
- [x] Apply step: copies each sprint overlay `.md` file (excluding
      `.diff.md` files) over its corresponding canonical
      `docs/design/<name>.md`, and the resulting canonical file is
      byte-identical to the overlay file (round-trip property from the
      issue).
- [x] Apply step raises a clear, typed error without partially applying
      if any overlay file's canonical target cannot be determined (e.g.
      overlay filename doesn't match any canonical doc) — this must fail
      loudly rather than silently skip, since ticket 006 gates the
      version-bump/tag step on apply succeeding.
- [x] All git operations follow the existing inline-`subprocess.run`
      idiom already used in `sprint.py`/`artifact_tools.py` (per prior
      research, no shared `git_ops.py` module exists yet) — do not
      introduce a new git abstraction layer unless the sprint lead
      explicitly decides to extract one; consistency with the existing
      codebase style takes priority here.

## Implementation Plan

**Approach**: Four focused functions/methods, each independently
testable against a temp git repo fixture: `seed_and_commit(...)`,
`generate_diffs(...)`, `commit_edits(...)`, `apply(...)`. Reuse whatever
`subprocess.run(["git", ...], cwd=..., capture_output=True, text=True)`
idiom is already established in `sprint.py` (`create_branch`,
`merge_branch`) rather than inventing a new calling convention.

**Files to create/modify**:
- `src/clasi/design/overlay.py` (new)

**Testing plan**:
- Integration tests against a throwaway git repo fixture (init a temp
  repo, create a canonical doc, run seed, assert commit exists and
  content matches; edit, run diff generation, assert `.diff.md` content;
  run commit-edits, assert working tree clean and commit exists; run
  apply, assert canonical doc matches overlay).
- Diff content test: assert the generated `.diff.md` is genuinely
  human-readable (fenced code block or before/after sections), not raw
  unified-diff syntax, per the issue's explicit requirement.
- Failure-path test: apply with a mismatched overlay filename raises
  without partially applying (assert no canonical file was modified).

**Documentation updates**:
- Module docstring describing the four-step lifecycle and exactly which
  git state each step assumes/produces — ticket 006 depends on this
  contract being precise.
