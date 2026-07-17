# clasi.design

**Owner:** clasi maintainers · **Last reviewed:** 2026-07-17 · **Status:** in-flux

---

## 1. Purpose

`clasi.design` implements the persistent per-subsystem architecture documentation set introduced in sprint 021 and retargeted in sprint 022 to a co-located model: a top-level `docs/design/design.md` plus one design doc per subsystem, living directly in that subsystem's own source directory as `<subsystem>/DESIGN.md`. It is a subsystem because it owns a problem nothing else in the codebase owned before sprint 021: architecture prose has no stable home, drifts from the code, and is never merged back after a sprint closes. It owns path resolution, storage, validation, and the sprint-time overlay lifecycle for that doc set — every other module either produces content for it (agents, skills) or orchestrates when its lifecycle hooks fire (sprint lifecycle tools).

## 2. Orientation

Four internal modules, layered with a strict one-way dependency order (innermost first, no cycles):

- `paths.py` — pure functions resolving canonical paths (`design_doc_path_for`, `system_doc_name`) for the system doc and for a subsystem's co-located `DESIGN.md`. No I/O, no slugification, no source-root disambiguation — a subsystem doc's path is always `<subsystem_path>/DESIGN.md`, and that path is the doc's own identity.
- `store.py` — reads and writes the doc set as `Artifact` objects (`write_design_doc`, `write_system_doc`, and their `read_*` counterparts, plus `read_doc_set` which enumerates the *expected* doc set from `Project.sources`). Depends only on `paths`.
- `validator.py` — read-only structural checks over the doc set produced by `store`, modeled on `clasi.schemas.loader`'s shape (collects every failure, never raises except via the `_or_raise` variant). Depends on `paths` and `store`.
- `overlay.py` — the only module that shells out to git for design-doc purposes; implements the four-step sprint overlay lifecycle (seed-and-commit, generate-diffs, commit-edits, apply). Depends on all three of the above.

`templates/subsystem-design.md` ships as packaged data and is served by `store.subsystem_template()` — the starting point every subsystem doc (including this one) is written from. It carries no frontmatter block.

## 3. Constraints and Invariants

- **One-way dependency order (paths -> store -> validator -> overlay):** breaking this (e.g. `paths` importing from `store`) reintroduces the coupling this subsystem was split up specifically to avoid. Each module's docstring states its allowed dependencies; keep them true.
- **`store.py` never validates cross-doc consistency and never touches git:** that is deliberately `validator.py`'s and `overlay.py`'s job respectively. Adding validation logic or git calls to `store.py` duplicates responsibility that already has a home.
- **Write functions are full-overwrite, not merge:** `write_design_doc` and `write_system_doc` replace the entire file. A caller that must preserve hand-edited content has to read the existing doc first and pass the preserved body through — no merge logic exists in this package, by design (see `store.py`'s module docstring).
- **A subsystem doc's path is never hand-constructed, and it carries no frontmatter:** `design_doc_path_for` is the only sanctioned way to derive a subsystem's `DESIGN.md` path — always `<subsystem_path>/DESIGN.md`. There is no backlink to maintain and no slug to derive, so there is nothing to validate in frontmatter for a subsystem doc; `write_design_doc` writes a bare markdown body by default. This is enforced by convention (the `bootstrap-design` skill states it explicitly) rather than by a runtime check.
- **`overlay.apply` resolves canonical targets from a seed-time manifest, never by filename:** because `DESIGN.md` is not a unique filename across subsystems, `seed_and_commit` records each seeded file's canonical source path in `_sources.json` alongside the overlay files, and `apply` reads that manifest to resolve targets. Re-deriving a target from the overlay file's name or a flat target directory would silently misroute a multi-subsystem overlay.
- **`overlay.py`'s diff staleness check depends on exact hash agreement with `validator.py`'s `_content_hash`:** the two are independently implemented (duplicated on purpose, per each module's docstring) but must compute identical SHA-256 hashes over identical content, or staleness detection silently breaks.

## 4. Design

**Path resolution (`paths.py`):** the system doc is always `docs/design/design.md`, resolved under `project.design_dir`, independent of subsystem count. A subsystem doc is always `<subsystem_path>/DESIGN.md` — no slugification, no source-root name, no collision handling, because each subsystem has its own directory and can never collide with another subsystem's doc on a name.

**Storage (`store.py`):** `_subsystem_dirs(root)` enumerates a source root's immediate subdirectories only (hidden dirs and `__pycache__` excluded) — nested directories belong to the subsystem that contains them and never get their own doc. `read_doc_set` walks every configured source root this way and returns `Artifact` handles (not-necessarily-existing) for the system doc and every subsystem's co-located `DESIGN.md`, keyed by subsystem path. `write_design_doc` writes a bare markdown body with no `---` frontmatter block unless a caller explicitly passes `extra_frontmatter`.

**Validation (`validator.py`):** two independent check groups — canonical doc-set structure (always run: system doc present; every subsystem directory has a non-empty co-located `DESIGN.md`; no unmapped source roots; no stray `DESIGN.md` under a source root that isn't a recognized subsystem's own doc path) and sprint-overlay checks (run only when an overlay directory is passed: overlay filenames match a canonical doc's filename, every overlay file has a non-stale `.diff.md`). The five project-level docs alongside the system doc (`overview.md`, `specification.md`, `usecases.md`, `state-machines.md`, `worktree-process.md`) have no frontmatter shape to recognize and are reported as informational entries (`ValidationResult.info`), never as orphan errors. All checks run to completion and collect every failure rather than stopping at the first, mirroring `clasi.schemas.loader.load`'s behavior.

**Overlay lifecycle (`overlay.py`):** git-anchored, not a custom diff renderer. `seed_and_commit` copies canonical docs into a sprint's `design/` dir, records each seeded file's canonical source path in a `_sources.json` manifest written alongside them, and commits both (the pristine baseline); `generate_diffs` compares current content against that same seed-commit baseline (walking git history to the *earliest* commit that touched the file, deliberately without `--follow`, since the seed copy and the canonical doc have unrelated git history) and writes a human-readable fenced-diff `.diff.md` alongside each edited file; `commit_edits` stages and commits only the sprint's `design/` directory; `apply` reads `_sources.json` to resolve each overlay file's canonical target and copies it over that target, resolving the full mapping before writing anything so a partial apply never happens and a multi-subsystem overlay directory holding several files all named `DESIGN.md` still resolves each one to its own distinct subsystem.

## 5. Interfaces

### Exposes
- **`clasi.design.paths.design_doc_path_for(subsystem_path)`:** canonical path for a subsystem's co-located design doc — always `<subsystem_path>/DESIGN.md`.
- **`clasi.design.paths.system_doc_name()`:** the system doc's filename, always `design.md`.
- **`clasi.design.store.write_design_doc/write_system_doc`:** the only sanctioned way to write doc-set files. `write_design_doc` writes no frontmatter unless `extra_frontmatter` is explicitly passed; `write_system_doc` always sets `source_paths`.
- **`clasi.design.store.read_doc_set(project)`:** enumerates the expected doc set (existing or not) from `project.sources`.
- **`clasi.design.store.subsystem_template()`:** packaged subsystem-doc template text (no frontmatter), the required starting point for any new subsystem doc.
- **`clasi.design.validator.validate(project, overlay_dir=None)` / `validate_or_raise`:** structural validation; returns a `ValidationResult` (`.ok`, `.messages`, `.info`) or raises `DesignError` joining all messages with newlines.
- **`clasi.design.overlay.seed_and_commit/generate_diffs/commit_edits/apply`:** the four sprint-lifecycle hook points, called by sprint lifecycle tools (see the `clasi-core` doc's coverage of `sprint.py`/`tools/artifact_tools.py`) at branch creation, pre-execution review, and sprint close respectively.

### Consumes
- **`Artifact` (from `clasi.artifact`):** every read/write in `store.py` wraps an `Artifact` — see the core doc for the frontmatter/body contract it provides.
- **`Project.sources`/`Project.design_dir` (from `clasi.project`):** the only sources of source-root and output-directory configuration; this package never reads `.clasi/config.yaml` directly.
- **Sprint lifecycle git conventions (from `clasi.sprint`/`tools/artifact_tools.py`):** `overlay.py`'s `_run_git` idiom matches the existing inline `subprocess.run` pattern already used elsewhere in the codebase rather than introducing a new git abstraction.

## 6. Open Questions / Known Limitations

- The `bootstrap-design` skill's mechanical subsystem enumeration (`store._subsystem_dirs`) only considers *directories* one level under a source root. `src/clasi` also has a substantial set of loose top-level `.py` files (`agent.py`, `cli.py`, `sprint.py`, `ticket.py`, `mcp_server.py`, etc.) that are not inside any subdirectory and therefore have no mechanical "subsystem" home in this doc set — they cannot get their own `write_design_doc` call without either a synthetic directory that doesn't exist on disk (which the validator would then flag as orphaned, since its orphan check is keyed off real subsystem directories) or a change to `_subsystem_dirs`'s contract. The sprint 021 bootstrap run resolved that gap by describing the loose top-level modules narratively inside the system doc (`design.md`) under a `clasi-core` heading, with no dedicated per-file doc — this is a skill/tooling gap worth resolving in a future sprint if the loose-file surface grows large enough to need its own maintained doc.
- `design_docs:` is a frontmatter linkage field on sprints and tickets (added sprint 022) pointing at the design doc(s) a sprint's overlay touches; this package does not itself read or validate that field — it lives on the sprint/ticket artifact schema, not here.
