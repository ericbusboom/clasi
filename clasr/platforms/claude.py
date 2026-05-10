"""
clasr/platforms/claude.py

Claude platform installer.

Given an ``asr/`` source directory, installs CLASI-rendered content into
``.claude/`` in the target directory, writes named marker blocks into
``AGENTS.md`` and ``CLAUDE.md``, and records everything in a manifest.

Public API:
    ClaudeIntegration — use via INTEGRATION_REGISTRY or instantiate directly.

Source layout expected:
    <source>/skills/<n>/SKILL.md  — installed as symlinks/copies
    <source>/agents/<n>.md        — rendered with platform="claude"
    <source>/rules/<n>.md         — rendered with platform="claude"
    <source>/claude/**            — passthrough to .claude/
    <source>/AGENTS.md            — written as named marker block

No imports from clasi.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

import clasr.frontmatter as frontmatter
import clasr.links as links
import clasr.manifest as manifest
import clasr.markers as markers
import clasr.merge as merge
from clasr.integration import (
    ManifestEntry,
    MarkdownIntegration,
    SkillsIntegration,
    write_marker_blocks,
)


def _discover_other_provider(claude_dir: Path, path_rel: str) -> str | None:
    """Return the name of any other provider that owns *path_rel*, or None.

    Scans all manifests in ``<claude_dir>/.clasr-manifest/`` looking for an
    entry with this relative path.  Returns the first provider name found, or
    ``None`` if no manifest claims it.
    """
    manifest_dir = claude_dir / ".clasr-manifest"
    if not manifest_dir.is_dir():
        return None
    for mf in manifest_dir.glob("*.json"):
        try:
            data = json.loads(mf.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for entry in data.get("entries", []):
            if entry.get("path") == path_rel:
                return mf.stem  # stem = provider name
    return None


def _cleanup_empty_dirs(target: Path) -> None:
    """Remove empty directories that clasr may have created under *target*.

    Tries to remove (in order, deepest first): skill subdirs, then
    .claude/skills, .claude/agents, .claude/rules, and .claude itself.
    Only removes directories that are truly empty.
    """
    claude_dir = target / ".claude"

    candidates: list[Path] = []

    # Collect skill subdirectories.
    skills_dir = claude_dir / "skills"
    if skills_dir.is_dir():
        for child in skills_dir.iterdir():
            if child.is_dir():
                candidates.append(child)

    # Standard subdirectories.
    for name in ("skills", "agents", "rules"):
        candidates.append(claude_dir / name)

    # The manifest dir itself.
    candidates.append(claude_dir / ".clasr-manifest")

    # The .claude dir last.
    candidates.append(claude_dir)

    for d in candidates:
        try:
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()
        except OSError:
            pass


# ---------------------------------------------------------------------------
# ClaudeIntegration
# ---------------------------------------------------------------------------


class ClaudeIntegration(MarkdownIntegration, SkillsIntegration):
    """Claude Code platform integration.

    Subclasses :class:`~clasr.integration.MarkdownIntegration` (for
    YAML-frontmatter ``.md`` agent files) and
    :class:`~clasr.integration.SkillsIntegration` (for SKILL.md symlinks/copies).

    Installs into ``.claude/`` within the project root, writes marker blocks
    into ``AGENTS.md`` and ``CLAUDE.md``, and handles JSON passthrough merging
    for ``settings.json``.
    """

    # --- Class-level field declarations ---

    id = "claude"
    display_name = "Claude Code"
    detect_files = [".claude/.clasr-manifest"]
    target_root = Path(".claude")
    skill_dir = Path(".claude/skills")
    agent_dir = Path(".claude/agents")
    rule_dir = Path(".claude/rules")
    command_dir = None
    settings_file = Path(".claude/settings.json")
    command_format = "md"
    frontmatter_dialect = "yaml"
    invoke_separator = "/"
    companion_files = ["AGENTS.md", "CLAUDE.md"]

    # --- render_agent ---

    def render_agent(
        self,
        source: Path,
        target_dir: Path,
        provider: str,
    ) -> list[ManifestEntry]:
        """Render ``.md`` agent files from *source* into *target_dir*.

        Walks *source* recursively for ``**/*.md`` files, renders each with
        :func:`clasr.frontmatter.render_file` using the ``claude`` platform key,
        and writes to ``target_dir / rel`` preserving relative sub-paths.

        Manifest paths are recorded as ``.claude/agents/{rel}``.
        """
        entries: list[ManifestEntry] = []
        for agent_file in sorted(source.glob("**/*.md")):
            rel = agent_file.relative_to(source)
            dest = target_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            rendered = frontmatter.render_file(agent_file, self.id)
            dest.write_text(rendered, encoding="utf-8")
            entries.append({
                "path": f".claude/agents/{rel}",
                "kind": "rendered",
                "from": str(agent_file.resolve()),
            })
        return entries

    # --- render_rule ---

    def render_rule(
        self,
        source: Path,
        target_dir: Path,
        provider: str,
    ) -> list[ManifestEntry]:
        """Render ``.md`` rule files from *source* into *target_dir*.

        Walks *source* recursively for ``**/*.md`` files, renders each with
        :func:`clasr.frontmatter.render_file` using the ``claude`` platform key,
        and writes to ``target_dir / rel`` preserving relative sub-paths.

        Manifest paths are recorded as ``.claude/rules/{rel}``.
        """
        entries: list[ManifestEntry] = []
        for rule_file in sorted(source.glob("**/*.md")):
            rel = rule_file.relative_to(source)
            dest = target_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            rendered = frontmatter.render_file(rule_file, self.id)
            dest.write_text(rendered, encoding="utf-8")
            entries.append({
                "path": f".claude/rules/{rel}",
                "kind": "rendered",
                "from": str(rule_file.resolve()),
            })
        return entries

    # --- render_skill ---

    def render_skill(
        self,
        source: Path,
        target_dir: Path,
        provider: str,
        copy: bool,
    ) -> list[ManifestEntry]:
        """Symlink or copy each ``SKILL.md`` from *source* into *target_dir*.

        Manifest paths are recorded as ``.claude/skills/{skill_name}/SKILL.md``.
        """
        entries: list[ManifestEntry] = []
        for skill_file in sorted(source.glob("*/SKILL.md")):
            skill_name = skill_file.parent.name
            alias = target_dir / "skills" / skill_name / "SKILL.md"
            alias.parent.mkdir(parents=True, exist_ok=True)
            kind = links.link_or_copy(skill_file.resolve(), alias, copy=copy)
            entries.append({
                "path": f".claude/skills/{skill_name}/SKILL.md",
                "kind": kind,
                "target": str(skill_file.resolve()),
            })
        return entries

    # --- install ---

    def install(
        self,
        source: Path,
        target: Path,
        provider: str,
        copy: bool = False,
    ) -> None:
        """Install the Claude platform from *source* into *target*.

        Parameters
        ----------
        source:
            Path to the ``asr/`` source directory.
        target:
            The project root where ``.claude/`` will be created.
        provider:
            Name of the provider (e.g. ``"myprovider"``).  Used for manifest
            naming and marker-block identification.
        copy:
            If ``True``, copy skills files instead of symlinking.
        """
        claude_dir = target / ".claude"
        entries: list[ManifestEntry] = []

        # ------------------------------------------------------------------
        # 1. Skills: source/skills/<n>/SKILL.md → .claude/skills/<n>/SKILL.md
        # ------------------------------------------------------------------
        skills_src = source / "skills"
        if skills_src.is_dir():
            claude_dir.mkdir(parents=True, exist_ok=True)
            entries.extend(self.render_skill(skills_src, claude_dir, provider, copy))

        # ------------------------------------------------------------------
        # 2. Agents: render source/agents/<n>.md → .claude/agents/<n>.md
        # ------------------------------------------------------------------
        agents_src = source / "agents"
        if agents_src.is_dir():
            agents_dest = claude_dir / "agents"
            agents_dest.mkdir(parents=True, exist_ok=True)
            entries.extend(self.render_agent(agents_src, agents_dest, provider))

        # ------------------------------------------------------------------
        # 3. Rules: render source/rules/<n>.md → .claude/rules/<n>.md
        # ------------------------------------------------------------------
        rules_src = source / "rules"
        if rules_src.is_dir():
            rules_dest = claude_dir / "rules"
            rules_dest.mkdir(parents=True, exist_ok=True)
            entries.extend(self.render_rule(rules_src, rules_dest, provider))

        # ------------------------------------------------------------------
        # 4. Passthrough: source/claude/** → .claude/
        # ------------------------------------------------------------------
        # Read the existing manifest for this provider so we know what paths we
        # previously installed (those are ours to overwrite without conflict).
        existing_manifest = manifest.read_manifest(claude_dir, provider)
        own_paths: set[str] = set()
        if existing_manifest:
            for entry in existing_manifest.get("entries", []):
                own_paths.add(entry["path"])

        claude_passthrough_src = source / "claude"
        if claude_passthrough_src.is_dir():
            for src_file in sorted(claude_passthrough_src.rglob("*")):
                if not src_file.is_file():
                    continue
                rel = src_file.relative_to(claude_passthrough_src)
                dest = claude_dir / rel
                rel_str = f".claude/{rel}"

                dest.parent.mkdir(parents=True, exist_ok=True)
                incoming = json.loads(src_file.read_text(encoding="utf-8")) if merge.is_json_passthrough(src_file) else None

                if merge.is_json_passthrough(src_file):
                    if dest.exists():
                        # Find who owns it (for the warning message).
                        other_prov = _discover_other_provider(claude_dir, rel_str) or "another provider"
                        merged_dict, diff = merge.merge_json_files(
                            dest, incoming, provider, other_prov
                        )
                        dest.write_text(json.dumps(merged_dict, indent=2), encoding="utf-8")
                        entries.append({
                            "path": rel_str,
                            "kind": "json-merged",
                            "keys": list(diff.keys()),
                            "contributed": diff,
                        })
                    else:
                        # No existing file — plain write (nothing to merge).
                        dest.write_text(json.dumps(incoming, indent=2), encoding="utf-8")
                        entries.append({
                            "path": rel_str,
                            "kind": "copy",
                            "from": str(src_file.resolve()),
                        })
                else:
                    # Non-JSON passthrough
                    if dest.exists() and rel_str not in own_paths:
                        other_prov = _discover_other_provider(claude_dir, rel_str) or "another provider"
                        raise RuntimeError(
                            f"clasr: install conflict: '{rel_str}' already exists and "
                            f"is owned by '{other_prov}', not by provider '{provider}'. "
                            "Remove or uninstall the other provider first."
                        )
                    shutil.copy2(src_file, dest)
                    entries.append({
                        "path": rel_str,
                        "kind": "copy",
                        "from": str(src_file.resolve()),
                    })

        # ------------------------------------------------------------------
        # 5. Marker blocks: source/AGENTS.md → AGENTS.md + CLAUDE.md
        # ------------------------------------------------------------------
        agents_md_src = source / "AGENTS.md"
        if agents_md_src.exists():
            content = agents_md_src.read_text(encoding="utf-8")
            entries.extend(write_marker_blocks(target, provider, content, self.companion_files))

        # ------------------------------------------------------------------
        # 6. Write manifest (last — atomic)
        # ------------------------------------------------------------------
        manifest_data = {
            "version": 1,
            "provider": provider,
            "platform": "claude",
            "source": str(source.resolve()),
            "entries": entries,
        }
        manifest.write_manifest(claude_dir, provider, manifest_data)

    # --- uninstall ---

    def uninstall(self, target: Path, provider: str) -> None:
        """Uninstall the Claude platform for *provider* from *target*.

        Reads the manifest at ``.claude/.clasr-manifest/<provider>.json`` and
        reverses each installation entry.  If the manifest does not exist,
        returns silently (idempotent).

        Parameters
        ----------
        target:
            The project root (same ``target`` passed to :meth:`install`).
        provider:
            Provider name whose installation should be removed.
        """
        claude_dir = target / ".claude"
        mf = manifest.read_manifest(claude_dir, provider)
        if mf is None:
            # No manifest — nothing to do (idempotent).
            return

        for entry in mf.get("entries", []):
            kind = entry["kind"]
            path_rel = entry["path"]

            # Reconstruct the full path.  Marker-block entries for AGENTS.md /
            # CLAUDE.md live directly in target (no .claude/ prefix).
            if path_rel.startswith(".claude/") or path_rel.startswith(".claude\\"):
                full_path = target / path_rel
            else:
                full_path = target / path_rel

            if kind in ("symlink", "copy"):
                links.unlink_alias(full_path)

            elif kind == "rendered":
                full_path.unlink(missing_ok=True)

            elif kind == "marker-block":
                markers.strip_block(full_path, provider)

            elif kind == "json-merged":
                if full_path.exists():
                    try:
                        data = json.loads(full_path.read_text(encoding="utf-8"))
                    except (OSError, json.JSONDecodeError):
                        data = {}
                    contributed = entry.get("contributed")
                    if contributed is not None:
                        # New format: reverse the deep-diff precisely.
                        data = merge.reverse_diff(data, contributed)
                    else:
                        # Old format fallback: top-level key removal.
                        print(
                            f"WARNING: clasr: manifest entry for '{path_rel}' uses old format "
                            f"(no 'contributed' field); falling back to top-level key removal. "
                            f"Reinstall '{provider}' to upgrade the manifest.",
                            file=sys.stderr,
                        )
                        for k in entry.get("keys", []):
                            data.pop(k, None)
                    if data:
                        full_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
                    else:
                        full_path.unlink(missing_ok=True)

        # Delete the manifest file.
        manifest.delete_manifest(claude_dir, provider)

        # Best-effort cleanup of empty parent directories.
        _cleanup_empty_dirs(target)


