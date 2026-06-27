---
status: approved
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 006 Use Cases

## SUC-001: Human or agent queries project status via CLI

- **Actor**: Developer or agent (any role)
- **Preconditions**: A CLASI-initialized project exists; the `clasi` CLI is installed.
- **Main Flow**:
  1. User runs `clasi status` (optionally with `--agent`, `--sprint`, `--ticket`, `--format` flags).
  2. CLI resolves the agent role (flag > `$CLASI_AGENT_NAME` > `team-lead`).
  3. CLI instantiates `ClasiStateReader` against the current project root.
  4. Status reporter evaluates state machines for project, all sprints, and relevant tickets.
  5. CLI serializes and prints the result as YAML (default) or JSON.
- **Postconditions**: Output matches the defined output shape with `agent:`, `project:`, `sprints:`, `issues:`, `notes:`, and `inconsistencies:` sections.
- **Acceptance Criteria**:
  - [ ] `clasi status` prints valid YAML with all required top-level keys.
  - [ ] `clasi status --format json` prints valid JSON with the same shape.
  - [ ] Role defaults to `team-lead` when no flag or env var is set.

---

## SUC-002: Team-lead gets full project-wide status

- **Actor**: Team-lead agent
- **Preconditions**: Project is CLASI-initialized; one or more sprints exist.
- **Main Flow**:
  1. Team-lead calls `clasi status` or `get_status()` with agent=`team-lead`.
  2. Status reporter evaluates all three machines for the project and every sprint and its tickets.
  3. Full output is returned: project block, all sprints with ticket details, issues summary, notes, inconsistencies.
- **Postconditions**: Team-lead can see every sprint's state, every in-progress ticket's available transitions, and any blocking predicates.
- **Acceptance Criteria**:
  - [ ] Output includes `project:`, `sprints:` (all sprints), `issues:`, `notes:`, `inconsistencies:`.
  - [ ] Each sprint entry includes `state:`, `available_transitions:`, and `tickets:` with `total`, `by_state`, and `details` for non-done tickets.

---

## SUC-003: Sprint-planner gets narrowed view for one sprint

- **Actor**: Sprint-planner agent
- **Preconditions**: Sprint-planner is executing for a specific sprint.
- **Main Flow**:
  1. Sprint-planner calls `clasi status --agent sprint-planner --sprint 006` or equivalent.
  2. Status reporter returns the `project:` block plus the matching sprint entry with summarized tickets (no per-ticket `details:`).
  3. Other sprints are excluded.
- **Postconditions**: Sprint-planner sees its sprint's state, fireable transitions, and ticket summary without noise from other sprints.
- **Acceptance Criteria**:
  - [ ] Output contains `project:` and exactly one sprint under `sprints:`.
  - [ ] `tickets:` has `total` and `by_state` but no `details:` list.
  - [ ] `notes:` is recomputed against the narrowed scope.
  - [ ] If `--sprint` is omitted, fallback note is included and broadest available view is returned.

---

## SUC-004: Programmer gets ticket-focused view

- **Actor**: Programmer agent
- **Preconditions**: Programmer is executing a specific ticket.
- **Main Flow**:
  1. Programmer calls `clasi status --agent programmer --ticket 006-003` or equivalent.
  2. Status reporter returns the `project:` block (read-only context), the parent sprint in summary form, and the single ticket under `tickets.details`.
  3. `notes:` focuses on that ticket's transitions.
- **Postconditions**: Programmer knows exactly what transitions are available for their ticket and what is blocking them.
- **Acceptance Criteria**:
  - [ ] Output contains `project:` (read-only), one sprint summary, one ticket detail.
  - [ ] Ticket detail includes `state:`, `available_transitions:`, and per-transition `fireable:` and `blocked_by:` lists.
  - [ ] If `--ticket` is omitted, fallback note is included.

---

## SUC-005: Agent receives auto-injected status context at session start

- **Actor**: Any CLASI agent (team-lead, sprint-planner, programmer)
- **Preconditions**: `UserPromptSubmit` or `SubagentStart` hook is configured; project is CLASI-initialized; `.clasi/oop` does not exist.
- **Main Flow**:
  1. Claude Code fires `UserPromptSubmit` (or `SubagentStart` for subagents) hook.
  2. Hook handler reads `$CLASI_AGENT_NAME` to determine role; defaults to `team-lead`.
  3. Handler calls the status reporter and prepends a `## CLASI status` YAML fenced block to the hook output.
  4. Agent receives status in its context window automatically.
- **Postconditions**: Every agent session starts with the current project state without manual `clasi status` invocation.
- **Acceptance Criteria**:
  - [ ] `UserPromptSubmit` hook output contains a `## CLASI status` block with valid YAML.
  - [ ] `SubagentStart` hook output contains the same block scoped to the agent's role.
  - [ ] If `.clasi/oop` exists, the hook exits 0 and emits nothing.
  - [ ] If the project is not CLASI-initialized (no `.clasi/`), the hook exits 0 silently.

---

## SUC-006: MCP tool returns structured status for agent tool calls

- **Actor**: Any CLASI agent calling MCP tools
- **Preconditions**: The CLASI MCP server is running.
- **Main Flow**:
  1. Agent calls `get_status(agent="team-lead")` (or with `sprint_id` / `ticket_id`).
  2. MCP server instantiates `ClasiStateReader`, runs status reporter, and returns JSON.
- **Postconditions**: Agent receives the same status shape as the CLI, as structured JSON suitable for programmatic use.
- **Acceptance Criteria**:
  - [ ] `get_status()` returns valid JSON matching the output shape.
  - [ ] `get_status(agent="sprint-planner", sprint_id="006")` returns the narrowed sprint-planner view.
  - [ ] `get_status(agent="programmer", ticket_id="006-003")` returns the programmer ticket view.

---

## SUC-007: Inconsistency between declared and computed state is reported

- **Actor**: Any consumer of `clasi status`
- **Preconditions**: A sprint or ticket artifact has a `status:` frontmatter value that contradicts the state machine's computed state.
- **Main Flow**:
  1. Status reporter computes the state machine state for an artifact.
  2. Reporter reads the declared `status:` from the artifact's frontmatter.
  3. If they disagree, an entry is added to `inconsistencies:` with `kind: state_drift`, the `declared` and `computed` values, and an explanation listing the failing predicates.
- **Postconditions**: The inconsistency is visible in all three output surfaces (CLI, MCP, hook).
- **Acceptance Criteria**:
  - [ ] An artifact whose frontmatter `status:` disagrees with computed state produces a `state_drift` entry.
  - [ ] The `explanation:` field names the specific predicates that failed.
  - [ ] Consistent artifacts produce an empty `inconsistencies: []` list.
