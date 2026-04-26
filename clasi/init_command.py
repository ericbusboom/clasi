"""Implementation of the `clasi init` command.

Installs the CLASI SE process into a target repository. Supports two modes:

- **Project-local mode** (default): Copies skills, agents, and hook config
  from the bundled plugin/ directory into the project's .claude/ directory.
  Skills are unnamespaced (/plan-sprint, /se, /todo).

- **Plugin mode** (--plugin): Registers the CLASI plugin with Claude Code.
  Skills are namespaced (/clasi:plan-sprint, /clasi:se, /clasi:todo).

Both modes also configure MCP server, permissions, TODO directories,
and path-scoped rules.
"""

import json
import re
from pathlib import Path

import click

# The plugin directory is bundled inside the clasi package.
_PLUGIN_DIR = Path(__file__).parent / "plugin"

# Re-export RULES for backward compatibility with existing tests that import
# RULES from clasi.init_command.
from clasi.platforms.claude import RULES  # noqa: E402,F401


def _detect_mcp_command(target: Path) -> dict:
    """Detect the correct MCP server command for the target project.

    Uses 'uv run clasi mcp' only when a pyproject.toml declares a
    [project] table (the minimum uv needs to set up an environment).
    A pyproject.toml that only carries tool config (e.g. [tool.black])
    will make 'uv run' abort with "No `project` table found", so in
    that case fall back to bare 'clasi mcp'.
    """
    for candidate in (target / "pyproject.toml", Path.cwd() / "pyproject.toml"):
        if not candidate.exists():
            continue
        try:
            text = candidate.read_text(encoding="utf-8")
        except OSError:
            continue
        if re.search(r"(?m)^\[project\]\s*$", text):
            return {"command": "uv", "args": ["run", "clasi", "mcp"]}
    return {"command": "clasi", "args": ["mcp"]}


def _update_mcp_json(mcp_json_path: Path, target: Path) -> bool:
    """Merge MCP server config into .mcp.json.

    Returns True if the file was written/updated, False if unchanged.
    """
    rel = str(mcp_json_path.name)
    mcp_config = _detect_mcp_command(target)

    if mcp_json_path.exists():
        try:
            data = json.loads(mcp_json_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            data = {}
    else:
        data = {}

    mcp_servers = data.setdefault("mcpServers", {})

    if mcp_servers.get("clasi") == mcp_config:
        click.echo(f"  Unchanged: {rel}")
        return False

    mcp_servers["clasi"] = mcp_config
    mcp_json_path.write_text(
        json.dumps(data, indent=2) + "\n", encoding="utf-8"
    )
    click.echo(f"  Updated: {rel}")
    return True


def run_init(
    target: str,
    plugin_mode: bool = False,
    claude: bool = True,
    codex: bool = False,
) -> None:
    """Initialize a repository for the CLASI SE process.

    In project-local mode (default), copies skills, agents, and hooks
    from the plugin/ directory into .claude/. In plugin mode, registers
    the CLASI plugin with Claude Code.

    Args:
        target: Path to the target project root (string; resolved internally).
        plugin_mode: If True, run in plugin mode instead of project-local mode.
        claude: If True (default), run the Claude platform installer.
        codex: If True, run the Codex platform installer (no-op in this release).
    """
    from clasi.platforms.claude import install as claude_install

    target_path = Path(target).resolve()
    mode_label = "plugin" if plugin_mode else "project-local"
    click.echo(f"Initializing CLASI in {target_path} ({mode_label} mode)")
    click.echo()

    # Detect MCP command once; shared scaffolding and platform installers use it.
    mcp_config = _detect_mcp_command(target_path)

    if plugin_mode:
        # Plugin mode: just tell the user how to install
        click.echo("Plugin mode: install the CLASI plugin with Claude Code:")
        click.echo(f"  claude --plugin-dir {_PLUGIN_DIR}")
        click.echo("  Or: /plugin install clasi (from marketplace)")
        click.echo()
    elif claude:
        # Project-local mode: delegate all Claude-specific steps to the platform module.
        claude_install(target_path, mcp_config)

    # Codex platform install (no-op in this release; reserved for ticket 004).
    # if codex:
    #     from clasi.platforms.codex import install as codex_install
    #     codex_install(target_path)

    # Configure MCP server in .mcp.json at project root (shared setup).
    click.echo("MCP server configuration:")
    _update_mcp_json(target_path / ".mcp.json", target_path)
    click.echo()

    # Create TODO directories (shared setup).
    click.echo("TODO directories:")
    todo_dir = target_path / "docs" / "clasi" / "todo"
    todo_in_progress = todo_dir / "in-progress"
    todo_done = todo_dir / "done"
    for d in [todo_dir, todo_in_progress, todo_done]:
        d.mkdir(parents=True, exist_ok=True)
        gitkeep = d / ".gitkeep"
        if not gitkeep.exists() and not any(d.iterdir()):
            gitkeep.touch()
    click.echo("  Created: docs/clasi/todo/ (with in-progress/ and done/)")

    # Create log directory with .gitignore (shared setup).
    click.echo()
    click.echo("Log directory:")
    log_dir = target_path / "docs" / "clasi" / "log"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_gitignore = log_dir / ".gitignore"
    log_gitignore.write_text("# Ignore all log files\n*\n!.gitignore\n", encoding="utf-8")
    click.echo("  Created: docs/clasi/log/ (with .gitignore)")

    click.echo()
    click.echo("Done! The CLASI SE process is now configured.")
