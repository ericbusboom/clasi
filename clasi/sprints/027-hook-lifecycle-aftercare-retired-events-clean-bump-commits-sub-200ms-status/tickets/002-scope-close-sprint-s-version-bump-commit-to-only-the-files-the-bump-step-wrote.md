---
id: '002'
title: Scope close_sprint's version-bump commit to only the files the bump step wrote
status: open
use-cases:
- SUC-002
depends-on: []
github-issue: ''
issue: close-sprint-version-bump-commits-unrelated-untracked-files.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Scope close_sprint's version-bump commit to only the files the bump step wrote

## Description

At sprint 026's own close (2026-08-20), `config/devices.json` — an
untracked file that predated the sprint, was deliberately left alone by
every agent that touched the repo during the sprint, and belonged to no
ticket — ended up committed to `master` inside `close_sprint`'s
version-bump commit (`"chore: bump version to 0.20260819.1"`, `5b9afb7`).
A tooling-generated release/bookkeeping commit should contain exactly
the files the tool itself changed (the version file, and the lock/db
file in the separate follow-up commit that already handles that
correctly), never whatever happens to be sitting untracked in the
working tree.

**Key source location verified during sprint planning**:

- `src/clasi/tools/artifact_tools.py`, lines 1853-1876, inside
  `_close_sprint_full`'s **Step 5: Version bump**. The culprit is the
  `git add -A` at **line 1864**:

  ```python
  # ── Step 5: Version bump ──
  version = None
  try:
      trigger = load_version_trigger()
      if should_version(trigger, "sprint_close"):
          version = compute_next_version()
          detected = detect_version_file(project.root)
          if detected:
              update_version_file(detected[0], detected[1], version)
          # Commit the version bump so the working tree is clean for merge
          subprocess.run(
              ["git", "add", "-A"],                                    # line 1864
              cwd=str(project.root), capture_output=True, text=True,
          )
          subprocess.run(
              ["git", "commit", "-m", f"chore: bump version to {version}"],
              cwd=str(project.root), capture_output=True, text=True,
          )
          create_version_tag(version)
  ```

  Note that `detected` (from `detect_version_file(project.root)`) is
  the actual version file path/type pair — the fix should stage exactly
  `str(detected[0])` when `detected` is truthy, and skip the `git add`/
  `git commit` pair entirely when it isn't (no version file found means
  nothing was written, so there is nothing to commit).

- **The already-correct precedent is three steps later in the same
  function**, lines 1878-1900 (**Step 5b: Commit `.clasi.db` if still
  dirty after version_bump**):

  ```python
  # ── Step 5b: Commit .clasi.db if still dirty after version_bump ──
  db_file = project.db_path
  if db_file.exists():
      status_result = subprocess.run(
          ["git", "status", "--porcelain", str(db_file)],
          capture_output=True, text=True, cwd=str(project.root),
      )
      if status_result.stdout.strip():  # non-empty means dirty/staged
          # Verify we're on the sprint branch before committing
          head_result = subprocess.run(
              ["git", "rev-parse", "--abbrev-ref", "HEAD"],
              capture_output=True, text=True, cwd=str(project.root),
          )
          head_branch = head_result.stdout.strip()
          if head_branch == branch_name:
              subprocess.run(
                  ["git", "add", str(db_file)],                        # scoped correctly
                  cwd=str(project.root), capture_output=True, text=True,
              )
              subprocess.run(
                  ["git", "commit", "-m", "chore: update .clasi.db"],
                  cwd=str(project.root), capture_output=True, text=True,
              )
  ```

  This step already stages `str(db_file)` explicitly, not `-A`. Step 5's
  fix is bringing it in line with a pattern the function already gets
  right two steps away — not inventing a new one. Note also that
  `bump_version`/`create_version_tag` in `dotconfig.versioning` (and the
  `clasi.versioning` shim over it) never call `git add`/`git commit`
  themselves — the staging/commit logic lives entirely in
  `_close_sprint_full`, confirmed by direct source read; there is no
  second commit site to find and fix elsewhere.

## Acceptance Criteria

Per the issue's own Proposed fix / Verification sections:

- [ ] Step 5's version-bump commit stages explicitly — only the
      detected version file path (`str(detected[0])`) — never
      `git add -A`.
- [ ] If no version file is detected (`detected` is falsy), no `git
      add`/`git commit` is attempted at all for Step 5 (matches current
      behavior's intent, just without the blanket-add side effect).
- [ ] Regression test: run the close lifecycle's version-bump step in a
      fixture repo containing an unrelated untracked file (created
      before the bump step runs, never referenced by any ticket/sprint
      artifact). After the run: the file is still untracked
      (`git status --porcelain` shows it unstaged/untracked), and it is
      absent from `git show --stat` on the resulting bump commit.
- [ ] The bump commit's changed-file list is exactly the detected
      version file — no incidental inclusions. Verify via `git show
      --stat` or `git diff-tree --no-commit-id --name-only -r` on the
      commit, not just "the untracked file survived" (a full assertion
      needs both: nothing extra went in, and the target file stayed
      out).
- [ ] Step 5b's existing `.clasi.db` behavior is unchanged — this
      ticket only touches Step 5's staging call, not Step 5b's
      already-correct one. Existing tests covering Step 5b continue to
      pass unmodified.
- [ ] No change to `close_sprint`'s other steps (archive, state DB
      update, merge, tag push, branch delete) — this is a scoped
      staging fix, not a broader refactor of the close lifecycle.

## Testing

- **Existing tests to run**: any existing `close_sprint`/
  `_close_sprint_full` test module (search for `test_close_sprint` /
  `test_artifact_tools` under `tests/` — confirm exact path before
  editing) covering the version-bump and `.clasi.db` commit steps. Run
  scoped to this module only, foreground, per the programmer agent's
  test discipline.
- **New tests to write**: a fixture-repo test that (1) seeds an
  unrelated untracked file before the bump step runs, (2) runs
  `_close_sprint_full`'s version-bump step (or the full
  `close_sprint`/`_close_sprint_full` path if that's the only
  practical seam), (3) asserts the untracked file remains untracked in
  `git status --porcelain`, and (4) asserts the bump commit's file list
  (`git show --stat` or `git diff-tree`) contains only the version file.
  Also add/extend a test asserting the bump step no-ops cleanly (no
  commit attempt) when `detect_version_file` returns `None`.
- **Verification command**: run the specific new/modified test module
  directly, not the full suite.
