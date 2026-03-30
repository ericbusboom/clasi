"""Implementation of the `clasi init` command.

Installs the CLASI SE process into a target repository with minimal
footprint: CLAUDE.md (with inline CLASI section), one skill stub,
MCP config, and permissions. Does not take over existing files.
"""

import json
import shutil
import stat
from pathlib import Path
from typing import Dict

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
            "matcher": "",
            "hooks": [
                {
                    "type": "command",
                    "command": (
                        "echo 'CLASI: Call get_se_overview() to load the"
                        " SE process before doing any work.'"
                    ),
                }
            ],
        }
    ],
    "PreToolUse": [
        {
            "matcher": "Edit|Write|MultiEdit",
            "hooks": [
                {
                    "type": "command",
                    "command": "python3 .claude/hooks/role_guard.py",
                }
            ],
        }
    ],
    "PostToolUse": [
        {
            "matcher": "Bash",
            "hooks": [
                {
                    "type": "command",
                    "command": (
                        "if echo \"$TOOL_INPUT\" | grep -q 'git commit' && "
                        "git branch --show-current 2>/dev/null | grep -qE '^(master|main)$'; then "
                        "echo 'CLASI: You committed on master. Call tag_version() to bump the version.'; "
                        "fi"
                    ),
                }
            ],
        }
    ],
}

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
""",
    "source-code.md": """\
---
paths:
  - claude_agent_skills/**
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

_PACKAGE_DIR = Path(__file__).parent
_SE_SKILL_PATH = _PACKAGE_DIR / "skills" / "se.md"
_AGENTS_SECTION_PATH = _PACKAGE_DIR / "init" / "agents-section.md"
_ROLE_GUARD_SOURCE = _PACKAGE_DIR / "hooks" / "role_guard.py"

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
    """Install all CLASI hooks into settings.json (shared, checked in).

    Installs hooks from HOOKS_CONFIG for each event type
    (UserPromptSubmit, PostToolUse, etc.). Idempotent: checks by
    matching the command string inside each hook entry.

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
    changed = False

    for event_type, entries in HOOKS_CONFIG.items():
        existing = hooks.get(event_type, [])
        for target_entry in entries:
            clasi_command = target_entry["hooks"][0]["command"]
            already_present = any(
                clasi_command in (h.get("command", "") for h in entry.get("hooks", []))
                for entry in existing
            )
            if not already_present:
                existing.append(target_entry)
                changed = True
        hooks[event_type] = existing

    if not changed:
        click.echo("  Unchanged: .claude/settings.json (hooks)")
        return False

    settings_path.write_text(
        json.dumps(data, indent=2) + "\n", encoding="utf-8"
    )
    click.echo("  Updated: .claude/settings.json (hooks)")
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

        if path.exists() and path.read_text(encoding="utf-8") == content:
            click.echo(f"  Unchanged: {rel}")
            continue

        path.write_text(content, encoding="utf-8")
        click.echo(f"  Wrote: {rel}")
        changed = True

    return changed


def _install_role_guard(target: Path) -> bool:
    """Install role_guard.py to .claude/hooks/ with execute permissions.

    Copies from the package's hooks/role_guard.py source file.
    Returns True if the file was written/updated, False if unchanged.
    """
    source = _ROLE_GUARD_SOURCE.read_text(encoding="utf-8")
    dest = target / ".claude" / "hooks" / "role_guard.py"
    dest.parent.mkdir(parents=True, exist_ok=True)
    rel = ".claude/hooks/role_guard.py"

    if dest.exists() and dest.read_text(encoding="utf-8") == source:
        click.echo(f"  Unchanged: {rel}")
        return False

    dest.write_text(source, encoding="utf-8")
    # Set execute permission
    dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    click.echo(f"  Wrote: {rel}")
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

    # Add MCP permission to .claude/settings.local.json (user-specific, gitignored)
    click.echo("MCP permissions:")
    settings_local = target_path / ".claude" / "settings.local.json"
    _update_settings_json(settings_local)
    click.echo()

    # Install session-start hook in .claude/settings.json (shared, checked in)
    click.echo("Session-start hook:")
    settings_shared = target_path / ".claude" / "settings.json"
    _update_hooks_config(settings_shared)
    click.echo()

    # Install role guard hook to .claude/hooks/
    click.echo("Role guard hook:")
    _install_role_guard(target_path)
    click.echo()

    # Install path-scoped rules in .claude/rules/
    click.echo("Path-scoped rules:")
    _create_rules(target_path)

    click.echo()
    click.echo("Done! The CLASI SE process is now configured.")
