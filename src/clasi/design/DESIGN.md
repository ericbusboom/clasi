# clasi.design

**Owner:** clasi maintainers · **Last reviewed:** 2026-07-16 · **Status:** in-flux

---

## 1. Purpose

`clasi.design` implements the persistent per-subsystem architecture documentation set introduced in sprint 021: a top-level `docs/design/design.md` plus one design doc per subsystem, plus a frontmattered `README.md` in each subsystem's own source directory. It is a subsystem because it owns a problem nothing else in the codebase owned before this sprint: architecture prose has no stable home, drifts from the code, and is never merged back after a sprint closes. It owns naming, storage, validation, and the sprint-time overlay lifecycle for that doc set — every other module either produces content for it (agents, skills) or orchestrates when its lifecycle hooks fire (sprint lifecycle tools).

## 2. Orientation

Four internal modules, layered with a strict one-way dependency order (innermost first, no cycles):

- `paths.py` — pure functions deriving canonical filenames (`design_doc_slug`, `readme_path_for`, `system_doc_name`) from a subsystem path and the project's configured `sources:` roots. No I/O.
- `store.py` — reads and writes the doc set as `Artifact` objects (`write_design_doc`, `write_readme`, `write_system_doc`, and their `read_*` counterparts, plus `read_doc_set` which enumerates the *expected* doc set from `Project.sources`). Depends only on `paths`.
- `validator.py` — read-only structural/link checks over the doc set produced by `store`, modeled on `clasi.schemas.loader`'s shape (collects every failure, never raises except via the `_or_raise` variant). Depends on `paths` and `store`.
- `overlay.py` — the only module that shells out to git for design-doc purposes; implements the four-step sprint overlay lifecycle (seed-and-commit, generate-diffs, commit-edits, apply). Depends on all three of the above.

`templates/subsystem-design.md` ships as packaged data and is served by `store.subsystem_template()` — the starting point every subsystem doc (including this one) is written from.

## 3. Constraints and Invariants

- **One-way dependency order (paths -> store -> validator -> overlay):** breaking this (e.g. `paths` importing from `store`) reintroduces the coupling this subsystem was split up specifically to avoid. Each module's docstring states its allowed dependencies; keep them true.
- **`store.py` never validates cross-doc consistency and never touches git:** that is deliberately `validator.py`'s and `overlay.py`'s job respectively. Adding validation logic or git calls to `store.py` duplicates responsibility that already has a home.
- **Write functions are full-overwrite, not merge:** `write_design_doc`, `write_readme`, and `write_system_doc` replace the entire file. A caller that must preserve hand-edited content has to read the existing doc first and pass the preserved body through — no merge logic exists in this package, by design (see `store.py`'s module docstring).
- **Filenames and paths are never hand-constructed:** `design_doc_slug` and `readme_path_for` are the only sanctioned way to derive a design-doc path or a README path. This is enforced by convention (the `bootstrap-design` skill states it explicitly) rather than by a runtime check — a caller that joins path segments by hand will not be caught automatically.
- **`overlay.py`'s diff staleness check depends on exact hash agreement with `validator.py`'s `_content_hash`:** the two are independently implemented (duplicated on purpose, per each module's docstring) but must compute identical SHA-256 hashes over identical content, or staleness detection silently breaks.

## 4. Design

**Naming (`paths.py`):** single-source-root projects omit the root name from the slug (`src/clasi/tools/` -> `clasi-tools.md`); multi-root projects include the containing root's name to disambiguate (`tests/e2e/` -> `tests-e2e.md`). This repo is configured with a single root, `src/clasi` (see `.clasi/config.yaml`'s `sources:` — chosen as `src/clasi` rather than `src` so that `_subsystem_dirs` enumerates real subsystems rather than build artifacts like `clasi.egg-info` or the stray top-level `clasr/` directory that also lives under `src/`).

**Storage (`store.py`):** `_subsystem_dirs(root)` enumerates a source root's immediate subdirectories only (hidden dirs and `__pycache__` excluded) — nested directories belong to the subsystem that contains them and never get their own doc. `read_doc_set` walks every configured source root this way and returns `Artifact` handles (not-necessarily-existing) for the system doc, every subsystem doc, and every subsystem README, keyed by subsystem path.

**Validation (`validator.py`):** two independent check groups — canonical doc-set structure (always run: system doc present, one doc per subsystem, bidirectional design-doc<->README links resolve, no orphaned docs, no unmapped source roots) and sprint-overlay checks (run only when an overlay directory is passed: overlay filenames match a canonical doc, overlay frontmatter references resolve, every overlay file has a non-stale `.diff.md`). All checks run to completion and collect every failure rather than stopping at the first, mirroring `clasi.schemas.loader.load`'s behavior.

**Overlay lifecycle (`overlay.py`):** git-anchored, not a custom diff renderer. `seed_and_commit` copies canonical docs into a sprint's `design/` dir and commits them (the pristine baseline); `generate_diffs` compares current content against that same seed-commit baseline (walking git history to the *earliest* commit that touched the file, deliberately without `--follow`, since the seed copy and the canonical doc have unrelated git history) and writes a human-readable fenced-diff `.diff.md` alongside each edited file; `commit_edits` stages and commits only the sprint's `design/` directory; `apply` copies every overlay file over its canonical target, resolving the full mapping before writing anything so a partial apply never happens.

## 5. Interfaces

### Exposes
- **`clasi.design.paths.design_doc_slug(subsystem_path, sources)`:** canonical filename for a subsystem's design doc. Raises `DesignPathError` if the path is not under any declared source root.
- **`clasi.design.store.write_design_doc/write_readme/write_system_doc`:** the only sanctioned way to write doc-set files; sets required frontmatter automatically.
- **`clasi.design.store.read_doc_set(project)`:** enumerates the expected doc set (existing or not) from `project.sources`.
- **`clasi.design.store.subsystem_template()`:** packaged subsystem-doc template text, the required starting point for any new subsystem doc.
- **`clasi.design.validator.validate(project, overlay_dir=None)` / `validate_or_raise`:** structural/link validation; returns a `ValidationResult` (`.ok`, `.messages`) or raises `DesignError` joining all messages with newlines.
- **`clasi.design.overlay.seed_and_commit/generate_diffs/commit_edits/apply`:** the four sprint-lifecycle hook points, called by sprint lifecycle tools (see the `clasi-core` doc's coverage of `sprint.py`/`tools/artifact_tools.py`) at branch creation, pre-execution review, and sprint close respectively.

### Consumes
- **`Artifact` (from `clasi.artifact`):** every read/write in `store.py` wraps an `Artifact` — see the core doc for the frontmatter/body contract it provides.
- **`Project.sources`/`Project.design_dir` (from `clasi.project`):** the only sources of source-root and output-directory configuration; this package never reads `.clasi/config.yaml` directly.
- **Sprint lifecycle git conventions (from `clasi.sprint`/`tools/artifact_tools.py`):** `overlay.py`'s `_run_git` idiom matches the existing inline `subprocess.run` pattern already used elsewhere in the codebase rather than introducing a new git abstraction.

## 6. Open Questions / Known Limitations

- The `bootstrap-design` skill's mechanical subsystem enumeration (`store._subsystem_dirs`) only considers *directories* one level under a source root. `src/clasi` also has a substantial set of loose top-level `.py` files (`agent.py`, `cli.py`, `sprint.py`, `ticket.py`, `mcp_server.py`, etc.) that are not inside any subdirectory and therefore have no mechanical "subsystem" home in this doc set — they cannot get their own `write_design_doc`/`write_readme` pair without either a synthetic directory that doesn't exist on disk (which the validator would then flag as orphaned, since its orphan check is keyed off real subsystem directories) or a change to `_subsystem_dirs`'s contract. This bootstrap run resolved that gap by describing the loose top-level modules narratively inside the system doc (`design.md`) under a `clasi-core` heading, with no dedicated per-file doc or README — this is a skill/tooling gap worth resolving in a future sprint if the loose-file surface grows large enough to need its own maintained doc.
