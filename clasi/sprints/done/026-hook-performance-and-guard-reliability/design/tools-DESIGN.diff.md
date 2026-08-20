---
source_file: tools-DESIGN.md
source_hash: d5a6e36ca75c82b8334993fb84f473697d69c2a82c6412f00deaacfe565d1885
---
# Diff: tools-DESIGN.md

Comparison of the sprint overlay copy of `tools-DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- tools-DESIGN.md (pristine)
+++ tools-DESIGN.md (current)
@@ -12,7 +12,7 @@
 
 Three modules, split for file-size isolation rather than for a deep conceptual boundary (per `design_tools.py`'s own docstring):
 
-- `artifact_tools.py` — the largest module (roughly 100KB per its sibling's docstring): create/query/update tools for sprints, tickets, issues, and briefs — the bulk of CLASI's MCP surface. Also owns the design-overlay seed path: `seed_sprint_design_overlay` accepts either a bare canonical-doc basename (resolved relative to `docs/design/`, the system-doc/legacy form) or a co-located canonical source path such as `src/firm/app/DESIGN.md` (resolved relative to `project.root`, no `../../` escape — sprint 025's `_resolve_overlay_doc_path`); a co-located path is no longer required to be a bare filename hardcoded against `docs/design/`. A sibling helper, `_derive_overlay_slug`, derives a unique per-doc overlay slug from each co-located path's components relative to its enclosing `project.sources` root (e.g. `src/firm/app/DESIGN.md` -> `firm-app-DESIGN.md`), so multiple subsystems' same-named `DESIGN.md` docs seeded in one call land as distinct overlay files instead of colliding.
+- `artifact_tools.py` — the largest module (roughly 100KB per its sibling's docstring): create/query/update tools for sprints, tickets, issues, and briefs — the bulk of CLASI's MCP surface. Also owns the design-overlay seed path: `seed_sprint_design_overlay` accepts either a bare canonical-doc basename (resolved relative to `docs/design/`, the system-doc/legacy form) or a co-located canonical source path such as `src/firm/app/DESIGN.md` (resolved relative to `project.root`, no `../../` escape — sprint 025's `_resolve_overlay_doc_path`); a co-located path is no longer required to be a bare filename hardcoded against `docs/design/`. A sibling helper, `_derive_overlay_slug`, derives a unique per-doc overlay slug from each co-located path's components relative to its enclosing `project.sources` root (e.g. `src/firm/app/DESIGN.md` -> `firm-app-DESIGN.md`), so multiple subsystems' same-named `DESIGN.md` docs seeded in one call land as distinct overlay files instead of colliding. As of sprint 026, `_close_sprint_full`'s frontmatter-fence-error and sprint-id-mismatch precondition branches also call `db.write_recovery_state(...)` with the offending `sprint.md` path — the same pattern its ticket-not-done branch already used, now applied consistently across all three precondition-failure branches so every recovery instruction `close_sprint` hands out is one role-guard will actually honor.
 - `process_tools.py` — read-only tools serving packaged content: `list_agents`/`get_agent_definition`, `list_skills`/`get_skill_definition`, `list_instructions`/`get_instruction`, `list_language_instructions`/`get_language_instruction`, plus `get_version`, `get_status`, `get_use_case_coverage`, and `get_activity_guide`.
 - `design_tools.py` — a single tool, `validate_design`, thin-wrapping `clasi.design.validator.validate` so the MCP surface and the `clasi design validate` CLI command share one validation implementation.
 
@@ -21,6 +21,7 @@
 - **Tools here should not duplicate logic that belongs to an artifact class:** where `Sprint`/`Ticket`/`Issue`/`Project` already own a piece of behavior, the tool function should call it, not reimplement it — `design_tools.validate_design` is the model to follow ("no validation logic is duplicated between the two entry points", per its own docstring).
 - **`design_tools.py` was kept separate from `artifact_tools.py` purely for file-size isolation, not a conceptual split:** don't read more architectural intent into that separation than exists; a future refactor could reasonably move design tools into `artifact_tools.py` or vice versa without changing behavior.
 - **Every tool function is the literal contract agents depend on:** its docstring is what an agent sees when deciding how to call it (surfaced via MCP tool descriptions) — treat docstring changes here with the same care as a public API change, since it changes what calling agents believe about the tool's behavior.
+- **A precondition-failure branch that names a recovery instruction must also write the recovery state that makes it actionable:** `close_sprint`'s three failure branches (frontmatter fence, id mismatch, ticket-not-done) all tell the caller to edit a specific file and retry; as of sprint 026 all three also call `db.write_recovery_state(...)` for that file, not just the one that historically did. A new precondition-failure branch that skips this call reintroduces the exact dead end sprint 026 fixed.
 
 ## 4. Design
 
```
