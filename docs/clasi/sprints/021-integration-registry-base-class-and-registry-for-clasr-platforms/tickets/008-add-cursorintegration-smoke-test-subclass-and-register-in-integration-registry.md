---
id: "008"
title: "Add CursorIntegration smoke-test subclass and register in INTEGRATION_REGISTRY"
status: todo
use-cases: [SUC-008]
depends-on: ["006"]
github-issue: ""
todo: ""
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Add CursorIntegration smoke-test subclass and register in INTEGRATION_REGISTRY

## Description

Create `clasr/platforms/cursor.py` with `CursorIntegration` subclassing `MarkdownIntegration` (no skills). Add `"cursor": CursorIntegration` to `INTEGRATION_REGISTRY` in `clasr/registry.py`.

Class-level fields:
- `id = "cursor"`, `display_name = "Cursor"`
- `detect_files = [".cursor/"]`
- `target_root = Path(".cursor")`, `command_dir = Path(".cursor/rules")`, `rule_dir = Path(".cursor/rules")`
- `skill_dir = None`, `agent_dir = None`, `settings_file = None`
- `command_format = "md"`, `frontmatter_dialect = "yaml"`, `invoke_separator = "/"`
- `companion_files = []`

Cursor uses `.mdc` extension for rule files. `render_rule` is overridden to write `.mdc` output files instead of `.md`.

The key validation: adding Cursor requires only this file plus one line in `INTEGRATION_REGISTRY`. No changes to `IntegrationBase`, registry helpers, CLI dispatch logic, or the contract test file. If any of those need changes to accommodate Cursor, the sprint has surfaced a design flaw — stop and reassess.

## Acceptance Criteria

- [ ] `clasr/platforms/cursor.py` exists with `CursorIntegration` subclassing `MarkdownIntegration`.
- [ ] All 14 class-level fields declared with correct Cursor-specific values.
- [ ] `render_rule` overridden to emit `.mdc` files in `.cursor/rules/`.
- [ ] `INTEGRATION_REGISTRY` in `registry.py` has `"cursor": CursorIntegration`.
- [ ] `test_integration_contract.py` now shows 4 parametrized runs (claude, codex, copilot, cursor), all pass — with NO changes to the test file.
- [ ] `IntegrationBase`, registry helpers, and CLI dispatch unchanged.
- [ ] `uv run pytest` green.

## Implementation Plan

### Files to Create

- `clasr/platforms/cursor.py`

### Files to Modify

- `clasr/registry.py` — add `"cursor": CursorIntegration` line.

### Testing Plan

- `uv run pytest tests/clasr/test_integration_contract.py` — 4 runs, all pass.
- `uv run pytest` — full suite green.

### Documentation Updates

None.
