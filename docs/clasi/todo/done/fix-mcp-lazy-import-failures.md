---
status: done
sprint: '007'
tickets:
- '001'
---

# Fix MCP tool failures from stale server process (lazy imports)

Lazy imports in `artifact_tools.py` cause `ModuleNotFoundError` for
`clasi.sprint`, `clasi.todo`, `clasi.artifact` when the MCP server was
started from an older source snapshot. Tools like `list_sprints`,
`list_tickets`, `list_todos`, and `read_artifact_frontmatter` fail,
while tools whose handlers don't hit those imports (`get_version`,
`get_sprint_phase`, `get_use_case_coverage`) work fine.

## Root cause

Handler functions import `clasi.sprint`, `clasi.todo`, `clasi.artifact`,
`clasi.ticket`, and `clasi.versioning` lazily inside function bodies
rather than at module level. If the server process was started before
those modules existed on disk (or from a stale snapshot), Python's
negative import cache pins `ModuleNotFoundError` for the life of the
process.

## Proposed fixes

1. **Eager top-level imports in `artifact_tools.py`**: Move all lazy
   `from clasi.{sprint,todo,artifact,ticket,versioning}` imports to
   module level so the server fails fast at startup if the source tree
   is inconsistent.

2. **Preflight import check in `mcp_server.py` `run()`**: Before
   registering tools, eagerly import all required submodules and abort
   with a clear error banner if any fail.

3. **Enrich `get_version`**: Return `importlib.metadata.version("clasi")`
   alongside the current `__version__`, plus the resolved source path,
   so staleness is detectable from a single `get_version` call.

## Repro steps

1. Install clasi in an editable pipx venv at a commit predating the
   sprint/todo/artifact submodule split.
2. Start the MCP server (`uv run clasi mcp`) from a project with
   `.mcp.json` pointing at it.
3. Update the source tree so those submodules now exist on disk.
4. Without restarting the server, call `list_sprints`, `list_todos`,
   `list_tickets` -- they all fail with `No module named 'clasi.X'`.

## Notes

- `clasi.mcp` import failure in the reporter's probe is a non-issue --
  the module is `clasi.mcp_server`, not `clasi.mcp`. The logger name
  `clasi.mcp` is just a logger namespace.
- Also check `process_tools.py` for one lazy import of
  `clasi.frontmatter` at line 447.
