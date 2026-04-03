---
status: done
sprint: '003'
tickets:
- 003-005
---

# Move remaining clasi/ content dirs into clasi/plugin/ and remove originals

Sprint 003 moved `plugin/` into `clasi/plugin/`, but several parallel directories
inside `clasi/` still duplicate or overlap with plugin content. The goal: all
installable content (agents, skills, hooks, rules, instructions) lives in
`clasi/plugin/`. Python code references it there. `clasi init` copies it out.

## Directories to consolidate

### clasi/instructions/, clasi/rules/, clasi/skills/ — dead, no Python refs

These markdown files are not imported by any Python code. They are older versions
of content that now lives in `clasi/plugin/skills/` and `clasi/plugin/hooks/`.
Audit for any unique content worth merging into `clasi/plugin/`, then delete.

### clasi/hooks/ — duplicate of clasi/plugin/hooks/

`clasi/hooks/role_guard.py` is identical to `clasi/plugin/hooks/role_guard.py`.
Tests in `test_role_guard.py` reference `clasi/hooks/` by path. Update tests to
point at `clasi/plugin/hooks/`, then delete `clasi/hooks/`.

### clasi/agents/ — used by contracts.py

13 agents with `contract.yaml` files, used by `contracts.py` for agent return
validation. Move the `contract.yaml` files (and any agent.md content not already
in `clasi/plugin/agents/`) into `clasi/plugin/agents/`. Update `contracts.py` to
search `clasi/plugin/agents/` instead of `clasi/agents/`. Then delete `clasi/agents/`.

## End state

After this work, the only content directories inside `clasi/` should be:
- `clasi/plugin/` — all installable content (agents, skills, hooks, rules, instructions)
- `clasi/templates/` — sprint/ticket templates used by MCP tools
- `clasi/tools/` — Python MCP tool implementations
- Standard Python modules (*.py files)

No more `clasi/agents/`, `clasi/hooks/`, `clasi/instructions/`, `clasi/rules/`,
`clasi/skills/`.
