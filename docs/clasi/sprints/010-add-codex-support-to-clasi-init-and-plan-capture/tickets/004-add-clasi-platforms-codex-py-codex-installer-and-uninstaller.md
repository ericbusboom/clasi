---
id: "004"
title: "Add clasi/platforms/codex.py — Codex installer and uninstaller"
status: done
use-cases:
  - SUC-003
  - SUC-004
  - SUC-007
  - SUC-008
  - SUC-012
depends-on:
  - "001"
  - "002"
github-issue: ""
todo: ""
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Add clasi/platforms/codex.py — Codex installer and uninstaller

## Description

Create `clasi/platforms/codex.py` with two public functions: `install(target, mcp_config)`
and `uninstall(target)`. This implements the Codex platform integration that `clasi init
--codex` will invoke.

The installer writes four artifacts:
1. `AGENTS.md` — CLASI marker-managed section pointing to `.agents/skills/se/SKILL.md`.
2. `.codex/config.toml` — TOML config with `[mcp_servers.clasi]` and `codex_hooks = true`.
3. `.codex/hooks.json` — Codex Stop hook calling `clasi hook codex-plan-to-todo`.
4. `.agents/skills/se/SKILL.md` — Codex-readable SE skill, sourced from bundled plugin.

All writes are idempotent: re-running updates CLASI-managed sections without clobbering
user content.

The uninstaller is the reverse: removes only CLASI-owned sections/entries from each file.

Depends on ticket 001 (tomli/tomli-w) and ticket 002 (platforms package exists).

## Acceptance Criteria

- [x] `clasi/platforms/codex.py` defines `install(target: Path, mcp_config: dict) -> None`.
- [x] `install` creates or updates `AGENTS.md` with a CLASI marker block
      (`<!-- CLASI:START -->` / `<!-- CLASI:END -->`).
- [x] `install` writes `.codex/config.toml` with `[mcp_servers.clasi]` using the
      provided `mcp_config` dict (same detection result as Claude path).
- [x] `install` writes `.codex/hooks.json` with a `Stop` hook entry:
      `{"command": "clasi", "args": ["hook", "codex-plan-to-todo"]}`.
- [x] `install` writes `.agents/skills/se/SKILL.md` sourced from the bundled plugin
      skills content (same file served to Claude's `.claude/skills/se/SKILL.md`).
- [x] Re-running `install` is idempotent: CLASI section in `AGENTS.md` is updated, not
      duplicated; TOML and JSON entries are merged, not duplicated.
- [x] `clasi/platforms/codex.py` defines `uninstall(target: Path) -> None`.
- [x] `uninstall` removes the CLASI marker block from `AGENTS.md` (preserves rest).
- [x] `uninstall` removes the `clasi` key from `[mcp_servers]` in `.codex/config.toml`
      and the `codex_hooks` key if present; leaves other keys intact.
- [x] `uninstall` removes the CLASI Stop hook entry from `.codex/hooks.json`; leaves
      other entries intact.
- [x] `uninstall` removes `.agents/skills/se/SKILL.md`; leaves `.agents/skills/`
      subtrees it did not create.
- [x] TOML read/write uses the `tomllib`/`tomli` shim and `tomli_w` (from ticket 001).
- [x] Tests in `tests/unit/test_platform_codex.py` cover install, idempotency, uninstall,
      and partial uninstall (user content preserved).

## Implementation Plan

### Files to create

- `clasi/platforms/codex.py`
- `tests/unit/test_platform_codex.py`

### Approach

**AGENTS.md marker pattern**: reuse the same `_AGENTS_SECTION_START` / `_AGENTS_SECTION_END`
marker constants already defined in `clasi/platforms/claude.py` (or a shared constants
module if the implementer prefers). The body content should be a one-paragraph pointer:
"This project uses the CLASI SE process. Skills are in `.agents/skills/se/SKILL.md`."

**`.codex/config.toml` merge**:
1. Read existing TOML if present (`tomllib.loads`), else start with `{}`.
2. Set `data["mcp_servers"]["clasi"] = {<mcp_config fields>}` and
   `data["codex_hooks"] = True`.
3. Write back with `tomli_w.dumps(data)`.

**`.codex/hooks.json` merge**:
1. Read existing JSON if present, else `{"hooks": {}}`.
2. Set `hooks["Stop"] = [{"command": "clasi", "args": ["hook", "codex-plan-to-todo"]}]`
   (or append to existing Stop list if the entry is not already present).
3. Write back.

**`.agents/skills/se/SKILL.md`**:
Find the source from `_PLUGIN_DIR / "skills" / "se" / "SKILL.md"` (same pattern as
`_install_plugin_content` in `claude.py`). Write to `target / ".agents" / "skills" /
"se" / "SKILL.md"`.

**`uninstall`**:
- `AGENTS.md`: remove the CLASI:START–CLASI:END block. If the file becomes empty after
  removal, delete it.
- `.codex/config.toml`: read, pop `mcp_servers.clasi` and `codex_hooks`, write back.
  If the file becomes effectively empty (`{}`), delete it.
- `.codex/hooks.json`: read, remove only the CLASI Stop hook entry from the `Stop` list.
  If the list becomes empty, remove the `Stop` key. If hooks becomes `{}`, delete the file.
- `.agents/skills/se/SKILL.md`: delete. If `.agents/skills/se/` directory is now empty,
  delete it too.

### Testing plan

Use `tmp_path` fixtures for a fresh project directory per test.

Tests to write:
- `test_codex_install_creates_all_artifacts`: run `install`, assert all 4 artifacts exist.
- `test_codex_install_idempotent`: run `install` twice, assert no duplication in any file.
- `test_codex_install_agents_md_preserves_user_content`: create `AGENTS.md` with user
  content before install, assert it is preserved after install.
- `test_codex_uninstall_removes_clasi_sections`: install then uninstall, assert CLASI
  sections removed but user content intact.
- `test_codex_uninstall_partial`: uninstall when some files are missing — should be
  idempotent (no errors).

```
uv run pytest tests/unit/test_platform_codex.py -v
uv run pytest -x
```

### Documentation updates

None — behavior is exposed through the CLI (tickets 005 and 007).
