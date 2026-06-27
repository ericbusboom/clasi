---
id: 008
title: Wire migration prompt into clasi init and add relocate tests
status: in-progress
use-cases:
- SUC-004
depends-on:
- '007'
github-issue: ''
issue: ''
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Wire migration prompt into clasi init and add relocate tests

## Description

With `detect_moves` and `execute_moves` built in ticket 007, this ticket wires
the detect-and-prompt flow into `clasi init` and adds the `--yes/--relocate`
flags to both `init` and `migrate` in `clasi/cli.py`. Also adds the full
`tests/unit/test_relocate.py` suite that exercises the end-to-end flow
against scratch directories.

The interactive prompt behavior:
- After scaffolding, `run_init` calls `detect_moves(project)`.
- If the list is non-empty AND the process is interactive
  (`sys.stdin.isatty() and sys.stdout.isatty()`):
  prints each proposed move and calls `click.confirm("Move them?", default=False)`.
  If confirmed, calls `execute_moves`.
- If non-interactive (MCP, CI, piped): prints a warning message
  ("Files found at legacy locations. Run `clasi migrate` to relocate.")
  and does NOT move anything.
- If `--yes` or `--relocate` flag is passed to `init`, skips the prompt
  and relocates immediately.

## Acceptance Criteria

- [ ] `clasi init` in an interactive scratch dir with legacy files at
      `.clasi/issues/` prompts `"Your files are not in the right spot. Move them
      to these locations? [y/N]"` and lists the proposed moves.
- [ ] Answering `y` calls `execute_moves`; files land at the configured
      destination; re-running `clasi init` shows no further moves.
- [ ] Answering `N` (or no TTY) leaves files untouched; a warning is printed.
- [ ] `clasi init --yes` relocates without prompting.
- [ ] `clasi migrate --yes` (or `--relocate`) relocates without prompting.
- [ ] `clasi/cli.py` exposes `--yes/--relocate` on both `init` and `migrate`
      commands.
- [ ] `uv run pytest tests/unit/test_relocate.py` passes.
- [ ] `uv run pytest` passes (full suite).

## Implementation Plan

### Files to Modify

- `clasi/init_command.py` — add the post-scaffold detect/prompt block at the
  end of `run_init` (after the config.yaml write). Accept a `yes: bool = False`
  parameter.
- `clasi/cli.py` — add `--yes`/`--relocate` option to `init` and `migrate`
  commands; pass to `run_init` / `run_migrate`.

### Files to Create

- `tests/unit/test_relocate.py`

### Implementation Steps

1. In `clasi/init_command.py`, at the end of `run_init`, add:
   ```python
   from clasi.migrate_command import detect_moves, execute_moves
   project = Project(target_path)
   moves = detect_moves(project)
   if moves:
       if yes:
           execute_moves(project, moves)
       elif sys.stdin.isatty() and sys.stdout.isatty():
           click.echo("Your files are not in the right spot. Proposed moves:")
           for m in moves:
               click.echo(f"  {m.src} → {m.dst}")
           if click.confirm("Move them?", default=False):
               execute_moves(project, moves)
       else:
           click.echo(
               "WARNING: Files found at legacy locations. "
               "Run `clasi migrate` to relocate.",
               err=True,
           )
   ```

2. Add `yes: bool = False` parameter to `run_init` signature.

3. In `clasi/cli.py`, add `@click.option("--yes", is_flag=True, ...)` to both
   `init` and `migrate` command decorators; pass `yes=yes` to the underlying
   run functions.

4. Update `run_migrate` in `migrate_command.py` to also accept a `yes: bool`
   parameter for non-interactive usage.

### Testing Plan

New file `tests/unit/test_relocate.py`:

- `test_init_prompts_when_legacy_files_found(tmp_path, monkeypatch)` — seed
  `tmp_path/.clasi/issues/idea.md`; configure project to expect `clasi/issues`;
  monkeypatch `click.confirm` to return True; run `run_init(str(tmp_path))`;
  assert `tmp_path / "clasi/issues/idea.md"` exists.
- `test_init_warns_non_interactive(tmp_path, monkeypatch, capsys)` — seed legacy
  file; monkeypatch `sys.stdin.isatty()` to False; run `run_init`;
  assert file NOT moved; assert warning in stderr.
- `test_init_yes_flag_skips_prompt(tmp_path)` — seed legacy file; run
  `run_init(yes=True)`; assert file moved without any prompt interaction.
- `test_migrate_command_yes_flag(tmp_path)` — seed legacy file; run
  `run_migrate(str(tmp_path), yes=True)`; assert file moved.
- `test_no_moves_on_clean_install(tmp_path)` — run init with no legacy files;
  assert no prompt, no error.

Run: `uv run pytest tests/unit/test_relocate.py -v`
