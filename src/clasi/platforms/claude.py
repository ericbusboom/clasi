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
import shutil
from pathlib import Path
from typing import Dict

import click

from clasi.platforms import _links
from clasi.platforms._rules import (
    CLASI_ARTIFACTS_BODY,
    GIT_COMMITS_BODY,
    MCP_REQUIRED_BODY,
    SOURCE_CODE_BODY,
    TODO_DIR_BODY,
    TOOL_CALL_EMPTY_ARGS_BODY,
)

# The plugin directory is bundled inside the clasi package.
_PLUGIN_DIR = Path(__file__).parent.parent / "plugin"

# ---------------------------------------------------------------------------
# Path-scoped rules
# ---------------------------------------------------------------------------

# Path-scoped rules installed by `clasi init`.
# Each key is the filename under `.claude/rules/`, each value is the
# complete file content (YAML frontmatter + markdown body).
# Rule bodies are sourced from clasi.platforms._rules (single source of truth).
RULES: Dict[str, str] = {
    "mcp-required.md": (
        '---\npaths:\n  - "**"\n---\n\n' + MCP_REQUIRED_BODY
    ),
    "clasi-artifacts.md": (
        "---\npaths:\n  - clasi/**\n---\n\n" + CLASI_ARTIFACTS_BODY
    ),
    "source-code.md": SOURCE_CODE_BODY,
    "todo-dir.md": (
        "---\npaths:\n  - clasi/issues/**\n---\n\n" + TODO_DIR_BODY
    ),
    "git-commits.md": (
        '---\npaths:\n  - "**/*.py"\n  - "**/*.md"\n---\n\n' + GIT_COMMITS_BODY
    ),
    "tool-call-empty-args.md": (
        '---\npaths:\n  - "**"\n---\n\n# Tool Call Empty-Argument Bug\n\n'
        + TOOL_CALL_EMPTY_ARGS_BODY
    ),
}

# ---------------------------------------------------------------------------
# CLAUDE.md helpers
# ---------------------------------------------------------------------------

_CLAUDE_ENTRY_POINT = (
    "**You are the CLASI team-lead** — the root agent the user "
    "interacts with. Read `.claude/agents/team-lead/agent.md` at "
    "session start for your role and workflow. Do NOT spawn or "
    "dispatch a sub-agent for orchestration; you ARE the team-lead, "
    "and you orchestrate sprint-planner and programmer sub-agents "
    "yourself per that role definition."
)


def _write_claude_md(target: Path, copy: bool = False) -> bool:
    """Write the CLASI marker block into both AGENTS.md and CLAUDE.md.

    Both files are regular files holding their own copy of the CLASI
    block, written via the marker-block writer. This makes CLASI a
    well-behaved tenant alongside other tools (e.g. rundbat) that
    already manage their own named blocks in CLAUDE.md.

    The previous symlink-based model (CLAUDE.md → AGENTS.md) is
    retired: it failed when CLAUDE.md was already a regular file owned
    by another tool, and it required a `--migrate` flag to escape.

    The `copy` parameter is accepted for interface symmetry with the
    legacy installer call sites but is no longer meaningful for this
    function (no symlinking happens here). Skill aliases under
    `.claude/skills/` are still symlinked-or-copied; that path is
    handled by `_install_plugin_content`.

    Returns True if either file was written/updated, False if both
    were already up to date.
    """
    from clasi.platforms._markers import write_section

    agents_md = target / "AGENTS.md"
    claude_md = target / "CLAUDE.md"

    agents_changed = write_section(
        agents_md,
        entry_point=_CLAUDE_ENTRY_POINT,
        legacy_match_substr="team-lead/agent.md",
    )
    claude_changed = write_section(
        claude_md,
        entry_point=_CLAUDE_ENTRY_POINT,
        legacy_match_substr="team-lead/agent.md",
    )
    return agents_changed or claude_changed




# ---------------------------------------------------------------------------
# Migration helpers
# ---------------------------------------------------------------------------

def _migrate_claude(target: Path) -> dict:
    """Convert legacy direct-copy installs to symlinks (pre-install migration pass).

    Iterates over every expected alias path — one per bundled skill plus
    ``CLAUDE.md`` — and calls ``_links.migrate_to_symlink`` on each.
    Results are aggregated into a summary dict and printed via ``click.echo``.

    The skill canonicals are written to ``.agents/skills/<n>/SKILL.md`` before
    migration so that ``migrate_to_symlink`` can do the byte-for-byte content
    comparison.  ``AGENTS.md`` is written before comparing ``CLAUDE.md``.

    Parameters
    ----------
    target:
        Resolved path to the target project root.

    Returns
    -------
    dict
        ``{"migrated": int, "conflict": int, "skipped": int}`` counts.
    """
    from clasi.platforms._markers import write_section

    counts: dict = {"migrated": 0, "conflict": 0, "skipped": 0}

    if not _PLUGIN_DIR.exists():
        return counts

    # --- Skills ---
    plugin_skills = _PLUGIN_DIR / "skills"
    if plugin_skills.exists():
        from clasi.tools.process_tools import resolve_skill_body
        for skill_dir in sorted(plugin_skills.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_src = skill_dir / "SKILL.md"
            if not skill_src.exists():
                continue

            # Write canonical so migrate_to_symlink can compare bytes.
            # Resolve any Load from: directive so the installed file has the full prose.
            canonical = target / ".agents" / "skills" / skill_dir.name / "SKILL.md"
            canonical.parent.mkdir(parents=True, exist_ok=True)
            raw = skill_src.read_text(encoding="utf-8")
            resolved = resolve_skill_body(raw)
            if resolved != raw:
                canonical.write_text(resolved, encoding="utf-8")
            else:
                shutil.copy2(skill_src, canonical)

            alias = target / ".claude" / "skills" / skill_dir.name / "SKILL.md"
            result = _links.migrate_to_symlink(canonical, alias)

            alias_rel = f".claude/skills/{skill_dir.name}/SKILL.md"
            if result == "migrated":
                click.echo(f"  Migrated: {alias_rel} -> symlink")
                counts["migrated"] += 1
            elif result == "conflict":
                click.echo(
                    f"  Warning: {alias_rel} has different content — "
                    "skipping (investigate and resolve manually)"
                )
                counts["conflict"] += 1
            else:
                # "already-symlink" or "not-found" — silent skip
                counts["skipped"] += 1

    # --- CLAUDE.md ---
    agents_md = target / "AGENTS.md"
    claude_md = target / "CLAUDE.md"

    # Write AGENTS.md so we can compare against it.
    write_section(
        agents_md,
        entry_point=_CLAUDE_ENTRY_POINT,
        legacy_match_substr="team-lead/agent.md",
    )

    result = _links.migrate_to_symlink(agents_md, claude_md)
    if result == "migrated":
        click.echo("  Migrated: CLAUDE.md -> symlink")
        counts["migrated"] += 1
    elif result == "conflict":
        click.echo(
            "  Warning: CLAUDE.md has different content — "
            "skipping (investigate and resolve manually)"
        )
        counts["conflict"] += 1
    else:
        # "already-symlink" or "not-found" — silent skip
        counts["skipped"] += 1

    click.echo(
        f"Migration complete: {counts['migrated']} converted, "
        f"{counts['conflict']} conflicts, "
        f"{counts['skipped']} skipped."
    )
    return counts


# ---------------------------------------------------------------------------
# Plugin content helpers
# ---------------------------------------------------------------------------

def _install_plugin_content(
    target: Path,
    copy: bool = False,
    migrate: bool = False,
) -> None:
    """Copy skills, agents, and hooks from the plugin/ directory to .claude/.

    This is the project-local installation mode. Skills are unnamespaced.

    Skills are written canonically to ``.agents/skills/<n>/SKILL.md`` and
    aliased (symlink or copy) at ``.claude/skills/<n>/SKILL.md``.  When
    *migrate* is ``True``, an existing direct-copy alias is converted to a
    symlink before the standard alias step (no-op if already a symlink or if
    a conflict is detected — conflict is reported to stdout and the alias is
    left unchanged).
    """
    if not _PLUGIN_DIR.exists():
        click.echo("  Warning: plugin/ directory not found, skipping content install")
        return

    # Copy skills
    plugin_skills = _PLUGIN_DIR / "skills"
    if plugin_skills.exists():
        from clasi.tools.process_tools import resolve_skill_body
        click.echo("Skills:")
        for skill_dir in sorted(plugin_skills.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_src = skill_dir / "SKILL.md"
            if not skill_src.exists():
                continue

            # 1. Write canonical to .agents/skills/<n>/SKILL.md
            # Resolve any Load from: directive so the installed file has the full prose.
            canonical = target / ".agents" / "skills" / skill_dir.name / "SKILL.md"
            canonical.parent.mkdir(parents=True, exist_ok=True)
            raw = skill_src.read_text(encoding="utf-8")
            resolved = resolve_skill_body(raw)
            if resolved != raw:
                canonical.write_text(resolved, encoding="utf-8")
            else:
                shutil.copy2(skill_src, canonical)

            # 2. Create alias .claude/skills/<n>/SKILL.md
            alias = target / ".claude" / "skills" / skill_dir.name / "SKILL.md"

            # Handle --migrate: convert legacy copy to symlink before alias step
            if migrate and alias.exists():
                migrate_result = _links.migrate_to_symlink(canonical, alias)
                if migrate_result == "conflict":
                    click.echo(
                        f"  Conflict: .claude/skills/{skill_dir.name}/SKILL.md "
                        f"differs from canonical — skipping migrate"
                    )
                    # Leave the alias unchanged; skip the normal alias step
                    click.echo(f"  Canonical: .agents/skills/{skill_dir.name}/SKILL.md")
                    continue
                elif migrate_result == "migrated":
                    click.echo(f"  Migrated: .claude/skills/{skill_dir.name}/SKILL.md -> symlink")
                    click.echo(f"  Canonical: .agents/skills/{skill_dir.name}/SKILL.md")
                    continue
                # "already-symlink" or "not-found" — fall through to normal alias step

            # Remove stale alias if present so link_or_copy won't fail
            if alias.exists() or alias.is_symlink():
                alias.unlink()

            result = _links.link_or_copy(canonical, alias, copy=copy)
            verb = "Symlinked" if result == "symlink" else "Copied"
            click.echo(f"  {verb}: .claude/skills/{skill_dir.name}/SKILL.md")
            click.echo(f"  Canonical: .agents/skills/{skill_dir.name}/SKILL.md")
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

def install(
    target: Path,
    mcp_config: dict,
    copy: bool = False,
    migrate: bool = False,
) -> None:
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
        copy: If True, use file copy instead of symlink for alias operations.
            Passed through to ``_links.link_or_copy``.
        migrate: If True, run a dedicated migration pass before the standard
            install.  ``_migrate_claude`` iterates over all expected alias paths,
            calls ``_links.migrate_to_symlink`` on each, and prints a summary
            line.  The standard install then proceeds normally.
    """
    if migrate:
        click.echo("Migration pass:")
        _migrate_claude(target)
        click.echo()

    # Copy plugin content (skills, agents, hooks/settings.json).
    # When migrate=True the dedicated pass above already ran; pass migrate
    # through so _install_plugin_content still guards against overwriting
    # conflicting aliases that the migration pass left unchanged.
    _install_plugin_content(target, copy=copy, migrate=migrate)

    # Write AGENTS.md and create CLAUDE.md alias
    click.echo("CLAUDE.md / AGENTS.md:")
    _write_claude_md(target, copy=copy)
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

    # Drop a version stamp so it's obvious which clasi release wrote the contents.
    from clasi.platforms._markers import write_version_stamp
    click.echo("Version stamp:")
    write_version_stamp(target)
    click.echo()


def uninstall(target: Path, copy: bool = False) -> None:
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
        copy: If True, alias removal uses file-copy semantics.  Accepted for
            parity with ``clasi uninstall --copy``; wired to
            ``_links.unlink_alias`` in ticket 003/004.  Currently a no-op.
    """
    click.echo(f"Uninstalling Claude platform integration from {target}")
    click.echo()

    # --- CLAUDE.md (alias) ---
    _links.unlink_alias(target / "CLAUDE.md")
    click.echo("  Removed: CLAUDE.md (alias)")

    # --- AGENTS.md (canonical) ---
    # Strip the CLASI block only if Codex is NOT installed; if Codex is present
    # it owns the AGENTS.md block and will clean it up on its own uninstall.
    from clasi.platforms._markers import strip_section
    codex_installed = (target / ".codex").exists()
    if not codex_installed:
        strip_section(target / "AGENTS.md")

    # --- .claude/skills/ (alias only — canonical .agents/skills/ is preserved) ---
    skills_dir = target / ".claude" / "skills"
    if skills_dir.exists() and _PLUGIN_DIR.exists():
        plugin_skills = _PLUGIN_DIR / "skills"
        if plugin_skills.exists():
            for skill_dir in plugin_skills.iterdir():
                if not skill_dir.is_dir():
                    continue
                target_skill = skills_dir / skill_dir.name
                if not target_skill.exists():
                    continue
                alias = target_skill / "SKILL.md"
                _links.unlink_alias(alias)
                if not any(target_skill.iterdir()):
                    target_skill.rmdir()
                    click.echo(f"  Removed: .claude/skills/{skill_dir.name}/")
                else:
                    click.echo(
                        f"  Partial: .claude/skills/{skill_dir.name}/ "
                        f"(removed SKILL.md alias; user files preserved)"
                    )

    # --- .claude/agents/ ---
    agents_dir = target / ".claude" / "agents"
    if agents_dir.exists() and _PLUGIN_DIR.exists():
        plugin_agents = _PLUGIN_DIR / "agents"
        if plugin_agents.exists():
            for agent_dir in plugin_agents.iterdir():
                if not agent_dir.is_dir():
                    continue
                target_agent = agents_dir / agent_dir.name
                if not target_agent.exists():
                    continue
                # Install copies *.md from plugin/agents/<name>/ — mirror that.
                for plugin_md in agent_dir.glob("*.md"):
                    target_md = target_agent / plugin_md.name
                    if target_md.exists():
                        target_md.unlink()
                if not any(target_agent.iterdir()):
                    target_agent.rmdir()
                    click.echo(f"  Removed: .claude/agents/{agent_dir.name}/")
                else:
                    click.echo(
                        f"  Partial: .claude/agents/{agent_dir.name}/ "
                        f"(removed CLASI .md files; user files preserved)"
                    )

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

    # --- .clasi/clasi-version ---
    from clasi.platforms._markers import remove_version_stamp
    remove_version_stamp(target)

    click.echo()
    click.echo("Done! Claude platform integration removed.")
