---
id: "005"
title: "Wire --claude / --codex flags and install synonym into cli.py and init_command"
status: done
use-cases:
  - SUC-001
  - SUC-002
  - SUC-003
  - SUC-004
  - SUC-005
depends-on:
  - "002"
  - "004"
github-issue: ""
todo: ""
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Wire --claude / --codex flags and install synonym into cli.py and init_command

## Description

Wire the `--claude` and `--codex` CLI flags into `clasi init` and add `clasi install`
as a synonym. Update `init_command.run_init` to accept `claude` and `codex` boolean
parameters and dispatch to the appropriate platform installers.

This ticket connects tickets 002 (Claude refactor) and 004 (Codex installer) to the
user-facing CLI. After this ticket, `clasi init --codex` and `clasi install --claude
--codex` work end-to-end in non-interactive mode.

## Acceptance Criteria

- [x] `clasi init --claude` installs Claude artifacts only (no Codex artifacts created).
- [x] `clasi init --codex` installs Codex artifacts only (no Claude artifacts created,
      except shared scaffolding: TODO dirs, log dir, `.mcp.json`).
- [x] `clasi init --claude --codex` installs both.
- [x] `clasi init` with no flag in non-interactive mode defaults to Claude only
      (backward compat).
- [x] `clasi install` is recognized by the CLI and behaves identically to `clasi init`
      with the same flags.
- [x] `clasi install --codex`, `clasi install --claude`, `clasi install --claude --codex`
      all work.
- [x] Tests in `tests/unit/test_cli_init.py` (new or extended) verify the above
      flag combinations produce the correct file sets in a `tmp_path`.

## Implementation Plan

### Files to modify

- `clasi/cli.py` — add `--claude` / `--codex` options to `init`; add `install` alias
- `clasi/init_command.py` — update `run_init` to accept and dispatch on `claude`/`codex`

### Files to create or extend

- `tests/unit/test_cli_init.py` (extend or create)

### Approach

**`cli.py`**:

1. Add flags to `init`:
```python
@cli.command()
@click.argument("target", default=".", type=click.Path(exists=True))
@click.option("--plugin", is_flag=True, ...)
@click.option("--claude", "install_claude", is_flag=True, default=False,
              help="Install Claude platform integration.")
@click.option("--codex", "install_codex", is_flag=True, default=False,
              help="Install Codex platform integration.")
def init(target, plugin, install_claude, install_codex):
    from clasi.init_command import run_init
    run_init(target, plugin_mode=plugin, claude=install_claude, codex=install_codex)
```

2. Register `install` as an alias (same callback):
```python
cli.add_command(init, name="install")
```

**`init_command.run_init`**:

Update signature:
```python
def run_init(target: str, plugin_mode: bool = False,
             claude: bool = False, codex: bool = False) -> None:
```

Non-interactive default logic:
- If `claude` is False and `codex` is False: set `claude = True` (backward compat).
- Interactive prompt (if applicable) is handled in ticket 006; for now non-interactive
  always uses the flag values.

Dispatch:
```python
mcp_config = _detect_mcp_command(target_path)
# Shared setup (always):
_update_mcp_json(...)
_create_todo_dirs(...)
_create_log_dir(...)

if claude:
    from clasi.platforms.claude import install as claude_install
    claude_install(target_path, mcp_config)

if codex:
    from clasi.platforms.codex import install as codex_install
    codex_install(target_path, mcp_config)
```

### Testing plan

Write or extend `tests/unit/test_cli_init.py` using Click's `CliRunner` or direct
`run_init` calls with `tmp_path`:

- `test_default_installs_claude_only`: `run_init(tmp, claude=False, codex=False)`
  creates `.claude/` artifacts, does NOT create `.codex/` or `.agents/`.
- `test_explicit_claude`: `run_init(tmp, claude=True, codex=False)` same as above.
- `test_codex_only`: `run_init(tmp, claude=False, codex=True)` creates Codex artifacts,
  does NOT create `.claude/` or `CLAUDE.md`.
- `test_both`: `run_init(tmp, claude=True, codex=True)` creates all artifacts.
- `test_install_synonym_cli`: use `CliRunner` to invoke `clasi install --codex` and
  assert Codex artifacts are created.

```
uv run pytest tests/unit/test_cli_init.py -v
uv run pytest tests/unit/test_init_command.py -v
uv run pytest -x
```

### Documentation updates

Update `clasi/cli.py` docstring for `init` to mention `--claude` and `--codex`. No
external docs changes required at this stage.
