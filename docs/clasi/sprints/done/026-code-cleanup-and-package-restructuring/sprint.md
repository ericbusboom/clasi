---
id: '026'
title: Code Cleanup and Package Restructuring
status: done
phase: planning-docs
branch: sprint/026-code-cleanup-and-package-restructuring
todos:
- code-review-procedural-bypasses.md
- refactor-tools-into-module.md
- rename-source-dir-to-clasi.md
---

# Sprint 026: Code Cleanup and Package Restructuring

## Goals

1. **Fix procedural bypasses in artifact_tools.py** — The code review
   identified 28 places where MCP tool functions bypass domain objects
   (Project, Sprint, Ticket, Todo, Artifact) with raw frontmatter
   mutations, duplicate lookups, and direct DB calls. Refactor these
   to delegate to the domain API.

2. **Move *_tools.py into a tools/ subpackage** — Extract
   `process_tools.py`, `artifact_tools.py`, and `dispatch_tools.py`
   into `claude_agent_skills/tools/` to separate the MCP interface
   layer from domain classes and shared modules.

3. **Rename package from claude_agent_skills to clasi** — The project
   is called CLASI but the Python package still uses the long name.
   Rename the directory and update all imports, pyproject.toml, tests,
   and documentation.

## Scope

### In Scope

- Refactoring artifact_tools.py to use domain object methods instead
  of raw procedural code (all 28 issues from the code review TODO)
- Creating `claude_agent_skills/tools/` package and moving tool files
- Renaming the top-level package directory from `claude_agent_skills/`
  to `clasi/`
- Updating all imports, entry points, and test references
- Fixing inline review comments (issues 25-28) as part of cleanup

### Out of Scope

- New features or new MCP tools
- Changes to domain object APIs (Sprint, Ticket, Todo, etc.)
- Changes to MCP tool names or signatures
- External documentation or README updates beyond what the rename requires

## Dependency Order

The three work items must be executed in sequence:

1. **Procedural bypasses first** — These changes touch artifact_tools.py
   heavily. Doing the rename or move first would create merge conflicts
   with every bypass fix.
2. **Tools subpackage second** — Once artifact_tools.py is clean, move
   the tool files into `tools/`. This is a mechanical move with import
   updates.
3. **Package rename last** — The rename touches every import in the
   project. Doing it last means the prior two items are stable and the
   rename is a clean find-and-replace pass.
