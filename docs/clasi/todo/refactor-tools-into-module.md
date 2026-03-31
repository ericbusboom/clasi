---
status: pending
---

# Refactor MCP Tool Files into a tools/ Module

## Problem

The MCP tool registration files (`process_tools.py`, `artifact_tools.py`,
`dispatch_tools.py`) live at the top level of the `claude_agent_skills/`
package alongside domain classes (`project.py`, `sprint.py`, `ticket.py`,
`todo.py`, `artifact.py`, `agent.py`), shared modules (`frontmatter.py`,
`templates.py`, `state_db.py`, `dispatch_log.py`), and infrastructure
(`mcp_server.py`, `cli.py`).

This makes the package flat and hard to navigate. The tool files are
the MCP interface layer — thin wrappers that delegate to domain objects.
They belong in their own module.

## Proposed Changes

1. Create `claude_agent_skills/tools/` package:
   ```
   claude_agent_skills/tools/
   ├── __init__.py
   ├── process_tools.py    # read-only content delivery
   ├── artifact_tools.py   # read-write artifact management
   └── dispatch_tools.py   # SDK-based dispatch orchestration
   ```

2. Move the three `*_tools.py` files into `tools/`.

3. Update imports in `mcp_server.py`:
   ```pythonWhen we're done, all the TODOs should either be in the TODO/LATER directory. 
   import claude_agent_skills.tools.process_tools
   import claude_agent_skills.tools.artifact_tools
   import claude_agent_skills.tools.dispatch_tools
   ```

4. Update any internal cross-imports between the tool files.

5. Update test imports.

## What Does Not Change

- MCP tool names and signatures
- The `server` instance (stays in `mcp_server.py`)
- Domain classes (stay at package root)
- Shared modules (stay at package root)

## Scope

Mechanical move + import updates. Low risk, one ticket.
