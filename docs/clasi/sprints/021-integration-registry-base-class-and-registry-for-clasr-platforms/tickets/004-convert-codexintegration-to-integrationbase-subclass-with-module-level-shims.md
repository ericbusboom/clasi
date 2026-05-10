---
id: "004"
title: "Convert CodexIntegration to IntegrationBase subclass with module-level shims"
status: todo
use-cases: [SUC-004]
depends-on: ["001", "003"]
github-issue: ""
todo: ""
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Convert CodexIntegration to IntegrationBase subclass with module-level shims

## Description

Refactor `clasr/platforms/codex.py` to expose `CodexIntegration`, subclassing `TomlIntegration` and `SkillsIntegration`. Same pattern as ticket 003 (Claude conversion). Module-level shims preserved for backward compatibility.

Class-level fields:
- `id = "codex"`, `display_name = "Codex"`
- `detect_files = [".codex/.clasr-manifest"]`
- `target_root = Path(".codex")`, `skill_dir = Path(".agents/skills")`, `agent_dir = Path(".codex/agents")`
- `command_dir = None`, `rule_dir = None` (Codex rules go to nested AGENTS.md, not a rule_dir), `settings_file = None`
- `command_format = "toml"`, `frontmatter_dialect = "toml"`, `invoke_separator = ":"`
- `companion_files = ["AGENTS.md"]`

Codex-specific rule logic (scoped rules to nested AGENTS.md, unscoped rules collected into root marker block) moves into `CodexIntegration.install()`. `_scope_to_dir` helper stays as a module-level function.

## Acceptance Criteria

- [ ] `CodexIntegration` class exists and subclasses `TomlIntegration` and `SkillsIntegration`.
- [ ] All 14 class-level fields declared with correct Codex-specific values.
- [ ] `mypy clasr/platforms/codex.py` passes clean.
- [ ] Module-level `install()` and `uninstall()` shims present.
- [ ] `tests/clasr/test_platform_codex.py` passes unchanged.
- [ ] `uv run pytest` green.

## Implementation Plan

### Approach

Edit `clasr/platforms/codex.py` in-place. Same structural transformation as ticket 003.

### Files to Modify

- `clasr/platforms/codex.py`

### Testing Plan

- `uv run pytest tests/clasr/test_platform_codex.py` — unchanged.
- `uv run pytest` — full suite green.
- `mypy clasr/platforms/codex.py`.

### Documentation Updates

None.
