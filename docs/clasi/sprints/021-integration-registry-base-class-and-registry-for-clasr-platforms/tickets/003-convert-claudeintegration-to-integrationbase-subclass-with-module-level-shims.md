---
id: "003"
title: "Convert ClaudeIntegration to IntegrationBase subclass with module-level shims"
status: todo
use-cases: [SUC-003]
depends-on: ["001"]
github-issue: ""
todo: ""
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Convert ClaudeIntegration to IntegrationBase subclass with module-level shims

## Description

Refactor `clasr/platforms/claude.py` to expose `ClaudeIntegration`, which subclasses `MarkdownIntegration` and `SkillsIntegration`. Move the install/uninstall logic from the module-level `install()` and `uninstall()` free functions into class methods. Declare all required class-level fields.

Retain module-level shim functions so existing tests and callers continue to work unchanged:

```python
def install(source, target, provider, copy=False):
    ClaudeIntegration().install(source, target, provider, copy)

def uninstall(target, provider):
    ClaudeIntegration().uninstall(target, provider)
```

Class-level fields to declare:
- `id = "claude"`, `display_name = "Claude Code"`
- `detect_files = [".claude/.clasr-manifest"]`
- `target_root = Path(".claude")`, `skill_dir = Path(".claude/skills")`, `agent_dir = Path(".claude/agents")`, `rule_dir = Path(".claude/rules")`
- `command_dir = None`, `settings_file = Path(".claude/settings.json")`
- `command_format = "md"`, `frontmatter_dialect = "yaml"`, `invoke_separator = "/"`
- `companion_files = ["AGENTS.md", "CLAUDE.md"]`

Private helpers `_discover_other_provider` and `_cleanup_empty_dirs` remain as module-level functions called by the class methods.

## Acceptance Criteria

- [ ] `ClaudeIntegration` class exists in `clasr/platforms/claude.py` and subclasses `MarkdownIntegration` and `SkillsIntegration`.
- [ ] All 14 class-level fields are declared with correct values.
- [ ] `ClaudeIntegration` passes `mypy` with no `IntegrationBase` violations.
- [ ] Module-level `install()` and `uninstall()` shims are present.
- [ ] `tests/clasr/test_platform_claude.py` passes unchanged.
- [ ] `uv run pytest` green.

## Implementation Plan

### Approach

Edit `clasr/platforms/claude.py` in-place. Move function body logic into `ClaudeIntegration.install()` and `ClaudeIntegration.uninstall()`. Add class-level field declarations above the method definitions. Add shim functions below the class.

### Files to Modify

- `clasr/platforms/claude.py`

### Files to Create

None.

### Testing Plan

- `uv run pytest tests/clasr/test_platform_claude.py` — must pass unchanged.
- `uv run pytest` — full suite green.
- `mypy clasr/platforms/claude.py`.

### Documentation Updates

None.
