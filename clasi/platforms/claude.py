"""Claude platform installer and uninstaller for CLASI.

Handles all Claude-specific file operations:
- Writing CLAUDE.md with the CLASI section
- Copying skills, agents, and hooks from the plugin/ directory
- Updating .claude/settings.json hooks
- Updating .claude/settings.local.json MCP permissions
- Creating path-scoped rules in .claude/rules/

Public interface::

    install(target: Path, mcp_config: dict) -> None
    uninstall(target: Path) -> None

Neither function knows about shared scaffolding (TODO dirs, log dir, .mcp.json).
Those remain in init_command.py.
"""

import json
from pathlib import Path
from typing import Dict

import click

# The plugin directory is bundled inside the clasi package.
_PLUGIN_DIR = Path(__file__).parent.parent / "plugin"

# ---------------------------------------------------------------------------
# Path-scoped rules
# ---------------------------------------------------------------------------

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
3. Run the project's test suite after changes.
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
1. All tests pass (run the project's test suite).
2. If on a sprint branch, the sprint has an execution lock.
3. Commit message references the ticket ID if working on a ticket.

After committing substantive changes, run `clasi version bump` to
advance the version, then commit that change (`chore: bump version`).
Tools are installed editable, so the version is how sessions tell
which code is live — bump per commit, not just at sprint close.
Skip the manual bump right before `close_sprint` (it bumps + tags).

See `instructions/git-workflow` for full rules.
""",
}

# ---------------------------------------------------------------------------
# CLAUDE.md helpers
# ---------------------------------------------------------------------------

_CLAUDE_ENTRY_POINT = (
    "Your role and workflow are defined in "
    "`.claude/agents/team-lead/agent.md` — read it at session start."
)


def _write_claude_md(target: Path) -> bool:
    """Write or update CLAUDE.md with the CLASI section."""
    from clasi.platforms._markers import write_section

    return write_section(
        target / "CLAUDE.md",
        entry_point=_CLAUDE_ENTRY_POINT,
        legacy_match_substr="team-lead/agent.md",
    )


# ---------------------------------------------------------------------------
# Plugin content helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Settings helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def install(target: Path, mcp_config: dict) -> None:
    """Install the Claude platform integration into *target*.

    Performs the Claude-specific steps only:
    - Copy skills, agents, and hooks from plugin/ to .claude/
    - Write/update CLAUDE.md with the CLASI marker section
    - Update .claude/settings.local.json with mcp__clasi__* permission
    - Create path-scoped rules in .claude/rules/

    Shared scaffolding (TODO dirs, log dir, .mcp.json) is handled by the
    caller (init_command.run_init).

    Args:
        target: Resolved Path to the target project root.
        mcp_config: The MCP server command dict (unused here; kept for
            interface symmetry with future platform modules that may need it).
    """
    # Copy plugin content (skills, agents, hooks/settings.json)
    _install_plugin_content(target)

    # Write CLAUDE.md
    click.echo("CLAUDE.md:")
    _write_claude_md(target)
    click.echo()

    # Add MCP permission to .claude/settings.local.json
    click.echo("MCP permissions:")
    settings_local = target / ".claude" / "settings.local.json"
    _update_settings_json(settings_local)
    click.echo()

    # Install path-scoped rules in .claude/rules/
    click.echo("Path-scoped rules:")
    _create_rules(target)
    click.echo()


def uninstall(target: Path) -> None:
    """Remove the Claude platform integration from *target*.

    Reverses each Claude-managed artifact:
    - Removes the CLASI marker block from CLAUDE.md (leaves the rest intact).
    - Deletes CLASI-installed files from .claude/skills/ (only skill names
      matching those in the bundled plugin).
    - Deletes CLASI-installed files from .claude/agents/ (only agent dirs
      matching those in the bundled plugin).
    - Deletes CLASI rule files from .claude/rules/ (only filenames in RULES).
    - Removes CLASI hook entries from .claude/settings.json (leaves other
      hooks and keys intact).
    - Removes mcp__clasi__* from the allow list in .claude/settings.local.json.

    This function is non-destructive toward user-added files: only CLASI-owned
    names are touched.

    Args:
        target: Resolved Path to the target project root.
    """
    click.echo(f"Uninstalling Claude platform integration from {target}")
    click.echo()

    # --- CLAUDE.md ---
    from clasi.platforms._markers import strip_section
    strip_section(target / "CLAUDE.md")

    # --- .claude/skills/ ---
    skills_dir = target / ".claude" / "skills"
    if skills_dir.exists() and _PLUGIN_DIR.exists():
        plugin_skills = _PLUGIN_DIR / "skills"
        if plugin_skills.exists():
            for skill_dir in plugin_skills.iterdir():
                if not skill_dir.is_dir():
                    continue
                target_skill = skills_dir / skill_dir.name
                if target_skill.exists():
                    import shutil
                    shutil.rmtree(target_skill)
                    click.echo(f"  Removed: .claude/skills/{skill_dir.name}/")

    # --- .claude/agents/ ---
    agents_dir = target / ".claude" / "agents"
    if agents_dir.exists() and _PLUGIN_DIR.exists():
        plugin_agents = _PLUGIN_DIR / "agents"
        if plugin_agents.exists():
            for agent_dir in plugin_agents.iterdir():
                if not agent_dir.is_dir():
                    continue
                target_agent = agents_dir / agent_dir.name
                if target_agent.exists():
                    import shutil
                    shutil.rmtree(target_agent)
                    click.echo(f"  Removed: .claude/agents/{agent_dir.name}/")

    # --- .claude/rules/ ---
    rules_dir = target / ".claude" / "rules"
    if rules_dir.exists():
        for filename in RULES:
            rule_path = rules_dir / filename
            if rule_path.exists():
                rule_path.unlink()
                click.echo(f"  Removed: .claude/rules/{filename}")

    # --- .claude/settings.json hooks ---
    settings_json = target / ".claude" / "settings.json"
    if settings_json.exists():
        plugin_hooks_path = _PLUGIN_DIR / "hooks" / "hooks.json"
        if plugin_hooks_path.exists():
            try:
                settings = json.loads(settings_json.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, ValueError):
                settings = {}
            hooks_data = json.loads(plugin_hooks_path.read_text(encoding="utf-8"))
            clasi_hooks = hooks_data.get("hooks", {})
            current_hooks = settings.get("hooks", {})
            changed = False
            for event_type, clasi_entries in clasi_hooks.items():
                if event_type in current_hooks and current_hooks[event_type] == clasi_entries:
                    del current_hooks[event_type]
                    changed = True
            if not current_hooks:
                settings.pop("hooks", None)
            elif changed:
                settings["hooks"] = current_hooks
            if changed:
                settings_json.write_text(
                    json.dumps(settings, indent=2) + "\n", encoding="utf-8"
                )
                click.echo("  Updated: .claude/settings.json (removed CLASI hooks)")
            else:
                click.echo("  Unchanged: .claude/settings.json (CLASI hooks not found)")

    # --- .claude/settings.local.json ---
    settings_local = target / ".claude" / "settings.local.json"
    if settings_local.exists():
        try:
            data = json.loads(settings_local.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            data = {}
        allow = data.get("permissions", {}).get("allow", [])
        target_perm = "mcp__clasi__*"
        if target_perm in allow:
            allow.remove(target_perm)
            settings_local.write_text(
                json.dumps(data, indent=2) + "\n", encoding="utf-8"
            )
            click.echo("  Updated: .claude/settings.local.json (removed mcp__clasi__*)")
        else:
            click.echo("  Unchanged: .claude/settings.local.json (permission not found)")

    click.echo()
    click.echo("Done! Claude platform integration removed.")
