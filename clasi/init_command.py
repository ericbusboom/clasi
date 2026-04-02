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
import shutil
import stat
from pathlib import Path
from typing import Dict

import click

# The plugin directory is at the repo root (sibling of clasi/).
# In development, resolve relative to this file. When installed as a
# package, the plugin/ directory should also be findable.
_PLUGIN_DIR = Path(__file__).parent.parent / "plugin"
if not _PLUGIN_DIR.exists():
    # Fallback: check if plugin content is bundled inside the package
    _PLUGIN_DIR = Path(__file__).parent / "plugin"

def _detect_mcp_command(target: Path) -> dict:
    """Detect the correct MCP server command for the target project.

    Uses 'uv run clasi mcp' when a pyproject.toml exists (uv project),
    otherwise falls back to bare 'clasi mcp'.
    """
    if (target / "pyproject.toml").exists() or (Path.cwd() / "pyproject.toml").exists():
        return {"command": "uv", "args": ["run", "clasi", "mcp"]}
    return {"command": "clasi", "args": ["mcp"]}


# Path-scoped rules installed by `clasi init`.
# Each key is the filename under `.claude/rules/`, each value is the
# complete file content (YAML frontmatter + markdown body).
RULES: Dict[str, str] = {
    "mcp-required.md": """\
---
paths:
  - "**"
---

This project uses the CLASI MCP server. Before doing ANY work:

1. Call `get_version()` to verify the MCP server is running.
2. If the call fails, STOP. Do not proceed. Tell the stakeholder:
   "The CLASI MCP server is not available. Check .mcp.json and
   restart the session."
3. Do NOT create sprint directories, tickets, TODOs, or planning
   artifacts manually. Do NOT improvise workarounds. All SE process
   operations require the MCP server.
""",
    "clasi-artifacts.md": """\
---
paths:
  - docs/clasi/**
---

You are modifying CLASI planning artifacts. Before making changes:

1. Confirm you have an active sprint (`list_sprints(status="active")`),
   or the stakeholder said "out of process" / "direct change".
2. If creating or modifying tickets, the sprint must be in `ticketing`
   or `executing` phase (`get_sprint_phase(sprint_id)`).
3. Use CLASI MCP tools for all artifact operations — do not create
   sprint/ticket/TODO files manually.

Direct edits to `docs/clasi/sprints/` are blocked for team-lead. Use MCP tools.
""",
    "source-code.md": """\
---
paths:
  - clasi/**
  - tests/**
---

You are modifying source code or tests. Before writing code:

1. You must have a ticket in `in-progress` status, or the stakeholder
   said "out of process".
2. If you have a ticket, follow the execute-ticket skill — call
   `get_skill_definition("execute-ticket")` if unsure of the steps.
3. Run tests after changes: `uv run pytest`.
""",
    "todo-dir.md": """\
---
paths:
  - docs/clasi/todo/**
---

Use the CLASI `todo` skill or `move_todo_to_done` MCP tool for TODO
operations. Do not use the generic TodoWrite tool for CLASI TODOs.
""",
    "git-commits.md": """\
---
paths:
  - "**/*.py"
  - "**/*.md"
---

Before committing, verify:
1. All tests pass (`uv run pytest`).
2. If on a sprint branch, the sprint has an execution lock.
3. Commit message references the ticket ID if working on a ticket.
See `instructions/git-workflow` for full rules.
""",
}

# Marker used to find/replace the CLASI section in CLAUDE.md.
_AGENTS_SECTION_START = "<!-- CLASI:START -->"
_AGENTS_SECTION_END = "<!-- CLASI:END -->"


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



def _update_settings_json(settings_path: Path) -> bool:
    """Add mcp__clasi__* to the permissions allowlist in settings.local.json.

    Only adds the single permission entry; does not overwrite other settings.
    Creates the file if it doesn't exist.
    Returns True if the file was written/updated, False if unchanged.
    """
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    if settings_path.exists():
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            data = {}
    else:
        data = {}

    permissions = data.setdefault("permissions", {})
    allow = permissions.setdefault("allow", [])

    target_perm = "mcp__clasi__*"
    if target_perm in allow:
        click.echo("  Unchanged: .claude/settings.local.json")
        return False

    allow.append(target_perm)
    settings_path.write_text(
        json.dumps(data, indent=2) + "\n", encoding="utf-8"
    )
    click.echo("  Updated: .claude/settings.local.json")
    return True


def _create_rules(target: Path) -> bool:
    """Create path-scoped rule files in .claude/rules/.

    Writes each CLASI-managed rule file.  Idempotent: compares content
    before writing and skips unchanged files.  Only writes files whose
    names are keys in :data:`RULES`; any other files in the directory
    (custom rules added by the developer) are left untouched.

    Returns True if any file was written/updated, False if all unchanged.
    """
    rules_dir = target / ".claude" / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    changed = False

    for filename, content in RULES.items():
        path = rules_dir / filename
        rel = f".claude/rules/{filename}"
        path.write_text(content, encoding="utf-8")
        click.echo(f"  Wrote: {rel}")
        changed = True

    return changed


_CLAUDE_MD_CONTENT = """\
# CLASI Software Engineering Process

This project uses the CLASI SE process. Your role and workflow are
defined in `.claude/agents/team-lead/agent.md` — read it at session start.

Available skills: run `/se` for a list.
"""


def _write_claude_md(target: Path) -> bool:
    """Write a minimal CLAUDE.md that points to the team-lead agent definition.

    If CLAUDE.md already exists, appends the CLASI section (or updates it
    if the old CLASI:START/END markers are present). If it doesn't exist,
    creates it.
    """
    claude_md = target / "CLAUDE.md"

    if claude_md.exists():
        content = claude_md.read_text(encoding="utf-8")

        # Replace old CLASI:START/END block if present
        if _AGENTS_SECTION_START in content and _AGENTS_SECTION_END in content:
            start_idx = content.index(_AGENTS_SECTION_START)
            end_idx = content.index(_AGENTS_SECTION_END) + len(_AGENTS_SECTION_END)
            new_content = content[:start_idx] + _CLAUDE_MD_CONTENT.strip() + content[end_idx:]
            if new_content != content:
                claude_md.write_text(new_content, encoding="utf-8")
                click.echo("  Updated: CLAUDE.md (replaced old CLASI section)")
                return True
            click.echo("  Unchanged: CLAUDE.md")
            return False

        # Check if our new content is already there
        if "CLASI SE process" in content and "team-lead/agent.md" in content:
            click.echo("  Unchanged: CLAUDE.md")
            return False

        # Append
        if not content.endswith("\n"):
            content += "\n"
        content += "\n" + _CLAUDE_MD_CONTENT
        claude_md.write_text(content, encoding="utf-8")
        click.echo("  Updated: CLAUDE.md (appended CLASI section)")
        return True
    else:
        claude_md.write_text(_CLAUDE_MD_CONTENT, encoding="utf-8")
        click.echo("  Created: CLAUDE.md")
        return True


def _install_plugin_content(target: Path) -> None:
    """Copy skills, agents, and hooks from the plugin/ directory to .claude/.

    This is the project-local installation mode. Skills are unnamespaced.
    """
    if not _PLUGIN_DIR.exists():
        click.echo("  Warning: plugin/ directory not found, skipping content install")
        return

    # Copy skills
    plugin_skills = _PLUGIN_DIR / "skills"
    if plugin_skills.exists():
        target_skills = target / ".claude" / "skills"
        click.echo("Skills:")
        for skill_dir in sorted(plugin_skills.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            dest_dir = target_skills / skill_dir.name
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / "SKILL.md"
            source_content = skill_md.read_text(encoding="utf-8")
            rel = f".claude/skills/{skill_dir.name}/SKILL.md"
            dest.write_text(source_content, encoding="utf-8")
            click.echo(f"  Wrote: {rel}")
        click.echo()

    # Copy agents
    plugin_agents = _PLUGIN_DIR / "agents"
    if plugin_agents.exists():
        target_agents = target / ".claude" / "agents"
        click.echo("Agents:")
        for agent_dir in sorted(plugin_agents.iterdir()):
            if not agent_dir.is_dir():
                continue
            for md_file in agent_dir.glob("*.md"):
                dest_dir = target_agents / agent_dir.name
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest = dest_dir / md_file.name
                source_content = md_file.read_text(encoding="utf-8")
                rel = f".claude/agents/{agent_dir.name}/{md_file.name}"
                dest.write_text(source_content, encoding="utf-8")
                click.echo(f"  Wrote: {rel}")
        click.echo()

    # Copy hook scripts
    plugin_hooks_dir = _PLUGIN_DIR / "hooks"
    if plugin_hooks_dir.exists():
        target_hooks = target / ".claude" / "hooks"
        target_hooks.mkdir(parents=True, exist_ok=True)
        click.echo("Hook scripts:")
        for py_file in sorted(plugin_hooks_dir.glob("*.py")):
            dest = target_hooks / py_file.name
            source_content = py_file.read_text(encoding="utf-8")
            rel = f".claude/hooks/{py_file.name}"
            dest.write_text(source_content, encoding="utf-8")
            # Set execute permission
            dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            click.echo(f"  Wrote: {rel}")
        click.echo()

    # Merge hooks from plugin hooks.json into .claude/settings.json
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

        existing_hooks = settings.setdefault("hooks", {})
        changed = False

        for event_type, entries in hooks_data.get("hooks", {}).items():
            existing = existing_hooks.get(event_type, [])
            for entry in entries:
                cmd = entry.get("hooks", [{}])[0].get("command", "")
                already = any(
                    cmd in (h.get("command", "") for h in e.get("hooks", []))
                    for e in existing
                )
                if not already:
                    existing.append(entry)
                    changed = True
            existing_hooks[event_type] = existing

        if changed:
            settings_path.write_text(
                json.dumps(settings, indent=2) + "\n", encoding="utf-8"
            )
            click.echo("  Updated: .claude/settings.json (hooks)")
        else:
            click.echo("  Unchanged: .claude/settings.json (hooks)")
        click.echo()


def run_init(target: str, plugin_mode: bool = False) -> None:
    """Initialize a repository for the CLASI SE process.

    In project-local mode (default), copies skills, agents, and hooks
    from the plugin/ directory into .claude/. In plugin mode, registers
    the CLASI plugin with Claude Code.
    """
    target_path = Path(target).resolve()
    mode_label = "plugin" if plugin_mode else "project-local"
    click.echo(f"Initializing CLASI in {target_path} ({mode_label} mode)")
    click.echo()

    if plugin_mode:
        # Plugin mode: just tell the user how to install
        click.echo("Plugin mode: install the CLASI plugin with Claude Code:")
        click.echo(f"  claude --plugin-dir {_PLUGIN_DIR}")
        click.echo("  Or: /plugin install clasi (from marketplace)")
        click.echo()
    else:
        # Project-local mode: copy plugin content to .claude/
        _install_plugin_content(target_path)

    # Create CLAUDE.md with minimal CLASI pointer (if it doesn't exist)
    click.echo("CLAUDE.md:")
    _write_claude_md(target_path)
    click.echo()

    # Configure MCP server in .mcp.json at project root
    click.echo("MCP server configuration:")
    _update_mcp_json(target_path / ".mcp.json", target_path)
    click.echo()

    # Add MCP permission to .claude/settings.local.json
    click.echo("MCP permissions:")
    settings_local = target_path / ".claude" / "settings.local.json"
    _update_settings_json(settings_local)
    click.echo()

    if not plugin_mode:
        # Install path-scoped rules in .claude/rules/
        click.echo("Path-scoped rules:")
        _create_rules(target_path)
        click.echo()

    # Create TODO directories
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

    click.echo()
    click.echo("Done! The CLASI SE process is now configured.")
