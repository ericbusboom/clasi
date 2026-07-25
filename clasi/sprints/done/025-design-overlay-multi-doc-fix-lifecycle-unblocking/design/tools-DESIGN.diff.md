---
source_file: tools-DESIGN.md
source_hash: 41448656a395349312de774aa36bfa7f101b3c45beb46c57e7efccc0dbf62ebb
---
# Diff: tools-DESIGN.md

Comparison of the sprint overlay copy of `tools-DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- tools-DESIGN.md (pristine)
+++ tools-DESIGN.md (current)
@@ -1,6 +1,6 @@
 # clasi.tools
 
-**Owner:** clasi maintainers · **Last reviewed:** 2026-07-16 · **Status:** stable
+**Owner:** clasi maintainers · **Last reviewed:** 2026-07-24 · **Status:** stable
 
 ---
 
@@ -12,7 +12,7 @@
 
 Three modules, split for file-size isolation rather than for a deep conceptual boundary (per `design_tools.py`'s own docstring):
 
-- `artifact_tools.py` — the largest module (roughly 100KB per its sibling's docstring): create/query/update tools for sprints, tickets, issues, and briefs — the bulk of CLASI's MCP surface.
+- `artifact_tools.py` — the largest module (roughly 100KB per its sibling's docstring): create/query/update tools for sprints, tickets, issues, and briefs — the bulk of CLASI's MCP surface. Also owns the design-overlay seed path: `seed_sprint_design_overlay` accepts either a bare canonical-doc basename (resolved relative to `docs/design/`, the system-doc/legacy form) or a co-located canonical source path such as `src/firm/app/DESIGN.md` (resolved relative to `project.root`, no `../../` escape — sprint 025's `_resolve_overlay_doc_path`); a co-located path is no longer required to be a bare filename hardcoded against `docs/design/`. A sibling helper, `_derive_overlay_slug`, derives a unique per-doc overlay slug from each co-located path's components relative to its enclosing `project.sources` root (e.g. `src/firm/app/DESIGN.md` -> `firm-app-DESIGN.md`), so multiple subsystems' same-named `DESIGN.md` docs seeded in one call land as distinct overlay files instead of colliding.
 - `process_tools.py` — read-only tools serving packaged content: `list_agents`/`get_agent_definition`, `list_skills`/`get_skill_definition`, `list_instructions`/`get_instruction`, `list_language_instructions`/`get_language_instruction`, plus `get_version`, `get_status`, `get_use_case_coverage`, and `get_activity_guide`.
 - `design_tools.py` — a single tool, `validate_design`, thin-wrapping `clasi.design.validator.validate` so the MCP surface and the `clasi design validate` CLI command share one validation implementation.
 
```
