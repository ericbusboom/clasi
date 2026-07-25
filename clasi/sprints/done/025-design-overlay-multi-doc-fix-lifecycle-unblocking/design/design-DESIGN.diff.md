---
source_file: design-DESIGN.md
source_hash: a64558c81506bd3ecd09c9f6977b67c8de0c0692eeda4b37e58015c1aa81f03d
---
# Diff: design-DESIGN.md

Comparison of the sprint overlay copy of `design-DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- design-DESIGN.md (pristine)
+++ design-DESIGN.md (current)
@@ -1,6 +1,6 @@
 # clasi.design
 
-**Owner:** clasi maintainers · **Last reviewed:** 2026-07-17 · **Status:** in-flux
+**Owner:** clasi maintainers · **Last reviewed:** 2026-07-24 · **Status:** in-flux
 
 ---
 
@@ -25,7 +25,7 @@
 - **`store.py` never validates cross-doc consistency and never touches git:** that is deliberately `validator.py`'s and `overlay.py`'s job respectively. Adding validation logic or git calls to `store.py` duplicates responsibility that already has a home.
 - **Write functions are full-overwrite, not merge:** `write_design_doc` and `write_system_doc` replace the entire file. A caller that must preserve hand-edited content has to read the existing doc first and pass the preserved body through — no merge logic exists in this package, by design (see `store.py`'s module docstring).
 - **A subsystem doc's path is never hand-constructed, and it carries no frontmatter:** `design_doc_path_for` is the only sanctioned way to derive a subsystem's `DESIGN.md` path — always `<subsystem_path>/DESIGN.md`. There is no backlink to maintain and no slug to derive, so there is nothing to validate in frontmatter for a subsystem doc; `write_design_doc` writes a bare markdown body by default. This is enforced by convention (the `bootstrap-design` skill states it explicitly) rather than by a runtime check.
-- **`overlay.apply` resolves canonical targets from a seed-time manifest, never by filename:** because `DESIGN.md` is not a unique filename across subsystems, `seed_and_commit` records each seeded file's canonical source path in `_sources.json` alongside the overlay files, and `apply` reads that manifest to resolve targets. Re-deriving a target from the overlay file's name or a flat target directory would silently misroute a multi-subsystem overlay.
+- **`overlay.apply` resolves canonical targets from a seed-time manifest, keyed by slug, never by filename:** because `DESIGN.md` is not a unique filename across subsystems, `seed_and_commit` takes an optional `slugs` parameter (one per canonical path, defaulting to each path's bare basename when omitted) and records each seeded file's canonical source path in `_sources.json` keyed by that slug, alongside the overlay files. `validator.py`'s overlay check resolves each overlay file's target the same way — via its slug's manifest entry, never via basename-set membership (sprint 025). Re-deriving a target from the overlay file's name or a flat target directory would silently misroute a multi-subsystem overlay.
 - **`overlay.py`'s diff staleness check depends on exact hash agreement with `validator.py`'s `_content_hash`:** the two are independently implemented (duplicated on purpose, per each module's docstring) but must compute identical SHA-256 hashes over identical content, or staleness detection silently breaks.
 
 ## 4. Design
@@ -36,7 +36,7 @@
 
 **Validation (`validator.py`):** two independent check groups — canonical doc-set structure (always run: system doc present; every subsystem directory has a non-empty co-located `DESIGN.md`; no unmapped source roots; no stray `DESIGN.md` under a source root that isn't a recognized subsystem's own doc path) and sprint-overlay checks (run only when an overlay directory is passed: overlay filenames match a canonical doc's filename, every overlay file has a non-stale `.diff.md`). The five project-level docs alongside the system doc (`overview.md`, `specification.md`, `usecases.md`, `state-machines.md`, `worktree-process.md`) have no frontmatter shape to recognize and are reported as informational entries (`ValidationResult.info`), never as orphan errors. All checks run to completion and collect every failure rather than stopping at the first, mirroring `clasi.schemas.loader.load`'s behavior.
 
-**Overlay lifecycle (`overlay.py`):** git-anchored, not a custom diff renderer. `seed_and_commit` copies canonical docs into a sprint's `design/` dir, records each seeded file's canonical source path in a `_sources.json` manifest written alongside them, and commits both (the pristine baseline); `generate_diffs` compares current content against that same seed-commit baseline (walking git history to the *earliest* commit that touched the file, deliberately without `--follow`, since the seed copy and the canonical doc have unrelated git history) and writes a human-readable fenced-diff `.diff.md` alongside each edited file; `commit_edits` stages and commits only the sprint's `design/` directory; `apply` reads `_sources.json` to resolve each overlay file's canonical target and copies it over that target, resolving the full mapping before writing anything so a partial apply never happens and a multi-subsystem overlay directory holding several files all named `DESIGN.md` still resolves each one to its own distinct subsystem.
+**Overlay lifecycle (`overlay.py`):** git-anchored, not a custom diff renderer. `seed_and_commit` copies canonical docs into a sprint's `design/` dir under a per-doc slug filename (an optional `slugs` list, one entry per canonical path; when omitted, each slug defaults to that path's bare basename, preserving prior single-doc behavior), records each seeded file's canonical source path in a `_sources.json` manifest keyed by slug and written alongside them, and commits both (the pristine baseline); `generate_diffs` compares current content against that same seed-commit baseline (walking git history to the *earliest* commit that touched the file, deliberately without `--follow`, since the seed copy and the canonical doc have unrelated git history) and writes a human-readable fenced-diff `.diff.md` alongside each edited file; `commit_edits` stages and commits only the sprint's `design/` directory; `apply` reads `_sources.json` to resolve each overlay file's canonical target by its slug key and copies it over that target, resolving the full mapping before writing anything so a partial apply never happens and a multi-subsystem overlay directory holding several files all named `DESIGN.md` still resolves each one to its own distinct subsystem. `seed_sprint_design_overlay` (the MCP-facing tool in `tools/artifact_tools.py`) is what derives those slugs from co-located canonical source paths before calling `seed_and_commit` — see the `clasi.tools` doc.
 
 ## 5. Interfaces
 
@@ -47,7 +47,7 @@
 - **`clasi.design.store.read_doc_set(project)`:** enumerates the expected doc set (existing or not) from `project.sources`.
 - **`clasi.design.store.subsystem_template()`:** packaged subsystem-doc template text (no frontmatter), the required starting point for any new subsystem doc.
 - **`clasi.design.validator.validate(project, overlay_dir=None)` / `validate_or_raise`:** structural validation; returns a `ValidationResult` (`.ok`, `.messages`, `.info`) or raises `DesignError` joining all messages with newlines.
-- **`clasi.design.overlay.seed_and_commit/generate_diffs/commit_edits/apply`:** the four sprint-lifecycle hook points, called by sprint lifecycle tools (see the `clasi-core` doc's coverage of `sprint.py`/`tools/artifact_tools.py`) at branch creation, pre-execution review, and sprint close respectively.
+- **`clasi.design.overlay.seed_and_commit/generate_diffs/commit_edits/apply`:** the four sprint-lifecycle hook points, called by sprint lifecycle tools (see the `clasi-core` doc's coverage of `sprint.py`/`tools/artifact_tools.py`) at branch creation, pre-execution review, and sprint close respectively. `seed_and_commit` takes an optional `slugs` parameter (sprint 025) to disambiguate multiple co-located `DESIGN.md` docs seeded in the same call.
 
 ### Consumes
 - **`Artifact` (from `clasi.artifact`):** every read/write in `store.py` wraps an `Artifact` — see the core doc for the frontmatter/body contract it provides.
```
