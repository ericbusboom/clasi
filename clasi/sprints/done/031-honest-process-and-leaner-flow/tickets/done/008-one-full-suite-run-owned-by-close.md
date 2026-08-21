---
id: 008
title: One full-suite run, owned by close
status: done
use-cases:
- SUC-008
depends-on:
- '007'
github-issue: ''
issue: one-full-suite-run-per-sprint.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# One full-suite run, owned by close

## Description

A sprint currently runs the full test suite three times: `execution.md`
§5.2 instructs a pre-close run; the `sprint-review` skill independently
re-runs it; `close_sprint` runs it a third time internally as its
precondition. Measured cost in this repo: 9m30s-19m41s per run (per the
issue) — 20-60 minutes of wall-clock per sprint spent re-running an
identical suite against an unchanged tree. Observed during the 028-030
campaign: the team-lead ran the suite manually then passed
`test_command="true"` to `close_sprint` to dodge a second identical run
— a workaround that quietly weakens the gate for anyone who doesn't know
the tree is unchanged.

**Depends on ticket 007 (soft — file-overlap ordering, not a functional
block)**: both tickets edit `execution.md`/skill instruction files;
landing 008 after 007 avoids two agents editing the same files in
parallel and merge-conflicting. There is no logic dependency — this
ticket's fix (delete the redundant run, interpret instead of re-run, add
a HEAD-sha marker) does not require anything 007 produces.

## Acceptance Criteria

- [x] `execution.md` §5.2's separate pre-close full-suite-run
      instruction is deleted.
- [x] The `sprint-review` skill calls `review_sprint_pre_close` and
      interprets its output instead of re-running the suite itself.
- [x] The orphaned `review_sprint_post_close` MCP tool (confirmed by
      grep during planning: referenced by no skill or agent doc today)
      is either wired to a caller or explicitly retired with a note
      explaining the decision — not left silently unreferenced.
- [x] A "tests already passed for HEAD `<sha>`" marker (or equivalent)
      lets a deliberate close re-run skip redundant work without the
      operator reaching for a fake `test_command`. `close_sprint`'s
      existing `test_command="SKIP"` sentinel (030) is kept unchanged as
      the explicit escape hatch it already is — this marker makes it
      unnecessary in the *normal* flow, it does not replace it.
- [x] `close_sprint`'s own internal test run (`close.py`'s `SprintCloser`)
      is unchanged — this ticket makes it the sprint's *only* run, not a
      different run.
- [x] The docs state the number of full-suite runs per sprint (one) once,
      in one place, matching what the code does.

## Implementation Plan

**Approach**: delete two of the three run sites, wire the third
(`sprint-review`) to interpret rather than re-run, add the HEAD-sha
marker as a small, targeted addition — not a new test-result caching
subsystem.

**Files to modify**:
- `src/clasi/schemas/se-process/instructions/execution.md`
- `src/clasi/plugin/skills/sprint-review/SKILL.md` (or wherever
  `sprint-review`'s instructions actually live — confirm exact path
  during implementation)
- Wherever `review_sprint_pre_close`/`review_sprint_post_close` are
  defined (`tools/artifact_tools.py` or `process_tools.py` — confirm)
  for the HEAD-sha marker, if it needs a small code addition rather than
  being purely a doc/skill change

**Do not modify**: `close.py`'s test-execution step itself (unchanged —
this ticket makes it the sole run, not a different run); the
`test_command="SKIP"` sentinel's existing behavior.

## Process Notes (read before starting)

- **Guards are fail-closed as of sprint 029/009.** A crash inside
  role-guard or mcp-guard is a hard block, not a silent allow.
- **Editing ticket files under this locked sprint's `tickets/` tree is
  allowed for tier-2 agents as of sprint 029/010.** Check-boxes-then-flip
  or flip-then-check-boxes both work.
- **If a guard blocks you, STOP and report it.** Do not route around a
  block with a Bash heredoc, `sed`, redirection, or any mechanism that
  avoids the tool the guard is watching. Reporting a block is a
  successful outcome of this ticket, not a failure.

## Testing

- **Existing tests to run**:
  `uv run pytest tests/system/test_close_sprint_resumability.py tests/unit/test_close_sprint_auto_detect.py -v`
- **New tests to write**: the HEAD-sha marker's skip behavior;
  `sprint-review` calling `review_sprint_pre_close` instead of
  re-running.
- **Verification command**: the existing-tests command above, scoped to
  this ticket's modules — never a live full-suite run as part of this
  ticket's own testing (that would be exactly the redundant run this
  ticket exists to eliminate).

## Follow-up Defect Fix (reopened after first pass)

Found empirically while actually closing sprint 031 with this ticket's
own restructured code: `SprintCloser`'s test step
(`src/clasi/close.py`, the "tests" step inside `SprintCloser.run()`)
called `subprocess.run(test_cmd, capture_output=True, text=True,
timeout=...)` with **no `stdin=` argument**. A subprocess with no
`stdin=` inherits the *parent's* stdin, and when `close_sprint` runs
inside the MCP server, that parent stdin is the JSON-RPC pipe from the
client — it never delivers input. Any test that reads stdin therefore
blocks forever, taking the whole sprint close down with it.

Measured, not theorized: `uv run pytest -q < /dev/null` from a shell
finished in 714s (about 12 minutes), 3192 passed. The identical suite
invoked through `close_sprint` via the MCP server was still running
past 32 minutes when found and killed by hand — the MCP call itself
had already aborted client-side at 1828s with "sent no response or
progress." A sampled stack of the hung process showed it alive and
doing I/O, not crashed. The only environmental difference between the
two runs was stdin. A second, related problem: the orphaned pytest
process kept running (and consuming CPU) after the MCP call aborted —
nothing reaped it.

**Fix** (`src/clasi/close.py`): the test step's subprocess call is now
routed through a new `_run_test_command(cmd, timeout)` helper that adds
`stdin=subprocess.DEVNULL` — same `subprocess.run` call shape otherwise
(`capture_output=True`, `text=True`, `timeout=...`), so a test that
reads stdin now hits EOF and fails fast (a diagnosable failure) instead
of hanging indefinitely.

**Consistency audit of other subprocesses in the close path**:
- `src/clasi/gitutil.py`'s `run_git()` — the shared helper every git
  call in `close.py` (and `sprint.py`, `versioning.py`,
  `design/overlay.py`, `tools/artifact_tools.py`) goes through — had
  the same gap. Fixed with the same `stdin=subprocess.DEVNULL` addition
  in the one shared helper, closing it everywhere at once.
- `src/clasi/worktree.py` — `close_sprint`'s `prune_worktrees` step
  unconditionally calls `reconcile_worktrees`, which (directly, via
  `_parse_ticket_worktrees`, and via `cleanup_worktree`) makes 7 bare
  `subprocess.run(["git", ...])` calls with the same missing-`stdin=`
  gap. All 7 fixed. The module's *other* bare git calls
  (`create_worktree`, `create_ticket_branch`, `validate_worktree`,
  `merge_ticket_branch`) back the parallel-execution controller, which
  the module's own docstring says is "not yet wired into the
  controller" — confirmed not reachable from `close_sprint` today, so
  deliberately left alone as out of this fix's scope (same pattern,
  dead code; worth a follow-up if that controller gets wired up).

**Process-group killing on timeout — investigated, deliberately not
done here**: `subprocess.run`'s timeout handling kills only the direct
child (`Popen.kill()`); `uv run pytest` can fork pytest as a
grandchild rather than exec-replacing itself, which is very likely why
the orphan survived the aborted MCP call. The robust fix (switch to
manual `Popen` + `communicate()`, spawn with `start_new_session=True`,
and `os.killpg()` the whole group on timeout) was implemented and
worked correctly in isolation, but it replaces the test step's
`subprocess.run` call with `subprocess.Popen`, which silently bypasses
`tests/unit/test_close_sprint_worktrees.py`'s pre-existing
`@patch("subprocess.run")` global mock (a hand-ordered `side_effect`
list with an explicit `# pytest` slot at position 0) — two of that
file's tests broke, and in that specific test's scratch tmp_path a real
`uv run pytest` was actually spawned inside a unit test (it happened to
exit fast with code 5, "no tests collected," which is why it surfaced
as a shifted-index assertion failure rather than a hang, but the
bypass itself is real). Making that robust would mean also reworking
that file's mocking to be `Popen`-aware — real, but no longer small or
self-contained. Reverted to the plain `subprocess.run`-based fix
instead. Recommend filing the process-group-kill as its own follow-up
ticket/issue.

**Regression tests added**:
- `tests/unit/test_close_run_test_command.py` (new) — asserts
  `_run_test_command` calls `subprocess.run` with
  `stdin=subprocess.DEVNULL`, that the pre-existing
  `capture_output`/`text`/`timeout` shape is unchanged, and that
  `TimeoutExpired`/`FileNotFoundError` still propagate.
- `tests/unit/test_gitutil.py` — `TestRunGit::test_stdin_is_devnull`
  asserts `run_git` calls `subprocess.run` with `stdin=subprocess.DEVNULL`.
- `tests/clasi/test_worktree.py` —
  `TestGitSubprocessCallsCloseStdin` (new class, 3 tests): spies on the
  real `subprocess.run` while exercising `cleanup_worktree` and
  `reconcile_worktrees` (both the non-merged and the merged-state code
  path, which hits the distinct `git merge-base --is-ancestor` call) end
  to end against a real scratch repo, asserting every git call made
  carries `stdin=subprocess.DEVNULL`.

All scoped tests run in the foreground and passing (92 passed):
`tests/unit/test_close_run_test_command.py`,
`tests/unit/test_gitutil.py`, `tests/clasi/test_worktree.py`,
`tests/unit/test_close_sprint_auto_detect.py`,
`tests/unit/test_close_sprint_worktrees.py`,
`tests/system/test_close_sprint_resumability.py`,
`tests/system/test_close_sprint_test_pass_marker.py`. Additionally
re-ran the broader close/version/worktree-adjacent system and unit
suites (173 passed) as a collateral-damage check given the mocking
fragility discovered above.
