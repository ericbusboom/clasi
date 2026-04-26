---
id: "006"
title: "Update tests: remove SDK tests, add no-SDK import guard test"
status: done
use-cases: ["SUC-001", "SUC-002", "SUC-003", "SUC-004"]
depends-on: ["001", "002", "003", "004"]
github-issue: ""
todo: ""
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Update tests: remove SDK tests, add no-SDK import guard test

## Description

With the SDK and dispatch infrastructure removed, several test files are stale and must
be cleaned up:

- `tests/unit/test_dispatch_tools.py` — tests a deleted module; delete this file.
- `tests/unit/test_role_guard.py` — tests `_build_role_guard_hooks()` which is removed; delete this file.
- `tests/unit/test_agent.py` — contains ~15 test methods that mock `claude_agent_sdk` via
  `patch.dict(sys.modules, {"claude_agent_sdk": ...})`. These test removed methods
  (`dispatch()`, `_build_role_guard_hooks()`, `_build_retry_prompt()`). Delete those test
  methods; retain tests of read-only `Agent` properties.

New tests to add:

- `tests/unit/test_no_sdk_import.py` — parametrized test asserting that importing core
  CLASI modules does not bring `claude_agent_sdk` into `sys.modules`.
- A content-check test asserting no active plugin `.md` or `.yaml` file under
  `clasi/plugin/agents/` (excluding `old/`) contains old agent names as delegation targets.

## Acceptance Criteria

- [x] `tests/unit/test_dispatch_tools.py` is deleted.
- [x] `tests/unit/test_role_guard.py` is deleted.
- [x] All test methods in `test_agent.py` that use `patch.dict(sys.modules, {"claude_agent_sdk": ...})` are removed.
- [x] Remaining `test_agent.py` tests (read-only property tests) pass.
- [x] `tests/unit/test_no_sdk_import.py` exists with parametrized tests for `clasi.agent`, `clasi.project`, `clasi.tools.artifact_tools`, `clasi.tools.process_tools`.
- [x] The no-SDK guard test passes: none of those modules import `claude_agent_sdk`.
- [x] A content-check test asserts active plugin files contain none of the old delegation agent names.
- [x] `uv run pytest` passes with no ignore flags.

## Implementation Plan

### Approach

1. Delete `tests/unit/test_dispatch_tools.py`.
2. Delete `tests/unit/test_role_guard.py`.
3. Open `tests/unit/test_agent.py`. Remove every test method/class that calls
   `patch.dict(sys.modules, {"claude_agent_sdk": ...})`. Retain tests for `Agent.name`,
   `Agent.tier`, `Agent.model`, `Agent.definition`, `Agent.contract`, `Agent.render_prompt()`,
   `Agent.has_dispatch_template`.
4. Create `tests/unit/test_no_sdk_import.py`:

```python
import sys
import importlib
import pytest

MODULES_TO_CHECK = [
    "clasi.agent",
    "clasi.project",
    "clasi.tools.artifact_tools",
    "clasi.tools.process_tools",
]

@pytest.mark.parametrize("module_name", MODULES_TO_CHECK)
def test_module_does_not_import_sdk(module_name):
    sys.modules.pop("claude_agent_sdk", None)
    importlib.import_module(module_name)
    assert "claude_agent_sdk" not in sys.modules, (
        f"{module_name} transitively imported claude_agent_sdk"
    )

OLD_DELEGATION_NAMES = [
    "code-monkey", "sprint-executor", "ad-hoc-executor",
    "technical-lead", "project-manager", "code-reviewer",
]

def test_active_plugin_files_have_no_old_delegation_targets():
    from pathlib import Path
    plugin_agents = Path(__file__).parent.parent.parent / "clasi" / "plugin" / "agents"
    violations = []
    for path in plugin_agents.rglob("*"):
        if "old" in path.parts:
            continue
        if path.suffix not in {".md", ".yaml"}:
            continue
        text = path.read_text(encoding="utf-8")
        for old_name in OLD_DELEGATION_NAMES:
            if old_name in text:
                violations.append(f"{path.name}: contains '{old_name}'")
    assert not violations, "Old agent names found in active plugin files:\n" + "\n".join(violations)
```

### Files to Create / Modify

- **Delete**: `tests/unit/test_dispatch_tools.py`
- **Delete**: `tests/unit/test_role_guard.py`
- **Edit**: `tests/unit/test_agent.py` — remove SDK-mock test methods
- **Create**: `tests/unit/test_no_sdk_import.py`

### Testing Plan

- `uv run pytest` — full suite passes with no ignore flags.
- `uv run pytest tests/unit/test_no_sdk_import.py -v` — all parametrized cases pass.
- `uv run pytest tests/unit/test_agent.py -v` — only property tests remain; all pass.

### Documentation Updates

None. Test changes are self-documenting.
