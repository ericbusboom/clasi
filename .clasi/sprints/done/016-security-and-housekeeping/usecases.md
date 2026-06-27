---
status: final
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 016 Use Cases

## SUC-016-001: Root .gitignore covers the configured log directory

- **Actor**: Developer running git in a CLASI-initialized project
- **Preconditions**: Project has been initialized by `clasi init`; log directory default is `.clasi/log/`
- **Main Flow**:
  1. Developer stages all files (`git add -A` or similar).
  2. Developer attempts to commit.
  3. Git skips all files under the log directory because `.gitignore` patterns exclude them.
- **Postconditions**: No transcript files are staged or committed. Secrets in log files are never exposed to the remote.
- **Acceptance Criteria**:
  - [ ] Root `.gitignore` contains a pattern matching `.clasi/log/` (already present; confirm idempotent).
  - [ ] Root `.gitignore` also covers any non-default `paths.logs` value set in `.clasi/config.yaml`.
  - [ ] `clasi init` (re-run) does not remove or clobber existing root `.gitignore` entries.

## SUC-016-002: Initialized project has a self-contained log-dir gitignore

- **Actor**: Developer who has just run `clasi init` on a fresh project
- **Preconditions**: `clasi init` has completed for a given `target` path.
- **Main Flow**:
  1. Developer inspects `<log_dir>/.gitignore`.
  2. File exists and contains `*` + `!.gitignore` — all files in that directory are ignored.
- **Postconditions**: Even without a root `.gitignore` entry, files under the log directory are ignored by git.
- **Acceptance Criteria**:
  - [ ] `clasi init` writes `<configured_log_dir>/.gitignore` containing `*` and `!.gitignore`.
  - [ ] Re-running `clasi init` is idempotent — the `.gitignore` is overwritten with the same content (already implemented; verify via existing test `test_log_gitignore_idempotent`).
  - [ ] The `.gitignore` is written for the **configured** log path (`paths.logs`), not a hardcoded path.

## SUC-016-003: Runtime log-dir creation ensures gitignore protection

- **Actor**: Hook handler creating the log directory at first use
- **Preconditions**: `.clasi/` exists; `.clasi/log/` does not yet exist (first hook invocation).
- **Main Flow**:
  1. Hook handler calls `log_dir.mkdir(parents=True, exist_ok=True)`.
  2. A `.gitignore` containing `*` + `!.gitignore` is written inside the newly created log directory.
- **Postconditions**: Log directory is immediately protected, even if the directory was created at runtime rather than by `clasi init`.
- **Acceptance Criteria**:
  - [ ] `hook_handlers.py` writes log-dir `.gitignore` whenever it creates the log directory.
  - [ ] Behavior is idempotent: if the directory already exists with a `.gitignore`, it is not overwritten.

## SUC-016-004: Agents use NONE sentinel for optional MCP parameters

- **Actor**: Claude Code agent calling a CLASI MCP tool with an optional parameter
- **Preconditions**: Agent constructs a tool call where an optional parameter has no meaningful value.
- **Main Flow**:
  1. Agent passes `"NONE"` as the string value for an optional parameter.
  2. MCP server receives the call; `_logged_call_tool` converts `"NONE"` to `None` before dispatch.
  3. The tool function receives `None`, which it interprets as "absent / use default".
- **Postconditions**: The tool executes with the default behavior for that optional parameter.
- **Acceptance Criteria**:
  - [ ] `_logged_call_tool` in `clasi/mcp_server.py` strips `"NONE"` → `None` for all arguments (already implemented; confirm and add tests).
  - [ ] Passing `"NONE"` for `test_command` in `close_sprint` results in `None` being passed to the implementation, triggering the default `uv run pytest` behavior.
  - [ ] A legitimate string value that is not `"NONE"` (e.g., `"pytest -q"`) is passed through unchanged.
  - [ ] Unit tests in `tests/unit/test_mcp_server.py` cover the sentinel stripping behavior.

## SUC-016-005: Agents are informed of the empty-argument bug and NONE mitigation

- **Actor**: Claude Code agent starting a session in a CLASI project
- **Preconditions**: Claude Code loads `.claude/rules/` files at session start.
- **Main Flow**:
  1. Session starts; Claude Code loads all always-on rule files.
  2. Agent reads the rule documenting the harness bug and the `"NONE"` sentinel convention.
  3. Agent uses `"NONE"` for optional parameters in subsequent tool calls.
- **Postconditions**: Agent uses the correct pattern; silent parameter-drop failures do not occur.
- **Acceptance Criteria**:
  - [ ] `clasi/plugin/rules/tool-call-empty-args.md` exists with `paths: ["**"]` frontmatter.
  - [ ] Rule documents: the confirmed bug (empty/null arg → all args dropped), the mitigation (`"NONE"` sentinel), the server-side stripping that converts `"NONE"` back to `None`.
  - [ ] `clasi init` installs this rule file into the target project's `.claude/rules/` directory.
