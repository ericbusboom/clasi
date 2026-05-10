---
id: "010"
title: "clasi schema validate CLI subcommand"
status: todo
use-cases: [SUC-002, SUC-005]
depends-on: ["002"]
github-issue: ""
todo: ""
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# clasi schema validate CLI subcommand

## Description

Add a `clasi schema validate <path>` CLI subcommand to `cli.py`. The
subcommand runs `loader.load(path)` and reports success or failure. It is
the primary user-facing entry point for validating custom schemas without
starting the MCP server.

The `clasi schema` group does not yet exist in `cli.py`. This ticket adds
both the group and the `validate` subcommand.

## Acceptance Criteria

- [ ] `cli.py` has a `schema` Click group registered at the top level.
- [ ] `clasi schema validate <path>` is a subcommand of the `schema` group.
- [ ] On success: prints `Schema valid: <schema.name> (version <schema.version>)` to stdout; exits 0.
- [ ] On `SchemaError`: prints the error message to stderr; exits non-zero (exit code 1).
- [ ] On file-not-found: prints a clear error message to stderr; exits non-zero.
- [ ] `clasi schema validate --help` works and describes the subcommand.
- [ ] A Click test (using `CliRunner`) covers: valid schema path (se-process), invalid schema (cycle), missing file.
- [ ] `uv run pytest` passes.

## Implementation Plan

**Approach**: Add to `cli.py`:

```python
@cli.group()
def schema():
    """Schema validation and management tools."""

@schema.command("validate")
@click.argument("path", type=click.Path())
def schema_validate(path):
    """Validate a CLASI schema file."""
    from clasi.schemas import loader, SchemaError
    try:
        ws = loader.load(path)
        click.echo(f"Schema valid: {ws.name} (version {ws.version})")
    except SchemaError as e:
        click.echo(str(e), err=True)
        raise SystemExit(1)
    except FileNotFoundError:
        click.echo(f"File not found: {path}", err=True)
        raise SystemExit(1)
```

**Files to modify**:
- `clasi/cli.py` — add `schema` group and `validate` subcommand

**Files to create**:
- `tests/clasi/test_cli_schema.py` — CLI tests using `CliRunner`

**Testing plan**: Use Click's `CliRunner` to invoke `clasi schema validate`
with a valid path (pointing at the se-process schema), a synthesized invalid
schema YAML (write to a tempfile), and a non-existent path. Verify exit codes
and output.

**Documentation updates**: None in this ticket (CLI help text is self-documenting).
