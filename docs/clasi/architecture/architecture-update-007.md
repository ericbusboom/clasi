---
sprint: "007"
status: approved
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Architecture Update -- Sprint 007: Non-Python project support and MCP import reliability

## What Changed

### 1. Eager module-level imports in `artifact_tools.py`

All `from clasi.{sprint,todo,artifact,ticket,versioning}` imports that were
previously inside function bodies are moved to the top of the module. One
lazy import of `clasi.frontmatter` in `process_tools.py` (line 447) is
similarly promoted.

This is a structural change in import order only. No function signatures,
return values, or tool behaviors change.

### 2. Preflight import check in `mcp_server.py` `run()`

Before registering tool modules, `run()` attempts to import each required
submodule and raises a startup error with a clear banner if any fail. The
check covers `clasi.sprint`, `clasi.todo`, `clasi.artifact`, `clasi.ticket`,
and `clasi.versioning`.

### 3. `get_version` enriched with `metadata_version` and `source_path`

The `get_version` tool in `process_tools.py` gains two new fields in its
JSON response:
- `metadata_version`: the version from `importlib.metadata.version("clasi")`
- `source_path`: the resolved path of `clasi/__init__.py` from `importlib.util`

When these match the in-process `__version__`, the server is current. When
they diverge, the operator knows a restart is needed.

### 4. `close_sprint` gains `test_command` parameter

`close_sprint` in `artifact_tools.py` gains:
```
test_command: Optional[str] = None
```
- `None` (default): runs `uv run pytest` as before.
- `""` (empty string): skips the tests step entirely.
- Any other string: runs that command via `subprocess.run` with `shell=True`.

`_close_sprint_full` is updated to accept and use the parameter. The
`close_sprint` public tool passes it through.

### 5. Language-neutral init rule templates

`RULES` dict in `init_command.py`:
- `source-code.md`: the step "Run tests after changes: `uv run pytest`" is
  replaced with a language-neutral instruction to run the project's test suite.
- `git-commits.md`: the step "All tests pass (`uv run pytest`)" is replaced
  with "All tests pass (run the project's test suite)."

### 6. `docs/clasi/log/.gitignore` created during `clasi init`

`run_init` in `init_command.py` creates `<project_root>/docs/clasi/log/` and
writes a `.gitignore` containing `*.log` (and `*` as a fallback) to prevent
log files from surfacing in `git status`.

## Why

- **SUC-001** (MCP server fails fast): Lazy imports masked server staleness.
  Moving them to module level makes the failure manifest at startup, where
  the operator can act on it immediately rather than discovering it mid-session.

- **SUC-002** (Close sprint on non-Python project): The hardcoded
  `uv run pytest` in `_close_sprint_full` is the sole blocker for non-Python
  projects completing a sprint. A configurable `test_command` removes the
  assumption without breaking existing Python workflows.

- **SUC-003** (Language-neutral init): Embedding `uv run pytest` in installed
  rules teaches the model incorrect behavior for non-Python projects. Removing
  the references makes the rules accurate for any language. The `.gitignore`
  is a quality-of-life fix that prevents noise in `git status` for all project
  types.

## Impact on Existing Components

```mermaid
graph LR
    MCPServer[mcp_server.py<br/>run()] -->|eager import check| AT[artifact_tools.py]
    MCPServer -->|eager import check| PT[process_tools.py]
    AT -->|module-level| Sprint[clasi.sprint]
    AT -->|module-level| Todo[clasi.todo]
    AT -->|module-level| Artifact[clasi.artifact]
    AT -->|module-level| Ticket[clasi.ticket]
    AT -->|module-level| Versioning[clasi.versioning]
    AT -->|test_command param| CloseSprint[close_sprint / _close_sprint_full]
    PT -->|get_version enriched| GV[get_version tool]
    IC[init_command.py] -->|writes| LogGitignore[docs/clasi/log/.gitignore]
    IC -->|updates| Rules[source-code.md / git-commits.md]
```

| Component | Change |
|---|---|
| `clasi/tools/artifact_tools.py` | Move ~15 lazy imports to top-level; add `test_command` param to `close_sprint` / `_close_sprint_full` |
| `clasi/mcp_server.py` | Add preflight import check before tool registration |
| `clasi/tools/process_tools.py` | Move `clasi.frontmatter` import to top-level; enrich `get_version` response |
| `clasi/init_command.py` | Remove `uv run pytest` from rule templates; add log `.gitignore` creation |
| `clasi/plugin/skills/close-sprint/SKILL.md` | Document `test_command` parameter |
| Tests | New tests for preflight, `get_version` shape, `test_command` variants, init rules, init gitignore |

No other components change. Hook handlers, plan-to-todo, state DB, and
template system are unaffected.

## Migration Concerns

- **Backward compatibility**: `close_sprint` default (`test_command=None`)
  is unchanged. All callers without the parameter continue to run `uv run
  pytest`. No API breakage.
- **Import order side effects**: Promoting lazy imports to module level means
  any import-time failure surfaces at server startup rather than on first use.
  This is the intended behavior and requires no caller changes.
- **Init rules**: Existing projects that already ran `clasi init` retain their
  current rules. The updated templates only affect new `clasi init` runs or
  explicit re-runs. No migration of existing rule files is needed.
- **No data migration**: No DB schemas, MCP state, or artifact formats change.

## Design Rationale

### Decision: `test_command: Optional[str] = None` with empty-string-means-skip

**Context**: Three behaviors needed: default (pytest), skip, custom command.
Using `None`/empty-string/string maps cleanly to these without a separate
boolean flag, keeps the MCP schema simple, and is idiomatic Python.

**Alternatives considered**:
1. Separate `skip_tests: bool` parameter alongside `test_command`.
2. Sentinel string value like `"none"` or `"skip"`.

**Why this choice**: `Optional[str]` with empty-string semantics avoids
parameter proliferation and is self-documenting at the call site:
`test_command=""` reads as "empty command = no command".

**Consequences**: Callers must know that `""` means skip. This is documented
in the tool docstring and skill docs.

### Decision: Preflight as a startup check, not a runtime guard

**Context**: We could add a try/except around every tool call, or check
imports once at startup.

**Why this choice**: Startup failure is more honest — it prevents a server
that looks healthy (`get_version` passes) from silently failing on most tool
calls. Operators restart servers; they do not expect mid-session degradation.

**Consequences**: Any import failure in the checked modules prevents the
server from starting. This is acceptable because those modules are required
for the server to be useful.

## Open Questions

None. All decisions are informed by the existing codebase and the TODO
specifications.
