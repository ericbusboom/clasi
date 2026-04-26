---
id: '004'
title: Add .codex/agents/<name>.toml sub-agent install and uninstall
status: done
use-cases:
  - SUC-004
  - SUC-005
depends-on: []
github-issue: ''
todo: ''
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Add .codex/agents/<name>.toml sub-agent install and uninstall

## Description

Codex's native sub-agent feature uses TOML definition files at
`.codex/agents/<name>.toml`. CLASI has three active agents (`team-lead`,
`sprint-planner`, `programmer`) defined as Markdown files in
`clasi/plugin/agents/<name>/agent.md`, but the Codex installer does not write these
TOML files. This ticket adds `_install_agents` and `_uninstall_agents` helper functions
to `clasi/platforms/codex.py` and hooks them into the `install` and `uninstall` public
functions.

**Known limitation**: the `developer_instructions` content is the `agent.md` body
verbatim. Some Claude-Code-specific phrasing will be present (e.g., "dispatch via Agent
tool"). A translation layer is deferred to a future sprint.

## Acceptance Criteria

- [x] After `clasi install --codex`, `.codex/agents/team-lead.toml`,
      `.codex/agents/sprint-planner.toml`, and `.codex/agents/programmer.toml` exist in
      the target directory.
- [x] Each TOML file round-trip parses via `tomllib.loads` (no parse errors).
- [x] Each TOML file contains `name` (string, non-empty), `description` (string, may
      be empty), and `developer_instructions` (string, non-empty) fields.
- [x] `developer_instructions` is the agent.md body with YAML frontmatter stripped.
- [x] `description` falls back to `""` if absent from frontmatter.
- [x] After `clasi uninstall --codex`, the three TOML files are removed.
- [x] Uninstall does not remove user-added TOML files in `.codex/agents/`.
- [x] If `.codex/agents/` is empty after uninstall, the directory is removed.
- [x] Unit tests cover install (TOML shape assertions) and uninstall (file removal,
      user-file preservation).

## Implementation Plan

### Approach

In `clasi/platforms/codex.py`:

1. Add helper `_strip_frontmatter(text: str) -> str` that removes the leading YAML block
   (everything between the first `---` pair, inclusive) and strips leading/trailing
   whitespace from the remainder.

2. Add `_install_agents(target: Path) -> None`:
   ```python
   _ACTIVE_AGENTS = ["team-lead", "sprint-planner", "programmer"]

   def _install_agents(target: Path) -> None:
       agents_dir = target / ".codex" / "agents"
       agents_dir.mkdir(parents=True, exist_ok=True)
       for name in _ACTIVE_AGENTS:
           agent_md = _PLUGIN_DIR / "agents" / name / "agent.md"
           if not agent_md.exists():
               click.echo(f"  Warning: plugin/agents/{name}/agent.md not found, skipping")
               continue
           text = agent_md.read_text(encoding="utf-8")
           fm = _parse_frontmatter(text)  # minimal frontmatter parser
           body = _strip_frontmatter(text)
           toml_name = name  # directory name is the agent name
           data = {
               "name": fm.get("title", name),
               "description": fm.get("description", ""),
               "developer_instructions": body,
           }
           dest = agents_dir / f"{toml_name}.toml"
           dest.write_text(tomli_w.dumps(data), encoding="utf-8")
           click.echo(f"  Wrote: .codex/agents/{toml_name}.toml")
   ```

3. Add `_uninstall_agents(target: Path) -> None`:
   - Remove each `<name>.toml` from `.codex/agents/` for names in `_ACTIVE_AGENTS`.
   - If `.codex/agents/` is empty after removal, remove it.

4. Add a minimal `_parse_frontmatter(text: str) -> dict` helper that reads YAML-style
   `key: value` lines from between the first `---` pair. (Do not import `yaml` — simple
   line-by-line parsing is sufficient for the flat frontmatter used in agent.md files.)

5. Call `_install_agents(target)` from `install()`.
6. Call `_uninstall_agents(target)` from `uninstall()`.

### Files to Modify

- `clasi/platforms/codex.py` — add `_ACTIVE_AGENTS`, `_strip_frontmatter`,
  `_parse_frontmatter`, `_install_agents`, `_uninstall_agents`; update `install` and
  `uninstall`.
- `tests/unit/test_platform_codex.py` — add tests:
  - `test_install_agents_creates_toml_files`: call `install()` in tmp_path, assert each
    TOML exists and round-trip parses with required fields.
  - `test_uninstall_agents_removes_toml_files`: install then uninstall; assert files gone.
  - `test_uninstall_agents_preserves_user_files`: install, add a user file, uninstall;
    assert user file remains.

### Testing Plan

1. `uv run pytest tests/unit/test_platform_codex.py -v`
2. `uv run pytest` — full suite regression.

### Documentation Updates

Deferred to ticket 007 (README). Add a code comment noting the known limitation about
Claude-specific phrasing in `developer_instructions`.
