---
id: "002"
title: "Refactor init_command into clasi/platforms/claude.py"
status: done
use-cases:
  - SUC-001
  - SUC-002
  - SUC-004
depends-on: []
github-issue: ""
todo: ""
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Refactor init_command into clasi/platforms/claude.py

## Description

Extract the Claude-specific install logic from `clasi/init_command.py` into a new
`clasi/platforms/claude.py` module. This is a pure structural refactor — no behavior
changes. The goal is to give Claude install/uninstall a clean, independently testable
home so that the Codex installer (ticket 004) can be a parallel sibling without mixing
Claude-specific code back into `init_command.py`.

The refactor also creates the `clasi/platforms/` package (`__init__.py`).

After this ticket:
- `clasi/platforms/claude.py` exposes `install(target: Path, mcp_config: dict) -> None`
  and `uninstall(target: Path) -> None`.
- `clasi/init_command.py` retains only shared setup: MCP server detection (`_detect_mcp_command`),
  TODO directory creation, and log `.gitignore` creation. It delegates Claude install to
  `clasi.platforms.claude.install(target, mcp_config)`.
- All existing `clasi init` behavior is preserved exactly.

## Acceptance Criteria

- [x] `clasi/platforms/__init__.py` exists (may be empty).
- [x] `clasi/platforms/claude.py` contains `install(target: Path, mcp_config: dict) -> None`
      and `uninstall(target: Path) -> None`.
- [x] `install` contains the logic for: `_write_claude_md`, `_install_plugin_content`,
      `_update_settings_json`, `_create_rules`, and settings.json hook update.
- [x] `uninstall` removes the CLASI marker block from `CLAUDE.md`, CLASI-managed
      `.claude/skills/`, `.claude/agents/`, `.claude/rules/`, CLASI hook entries in
      `.claude/settings.json`, and the CLASI MCP permission from `.claude/settings.local.json`.
- [x] `clasi/init_command.py` calls `clasi.platforms.claude.install(target_path, mcp_config)`
      for the Claude path. Shared steps (MCP detection, TODO dirs, log dir) remain in
      `init_command.py`.
- [x] All existing `tests/unit/test_init_command.py` tests pass without modification to
      the tests themselves.
- [x] No new behavior is introduced — this is refactor only.

## Implementation Plan

### Files to create

- `clasi/platforms/__init__.py` — empty
- `clasi/platforms/claude.py` — extract from `init_command.py`

### Files to modify

- `clasi/init_command.py` — slim down to shared setup + delegation
- `tests/unit/test_init_command.py` — add at minimum one integration test that verifies
  `run_init` (with default args) produces the same file set as before

### Approach

1. Create `clasi/platforms/` directory with empty `__init__.py`.
2. Create `clasi/platforms/claude.py`. Move these private helpers into it:
   - `_write_claude_md` (rename to a module-level function; keep `_CLAUDE_MD_CONTENT`,
     `_CLAUDE_MD_BODY`, `_AGENTS_SECTION_START`, `_AGENTS_SECTION_END` constants here)
   - `_install_plugin_content`
   - `_create_rules` (and the `RULES` dict)
   - The `.claude/settings.json` hooks update logic
   - `_update_settings_json`
3. Define `install(target: Path, mcp_config: dict) -> None` in `claude.py` that
   calls the extracted helpers in the same order as the current `run_init` Claude steps.
4. Define `uninstall(target: Path) -> None` in `claude.py` that reverses each
   Claude-managed artifact:
   - Remove CLASI marker block from `CLAUDE.md` (leave rest of file intact).
   - Delete `target/.claude/skills/` contents installed by CLASI (skip user-added files
     by only deleting files whose names match CLASI skill names from `RULES` / plugin).
   - Delete `target/.claude/agents/` contents installed by CLASI.
   - Delete `target/.claude/rules/` files matching CLASI rule names.
   - Remove CLASI hook entries from `.claude/settings.json` (leave other hooks intact).
   - Remove `mcp__clasi__*` from `.claude/settings.local.json` allow list.
5. Slim `init_command.py`:
   - Keep `_detect_mcp_command`, TODO dir creation, log dir creation.
   - Replace inline Claude steps with: `from clasi.platforms.claude import install as claude_install; claude_install(target_path, mcp_config)`.
   - Update `run_init` signature to add `claude: bool = True, codex: bool = False`
     parameters (codex path is a no-op in this ticket — just the parameter added).
6. Run existing tests and confirm all pass.

### Testing plan

```
uv run pytest tests/unit/test_init_command.py -v
uv run pytest -x
```

Verify: no new failures; the refactored code produces identical file output for
`run_init(target=".")` as the pre-refactor code did.

### Documentation updates

None — this is internal restructuring with no user-visible change.
