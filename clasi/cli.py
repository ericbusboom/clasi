"""
CLI entry point for CLASI.

Subcommands:
    clasi init [target]             — Initialize a repo for CLASI
    clasi mcp                       — Run the MCP server (stdio)
    clasi tool todo-split           — Split multi-heading TODO files
    clasi tool plan-to-todo         — Convert plan file to TODO
    clasi todo-split                — Alias for tool todo-split
    clasi version                   — Show the current project version
    clasi version bump              — Bump version, update files, tag
"""

import click


@click.group()
@click.version_option(package_name="clasi")
def cli():
    """CLASI.

    MCP server for AI-driven software engineering process.
    """


@cli.command()
@click.argument("target", default=".", type=click.Path(exists=True))
@click.option("--plugin", is_flag=True, help="Install as a Claude Code plugin instead of project-local .claude/ content.")
def init(target, plugin):
    """Initialize a repository for the CLASI SE process.

    By default, copies skills, agents, and hooks into the project's
    .claude/ directory (project-local mode). With --plugin, registers
    the CLASI plugin with Claude Code (plugin mode).
    """
    from clasi.init_command import run_init

    run_init(target, plugin_mode=plugin)


@cli.group()
def tool():
    """Utility tools for CLASI workflows."""


@tool.command("todo-split")
@click.argument("todo_dir", default="docs/clasi/todo", type=click.Path(exists=True))
def tool_todo_split(todo_dir):
    """Split multi-heading TODO files into individual files.

    Scans the TODO directory for markdown files with multiple level-1
    headings and splits each into a separate file.
    """
    from pathlib import Path

    from clasi.todo_split import split_todo_files

    actions = split_todo_files(Path(todo_dir))
    if actions:
        click.echo("TODO split results:")
        for action in actions:
            click.echo(action)
    else:
        click.echo("No files needed splitting.")


@tool.command("plan-to-todo")
@click.option("--plans-dir", default=None, type=click.Path(), help="Override plans directory (default: ~/.claude/plans).")
@click.option("--todo-dir", default="docs/clasi/todo", type=click.Path(), help="TODO output directory.")
def tool_plan_to_todo(plans_dir, todo_dir):
    """Copy the most recent plan file to the TODO directory.

    Finds the newest .md file in ~/.claude/plans/, prepends
    status: pending frontmatter, writes it to docs/clasi/todo/,
    and deletes the original plan file.
    """
    from pathlib import Path

    from clasi.plan_to_todo import plan_to_todo

    plans = Path(plans_dir) if plans_dir else Path.home() / ".claude" / "plans"
    result = plan_to_todo(plans, Path(todo_dir))
    if result:
        click.echo(f"CLASI: Plan saved as TODO: {result}")
    else:
        click.echo("No plan file found to convert.")


# Keep top-level alias for backwards compatibility
@cli.command("todo-split")
@click.argument("todo_dir", default="docs/clasi/todo", type=click.Path(exists=True))
def todo_split(todo_dir):
    """Split multi-heading TODO files (alias for 'tool todo-split')."""
    from pathlib import Path

    from clasi.todo_split import split_todo_files

    actions = split_todo_files(Path(todo_dir))
    if actions:
        click.echo("TODO split results:")
        for action in actions:
            click.echo(action)
    else:
        click.echo("No files needed splitting.")


@cli.group(invoke_without_command=True)
@click.pass_context
def version(ctx):
    """Show or bump the project version.

    With no subcommand, shows the current version.
    """
    if ctx.invoked_subcommand is None:
        from clasi.versioning import read_current_version

        ver = read_current_version()
        if ver:
            click.echo(ver)
        else:
            click.echo("No version file found.", err=True)
            ctx.exit(1)


@version.command(name="bump")
@click.option("--major", default=0, type=int, help="Major version number.")
@click.option("--tag", is_flag=True, help="Create a git tag for the new version.")
@click.option("--push", "-p", is_flag=True, help="Commit, tag, and push (requires clean master).")
def version_bump(major, tag, push):
    """Compute the next version and update version files.

    Reads version_format from settings to determine the format.
    Updates the source file and all sync files.

    With --tag, also creates a git tag.
    With --push, checks for clean master/main, bumps, commits, tags, and pushes.
    """
    import subprocess

    from clasi.versioning import bump_version

    if push:
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        if branch not in ("master", "main"):
            click.echo(
                f"Error: not on master/main branch (on {branch})", err=True
            )
            raise SystemExit(1)

        status = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        if status:
            click.echo("Error: uncommitted changes", err=True)
            raise SystemExit(1)

    result = bump_version(major=major, tag=False)
    click.echo(f"Version: {result['version']}")
    if result["source"]:
        click.echo(f"Updated: {result['source']}")
    for s in result["synced"]:
        click.echo(f"Synced:  {s}")

    if push:
        subprocess.run(["git", "add", "pyproject.toml"], check=True)
        subprocess.run(
            ["git", "commit", "-m", f"chore: bump version to {result['version']}"],
            check=True,
        )
        from clasi.versioning import create_version_tag

        create_version_tag(result["version"])
        click.echo(f"Tagged:  v{result['version']}")
        subprocess.run(["git", "push", "--tags"], check=True)
        click.echo("Pushed.")
    elif tag:
        from clasi.versioning import create_version_tag

        create_version_tag(result["version"])
        click.echo(f"Tagged:  v{result['version']}")


@cli.command()
def mcp():
    """Run the CLASI MCP server (stdio transport)."""
    from clasi.mcp_server import run_server

    run_server()


@cli.command()
@click.argument(
    "event",
    type=click.Choice(
        [
            "role-guard",
            "subagent-start",
            "subagent-stop",
            "task-created",
            "task-completed",
            "mcp-guard",
            "plan-to-todo",
            "commit-check",
        ]
    ),
)
def hook(event):
    """Handle a Claude Code hook event.

    Reads hook payload from stdin (JSON), delegates to the appropriate
    handler in clasi.hooks, and exits with the correct code.
    """
    from clasi.hook_handlers import handle_hook

    handle_hook(event)
