---
status: draft
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 007 Use Cases

## SUC-001: Close a sprint from the shell when MCP tool is broken

- **Actor**: CLASI user (team-lead, affected by VS Code extension MCP bug)
- **Preconditions**:
  - A sprint is in `executing` phase, all tickets done, ready to close
  - The `mcp__clasi__close_sprint` MCP tool fails in the user's environment
  - `clasi` CLI is installed and on PATH
- **Main Flow**:
  1. User invokes `clasi sprint close <sprint_id> --branch <branch>` from a
     terminal or Bash tool call.
  2. The CLI wrapper calls `close_sprint` from `artifact_tools.py` with the
     provided arguments.
  3. `close_sprint` executes the full lifecycle: pre-condition verification,
     tests, archive, state DB update, version bump, git merge, push tags,
     branch deletion.
  4. The result JSON is printed to stdout.
- **Postconditions**:
  - Sprint is archived in `sprints/done/`, state DB updated, branch deleted,
    version bumped and tagged — identical outcome to a successful MCP call.
- **Acceptance Criteria**:
  - [ ] `clasi sprint close --help` shows correct usage and all options
  - [ ] `clasi sprint close <id> --branch <branch>` succeeds and produces
        the same JSON result as `close_sprint` called directly
  - [ ] All `close_sprint` options are exposed: `--branch`, `--main-branch`,
        `--push-tags/--no-push-tags`, `--delete-branch/--no-delete-branch`,
        `--test-command`
  - [ ] `clasi sprint --help` lists `close` as a subcommand

## SUC-002: Use a tool-name alias to diagnose the VS Code MCP bug

- **Actor**: CLASI developer (diagnosing the VS Code extension bug)
- **Preconditions**:
  - The VS Code extension drops params for `close_sprint` calls
  - `finalize_sprint` is registered as an MCP tool with identical signature
- **Main Flow**:
  1. Developer (or affected user) calls `mcp__clasi__finalize_sprint` with the
     same arguments they would pass to `close_sprint`.
  2. The alias delegates to `close_sprint` and returns its result.
  3. The outcome (success or failure) disambiguates the bug:
     - Success → tool name was the trigger; alias becomes permanent workaround.
     - Failure → cause is structural (likely boolean-with-True-default params).
- **Postconditions**:
  - Sprint is closed (on success), or the bug is further narrowed (on failure).
  - Either way, diagnostic information is gained.
- **Acceptance Criteria**:
  - [ ] `finalize_sprint` is registered as an MCP tool (appears in tool list)
  - [ ] `finalize_sprint` has an identical Python signature to `close_sprint`:
        same parameter names, types, defaults, and order
  - [ ] `finalize_sprint` produces identical output to `close_sprint` for the
        same inputs
  - [ ] `close_sprint` is unchanged in behavior and signature
