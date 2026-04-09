---
id: '003'
title: Fix clasi init to overwrite hooks section
status: done
use-cases:
- SUC-002
depends-on:
- '001'
github-issue: ''
todo: ''
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Fix clasi init to overwrite hooks section

## Description

`clasi init` currently merges new hooks into `settings.json` using
`setdefault` and skips entries whose command string is already present.
This means users who installed before the hooks refactor never receive
updated hook commands — their `python3 .claude/hooks/foo.py` entries remain.

This ticket:
1. Changes `_install_plugin_content` in `init_command.py` to overwrite the
   `hooks` key in `settings.json` entirely with the content from
   `plugin/hooks/hooks.json`, rather than merging.
2. Removes the `.py` hook script copy loop (no `.py` files exist in the
   plugin template after ticket 001).
3. Preserves idempotency: if `settings.json` already has the correct hooks,
   report "Unchanged".

## Acceptance Criteria

- [x] Running `clasi init` on a project with old `python3` hook commands
  updates them to `clasi hook <event>` commands
- [x] Running `clasi init` on a project already using `clasi hook <event>`
  commands reports "Unchanged: .claude/settings.json (hooks)"
- [x] Other keys in `settings.json` (e.g., `permissions`) are not disturbed
- [x] No `.py` files are copied to `.claude/hooks/` by `clasi init`
- [x] All existing tests pass (`uv run pytest`)
- [x] New unit test covers the overwrite and idempotency behavior

## Implementation Plan

### Approach

In `_install_plugin_content`, replace the merge loop with a direct assignment:
read `hooks.json`, load it, compare `settings.get("hooks")` with
`hooks_data["hooks"]`. If equal, report unchanged; otherwise overwrite and
write. Remove the `*.py` copy loop.

### Files to Modify

**`clasi/init_command.py`** — in `_install_plugin_content`:

Replace the section starting with `# Copy hook scripts` through the
`click.echo("  Unchanged/Updated: .claude/settings.json (hooks)")` block with:

```python
# Overwrite hooks from plugin hooks.json into .claude/settings.json
plugin_hooks = _PLUGIN_DIR / "hooks" / "hooks.json"
if plugin_hooks.exists():
    click.echo("Hooks (from plugin):")
    hooks_data = json.loads(plugin_hooks.read_text(encoding="utf-8"))
    settings_path = target / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            settings = {}
    else:
        settings = {}

    new_hooks = hooks_data.get("hooks", {})
    if settings.get("hooks") == new_hooks:
        click.echo("  Unchanged: .claude/settings.json (hooks)")
    else:
        settings["hooks"] = new_hooks
        settings_path.write_text(
            json.dumps(settings, indent=2) + "\n", encoding="utf-8"
        )
        click.echo("  Updated: .claude/settings.json (hooks)")
    click.echo()
```

Remove the entire "Copy hook scripts" block that copies `*.py` files from
`plugin_hooks_dir` to `target_hooks`.

### Testing Plan

- **New tests** in `tests/test_init_command.py`:
  - Test that `run_init` on a temp directory with old `python3` hook commands
    in `settings.json` overwrites them with `clasi hook` commands.
  - Test that `run_init` on a directory already having correct hooks does not
    rewrite `settings.json` (output contains "Unchanged").
  - Test that a pre-existing `permissions` key in `settings.json` is preserved
    after `run_init`.
  - Test that no `.py` files are copied to `<target>/.claude/hooks/`.
- **Existing tests**: `uv run pytest` — all must pass.

### Documentation Updates

None. The `clasi init` output messages are self-explanatory.
