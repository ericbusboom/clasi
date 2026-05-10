---
id: '002'
title: Scaffold parametrized contract test with empty registry placeholder
status: done
use-cases:
- SUC-002
depends-on:
- '001'
github-issue: ''
todo: ''
completes_todo: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Scaffold parametrized contract test with empty registry placeholder

## Description

Create `tests/clasr/test_integration_contract.py` with a `pytest.mark.parametrize` fixture that reads `INTEGRATION_REGISTRY.values()`. At the time of this ticket the registry is not yet populated (ticket 006 creates it), so use a local placeholder dict for the parametrize source. The test file must be structured so that adding an integration to the real registry in ticket 006 automatically expands test coverage with no changes to this file.

The test fixture builds a minimal source directory valid for all platform types: one `SKILL.md`, one agent `.md`, one rule `.md`, one `AGENTS.md`. The contract test:
1. Instantiates the integration class.
2. Calls `install(source, target, provider="test-provider")`.
3. Asserts the manifest file exists in the expected location (`target_root / ".clasr-manifest" / "test-provider.json"`).
4. Asserts at least one file was installed in `target`.
5. Calls `uninstall(target, provider="test-provider")`.
6. Asserts the manifest file is gone.

## Acceptance Criteria

- [x] `tests/clasr/test_integration_contract.py` exists.
- [x] The parametrize source is `INTEGRATION_REGISTRY.values()` (after 006 lands; placeholder before).
- [x] The minimal-source fixture creates `skills/test-skill/SKILL.md`, `agents/agent.md`, `rules/rule.md`, `AGENTS.md`.
- [x] The test runs and is skipped (or passes vacuously) if the registry is empty — no collection error.
- [x] `uv run pytest tests/clasr/test_integration_contract.py` exits 0.

## Implementation Plan

### Approach

Write the test file with a placeholder `_TEST_REGISTRY: dict[str, type] = {}`. After ticket 006 lands, switch the parametrize source to `INTEGRATION_REGISTRY`. The test body is fully written in this ticket using the architecture-update spec.

### Files to Create

- `tests/clasr/test_integration_contract.py`

### Files to Modify

None.

### Testing Plan

- Run `uv run pytest tests/clasr/test_integration_contract.py` — must collect and pass (vacuously with empty registry).
- Run `uv run pytest` — full suite must stay green.

### Documentation Updates

None.
