---
status: final
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Use Cases — Sprint 015: close_sprint and sprint-lifecycle hardening

## SUC-015-001: Auto-detect sprint from current branch

- **Actor**: Team-lead agent (or human operator)
- **Preconditions**: The current git branch is `sprint/NNN-slug`.
- **Main Flow**:
  1. Caller invokes `close_sprint()` with no arguments (or `sprint_id=None`).
  2. The tool reads the current branch via `git branch --show-current`.
  3. It parses `sprint/NNN-slug` → `NNN` and derives the sprint ID and branch name.
  4. The full close lifecycle proceeds as if the caller had passed `sprint_id="NNN"` and `branch_name="sprint/NNN-slug"` explicitly.
- **Postconditions**: Sprint is closed; no change from explicit-argument behavior.
- **Acceptance Criteria**:
  - [ ] `close_sprint()` with no args on `sprint/015-*` branch closes sprint 015 successfully.
  - [ ] `close_sprint()` on `master` returns a descriptive error, not a traceback.
  - [ ] `close_sprint()` on an unrelated feature branch returns a descriptive error.

---

## SUC-015-002: Clean up git worktrees after sprint close

- **Actor**: `close_sprint` internal lifecycle (post-merge step)
- **Preconditions**: One or more git worktrees with branch `sprint/NNN-*` exist for the sprint being closed.
- **Main Flow**:
  1. After the merge and branch deletion step, `close_sprint` enumerates git worktrees via `git worktree list --porcelain`.
  2. It identifies worktrees whose tracked branch matches the closing sprint's branch pattern.
  3. It removes each matching worktree (`git worktree remove --force <path>`).
  4. The result JSON includes a `worktrees_pruned` list of removed paths.
- **Postconditions**: No git worktrees for the closed sprint remain on disk.
- **Acceptance Criteria**:
  - [ ] After `close_sprint`, `git worktree list` shows no worktrees for the closed sprint branch.
  - [ ] Close succeeds even when no worktrees exist (`worktrees_pruned: []`).
  - [ ] A single failed removal does not abort the close; error is surfaced in the result JSON.

---

## SUC-015-003: Remove finalize_sprint alias

- **Actor**: CLASI MCP server (post-removal state)
- **Preconditions**: `finalize_sprint` is currently registered as an MCP tool.
- **Main Flow** (after this sprint):
  1. The `finalize_sprint` function is deleted from `clasi/tools/artifact_tools.py`.
  2. `tests/unit/test_finalize_sprint_alias.py` is deleted.
  3. `test_mcp_server.py` EXPECTED_ARTIFACT_TOOLS no longer lists `finalize_sprint`.
  4. `clasi/plugin/skills/close-sprint/SKILL.md` contains no references to `finalize_sprint`.
- **Postconditions**: `finalize_sprint` is not callable or visible to the model; `close_sprint` behavior is unchanged.
- **Acceptance Criteria**:
  - [ ] `mcp__clasi__finalize_sprint` no longer appears in the MCP tool registry.
  - [ ] `pytest -q` passes with no regressions.
  - [ ] Existing `close_sprint` and sprint 011 exit-code-5 tests pass unchanged.
