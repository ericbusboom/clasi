---
id: '007'
title: Wire clasr/cli.py install and uninstall to use INTEGRATION_REGISTRY dispatch
status: done
use-cases:
- SUC-007
depends-on:
- '006'
github-issue: ''
todo: ''
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Wire clasr/cli.py install and uninstall to use INTEGRATION_REGISTRY dispatch

## Description

Update `_cmd_install` and `_cmd_uninstall` in `clasr/cli.py` to resolve platforms via `INTEGRATION_REGISTRY` instead of importing each platform module by name.

Before (current state):
```python
from clasr.platforms import claude, codex, copilot
if args.claude:
    claude.install(source, target, args.provider, copy=args.copy)
```

After:
```python
from clasr.registry import INTEGRATION_REGISTRY
selected = []
if args.claude:
    selected.append("claude")
if args.codex:
    selected.append("codex")
if args.copilot:
    selected.append("copilot")
for name in selected:
    INTEGRATION_REGISTRY[name]().install(source, target, args.provider, copy=args.copy)
```

The `--claude`, `--codex`, `--copilot` CLI flags continue to exist — only the dispatch mechanism changes. Existing CLI behavior is identical from the user's perspective.

## Acceptance Criteria

- [x] `_cmd_install` resolves platforms via `INTEGRATION_REGISTRY`, not direct module imports.
- [x] `_cmd_uninstall` resolves platforms via `INTEGRATION_REGISTRY`.
- [x] `clasr install --claude --source ... --provider ...` works end-to-end.
- [x] `clasr uninstall --claude --provider ...` works end-to-end.
- [x] `tests/clasr/test_cli.py` passes unchanged.
- [x] `uv run pytest` green.

## Implementation Plan

### Files to Modify

- `clasr/cli.py` — update `_cmd_install` and `_cmd_uninstall`.

### Testing Plan

- `uv run pytest tests/clasr/test_cli.py` — unchanged.
- `uv run pytest` — full suite green.

### Documentation Updates

None (user-facing CLI flags unchanged).
