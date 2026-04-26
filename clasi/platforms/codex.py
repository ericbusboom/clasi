"""Codex platform installer and uninstaller for CLASI.

Handles all Codex-specific file operations:
- Writing AGENTS.md with a CLASI marker-managed section
- Writing .codex/config.toml with [mcp_servers.clasi] and codex_hooks
- Writing .codex/hooks.json with a Stop hook entry
- Installing .agents/skills/se/SKILL.md from the bundled plugin

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
    "Skills are in `.agents/skills/` — start with the `se` skill at "
    "`.agents/skills/se/SKILL.md`."
)

# ---------------------------------------------------------------------------
# CLASI Stop hook entry
# ---------------------------------------------------------------------------

_CLASI_STOP_HOOK = {"command": "clasi", "args": ["hook", "codex-plan-to-todo"]}


# ---------------------------------------------------------------------------
# AGENTS.md helpers
# ---------------------------------------------------------------------------


def _write_agents_md(target: Path) -> None:
    """Write or update AGENTS.md with the CLASI marker block."""
    from clasi.platforms._markers import write_section

    write_section(target / "AGENTS.md", entry_point=_CODEX_ENTRY_POINT)


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


def _write_codex_hooks(target: Path) -> None:
    """Write or merge .codex/hooks.json with the CLASI Stop hook entry.

    Reads existing JSON if present, merges the CLASI Stop hook entry, and
    writes back. Avoids duplicating the entry if already present.
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

    # Add the CLASI entry only if not already present
    if _CLASI_STOP_HOOK not in stop_list:
        stop_list.append(_CLASI_STOP_HOOK)

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
# Public interface
# ---------------------------------------------------------------------------


def install(target: Path, mcp_config: dict) -> None:
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


def uninstall(target: Path) -> None:
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
        if _CLASI_STOP_HOOK in stop_list:
            stop_list.remove(_CLASI_STOP_HOOK)
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
        # Remove .agents/skills/ if now empty
        if skills_dir.exists() and not any(skills_dir.iterdir()):
            skills_dir.rmdir()
            click.echo("  Removed: .agents/skills/ (empty)")
        # Remove .agents/ if now empty
        agents_root = target / ".agents"
        if agents_root.exists() and not any(agents_root.iterdir()):
            agents_root.rmdir()
            click.echo("  Removed: .agents/ (empty)")
    else:
        click.echo("  Skipped: .agents/skills/ (not found)")

    click.echo()
    click.echo("Done! Codex platform integration removed.")
