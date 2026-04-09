---
status: draft
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 004 Use Cases

## SUC-001: Hook Event Dispatched via CLI Without Python Scripts

- **Actor**: Claude Code harness (automated, fires on lifecycle events)
- **Preconditions**: CLASI is installed via pipx; `clasi` is on PATH; a CLASI
  project has been initialized with `clasi init`
- **Main Flow**:
  1. Claude Code fires a lifecycle event (e.g., SubagentStart)
  2. The harness reads `settings.json` and finds `"command": "clasi hook subagent-start"`
  3. The harness invokes `clasi hook subagent-start` with the event JSON on stdin
  4. The CLI routes to `handle_hook("subagent-start")`
  5. `handle_hook` reads stdin, dispatches to `handle_subagent_start(payload)`
  6. The handler performs its action and exits 0
- **Postconditions**: Hook action is performed; no Python script was invoked
- **Acceptance Criteria**:
  - [ ] All seven event names route correctly through `handle_hook()`
  - [ ] `clasi hook <event>` exits 0 for well-formed payloads
  - [ ] `clasi hook <event>` exits 2 for blocking events (role-guard violation)
  - [ ] No `.py` files exist in `.claude/hooks/`
  - [ ] `clasi/plugin/hooks/` contains only `hooks.json` (no `.py` files)

## SUC-002: clasi init Always Installs Current Hook Commands

- **Actor**: Developer running `clasi init` on an existing project
- **Preconditions**: Project already has `.claude/settings.json` with old
  `python3 .claude/hooks/foo.py` commands
- **Main Flow**:
  1. Developer runs `clasi init` (or `clasi init .`)
  2. `init_command.py` reads the existing `settings.json`
  3. The hooks section is overwritten with the canonical `clasi hook <event>`
     commands from `hooks.json`
  4. The updated `settings.json` is written back
  5. Init prints "Updated: .claude/settings.json (hooks)"
- **Postconditions**: `settings.json` hooks section contains only
  `clasi hook <event>` commands; no `python3` commands remain
- **Acceptance Criteria**:
  - [ ] Re-running `clasi init` on a project with old hooks updates them
  - [ ] Re-running `clasi init` on an up-to-date project reports "Unchanged"
  - [ ] Other sections of `settings.json` are not disturbed

## SUC-003: Team-Lead Write to Source File Is Blocked

- **Actor**: Team-lead agent (tier 0) attempting to write Python source code
- **Preconditions**: Session is a tier-0 (team-lead) session; no OOP bypass
  file (`.clasi-oop`) is present
- **Main Flow**:
  1. Team-lead attempts to Write or Edit a `.py` file (e.g., `clasi/cli.py`)
  2. Claude Code fires PreToolUse → role-guard hook
  3. `clasi hook role-guard` reads the payload and detects tier 0 and a
     disallowed path
  4. Handler prints CLASI ROLE VIOLATION to stderr
  5. Handler exits 2, blocking the write
- **Postconditions**: File is not written; model receives the violation message
  and is redirected
- **Acceptance Criteria**:
  - [ ] Tier-0 attempt to Write `*.py` is blocked with exit 2
  - [ ] Tier-0 attempt to Write `*.toml` is blocked with exit 2
  - [ ] Tier-0 attempt to Write inside `docs/clasi/` (non-sprint) is allowed
  - [ ] Tier-0 attempt to Write inside `.claude/` is allowed (settings, rules)
  - [ ] Tier-2 (programmer) write to any path is still allowed

## SUC-004: Completed Ticket Moved to done/ After Programmer Task

- **Actor**: Team-lead monitoring execute-sprint skill
- **Preconditions**: Sprint is executing; a programmer has just completed a
  ticket (set frontmatter to `status: done`, tests pass)
- **Main Flow**:
  1. Programmer marks task complete
  2. Team-lead (or TaskCompleted hook) calls `move_ticket_to_done(ticket_path)`
  3. Ticket file moves from `tickets/` to `tickets/done/`
  4. Sprint completion check passes (all tickets in done/)
- **Postconditions**: Ticket file is in `tickets/done/`; sprint can be closed
- **Acceptance Criteria**:
  - [ ] execute-sprint SKILL.md contains a step to call `move_ticket_to_done`
    after each programmer task completes
  - [ ] After sprint execution, all completed tickets are in `tickets/done/`
  - [ ] Sprint can be closed without manual ticket moves by the team-lead
