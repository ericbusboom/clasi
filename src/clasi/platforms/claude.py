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

from clasi.platforms import _links, _manifest
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
        from clasi.skill_resolve import resolve_skill_body
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
# Hooks merge helpers
# ---------------------------------------------------------------------------

_CLASI_HOOK_COMMAND_PREFIX = "clasi hook"


def _is_clasi_hook_entry(entry: dict) -> bool:
    """Return True if every hook command in *entry* is CLASI-owned.

    *entry* is a single matcher-group dict from a hooks.json event list —
    ``{"matcher": ..., "hooks": [{"type": "command", "command": ...}, ...]}``.
    It is identified as CLASI's own only if every command in its "hooks"
    list starts with ``"clasi hook"``, the CLI convention every CLASI hook
    registration uses. An entry with no hooks, or with any non-CLASI
    command mixed in, is treated as user-owned and left alone.
    """
    hook_list = entry.get("hooks", [])
    if not hook_list:
        return False
    return all(
        str(h.get("command", "")).startswith(_CLASI_HOOK_COMMAND_PREFIX)
        for h in hook_list
    )


def _merge_hooks(existing_hooks: dict, new_hooks: dict) -> tuple[dict, bool]:
    """Merge CLASI's hook registrations into *existing_hooks*, per event type.

    For each event type CLASI defines (a key in *new_hooks*): existing
    entries identified as CLASI's own (:func:`_is_clasi_hook_entry`) are
    dropped, and the current plugin entries for that event are appended in
    their place — this is the "replace only CLASI's own entries" half.
    Any existing entry NOT identified as CLASI's — a user-defined hook,
    however it's shaped — is kept in the list untouched. Event types that
    CLASI does not define are not touched at all, even if *existing_hooks*
    has entries under them.

    Returns ``(merged_hooks, changed)``, where *changed* is True if the
    merge result differs from *existing_hooks* for any touched event type.
    """
    merged = dict(existing_hooks)
    changed = False
    for event_type, clasi_entries in new_hooks.items():
        existing_entries = existing_hooks.get(event_type, [])
        kept = [e for e in existing_entries if not _is_clasi_hook_entry(e)]
        merged_entries = kept + clasi_entries
        if existing_hooks.get(event_type) != merged_entries:
            changed = True
        merged[event_type] = merged_entries
    return merged, changed


# ---------------------------------------------------------------------------
# Plugin content helpers
# ---------------------------------------------------------------------------

def _install_plugin_content(
    target: Path,
    copy: bool = False,
    migrate: bool = False,
) -> list:
    """Copy skills, agents, and hooks from the plugin/ directory to .claude/.

    This is the project-local installation mode. Skills are unnamespaced.

    Skills are written canonically to ``.agents/skills/<n>/SKILL.md`` and
    aliased (symlink or copy) at ``.claude/skills/<n>/SKILL.md``.  When
    *migrate* is ``True``, an existing direct-copy alias is converted to a
    symlink before the standard alias step (no-op if already a symlink or if
    a conflict is detected — conflict is reported to stdout and the alias is
    left unchanged).

    Returns the list of manifest entries (``{"path": ..., "kind": ...}``)
    for every skill alias and agent file actually written or already owned
    by this install (sprint 033 — see ``_manifest.py``). Hook merging is
    NOT manifest-tracked: `uninstall()` reverses hook entries via the
    shared `_is_clasi_hook_entry` predicate instead (see that function's
    docstring for why the two mechanisms are kept separate).
    """
    entries: list = []

    if not _PLUGIN_DIR.exists():
        click.echo("  Warning: plugin/ directory not found, skipping content install")
        return entries

    # Copy skills
    plugin_skills = _PLUGIN_DIR / "skills"
    if plugin_skills.exists():
        from clasi.skill_resolve import resolve_skill_body
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
            alias_rel = f".claude/skills/{skill_dir.name}/SKILL.md"

            # Handle --migrate: convert legacy copy to symlink before alias step
            if migrate and alias.exists():
                migrate_result = _links.migrate_to_symlink(canonical, alias)
                if migrate_result == "conflict":
                    click.echo(
                        f"  Conflict: {alias_rel} "
                        f"differs from canonical — skipping migrate"
                    )
                    # Leave the alias unchanged; skip the normal alias step.
                    # Still recorded in the manifest (the path exists and is
                    # part of this install's file set, same as pre-033 —
                    # reconciliation must not treat "left alone on conflict"
                    # as "orphaned by a rename" and delete it).
                    click.echo(f"  Canonical: .agents/skills/{skill_dir.name}/SKILL.md")
                    entries.append({"path": alias_rel, "kind": "skill-alias"})
                    continue
                elif migrate_result == "migrated":
                    click.echo(f"  Migrated: {alias_rel} -> symlink")
                    click.echo(f"  Canonical: .agents/skills/{skill_dir.name}/SKILL.md")
                    entries.append({"path": alias_rel, "kind": "skill-alias"})
                    continue
                # "already-symlink" or "not-found" — fall through to normal alias step

            # Remove stale alias if present so link_or_copy won't fail
            if alias.exists() or alias.is_symlink():
                alias.unlink()

            result = _links.link_or_copy(canonical, alias, copy=copy)
            verb = "Symlinked" if result == "symlink" else "Copied"
            click.echo(f"  {verb}: {alias_rel}")
            click.echo(f"  Canonical: .agents/skills/{skill_dir.name}/SKILL.md")
            entries.append({"path": alias_rel, "kind": "skill-alias"})
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
                entries.append({"path": rel, "kind": "agent-file"})
        click.echo()

    # Merge hooks from plugin hooks.json into .claude/settings.json.
    # Per-event-type merge, not a wholesale replace: only entries
    # identifiable as CLASI's own are added/replaced; any other entry
    # under the same event key (a user-defined hook) is left in place.
    # See _merge_hooks.
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
        existing_hooks = settings.get("hooks", {})
        merged_hooks, changed = _merge_hooks(existing_hooks, new_hooks)
        if not changed:
            click.echo("  Unchanged: .claude/settings.json (hooks)")
        else:
            settings["hooks"] = merged_hooks
            settings_path.write_text(
                json.dumps(settings, indent=2) + "\n", encoding="utf-8"
            )
            click.echo("  Updated: .claude/settings.json (hooks)")
        click.echo()

    return entries


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
        if path.exists():
            try:
                existing = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                existing = None
        else:
            existing = None

        if existing == content:
            click.echo(f"  Unchanged: {rel}")
            continue

        path.write_text(content, encoding="utf-8")
        click.echo(f"  Wrote: {rel}")
        changed = True

    return changed


# ---------------------------------------------------------------------------
# Manifest replay helpers (sprint 033)
# ---------------------------------------------------------------------------
#
# `install()` records every skill alias, agent file, rule file, CLAUDE.md/
# AGENTS.md marker block, and settings.local.json permission entry it
# writes into a flat manifest (`_manifest.py`, `.claude/.clasi-manifest.json`).
# `_reverse_manifest_entry` is the single place that knows how to undo one
# such entry — it is used both by `install()`'s own reconciliation step
# (deleting paths a *previous* manifest recorded that this install no
# longer owns — e.g. a skill renamed since the last install) and by
# `uninstall()`'s manifest replay. Keeping one function for both call
# sites is what keeps "how install wrote it" and "how uninstall reverses
# it" from drifting apart, the same reason `_is_clasi_hook_entry` is
# shared between `_merge_hooks` and `uninstall()`'s hooks step below.
#
# Hook entries and the `.clasi/clasi-version` stamp are deliberately NOT
# manifest-tracked: hooks have their own symmetric predicate
# (`_is_clasi_hook_entry`) and the version stamp is a single well-known
# path unconditionally written/removed by `_markers.write_version_stamp`/
# `remove_version_stamp`. Neither needs manifest replay to stay correct.


def _reverse_manifest_entry(
    target: Path,
    entry: dict,
    codex_installed: bool = False,
) -> None:
    """Undo one manifest entry, the way `install()` wrote it.

    ``entry["kind"]`` selects the reversal:

    - ``"skill-alias"``, ``"agent-file"``, ``"rule-file"``: the path is a
      plain written file (symlink, copy, or rendered text) — unlink it.
      A missing file is not an error (already gone, or never created).
    - ``"marker-block"``: strip just the CLASI-managed section from the
      file via ``strip_section``, preserving any other content in it
      (e.g. another tool's block, or user prose). ``AGENTS.md`` is left
      untouched when *codex_installed* is True — Codex owns that file's
      block lifecycle in that case, matching `uninstall()`'s pre-033
      behavior for the non-manifest fallback path.
    - ``"permission"``: remove ``entry["value"]`` from the
      ``permissions.allow`` list in ``.claude/settings.local.json``, if
      present.

    An unrecognized ``kind`` is skipped with a warning rather than
    raising — this keeps a manifest written by a future `clasi` version
    (with a `kind` this version doesn't know about) from breaking
    uninstall for every other entry in the same manifest.
    """
    from clasi.platforms._markers import strip_section

    kind = entry.get("kind")
    path_rel = entry.get("path")
    if not path_rel:
        return
    full_path = target / path_rel

    if kind in ("skill-alias", "agent-file", "rule-file"):
        if _links.unlink_alias(full_path):
            click.echo(f"  Removed: {path_rel}")

    elif kind == "marker-block":
        if path_rel == "AGENTS.md" and codex_installed:
            click.echo(f"  Skipped: {path_rel} (Codex present; block preserved)")
            return
        strip_section(full_path)

    elif kind == "permission":
        if not full_path.exists():
            return
        try:
            data = json.loads(full_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            return
        allow = data.get("permissions", {}).get("allow", [])
        value = entry.get("value", "mcp__clasi__*")
        if value in allow:
            allow.remove(value)
            full_path.write_text(
                json.dumps(data, indent=2) + "\n", encoding="utf-8"
            )
            click.echo(f"  Updated: {path_rel} (removed {value})")
        else:
            click.echo(f"  Unchanged: {path_rel} (permission not found)")

    else:
        click.echo(
            f"  Warning: unrecognized manifest entry kind {kind!r} for "
            f"{path_rel}; skipping"
        )


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
    - Reconcile against, then overwrite, the install manifest
      (``.claude/.clasi-manifest.json`` — sprint 033)

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
    # Skill-alias and agent-file manifest entries come back from here —
    # everything else this install writes is appended below as it happens.
    entries = _install_plugin_content(target, copy=copy, migrate=migrate)

    # Write AGENTS.md and create CLAUDE.md alias
    click.echo("CLAUDE.md / AGENTS.md:")
    _write_claude_md(target, copy=copy)
    click.echo()
    entries.append({"path": "CLAUDE.md", "kind": "marker-block"})
    entries.append({"path": "AGENTS.md", "kind": "marker-block"})

    # Add MCP permission to .claude/settings.local.json
    click.echo("MCP permissions:")
    settings_local = target / ".claude" / "settings.local.json"
    _update_settings_json(settings_local)
    click.echo()
    entries.append({
        "path": ".claude/settings.local.json",
        "kind": "permission",
        "value": "mcp__clasi__*",
    })

    # Install path-scoped rules in .claude/rules/
    click.echo("Path-scoped rules:")
    _create_rules(target)
    click.echo()
    for filename in RULES:
        entries.append({"path": f".claude/rules/{filename}", "kind": "rule-file"})

    # Drop a version stamp so it's obvious which clasi release wrote the contents.
    # Not manifest-tracked (see the "Manifest replay helpers" section above).
    from clasi.platforms._markers import write_version_stamp
    click.echo("Version stamp:")
    write_version_stamp(target)
    click.echo()

    # --- Manifest reconciliation + write (sprint 033; last step) ---
    # The full `entries` list above is now complete — only now is it safe
    # to diff against the previous manifest. Diffing earlier, before every
    # write site had appended its entry, would wrongly flag an
    # already-written file as "stale" before its own entry existed yet.
    platform_dir = target / ".claude"
    try:
        previous_manifest = _manifest.read_manifest(platform_dir)
    except (json.JSONDecodeError, ValueError, OSError):
        previous_manifest = None

    if previous_manifest:
        old_entries = previous_manifest.get("entries", [])
        old_by_path = {e["path"]: e for e in old_entries if e.get("path")}
        new_paths = {e["path"] for e in entries}
        stale_paths = set(old_by_path) - new_paths
        if stale_paths:
            click.echo(
                "Manifest reconciliation (removing entries from a previous "
                "install no longer part of this one):"
            )
            for rel in sorted(stale_paths):
                _reverse_manifest_entry(target, old_by_path[rel])
            click.echo()

    click.echo("Manifest:")
    _manifest.write_manifest(platform_dir, {"version": 1, "entries": entries})
    click.echo("  Wrote: .claude/.clasi-manifest.json")
    click.echo()


def uninstall(target: Path, copy: bool = False) -> None:
    """Remove the Claude platform integration from *target*.

    Sprint 033: the source of truth for "what to remove" is now the
    install manifest (``.claude/.clasi-manifest.json``, written by
    ``install()``), read *before any file is touched*. When present, its
    entries are replayed exactly — this closes review finding F14: a
    file written by an older, differently-named `clasi` is no longer
    orphaned, because the manifest recorded the path actually written
    rather than requiring uninstall to re-derive "what should be there"
    from the currently-installed package's current name list.

    When the manifest is absent, or fails to parse (corrupt JSON — either
    case reads the same as "no manifest"), uninstall falls back to the
    pre-033 name-based enumeration, unchanged: an install that predates
    sprint 033 has no manifest, and must still uninstall cleanly.

    Either path also (not manifest-tracked, so always runs regardless of
    which branch above ran):
    - Removes CLASI hook entries from .claude/settings.json (leaves other
      hooks and keys intact) via the same per-entry ``_is_clasi_hook_entry``
      predicate ``install()``'s ``_merge_hooks`` uses — the two must agree
      on what "a CLASI hook entry" is, or they drift apart the moment a
      user hook can coexist with CLASI's own under one event key (sprint
      032 made that possible; see ``_is_clasi_hook_entry``'s docstring).
    - Removes the ``.clasi/clasi-version`` stamp.

    This function is non-destructive toward user-added files: only
    CLASI-owned paths (manifest entries, or — in the fallback — CLASI-owned
    names) are touched.

    Args:
        target: Resolved Path to the target project root.
        copy: If True, alias removal uses file-copy semantics.  Accepted for
            parity with ``clasi uninstall --copy``; wired to
            ``_links.unlink_alias`` for the skill-alias removal path below.
            Currently a no-op there too (removal doesn't depend on how the
            alias was created). Not used by the CLAUDE.md path, which uses
            ``strip_section`` regardless of *copy* since CLAUDE.md is a
            regular file, never a symlink alias.
    """
    click.echo(f"Uninstalling Claude platform integration from {target}")
    click.echo()

    from clasi.platforms._markers import strip_section

    codex_installed = (target / ".codex").exists()

    # --- Manifest read (first, before touching any file) ---
    # A read failure (corrupt JSON) is caught here so it is discovered
    # before any deletion begins, not mid-removal — see platforms-DESIGN.md.
    platform_dir = target / ".claude"
    try:
        manifest_data = _manifest.read_manifest(platform_dir)
    except (json.JSONDecodeError, ValueError, OSError):
        manifest_data = None

    if manifest_data is not None and isinstance(manifest_data.get("entries"), list):
        # --- Manifest-driven removal (sprint 033) ---
        click.echo("Manifest found — replaying recorded install entries:")
        manifest_entries = manifest_data["entries"]
        for entry in manifest_entries:
            _reverse_manifest_entry(target, entry, codex_installed=codex_installed)

        # Best-effort cleanup of now-empty per-skill/per-agent directories
        # (mirrors the pre-033 fallback's tidiness below; a directory that
        # still holds a user file — e.g. notes.md dropped next to
        # SKILL.md — is left alone since it won't be empty).
        cleanup_dirs = {
            (target / e["path"]).parent
            for e in manifest_entries
            if e.get("kind") in ("skill-alias", "agent-file") and e.get("path")
        }
        for d in sorted(cleanup_dirs, key=lambda p: -len(p.parts)):
            try:
                if d.is_dir() and not any(d.iterdir()):
                    d.rmdir()
            except OSError:
                pass

        _manifest.delete_manifest(platform_dir)
        click.echo("  Removed: .claude/.clasi-manifest.json")
        click.echo()
    else:
        # --- Pre-033 fallback: name-based enumeration (unchanged) ---
        click.echo("No manifest found — falling back to name-based removal:")

        # --- CLAUDE.md (regular file holding the CLASI marker block) ---
        # CLAUDE.md is written via the marker-block writer (_write_claude_md)
        # specifically so other tools can manage their own blocks in the same
        # file. Uninstall must strip only CLASI's block, not delete the whole
        # file — `_links.unlink_alias` would destroy any other-tool content
        # sharing the file (ticket 032/004). Deletes the file only if the
        # CLASI block was its only content, matching AGENTS.md below.
        strip_section(target / "CLAUDE.md")

        # --- AGENTS.md (canonical) ---
        # Strip the CLASI block only if Codex is NOT installed; if Codex is
        # present it owns the AGENTS.md block and will clean it up on its
        # own uninstall.
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

    # --- .claude/settings.json hooks (not manifest-tracked; always runs) ---
    # Fix B (uninstall-hook-removal-uses-exact-match.md): removes CLASI's
    # own entries per-entry via `_is_clasi_hook_entry`, the same predicate
    # `_merge_hooks` uses on install, instead of comparing an entire event
    # type's entry list for exact equality — the exact-match form silently
    # stopped matching, and so stopped removing anything, the moment a user
    # hook could legitimately coexist under the same event key (sprint
    # 032/004's per-event install merge made that possible for the first
    # time).
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
            for event_type in clasi_hooks:
                if event_type not in current_hooks:
                    continue
                existing_entries = current_hooks[event_type]
                kept = [e for e in existing_entries if not _is_clasi_hook_entry(e)]
                if kept != existing_entries:
                    changed = True
                if kept:
                    current_hooks[event_type] = kept
                else:
                    del current_hooks[event_type]
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

    # --- .clasi/clasi-version (not manifest-tracked; always runs) ---
    from clasi.platforms._markers import remove_version_stamp
    remove_version_stamp(target)

    click.echo()
    click.echo("Done! Claude platform integration removed.")
