---
status: in-progress
sprint: '026'
tickets:
- 026-003
---

# Rename Source Directory and Code References to "clasi"

## Problem

The Python package is named `claude_agent_skills` but the project is
called CLASI. The package name appears everywhere: import paths, entry
points, pyproject.toml, test files, documentation, MCP tool prefixes
(`mcp__clasi__` already uses the short name but imports reference the
long name). The mismatch is confusing and the long name is unwieldy.

## Proposed Changes

1. **Rename `claude_agent_skills/` to `clasi/`** — the top-level
   Python package directory.

2. **Update all imports** — every `from claude_agent_skills.X import Y`
   and `import claude_agent_skills.X` becomes `from clasi.X import Y`
   and `import clasi.X`.

3. **Update pyproject.toml** — package name, entry point
   (`clasi = "clasi.cli:cli"`), package data paths, and any other
   references.

4. **Update test files** — all imports in `tests/` referencing the
   old package name.

5. **Update documentation** — CLAUDE.md, agent definitions, skills,
   and any other docs that reference `claude_agent_skills`.

6. **Update init_command.py** — paths to bundled content, template
   references.

7. **Verify MCP tool prefixes** — `mcp__clasi__*` should continue to
   work since they already use the short name.

## Scope

This is a mechanical rename — large in terms of files touched but
low risk. Every change is a find-and-replace of the package name.
Should be done in a single sprint (or even a single ticket) to avoid
partial-rename states.

## Risk

- Editable installs (`pip install -e .`) will need to be re-run after
  the rename.
- Any external project that imports `claude_agent_skills` will break.
  Since this is a CLI tool installed as `clasi`, external imports are
  unlikely but worth checking.
