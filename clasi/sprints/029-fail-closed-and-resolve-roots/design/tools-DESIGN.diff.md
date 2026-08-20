---
source_file: tools-DESIGN.md
source_hash: 8b4152821ea159e709f68ca46059f1f982e03d7611b984d1bd87a7a1d5d3e1cd
---
# Diff: tools-DESIGN.md

Comparison of the sprint overlay copy of `tools-DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- tools-DESIGN.md (pristine)
+++ tools-DESIGN.md (current)
@@ -12,8 +12,8 @@
 
 Three modules, split for file-size isolation rather than for a deep conceptual boundary (per `design_tools.py`'s own docstring):
 
-- `artifact_tools.py` — the largest module (roughly 100KB per its sibling's docstring): create/query/update tools for sprints, tickets, issues, and briefs — the bulk of CLASI's MCP surface. Also owns the design-overlay seed path: `seed_sprint_design_overlay` accepts either a bare canonical-doc basename (resolved relative to `docs/design/`, the system-doc/legacy form) or a co-located canonical source path such as `src/firm/app/DESIGN.md` (resolved relative to `project.root`, no `../../` escape — sprint 025's `_resolve_overlay_doc_path`); a co-located path is no longer required to be a bare filename hardcoded against `docs/design/`. A sibling helper, `_derive_overlay_slug`, derives a unique per-doc overlay slug from each co-located path's components relative to its enclosing `project.sources` root (e.g. `src/firm/app/DESIGN.md` -> `firm-app-DESIGN.md`), so multiple subsystems' same-named `DESIGN.md` docs seeded in one call land as distinct overlay files instead of colliding. As of sprint 026, `_close_sprint_full`'s frontmatter-fence-error and sprint-id-mismatch precondition branches also call `db.write_recovery_state(...)` with the offending `sprint.md` path — the same pattern its ticket-not-done branch already used, now applied consistently across all three precondition-failure branches so every recovery instruction `close_sprint` hands out is one role-guard will actually honor. As of sprint 028, `get_sprint_phase` (which calls `StateDB.get_sprint_state`, not `detail_sprint`/`get_sprint_status` — neither of those reads DB phase state) additionally returns the sprint's `phase_transitions` history (from `state_db_class.py`'s new table, see the root `DESIGN.md`'s sprint-028 entry) as a timestamped `from_phase`/`to_phase`/`at` list, so per-phase wall time is readable without a direct DB query.
-- `process_tools.py` — read-only tools serving packaged content: `list_agents`/`get_agent_definition`, `list_skills`/`get_skill_definition`, `list_instructions`/`get_instruction`, `list_language_instructions`/`get_language_instruction`, plus `get_version`, `get_status`, `get_use_case_coverage`, and `get_activity_guide`.
+- `artifact_tools.py` — the largest module (roughly 100KB per its sibling's docstring): create/query/update tools for sprints, tickets, issues, and briefs — the bulk of CLASI's MCP surface. Also owns the design-overlay seed path: `seed_sprint_design_overlay` accepts either a bare canonical-doc basename (resolved relative to `docs/design/`, the system-doc/legacy form) or a co-located canonical source path such as `src/firm/app/DESIGN.md` (resolved relative to `project.root`, no `../../` escape — sprint 025's `_resolve_overlay_doc_path`); a co-located path is no longer required to be a bare filename hardcoded against `docs/design/`. A sibling helper, `_derive_overlay_slug`, derives a unique per-doc overlay slug from each co-located path's components relative to its enclosing `project.sources` root (e.g. `src/firm/app/DESIGN.md` -> `firm-app-DESIGN.md`), so multiple subsystems' same-named `DESIGN.md` docs seeded in one call land as distinct overlay files instead of colliding. As of sprint 026, `_close_sprint_full`'s frontmatter-fence-error and sprint-id-mismatch precondition branches also call `db.write_recovery_state(...)` with the offending `sprint.md` path — the same pattern its ticket-not-done branch already used, now applied consistently across all three precondition-failure branches so every recovery instruction `close_sprint` hands out is one role-guard will actually honor. As of sprint 028, `get_sprint_phase` (which calls `StateDB.get_sprint_state`, not `detail_sprint`/`get_sprint_status` — neither of those reads DB phase state) additionally returns the sprint's `phase_transitions` history (from `state_db_class.py`'s new table, see the root `DESIGN.md`'s sprint-028 entry) as a timestamped `from_phase`/`to_phase`/`at` list, so per-phase wall time is readable without a direct DB query. **As of sprint 029**: every git subprocess this module spawns (branch detection, merge, tag push, branch delete, worktree pruning — previously inconsistent, since only the version-bump/db-guard calls passed `cwd=str(project.root)`) routes through the new `gitutil.run_git(args, cwd=project.root)` (see root `DESIGN.md`'s sprint-029 entry), so `close_sprint` always operates on the actual project repository regardless of the server process's own cwd; CLASI-generated commits stage and commit only the specific paths a step just wrote, via explicit pathspecs. `resolve_artifact_path` anchors a relative input path to `project.root` instead of the server process's cwd, so a root-relative ticket path (the natural form an agent passes) no longer produces a spurious "not found" when the server's cwd differs.
+- `process_tools.py` — read-only tools serving packaged content: `list_agents`/`get_agent_definition`, `list_skills`/`get_skill_definition`, `list_instructions`/`get_instruction`, `list_language_instructions`/`get_language_instruction`, plus `get_version`, `get_status`, `get_use_case_coverage`, and `get_activity_guide`. **As of sprint 029**: `resolve_skill_body` — a pure `Load from:`-directive resolver with no dependency on `clasi.mcp_server` — moves out to a new top-level `clasi.skill_resolve` module (see root `DESIGN.md`'s sprint-029 entry); `get_skill_definition`'s three call sites import it back from there. This module's own dependency on `clasi.mcp_server` (`server`/`get_project`/`content_path`, used by its other 15+ tools) is unchanged — only `platforms/claude.py`'s indirect path through this module for one unrelated pure function is removed, which is what let an unbounded `mcp` dependency resolving to `mcp==2.0.0` crash `clasi init` (a CLI command with no business needing FastMCP at all) via this module's own top-level `from clasi.mcp_server import ...`.
 - `design_tools.py` — a single tool, `validate_design`, thin-wrapping `clasi.design.validator.validate` so the MCP surface and the `clasi design validate` CLI command share one validation implementation.
 
 ## 3. Constraints and Invariants
@@ -28,6 +28,19 @@
 
 All three modules import `server` and `get_project`/`content_path` from `clasi.mcp_server` (the loose top-level module that owns the actual MCP server instance and stdio transport) and register tools onto that shared `server` object via the `@server.tool()` decorator at import time. None of the three modules constructs its own MCP server.
 
+**As of sprint 029**: a pure helper with no MCP-server dependency
+(`resolve_skill_body`, previously living in `process_tools.py`) has been
+extracted to a new top-level `clasi.skill_resolve` leaf module so that a
+non-MCP consumer (`platforms/claude.py`'s install path) can use it
+without transitively importing FastMCP. This is a narrow exception to
+this section's own rule, not a reversal of it: `process_tools.py` itself
+still imports `server`/`get_project`/`content_path` from `clasi.mcp_server`
+unconditionally, exactly as every other tool in this package does — only
+one pure, MCP-independent helper function moved out, because its second
+real consumer (the CLI install path) has no business importing an MCP
+server at all. Every `@server.tool()`-decorated function stays where it
+was.
+
 ## 5. Interfaces
 
 ### Exposes
@@ -38,6 +51,8 @@
 - **`clasi.sprint.Sprint`, `clasi.ticket.Ticket`, `clasi.issue.Issue`, `clasi.project.Project`** (all loose top-level modules, `clasi-core`) for the actual artifact manipulation each tool wraps.
 - **`clasi.design.validate`** (from `clasi.design`, this doc set's own subsystem) for `design_tools.validate_design`.
 - **`clasi.versioning`** and **`clasi.templates`** for version-bump and artifact-template support inside `artifact_tools.py`.
+- **`clasi.gitutil`** (new, sprint 029) for every git subprocess this package's tools spawn, always rooted at `project.root`.
+- **`clasi.skill_resolve`** (new, sprint 029), consumed by `process_tools.py`'s `get_skill_definition` for the `Load from:` resolver it no longer defines locally.
 
 ## 6. Open Questions / Known Limitations
 
```
