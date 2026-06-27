---
status: draft
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 013 Use Cases

## SUC-001: Configure artifact locations via paths block
Parent: (new)

- **Actor**: Developer / project owner
- **Preconditions**: A CLASI project is initialized with a `.clasi/config.yaml`.
- **Main Flow**:
  1. Developer adds a `paths:` map to `.clasi/config.yaml` overriding one or
     more category locations (e.g. `issues: myteam/issues`).
  2. Developer runs any CLASI command or MCP tool that resolves artifact paths.
  3. CLASI reads `config.yaml`, extracts the `paths:` map, and resolves each
     category from the override if present, or the built-in default otherwise.
  4. Files are found and operations succeed at the configured locations.
- **Postconditions**: Artifact operations target the user-specified directories.
- **Acceptance Criteria**:
  - [ ] `Project.issues_dir` returns the override path when `paths.issues` is set.
  - [ ] `Project.issues_dir` returns `clasi/issues` when no `paths:` key exists.
  - [ ] A missing or malformed `paths:` key falls back to defaults without error.
  - [ ] All other category properties (`sprints_dir`, `architecture_dir`,
        `reflections_dir`, `design_dir`, `log_dir`, `db_path`) respect the same
        pattern.

## SUC-002: Fresh init writes the new layout
Parent: (new)

- **Actor**: Developer setting up a new project
- **Preconditions**: Empty directory, CLASI installed.
- **Main Flow**:
  1. Developer runs `clasi init` in an empty project directory.
  2. CLASI creates artifact directories using `ARTIFACT_PATH_DEFAULTS`:
     `clasi/issues`, `clasi/sprints`, `clasi/reflections`, `docs/architecture`,
     `docs/design`, `.clasi/log`.
  3. CLASI writes a `paths:` block into `.clasi/config.yaml` matching the
     defaults, so the layout is explicit and re-runnable.
  4. Developer browses `clasi/` and `docs/` and finds all artifact dirs present.
- **Postconditions**: Project has the new visible layout; config records it.
- **Acceptance Criteria**:
  - [ ] `clasi/issues/`, `clasi/sprints/`, `clasi/reflections/` created.
  - [ ] `docs/architecture/` created.
  - [ ] `paths:` block written to `.clasi/config.yaml` using `setdefault`
        (re-running init does not overwrite a custom override).
  - [ ] `.clasi/log/` still created with its `.gitignore`.

## SUC-003: Existing install keeps working without migration
Parent: (new)

- **Actor**: Developer on an existing install (files in `.clasi/`)
- **Preconditions**: CLASI project with files physically in `.clasi/issues`,
  `.clasi/sprints`, `.clasi/architecture`. No `paths:` block in config.
- **Main Flow**:
  1. Developer upgrades CLASI to the Sprint 013 release.
  2. Developer does NOT run `clasi migrate`.
  3. Developer runs `clasi status` or any MCP tool.
  4. CLASI resolves each category from `ARTIFACT_PATH_DEFAULTS` (new defaults:
     `clasi/issues`, etc.). Those directories are absent or empty; `Project`
     read methods guard with `.exists()` and return empty lists.
  5. Developer pins their `.clasi/config.yaml` with the old locations to restore
     full functionality (or runs `clasi migrate` to move files).
- **Postconditions**: No crash; degraded-but-safe behavior until config is pinned
  or migration is run.
- **Acceptance Criteria**:
  - [ ] `Project` methods return empty lists (not exceptions) when configured
        dirs are absent.
  - [ ] `clasi status` does not crash after an upgrade without migration.
  - [ ] Config-pin approach (explicit `paths:` pointing at `.clasi/...`)
        restores full functionality without moving files.

## SUC-004: Detect and migrate misplaced artifacts
Parent: (new)

- **Actor**: Developer whose files are in legacy locations
- **Preconditions**: CLASI project with files at `.clasi/issues` (legacy) but
  configured destination is `clasi/issues`.
- **Main Flow**:
  1. Developer runs `clasi init` (interactive terminal).
  2. After scaffolding, CLASI calls `detect_moves` and finds files in
     `.clasi/issues` that belong in `clasi/issues`.
  3. CLASI prints the proposed moves and asks `"Move files? [y/N]"`.
  4. Developer enters `y`.
  5. `execute_moves` performs `git mv` (or `shutil.move`) for each category,
     rewrites `.gitignore`, cleans up empty parents.
  6. Re-running `clasi init` reports "nothing to do".
- **Postconditions**: Files are at the configured locations; `.gitignore` updated.
- **Acceptance Criteria**:
  - [ ] `detect_moves` returns a `Move` per out-of-place category.
  - [ ] `execute_moves` moves files idempotently (second run is a no-op).
  - [ ] Non-interactive (no TTY) warns only; does not prompt.
  - [ ] `--yes/--relocate` flags trigger migration without a prompt.
  - [ ] `clasi migrate` is a thin wrapper over detect/execute.
  - [ ] Legacy `docs/clasi/` whole-tree case still works.

## SUC-005: Role-guard respects configured artifact paths
Parent: (new)

- **Actor**: Team-lead agent writing a planning artifact
- **Preconditions**: Configured artifact layout may differ from legacy `.clasi/`.
- **Main Flow**:
  1. Team-lead agent attempts a write to `clasi/issues/my-idea.md`.
  2. Role-guard hook fires and checks the write against Project-derived allow
     and block sets.
  3. CLASI allows the write (issues_dir is in the allow set).
  4. Team-lead agent attempts a write directly to `clasi/sprints/013-.../sprint.md`.
  5. Role-guard blocks the write (sprints_dir is in the block set).
- **Postconditions**: Planning writes succeed; direct sprint writes are blocked.
- **Acceptance Criteria**:
  - [ ] Writes to `issues_dir`, `reflections_dir`, `architecture_dir`,
        `design_dir`, `clasi_dir`, `log_dir` are allowed for tier-0.
  - [ ] Writes to `sprints_dir` are blocked for tier-0.
  - [ ] Allow/block sets are derived from live `Project` properties, not
        hardcoded `.clasi/` prefixes.

## SUC-006: Plugin prompts reference the new default paths
Parent: (new)

- **Actor**: Agent reading its prompt/skill markdown
- **Preconditions**: Sprint 013 code is deployed; files may still be at `.clasi/`
  in this repo (backward-compat phase).
- **Main Flow**:
  1. Agent receives its system prompt.
  2. Prompt references `clasi/issues/`, `clasi/sprints/`, `clasi/reflections/`,
     `docs/architecture/` — the new default locations.
  3. Agent directs the user to the correct visible directories.
- **Postconditions**: Prompt paths match the default post-migration layout.
- **Acceptance Criteria**:
  - [ ] All plugin markdown files under `clasi/plugin/` and `.claude/` that
        previously referenced `.clasi/issues`, `.clasi/sprints`,
        `.clasi/reflections`, or `.clasi/architecture` now reference the new
        default paths.
  - [ ] `.clasi/log` references are left unchanged (log stays in `.clasi/`).
