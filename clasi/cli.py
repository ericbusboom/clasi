"""
CLI entry point for CLASI.

Subcommands:
    clasi init [target]             — Initialize a repo for CLASI
    clasi install [target]          — Synonym for clasi init
    clasi uninstall [target]        — Remove CLASI platform integration files
    clasi migrate [target]          — One-shot docs/clasi/ → .clasi/ migration
    clasi mcp                       — Run the MCP server (stdio)
    clasi tool plan-to-issue        — Convert plan file to issue
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
@click.option("--claude", "install_claude", is_flag=True, default=False,
              help="Install Claude platform integration.")
@click.option("--codex", "install_codex", is_flag=True, default=False,
              help="Install Codex platform integration.")
@click.option("--copilot", "install_copilot", is_flag=True, default=False,
              help="Install GitHub Copilot platform integration.")
@click.option("--copy/--no-copy", default=False,
              help="Use file copy instead of symlink for alias operations.")
@click.option("--migrate", is_flag=True, default=False,
              help="Convert legacy direct-copy installs to symlinks.")
def init(target, plugin, install_claude, install_codex, install_copilot, copy, migrate):
    """Initialize a repository for the CLASI SE process.

    By default (no --claude, --codex, or --copilot flag), behavior depends on context:

    \b
    - Interactive (TTY): inspects advisory platform signals and prompts the
      user to choose Claude, Codex, Copilot, or all three, with a recommended
      default.
    - Non-interactive (no TTY, e.g. scripts/CI): defaults to Claude-only for
      backward compatibility.

    With --claude, --codex, and/or --copilot, installs the selected platform(s)
    without prompting.  With --plugin, registers the CLASI plugin with Claude
    Code (plugin mode).  With --copy, alias operations use file copy instead of
    symlink (useful on Windows without Developer Mode).  With --migrate,
    converts legacy direct-copy installs to symlinks.
    """
    from clasi.init_command import run_init

    run_init(
        target,
        plugin_mode=plugin,
        claude=install_claude,
        codex=install_codex,
        copilot=install_copilot,
        copy=copy,
        migrate=migrate,
    )


# Register 'install' as a synonym for 'init' — same callback, same options.
cli.add_command(init, name="install")


@cli.command()
@click.argument("target", default=".", type=click.Path(exists=True))
@click.option("--claude", "uninstall_claude", is_flag=True, default=False,
              help="Remove Claude platform integration.")
@click.option("--codex", "uninstall_codex", is_flag=True, default=False,
              help="Remove Codex platform integration.")
@click.option("--copilot", "uninstall_copilot", is_flag=True, default=False,
              help="Remove GitHub Copilot platform integration.")
@click.option("--copy/--no-copy", default=False,
              help="Use file copy removal instead of symlink removal for alias operations.")
def uninstall(target, uninstall_claude, uninstall_codex, uninstall_copilot, copy):
    """Remove CLASI-managed platform integration files."""
    from clasi.uninstall_command import run_uninstall
    run_uninstall(
        target,
        claude=uninstall_claude,
        codex=uninstall_codex,
        copilot=uninstall_copilot,
        copy=copy,
    )


@cli.group()
def tool():
    """Utility tools for CLASI workflows."""


@tool.command("plan-to-issue")
@click.option("--plans-dir", default=None, type=click.Path(), help="Override plans directory (default: ~/.claude/plans).")
@click.option("--issues-dir", default=".clasi/issues", type=click.Path(), help="Issues output directory.")
def tool_plan_to_issue(plans_dir, issues_dir):
    """Copy the most recent plan file to the issues directory.

    Finds the newest .md file in ~/.claude/plans/, prepends
    status: pending frontmatter, writes it to .clasi/issues/,
    and deletes the original plan file.
    """
    from pathlib import Path

    from clasi.plan_to_issue import plan_to_issue

    plans = Path(plans_dir) if plans_dir else Path.home() / ".claude" / "plans"
    result = plan_to_issue(plans, Path(issues_dir))
    if result:
        click.echo(f"CLASI: Plan saved as issue: {result}")
    else:
        click.echo("No plan file found to convert.")


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
@click.argument("target", default=".", type=click.Path(exists=True))
def migrate(target):
    """Migrate a project from docs/clasi/ to .clasi/.

    Moves docs/clasi/ to .clasi/ (using git mv when inside a git repo),
    updates .gitignore, and re-runs clasi install to refresh rule files
    and agent prompts.

    Guards:
      - Exits with an error if .clasi/ already exists (already migrated).
      - Exits with an error if an execution lock is held.
    """
    from clasi.migrate_command import run_migrate

    run_migrate(target)


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
            "plan-to-issue",
            "plan-to-todo",
            "codex-plan-to-issue",
            "codex-plan-to-todo",
            "commit-check",
        ]
    ),
)
def hook(event):
    """Handle a hook event from Claude Code or Codex.

    Reads hook payload from stdin (JSON), delegates to the appropriate
    handler in clasi.hooks, and exits with the correct code.

    Valid events:
      role-guard           PreToolUse: enforce write-scope rules by agent tier.
      subagent-start       SubagentStart: log subagent lifecycle start.
      subagent-stop        SubagentStop: append transcript to subagent log.
      task-created         TaskCreated: log parallel-task lifecycle start.
      task-completed       TaskCompleted: append transcript to task log.
      mcp-guard            PreToolUse: block team-lead from direct MCP writes.
      plan-to-issue        PostToolUse(ExitPlanMode): save Claude plan as issue.
      plan-to-todo         PostToolUse(ExitPlanMode): alias for plan-to-issue (deprecated).
      codex-plan-to-issue  Stop(Codex): extract <proposed_plan> and save as issue.
      codex-plan-to-todo   Stop(Codex): alias for codex-plan-to-issue (deprecated).
      commit-check         PostToolUse(Bash): remind to bump version on master.
    """
    from clasi.hook_handlers import handle_hook

    handle_hook(event)
