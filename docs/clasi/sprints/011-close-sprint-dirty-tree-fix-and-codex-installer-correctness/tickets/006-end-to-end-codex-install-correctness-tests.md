---
id: '006'
title: End-to-end Codex install correctness tests
status: todo
use-cases:
  - SUC-008
depends-on:
  - '002'
  - '003'
  - '004'
  - '005'
github-issue: ''
todo: ''
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# End-to-end Codex install correctness tests

## Description

Tickets 002–005 each add unit tests for their individual changes. This ticket adds a
single end-to-end integration test that calls `codex.install()` against a fresh
`tmp_path` directory and then validates every emitted file via round-trip parse against
its spec. This is the canonical correctness check — it prevents any single ticket's
changes from silently breaking another artifact's shape.

This ticket depends on tickets 002, 003, 004, and 005 being implemented first.

## Acceptance Criteria

- [ ] A single test function `test_codex_install_end_to_end` (or equivalent) calls
      `codex.install(tmp_path, mcp_config={"command": "clasi", "args": ["mcp"]})` and
      then validates:
  - [ ] `.codex/config.toml` — parses via `tomllib.loads`; `data["mcp_servers"]["clasi"]`
        is present and equals the supplied `mcp_config`.
  - [ ] `.codex/hooks.json` — parses via `json.loads`; `data["hooks"]["Stop"][0]["hooks"][0]`
        has `type == "command"` and `command == "clasi hook codex-plan-to-todo"` and
        `"timeout"` key present; `"args"` key absent.
  - [ ] `.codex/agents/team-lead.toml` — parses via `tomllib.loads`; has `name`,
        `description`, `developer_instructions` keys; `developer_instructions` is
        non-empty.
  - [ ] `AGENTS.md` — file exists; CLASI marker section present; `/se` substring absent.
  - [ ] `docs/clasi/AGENTS.md` — exists; contains "MCP" or "CLASI MCP" text.
  - [ ] `clasi/AGENTS.md` — exists; contains "ticket" or "in-progress" text.
- [ ] All assertions pass in a single offline test run (no network access).
- [ ] Test runs in under 5 seconds.
- [ ] `uv run pytest` passes.

## Implementation Plan

### Approach

Add a test function to `tests/unit/test_platform_codex.py` (or a new
`tests/integration/test_codex_install_e2e.py` if the test file is getting long):

```python
def test_codex_install_end_to_end(tmp_path):
    from clasi.platforms import codex
    import json
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib

    mcp_config = {"command": "clasi", "args": ["mcp"]}
    codex.install(tmp_path, mcp_config=mcp_config)

    # .codex/config.toml
    config = tomllib.loads((tmp_path / ".codex" / "config.toml").read_text())
    assert config["mcp_servers"]["clasi"] == mcp_config

    # .codex/hooks.json
    hooks = json.loads((tmp_path / ".codex" / "hooks.json").read_text())
    stop_hook = hooks["hooks"]["Stop"][0]["hooks"][0]
    assert stop_hook["type"] == "command"
    assert stop_hook["command"] == "clasi hook codex-plan-to-todo"
    assert "timeout" in stop_hook
    assert "args" not in stop_hook

    # .codex/agents/team-lead.toml
    agent = tomllib.loads((tmp_path / ".codex" / "agents" / "team-lead.toml").read_text())
    assert agent["name"]
    assert "developer_instructions" in agent
    assert agent["developer_instructions"]

    # AGENTS.md (root)
    agents_md = (tmp_path / "AGENTS.md").read_text()
    assert "CLASI" in agents_md
    assert "/se" not in agents_md

    # docs/clasi/AGENTS.md
    docs_rules = (tmp_path / "docs" / "clasi" / "AGENTS.md").read_text()
    assert "MCP" in docs_rules or "clasi" in docs_rules.lower()

    # clasi/AGENTS.md
    src_rules = (tmp_path / "clasi" / "AGENTS.md").read_text()
    assert "ticket" in src_rules.lower() or "in-progress" in src_rules
```

### Files to Modify

- `tests/unit/test_platform_codex.py` (or new `tests/integration/test_codex_install_e2e.py`)
  — add `test_codex_install_end_to_end`.

### Testing Plan

1. `uv run pytest tests/unit/test_platform_codex.py::test_codex_install_end_to_end -v`
2. `uv run pytest` — full suite regression.

### Documentation Updates

None (test file only).
