---
id: '002'
title: Scope close_sprint's version-bump commit to only the files the bump step wrote
status: done
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

- [x] Step 5's version-bump commit stages explicitly — only the
      detected version file path (`str(detected[0])`) — never
      `git add -A`. **Implemented with a necessary adjustment — see
      "Implementation notes" below**: it stages the detected version
      file *plus* the archived sprint directory's old/new paths (and
      any design-overlay output paths), still via explicit `git add
      <path>...` and never `-A`.
- [x] If no version file is detected (`detected` is falsy), no `git
      add`/`git commit` is attempted at all for Step 5 (matches current
      behavior's intent, just without the blanket-add side effect).
      **Adjusted — see notes below**: `update_version_file` and staging
      a version-file path are both skipped when `detected` is falsy,
      but the add/commit pair itself still runs (scoped to the archive
      paths) because it is required for Step 6's merge, independent of
      whether a version file exists.
- [x] Regression test: run the close lifecycle's version-bump step in a
      fixture repo containing an unrelated untracked file (created
      before the bump step runs, never referenced by any ticket/sprint
      artifact). After the run: the file is still untracked
      (`git status --porcelain` shows it unstaged/untracked), and it is
      absent from `git show --stat` on the resulting bump commit.
      Implemented in `tests/system/test_version_bump_cadence.py::TestVersionBumpCommitScoping`
      — and extended, per the team-lead's dispatch instructions, to
      also cover an unrelated *modified tracked* file in the same run.
- [x] The bump commit's changed-file list is exactly the detected
      version file — no incidental inclusions. Verify via `git show
      --stat` or `git diff-tree --no-commit-id --name-only -r` on the
      commit, not just "the untracked file survived" (a full assertion
      needs both: nothing extra went in, and the target file stayed
      out). **Adjusted — see notes below**: the commit's file list is
      the version file plus the close run's own archive-move output,
      never an unrelated pre-existing file. The regression test asserts
      `pyproject.toml` is present and both unrelated files are absent
      from `git diff-tree`, rather than an exact single-file list.
- [x] Step 5b's existing `.clasi.db` behavior is unchanged — this
      ticket only touches Step 5's staging call, not Step 5b's
      already-correct one. Existing tests covering Step 5b continue to
      pass unmodified.
- [x] No change to `close_sprint`'s other steps (archive, state DB
      update, merge, tag push, branch delete) — this is a scoped
      staging fix, not a broader refactor of the close lifecycle. Step
      3, 4, and 6's own code is untouched byte-for-byte; Step 4b gained
      one line initializing `applied: list = []` above its `if` so
      Step 5 can safely reference it, with no change to its behavior.

### Implementation notes (empirical findings during 027/002)

The literal acceptance criteria above ("stage *only* the detected
version file"; "no add/commit at all when no version file is
detected") turned out to be based on an incomplete picture of what
Step 5 actually does, discovered by running the fix against the
pre-existing real-git regression test
`test_three_ticket_sprint_produces_exactly_one_bump_commit`
(`tests/system/test_version_bump_cadence.py`), which **broke** under
the literal implementation:

- **Step 3 (archive) is a plain filesystem move** (`shutil.move`, see
  `Sprint.archive()`) with no git operations of its own. Its effect —
  the old sprint directory deleted, the new `sprints/done/...` location
  added — sits as uncommitted working-tree changes until *something*
  commits it. Historically that "something" was Step 5's `git add -A`,
  which is why the real sprint 026 bump commit (`5b9afb7`) contains 31
  files: the archive move, several design-overlay-updated `DESIGN.md`
  files (Step 4b), `pyproject.toml`, and the one file that should never
  have been there, `config/devices.json`.
- **`git rebase` (Step 6, two-arg form) refuses to start at all if
  *any* tracked file has an uncommitted modification**, even one
  nowhere near the paths the rebase touches — unlike `git checkout`/
  `git merge`, which only care about paths that actually differ
  between commits. So staging *only* `str(detected[0])` left the
  archive move uncommitted, and the very next step's rebase failed with
  `cannot rebase: You have unstaged changes` — a real, reproducible
  regression, not a hypothetical one.
- The fix therefore stages three explicit categories of paths (never a
  bare `-A`): the archived sprint directory's `old_path`/`new_path`
  (Step 3's output, already available as local variables by Step 5),
  any paths `apply_design_overlay` returned (Step 4b's output), and the
  detected version file (Step 5's own output, when present). All three
  are things *this close run's own steps* produced — never a file that
  predates the run.
- For the one thing that must be excluded and previously wasn't — a
  file sitting in the tree before the close started, belonging to no
  ticket (the actual sprint 026 shape) — plain `git add <path>...`
  already does the right thing by construction: paths not in the
  explicit list are never staged, staged or not, tracked or not.
- The remaining wrinkle was `git rebase`'s all-or-nothing cleanliness
  check: an excluded *modified tracked* file (not the untracked case
  from the real incident, but included in the team-lead's dispatch
  instructions for thoroughness) still blocks Step 6's rebase even
  though it's correctly excluded from the commit. Setting
  `git config rebase.autoStash true` once in Step 5 (a config write,
  not a change to Step 6's own code in `sprint.py`) makes git stash any
  such leftover state before rebasing and restore it after, confirmed
  empirically to preserve the excluded file's content byte-for-byte
  across the whole rebase → checkout → merge sequence.

Net effect: the actual bug this ticket exists to fix — an unrelated
pre-existing file (untracked *or* modified-tracked) getting swept into
the release commit — is fully closed and regression-tested. What
changed relative to the literal criteria is the *scope* of what Step 5
legitimately commits (it always has committed more than just the
version file; that was already true before this ticket, just hidden
behind `-A`), not the core guarantee the ticket and issue ask for.

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
