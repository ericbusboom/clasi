---
sprint: "003"
status: draft
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 003 Use Cases

## SUC-001: Consolidate Agent Definitions into Package Data

**Actor**: Developer / `clasi init`

**Preconditions**:
- `plugin/` exists at the repo root with 3 agents and 27 skills
- `clasi/agents/` exists with 13 agents in a 3-tier hierarchy
- `clasi/init_command.py` references `_PLUGIN_DIR` as a sibling of `clasi/`

**Main Flow**:
1. Developer runs `clasi init` in a target project.
2. The system reads agent and skill content from `clasi/plugin/` (inside the package).
3. Agent and skill files are copied to the target project's `.claude/` directory.
4. The installed agents and skills are identical to those from the old `plugin/` layout.

**Postconditions**:
- `plugin/` at the repo root no longer exists.
- `clasi/plugin/` contains all previously-installed content.
- `_PLUGIN_DIR` in `init_command.py` resolves to `clasi/plugin/`.
- `clasi/agents/` is removed or reduced to only what `contracts.py` actively uses.
- No duplicate agent definitions for sprint-planner, team-lead, or programmer.

**Error Flows**:
- If `clasi/plugin/` is missing at install time, `clasi init` prints a warning and
  skips content installation (existing fallback behavior preserved).

---

## SUC-002: Project Initiation Outputs to docs/clasi/design/

**Actor**: Team-lead (via `project-initiation` skill)

**Preconditions**:
- A stakeholder specification file exists.
- No `overview.md`, `specification.md`, or `usecases.md` exist yet.

**Main Flow**:
1. Team-lead invokes the `project-initiation` skill.
2. Skill dispatches to a subagent to write design documents.
3. Subagent writes `overview.md`, `specification.md`, and `usecases.md` to
   `docs/clasi/design/`.
4. `create_overview` MCP tool is called to register the overview.

**Postconditions**:
- All three design documents exist under `docs/clasi/design/`.
- No documents written to alternate locations (e.g., repo root, `docs/clasi/`).

**Error Flows**:
- If `docs/clasi/design/` does not exist, the subagent creates it.

---

## SUC-003: Project Initiation Dispatches to Subagent

**Actor**: Team-lead

**Preconditions**:
- Team-lead is invoked for a new project with no existing design documents.

**Main Flow**:
1. Team-lead reads the `project-initiation` skill instructions.
2. Skill instructs team-lead to dispatch to the sprint-planner agent (or a dedicated
   initiation agent) via the Agent tool.
3. Team-lead does NOT write `overview.md`, `specification.md`, or `usecases.md`
   directly.
4. The dispatched subagent writes all three documents and calls `create_overview`.
5. Team-lead receives confirmation and continues the SE process.

**Postconditions**:
- Team-lead's "never write content directly" rule is not violated.
- Design documents are created by a subagent, not by the team-lead itself.

**Error Flows**:
- If the subagent fails, team-lead reports the error to the stakeholder.

---

## SUC-004: Sprint Planner Backfills Ticket Summary in sprint.md

**Actor**: Sprint-planner agent

**Preconditions**:
- Sprint is in the `ticketing` phase.
- Tickets have been created via `create_ticket` MCP tool.

**Main Flow**:
1. Sprint-planner creates all tickets in dependency order.
2. Sprint-planner reads back the created ticket IDs, titles, and depends-on values.
3. Sprint-planner computes parallel execution groups via topological ordering:
   - Group 1: tickets with no dependencies
   - Group 2: tickets depending only on Group 1
   - Group N: tickets depending only on Groups 1..N-1
4. Sprint-planner updates the `## Tickets` section of `sprint.md` with the populated
   summary table.

**Postconditions**:
- `sprint.md` `## Tickets` section contains a table: `| # | Title | Depends On | Group |`
- Every created ticket appears in the table.
- Stakeholder can read `sprint.md` to understand the full ticket plan without opening
  individual ticket files.

**Error Flows**:
- If circular dependencies exist, sprint-planner flags the issue and does not create
  a table (reports error to team-lead instead).
