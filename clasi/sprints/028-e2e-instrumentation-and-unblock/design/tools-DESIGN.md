# clasi.tools

**Owner:** clasi maintainers · **Last reviewed:** 2026-07-24 · **Status:** stable

---

## 1. Purpose

`clasi.tools` holds every `@server.tool()`-decorated MCP tool function CLASI exposes to agents: artifact lifecycle operations (sprints, tickets, issues), SE process access (skills, agents, instructions, status), and design-doc-set validation. It is the subsystem boundary between "business logic that manipulates project artifacts" (which mostly lives in `clasi.sprint`/`clasi.ticket`/`clasi.issue`/`clasi.project`, all loose top-level modules) and "the MCP-callable surface an agent actually invokes" — this directory is thin wrappers plus orchestration, not where the artifact classes' own logic lives.

## 2. Orientation

Three modules, split for file-size isolation rather than for a deep conceptual boundary (per `design_tools.py`'s own docstring):

- `artifact_tools.py` — the largest module (roughly 100KB per its sibling's docstring): create/query/update tools for sprints, tickets, issues, and briefs — the bulk of CLASI's MCP surface. Also owns the design-overlay seed path: `seed_sprint_design_overlay` accepts either a bare canonical-doc basename (resolved relative to `docs/design/`, the system-doc/legacy form) or a co-located canonical source path such as `src/firm/app/DESIGN.md` (resolved relative to `project.root`, no `../../` escape — sprint 025's `_resolve_overlay_doc_path`); a co-located path is no longer required to be a bare filename hardcoded against `docs/design/`. A sibling helper, `_derive_overlay_slug`, derives a unique per-doc overlay slug from each co-located path's components relative to its enclosing `project.sources` root (e.g. `src/firm/app/DESIGN.md` -> `firm-app-DESIGN.md`), so multiple subsystems' same-named `DESIGN.md` docs seeded in one call land as distinct overlay files instead of colliding. As of sprint 026, `_close_sprint_full`'s frontmatter-fence-error and sprint-id-mismatch precondition branches also call `db.write_recovery_state(...)` with the offending `sprint.md` path — the same pattern its ticket-not-done branch already used, now applied consistently across all three precondition-failure branches so every recovery instruction `close_sprint` hands out is one role-guard will actually honor.
- `process_tools.py` — read-only tools serving packaged content: `list_agents`/`get_agent_definition`, `list_skills`/`get_skill_definition`, `list_instructions`/`get_instruction`, `list_language_instructions`/`get_language_instruction`, plus `get_version`, `get_status`, `get_use_case_coverage`, and `get_activity_guide`.
- `design_tools.py` — a single tool, `validate_design`, thin-wrapping `clasi.design.validator.validate` so the MCP surface and the `clasi design validate` CLI command share one validation implementation.

## 3. Constraints and Invariants

- **Tools here should not duplicate logic that belongs to an artifact class:** where `Sprint`/`Ticket`/`Issue`/`Project` already own a piece of behavior, the tool function should call it, not reimplement it — `design_tools.validate_design` is the model to follow ("no validation logic is duplicated between the two entry points", per its own docstring).
- **`design_tools.py` was kept separate from `artifact_tools.py` purely for file-size isolation, not a conceptual split:** don't read more architectural intent into that separation than exists; a future refactor could reasonably move design tools into `artifact_tools.py` or vice versa without changing behavior.
- **Every tool function is the literal contract agents depend on:** its docstring is what an agent sees when deciding how to call it (surfaced via MCP tool descriptions) — treat docstring changes here with the same care as a public API change, since it changes what calling agents believe about the tool's behavior.
- **A precondition-failure branch that names a recovery instruction must also write the recovery state that makes it actionable:** `close_sprint`'s three failure branches (frontmatter fence, id mismatch, ticket-not-done) all tell the caller to edit a specific file and retry; as of sprint 026 all three also call `db.write_recovery_state(...)` for that file, not just the one that historically did. A new precondition-failure branch that skips this call reintroduces the exact dead end sprint 026 fixed.
- **A tooling-generated commit must stage exactly the files that tooling step wrote, never a blanket `git add -A`:** as of sprint 027, `_close_sprint_full`'s version-bump step (Step 5) stages only the version file `detect_version_file`/`update_version_file` just modified — and stages/commits nothing if no version file was detected — instead of the `git add -A` it previously used, which had swept an unrelated pre-existing untracked file into a "chore: bump version" commit at sprint 026's own close. This brings Step 5 in line with the explicit-staging pattern Step 5b (three steps later, the `.clasi.db` follow-up commit) already used correctly; any future tooling-generated commit in this function should stage explicitly by the same rule, not reach for `-A`.

## 4. Design

All three modules import `server` and `get_project`/`content_path` from `clasi.mcp_server` (the loose top-level module that owns the actual MCP server instance and stdio transport) and register tools onto that shared `server` object via the `@server.tool()` decorator at import time. None of the three modules constructs its own MCP server.

## 5. Interfaces

### Exposes
- Every MCP tool listed above, registered on import against `clasi.mcp_server.server` — this is CLASI's entire agent-facing tool surface, aside from a small number of tools that may be registered directly in `mcp_server.py` itself.

### Consumes
- **`clasi.mcp_server`** for the `server` singleton and `get_project`/`content_path` helpers.
- **`clasi.sprint.Sprint`, `clasi.ticket.Ticket`, `clasi.issue.Issue`, `clasi.project.Project`** (all loose top-level modules, `clasi-core`) for the actual artifact manipulation each tool wraps.
- **`clasi.design.validate`** (from `clasi.design`, this doc set's own subsystem) for `design_tools.validate_design`.
- **`clasi.versioning`** and **`clasi.templates`** for version-bump and artifact-template support inside `artifact_tools.py`.

## 6. Open Questions / Known Limitations

- `artifact_tools.py`'s size (roughly 100KB) is noted by a sibling module's own docstring as the reason `design_tools.py` was split out; whether `artifact_tools.py` itself should be further split along artifact-type lines (sprint tools / ticket tools / issue tools) is an open question this bootstrap run does not resolve.
