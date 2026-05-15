---
id: '007'
title: 'Hook injection: UserPromptSubmit and SubagentStart auto-inject status block'
status: done
use-cases:
- SUC-005
depends-on:
- '003'
- '004'
issue: clasi-status-per-agent-process-status-with-gate-derived-next-step-notes.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Hook injection: UserPromptSubmit and SubagentStart auto-inject status block

## Description

This ticket implements the automatic status injection hooks. When Claude Code
fires `UserPromptSubmit` (for the top-level session) or `SubagentStart` (for
subagents), a `## CLASI status` block is prepended to the hook output. This
gives every agent session the current project state without requiring a manual
`clasi status` call.

The hooks are silent (exit 0, no output) if the project is not CLASI-initialized
or if `.clasi/oop` exists.

This ticket also updates the `clasi init` platform templates to register the new
`status-inject` hook for `UserPromptSubmit`, and extends `handle_subagent_start`
to prepend the status block.

## Acceptance Criteria

- [x] `clasi/hook_handlers.py` contains `handle_status_inject(payload)` for `UserPromptSubmit`.
- [x] `handle_status_inject` calls `build_status` + `narrow_status` (using `$CLASI_AGENT_NAME`), serializes to YAML, and prints a `## CLASI status` fenced block to stdout.
- [x] `handle_status_inject` exits 0 silently if `.clasi/` does not exist.
- [x] `handle_status_inject` exits 0 silently if `.clasi/oop` exists.
- [x] `clasi hook status-inject` is a valid event in `clasi/cli.py`'s hook event list.
- [x] `handle_subagent_start` is extended to prepend a `## CLASI status` block (agent scope derived from `agent_type` in payload; maps `programmer`→programmer role, `sprint-planner`→sprint-planner role, else team-lead).
- [x] Platform install templates in `clasi/plugin/platforms/` are updated to add a `UserPromptSubmit` hook entry calling `clasi hook status-inject`.
- [x] Unit tests in `tests/unit/test_status/test_hook_injection.py` cover:
  - OOP bypass: no output.
  - Non-CLASI project: no output.
  - Valid CLASI project: output contains `## CLASI status` and valid YAML.
- [x] `uv run pytest tests/unit/test_status/test_hook_injection.py` passes.
- [x] `uv run pytest` (full suite) passes.

## Implementation Plan

### Approach

**First**: verify the `UserPromptSubmit` hook output protocol. Read the existing
`handle_plan_to_issue` `PostToolUse` handler for reference. For `UserPromptSubmit`,
Claude Code likely uses a different envelope. Check the Claude Code hook docs
(or inspect existing hooks in the repo's `.claude/settings.json`) to confirm
whether stdout must be JSON or plain text.

**Implement `handle_status_inject`**:
```python
def handle_status_inject(payload: dict) -> None:
    project = get_project()
    if not project.clasi_dir.exists() or (project.clasi_dir / "oop").exists():
        sys.exit(0)
    agent = os.environ.get("CLASI_AGENT_NAME", "team-lead")
    from clasi.status import build_status, narrow_status
    from clasi.status.formatting import to_yaml
    full = build_status(project, agent=agent)
    narrowed = narrow_status(full, agent=agent)
    block = f"## CLASI status\n\n```yaml\n{to_yaml(narrowed)}```\n"
    print(block)
    sys.exit(0)
```

**Extend `handle_subagent_start`**: after creating the log file, compute and
print the status block before calling `_exit_hook`.

**Platform templates**: find `clasi/plugin/platforms/` templates (one per
platform). Add the `status-inject` hook entry for `UserPromptSubmit` in each
Claude Code template. Identify which template file is used by `clasi init --claude`.

### Files to modify

- `clasi/hook_handlers.py` — add `handle_status_inject`, extend `handle_subagent_start`, add to routing table
- `clasi/cli.py` — add `status-inject` to hook event choice list
- `clasi/plugin/platforms/claude/` (or similar) — update install templates

### Files to create

- `tests/unit/test_status/test_hook_injection.py` — unit tests

### Testing plan

Use `tmp_path` fixture to simulate CLASI-initialized and non-CLASI projects.
Capture stdout to verify `## CLASI status` block presence. Test OOP bypass.

### Documentation updates

Update `clasi/cli.py` hook command docstring to add `status-inject` event description.
