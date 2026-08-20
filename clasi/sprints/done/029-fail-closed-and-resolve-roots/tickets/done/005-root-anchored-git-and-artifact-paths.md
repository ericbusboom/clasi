---
id: '005'
title: Root-anchored git and artifact paths
status: done
use-cases:
- SUC-005
depends-on: []
github-issue: ''
issue: root-anchored-git-and-artifact-paths.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Root-anchored git and artifact paths

## Description

Most git subprocesses in the tools layer run with no `cwd=`, silently
operating on whatever directory the MCP server process happens to be
in; `_close_sprint_full` is internally inconsistent (some calls pass
`cwd=str(project.root)`, branch detection/merge/tag-push/prune do not).
Relative artifact paths resolve against process cwd, not
`project.root`. Bare `git commit -m` sweeps whatever the stakeholder
had pre-staged into CLASI's own chore commits. This ticket introduces
one shared `run_git` helper and anchors every call site to
`project.root`.

**Scope**: new `src/clasi/gitutil.py`, `src/clasi/sprint.py`,
`src/clasi/tools/artifact_tools.py`, `src/clasi/design/overlay.py`,
`src/clasi/versioning.py`.

**Files to touch (verified during planning):**

- New `src/clasi/gitutil.py` — `run_git(args: list[str], cwd: Path) ->
  subprocess.CompletedProcess[str]`, promoted from
  `design/overlay.py`'s existing local `_run_git`
  (`design/overlay.py:113-118`, already correct:
  `subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
  text=True)`). Design decision (see sprint.md Architecture Design
  Rationale): keep this module small and scoped to exactly this helper
  — do not build the larger `tools/_common.py` the reliability review's
  own decomposition proposal describes; that is separate,
  not-yet-designed Phase 3/4 work (`uniform-mcp-tool-envelope.md`).
- `src/clasi/design/overlay.py:113-118` — delete the local `_run_git`;
  every one of its call sites (`overlay.py:247, 255, 285, 296, 415,
  422, 428`) imports and calls the shared `gitutil.run_git` instead. No
  behavior change (it already passed `cwd` correctly) — a pure
  consolidation.
- `src/clasi/sprint.py` — every bare `subprocess.run([...])` git call
  (currently at lines 304, 311, 343, 352, 364, 370, 376, 386, 392, 402,
  424, 433 — verified via grep during planning) routes through
  `gitutil.run_git(args, cwd=project.root)`.
- `src/clasi/tools/artifact_tools.py` — every git call site not already
  passing `cwd=str(project.root)` (branch detection ~1111,
  merge/tag/prune-adjacent calls in the `_close_sprint_full` sequence
  ~1341, 1373, 1912-1981) routes through `gitutil.run_git(args,
  cwd=project.root)`; the version-bump/db-guard calls that already
  correctly pass `cwd=str(project.root)` (~1890-1931) may switch to the
  shared helper too for consistency, or stay as-is — no behavior change
  either way, implementer's call. Also: `resolve_artifact_path`
  (`artifact_tools.py:53-68`) anchors a relative input path to
  `project.root` (`p = Path(path); p = p if p.is_absolute() else
  get_project().root / p`) instead of resolving bare against process
  cwd. Also: any `git commit -m` call in this file uses explicit
  pathspecs (`git commit -m msg -- <paths>`) rather than committing
  whatever else happens to be staged.
- `src/clasi/versioning.py:225-234` (`_get_existing_tags`) — currently
  `subprocess.run(["git", "tag", "-l"], capture_output=True,
  text=True, check=False)` with no `cwd` at all (verified during
  planning — the exact F15-cwd-note gap: "compute_next_version/
  _get_existing_tags implicitly use Path.cwd() while callers pass
  project.root to detect_version_file"). Add an explicit
  `project_root: Path` parameter, threaded through to
  `gitutil.run_git(["tag", "-l"], cwd=project_root)`;
  `compute_next_version` (`versioning.py:238+`) gains the same explicit
  parameter and passes it through instead of relying on the MCP
  server's own cwd happening to already be `project.root`.

## Acceptance Criteria

- [x] One `run_git(args, cwd=project.root)` helper used by every git
      call in the tools layer, `sprint.py`, and `design/overlay.py`; no
      bare `subprocess` git invocations remain in any of them.
      `src/clasi/gitutil.py` is new. Scoping note: `artifact_tools.py`'s
      GitHub-issue helpers (`_get_github_repo`, `_check_gh_access`,
      `list_github_issues`, `close_github_issue`) and the sprint-review
      helper `_check_git_branch` were deliberately left as bare
      `subprocess` calls — they are not part of the "Files to touch"
      itemization above, belong to unrelated features, and sit outside
      the close_sprint/versioning safety concern this ticket fixes.
      Every call site the ticket itemizes (branch detection,
      `_prune_sprint_worktrees`, and the `_close_sprint_full`
      version-bump / `.clasi.db` / push-tags sequence) now routes
      through `run_git`.
- [x] CLASI-generated commits use explicit pathspecs
      (`git commit -m msg -- <paths>`)
- [x] `resolve_artifact_path` anchors relative paths to `project.root`
- [x] `compute_next_version`/`_get_existing_tags` take an explicit
      `project_root` parameter instead of relying on implicit cwd
- [x] A test runs a representative tool (e.g. a `close_sprint` step, or
      `_get_existing_tags`) with the process cwd set somewhere other
      than `project.root` and asserts correct behavior

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/test_artifact_tools.py tests/unit/test_sprint.py tests/unit/test_design_overlay.py tests/unit/test_versioning.py`
  (scoped, foreground)
- **New tests to write**: the cwd-independence test above; a unit test
  for `gitutil.run_git` itself; a test asserting a CLASI-generated
  commit does not sweep a pre-staged unrelated file.
- **Verification command**: `uv run pytest tests/unit/test_artifact_tools.py tests/unit/test_sprint.py tests/unit/test_design_overlay.py tests/unit/test_versioning.py -v`
