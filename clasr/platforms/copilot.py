"""
clasr/platforms/copilot.py

GitHub Copilot platform installer.

Given an ``asr/`` source directory, installs CLASI-rendered content into
``.github/`` in the target directory, writes a named marker block into
``.github/copilot-instructions.md``, and records everything in a manifest.

Public API:
    install(source: Path, target: Path, provider: str, copy: bool = False) -> None
    uninstall(target: Path, provider: str) -> None

Source layout expected:
    <source>/skills/<n>/SKILL.md  — installed under .agents/skills/; .github/skills/
                                     symlinked (or copied) to .agents/skills/
    <source>/agents/<n>.md        — rendered with platform="copilot" → .github/agents/<n>.agent.md
    <source>/rules/<n>.md         — rendered with platform="copilot" → .github/instructions/<n>.instructions.md
    <source>/copilot/**           — passthrough to .github/
    <source>/AGENTS.md            — written as named marker block into .github/copilot-instructions.md ONLY

No imports from clasi.
"""

from __future__ import annotations

import json
import os
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
)


def _discover_other_provider(github_dir: Path, path_rel: str) -> str | None:
    """Return the name of any other provider that owns *path_rel*, or None.

    Scans all manifests in ``<github_dir>/.clasr-manifest/`` looking for an
    entry with this relative path.  Returns the first provider name found, or
    ``None`` if no manifest claims it.
    """
    manifest_dir = github_dir / ".clasr-manifest"
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

    Tries to remove (in order, deepest first): skill subdirs under .agents/skills,
    then .agents/skills, .agents, .github/agents, .github/instructions,
    .github/.clasr-manifest, and .github itself.
    Only removes directories that are truly empty.
    """
    github_dir = target / ".github"
    agents_dir = target / ".agents"

    candidates: list[Path] = []

    # Collect skill subdirectories under .agents/skills.
    skills_dir = agents_dir / "skills"
    if skills_dir.is_dir():
        for child in skills_dir.iterdir():
            if child.is_dir():
                candidates.append(child)

    # .agents subdirectories.
    candidates.append(skills_dir)
    candidates.append(agents_dir)

    # .github subdirectories.
    for name in ("agents", "instructions"):
        candidates.append(github_dir / name)

    # The manifest dir itself.
    candidates.append(github_dir / ".clasr-manifest")

    # The .github dir last.
    candidates.append(github_dir)

    for d in candidates:
        try:
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()
        except OSError:
            pass


# ---------------------------------------------------------------------------
# CopilotIntegration
# ---------------------------------------------------------------------------


class CopilotIntegration(MarkdownIntegration, SkillsIntegration):
    """GitHub Copilot platform integration.

    Subclasses :class:`~clasr.integration.MarkdownIntegration` (for
    YAML-frontmatter ``.md`` agent files) and
    :class:`~clasr.integration.SkillsIntegration` (for SKILL.md symlinks/copies).

    Installs into ``.github/`` within the project root, writes a marker block
    into ``.github/copilot-instructions.md``, and creates a directory-level
    ``.github/skills/`` symlink (or copy) to ``.agents/skills/``.

    Agent files are rendered with an ``.agent.md`` suffix (not plain ``.md``).
    Rule files are rendered with an ``.instructions.md`` suffix.
    """

    # --- Class-level field declarations ---

    id = "copilot"
    display_name = "GitHub Copilot"
    detect_files = [".github/.clasr-manifest"]
    target_root = Path(".github")
    skill_dir = Path(".agents/skills")
    agent_dir = Path(".github/agents")
    rule_dir = Path(".github/instructions")
    command_dir = None
    settings_file = None
    command_format = "md"
    frontmatter_dialect = "yaml"
    invoke_separator = "/"
    companion_files = [".github/copilot-instructions.md"]

    # --- render_agent ---

    def render_agent(
        self,
        source: Path,
        target_dir: Path,
        provider: str,
    ) -> list[ManifestEntry]:
        """Render ``.md`` agent files from *source* into *target_dir*.

        Walks *source* recursively for ``**/*.md`` files, renders each with
        :func:`clasr.frontmatter.render_file` using the ``copilot`` platform key,
        and writes to ``target_dir / <stem>.agent.md`` (appending ``.agent.md``
        instead of preserving the original ``.md`` extension).

        Manifest paths are recorded as ``.github/agents/{stem}.agent.md``.
        """
        entries: list[ManifestEntry] = []
        for agent_file in sorted(source.glob("**/*.md")):
            rel = agent_file.relative_to(source)
            # Append .agent.md suffix (replace .md with .agent.md)
            dest_name = rel.stem + ".agent.md"
            dest = target_dir / rel.parent / dest_name
            dest.parent.mkdir(parents=True, exist_ok=True)
            rendered = frontmatter.render_file(agent_file, self.id)
            dest.write_text(rendered, encoding="utf-8")
            dest_rel = (
                f".github/agents/{rel.parent / dest_name}"
                if str(rel.parent) != "."
                else f".github/agents/{dest_name}"
            )
            entries.append({
                "path": dest_rel,
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
        :func:`clasr.frontmatter.render_file` using the ``copilot`` platform key,
        and writes to ``target_dir / <stem>.instructions.md`` (appending
        ``.instructions.md`` instead of preserving the original ``.md`` extension).

        Manifest paths are recorded as ``.github/instructions/{stem}.instructions.md``.
        """
        entries: list[ManifestEntry] = []
        for rule_file in sorted(source.glob("**/*.md")):
            rel = rule_file.relative_to(source)
            # Append .instructions.md suffix
            dest_name = rel.stem + ".instructions.md"
            dest = target_dir / rel.parent / dest_name
            dest.parent.mkdir(parents=True, exist_ok=True)
            rendered = frontmatter.render_file(rule_file, self.id)
            dest.write_text(rendered, encoding="utf-8")
            dest_rel = (
                f".github/instructions/{rel.parent / dest_name}"
                if str(rel.parent) != "."
                else f".github/instructions/{dest_name}"
            )
            entries.append({
                "path": dest_rel,
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

        Manifest paths are recorded as ``.agents/skills/{skill_name}/SKILL.md``.
        """
        return SkillsIntegration.render_skill(self, source, target_dir, provider, copy)

    # --- install ---

    def install(
        self,
        source: Path,
        target: Path,
        provider: str,
        copy: bool = False,
    ) -> None:
        """Install the Copilot platform from *source* into *target*.

        Parameters
        ----------
        source:
            Path to the ``asr/`` source directory.
        target:
            The project root where ``.github/`` will be created.
        provider:
            Name of the provider (e.g. ``"myprovider"``).  Used for manifest
            naming and marker-block identification.
        copy:
            If ``True``, copy skills instead of symlinking.
        """
        github_dir = target / ".github"
        agents_dir = target / ".agents"
        entries: list[ManifestEntry] = []

        # ------------------------------------------------------------------
        # 1. Skills:
        #    a. source/skills/<n>/SKILL.md → .agents/skills/<n>/SKILL.md (symlink or copy)
        #    b. .github/skills/ → .agents/skills/ (directory-level symlink or copytree)
        # ------------------------------------------------------------------
        skills_src = source / "skills"
        agents_skills_dir = agents_dir / "skills"
        github_skills_dir = github_dir / "skills"

        if skills_src.is_dir():
            # Step 1a: install each SKILL.md into .agents/skills/<n>/SKILL.md
            for skill_file in sorted(skills_src.glob("*/SKILL.md")):
                skill_name = skill_file.parent.name
                alias = agents_skills_dir / skill_name / "SKILL.md"
                alias.parent.mkdir(parents=True, exist_ok=True)
                kind = links.link_or_copy(skill_file.resolve(), alias, copy=copy)
                entries.append({
                    "path": f".agents/skills/{skill_name}/SKILL.md",
                    "kind": kind,
                    "target": str(skill_file.resolve()),
                })

            # Step 1b: create .github/skills/ → .agents/skills/ (directory alias)
            github_dir.mkdir(parents=True, exist_ok=True)
            agents_skills_dir.mkdir(parents=True, exist_ok=True)

            if copy:
                # Copy the directory tree
                if github_skills_dir.exists() or github_skills_dir.is_symlink():
                    if github_skills_dir.is_symlink():
                        github_skills_dir.unlink()
                    else:
                        shutil.rmtree(github_skills_dir)
                shutil.copytree(str(agents_skills_dir), str(github_skills_dir))
                entries.append({
                    "path": ".github/skills",
                    "kind": "copy",
                    "target": str(agents_skills_dir.resolve()),
                })
            else:
                # Symlink the directory
                if github_skills_dir.exists() or github_skills_dir.is_symlink():
                    if github_skills_dir.is_symlink():
                        github_skills_dir.unlink()
                    else:
                        shutil.rmtree(github_skills_dir)
                try:
                    os.symlink(agents_skills_dir.resolve(), github_skills_dir)
                    entries.append({
                        "path": ".github/skills",
                        "kind": "symlink",
                        "target": str(agents_skills_dir.resolve()),
                    })
                except OSError:
                    shutil.copytree(str(agents_skills_dir), str(github_skills_dir))
                    entries.append({
                        "path": ".github/skills",
                        "kind": "copy",
                        "target": str(agents_skills_dir.resolve()),
                    })

        # ------------------------------------------------------------------
        # 2. Agents: render source/agents/<n>.md → .github/agents/<n>.agent.md
        # ------------------------------------------------------------------
        agents_src = source / "agents"
        if agents_src.is_dir():
            agents_dest = github_dir / "agents"
            agents_dest.mkdir(parents=True, exist_ok=True)
            entries.extend(self.render_agent(agents_src, agents_dest, provider))

        # ------------------------------------------------------------------
        # 3. Rules: render source/rules/<n>.md → .github/instructions/<n>.instructions.md
        #    Preserve applyTo: from projected frontmatter.
        # ------------------------------------------------------------------
        rules_src = source / "rules"
        if rules_src.is_dir():
            rules_dest = github_dir / "instructions"
            rules_dest.mkdir(parents=True, exist_ok=True)
            entries.extend(self.render_rule(rules_src, rules_dest, provider))

        # ------------------------------------------------------------------
        # 4. Passthrough: source/copilot/** → .github/
        # ------------------------------------------------------------------
        existing_manifest = manifest.read_manifest(github_dir, provider)
        own_paths: set[str] = set()
        if existing_manifest:
            for entry in existing_manifest.get("entries", []):
                own_paths.add(entry["path"])

        copilot_passthrough_src = source / "copilot"
        if copilot_passthrough_src.is_dir():
            for src_file in sorted(copilot_passthrough_src.rglob("*")):
                if not src_file.is_file():
                    continue
                rel = src_file.relative_to(copilot_passthrough_src)
                dest = github_dir / rel
                rel_str = f".github/{rel}"

                dest.parent.mkdir(parents=True, exist_ok=True)
                incoming: Any = json.loads(src_file.read_text(encoding="utf-8")) if merge.is_json_passthrough(src_file) else None

                if merge.is_json_passthrough(src_file):
                    if dest.exists():
                        other_prov = _discover_other_provider(github_dir, rel_str) or "another provider"
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
                        # No existing file — plain write.
                        dest.write_text(json.dumps(incoming, indent=2), encoding="utf-8")
                        entries.append({
                            "path": rel_str,
                            "kind": "copy",
                            "from": str(src_file.resolve()),
                        })
                else:
                    # Non-JSON passthrough
                    if dest.exists() and rel_str not in own_paths:
                        other_prov = _discover_other_provider(github_dir, rel_str) or "another provider"
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
        # 5. Marker block: source/AGENTS.md → .github/copilot-instructions.md ONLY
        # ------------------------------------------------------------------
        agents_md_src = source / "AGENTS.md"
        if agents_md_src.exists():
            content = agents_md_src.read_text(encoding="utf-8")
            block_name = f"clasr:{provider}"

            copilot_instructions = github_dir / "copilot-instructions.md"
            github_dir.mkdir(parents=True, exist_ok=True)
            markers.write_block(copilot_instructions, provider, content)
            entries.append({
                "path": ".github/copilot-instructions.md",
                "kind": "marker-block",
                "block": block_name,
            })

        # ------------------------------------------------------------------
        # 6. Write manifest (last — atomic)
        # ------------------------------------------------------------------
        manifest_data = {
            "version": 1,
            "provider": provider,
            "platform": "copilot",
            "source": str(source.resolve()),
            "entries": entries,
        }
        manifest.write_manifest(github_dir, provider, manifest_data)

    # --- uninstall ---

    def uninstall(self, target: Path, provider: str) -> None:
        """Uninstall the Copilot platform for *provider* from *target*.

        Reads the manifest at ``.github/.clasr-manifest/<provider>.json`` and
        reverses each installation entry.  If the manifest does not exist,
        returns silently (idempotent).

        Parameters
        ----------
        target:
            The project root (same ``target`` passed to :meth:`install`).
        provider:
            Provider name whose installation should be removed.
        """
        github_dir = target / ".github"
        mf = manifest.read_manifest(github_dir, provider)
        if mf is None:
            # No manifest — nothing to do (idempotent).
            return

        for entry in mf.get("entries", []):
            kind = entry["kind"]
            path_rel = entry["path"]
            full_path = target / path_rel

            if kind in ("symlink", "copy"):
                # For .github/skills directory alias (directory symlink or copytree)
                if full_path.is_dir() and not full_path.is_symlink():
                    # It's a real directory (copy mode) — remove it
                    shutil.rmtree(full_path, ignore_errors=True)
                else:
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
        manifest.delete_manifest(github_dir, provider)

        # Best-effort cleanup of empty parent directories.
        _cleanup_empty_dirs(target)


# ---------------------------------------------------------------------------
# Module-level shims (backward compatibility)
# ---------------------------------------------------------------------------


def install(
    source: Path,
    target: Path,
    provider: str,
    copy: bool = False,
) -> None:
    """Install the Copilot platform from *source* into *target*.

    Shim that delegates to :class:`CopilotIntegration`.
    """
    CopilotIntegration().install(source, target, provider, copy)


def uninstall(target: Path, provider: str) -> None:
    """Uninstall the Copilot platform for *provider* from *target*.

    Shim that delegates to :class:`CopilotIntegration`.
    """
    CopilotIntegration().uninstall(target, provider)
