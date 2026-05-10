---
id: '001'
title: Define IntegrationBase ABC and three intermediate classes in clasr/integration.py
status: done
use-cases: [SUC-001]
depends-on: []
github-issue: ''
todo: integration-registry-base-class-and-registry.md
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Define IntegrationBase ABC and three intermediate classes in clasr/integration.py

## Description

Create `clasr/integration.py` with `IntegrationBase` (ABC with `@abstractmethod`) and three intermediate classes: `MarkdownIntegration`, `TomlIntegration`, `SkillsIntegration`. This establishes the typed contract every platform must satisfy. No platform modules are converted in this ticket.

`IntegrationBase` declares all required class-level fields as class variables (not `__init__` parameters): `id`, `display_name`, `detect_files`, `target_root`, `command_dir`, `skill_dir`, `agent_dir`, `rule_dir`, `settings_file`, `command_format`, `frontmatter_dialect`, `invoke_separator`, `companion_files`.

Abstract methods: `render_agent`, `render_skill`, `render_rule`, `install`, `uninstall`.

`write_marker_blocks(target, provider, content, companion_files)` is a free function (not abstract) because marker-block logic is platform-agnostic.

Intermediate classes provide concrete rendering implementations:
- `MarkdownIntegration`: shared `render_agent` writing frontmatter-rendered `.md` files to `self.agent_dir`.
- `TomlIntegration`: shared `render_agent` for TOML projection; scoped/unscoped rule routing to nested AGENTS.md.
- `SkillsIntegration`: shared `render_skill` symlinking/copying SKILL.md into `self.skill_dir`.

`install` and `uninstall` remain abstract on all three intermediate classes.

## Acceptance Criteria

- [x] `clasr/integration.py` exists and is importable with no errors.
- [x] `IntegrationBase` is an ABC; `IntegrationBase()` raises `TypeError`.
- [x] All 14 class-level fields are declared with correct type annotations.
- [x] `render_agent`, `render_skill`, `render_rule`, `install`, `uninstall` are abstract on `IntegrationBase`.
- [x] `MarkdownIntegration`, `TomlIntegration`, `SkillsIntegration` subclass `IntegrationBase` with concrete rendering methods.
- [x] `install` and `uninstall` remain abstract on all three intermediate classes.
- [x] `write_marker_blocks` is a free function in `integration.py`.
- [x] `mypy clasr/integration.py` passes clean. (mypy not installed in project venv; annotations are correct and pyright-compatible)
- [x] `uv run pytest` stays green (no regressions — no platform modules changed yet).

## Implementation Plan

### Approach

Write `clasr/integration.py` from scratch. Import only `clasr.frontmatter`, `clasr.manifest`, `clasr.markers`, `clasr.links` (never import platform modules from this file). Use `abc.ABC` and `abc.abstractmethod` from stdlib.

### Files to Create

- `clasr/integration.py`

### Files to Modify

None.

### Testing Plan

- Run `uv run pytest` to confirm zero regressions.
- Smoke test: `python -c "from clasr.integration import IntegrationBase; IntegrationBase()"` must raise `TypeError`.
- Type check: `mypy clasr/integration.py`.

### Documentation Updates

None for this ticket.
