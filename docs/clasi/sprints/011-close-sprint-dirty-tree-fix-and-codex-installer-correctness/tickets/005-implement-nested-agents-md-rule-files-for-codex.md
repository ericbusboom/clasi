---
id: '005'
title: Implement nested AGENTS.md rule files for Codex
status: todo
use-cases:
  - SUC-007
depends-on: []
github-issue: ''
todo: ''
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Implement nested AGENTS.md rule files for Codex

## Description

Codex has no path-scoped rule equivalent to Claude's `.claude/rules/` directory. The
closest mechanism is nested `AGENTS.md` files at subdirectory roots — Codex (and all
other AGENTS.md-aware tools) reads the closest file upward in the directory tree, so
placing rule content in nested `AGENTS.md` files at the relevant directory roots gives
context-scoped guidance.

This ticket adds `_install_rules` and `_uninstall_rules` helpers to
`clasi/platforms/codex.py` that write two nested `AGENTS.md` files:

- `docs/clasi/AGENTS.md` — SE process rules: require MCP server check before any SE
  action; use CLASI MCP tools for sprint/ticket operations; do not create planning
  artifacts manually.
- `clasi/AGENTS.md` — source code rules: require a ticket in `in-progress` status
  before modifying source; reference the execute-ticket skill for the full flow.

These files are plain prose files (not marker-block managed). The Codex uninstaller
removes them by exact path.

## Acceptance Criteria

- [ ] After `clasi install --codex`, `docs/clasi/AGENTS.md` and `clasi/AGENTS.md` exist
      in the target directory.
- [ ] `docs/clasi/AGENTS.md` contains SE process rule content mentioning MCP server and
      CLASI MCP tools.
- [ ] `clasi/AGENTS.md` contains source-code rule content mentioning ticket status
      requirements.
- [ ] Neither file contains Claude-Code-specific syntax (e.g., no YAML frontmatter, no
      rule-file-specific metadata).
- [ ] After `clasi uninstall --codex`, both files are removed.
- [ ] Uninstall is non-destructive: if either file does not exist, uninstall skips it
      without error.
- [ ] Unit tests cover install (file existence and content substring checks) and uninstall
      (removal).

## Implementation Plan

### Approach

In `clasi/platforms/codex.py`:

1. Define two rule content constants (inline string literals — no external files needed):

   ```python
   _DOCS_CLASI_RULES = """\
   # CLASI SE Process Rules

   Before doing any SE process work in this directory:

   1. Verify the CLASI MCP server is running by calling get_version().
      If the call fails, stop and report the issue.
   2. Use CLASI MCP tools for all sprint, ticket, and TODO operations.
      Do not create sprint directories, tickets, or TODO files manually.
   3. Do not create planning artifacts (sprint.md, usecases.md,
      architecture-update.md, ticket files) outside the MCP tools.
   """

   _CLASI_SRC_RULES = """\
   # CLASI Source Code Rules

   Before modifying source code or tests in this directory:

   1. You must have a ticket in `in-progress` status, or the stakeholder
      said "out of process".
   2. If you have a ticket, follow the execute-ticket skill for the full
      implementation flow.
   3. Run the project test suite after making changes.
   """
   ```

2. Add `_install_rules(target: Path) -> None`:
   ```python
   def _install_rules(target: Path) -> None:
       docs_clasi = target / "docs" / "clasi"
       docs_clasi.mkdir(parents=True, exist_ok=True)
       (docs_clasi / "AGENTS.md").write_text(_DOCS_CLASI_RULES, encoding="utf-8")
       click.echo("  Wrote: docs/clasi/AGENTS.md")

       clasi_src = target / "clasi"
       clasi_src.mkdir(parents=True, exist_ok=True)
       (clasi_src / "AGENTS.md").write_text(_CLASI_SRC_RULES, encoding="utf-8")
       click.echo("  Wrote: clasi/AGENTS.md")
   ```

3. Add `_uninstall_rules(target: Path) -> None`:
   - Remove `docs/clasi/AGENTS.md` if it exists.
   - Remove `clasi/AGENTS.md` if it exists.
   - Log each action (or "not found, skipping" if absent).

4. Call `_install_rules(target)` from `install()`.
5. Call `_uninstall_rules(target)` from `uninstall()`.

**Note**: `clasi/AGENTS.md` would not exist in a fresh tmp_path test directory.
The `mkdir(exist_ok=True)` call is safe. In a real project the `clasi/` directory
already exists (it's the source package). The test should use a tmp_path that mirrors
this structure or verify the file is written to the correct path.

### Files to Modify

- `clasi/platforms/codex.py` — add constants, `_install_rules`, `_uninstall_rules`;
  update `install` and `uninstall`.
- `tests/unit/test_platform_codex.py` — add tests:
  - `test_install_rules_creates_agents_md_files`: assert existence and content.
  - `test_uninstall_rules_removes_files`: install then uninstall; assert removed.
  - `test_uninstall_rules_no_error_if_missing`: call uninstall on tmp_path with no
    nested files; assert no exception.

### Testing Plan

1. `uv run pytest tests/unit/test_platform_codex.py -v`
2. `uv run pytest` — full suite regression.

### Documentation Updates

Deferred to ticket 007 (README).
