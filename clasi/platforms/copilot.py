"""GitHub Copilot platform installer and uninstaller for CLASI.

Handles all Copilot-specific file operations:
- Creating .github/skills/ as a symlink (or copy) to .agents/skills/
- Writing .github/copilot-instructions.md with the CLASI section (ticket 007)
- Writing .github/instructions/<n>.instructions.md path-rule files (ticket 008)
- Writing .github/agents/<n>.agent.md sub-agent files (ticket 009)
- Merging .vscode/mcp.json with the CLASI server entry (ticket 010)

Public interface::

    install(target: Path, mcp_config: dict, copy: bool = False, migrate: bool = False) -> None
    uninstall(target: Path, copy: bool = False) -> None

Neither function knows about shared scaffolding (TODO dirs, log dir, .mcp.json).
Those remain in init_command.py.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import click
import yaml

from clasi.platforms import _links
from clasi.platforms._markers import strip_section, write_section
from clasi.platforms._rules import (
    CLASI_ARTIFACTS_BODY,
    GIT_COMMITS_BODY,
    MCP_REQUIRED_BODY,
    SOURCE_CODE_BODY,
    TODO_DIR_BODY,
)

# The plugin directory is bundled inside the clasi package.
_PLUGIN_DIR = Path(__file__).parent.parent / "plugin"

# ---------------------------------------------------------------------------
# Copilot entry-point sentence
# ---------------------------------------------------------------------------

_COPILOT_ENTRY_POINT = (
    "Read `.github/agents/team-lead.agent.md` at session start "
    "and follow the team-lead role definition."
)


# ---------------------------------------------------------------------------
# Canonical skills writer
# ---------------------------------------------------------------------------


def _ensure_canonical_skills(target: Path) -> None:
    """Write plugin skills to .agents/skills/<n>/SKILL.md (idempotent).

    Copies each bundled SKILL.md to the canonical location only if the file
    does not already exist with matching content.  This means Claude or Codex
    installers that already wrote the canonical files are not disturbed.
    """
    plugin_skills = _PLUGIN_DIR / "skills"
    if not plugin_skills.exists():
        click.echo("  Warning: plugin/skills/ not found, skipping canonical skills write")
        return

    agents_skills = target / ".agents" / "skills"
    for skill_dir in sorted(plugin_skills.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_src = skill_dir / "SKILL.md"
        if not skill_src.exists():
            continue

        dest_dir = agents_skills / skill_dir.name
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / "SKILL.md"

        src_content = skill_src.read_text(encoding="utf-8")
        if dest.exists() and dest.read_text(encoding="utf-8") == src_content:
            # Already up to date — idempotent no-op
            continue

        shutil.copy2(skill_src, dest)
        click.echo(f"  Wrote: .agents/skills/{skill_dir.name}/SKILL.md")


# ---------------------------------------------------------------------------
# .github/skills/ symlink (or copy) — fully implemented here (not a stub)
# ---------------------------------------------------------------------------


def _install_skills(target: Path, copy: bool = False) -> None:
    """Create .github/skills/ as a directory-level alias for .agents/skills/.

    1. Ensures the canonical .agents/skills/ directory and its contents exist.
    2. Creates .github/skills/ -> .agents/skills/ via _links.link_or_copy.
       With copy=False (default), this is a directory symlink.
       With copy=True, the entire directory tree is copied (shutil.copytree).

    Idempotent: an existing symlink pointing at the correct target is replaced
    (removed then re-created) to handle stale symlinks on re-install.
    """
    _ensure_canonical_skills(target)

    agents_skills = target / ".agents" / "skills"
    github_skills = target / ".github" / "skills"

    # Ensure .agents/skills/ exists even if there are no plugin skills
    agents_skills.mkdir(parents=True, exist_ok=True)

    # Remove stale alias if present
    if github_skills.is_symlink() or github_skills.exists():
        if github_skills.is_symlink():
            github_skills.unlink()
        else:
            # It's a real directory — do not delete; leave it and skip
            click.echo(
                "  Warning: .github/skills/ exists as a real directory; "
                "skipping alias creation"
            )
            return

    github_skills.parent.mkdir(parents=True, exist_ok=True)

    if copy:
        shutil.copytree(agents_skills, github_skills)
        click.echo("  Copied: .github/skills/ <- .agents/skills/")
    else:
        import os
        try:
            os.symlink(agents_skills, github_skills)
            click.echo("  Symlinked: .github/skills/ -> .agents/skills/")
        except OSError as exc:
            import warnings
            warnings.warn(
                f"symlink({agents_skills!r} -> {github_skills!r}) failed ({exc}); "
                "falling back to copytree.",
                stacklevel=2,
            )
            shutil.copytree(agents_skills, github_skills)
            click.echo("  Copied (fallback): .github/skills/ <- .agents/skills/")


def _uninstall_skills(target: Path) -> None:
    """Remove the .github/skills/ alias (symlink or copy directory).

    Only the alias is removed; the canonical .agents/skills/ is preserved.
    """
    github_skills = target / ".github" / "skills"
    if github_skills.is_symlink():
        github_skills.unlink()
        click.echo("  Removed: .github/skills/ (symlink)")
    elif github_skills.exists():
        shutil.rmtree(github_skills)
        click.echo("  Removed: .github/skills/ (copy directory)")
    else:
        click.echo("  Skipped: .github/skills/ (not found)")


# ---------------------------------------------------------------------------
# Stubs — filled in by subsequent tickets
# ---------------------------------------------------------------------------


def _install_global_instructions(target: Path, copy: bool = False) -> None:
    """Write .github/copilot-instructions.md with the CLASI marker section.

    Creates or updates the marker block inside the file, preserving any
    user content outside the block.  The block contains:
    - Entry-point sentence pointing at .github/agents/team-lead.agent.md
    - Global-scope rules: MCP Required and Git Commits (from _rules.py)
    """
    path = target / ".github" / "copilot-instructions.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (
        f"{_COPILOT_ENTRY_POINT}\n\n"
        "## Global Rules\n\n"
        "### MCP Server Required\n\n"
        f"{MCP_REQUIRED_BODY}\n"
        "### Git Commits\n\n"
        f"{GIT_COMMITS_BODY}"
    )
    write_section(path, entry_point=body)


def _uninstall_global_instructions(target: Path) -> None:
    """Remove the CLASI block from .github/copilot-instructions.md.

    Strips the CLASI marker block, preserving user content outside it.
    The file is deleted only if it becomes empty after the strip.
    """
    path = target / ".github" / "copilot-instructions.md"
    strip_section(path)


# ---------------------------------------------------------------------------
# Path-scoped instruction files — ticket 008
# ---------------------------------------------------------------------------

# Decision: mcp-required and git-commits have global scope ("**") and are
# already written into .github/copilot-instructions.md by ticket 007.
# Writing them again here as separate .instructions.md files would duplicate
# content without adding value.  Only the three genuinely path-scoped rules
# are emitted here.
_PATH_RULES: list[tuple[str, str, str]] = [
    ("clasi-artifacts.instructions.md", ".clasi/**", CLASI_ARTIFACTS_BODY),
    ("todo-dir.instructions.md", ".clasi/issues/**", TODO_DIR_BODY),
    ("source-code.instructions.md", "clasi/**", SOURCE_CODE_BODY),
]


def _install_path_rules(target: Path) -> None:
    """Write .github/instructions/<n>.instructions.md path-rule files.

    Each file has YAML frontmatter with a single ``applyTo:`` glob field
    followed by the corresponding rule body from ``_rules.py``.  Files are
    full-file writes (not marker-managed) and are overwritten idempotently.

    The directory ``.github/instructions/`` is created if absent.
    """
    rules_dir = target / ".github" / "instructions"
    rules_dir.mkdir(parents=True, exist_ok=True)
    for fname, apply_to, body in _PATH_RULES:
        content = f'---\napplyTo: "{apply_to}"\n---\n\n{body}\n'
        (rules_dir / fname).write_text(content, encoding="utf-8")
        click.echo(f"  Wrote: .github/instructions/{fname}")


def _uninstall_path_rules(target: Path) -> None:
    """Remove CLASI .instructions.md files from .github/instructions/.

    Removes only the files written by ``_install_path_rules`` (by name).
    Does not remove user-created files in the directory.
    Does not rmdir ``.github/instructions/`` even if it becomes empty
    (mirrors the no-cascading-rmdir convention from sprint 012).
    """
    rules_dir = target / ".github" / "instructions"
    for fname, _apply_to, _body in _PATH_RULES:
        fpath = rules_dir / fname
        if fpath.exists():
            fpath.unlink()
            click.echo(f"  Removed: .github/instructions/{fname}")
        else:
            click.echo(f"  Skipped: .github/instructions/{fname} (not found)")


_AGENT_NAMES = ["team-lead", "sprint-planner", "programmer"]


def _install_agents(target: Path, copy: bool = False) -> None:
    """Write .github/agents/<n>.agent.md for each active CLASI agent.

    Reads plugin/agents/<name>/agent.md, maps frontmatter to the Copilot
    agent schema (``description`` required; ``name`` optional), and writes
    the body verbatim.  The directory ``.github/agents/`` is created if absent.
    """
    from clasi.frontmatter import read_document

    agents_dir = target / ".github" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)

    for agent_name in _AGENT_NAMES:
        agent_md = _PLUGIN_DIR / "agents" / agent_name / "agent.md"
        if not agent_md.exists():
            click.echo(
                f"  Warning: plugin/agents/{agent_name}/agent.md not found, skipping"
            )
            continue

        fm, body = read_document(agent_md)

        description = fm.get("description", f"CLASI {agent_name} agent")
        copilot_fm: dict = {"name": fm.get("name", agent_name), "description": description}

        content = "---\n" + yaml.dump(copilot_fm, default_flow_style=False) + "---\n\n" + body
        dest = agents_dir / f"{agent_name}.agent.md"
        dest.write_text(content, encoding="utf-8")
        click.echo(f"  Wrote: .github/agents/{agent_name}.agent.md")


def _uninstall_agents(target: Path) -> None:
    """Remove CLASI .agent.md files from .github/agents/.

    Only removes the CLASI-owned .agent.md files by name.  User-created files
    in ``.github/agents/`` are preserved.  The directory is removed only if it
    is empty after the CLASI files are deleted.
    """
    agents_dir = target / ".github" / "agents"
    if not agents_dir.exists():
        click.echo("  Skipped: .github/agents/ (not found)")
        return

    for agent_name in _AGENT_NAMES:
        dest = agents_dir / f"{agent_name}.agent.md"
        if dest.exists():
            dest.unlink()
            click.echo(f"  Removed: .github/agents/{agent_name}.agent.md")
        else:
            click.echo(f"  Skipped: .github/agents/{agent_name}.agent.md (not found)")

    # Remove the directory only if it is now empty (no user files remain).
    if agents_dir.exists() and not any(agents_dir.iterdir()):
        agents_dir.rmdir()
        click.echo("  Removed: .github/agents/ (empty)")


def _install_vscode_mcp(target: Path, mcp_config: dict) -> None:
    """Merge the CLASI server entry into .vscode/mcp.json.

    - If the file does not exist: create it with ``{"servers": {"clasi": mcp_config}}``.
    - If it exists and parses as JSON: merge ``servers.clasi``, preserving all
      other keys at every level.
    - If it exists but cannot be parsed (corrupt JSON): log an error and skip;
      never overwrite user content.

    Idempotent: if ``servers.clasi`` already matches *mcp_config*, the file is
    not rewritten.
    """
    vscode_dir = target / ".vscode"
    vscode_dir.mkdir(parents=True, exist_ok=True)
    mcp_path = vscode_dir / "mcp.json"

    if mcp_path.exists():
        try:
            data = json.loads(mcp_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            click.echo("  Error: .vscode/mcp.json is not valid JSON; skipping.")
            return
    else:
        data = {}

    servers = data.setdefault("servers", {})

    # Idempotency check — skip write if nothing would change.
    if servers.get("clasi") == mcp_config:
        click.echo("  .vscode/mcp.json already up to date.")
        return

    servers["clasi"] = mcp_config
    mcp_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    click.echo("  Wrote: .vscode/mcp.json")


def _uninstall_vscode_mcp(target: Path) -> None:
    """Remove the CLASI entry from .vscode/mcp.json.

    Strips ``servers.clasi`` from the file, preserving all other keys.
    If the file does not exist, this is a no-op.  If the file is corrupt JSON,
    logs an error and skips.  The ``.vscode/`` directory is never deleted.
    """
    mcp_path = target / ".vscode" / "mcp.json"
    if not mcp_path.exists():
        return

    try:
        data = json.loads(mcp_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        click.echo("  Error: .vscode/mcp.json is not valid JSON; skipping.")
        return

    servers = data.get("servers", {})
    if "clasi" not in servers:
        click.echo("  .vscode/mcp.json: clasi entry not found; nothing to remove.")
        return

    del servers["clasi"]
    mcp_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    click.echo("  Removed clasi from .vscode/mcp.json")


def _print_cloud_mcp_notice(mcp_config: dict) -> None:
    """Print a post-install notice for Copilot Cloud Coding Agent MCP setup.

    GitHub Copilot Cloud Coding Agent cannot read a committed .vscode/mcp.json
    — the MCP server must be registered via GitHub repository Settings.  This
    function emits the JSON snippet the user would paste into
    Settings → Copilot → MCP.
    """
    import json

    servers_entry = {"clasi": mcp_config}
    snippet = json.dumps({"servers": servers_entry}, indent=2)

    click.echo("Copilot Cloud Coding Agent MCP (manual step required):")
    click.echo(
        "  Go to: https://github.com/<owner>/<repo>/settings/copilot/mcp-servers"
    )
    click.echo("  Paste the following JSON snippet into the MCP configuration UI:")
    click.echo()
    for line in snippet.splitlines():
        click.echo(f"    {line}")
    click.echo()


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


def install(
    target: Path,
    mcp_config: dict,
    copy: bool = False,
    migrate: bool = False,
) -> None:
    """Install the GitHub Copilot platform integration into *target*.

    Performs the Copilot-specific steps in order:
    1. Write canonical .agents/skills/ content and create .github/skills/ alias.
    2. Write .github/copilot-instructions.md (ticket 007).
    3. Write .github/instructions/<n>.instructions.md (stub; ticket 008).
    4. Write .github/agents/<n>.agent.md (stub; ticket 009).
    5. Merge .vscode/mcp.json (stub; ticket 010).
    6. Print cloud MCP notice (ticket 007).

    Shared scaffolding (TODO dirs, log dir, .mcp.json) is handled by the
    caller (init_command.run_init).

    Args:
        target: Resolved Path to the target project root.
        mcp_config: The MCP server command dict (written into .vscode/mcp.json
            under servers.clasi in ticket 010).
        copy: If True, use file copy instead of symlink for alias operations.
            Passed through to ``_links.link_or_copy`` and ``_install_skills``.
        migrate: If True, convert legacy direct-copy installs to symlinks.
            Accepted for forward-compatibility; wired in a later ticket.
            Currently a no-op.
    """
    click.echo("GitHub Copilot:")
    click.echo()

    click.echo("Skills:")
    _install_skills(target, copy=copy)
    click.echo()

    click.echo("Global instructions:")
    _install_global_instructions(target, copy=copy)
    click.echo()

    click.echo("Path rules:")
    _install_path_rules(target)
    click.echo()

    click.echo("Agents:")
    _install_agents(target, copy=copy)
    click.echo()

    click.echo("VS Code MCP:")
    _install_vscode_mcp(target, mcp_config)
    click.echo()

    click.echo("Cloud MCP notice:")
    _print_cloud_mcp_notice(mcp_config)
    click.echo()

    from clasi.platforms._markers import write_version_stamp
    click.echo("Version stamp:")
    write_version_stamp(target)
    click.echo()


def uninstall(target: Path, copy: bool = False) -> None:
    """Remove the GitHub Copilot platform integration from *target*.

    Reverses each Copilot-managed artifact:
    - Removes the .github/skills/ alias (symlink or copy); canonical
      .agents/skills/ is preserved.
    - Removes the CLASI block from .github/copilot-instructions.md (stub; 007).
    - Removes .github/instructions/ CLASI files (stub; ticket 008).
    - Removes .github/agents/ CLASI files (stub; ticket 009).
    - Removes servers.clasi from .vscode/mcp.json (stub; ticket 010).

    This function is non-destructive toward user-added files: only
    CLASI-owned sections and entries are removed.

    Args:
        target: Resolved Path to the target project root.
        copy: If True, alias removal uses file-copy semantics.  ``unlink_alias``
            handles both symlinks and regular files uniformly; this flag is
            accepted for CLI parity with ``clasi uninstall --copy``.
    """
    click.echo(f"Uninstalling GitHub Copilot platform integration from {target}")
    click.echo()

    click.echo("Skills:")
    _uninstall_skills(target)
    click.echo()

    click.echo("Global instructions:")
    _uninstall_global_instructions(target)
    click.echo()

    click.echo("Path rules:")
    _uninstall_path_rules(target)
    click.echo()

    click.echo("Agents:")
    _uninstall_agents(target)
    click.echo()

    click.echo("VS Code MCP:")
    _uninstall_vscode_mcp(target)
    click.echo()

    # --- .clasi/clasi-version ---
    from clasi.platforms._markers import remove_version_stamp
    click.echo("Version stamp:")
    remove_version_stamp(target)
    click.echo()

    click.echo("Done! GitHub Copilot platform integration removed.")
