# Review: CLI, install, platforms, clasr (agent report, verbatim)

## Findings

**F1. critical / correctness — `src/clasi/init_command.py:37-52,84-111`** — `_update_mcp_json` unconditionally rewrites `mcpServers.clasi` to `{"command": "clasi", "args": ["mcp"]}` (`_detect_mcp_command` even `del target`s its only input). Failure: in the clasi repo itself, whose checked-in `.mcp.json` is `uv run clasi mcp`, every `clasi init` (and every `clasi migrate`, which calls `run_init`) reverts the config; the next session launches the PATH build instead of the venv editable build, which then trips (or worse, silently passes) the stale-guard. This is the known "init reverts this repo's own .mcp.json" issue. Fix: if a `clasi` server entry already exists in any form, leave it untouched; only add the entry when absent.

**F2. critical / correctness — `src/clasi/platforms/claude.py:503`** — `uninstall` runs `_links.unlink_alias(target / "CLAUDE.md")`, deleting the whole file, but the current install model (`_write_claude_md`, lines 81-117) writes CLAUDE.md as a regular file holding a marker block "alongside other tools (e.g. rundbat) that manage their own named blocks." Failure: `clasi uninstall --claude` on any repo with user or other-tool content in CLAUDE.md destroys that content. Fix: `strip_section(target / "CLAUDE.md")`, exactly as done for AGENTS.md two lines later.

**F3. major / correctness — `src/clasi/platforms/claude.py:337-345`** — install sets `settings["hooks"] = new_hooks` wholesale in `.claude/settings.json`. Failure: any user-defined hooks are silently deleted on every `clasi init`. Fix: merge per event type and only replace entries identifiable as CLASI's (command starts with `clasi hook`).

**F4. major / correctness — `src/clasi/platforms/codex.py:209-234`, `copilot.py:56-86` vs `claude.py:253-271`** — three installers write the same canonical `.agents/skills/<n>/SKILL.md` with different content rules: Claude resolves `Load from:` directives (which most bundled skills use); Codex and Copilot write the raw file. Failure: `clasi init --claude --codex` runs Codex second and stomps the resolved canonical that `.claude/skills/` symlinks point at — Claude skills silently lose their full prose. Fix: one shared canonical-skill writer (with `resolve_skill_body`) used by all three installers.

**F5. major / correctness+simplicity — `src/clasi/worktree.py:9-14` vs `src/clasi/schemas/se-process/instructions/execution.md` §0/Parallel Path** — the module docstring says "Parallel execution is disabled… not yet wired into the controller," while the shipped execution instructions describe a live parallel path behind sprint `worktree: true` that tells the agent to call `check_independence` / `create_worktree` — Python functions with **no MCP tool** (only `reconcile_worktrees` is exposed). Failure: an agent on a `worktree: true` sprint can only comply by improvised `python -c` shelling; meanwhile every real sprint (022-027) carries `worktree: false`. Fix: retire the parallel path from execution.md and delete the unreachable half of worktree.py; keep only reconcile/cleanup/audit, which `close_sprint._prune_sprint_worktrees` (`artifact_tools.py:1383-1414`) and the `reconcile_worktrees` tool actually use.

**F6. major / correctness — `src/clasi/staleness.py:100-163`** — no signal detects same-version drift. With an editable install, `source_path` equals the repo path (signal 2 path check never fires) and `metadata_version == repo pyproject version` unless a bump happened (signals 1 and 2 version checks never fire); the MCP server additionally runs the check only at startup (`mcp_server.py:134-158`) and in `get_version`/guards, all of which pass after an un-bumped edit. Failure: exactly the MEMORY.md "same-version drift" — a long-lived `clasi mcp` serves pre-fix code with a green staleness report. Simplest fix (~12 lines): record `_IMPORT_TIME = time.time()` in `clasi/__init__.py`; in `check_staleness`, flag stale if any `Path(clasi.__file__).parent.rglob("*.py")` mtime is newer than `_IMPORT_TIME`. No hashing needed; catches every post-import source edit regardless of version strings.

**F7. major / simplicity — `src/clasi/platforms/` (2,531 lines) vs `src/clasr/` (2,432 lines)** — two complete platform-adapter stacks. Nothing in `src/clasi` imports `clasr`; `clasi init` uses only `clasi.platforms`. Incompatible conventions: marker format (`<!-- CLASI:START -->` vs `<!-- BEGIN clasr:<provider> -->`), uninstall model (name-based vs manifest-based), near-identical-but-diverged leaf helpers (`_links.py` vs `links.py`). Failure on drift: if both are used on one repo, each tree's uninstaller cannot see the other's blocks → orphaned/duplicated sections and stranded skills; every behavior fix must be made twice. Fix: pick a direction — either make `clasi init` a thin "clasi" provider on top of clasr's manifest engine (the better model), or freeze clasr and extract it to its own repo.

**F8. major / correctness — `src/clasr/integration.py:430-442` + `src/clasr/platforms/codex.py:398-399`** — scoped-rule routing appends the rule body to an existing nested `AGENTS.md` with no marker and no idempotency check; uninstall records the file as kind `rendered` and `unlink()`s it wholesale. Failure: every reinstall duplicates the rule text; uninstall deletes a shared nested AGENTS.md including other content. Fix: use `markers.write_block`/`strip_block` for nested AGENTS.md too.

**F9. major / quality — `src/clasr/integration.py:351-382`** — `TomlIntegration.render_agent` is byte-identical to `MarkdownIntegration.render_agent` and emits YAML-frontmatter `.md` files despite the "TOML projection" contract; clasi's own Codex adapter writes real TOML (`clasi/platforms/codex.py:281-314`). Failure: clasr-installed Codex agents are in a format Codex doesn't read — clasr cannot subsume the Codex path today. Fix: implement TOML output or delete `TomlIntegration`.

**F10. major / correctness — `src/clasi/cli.py:131`** — `clasi tool plan-to-issue` defaults `--issues-dir` to `.clasi/issues`, while the hook handler (`hook_handlers.py:1730`) and `ARTIFACT_PATH_DEFAULTS` use `clasi/issues`. Failure: the CLI tool resurrects the legacy hidden dir, which `detect_moves` then perpetually proposes migrating. Fix: default from `Project(...).issues_dir`.

**F11. minor / correctness — `src/clasi/migrate_command.py:546`** — `run_migrate` always finishes with `run_init(target, claude=True)`. Failure: `clasi migrate` on a Codex- or Copilot-only repo installs the entire Claude integration. Fix: refresh only detected/installed platforms.

**F12. minor / correctness — `src/clasi/migrate_command.py:402-414`** — db move with existing destination warns "skipping (will not clobber)" and leaves *two* databases; the legacy one (possibly holding OOP/lock state) stays behind and `detect_moves` re-proposes it forever. Fix: fail loudly with a manual-reconciliation message, or compare/merge.

**F13. minor / quality — `src/clasi/platforms/claude.py:386-407`** — `_create_rules` docstring claims "compares content before writing and skips unchanged files"; the code always writes and always reports "Wrote". Combined with F1, `clasi init` in this repo silently reverts any local rule edits. Fix: compare-then-write (three lines).

**F14. minor / correctness — uninstall drift, `src/clasi/platforms/claude.py:516-559` (same pattern in codex/copilot)** — uninstall enumerates the *currently installed* package's plugin skills/agents/RULES; anything installed by an older clasi whose names have since changed is orphaned. clasr's manifest model already solves this. Fix: fold into F7 direction (manifest-based uninstall).

**F15. minor / quality — `src/clasi/versioning.py:314-346, 195-212, 127-135, 43, 30-31`** — dead surface: `bump_version` (docstring cites a `clasi version bump` command that no longer exists), `sync_version`, `load_version_sync`, `VERSION_PATTERN` (test-only), unused re-exports. Live callers (`artifact_tools.py:41-47`) use only `compute_next_version`, `create_version_tag`, `detect_version_file`, `load_version_trigger`, `should_version`, `update_version_file`. Also `compute_next_version`/`_get_existing_tags` implicitly use `Path.cwd()` while callers pass `project.root` to `detect_version_file` — works only because the MCP server chdirs to the root; thread `project_root` through.

**F16. minor / quality — `src/clasi/worktree.py:351-360`** — for an already-deleted worktree dir, the code re-runs `git worktree remove` (fails on a missing tree) and ignores the error; stale registrations linger. `git worktree prune` is the correct call.

**F17. minor / quality — `src/clasi/cli.py:224-232` vs `:341-352`** — `clasi status` requires `cwd/.clasi` with no upward walk, while `clasi oop` walks up via `_find_project_root`. Inconsistent root discovery (matches the open issue). Fix: use `_find_project_root` in `status` too.

**F18. minor / speed — `src/clasi/cli.py` hook path** — measured: `import click` ≈30 ms, `import clasi.hook_handlers` ≈80 ms total; lazy in-command imports keep `clasi hook` from paying for pydantic/mcp_server. No action needed beyond sprint-027 work; just protect the property (a top-level import of `clasi.mcp_server` anywhere in `hook_handlers` would regress every hook call).

**F19. minor / quality — `pyproject.toml:25-26`** — `pytest` and `pytest-cov` are **runtime** dependencies; every consumer `pip install clasi` drags in the test stack. Move to the `dev` extra.

**F20. minor / quality — `src/clasi/cli.py:8`** — docstring still describes `clasi migrate` as "One-shot docs/clasi/ → .clasi/ migration"; it is now config-driven. Also `src/clasr/cli.py:82` swallows all install exceptions after files are on disk but before the manifest is written (manifest is written last), so a failed clasr install is unreversible by its own uninstall.

## Deletion candidates

| path | lines | why safe | risk |
|---|---|---|---|
| `src/clasi/worktree.py` lines 48-294 + 736-1035 (`create_worktree`, `create_ticket_branch`, `validate_worktree`, `merge_ticket_branch`, `check_independence` + 7 parsing helpers) | ~550 of 1,035 | Unreachable from any live path: only reconcile/cleanup/audit are called (`artifact_tools.py:1385-1442`); parallel execution never ran (`worktree: false` on all sprints 022-027); no MCP tool exposes these | Must also delete Parallel Path sections of `schemas/*/instructions/execution.md` and the sprint `worktree` flag, or the spec re-orphans |
| `tests/clasi/test_worktree.py` (lifecycle portions) + `tests/system/test_worktree_and_planning_integration.py` | ~600 + 620 | Tests of deleted lifecycle functions; keep reconcile/audit tests | Low |
| `src/clasi/platforms/codex.py`, `copilot.py` + their unit tests | 1,126 src + 1,762 tests | Reachable only via explicit `--codex`/`--copilot`; never dogfooded; carry live bugs (F4) and a documented Codex hooks limitation | Product decision — archive to a branch if multi-platform is still a goal |
| `src/clasr/` (entire) **or** `src/clasi/platforms/` (after consolidation per F7) | ~2,430 / ~2,530 (+4,707 test lines in `tests/clasr/`) | Two parallel implementations; clasi imports nothing from clasr | High effort; near-term: freeze one tree and say so in its README |
| `src/clasr/platforms/detect.py` | 72 | Deprecated shim; only its own test calls it | None |
| `src/clasi/versioning.py` dead surface (F15) + tests | ~90 | No callers in `src/` | None |
| `build/` (untracked, gitignored) | 1.8 MB stale package copy | Confuses grep/imports/staleness debugging | None — `rm -rf` |

## Top structural recommendations

1. **Decide the worktree question in one place, then delete ~1,700 lines.** Retire the Parallel Path from execution.md, drop the sprint `worktree` flag, cut worktree.py to the ~350-line reconcile/cleanup/audit core. Biggest single reliability win per hour.
2. **Fix the four destructive installer behaviors (F1-F4) as one small sprint.** Shared root cause — installers overwrite instead of merge/compare; direct mechanism of "init breaks my own repo". Each fix <20 lines.
3. **Add the mtime-based same-version drift signal to `check_staleness` (F6).** ~12 lines; every guard and `get_version` call inherits it.
4. **End the clasi/clasr fork (F7) — first by fiat, then by code.** Declare one tree authoritative now; then port clasi init onto clasr's manifest engine (after fixing F8/F9) or archive clasr.
5. **Unify path/root resolution defaults (F10, F17, F15-cwd).** Make `Project` + `_find_project_root` the single source for issues-dir defaults, status root discovery, and versioning cwd assumptions.
