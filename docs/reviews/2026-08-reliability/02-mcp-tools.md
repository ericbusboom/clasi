# Review: MCP server + tools layer (agent report, verbatim)

## Findings

### Correctness

**F1. critical / correctness — `src/clasi/tools/artifact_tools.py:1857-1907` — `close_sprint` re-runs the version bump on every retry, and swallows every failure inside it.**
Failure scenario: merge conflict at Step 6 → agent fixes conflicts → calls `close_sprint` again → Step 5 runs again, `compute_next_version` sees the previous run's tag and mints a *second* version + tag + commit for the same sprint (build N and N+1 both exist). Worse, the `git add`/`git commit` calls at 1890-1901 ignore return codes: if the commit fails (hook, identity, nothing staged), `create_version_tag` tags the *previous* HEAD and Step 6's merge then fails on a dirty tree — and the whole step is wrapped in `except Exception: print(..., file=sys.stderr)` (1903-1905), so the agent never sees any of it. Fix: consult the recovery state that Step-failures already write — `write_recovery_state` is written on every failure but *never read by close_sprint itself* — to skip already-completed steps on retry (tests, version bump); check git return codes and fail the step loudly like tests/merge do.

**F2. critical / correctness — `artifact_tools.py:1564-1683` — `close_sprint`'s "self-repair" mutates state (moves tickets/issues, advances DB phases, re-acquires locks) *before* the test gate, with no rollback.**
Failure scenario: tickets moved to `done/`, issues relocated from the pool into `<sprint>/issues/done/`, DB phase advanced to `closing` — then tests fail at Step 2. The tool returns an error but the repo is now in a state that never existed before the call, `completed_steps: ["precondition_verification"]` notwithstanding. If the stakeholder decides not to close (fix is large), there is no `unclose_sprint`; the files stay half-migrated. Fix: make Step 1 read-only (report what *would* be repaired), run tests first, and apply repairs only after the test gate passes — or at minimum record every file move in the recovery state so it is reversible.

**F3. critical / correctness — `artifact_tools.py:1111, 1341, 1981; `_check_git_branch` at 2793; `sprint.py` (all git calls) — most git subprocesses run with no `cwd`, silently operating on whatever directory the MCP server process happens to be in.**
`_close_sprint_full` is internally inconsistent: version-bump/db-guard git calls pass `cwd=str(project.root)` (1890-1931) while branch detection, merge (`Sprint.merge_branch`), tag push, branch delete, and worktree pruning do not. Failure scenario: server launched by a harness whose cwd is not the project root (or after any future `os.chdir`) → `close_sprint` archives the sprint dir under the right root but merges/tags/prunes a *different* repo or fails with "not a git repository" mid-sequence — exactly the "weird bug makes the tool useless" class. Fix: one `run_git(args, repo_root)` helper (like `design/overlay.py:_run_git` but taking `project.root` always) used by every git call in the tools layer and `sprint.py`.

**F4. major / correctness — `artifact_tools.py:64` (`resolve_artifact_path`) — relative artifact paths resolve against process cwd, not `project.root`.**
Every path-taking tool (`update_ticket_status`, `move_ticket_to_done`, `add_issue_ref`, `read/write_artifact_frontmatter`...) funnels through this. Failure scenario: agent passes `clasi/sprints/016-x/tickets/001.md` (root-relative, the natural form) while the server cwd differs → `FileNotFoundError` → confusing "Ticket not found" even though the file exists. Fix: `p = Path(path); p = p if p.is_absolute() else get_project().root / p`.

**F5. major / correctness — `mcp_server.py:237-257` — the NONE sentinel (and all call logging) is installed only inside `run()` by monkey-patching `_tool_manager.call_tool`, alongside two other private-API taps (`_mcp_server.instructions` at 151, `JSONRPCMessage.model_validate_json` at 226).**
Failure scenario: an `mcp` library upgrade renames any of these internals → stripping silently stops → `"NONE"` strings flow into tools and get *written into frontmatter* (`record_gate_result(notes="NONE")` → `notes: NONE` in the DB; `close_sprint(test_command="NONE")` → attempts to run the literal command `NONE`, which lands in the `FileNotFoundError` branch and *silently skips tests*, line 1748-1750). This is the same fail-open pattern already bitten elsewhere (role-guard). Fix: move stripping to code CLASI owns — a `clasi_tool()` decorator wrapping `server.tool()` that strips the sentinel per-function before dispatch; it then also applies in unit tests and survives library upgrades.

**F6. major / correctness — `artifact_tools.py:1156-1157` vs the sentinel contract — "Pass empty string to skip tests" is unreachable.**
The documented skip mechanism for `close_sprint` is `test_command=""`, but the harness bug that motivated the sentinel makes `""` drop *all* arguments, and `"NONE"` maps to `None` → default `uv run pytest`. Non-Python consumer projects literally cannot skip tests through this tool. Fix: accept an explicit sentinel like `test_command="SKIP"` (or a boolean `skip_tests`), documented in the tool docstring.

**F7. major / correctness — `design/overlay.py:255, 428; artifact_tools.py:1898` — CLASI's `git commit -m` calls commit whatever the user already had staged.**
The code carefully stages *specific* paths (the sprint-026 `git add -A` fix) but then runs a bare `git commit -m`, which commits the pre-existing index too. Failure scenario: stakeholder has an unrelated file staged mid-review; `seed_sprint_design_overlay` or `close_sprint` sweeps it into a `chore:` commit that then gets merged. Fix: commit with explicit pathspecs (`git commit -m msg -- <paths>`) or verify the index is otherwise clean first.

**F8. major / correctness — `process_tools.py:491-495` — `get_use_case_coverage`, a query tool, renames `docs/plans/` → `.clasi/` as a side effect.**
A read-only status call performing a directory migration is exactly the kind of surprise that produces "some other weird bug": a stale checkout calling coverage silently moves a directory git considers tracked. Fix: delete the migration from the query path (it belongs in `clasi init`/`migrate_command`).

**F9. minor / correctness — `artifact_tools.py:1980` — `tag_name` assigned and never used; `git push --tags` pushes *all* local tags, not the sprint's tag.** Stray local tags get published. Fix: `git push origin f"v{version}"`.

**F10. minor / correctness — `artifact_tools.py:449, 561, 1263, 1809` — `except (ValueError, Exception)` is just `except Exception`, and these blocks `pass` under a "graceful degradation" banner.** Genuine bugs (schema drift, DB corruption) are indistinguishable from "DB not initialized". Fix: catch the specific expected exception and log anything else at WARNING with traceback.

**F11. minor / correctness — `frontmatter.py:125-129` + `artifact.py:58-62` — `update_frontmatter` is a non-atomic read-modify-write (`write_text` truncates in place), no temp-file rename, no lock.** Team-lead + hook processes both write sprint.md/tickets; a crash mid-write corrupts the file, which then trips `MalformedFrontmatterError` and blocks `get_sprint` entirely. Fix: write to `path.with_suffix(".tmp")` + `os.replace`.

**F12. minor / correctness — `artifact_tools.py:734-744` vs `sprint.py:246-251` — ticket→issue auto-link logic exists in two layers with different frontmatter keys (`issues` or `todos` at the tool layer, `todos` only in `Sprint.create_ticket`).** Two code paths that can disagree about whether a ticket gets linked. Fix: delete the auto-link from `Sprint.create_ticket`; the tool layer already decides.

### Simplicity / quality

**F13. major / simplicity — `artifact_tools.py:197-228, 1209-1246, 1608-1649` — the "relocate pending-pool issue into `<sprint>/issues/done/` and complete it" block is copy-pasted three times** (in `_sweep_done_issues`, `_close_sprint_legacy`, `_close_sprint_full`), each with its own inline `Artifact` rebinding. Any fix to one (e.g. the F2 rollback) must be made three times. Fix: one `Issue.relocate_to_sprint_done(sprint)` method; the three call sites become one line each.

**F14. major / simplicity — `artifact_tools.py:573-597` — `insert_sprint` re-implements `Project.create_sprint` inline (its own TODO admits it)** including template writing and DB registration, so template/schema changes must be mirrored here. Fix: `Project.create_sprint(title, sprint_id=...)`.

**F15. major / simplicity — error contract is three-way inconsistent across the 34 artifact tools.** Raise `ValueError` (surfaces as MCP tool error): `create_ticket`, `insert_sprint`, `update_ticket_status`, `move_ticket_to_done`, `reopen_ticket`, `add_issue_ref`, `move_issue_to_done`, `split_issue`, `read/write_artifact_frontmatter`, `get_sprint_status` (uncaught `SprintNotFoundError`), `tag_version`. Return `{"error": ...}` JSON (success-shaped result the agent must inspect): `detail_sprint`, `link_sprint_issues`, `get_sprint_phase`, `advance_sprint_phase`, `record_gate_result`, `acquire/release_execution_lock`, `reconcile_worktrees`, `list_github_issues`, `get_status`. Return `{"status": "error", error: {...}, completed_steps, remaining_steps}`: `close_sprint` full path only. Silent: `list_tickets` returns `[]` for an unknown sprint (typo in `sprint_id` looks like "no tickets"); `seed_sprint_design_overlay` no-ops when opt-in unset; version bump failures go to stderr only. An agent cannot learn one rule for "did it work". Fix: one decorator that catches domain exceptions and always returns `{"ok": bool, ...}`, applied uniformly; the raise-vs-return split disappears.

**F16. minor / simplicity — `schemas/loader.py:25-70 vs 73-134` — `load_from_dict` and `load` duplicate the entire validation body (~45 lines).** Fix: `load` = parse YAML + `load_from_dict(raw)` (only the error-message path suffix differs). Otherwise `schemas/` is pulling its weight: models are three tiny classes, the PEP-562 lazy `__getattr__` in `schemas/__init__.py` already fixed the pydantic import-time cost (sprint 027), and `ArtifactGraph` is a clean read-only index. No action needed beyond the loader dedup.

**F17. minor / simplicity — `design/validator.py:252-271` duplicates `design/overlay.py:_read_sources_manifest` and `_content_hash` verbatim, justified only by a docstring.** Manifest-format drift between writer and validator would be invisible. Fix: move both into `design/paths.py` (already the shared pure module) and import from both sides.

**F18. minor / quality — dead/vestigial code:** `process_tools.py:109` `_find_definition_in_tree` is never called; `artifact_tools.py:1566-1567` `if ticket_file.name == "done": continue` is unreachable under `glob("*.md")`; `_is_template_placeholder(file_path, template_str)` ignores `template_str`; `mcp_server.py`'s schema-dump and raw-RPC-tap diagnostics (189-229) are permanent debug scaffolding for a closed investigation that runs on every startup.

### Speed

**F19. major / speed — no caching in `Artifact`: every property access re-reads and re-parses the file.**
`get_sprint_status` (artifact_tools.py:910-929) parses `sprint.md` five times (`id`, `title`, `status`, `branch`, `worktree` each call `sprint_doc.frontmatter`) plus, via `ticket_counts` → `list_tickets` → `ticket.id`/`ticket.status`, parses every ticket file three times. `list_tickets` (tool) is four parses per ticket. `Project.get_sprint` (project.py:331-393) scans and parses every sprint dir on *every* call — and `_is_ticket_done` calls `get_sprint` once per ticket ref, so `move_ticket_to_done`'s `_sweep_done_issues` is O(issues × ticket-refs × sprints) file parses. `Project.get_issue` falls back to `list_sprints()` (parses all ~30 sprint.md files) per issue filename inside `create_ticket`. Fix with two small changes: (a) mtime-validated frontmatter cache on `Artifact` (or `functools.lru_cache` on `read_document` keyed by `(path, mtime)`); (b) a per-call `Project.sprint_index()` that scans directories once. This alone removes most repeated I/O from the three hottest tools (`create_ticket`, `update_ticket_status`, `get_sprint_status`) without changing any behavior.

**F20. minor / speed — `close_sprint` runs the full test suite (default timeout 900s, this repo ~500s) synchronously inside one MCP tool call.** Client-side MCP tool timeouts or user cancellation mid-run leaves the F2 self-repairs applied with no result returned at all. Consider splitting the test gate into its own tool (`run_close_gate`) so `close_sprint` proper is fast and idempotent, or persisting a "tests passed for HEAD <sha>" marker so retries skip it (also fixes half of F1).

**F21. minor / speed — `get_version` runs `check_staleness` (4+ file reads and regexes) per call — fine — but `_get_existing_tags` + `read_current_version` inside the close path spawn git and re-read pyproject each retry; negligible next to F20, no action needed.**

## artifact_tools decomposition proposal

`artifact_tools.py` currently jams together nine responsibilities: (1) path resolution/`done/`-variant logic, (2) sprint CRUD + renumbering, (3) ticket CRUD/status, (4) issue linkage + the tri-plicated sweep/relocate logic, (5) the entire close-sprint orchestration (~950 lines, 30% of the file), (6) worktree pruning, (7) GitHub API/gh-CLI integration, (8) generic frontmatter tools + versioning, (9) the three review/validation tools with their template-placeholder heuristics. The file's own sibling `design_tools.py` docstring concedes new tools are being placed elsewhere "purely for file-size isolation" — the split is already happening, just without a plan.

Target layout (tool functions stay thin `@server.tool()` wrappers; logic moves down):

```
src/clasi/tools/
  _common.py        # resolve_artifact_path (root-anchored, F4), run_git(args, root) (F3),
                    # tool_result()/tool_error() envelope + @clasi_tool decorator
                    # (uniform error contract F15 + NONE-sentinel stripping F5)
  sprint_tools.py   # create_sprint, detail_sprint, insert_sprint (+_renumber),
                    # list_sprints, get_sprint_status, seed_sprint_design_overlay,
                    # get/advance_sprint_phase, record_gate_result, acquire/release lock
  ticket_tools.py   # create_ticket, list_tickets, update_ticket_status,
                    # move_ticket_to_done, reopen_ticket, throw_ticket_exception, add_issue_ref
  issue_tools.py    # list_issues, move_issue_to_done, split_issue, link_sprint_issues
  close_tools.py    # close_sprint, clear_sprint_recovery, reconcile_worktrees —
                    # thin wrappers only; orchestration moves to clasi/close.py
  review_tools.py   # review_sprint_pre_execution / pre_close / post_close
  github_tools.py   # create/list/close_github_issue + _get_github_repo/_check_gh_access
  frontmatter_tools.py  # read/write_artifact_frontmatter, tag_version
src/clasi/close.py  # SprintCloser: explicit step objects (precondition, tests, archive,
                    # db, overlay, bump, merge, push, prune) each with run()/skip-if-done,
                    # reading recovery state so retry resumes instead of re-running (F1/F20)
src/clasi/issue.py  # gains relocate_to_sprint_done() + sweep helpers, deleting the
                    # three copies in artifact_tools (F13); _is_ticket_done and
                    # _issue_is_deferred move here too (they are Issue/Ticket logic)
```

Shared-layer consolidation: path building (`resolve_artifact_path` + the repeated `tickets_dir.name == "done" → parent → sprint_dir` dance in `add_issue_ref`/`move_ticket_to_done`/`reopen_ticket` becomes one `Ticket.from_path(project, path)` classmethod); frontmatter read/modify/write is already centralized in `Artifact` — the fix there is the mtime cache (F19) and atomic write (F11), not more layering; git ops consolidate onto `run_git` (F3) shared with `sprint.py` and `design/overlay.py`. Roughly 400-500 of the 3,192 lines are duplication that disappears in the move.

## Top structural recommendations

1. **Make `close_sprint` resumable and gate-ordered** (F1, F2, F20): read the recovery state it already writes, skip completed steps on retry (esp. tests and version bump), check git return codes, and move self-repair mutations after the test gate. Highest reliability payoff — close_sprint is where every "half-mutated repo" report originates — moderate effort, contained in one function today.

2. **One `run_git(args, cwd=project.root)` helper for the whole tools layer + `sprint.py`** (F3, F7): eliminates the cwd-dependent git class of failure and the pre-staged-index sweep in one ~30-line change. Small effort, large blast-radius reduction.

3. **Uniform tool envelope via a `@clasi_tool` decorator** (F15, F5): one decorator that (a) strips the NONE sentinel per-call in owned code instead of monkey-patched FastMCP internals, (b) anchors relative paths to `project.root`, (c) converts domain exceptions to a single `{"ok": false, "error": {...}}` shape. Kills the fail-open sentinel risk and gives agents one error contract. Small-medium effort.

4. **mtime-cached `Artifact.frontmatter` + atomic writes** (F19, F11): two changes in `artifact.py`/`frontmatter.py` that speed up every hot tool (`create_ticket`, `get_sprint_status`, `list_tickets`, the issue sweeps) and remove the file-corruption failure mode, with zero call-site changes. Small effort.

5. **Split `artifact_tools.py` per the layout above, starting with `close.py` + `issue.py` sweep dedup** (F13, decomposition): do it after 1-4 so the move is mechanical. The review/github/frontmatter splits are cosmetic and can trail; the close-orchestration and issue-sweep extractions are the ones that make future bugs findable.
