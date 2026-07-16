---
status: draft
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 020 Use Cases

## SUC-001: Team-lead performs an out-of-process edit
Parent: UC (enforcement / OOP escape hatch)

- **Actor**: Team-lead agent, stakeholder has set `.clasi/oop`
- **Preconditions**: `.clasi/oop` exists; no in-progress ticket; the running
  `clasi` build actually contains the current `_oop_active()` logic (not a
  stale install).
- **Main Flow**:
  1. Team-lead issues a Write/Edit against a source file.
  2. `role-guard` hook parses the real PreToolUse payload, calls
     `_oop_active()`, sees the flag, allows the write.
- **Postconditions**: Write succeeds; `role-guard` logs `oop-bypass`, not
  `blk-write`.
- **Acceptance Criteria**:
  - [ ] A captured real role-guard payload with `.clasi/oop` present is
        allowed against the actual invocation path used by
        `.claude/settings.json` (bare `clasi`, once ticket 002 lands — or
        `uv run clasi` if verified before it).
  - [ ] Revert-check: reverting the fix makes this test fail (not just
        pass because the test was already lenient).

## SUC-002: A session detects it is running a stale CLASI build
Parent: UC (install integrity)

- **Actor**: Any CLASI MCP client or hook invocation
- **Preconditions**: The resolved `clasi` (bare command or `uv run clasi`)
  differs in version/source_path from the project's own working tree.
- **Main Flow**:
  1. MCP server starts, or a hook fires.
  2. Server/hook compares its own `source_path`/version against the target
     project's tree.
  3. On mismatch beyond a threshold, it surfaces a loud, named-version
     warning (status block, MCP `instructions`, or startup log).
- **Postconditions**: The mismatch is visible to the operator before it
  causes a silent false-success (e.g. `close_sprint` archiving with the
  wrong status because the writer fix wasn't actually running).
- **Acceptance Criteria**:
  - [ ] A deliberately-stale install produces a visible warning naming both
        versions.
  - [ ] A fresh `clasi init` in a consumer project with no `uv`, no
        `[project]` table, still works unchanged.
  - [ ] This repo's own `.mcp.json`/hook invocation runs the working tree,
        not a stale install.
  - [ ] `close_sprint` on a tree containing the 019-007 writer fix produces
        `status: closed`, not `status: done`, when run through the actual
        configured invocation path (not just `uv run clasi`).

## SUC-003: Version bump policy matches actual sprint cadence
Parent: UC (git workflow)

- **Actor**: Programmer agent, team-lead, `dotconfig version bump`
- **Preconditions**: A sprint with multiple tickets is being executed.
- **Main Flow**:
  1. Rule and tooling agree on when a bump is required (reconciled: still
     enough to keep "which build is live" answerable per session, but not
     one bump per commit).
  2. Agents follow the reconciled rule.
- **Postconditions**: Git history for a multi-ticket sprint shows
  materially fewer bump commits than tickets, without losing the ability to
  tell which code is live in an editable install.
- **Acceptance Criteria**:
  - [ ] `.claude/rules/git-commits.md` and actual agent behavior agree.
  - [ ] A test sprint with 3+ tickets produces at most 1-2 bump commits,
        not one per ticket.
  - [ ] The reconciliation explicitly addresses the editable-install
        rationale, not just deletes the rule.

## SUC-004: Issue lifecycle links fire during normal planning and ticketing
Parent: UC (issue lifecycle, sprint 014)

- **Actor**: Sprint-planner, team-lead
- **Preconditions**: One or more `clasi/issues/*.md` files exist and are
  relevant to a sprint being planned.
- **Main Flow**:
  1. Sprint-planner (or team-lead) calls `link_sprint_issues` during
     roadmap/detail planning.
  2. Tickets are created with explicit `issue=` references.
  3. `add_issue_ref` / `move_issue_to_done` fire at the appropriate lifecycle
     points.
- **Postconditions**: Sprint and issue frontmatter show correct
  bidirectional links; issues move to `done/` when resolved.
- **Acceptance Criteria**:
  - [ ] A test sprint linked to 2+ issues shows non-empty `issues:` in
        `sprint.md` frontmatter.
  - [ ] Each ticket's `issue:` field reflects only the issue(s) it actually
        addresses.
  - [ ] Closing the sprint moves resolved issues to `done/` with correct
        backlinks intact.

## SUC-005: create_ticket on a multi-issue sprint does not cross-link
Parent: UC (issue lifecycle)

- **Actor**: Sprint-planner calling `create_ticket`
- **Preconditions**: Sprint has 2+ linked issues; ticket created without
  explicit `issue=`.
- **Main Flow**:
  1. `create_ticket(sprint_id, title)` is called with no `issue=`.
  2. Because more than one issue is linked, the tool does not silently
     link all of them.
- **Postconditions**: Ticket's `issue:` field is empty (or the call errors,
  depending on chosen fix) — never "all sprint issues."
- **Acceptance Criteria**:
  - [ ] Multi-issue sprint + no `issue=` produces empty `issue:` frontmatter
        or an explicit error, not all issues.
  - [ ] Single-issue sprint still auto-links as before (regression check).
  - [ ] Neither non-addressed issue's `tickets:` backlink gains the ticket.

## SUC-006: Sprint-planner produces a right-sized plan for a small project
Parent: UC (sprint planning)

- **Actor**: Sprint-planner
- **Preconditions**: Sprint scope is a small, well-understood change (e.g.
  one module, no architectural shift).
- **Main Flow**:
  1. Sprint-planner assesses scope size before writing `architecture-update.md`.
  2. For small scope, it skips Mermaid diagrams and produces a compact,
     bullet-structured plan.
- **Postconditions**: Plan length and structure are proportionate to scope.
- **Acceptance Criteria**:
  - [ ] A trivial single-module sprint plan is roughly 300-500 words, no
        Mermaid diagram.
  - [ ] A genuinely architectural sprint (like this one, arguably) still
        gets full treatment — the fix must not flatten all plans uniformly.

## SUC-007: Exiting plan mode produces a well-formed issue, not a plan copy
Parent: UC (issue capture)

- **Actor**: `plan-to-issue` hook (Claude Code path and Codex path)
- **Preconditions**: A plan is written and `ExitPlanMode` fires (or the
  Codex equivalent).
- **Main Flow**:
  1. Hook fires; instead of copying the plan body verbatim, the resulting
     file is reshaped into house issue format (`## Description`, `##
     Cause`, `## Proposed fix`, `## Verification`, `## Related`), with
     plan-mode scaffolding removed.
  2. Filename has no redundant `issue-` prefix.
- **Postconditions**: `clasi/issues/*.md` contains no "Scope of this plan",
  no "Deliverable", no "Files to touch (this plan)", no instruction to
  create the file that already exists.
- **Acceptance Criteria**:
  - [ ] Exiting plan mode with a plan containing "do not implement" framing
        produces an issue file with none of that framing.
  - [ ] Resulting file has `## Description` and `## Proposed fix` headings.
  - [ ] Filename has no `issue-` prefix.
  - [ ] `_unique_path` collision suffixing still works; `status: pending`
        frontmatter still present; both Claude and Codex paths covered.

## SUC-008: Re-enabled process-content MCP tools are live and covered
Parent: UC (MCP tool surface)

- **Actor**: Any MCP client (Claude Code, Codex, Copilot)
- **Preconditions**: The 9 disabled `@server.tool()` decorators in
  `process_tools.py` are re-enabled.
- **Main Flow**:
  1. Client calls e.g. `list_skills()` or `get_skill_definition(name)`.
  2. Tool responds as documented in `clasi-se-process.md` and related
     shipped rule files.
- **Postconditions**: Doc/implementation contradiction is resolved; tests
  reflect the real tool count.
- **Acceptance Criteria**:
  - [ ] `clasi mcp` exposes 45 tools (36 + 9).
  - [ ] `EXPECTED_PROCESS_TOOLS` and the hardcoded tool count in
        `test_mcp_server.py` updated and passing.
  - [ ] No discovery-reliability measurement or installer shrink bundled
        into this ticket (explicitly out of scope per the issue's staged
        plan).

## SUC-009: detect_inconsistencies does not drift-check terminal sprints
Parent: UC (status/consistency reporting)

- **Actor**: `detect_inconsistencies`, any future consumer
- **Preconditions**: A sprint is archived (`sprints/done/`) and in the
  state machine's terminal (`closed`) state, regardless of its declared
  frontmatter `status:` value (including legacy `status: done`).
- **Main Flow**:
  1. `detect_inconsistencies` iterates sprints.
  2. For a sprint in the machine's terminal state, it skips the drift
     check rather than comparing declared vs. computed state.
- **Postconditions**: Terminal/archived sprints never report `state_drift`,
  regardless of what legacy value their frontmatter carries. Non-terminal
  sprints still report genuine drift.
- **Acceptance Criteria**:
  - [ ] A sprint archived with legacy `status: done` produces zero
        `state_drift` entries.
  - [ ] A non-terminal sprint with genuinely disagreeing declared/computed
        state still reports drift (the fix must not over-broadly silence).
  - [ ] The 18 archived files remain byte-for-byte unmodified on disk.
