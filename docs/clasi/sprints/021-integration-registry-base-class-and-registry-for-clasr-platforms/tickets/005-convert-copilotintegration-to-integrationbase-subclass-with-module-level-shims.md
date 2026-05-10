---
id: "005"
title: "Convert CopilotIntegration to IntegrationBase subclass with module-level shims"
status: todo
use-cases: [SUC-005]
depends-on: ["001", "004"]
github-issue: ""
todo: ""
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Convert CopilotIntegration to IntegrationBase subclass with module-level shims

## Description

Refactor `clasr/platforms/copilot.py` to expose `CopilotIntegration`, subclassing `MarkdownIntegration` and `SkillsIntegration`. Module-level shims preserved.

Class-level fields:
- `id = "copilot"`, `display_name = "GitHub Copilot"`
- `detect_files = [".github/.clasr-manifest"]`
- `target_root = Path(".github")`, `skill_dir = Path(".agents/skills")`, `agent_dir = Path(".github/agents")`, `rule_dir = Path(".github/instructions")`
- `command_dir = None`, `settings_file = None`
- `command_format = "md"`, `frontmatter_dialect = "yaml"`, `invoke_separator = "/"`
- `companion_files = [".github/copilot-instructions.md"]`

Copilot overrides `render_agent` to append `.agent.md` suffix and `render_rule` to append `.instructions.md` suffix (divergences from `MarkdownIntegration` defaults). The directory-level `.github/skills/ → .agents/skills/` symlink logic in `install()` is Copilot-specific and stays in `CopilotIntegration.install()`.

## Acceptance Criteria

- [ ] `CopilotIntegration` class exists and subclasses `MarkdownIntegration` and `SkillsIntegration`.
- [ ] All 14 class-level fields declared with correct Copilot-specific values.
- [ ] `render_agent` override appends `.agent.md`; `render_rule` override appends `.instructions.md`.
- [ ] `mypy clasr/platforms/copilot.py` passes clean.
- [ ] Module-level `install()` and `uninstall()` shims present.
- [ ] `tests/clasr/test_platform_copilot.py` passes unchanged.
- [ ] `uv run pytest` green.

## Implementation Plan

### Approach

Edit `clasr/platforms/copilot.py` in-place. Same structural pattern as tickets 003 and 004, with the additional rendering overrides for Copilot's naming conventions.

### Files to Modify

- `clasr/platforms/copilot.py`

### Testing Plan

- `uv run pytest tests/clasr/test_platform_copilot.py` — unchanged.
- `uv run pytest` — full suite green.
- `mypy clasr/platforms/copilot.py`.

### Documentation Updates

None.
