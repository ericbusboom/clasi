"""Codex platform installer and uninstaller for CLASI.

Handles all Codex-specific file operations:
- Writing AGENTS.md with a CLASI marker-managed section
- Writing .codex/config.toml with [mcp_servers.clasi] and codex_hooks
- Writing .codex/hooks.json with a Stop hook entry
- Installing .agents/skills/se/SKILL.md from the bundled plugin
- Writing .codex/agents/<name>.toml sub-agent definitions

Public interface::

    install(target: Path, mcp_config: dict) -> None
    uninstall(target: Path) -> None

Neither function knows about shared scaffolding (TODO dirs, log dir, .mcp.json).
Those remain in init_command.py.
"""

from __future__ import annotations

import json
from pathlib import Path

import click

from clasi.platforms._rules import (
    CLASI_ARTIFACTS_BODY,
    GIT_COMMITS_BODY,
    MCP_REQUIRED_BODY,
    SOURCE_CODE_BODY,
    TODO_DIR_BODY,
)

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]
import tomli_w

# The plugin directory is bundled inside the clasi package.
_PLUGIN_DIR = Path(__file__).parent.parent / "plugin"

# ---------------------------------------------------------------------------
# CLASI section content (shared template via clasi.platforms._markers)
# ---------------------------------------------------------------------------

_CODEX_ENTRY_POINT = (
    "**You are the CLASI team-lead** — the root agent the user "
    "interacts with. Read `.codex/agents/team-lead.toml` at session "
    "start for your role and workflow (the `developer_instructions` "
    "field is your operating contract). Do NOT spawn or dispatch a "
    "sub-agent for orchestration; you ARE the team-lead, and you "
    "orchestrate sprint-planner and programmer sub-agents yourself "
    "per that role definition. Skills live under `.agents/skills/`."
)

# ---------------------------------------------------------------------------
# CLASI Stop hook entry
#
# Codex hooks.json schema (https://developers.openai.com/codex/hooks):
#   The Stop array contains wrapper objects. Each wrapper has a "hooks" list
#   of handler objects with type, command (shell string), and timeout.
#
# Known limitation (openai/codex#17532):
#   Repo-local .codex/hooks.json may not fire in interactive Codex sessions.
#   Only ~/.codex/hooks.json is reliably loaded. Until Codex resolves this,
#   users must manually copy .codex/hooks.json to ~/.codex/hooks.json for
#   the Stop hook to fire. See docs/README.md for the workaround.
#   Installing to ~/.codex/ is out of scope for `clasi install --codex`.
# ---------------------------------------------------------------------------

# Old flat format (wrong — kept only for backward-compat removal detection).
_CLASI_STOP_HOOK_OLD = {"command": "clasi", "args": ["hook", "codex-plan-to-todo"]}

# New wrapper format matching the Codex hooks specification.
_CLASI_STOP_HOOK_WRAPPER = {
    "hooks": [
        {"type": "command", "command": "clasi hook codex-plan-to-todo", "timeout": 30}
    ]
}

# Command string used to identify the CLASI handler in the nested hooks list.
_CLASI_HOOK_COMMAND = "clasi hook codex-plan-to-todo"


# ---------------------------------------------------------------------------
# AGENTS.md helpers
# ---------------------------------------------------------------------------


def _build_global_rules_content() -> str:
    """Render the global-scope rules content appended to the entry-point block.

    These are the rules with `paths: ["**"]` on the Claude side
    (mcp-required + git-commits). Codex has no native path-scoped rule
    mechanism, so global-scope rules ride along inside the same single
    CLASI block on root AGENTS.md as the entry-point sentence.
    """
    return (
        "## Global Rules\n\n"
        "### MCP Server Required\n\n"
        f"{MCP_REQUIRED_BODY}\n"
        "### Git Commits\n\n"
        f"{GIT_COMMITS_BODY}"
    )


def _write_agents_md(target: Path) -> None:
    """Write or update AGENTS.md with a single CLASI marker block.

    The block contains the entry-point sentence followed by the
    global-scope rules. One block, one purpose: tell the agent who they
    are and what global guardrails apply.
    """
    from clasi.platforms._markers import write_section

    body = f"{_CODEX_ENTRY_POINT}\n\n{_build_global_rules_content()}"
    write_section(target / "AGENTS.md", entry_point=body)


# ---------------------------------------------------------------------------
# .codex/config.toml helpers
# ---------------------------------------------------------------------------


def _write_codex_config(target: Path, mcp_config: dict) -> None:
    """Write or merge .codex/config.toml with [mcp_servers.clasi] and codex_hooks.

    Reads existing TOML if present, merges the CLASI keys, and writes back.
    """
    config_path = target / ".codex" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    if config_path.exists():
        try:
            data = tomllib.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    else:
        data = {}

    mcp_servers = data.setdefault("mcp_servers", {})
    mcp_servers["clasi"] = dict(mcp_config)
    data["codex_hooks"] = True

    config_path.write_text(tomli_w.dumps(data), encoding="utf-8")
    click.echo("  Wrote: .codex/config.toml")


# ---------------------------------------------------------------------------
# .codex/hooks.json helpers
# ---------------------------------------------------------------------------


def _is_clasi_wrapper_entry(entry: object) -> bool:
    """Return True if *entry* is a CLASI Stop hook wrapper (new format)."""
    if not isinstance(entry, dict):
        return False
    inner = entry.get("hooks", [])
    if not isinstance(inner, list) or not inner:
        return False
    return inner[0].get("command") == _CLASI_HOOK_COMMAND


def _write_codex_hooks(target: Path) -> None:
    """Write or merge .codex/hooks.json with the CLASI Stop hook entry.

    Reads existing JSON if present, merges the CLASI Stop hook entry, and
    writes back. Avoids duplicating the entry if already present.

    Backward compatibility: if the Stop list contains an old flat-format
    entry ``{"command": "clasi", "args": [...]}`` it is removed and replaced
    with the new wrapper format (see _CLASI_STOP_HOOK_WRAPPER).

    Schema source: https://developers.openai.com/codex/hooks
    Firing limitation: see module-level comment on openai/codex#17532.
    """
    hooks_path = target / ".codex" / "hooks.json"
    hooks_path.parent.mkdir(parents=True, exist_ok=True)

    if hooks_path.exists():
        try:
            data = json.loads(hooks_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            data = {}
    else:
        data = {}

    hooks = data.setdefault("hooks", {})
    stop_list = hooks.setdefault("Stop", [])

    # Remove old flat-format entry if present (backward compat migration).
    if _CLASI_STOP_HOOK_OLD in stop_list:
        stop_list.remove(_CLASI_STOP_HOOK_OLD)

    # Add the new wrapper entry only if not already present.
    if not any(_is_clasi_wrapper_entry(e) for e in stop_list):
        stop_list.append(_CLASI_STOP_HOOK_WRAPPER)

    hooks_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    click.echo("  Wrote: .codex/hooks.json")


# ---------------------------------------------------------------------------
# .agents/skills/se/SKILL.md helpers
# ---------------------------------------------------------------------------


def _install_skills(target: Path) -> None:
    """Copy every bundled skill into .agents/skills/<name>/SKILL.md.

    Mirrors the Claude installer, which copies every skill in plugin/skills/
    to .claude/skills/. Codex needs the full skill set for the SE process
    to function; installing only the `se` skill is not enough.
    """
    plugin_skills = _PLUGIN_DIR / "skills"
    if not plugin_skills.exists():
        click.echo("  Warning: plugin/skills/ not found, skipping")
        return

    target_skills = target / ".agents" / "skills"
    for skill_dir in sorted(plugin_skills.iterdir()):
        if not skill_dir.is_dir():
            continue
        source_skill_md = skill_dir / "SKILL.md"
        if not source_skill_md.exists():
            continue
        dest_dir = target_skills / skill_dir.name
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_skill_md = dest_dir / "SKILL.md"
        dest_skill_md.write_text(
            source_skill_md.read_text(encoding="utf-8"), encoding="utf-8"
        )
        click.echo(f"  Wrote: .agents/skills/{skill_dir.name}/SKILL.md")


# ---------------------------------------------------------------------------
# .codex/agents/<name>.toml sub-agent helpers
#
# Known limitation: developer_instructions is the agent.md body verbatim.
# Some Claude-Code-specific phrasing (e.g., "dispatch via Agent tool") is
# present in the instructions but does not apply on Codex. A translation layer
# that strips or adapts Claude-specific constructs is deferred to a future sprint.
# ---------------------------------------------------------------------------

_ACTIVE_AGENTS = ["team-lead", "sprint-planner", "programmer"]

# ---------------------------------------------------------------------------
# Nested AGENTS.md rule content
#
# These are plain prose instruction files owned entirely by the Codex installer.
# They are NOT marker-managed sections — the installer writes them in full and
# the uninstaller removes them by exact path.
#
# Rationale: Codex has no path-scoped rule equivalent to Claude's .claude/rules/
# directory. Nested AGENTS.md files at subdirectory roots are the closest
# alternative — Codex reads the closest file upward in the directory tree.
# ---------------------------------------------------------------------------

_CLASI_SRC_RULES = SOURCE_CODE_BODY


def _build_docs_clasi_content() -> str:
    """Build the full content for docs/clasi/AGENTS.md.

    Wraps the complete CLASI_ARTIFACTS_BODY (active-sprint check, phase check,
    and MCP-tools-only instruction) with a section header.
    """
    return f"# CLASI SE Process Rules\n\n{CLASI_ARTIFACTS_BODY}\n"


def _build_todo_dir_content() -> str:
    """Build the content for docs/clasi/todo/AGENTS.md.

    Wraps TODO_DIR_BODY with a section header so Codex agents working in
    docs/clasi/todo/ receive the instruction to use CLASI tooling.
    """
    return f"# CLASI TODO Rules\n\n{TODO_DIR_BODY}\n"


def _install_agents(target: Path) -> None:
    """Write .codex/agents/<name>.toml for each active CLASI agent.

    Reads plugin/agents/<name>/agent.md, extracts frontmatter (description,
    title) and body, then writes a TOML file with the fields required by the
    Codex sub-agent spec (https://developers.openai.com/codex/subagents):
    name, description, developer_instructions.
    """
    from clasi.frontmatter import read_document

    agents_dir = target / ".codex" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)

    for agent_name in _ACTIVE_AGENTS:
        agent_md = _PLUGIN_DIR / "agents" / agent_name / "agent.md"
        if not agent_md.exists():
            click.echo(
                f"  Warning: plugin/agents/{agent_name}/agent.md not found, skipping"
            )
            continue

        fm, body = read_document(agent_md)

        data = {
            "name": fm.get("name", agent_name),
            "description": fm.get("description", ""),
            # Body is the markdown content after the frontmatter block, stripped
            # of leading/trailing whitespace.
            "developer_instructions": body.strip(),
        }

        dest = agents_dir / f"{agent_name}.toml"
        dest.write_text(tomli_w.dumps(data), encoding="utf-8")
        click.echo(f"  Wrote: .codex/agents/{agent_name}.toml")


def _uninstall_agents(target: Path) -> None:
    """Remove .codex/agents/<name>.toml for each active CLASI agent.

    Only removes the CLASI-owned TOML files. User-added files in
    .codex/agents/ are preserved. The directory is removed only if it is
    empty after the CLASI files are deleted.
    """
    agents_dir = target / ".codex" / "agents"
    if not agents_dir.exists():
        click.echo("  Skipped: .codex/agents/ (not found)")
        return

    for agent_name in _ACTIVE_AGENTS:
        dest = agents_dir / f"{agent_name}.toml"
        if dest.exists():
            dest.unlink()
            click.echo(f"  Removed: .codex/agents/{agent_name}.toml")
        else:
            click.echo(f"  Skipped: .codex/agents/{agent_name}.toml (not found)")

    # Remove the directory only if it is now empty (no user files remain).
    if agents_dir.exists() and not any(agents_dir.iterdir()):
        agents_dir.rmdir()
        click.echo("  Removed: .codex/agents/ (empty)")


# ---------------------------------------------------------------------------
# Nested AGENTS.md rule file helpers
# ---------------------------------------------------------------------------


def _install_rules(target: Path) -> None:
    """Write nested AGENTS.md rule files at docs/clasi/, docs/clasi/todo/, and clasi/.

    These files provide path-scoped guidance for Codex agents operating in
    those directories, mirroring the intent of Claude's .claude/rules/ files.
    Each file is written in full (not marker-managed) and owned by the
    Codex installer.
    """
    docs_clasi = target / "docs" / "clasi"
    docs_clasi.mkdir(parents=True, exist_ok=True)
    (docs_clasi / "AGENTS.md").write_text(_build_docs_clasi_content(), encoding="utf-8")
    click.echo("  Wrote: docs/clasi/AGENTS.md")

    docs_clasi_todo = target / "docs" / "clasi" / "todo"
    docs_clasi_todo.mkdir(parents=True, exist_ok=True)
    (docs_clasi_todo / "AGENTS.md").write_text(_build_todo_dir_content(), encoding="utf-8")
    click.echo("  Wrote: docs/clasi/todo/AGENTS.md")

    clasi_src = target / "clasi"
    clasi_src.mkdir(parents=True, exist_ok=True)
    (clasi_src / "AGENTS.md").write_text(_CLASI_SRC_RULES, encoding="utf-8")
    click.echo("  Wrote: clasi/AGENTS.md")


def _uninstall_rules(target: Path) -> None:
    """Remove nested AGENTS.md rule files written by _install_rules.

    Non-destructive: if any file does not exist, the removal is skipped
    without error.
    """
    docs_clasi_md = target / "docs" / "clasi" / "AGENTS.md"
    if docs_clasi_md.exists():
        docs_clasi_md.unlink()
        click.echo("  Removed: docs/clasi/AGENTS.md")
    else:
        click.echo("  Skipped: docs/clasi/AGENTS.md (not found)")

    docs_clasi_todo_md = target / "docs" / "clasi" / "todo" / "AGENTS.md"
    if docs_clasi_todo_md.exists():
        docs_clasi_todo_md.unlink()
        click.echo("  Removed: docs/clasi/todo/AGENTS.md")
    else:
        click.echo("  Skipped: docs/clasi/todo/AGENTS.md (not found)")

    clasi_src_md = target / "clasi" / "AGENTS.md"
    if clasi_src_md.exists():
        clasi_src_md.unlink()
        click.echo("  Removed: clasi/AGENTS.md")
    else:
        click.echo("  Skipped: clasi/AGENTS.md (not found)")


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


def install(
    target: Path,
    mcp_config: dict,
    copy: bool = False,
    migrate: bool = False,
) -> None:
    """Install the Codex platform integration into *target*.

    Performs the Codex-specific steps only:
    - Create or update AGENTS.md with the CLASI marker section
    - Write .codex/config.toml with [mcp_servers.clasi] and codex_hooks = true
    - Write .codex/hooks.json with the CLASI Stop hook entry
    - Copy .agents/skills/se/SKILL.md from the bundled plugin

    Shared scaffolding (TODO dirs, log dir, .mcp.json) is handled by the
    caller (init_command.run_init).

    Args:
        target: Resolved Path to the target project root.
        mcp_config: The MCP server command dict (written into .codex/config.toml
            under [mcp_servers.clasi]).
        copy: If True, use file copy instead of symlink for alias operations.
            Accepted for forward-compatibility; wired to ``_links.link_or_copy``
            in a later ticket.  Currently a no-op.
        migrate: If True, convert legacy direct-copy installs to symlinks.
            Accepted for forward-compatibility; wired in a later ticket.
            Currently a no-op.
    """
    click.echo("AGENTS.md:")
    _write_agents_md(target)
    click.echo()

    click.echo("Codex config:")
    _write_codex_config(target, mcp_config)
    click.echo()

    click.echo("Codex hooks:")
    _write_codex_hooks(target)
    click.echo()

    click.echo("Codex skills:")
    _install_skills(target)
    click.echo()

    click.echo("Codex agents:")
    _install_agents(target)
    click.echo()

    click.echo("Nested rule files:")
    _install_rules(target)
    click.echo()

    from clasi.platforms._markers import write_version_stamp
    click.echo("Version stamps:")
    write_version_stamp(target, ".codex")
    write_version_stamp(target, ".agents")
    click.echo()


def uninstall(target: Path, copy: bool = False) -> None:
    """Remove the Codex platform integration from *target*.

    Reverses each Codex-managed artifact:
    - Removes the CLASI marker block from AGENTS.md (preserves rest of file).
      Deletes the file if it becomes empty.
    - Removes mcp_servers.clasi and codex_hooks from .codex/config.toml.
      Deletes the file if it becomes empty ({}).
    - Removes the CLASI Stop hook entry from .codex/hooks.json.
      Removes the Stop key if the list becomes empty.
      Deletes the file if hooks becomes {}.
    - Deletes .agents/skills/se/SKILL.md.
      Removes .agents/skills/se/ if it is now empty.

    This function is non-destructive toward user-added files: only CLASI-owned
    sections and entries are removed.

    Args:
        target: Resolved Path to the target project root.
        copy: If True, alias removal uses file-copy semantics.  Accepted for
            parity with ``clasi uninstall --copy``; wired to
            ``_links.unlink_alias`` in a later ticket.  Currently a no-op.
    """
    click.echo(f"Uninstalling Codex platform integration from {target}")
    click.echo()

    # --- AGENTS.md ---
    from clasi.platforms._markers import strip_section
    strip_section(target / "AGENTS.md")

    # --- .codex/config.toml ---
    config_path = target / ".codex" / "config.toml"
    if config_path.exists():
        try:
            data = tomllib.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        mcp_servers = data.get("mcp_servers", {})
        changed = False
        if "clasi" in mcp_servers:
            del mcp_servers["clasi"]
            changed = True
            if not mcp_servers:
                data.pop("mcp_servers", None)
        if "codex_hooks" in data:
            del data["codex_hooks"]
            changed = True
        if changed:
            if data:
                config_path.write_text(tomli_w.dumps(data), encoding="utf-8")
                click.echo("  Updated: .codex/config.toml (removed CLASI entries)")
            else:
                config_path.unlink()
                click.echo("  Deleted: .codex/config.toml (was only CLASI content)")
        else:
            click.echo("  Unchanged: .codex/config.toml (CLASI entries not found)")
    else:
        click.echo("  Skipped: .codex/config.toml (not found)")

    # --- .codex/hooks.json ---
    hooks_path = target / ".codex" / "hooks.json"
    if hooks_path.exists():
        try:
            data = json.loads(hooks_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            data = {}
        hooks = data.get("hooks", {})
        stop_list = hooks.get("Stop", [])
        # Remove both old flat-format and new wrapper-format CLASI entries.
        before_len = len(stop_list)
        stop_list[:] = [
            e for e in stop_list
            if e != _CLASI_STOP_HOOK_OLD and not _is_clasi_wrapper_entry(e)
        ]
        removed = len(stop_list) < before_len
        if removed:
            if not stop_list:
                del hooks["Stop"]
            if not hooks:
                data.pop("hooks", None)
            if data:
                hooks_path.write_text(
                    json.dumps(data, indent=2) + "\n", encoding="utf-8"
                )
                click.echo("  Updated: .codex/hooks.json (removed CLASI Stop hook)")
            else:
                hooks_path.unlink()
                click.echo("  Deleted: .codex/hooks.json (was only CLASI content)")
        else:
            click.echo("  Unchanged: .codex/hooks.json (CLASI Stop hook not found)")
    else:
        click.echo("  Skipped: .codex/hooks.json (not found)")

    # --- .agents/skills/ ---
    skills_dir = target / ".agents" / "skills"
    if skills_dir.exists() and _PLUGIN_DIR.exists():
        plugin_skills = _PLUGIN_DIR / "skills"
        if plugin_skills.exists():
            for skill_dir in plugin_skills.iterdir():
                if not skill_dir.is_dir():
                    continue
                target_skill = skills_dir / skill_dir.name
                if target_skill.exists():
                    skill_md = target_skill / "SKILL.md"
                    if skill_md.exists():
                        skill_md.unlink()
                    if not any(target_skill.iterdir()):
                        target_skill.rmdir()
                    click.echo(f"  Removed: .agents/skills/{skill_dir.name}/")
    else:
        click.echo("  Skipped: .agents/skills/ (not found)")

    # --- .codex/agents/ ---
    click.echo()
    click.echo("Codex agents:")
    _uninstall_agents(target)

    # --- Nested AGENTS.md rule files ---
    click.echo()
    click.echo("Nested rule files:")
    _uninstall_rules(target)

    click.echo()
    click.echo("Done! Codex platform integration removed.")
