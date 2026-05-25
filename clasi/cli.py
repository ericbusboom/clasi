"""
CLI entry point for CLASI.

Subcommands:
    clasi init [target]             — Initialize a repo for CLASI
    clasi install [target]          — Synonym for clasi init
    clasi uninstall [target]        — Remove CLASI platform integration files
    clasi migrate [target]          — One-shot docs/clasi/ → .clasi/ migration
    clasi mcp                       — Run the MCP server (stdio)
    clasi status                    — Print agent-scoped project status
    clasi tool plan-to-issue        — Convert plan file to issue
    clasi sprint close <sprint_id>  — Close a sprint

Versioning is delegated to dotconfig. Use ``dotconfig version`` and
``dotconfig version bump`` for the user-facing commands. The
``clasi.versioning`` module remains as an internal library used by
``close_sprint``'s bump-and-tag step; that internal usage is targeted
for retirement in a future sprint.
"""

import os

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
@click.option(
    "--process",
    type=click.Choice(["se", "solo"]),
    default="se",
    show_default=True,
    help="SE process variant to activate (se or solo).",
)
def init(target, plugin, install_claude, install_codex, install_copilot, copy, migrate, process):
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
    converts legacy direct-copy installs to symlinks.  With --process, selects
    the SE process variant (se or solo; default: se).
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
        process=process,
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
@click.option(
    "--agent",
    default=None,
    metavar="ROLE",
    help=(
        "Agent role for scoping output.  "
        "Defaults to $CLASI_AGENT_NAME env var, then 'team-lead'."
    ),
)
@click.option(
    "--sprint",
    "sprint_id",
    default=None,
    metavar="ID",
    help="Narrow output to a specific sprint (e.g. '006').",
)
@click.option(
    "--ticket",
    "ticket_id",
    default=None,
    metavar="ID",
    help="Narrow output to a specific ticket (e.g. '006-005').",
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["yaml", "json"]),
    default="yaml",
    show_default=True,
    help="Output format.",
)
def status(agent: str | None, sprint_id: str | None, ticket_id: str | None, fmt: str) -> None:
    """Print agent-scoped CLASI project status.

    Resolves the project from the current working directory.  Exits with
    a non-zero status code if no .clasi/ directory is found.

    Agent role resolution order: --agent flag > $CLASI_AGENT_NAME > 'team-lead'.
    """
    from pathlib import Path

    from clasi.project import Project
    from clasi.status import build_status, narrow_status
    from clasi.status.formatting import to_json, to_yaml

    cwd = Path.cwd()
    clasi_dir = cwd / ".clasi"
    if not clasi_dir.is_dir():
        click.echo(
            f"Error: No .clasi/ directory found in {cwd}. "
            "Run 'clasi init' to initialise this project.",
            err=True,
        )
        raise SystemExit(1)

    resolved_agent: str = agent or os.environ.get("CLASI_AGENT_NAME") or "team-lead"

    project = Project(cwd)
    full = build_status(project, agent=resolved_agent, sprint_id=sprint_id, ticket_id=ticket_id)
    narrowed = narrow_status(full, agent=resolved_agent, sprint_id=sprint_id, ticket_id=ticket_id)

    if fmt == "json":
        click.echo(to_json(narrowed))
    else:
        click.echo(to_yaml(narrowed), nl=False)


@cli.group()
def schema():
    """Schema validation and management tools."""


@schema.command("validate")
@click.argument("path", type=click.Path())
def schema_validate(path: str) -> None:
    """Validate a CLASI schema file."""
    from clasi.schemas import SchemaError
    from clasi.schemas import loader

    try:
        ws = loader.load(path)
        click.echo(f"Schema valid: {ws.name} (version {ws.version})")
    except SchemaError as e:
        click.echo(str(e), err=True)
        raise SystemExit(1)
    except FileNotFoundError:
        click.echo(f"File not found: {path}", err=True)
        raise SystemExit(1)


@cli.group()
def sprint() -> None:
    """Sprint lifecycle commands."""


@sprint.command("close")
@click.argument("sprint_id")
@click.option("--branch", "branch_name", default=None,
              help="Sprint branch name. When provided, enables full lifecycle with git operations.")
@click.option("--main-branch", default="master", show_default=True,
              help="Target branch for merge.")
@click.option("--push-tags/--no-push-tags", default=True, show_default=True,
              help="Whether to push tags after tagging.")
@click.option("--delete-branch/--no-delete-branch", default=True, show_default=True,
              help="Whether to delete the sprint branch after merge.")
@click.option("--test-command", default=None,
              help="Shell command to run tests. Pass empty string to skip.")
def sprint_close(
    sprint_id: str,
    branch_name: str | None,
    main_branch: str,
    push_tags: bool,
    delete_branch: bool,
    test_command: str | None,
) -> None:
    """Close a sprint, running tests and git lifecycle operations."""
    from clasi.tools.artifact_tools import close_sprint
    click.echo(close_sprint(sprint_id, branch_name, main_branch,
                            push_tags, delete_branch, test_command))


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
            "status-inject",
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
      status-inject        UserPromptSubmit: prepend CLASI status block to context.
    """
    from clasi.hook_handlers import handle_hook

    handle_hook(event)
