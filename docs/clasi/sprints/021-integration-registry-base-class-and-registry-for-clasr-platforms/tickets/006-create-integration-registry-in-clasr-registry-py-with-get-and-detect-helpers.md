---
id: "006"
title: "Create INTEGRATION_REGISTRY in clasr/registry.py with get() and detect() helpers"
status: todo
use-cases: [SUC-006]
depends-on: ["003", "004", "005"]
github-issue: ""
todo: ""
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Create INTEGRATION_REGISTRY in clasr/registry.py with get() and detect() helpers

## Description

Create `clasr/registry.py` with `INTEGRATION_REGISTRY`, `get()`, and `detect()`.

```python
from clasr.platforms.claude import ClaudeIntegration
from clasr.platforms.codex import CodexIntegration
from clasr.platforms.copilot import CopilotIntegration

INTEGRATION_REGISTRY: dict[str, type[IntegrationBase]] = {
    "claude":   ClaudeIntegration,
    "codex":    CodexIntegration,
    "copilot":  CopilotIntegration,
}

def get(id: str) -> IntegrationBase:
    """Return a fresh instance. Raises KeyError for unknown ids."""
    return INTEGRATION_REGISTRY[id]()

def detect(target: Path) -> list[IntegrationBase]:
    """Return instances of integrations whose detect_files are present in target."""
    found = []
    for cls in INTEGRATION_REGISTRY.values():
        instance = cls()
        if any((target / f).exists() for f in instance.detect_files):
            found.append(instance)
    return found
```

After this ticket, also update `tests/clasr/test_integration_contract.py` (ticket 002) to import from `clasr.registry` instead of the placeholder dict. The contract test now parametrizes over the real registry.

## Acceptance Criteria

- [ ] `clasr/registry.py` exists with `INTEGRATION_REGISTRY`, `get()`, `detect()`.
- [ ] `get("claude")` returns a `ClaudeIntegration` instance.
- [ ] `get("unknown")` raises `KeyError`.
- [ ] `detect(target)` returns correct integrations based on `detect_files` presence.
- [ ] `test_integration_contract.py` is updated to parametrize over `INTEGRATION_REGISTRY.values()`.
- [ ] Contract test passes for Claude, Codex, and Copilot (three parametrized runs).
- [ ] `uv run pytest` green.

## Implementation Plan

### Files to Create

- `clasr/registry.py`

### Files to Modify

- `tests/clasr/test_integration_contract.py` — switch placeholder to real registry.

### Testing Plan

- `uv run pytest tests/clasr/test_integration_contract.py` — must show 3 parametrized runs, all pass.
- `uv run pytest` — full suite green.

### Documentation Updates

None.
