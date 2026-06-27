---
status: in-progress
sprint: '013'
tickets:
- 013-001
---

# Reorganize CLASI files: visible `clasi/` artifacts, `docs/` documents, `src/` code, configurable + self-migrating

## Context

Everything CLASI produces is currently dumped into the **hidden** `.clasi/`
directory — architecture, reflections, issues, sprints, logs, and the state DB —
while only design/overview/spec/usecases live under `docs/design/`. Two problems:

1. **Hidden where the user can't see them.** Issues, sprints, and reflections are
   things a person should be able to browse — but `.clasi/` is a hidden dotdir.
   Architecture is genuinely a *document* and belongs with the other docs.
2. **Hardcoded, not configurable, not repairable.** Every location is hardcoded in
   the `Project` class. There's no way to relocate a category and no way to detect
   or fix an install whose files are in the wrong place. This is already biting us:
   the project reads `uninitialized` because the overview-presence check and the
   real overview location disagree (open issue
   `fix-clasi-overview-path-mismatch-project-reads-as-uninitialized.md`).

**The key move:** the top-level name `clasi/` is currently occupied by the Python
source package. We move the **source down into `src/clasi/`** so the top-level
`clasi/` name is freed to become the **visible artifact directory**. Process
artifacts (issues, sprints, reflections) move into `clasi/`; documents
(architecture, design) live under `docs/`; the hidden `.clasi/` is kept only for
machine state (DB, logs, config). Each major category's location becomes
**configurable** via `.clasi/config.yaml`, and `clasi init`/`migrate` learns to
**detect misplaced files and offer to move them**.

Decisions confirmed with the stakeholder:
- `clasi/` (visible): **issues, sprints, reflections**.
- `docs/` : **architecture** (joins design/overview/spec/usecases already there).
- `.clasi/` (hidden, machine state): **`.clasi.db`, `log/`, `config.yaml`**.
- New layout is the **built-in default** → agent prompts + the write-guard get updated.
- `src/` move happens in the **same effort** (sequenced so it frees `clasi/` before
  artifacts are migrated into it).

## Target end-state layout

```
src/
  clasi/          ← moved from ./clasi   (Python package; `import clasi` unchanged)
  clasr/          ← moved from ./clasr
clasi/            ← NEW visible artifact directory (was the source package name)
  issues/         ← moved from .clasi/issues
  sprints/        ← moved from .clasi/sprints   (tickets/issues nest inside, unchanged)
  reflections/    ← moved from .clasi/reflections
docs/
  design/         overview.md, specification.md, usecases.md, state-machines.md  (unchanged)
  architecture/   ← moved from .clasi/architecture
.clasi/           ← hidden; machine state ONLY
  .clasi.db
  log/
  config.yaml
tests/            (stays at repo root)
build/            (stays at repo root, git-ignored)
```

`.clasi/config.yaml` gains a `paths:` block (defaults shown; omit a key to fall back
to the default, or override to relocate that category). Paths are **relative to the
project root**:

```yaml
process: se
paths:
  issues:        clasi/issues
  sprints:       clasi/sprints
  reflections:   clasi/reflections
  architecture:  docs/architecture
  design:        docs/design
  logs:          .clasi/log
  db:            .clasi/.clasi.db
```

`.clasi/` (the state anchor that holds `config.yaml`) and `.mcp.json` remain fixed
and non-configurable. Keeping `config.yaml` in `.clasi/` means the existing config
reader ([clasi/schemas/__init__.py:30-62](clasi/schemas/__init__.py#L30-L62)) is
untouched.

---

## Phase 1 — Configurable path layer

The single seam: path resolution is already centralized in the `Project` class
([clasi/project.py:30-83](clasi/project.py#L30-L83)). Make each category property
read config, falling back to a central defaults table.

1. **Defaults table** — module-level `ARTIFACT_PATH_DEFAULTS` in
   [clasi/project.py](clasi/project.py) mapping category → root-relative default (the
   YAML above). Single source of truth shared by `Project` (read) and `init` (create)
   so they can't drift. `db` is a file; the rest are directories.
2. **Config loader** — module-level `_load_paths_config(root)` reading
   `root/.clasi/config.yaml`, returning `data.get("paths", {})` only when it's a
   `dict[str,str]`, swallowing missing-file / `YAMLError` / wrong-type into `{}`
   (mirror the graceful pattern already in `schemas/__init__.py`). Leave the
   `process:` reader alone.
3. **Project refactor** — in `__init__` add `self._paths = None` (do **not** read the
   file eagerly — the MCP server reconstructs `Project` per session). Add private
   `_path_config()` (lazy cache) + `_resolve_dir(key)` → `self._root / (config or default)`.
   - `clasi_dir` ([project.py:42](clasi/project.py#L42)) **keeps its current value** `.clasi`
     and now means *the hidden state dir only* (db, log, config). Minimal blast radius —
     existing references to `clasi_dir` for db/log stay correct.
   - Rewrite `issues_dir`, `sprints_dir`, `architecture_dir`, `design_dir`, `log_dir`
     to delegate to `_resolve_dir`. Add **new `reflections_dir`** (created by init today
     but has no property). Add **`db_path`** (`_resolve_dir("db")`) and change `db`
     ([project.py:82](clasi/project.py#L82)) to `StateDB(self.db_path)`. Add a `_db = None`
     reset path so migration can force a reopen.
4. **Route init through the table** — in
   [clasi/init_command.py:199-239](clasi/init_command.py#L199-L239) replace the hardcoded
   `clasi_dir / "issues"`, the `("sprints","architecture","reflections")` loop, and
   `clasi_dir / "log"` with iteration over `ARTIFACT_PATH_DEFAULTS` (build `target_path / rel`).
   Keep per-category `.gitkeep` and the log `.gitignore` special-casing. Write the
   `paths:` block via `config_data.setdefault("paths", ARTIFACT_PATH_DEFAULTS)`
   (`setdefault` so re-running init never clobbers a user's customization). Note
   architecture now creates `docs/architecture` and issues/sprints/reflections create
   under `clasi/`.
5. **Fix hardcoded reads outside `Project`** so they follow config:
   - [clasi/sprint.py](clasi/sprint.py) `project.clasi_dir / "architecture"` → `project.architecture_dir`
   - [clasi/tools/artifact_tools.py:237](clasi/tools/artifact_tools.py#L237) same; `project.clasi_dir / ".clasi.db"` (≈line 1476) → `project.db_path`
   - [clasi/hook_handlers.py](clasi/hook_handlers.py) the ~8 `clasi_dir / ".clasi.db"` → `get_project().db_path`; `base / "log"` → `get_project().log_dir`
   - **Overview-presence fix:** route the `is_overview_present` check through
     `project.design_dir / "overview.md"` (closes the `uninitialized` issue).

Backward compatibility: an install with no `paths:` key resolves each category from
`ARTIFACT_PATH_DEFAULTS` (the new locations). Its physical files, still in `.clasi/`,
become visible only after migration (Phase 3); `Project` read methods already guard
with `.exists()`, so they degrade to empty rather than crash in the meantime.

## Phase 2 — Make the new layout the default for agents (prompts + write-guard)

Two consumers can't read config and must be updated to match the new defaults:

1. **Write-guard (role-guard hook).** [clasi/hook_handlers.py:179-202](clasi/hook_handlers.py#L179-L202)
   currently allows tier-0/team-lead writes only under `.clasi/` (`_clasi_prefix`) and
   blocks `.clasi/sprints/`. With artifacts moving to `clasi/` and `docs/`, rebuild the
   allow/block sets **from `Project` properties** (as it already derives prefixes at
   [lines 183-184](clasi/hook_handlers.py#L183-L184)):
   - **Allow** team-lead writes under: `issues_dir`, `reflections_dir`, `architecture_dir`,
     `design_dir`, and `clasi_dir`/`log_dir` (state). Keep the `.claude/`, `CLAUDE.md`,
     `AGENTS.md` safe prefixes.
   - **Block** `sprints_dir` (sprint artifacts go through MCP tools) and everything else
     (source under `src/`, tests, config).
2. **Plugin prompt markdown.** Grep `\.clasi/(issues|sprints|reflections|architecture)`
   across `clasi/plugin/` and `clasi/plugin/rules/` and rewrite literals to the new
   homes: `.clasi/issues`→`clasi/issues`, `.clasi/sprints`→`clasi/sprints`,
   `.clasi/reflections`→`clasi/reflections`, `.clasi/architecture`→`docs/architecture`.
   Leave `.clasi/log` references alone. Representative files (re-grep for the full set):
   `clasi/plugin/skills/{self-reflect,consolidate-architecture,project-status}/SKILL.md`,
   `clasi/plugin/agents/{sprint-planner/agent.md,team-lead/project-status.md}`,
   `clasi/plugin/instructions/{software-engineering,subagent-protocol}.md`,
   `clasi/plugin/rules/scold-detection.md`. Also check the `.claude/agents/*` and
   `.claude/rules/*` copies in this repo (they mirror the plugin).

## Phase 3 — Detect misplaced artifacts and offer to move them

Generalize the existing one-shot migration
([clasi/migrate_command.py](clasi/migrate_command.py) — already does `docs/clasi/ → .clasi/`
via `git mv` + `shutil.move` fallback, `.gitignore` rewrite, empty-parent cleanup, lock
guard) into a config-driven detect/move:

1. **Candidate-locations table** — per category, an ordered list of legacy/alternate
   places files *could* be today (e.g. issues: `.clasi/issues`, `docs/clasi/issues`;
   architecture: `.clasi/architecture`, `docs/clasi/architecture`; reflections:
   `.clasi/reflections`). Static, owned by the migration code; the *destination* is read
   live from `Project` so it honors a user's custom `paths:`.
2. **`detect_moves(project) -> list[Move]`** (pure) — per category, compare each existing
   candidate against the resolved destination; emit `Move(category, src, dst, mode)` where
   `mode` is `"move"` (dest absent) or `"merge"` (dest populated). Skip when `src == dst`,
   missing, or empty. `is_file` flag for `db`/`config`. Empty list ⇒ nothing to do.
   Doubles as the dry-run preview.
3. **`execute_moves(project, moves, dry_run=)`** — reuse migrate_command's
   `_git_mv`/`shutil.move`, generalized `_update_gitignore` (iterate moves vs. the single
   hardcoded replace), generalized `_check_no_execution_lock` (scan all candidate `.clasi.db`
   locations + dest; refuse if any locked), file-by-file merge that **never clobbers** an
   existing dest file (skip+warn; never merge two `.clasi.db`), empty-parent cleanup,
   and `project._db = None` reset if the DB moved. Fully idempotent.
4. **Wire into `clasi init`** — after scaffolding (after
   [init_command.py:239](clasi/init_command.py#L239)): `detect_moves`; if non-empty and
   interactive (reuse the existing `sys.stdin.isatty() and sys.stdout.isatty()` gate),
   print `"Your files are not in the right spot. Move them to these locations?"` with a
   per-move listing and `click.confirm(default=False)` (the `[y/N]`). Non-interactive
   (MCP/CI, no TTY) → **warn only, don't move**, point at `clasi migrate`. Add `--yes/--relocate`
   on `init` and `migrate` in [clasi/cli.py](clasi/cli.py) for unattended opt-in.
5. **Rewrite `run_migrate`** as a thin wrapper over detect/execute + the existing
   `run_init` refresh and restart notice. Drop the hard "exit if `.clasi/` exists" guard
   (the point is to relocate *into* existing dirs). The legacy `docs/clasi/` whole-tree
   case still works because each category's candidates include `docs/clasi/<category>`.
   Update [tests/unit/test_migrate_command.py](tests/unit/test_migrate_command.py) for the
   changed guard behavior; add `tests/unit/test_relocate.py`.

## Phase 4 — Move source into `src/` (frees the `clasi/` name)

Must land **before** Phase 5 so top-level `clasi/` is empty when artifacts move in.

1. `git mv clasi src/clasi` and `git mv clasr src/clasr`. `tests/`, `build/` stay at root.
2. [pyproject.toml](pyproject.toml): `[tool.setuptools.packages.find]` `where = ["."]`
   → `where = ["src"]` (keep `include = ["clasi*","clasr*"]`). This also stops the
   build from accidentally treating the new top-level artifact `clasi/` as a package.
   `package-data` keys/globs are package-relative — no change. **Coverage `omit`** globs
   (`clasi/cli.py`, etc.) are filesystem paths — change to `*/clasi/...`. `--cov=clasi`,
   `source=["clasi","clasr"]`, `[project.scripts]` are import-name based — no change.
3. **⚠ Import-shadowing — the new risk introduced by this layout.** A top-level
   `clasi/` artifact dir (no `__init__.py`) sits next to the `src/clasi` package. With a
   modern editable install (`pip/uv install -e .`, setuptools ≥64) the editable
   **meta-path finder** resolves `import clasi` to `src/clasi` *before* the path-based
   finder ever looks at the cwd, so there is no shadow. The danger is running tests/tools
   against an **uninstalled** tree (cwd on `sys.path`, `./clasi/` found first as a
   namespace package). Mitigation: require the editable install to be present (this repo's
   convention already installs tools editable per `.claude/rules/git-commits.md`); ensure
   CI does `pip install -e .` before `pytest`; add a smoke test asserting `import clasi.cli`
   resolves under `src/`. Verify against a **built wheel**, not just editable.
4. **Verify `__file__`-relative asset resolution.** Most modules use
   `Path(__file__).parent` and track the move. The one to prove is the triple-`parent`
   `_PACKAGE_ROOT` in [clasi/tools/process_tools.py](clasi/tools/process_tools.py) that
   resolves `Load from: clasi/schemas/...` directives — after the move it resolves to
   `src/` and the `clasi/` prefix in the directive keeps it correct; prove against the wheel.
5. Update agent write-scope globs `clasi/**` → `src/clasi/**` (+ `src/clasr/**`):
   `clasi/platforms/claude.py`, `.claude/rules/source-code.md`,
   `.github/instructions/source-code.instructions.md`. Regenerate `clasi.egg-info` by rebuild.

## Phase 5 — Migrate this repo's own artifacts (dogfood)

After Phases 1-4 land (source now in `src/`, so top-level `clasi/` is free), run the new
migration on this repo:
- `.clasi/issues/` → `clasi/issues/`
- `.clasi/sprints/` → `clasi/sprints/` (tickets/issues nest along)
- `.clasi/reflections/` → `clasi/reflections/`
- `.clasi/architecture/` (11 update docs) → `docs/architecture/`
- `.clasi/log/`, `.clasi/.clasi.db`, `.clasi/config.yaml` stay put.

Use the executor (`git mv`). Then verify `clasi status` no longer reports `uninitialized`
and that sprint-close / consolidate-architecture / project-status still resolve every
category.

---

## Files to modify (summary)

| File | Change |
|---|---|
| [clasi/project.py](clasi/project.py) | `ARTIFACT_PATH_DEFAULTS`, `_load_paths_config`, `_resolve_dir`; delegate category props; keep `clasi_dir`=`.clasi` (state only); add `reflections_dir` + `db_path` |
| [clasi/init_command.py](clasi/init_command.py) | Create dirs from the table; write `paths:` block; wire post-scaffold detect/confirm |
| [clasi/migrate_command.py](clasi/migrate_command.py) | Generalize helpers; `detect_moves`/`execute_moves`; rewrite `run_migrate`; drop `.clasi/`-exists guard |
| [clasi/cli.py](clasi/cli.py) | `--yes/--relocate` on `init` + `migrate` |
| [clasi/hook_handlers.py](clasi/hook_handlers.py) | Rebuild role-guard allow/block sets from `Project` props (allow `clasi/issues`, `clasi/reflections`, `docs/architecture`, `docs/design`, `.clasi/`; block `clasi/sprints`); route DB/log through `Project` |
| [clasi/sprint.py](clasi/sprint.py), [clasi/tools/artifact_tools.py](clasi/tools/artifact_tools.py) | Replace hardcoded `clasi_dir / "architecture"` and `/ ".clasi.db"` with `Project` props |
| `clasi/plugin/**`, `.claude/{agents,rules}/**` | Rewrite `.clasi/{issues,sprints,reflections,architecture}` literals to new homes |
| [pyproject.toml](pyproject.toml) | `where=["src"]`; coverage `omit` globs `*/clasi/...` |
| Source tree | `git mv clasi src/clasi`, `git mv clasr src/clasr` |
| `tests/unit/` | Update `test_migrate_command.py`; add `test_relocate.py`, path-config + role-guard tests |

## Verification

1. **Unit/integration:** `pytest` green; coverage `fail_under` still met after the src/ move.
2. **Config resolution:** with no `paths:` key, `Project(...).issues_dir` → `clasi/issues`,
   `architecture_dir` → `docs/architecture`; a custom `paths:` override is followed.
3. **Fresh init (interactive):** `clasi init` in a scratch dir writes the `paths:` block and
   creates `clasi/{issues,sprints,reflections}`, `docs/{architecture,design}`, `.clasi/{log,config.yaml}`.
4. **Detect & migrate:** seed a scratch repo with files at `.clasi/issues`, `.clasi/architecture`,
   and legacy `docs/clasi/`; run `clasi init` → the `[y/N]` prompt lists the moves; yes → files
   land in `clasi/`/`docs/`, `.gitignore` rewritten, empty parents cleaned; re-run → "nothing to do".
   Non-interactive run warns only.
5. **Import shadow:** from the repo root, `python -c "import clasi.cli, clasi; print(clasi.__file__)"`
   resolves under `src/clasi/` (not the top-level artifact `clasi/`). Confirm `pytest` collects
   and imports cleanly.
6. **Built wheel (src/ move):** `python -m build`, unzip → `clasi/plugin/` + `clasi/schemas/`
   present; `pip install` into a clean venv → `clasi mcp` smoke + a skill `Load from:` resolution succeed.
7. **Role-guard:** as team-lead, a write to `clasi/issues/x.md` and `docs/architecture/x.md` is
   allowed; a write to `clasi/sprints/...` artifact is blocked.
8. **Dogfood:** migrate this repo; `clasi status` no longer reports `uninitialized`; MCP
   `get_status`/sprint tools still resolve artifacts.

## CLASI process note

This is feature work on the CLASI project itself. After approval, the natural path is to
capture it as a CLASI issue, then plan one sprint with tickets matching Phases 1→5 (Phase 4
before Phase 5). The existing `fix-clasi-overview-path-mismatch-...` issue is subsumed by
Phase 1's overview-presence fix.
