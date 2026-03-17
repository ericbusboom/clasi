"""Implementation of the `clasi init` command.

Installs the CLASI SE process into a target repository with minimal
footprint: CLAUDE.md (with inline CLASI section), one skill stub,
MCP config, and permissions. Does not take over existing files.
"""

import json
from pathlib import Path

import click

MCP_CONFIG = {
    "clasi": {
        "command": "clasi",
        "args": ["mcp"],
    }
}

HOOKS_CONFIG = {
    "UserPromptSubmit": [
        {
            "type": "command",
            "command": (
                "echo 'CLASI: Call get_se_overview() to load the"
                " SE process before doing any work.'"
            ),
        }
    ]
}

_PACKAGE_DIR = Path(__file__).parent
_SE_SKILL_PATH = _PACKAGE_DIR / "skills" / "se.md"
_AGENTS_SECTION_PATH = _PACKAGE_DIR / "init" / "agents-section.md"

# Marker used to find/replace the CLASI section in CLAUDE.md.
_AGENTS_SECTION_START = "<!-- CLASI:START -->"
_AGENTS_SECTION_END = "<!-- CLASI:END -->"


def _write_se_skill(target: Path) -> bool:
    """Write the /se skill stub to .claude/skills/se/SKILL.md.

    Copies from the package's skills/se.md source file.
    Returns True if the file was written/updated, False if unchanged.
    """
    source = _SE_SKILL_PATH.read_text(encoding="utf-8")
    path = target / ".claude" / "skills" / "se" / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    rel = ".claude/skills/se/SKILL.md"

    if path.exists() and path.read_text(encoding="utf-8") == source:
        click.echo(f"  Unchanged: {rel}")
        return False

    path.write_text(source, encoding="utf-8")
    click.echo(f"  Wrote: {rel}")
    return True


def _read_agents_section() -> str:
    """Read the AGENTS.md section content from the package file.

    Returns the section text with trailing whitespace stripped.
    """
    return _AGENTS_SECTION_PATH.read_text(encoding="utf-8").rstrip()


def _update_claude_md(target: Path) -> bool:
    """Append or update the CLASI section in CLAUDE.md.

    If CLAUDE.md doesn't exist, creates it with just the CLASI section.
    If it exists but has no CLASI section, appends the section.
    If it exists with a CLASI section, replaces it in place.

    Returns True if the file was written/updated, False if unchanged.
    """
    claude_md = target / "CLAUDE.md"
    section = _read_agents_section()

    if claude_md.exists():
        content = claude_md.read_text(encoding="utf-8")

        if _AGENTS_SECTION_START in content and _AGENTS_SECTION_END in content:
            # Replace existing CLASI section in place
            start_idx = content.index(_AGENTS_SECTION_START)
            end_idx = content.index(_AGENTS_SECTION_END) + len(_AGENTS_SECTION_END)
            new_content = content[:start_idx] + section + content[end_idx:]
        else:
            # Append to existing content
            if not content.endswith("\n"):
                content += "\n"
            new_content = content + "\n" + section + "\n"

        if new_content == content:
            click.echo("  Unchanged: CLAUDE.md")
            return False

        claude_md.write_text(new_content, encoding="utf-8")
        click.echo("  Updated: CLAUDE.md")
        return True
    else:
        claude_md.write_text(section + "\n", encoding="utf-8")
        click.echo("  Created: CLAUDE.md")
        return True


VSCODE_MCP_CONFIG = {
    "clasi": {
        "type": "stdio",
        "command": "clasi",
        "args": ["mcp"],
    }
}


def _update_mcp_json(mcp_json_path: Path) -> bool:
    """Merge MCP server config into .mcp.json.

    Returns True if the file was written/updated, False if unchanged.
    """
    rel = str(mcp_json_path.name)

    if mcp_json_path.exists():
        try:
            data = json.loads(mcp_json_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            data = {}
    else:
        data = {}

    mcp_servers = data.setdefault("mcpServers", {})

    if mcp_servers.get("clasi") == MCP_CONFIG["clasi"]:
        click.echo(f"  Unchanged: {rel}")
        return False

    mcp_servers["clasi"] = MCP_CONFIG["clasi"]
    mcp_json_path.write_text(
        json.dumps(data, indent=2) + "\n", encoding="utf-8"
    )
    click.echo(f"  Updated: {rel}")
    return True


def _update_vscode_mcp_json(target: Path) -> bool:
    """Merge MCP server config into .vscode/mcp.json.

    Uses the VS Code format (servers key with type field).
    Returns True if the file was written/updated, False if unchanged.
    """
    vscode_dir = target / ".vscode"
    mcp_json_path = vscode_dir / "mcp.json"
    rel = ".vscode/mcp.json"

    if mcp_json_path.exists():
        try:
            data = json.loads(mcp_json_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            data = {}
    else:
        data = {}

    servers = data.setdefault("servers", {})

    if servers.get("clasi") == VSCODE_MCP_CONFIG["clasi"]:
        click.echo(f"  Unchanged: {rel}")
        return False

    vscode_dir.mkdir(parents=True, exist_ok=True)
    servers["clasi"] = VSCODE_MCP_CONFIG["clasi"]
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


def _update_hooks_config(settings_path: Path) -> bool:
    """Add session-start hook to settings.local.json.

    Installs a UserPromptSubmit hook that reminds the agent to load the
    SE process.  Idempotent: if the hook already exists with the correct
    command, no changes are made.

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

    hooks = data.setdefault("hooks", {})
    target_hooks = HOOKS_CONFIG["UserPromptSubmit"]

    existing = hooks.get("UserPromptSubmit", [])

    # Check if the CLASI hook entry already exists (by command match)
    clasi_command = target_hooks[0]["command"]
    already_present = any(
        entry.get("command") == clasi_command for entry in existing
    )

    if already_present:
        click.echo("  Unchanged: .claude/settings.local.json (hooks)")
        return False

    existing.extend(target_hooks)
    hooks["UserPromptSubmit"] = existing
    settings_path.write_text(
        json.dumps(data, indent=2) + "\n", encoding="utf-8"
    )
    click.echo("  Updated: .claude/settings.local.json (hooks)")
    return True


def run_init(target: str) -> None:
    """Initialize a repository for the CLASI SE process.

    Creates CLAUDE.md (with inline CLASI section), writes the /se skill
    stub, and configures the MCP server.
    """
    target_path = Path(target).resolve()
    click.echo(f"Initializing CLASI in {target_path}")
    click.echo()

    # Install the /se skill dispatcher
    click.echo("Skill stub:")
    _write_se_skill(target_path)
    click.echo()

    # Create or update CLAUDE.md with inline CLASI section
    click.echo("CLAUDE.md:")
    _update_claude_md(target_path)
    click.echo()

    # Configure MCP server in .mcp.json at project root
    click.echo("MCP server configuration:")
    _update_mcp_json(target_path / ".mcp.json")
    _update_vscode_mcp_json(target_path)
    click.echo()

    # Add MCP permission to .claude/settings.local.json
    click.echo("MCP permissions:")
    settings_json = target_path / ".claude" / "settings.local.json"
    _update_settings_json(settings_json)
    click.echo()

    # Install session-start hook in .claude/settings.local.json
    click.echo("Session-start hook:")
    _update_hooks_config(settings_json)

    click.echo()
    click.echo("Done! The CLASI SE process is now configured.")
