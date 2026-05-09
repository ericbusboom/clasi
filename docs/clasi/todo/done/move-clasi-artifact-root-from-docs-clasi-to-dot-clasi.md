---
status: done
sprint: '015'
tickets:
- 015-006
- 015-007
- 015-008
- 015-009
- 015-010
- 015-011
- 015-012
- 015-015
- 015-016
- 015-021
---

# Move CLASI artifact root from `docs/clasi/` to `.clasi/`

Relocate the CLASI artifact root in target projects (and in this source repo, which is itself a CLASI project) from `docs/clasi/` to `.clasi/`. The `docs/` tree should be reserved for genuine project documentation; CLASI's runtime/process artifacts (sprints, issues, architecture updates, dispatch logs, state DB, design docs) belong in a hidden top-level directory like `.git/` or `.vscode/`.

This TODO is the umbrella migration that the [rename-clasi-todos-to-issues](rename-clasi-todos-to-issues.md) and [consolidate-the-clasi-version-marker-into-clasi-clasi-version](consolidate-the-clasi-version-marker-into-clasi-clasi-version.md) TODOs both depend on for moving real artifacts on disk.

## Motivation

- `docs/clasi/` mixes process artifacts with user-authored documentation in the same tree, which is confusing and pollutes `docs/` for projects that publish a `docs/` site.
- `.clasi/` is consistent with the just-decided `.clasi/clasi-version` marker location and parallels established hidden-config conventions (`.git/`, `.vscode/`, `.github/`).
- The move forces a clean cut on path-coupling: every reference to `docs/clasi/` becomes a single grep target.

## Scope and decisions to lock in (open questions for the planner)

- **Final path**: `.clasi/` at the project root.
- **Subdirectory layout under `.clasi/`**:
  ```
  .clasi/
    AGENTS.md
    .clasi.db
    clasi-version          # from the version-marker TODO
    sprints/
    issues/                # was todo/, renamed by the rename-todos-to-issues TODO
    architecture/
    log/
    reflections/
  ```
- **Design docs stay under `docs/`** (locked-in decision). `design/` is treated as canonical user documentation, not a CLASI process artifact. It does NOT move into `.clasi/`. `Project.design_dir` is updated from `self.clasi_dir / "design"` → `self._root / "docs" / "design"`. This matches the actual layout in this source repo today (where `docs/design/` already exists and `Project.design_dir` is currently broken pointing at the empty `docs/clasi/design/`). For target projects that have a populated `docs/clasi/design/`, the migration step moves it to `docs/design/` (not `.clasi/design/`).
- **Visibility / discoverability**: a hidden `.clasi/` is fine for tooling but reduces casual discoverability. Mitigation: README points at `.clasi/`; `clasi project-status` prints the path; the Codex `AGENTS.md` rule files inside `.clasi/` still get auto-loaded by Codex sessions.

## Surface area to update (~160 references)

**Python source — path constants**

- `clasi/project.py:28-29` — `clasi_dir` returns `self._root / "docs" / "clasi"` → `self._root / ".clasi"`. All derived properties (`design_dir`, `sprints_dir`, `issues_dir` (post-rename), `log_dir`, `architecture_dir`, `db`) inherit the change automatically.
- `clasi/hook_handlers.py` — ~14 occurrences of `Path("docs/clasi…")` and `file_path.startswith("docs/clasi/…")` strings (lines 50, 133, 152, 175–191, 239, 273, 279, 319, 417, 446, 558, 589, 872, 892). Replace with `Path(".clasi/…")` / `.startswith(".clasi/")`.
- `clasi/cli.py:103` — `--todo-dir` default `"docs/clasi/todo"` → `".clasi/issues"` (combines with the rename TODO).
- `clasi/cli.py:108` — help text.
- `clasi/init_command.py:205,214` — echoed paths.
- `clasi/versioning.py:3,192,214,222` — docstrings reference `docs/clasi/settings.yaml`.
- `clasi/sprint.py:404`, `clasi/todo.py:15`, `clasi/tools/artifact_tools.py:161,183,1366` — docstrings/comments.

**Platform installers**

- `clasi/platforms/_rules.py` — five rule bodies mention `docs/clasi/oop`, `docs/clasi/sprints/` in prose (lines 18, 28, 38, 47, 53, 66). The OOP override file moves to `.clasi/oop`; update `.gitignore` template too.
- `clasi/platforms/claude.py:51,57` — YAML frontmatter `paths: ["docs/clasi/**"]` and `paths: ["docs/clasi/todo/**"]`.
- `clasi/platforms/codex.py:264-397` — `_build_docs_clasi_content`, `_build_todo_dir_content`, `_install_rules`, `_uninstall_rules`. Function names should also drop the `docs_` infix. Three nested `AGENTS.md` files installed at `target/.clasi/AGENTS.md`, `target/.clasi/issues/AGENTS.md`, `target/clasi/AGENTS.md` (the third is unrelated, leave it).
- `clasi/platforms/copilot.py:208-209` — path-rules tuples for the `applyTo` glob.

**Templates and rule prose**

- `clasi/plugin/skills/*/SKILL.md` — 14 skill files contain ~36 references; each prose mention of `docs/clasi/…` becomes `.clasi/…`.
- `clasi/plugin/agents/team-lead/agent.md`, `team-lead/project-status.md`, `clasi/plugin/instructions/subagent-protocol.md`, `clasi/plugin/rules/*` — ~12 references.
- `clasi/AGENTS.md`, `clasi/se-overview-template.md` — body prose.

**Project root rule/agent files (this repo)**

These get **regenerated** by `clasi install`, but they're checked into source control here, so they need to be re-rendered after the installer changes:
- `.claude/rules/*.md`
- `.github/instructions/*.instructions.md` — including the `applyTo:` frontmatter that scopes the rule to a glob.
- `.github/agents/*.agent.md`
- `.github/copilot-instructions.md`
- `.codex/agents/*.toml` (if any reference the path)
- `AGENTS.md`, `README.md` (manual edits — README has 6 hits at lines 63, 89, 99, 129, 160, 279).

**Tests** — 75 references across 9 files

- `tests/unit/test_hook_handlers.py` (12)
- `tests/unit/test_platform_codex.py` (29) — heaviest
- `tests/unit/test_dispatch_log.py` (14)
- `tests/unit/test_three_platform_install.py` (5)
- `tests/unit/test_uninstall_command.py` (3)
- `tests/unit/test_platform_copilot.py` (2)
- `tests/unit/test_todo_tools.py` (1)
- `tests/system/test_artifact_tools.py` (3)
- `tests/clasr/test_platform_codex.py` (6)

Most are hardcoded path strings or `tmp_path / "docs" / "clasi"` builders; a handful set up fixture trees that need restructuring.

**`.gitignore`**

- Line 62: `docs/clasi/log/` → `.clasi/log/`. Also revisit `.clasi.db` and `.clasi-oop` entries; the new `.clasi/` directory itself should NOT be gitignored, but `.clasi/log/` and `.clasi/.clasi.db` should remain ignored.

## On-disk migration of this repo

After the code change lands, this source repo's own artifacts must move:

```
git mv docs/clasi .clasi
```

then verify that:
- `.clasi/sprints/done/` keeps its 14 historical sprint dirs intact (their inner ticket markdown bodies still reference `docs/clasi/…` in prose — leave those archives untouched).
- `.clasi/.clasi.db` is at the new path (any open clasi session must be restarted).
- `.gitignore` updates land in the same commit so `.clasi/log/` stays ignored and the new path doesn't accidentally pull in dispatch logs.

## Migration for downstream projects

`clasi/init_command.py` and the platform installers will create `.clasi/` for new projects. For existing projects on the old layout, add `clasi migrate` (one-shot subcommand) that:

1. Verifies no sprint is mid-execution (no execution lock held).
2. `git mv docs/clasi .clasi` (or non-git mv if the project isn't a git repo).
3. Updates `.gitignore` entries.
4. Re-runs `clasi install --force` to refresh rule files / agent prompts with the new globs.
5. Prints a one-line note to update any user-customized references in their own docs.

## Coordination with sibling TODOs

- [rename-clasi-todos-to-issues.md](rename-clasi-todos-to-issues.md) — when this umbrella migration runs, the `todo/` subdir is *also* renamed to `issues/`. The rename-issues TODO assumed this work would handle on-disk migration; do both at once or sequence the rename TODO immediately before this one with directory moves deferred.
- [consolidate-the-clasi-version-marker-into-clasi-clasi-version.md](consolidate-the-clasi-version-marker-into-clasi-clasi-version.md) — already targets `.clasi/clasi-version`; that TODO can land first, second, or together with this one. Either way, the marker file ends up at `.clasi/clasi-version`.
- Recommend bundling all three into one sprint, or running them in this order: version-marker (smallest) → rename-issues → root move. The root move is the largest blast radius and should land last so test-suite churn happens once.

## Not in scope

- Touching ticket markdown bodies inside `.clasi/sprints/done/**` or completed `issues/done/**` — those are historical artifacts.
- Backward-compat dual-path reads. Hard cut over.
- Authoring new design content. This TODO only relocates existing design files; the design-docs workflow is unchanged.

## Acceptance criteria

- `grep -rn "docs/clasi" clasi/ tests/ .claude/ .github/ AGENTS.md README.md` returns zero hits (historical references inside `.clasi/sprints/done/**` and `.clasi/issues/done/**` are exempt and may remain).
- `clasi install` on a fresh target creates `.clasi/` (not `docs/clasi/`).
- This source repo's own artifacts have moved to `.clasi/` and `clasi project-status` runs successfully against them.
- Full test suite passes.
- `clasi migrate` (or equivalent) successfully relocates a project from `docs/clasi/` to `.clasi/` and a smoke test against `rundbat`/`dotconfig` confirms the migration is clean.
- README documents the new layout and explains the `.clasi/` vs `docs/` distinction.
