---
status: planned
sprint_id: "001"
---

# Sprint 001 Use Cases

## SUC-001: Team-Lead Dispatches to Sprint-Planner via SDK

- **Actor**: Team-lead agent
- **Preconditions**:
  - Sprint directory exists with a sprint.md containing goals and TODO references.
  - The CLASI MCP server is running with `dispatch_tools.py` registered.
  - The sprint-planner agent has a `contract.yaml` and `agent.md` in its agent directory.
- **Main Flow**:
  1. Team-lead calls `dispatch_to_sprint_planner(sprint_id, sprint_directory, todo_ids, goals, mode="detail")`.
  2. The dispatch tool loads the Jinja2 dispatch template and renders it with the provided parameters.
  3. The dispatch tool calls `log_dispatch()` to write a pre-execution dispatch log entry with the rendered prompt, sprint name, and template reference.
  4. The dispatch tool loads `contract.yaml` from the sprint-planner agent directory.
  5. The dispatch tool configures `ClaudeAgentOptions` from the contract: `allowed_tools`, `mcp_servers`, `model` (defaulting to `"sonnet"` if omitted), and `cwd` (resolved to `sprint_directory`).
  6. The dispatch tool loads `agent.md` content as the system prompt.
  7. The dispatch tool calls `query(prompt=rendered, options=options)` and collects the `ResultMessage`.
  8. The dispatch tool extracts the JSON return block from the agent's final message.
  9. The dispatch tool validates the JSON against the `returns` schema from the contract (detail mode).
  10. The dispatch tool validates that output files declared in the contract exist with correct frontmatter.
  11. The dispatch tool calls `update_dispatch_result()` to write a post-execution log entry with the result.
  12. The dispatch tool returns structured JSON: `{"status": "success", "result": ..., "log_path": ..., "validations": ...}`.
  13. Team-lead receives the result and reports to the stakeholder.
- **Postconditions**:
  - A dispatch log entry exists with both pre-execution prompt and post-execution result.
  - The sprint directory contains the planning artifacts produced by the sprint-planner.
  - The team-lead never called Claude's `Agent` tool directly.
- **Alternate Flows**:
  - **A1: Contract validation fails** -- The dispatch tool returns `{"status": "validation_error", "errors": [...]}`. The team-lead reports the specific validation failures to the stakeholder.
  - **A2: Agent returns malformed JSON** -- The dispatch tool logs the raw result, returns a structured error with the parsing failure. The team-lead can retry or escalate.
  - **A3: `query()` raises an exception** -- The dispatch tool catches the exception, logs it as the result, and returns `{"status": "error", "message": ...}`. The pre-execution log entry still exists.
- **Acceptance Criteria**:
  - [ ] Dispatch tool calls `query()` internally, not the team-lead.
  - [ ] Pre-execution log entry is always written before `query()`.
  - [ ] Post-execution log entry is always written after `query()` completes or fails.
  - [ ] Contract-based validation runs on the return value.
  - [ ] Team-lead receives structured JSON, not a raw prompt.


## SUC-002: Nested Dispatch -- Sprint-Planner Dispatches to Architect

- **Actor**: Sprint-planner subagent (spawned by `dispatch_to_sprint_planner`)
- **Preconditions**:
  - Sprint-planner is running inside a `query()` session with MCP access to the CLASI server.
  - The sprint directory has a sprint.md with goals and scope.
  - The architect agent has a `contract.yaml` and `agent.md`.
- **Main Flow**:
  1. Sprint-planner reads its own contract and determines it `delegates_to` the architect agent for architecture document creation.
  2. Sprint-planner calls `dispatch_to_architect(sprint_id, sprint_directory)` via the CLASI MCP server.
  3. The dispatch tool renders the architect's dispatch template with sprint context.
  4. The dispatch tool logs the dispatch (nested: parent=sprint-planner, child=architect).
  5. The dispatch tool loads the architect's `contract.yaml` and configures `ClaudeAgentOptions`.
  6. The dispatch tool calls `query()` to spawn the architect as a nested subagent.
  7. The architect reads the sprint.md and usecases.md, then writes `technical-plan.md` (or `architecture.md` depending on naming convention).
  8. The architect returns structured JSON with status and files created.
  9. The dispatch tool validates the return against the architect's contract schema.
  10. The dispatch tool logs the result and returns to the sprint-planner.
  11. Sprint-planner continues its work using the architecture document.
- **Postconditions**:
  - The architecture document exists in the sprint directory.
  - A nested dispatch log entry exists (sprint-planner to architect).
  - The team-lead's session never saw or participated in this intermediate dispatch.
  - SQLite state DB was accessed by both parent and child MCP instances via WAL mode without conflict.
- **Alternate Flows**:
  - **A1: Architect validation fails** -- Sprint-planner receives the validation error and can retry the dispatch or report the failure in its own return JSON.
  - **A2: Concurrent DB access** -- Both the parent MCP instance (serving the sprint-planner) and the child MCP instance (serving the architect) access the state DB. WAL mode handles concurrent reads; writes are serialized.
- **Acceptance Criteria**:
  - [ ] Nested dispatch produces its own dispatch log entry.
  - [ ] The team-lead sees only one dispatch call and one result.
  - [ ] WAL mode prevents SQLite locking errors during nested dispatch.


## SUC-003: Sprint Closure via Enhanced close_sprint

- **Actor**: Team-lead agent (or sprint-executor)
- **Preconditions**:
  - All tickets in the sprint are in `tickets/done/` with `status: done`.
  - All TODOs referenced by the sprint have their referencing tickets closed.
  - The sprint branch exists and is checked out.
  - Tests pass on the sprint branch.
  - The execution lock is held for this sprint.
- **Main Flow**:
  1. Agent calls `close_sprint(sprint_id, branch_name="sprint/001-sdk-based-orchestration-and-enforcement-hardening", main_branch="master")`.
  2. `close_sprint` verifies preconditions:
     a. Checks all tickets are in `tickets/done/` with `status: done` frontmatter.
     b. Checks all TODOs referencing this sprint are in `todo/done/`.
     c. Checks state DB phase matches filesystem state.
     d. Checks execution lock is held for this sprint.
  3. For any precondition that can be self-repaired, the tool fixes it automatically:
     - Moves a ticket with `status: done` frontmatter from `tickets/` to `tickets/done/`.
     - Advances DB phase if behind filesystem state.
     - Releases stale lock and re-acquires if lock is for a nonexistent sprint.
  4. `close_sprint` runs `uv run pytest` to verify tests pass.
  5. `close_sprint` archives the sprint directory (moves to `sprints/done/`).
  6. `close_sprint` updates the state DB (phase to `done`).
  7. `close_sprint` bumps the version and creates a git tag.
  8. `close_sprint` runs `git checkout master && git merge --no-ff sprint/001-... -m "close sprint 001"`.
  9. `close_sprint` runs `git push --tags`.
  10. `close_sprint` runs `git branch -d sprint/001-...`.
  11. `close_sprint` releases the execution lock.
  12. `close_sprint` returns structured JSON with all operations and their results.
- **Postconditions**:
  - Sprint directory is in `sprints/done/`.
  - State DB phase is `done`, execution lock is released.
  - Sprint branch is merged into master with a `--no-ff` merge commit.
  - Version tag exists and is pushed.
  - Sprint branch is deleted.
  - No manual git operations were performed by the agent.
- **Acceptance Criteria**:
  - [ ] Single `close_sprint` call handles all operations.
  - [ ] Self-repair actions are recorded in the result JSON under `repairs`.
  - [ ] Each git operation result is individually reported in the result JSON.
  - [ ] The close-sprint skill is 3 steps: confirm, call, report.


## SUC-004: close_sprint Failure and Recovery

- **Actor**: Team-lead agent
- **Preconditions**:
  - A merge conflict exists between the sprint branch and main.
  - OR: Tests fail on the sprint branch.
  - OR: A ticket is genuinely incomplete (not auto-repairable).
- **Main Flow**:
  1. Agent calls `close_sprint(sprint_id, branch_name)`.
  2. `close_sprint` runs precondition verification; all pass (or are self-repaired).
  3. `close_sprint` runs tests; they pass.
  4. `close_sprint` archives the sprint directory.
  5. `close_sprint` attempts `git merge --no-ff`; a merge conflict occurs in `src/auth.py`.
  6. `close_sprint` writes a `recovery_state` record to the state DB:
     - `sprint_id`: the current sprint
     - `step`: "merge"
     - `allowed_paths`: `["src/auth.py"]`
     - `reason`: "Merge conflict in src/auth.py"
     - `recorded_at`: current timestamp
  7. `close_sprint` returns a structured error:
     ```json
     {
       "error": {
         "step": "merge",
         "message": "Merge conflict in src/auth.py",
         "recovery": {
           "recorded": true,
           "allowed_paths": ["src/auth.py"],
           "instruction": "Resolve the merge conflict in src/auth.py, then call close_sprint again."
         }
       }
     }
     ```
  8. The team-lead dispatches to the appropriate subagent to resolve the conflict. The PreToolUse hook allows writes to `src/auth.py` because it is in `allowed_paths`.
  9. After resolution, the agent calls `close_sprint` again.
  10. `close_sprint` detects that the sprint is already archived (step 5 was completed before the failure) and skips that step.
  11. `close_sprint` retries the merge; it succeeds.
  12. `close_sprint` completes remaining steps (push tags, delete branch, release lock).
  13. `close_sprint` clears the recovery state record.
  14. `close_sprint` returns a successful result JSON.
- **Postconditions**:
  - Sprint is fully closed despite the intermediate failure.
  - Recovery state is cleared.
  - The PreToolUse hook returns to normal restrictive behavior.
- **Alternate Flows**:
  - **A1: Test failure** -- `close_sprint` writes recovery state with `step: "tests"` and `allowed_paths` pointing to the failing test files. The agent fixes the tests and retries.
  - **A2: Stale recovery record** -- If a recovery record is older than 24 hours, `close_sprint` logs a warning, clears it, and proceeds with a fresh attempt.
  - **A3: Incomplete ticket (unrepairable)** -- `close_sprint` writes recovery state with `step: "precondition"` and the list of incomplete tickets. The agent completes the tickets and retries.
- **Acceptance Criteria**:
  - [ ] Recovery state is written to the DB on unrecoverable failure.
  - [ ] Recovery state includes the specific paths the agent may edit.
  - [ ] Retrying `close_sprint` skips already-completed steps (idempotent).
  - [ ] Recovery state is cleared on successful completion.
  - [ ] Stale records (>24h) are auto-cleared with a warning.


## SUC-005: PreToolUse Role Guard Blocks Team-Lead Write

- **Actor**: Team-lead agent (top-level Claude Code session)
- **Preconditions**:
  - `clasi init` has been run, installing `.claude/hooks/role_guard.py`.
  - The PreToolUse hook is registered in `.claude/settings.json` for Edit, Write, and MultiEdit tools.
  - No recovery state exists in the state DB.
  - No `.clasi-oop` flag file exists.
- **Main Flow**:
  1. The stakeholder asks the team-lead to "write the sprint docs."
  2. The team-lead (without dispatching) attempts to call `Write` on `docs/clasi/sprints/001/sprint.md`.
  3. Claude Code fires the PreToolUse hook before executing the Write tool.
  4. `role_guard.py` reads the tool input JSON and extracts the file path.
  5. `role_guard.py` checks for a `.clasi-oop` flag file; none exists.
  6. `role_guard.py` checks the state DB for an active recovery state; none exists.
  7. `role_guard.py` checks the file path against the safe list (`.claude/`, `CLAUDE.md`, `AGENTS.md`); the path is not in the safe list.
  8. `role_guard.py` outputs a blocking error:
     ```
     CLASI ROLE VIOLATION: team-lead attempted direct file write to docs/clasi/sprints/001/sprint.md
     The team-lead does not write files. Dispatch to the appropriate subagent:
     - sprint-planner for sprint/architecture/ticket artifacts
     - code-monkey for source code and tests
     - todo-worker for TODOs
     - ad-hoc-executor for out-of-process changes
     Call get_agent_definition("team-lead") to review your delegation map.
     ```
  9. `role_guard.py` exits with code 1 (non-zero).
  10. Claude Code blocks the Write tool call.
  11. The team-lead receives the error and dispatches to `dispatch_to_sprint_planner` instead.
- **Postconditions**:
  - The file was not written by the team-lead.
  - The team-lead dispatched to the correct subagent.
  - The Write tool call never executed.
- **Alternate Flows**:
  - **A1: Safe list path** -- Team-lead writes to `.claude/settings.json`. The hook checks the safe list, finds a match, exits with code 0. The write proceeds.
  - **A2: OOP bypass** -- Stakeholder says "out of process." The ad-hoc-executor dispatch tool creates a `.clasi-oop` flag file. The hook checks for it, finds it, exits with code 0. Writes are allowed until the flag is removed.
- **Acceptance Criteria**:
  - [ ] Hook fires on Write, Edit, and MultiEdit tool calls.
  - [ ] Hook blocks writes to CLASI artifacts and source code.
  - [ ] Hook allows writes to safe-list paths.
  - [ ] Hook exits non-zero to block, zero to allow.
  - [ ] Error message names the violation and suggests the correct action.


## SUC-006: Role Guard Allows Recovery Write

- **Actor**: Team-lead agent (or dispatched subagent in recovery scenario)
- **Preconditions**:
  - `close_sprint` has failed with a merge conflict in `src/auth.py`.
  - A recovery state record exists in the state DB with `allowed_paths: ["src/auth.py"]`.
  - The PreToolUse hook is installed and active.
- **Main Flow**:
  1. The team-lead (or a dispatched subagent) needs to edit `src/auth.py` to resolve the merge conflict.
  2. The agent calls `Edit` on `src/auth.py`.
  3. Claude Code fires the PreToolUse hook.
  4. `role_guard.py` extracts the file path from the tool input JSON.
  5. `role_guard.py` checks for `.clasi-oop` flag; none exists.
  6. `role_guard.py` queries the state DB for an active recovery state.
  7. `role_guard.py` finds a recovery record with `allowed_paths: ["src/auth.py"]`.
  8. `role_guard.py` checks whether the target path (`src/auth.py`) is in the allowed paths list.
  9. The path matches. `role_guard.py` exits with code 0.
  10. Claude Code allows the Edit tool call to proceed.
  11. The agent resolves the merge conflict.
  12. The agent calls `close_sprint` again; it succeeds.
  13. `close_sprint` clears the recovery state record.
  14. Subsequent writes to `src/auth.py` are blocked by the hook (no more recovery state).
- **Postconditions**:
  - The merge conflict was resolved via a targeted, permitted write.
  - The recovery state is cleared after successful sprint closure.
  - The hook returns to blocking all non-safe-list writes.
- **Alternate Flows**:
  - **A1: Write to non-allowed path during recovery** -- Agent attempts to write `src/main.py`, which is not in `allowed_paths`. The hook blocks it, even though a recovery record exists. Only the specific paths in the record are permitted.
- **Acceptance Criteria**:
  - [ ] Hook queries the state DB for recovery state before blocking.
  - [ ] Hook allows writes only to paths listed in `allowed_paths`.
  - [ ] Hook blocks writes to paths not in the recovery record.
  - [ ] Recovery state clearance re-enables full blocking.


## SUC-007: TODO Lifecycle Through Sprint

- **Actor**: Team-lead, sprint-planner, sprint-executor agents
- **Preconditions**:
  - A TODO file exists in `docs/clasi/todo/` with `status: pending`.
  - A sprint is being planned that incorporates this TODO.
- **Main Flow**:
  1. During sprint planning, the sprint-planner identifies a TODO to incorporate.
  2. The sprint-planner calls `create_ticket(sprint_id, title)` for a ticket that addresses the TODO.
  3. `create_ticket` detects the TODO reference in the ticket content (or is passed the TODO ID).
  4. `create_ticket` moves the TODO from `docs/clasi/todo/` to `docs/clasi/todo/in-progress/`.
  5. `create_ticket` updates the TODO's YAML frontmatter:
     ```yaml
     status: in-progress
     sprint: "001"
     tickets:
       - "001-003"
     ```
  6. The ticket is executed by the code-monkey during sprint execution.
  7. When the ticket is completed, the sprint-executor calls `move_ticket_to_done(ticket_path)`.
  8. `move_ticket_to_done` checks if the TODO referenced by this ticket has all its referencing tickets in `done` status.
  9. All referencing tickets are done. `move_ticket_to_done` (or a separate step) moves the TODO from `todo/in-progress/` to `todo/done/` and updates frontmatter to `status: done`.
  10. During `close_sprint`, the tool verifies that all in-progress TODOs for this sprint have been individually moved to done. No bulk-move occurs.
- **Postconditions**:
  - The TODO file is in `docs/clasi/todo/done/` with `status: done`.
  - The TODO's frontmatter records which sprint and tickets addressed it.
  - The `close_sprint` precondition check found no unresolved in-progress TODOs.
- **Alternate Flows**:
  - **A1: TODO referenced by multiple tickets** -- The TODO remains in `in-progress/` until ALL referencing tickets are done. If only some tickets close, the TODO stays in-progress.
  - **A2: Sprint closes with unresolved TODO** -- `close_sprint` precondition check finds an in-progress TODO whose tickets are not all done. The tool returns a structured error identifying the TODO and the incomplete tickets. The agent completes the tickets or removes the TODO reference before retrying.
  - **A3: TODO not referenced by any ticket** -- If a TODO is listed in the sprint's `todos` frontmatter but no ticket references it, `close_sprint` flags it during precondition verification for agent review.
- **Acceptance Criteria**:
  - [ ] `create_ticket` moves referenced TODOs to `in-progress/`.
  - [ ] TODO frontmatter is updated with sprint and ticket references.
  - [ ] TODOs move to `done/` individually when all referencing tickets close.
  - [ ] `close_sprint` does not bulk-move TODOs.
  - [ ] `close_sprint` verifies all in-progress TODOs for the sprint are resolved.


## SUC-008: Two-Phase Sprint Planning

- **Actor**: Team-lead agent
- **Preconditions**:
  - Multiple TODOs exist in `docs/clasi/todo/` that should be planned into sprints.
  - The stakeholder asks to "plan sprints" (plural).
- **Main Flow**:
  1. **Phase 1 -- Roadmap planning (batch, multiple sprints):**
     a. Team-lead calls `dispatch_to_sprint_planner(sprint_id="025", todo_ids=[...], goals="...", mode="roadmap")`.
     b. Sprint-planner creates a lightweight `sprint.md` with: title, goals, feature scope, TODO references. No use cases, no architecture, no tickets.
     c. The dispatch tool validates against the roadmap contract: sprint.md exists with required fields.
     d. Team-lead repeats for sprints 026, 027.
     e. All planning happens on main. No branches created.
  2. **Phase 2 -- Detailed planning (one sprint, pre-execution):**
     a. When sprint 025 is the next to execute, team-lead calls `dispatch_to_sprint_planner(sprint_id="025", mode="detail")`.
     b. Sprint-planner reads the existing sprint.md goals and fills in full artifacts: usecases.md, technical-plan.md, tickets.
     c. Sprint-planner dispatches to architect (SUC-002) for the architecture document.
     d. The dispatch tool validates against the detail contract: all required files exist, frontmatter checks pass, at least one ticket created.
     e. Still on main. No branch yet.
  3. **Execution:**
     a. Team-lead calls `acquire_execution_lock(sprint_id="025")`.
     b. `acquire_execution_lock` creates the sprint branch: `git checkout -b sprint/025-feature-name`.
     c. Execution proceeds (dispatch to sprint-executor, code-monkey).
  4. **Close:**
     a. `close_sprint` merges back to main, tags, deletes branch (SUC-003).
     b. Sprint 026's detailed planning runs against the updated main, accounting for everything sprint 025 changed.
- **Postconditions**:
  - Sprints 025-027 have roadmap-level sprint.md files on main.
  - Sprint 025 has full planning artifacts and has been executed and closed.
  - Sprint 026's detailed planning starts from the latest main (post-025 merge).
  - Only one sprint branch ever existed at a time.
- **Alternate Flows**:
  - **A1: Roadmap sprint needs adjustment** -- After sprint 025 completes, the stakeholder decides sprint 027's scope should change. Because only a lightweight sprint.md exists, updating it is trivial. No architecture docs or tickets need to be rewritten.
  - **A2: Stakeholder requests single sprint** -- Team-lead calls `dispatch_to_sprint_planner` with `mode="detail"` directly, skipping the roadmap phase. The two-phase model is optional, not mandatory.
- **Acceptance Criteria**:
  - [ ] `dispatch_to_sprint_planner` accepts a `mode` parameter.
  - [ ] Roadmap mode produces only sprint.md with goals, scope, and TODO refs.
  - [ ] Detail mode produces full artifacts (usecases, architecture, tickets).
  - [ ] Validation contract differs by mode.
  - [ ] Branches are created by `acquire_execution_lock`, not during planning.
  - [ ] Execution is strictly serial (one lock, one branch at a time).


## SUC-009: Contract Validation Catches Bad Subagent Output

- **Actor**: Dispatch tool (automated validation, no human actor)
- **Preconditions**:
  - A dispatch tool has called `query()` and the subagent has returned.
  - The agent's `contract.yaml` declares a `returns` schema and `outputs` spec.
- **Main Flow**:
  1. The dispatch tool extracts the JSON return block from the subagent's final message.
  2. The dispatch tool loads the `returns` schema from the agent's `contract.yaml`.
  3. The dispatch tool validates the JSON against the schema using `jsonschema.validate()`.
  4. Validation fails: the agent returned `{"status": "done"}` but the schema requires `files_created` (a required field).
  5. The dispatch tool logs the validation failure in the post-execution dispatch log.
  6. The dispatch tool returns a structured error to the caller:
     ```json
     {
       "status": "validation_error",
       "errors": [
         "'files_created' is a required property"
       ],
       "raw_result": "..."
     }
     ```
  7. The caller (team-lead or parent agent) can decide to retry the dispatch or report the error.
- **Postconditions**:
  - The invalid result was not silently passed to the caller as a success.
  - The validation error is recorded in the dispatch log.
  - The caller has enough information to decide on next steps.
- **Alternate Flows**:
  - **A1: File-level validation fails** -- The contract declares that `sprint.md` should exist with `status: planned` in frontmatter. The file exists but has `status: draft`. The dispatch tool returns a validation error listing the frontmatter mismatch.
  - **A2: No JSON block in agent output** -- The agent returned free-form text without a JSON return block. The dispatch tool treats this as a validation error with message "No JSON return block found in agent output."
  - **A3: Validation passes** -- Both return-level and file-level validation succeed. The dispatch tool returns `{"status": "success", ...}`.
- **Acceptance Criteria**:
  - [ ] Return JSON is validated against the contract's `returns` schema.
  - [ ] Output files are validated against the contract's `outputs` spec.
  - [ ] Validation errors are returned as structured JSON, not exceptions.
  - [ ] Validation failures are logged in the dispatch log.


## SUC-010: Agent Reads Its Own Contract to Format Response

- **Actor**: Subagent (e.g., sprint-planner, code-monkey)
- **Preconditions**:
  - The agent is running inside a `query()` session spawned by a dispatch tool.
  - The agent has MCP access to the CLASI server.
  - The agent's `contract.yaml` is included in its prompt (by the dispatch tool) or accessible via `get_agent_definition`.
- **Main Flow**:
  1. The sprint-planner agent is dispatched to plan a sprint in detail mode.
  2. The agent reads its own contract (included in the dispatch prompt or via `get_agent_definition("sprint-planner")`).
  3. The agent sees the `returns` schema:
     ```yaml
     returns:
       type: object
       required: [status, summary, files_created]
       properties:
         status:
           type: string
           enum: [success, partial, failed]
         summary:
           type: string
         files_created:
           type: array
           items:
             type: string
     ```
  4. The agent completes its work: writes sprint.md, usecases.md, technical-plan.md, creates tickets.
  5. The agent formats its final response as a JSON block matching the schema:
     ```json
     {
       "status": "success",
       "summary": "Sprint 025 fully planned with 3 use cases, architecture update, and 5 tickets.",
       "files_created": [
         "sprint.md",
         "usecases.md",
         "technical-plan.md",
         "tickets/025-001.md",
         "tickets/025-002.md",
         "tickets/025-003.md",
         "tickets/025-004.md",
         "tickets/025-005.md"
       ]
     }
     ```
  6. The dispatch tool extracts and validates this JSON (SUC-009).
- **Postconditions**:
  - The agent's final message contains a JSON block conforming to the contract schema.
  - The dispatch tool's validation succeeds.
  - The structured result flows back to the team-lead.
- **Alternate Flows**:
  - **A1: Agent encounters partial failure** -- The agent creates sprint.md and usecases.md but fails to create the architecture document. It returns `{"status": "partial", "summary": "...", "files_created": [...], "errors": ["Failed to create technical-plan.md"]}`. The dispatch tool validates this (the schema allows `partial` status with `errors`).
  - **A2: Contract not accessible** -- If `get_agent_definition` fails or the contract was not included in the prompt, the agent falls back to unstructured text. The dispatch tool's validation catches this as "no JSON return block" (SUC-009, A2).
- **Acceptance Criteria**:
  - [ ] Agent reads the `returns` schema from its contract.
  - [ ] Agent formats its final message as JSON matching the schema.
  - [ ] Dispatch tool includes the contract in the agent's prompt.
  - [ ] `get_agent_definition` returns contract content alongside agent.md.
