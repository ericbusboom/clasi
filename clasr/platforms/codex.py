"""
clasr/platforms/codex.py

Codex platform installer.

Given an ``asr/`` source directory, installs CLASI-rendered content into
``.codex/`` and ``.agents/`` in the target directory, writes named marker
blocks into ``AGENTS.md``, and records everything in a manifest.

Public API:
    install(source: Path, target: Path, provider: str, copy: bool = False) -> None
    uninstall(target: Path, provider: str) -> None

Source layout expected:
    <source>/skills/<n>/SKILL.md  — installed as symlinks/copies under .agents/
    <source>/agents/<n>.md        — rendered with platform="codex" → .codex/agents/
    <source>/rules/<n>.md         — rendered with platform="codex":
                                     applyTo/paths present → nested AGENTS.md
                                     absent (unscoped)     → included in root AGENTS.md block
    <source>/codex/**             — passthrough to .codex/
    <source>/AGENTS.md            — written as named marker block into AGENTS.md

No imports from clasi.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import clasr.frontmatter as frontmatter
import clasr.links as links
import clasr.manifest as manifest
import clasr.markers as markers
import clasr.merge as merge


def _discover_other_provider(codex_dir: Path, path_rel: str) -> str | None:
    """Return the name of any other provider that owns *path_rel*, or None.

    Scans all manifests in ``<codex_dir>/.clasr-manifest/`` looking for an
    entry with this relative path.  Returns the first provider name found, or
    ``None`` if no manifest claims it.
    """
    manifest_dir = codex_dir / ".clasr-manifest"
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


def _scope_to_dir(scope: str) -> str:
    """Derive a directory path from an applyTo/paths glob pattern.

    Examples:
        "docs/clasi/**" -> "docs/clasi"
        "docs/clasi/**/*.md" -> "docs/clasi"
        "docs/clasi" -> "docs/clasi"
    """
    # Strip trailing wildcard segments.
    # If "/**" appears, strip it and everything after.
    if "/**" in scope:
        return scope[: scope.index("/**")]
    # If it ends in /* or *, just take the parent-like prefix.
    if scope.endswith("/*"):
        return scope[:-2]
    # Otherwise treat as literal path.
    return scope


def install(
    source: Path,
    target: Path,
    provider: str,
    copy: bool = False,
) -> None:
    """Install the Codex platform from *source* into *target*.

    Parameters
    ----------
    source:
        Path to the ``asr/`` source directory.
    target:
        The project root where ``.codex/`` and ``.agents/`` will be created.
    provider:
        Name of the provider (e.g. ``"myprovider"``).  Used for manifest
        naming and marker-block identification.
    copy:
        If ``True``, copy skills files instead of symlinking.
    """
    codex_dir = target / ".codex"
    agents_dir = target / ".agents"
    entries: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # 1. Skills: source/skills/<n>/SKILL.md → .agents/skills/<n>/SKILL.md
    # ------------------------------------------------------------------
    skills_src = source / "skills"
    if skills_src.is_dir():
        for skill_file in sorted(skills_src.glob("*/SKILL.md")):
            skill_name = skill_file.parent.name
            alias = agents_dir / "skills" / skill_name / "SKILL.md"
            alias.parent.mkdir(parents=True, exist_ok=True)
            kind = links.link_or_copy(skill_file.resolve(), alias, copy=copy)
            entries.append({
                "path": f".agents/skills/{skill_name}/SKILL.md",
                "kind": kind,
                "target": str(skill_file.resolve()),
            })

    # ------------------------------------------------------------------
    # 2. Agents: render source/agents/<n>.md → .codex/agents/<n>.md
    # ------------------------------------------------------------------
    agents_src = source / "agents"
    if agents_src.is_dir():
        for agent_file in sorted(agents_src.glob("**/*.md")):
            rel = agent_file.relative_to(agents_src)
            dest = codex_dir / "agents" / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            rendered = frontmatter.render_file(agent_file, "codex")
            dest.write_text(rendered, encoding="utf-8")
            entries.append({
                "path": f".codex/agents/{rel}",
                "kind": "rendered",
                "from": str(agent_file.resolve()),
            })

    # ------------------------------------------------------------------
    # 3. Rules: render source/rules/<n>.md with platform="codex"
    #    - applyTo/paths present → nested AGENTS.md in that directory
    #    - absent (unscoped)     → collect body for root AGENTS.md block
    # ------------------------------------------------------------------
    unscoped_rule_bodies: list[str] = []
    rules_src = source / "rules"
    if rules_src.is_dir():
        for rule_file in sorted(rules_src.glob("**/*.md")):
            _shared_fm, full_fm, body = frontmatter.parse_union(rule_file)
            projected_fm, body = frontmatter.project(full_fm, body, "codex")

            # Determine scope: applyTo or paths field in projected frontmatter.
            scope: str | None = None
            if "applyTo" in projected_fm:
                scope = projected_fm["applyTo"]
            elif "paths" in projected_fm:
                paths_val = projected_fm["paths"]
                if isinstance(paths_val, list) and paths_val:
                    scope = paths_val[0]
                elif isinstance(paths_val, str):
                    scope = paths_val

            if scope is not None:
                subdir = _scope_to_dir(scope)
                nested_agents_md = target / subdir / "AGENTS.md"
                nested_agents_md.parent.mkdir(parents=True, exist_ok=True)
                # Append to existing content (multiple rules may target same file).
                if nested_agents_md.exists():
                    existing = nested_agents_md.read_text(encoding="utf-8")
                    sep = "" if existing.endswith("\n") else "\n"
                    nested_agents_md.write_text(
                        existing + sep + "\n" + body.strip() + "\n", encoding="utf-8"
                    )
                else:
                    nested_agents_md.write_text(body.strip() + "\n", encoding="utf-8")
                entries.append({
                    "path": f"{subdir}/AGENTS.md",
                    "kind": "rendered",
                    "from": str(rule_file.resolve()),
                })
            else:
                # Unscoped rule: collect body for inclusion in root AGENTS.md block.
                unscoped_rule_bodies.append(body.strip())

    # ------------------------------------------------------------------
    # 4. Passthrough: source/codex/** → .codex/
    # ------------------------------------------------------------------
    existing_manifest = manifest.read_manifest(codex_dir, provider)
    own_paths: set[str] = set()
    if existing_manifest:
        for entry in existing_manifest.get("entries", []):
            own_paths.add(entry["path"])

    codex_passthrough_src = source / "codex"
    if codex_passthrough_src.is_dir():
        for src_file in sorted(codex_passthrough_src.rglob("*")):
            if not src_file.is_file():
                continue
            rel = src_file.relative_to(codex_passthrough_src)
            dest = codex_dir / rel
            rel_str = f".codex/{rel}"

            dest.parent.mkdir(parents=True, exist_ok=True)
            incoming = json.loads(src_file.read_text(encoding="utf-8")) if merge.is_json_passthrough(src_file) else None

            if merge.is_json_passthrough(src_file):
                if dest.exists():
                    other_prov = _discover_other_provider(codex_dir, rel_str) or "another provider"
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
                    other_prov = _discover_other_provider(codex_dir, rel_str) or "another provider"
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
    # 5. Marker block: source/AGENTS.md (+ unscoped rule bodies) → AGENTS.md
    # ------------------------------------------------------------------
    agents_md_src = source / "AGENTS.md"
    if agents_md_src.exists() or unscoped_rule_bodies:
        base_content = ""
        if agents_md_src.exists():
            base_content = agents_md_src.read_text(encoding="utf-8")

        # Combine source/AGENTS.md with unscoped rule bodies.
        parts = []
        if base_content.strip():
            parts.append(base_content.strip())
        parts.extend(unscoped_rule_bodies)
        combined_content = "\n\n".join(parts)

        block_name = f"clasr:{provider}"
        agents_md_dest = target / "AGENTS.md"
        markers.write_block(agents_md_dest, provider, combined_content)
        entries.append({
            "path": "AGENTS.md",
            "kind": "marker-block",
            "block": block_name,
        })

    # ------------------------------------------------------------------
    # 6. Write manifest (last — atomic)
    # ------------------------------------------------------------------
    manifest_data = {
        "version": 1,
        "provider": provider,
        "platform": "codex",
        "source": str(source.resolve()),
        "entries": entries,
    }
    manifest.write_manifest(codex_dir, provider, manifest_data)


def uninstall(target: Path, provider: str) -> None:
    """Uninstall the Codex platform for *provider* from *target*.

    Reads the manifest at ``.codex/.clasr-manifest/<provider>.json`` and
    reverses each installation entry.  If the manifest does not exist,
    returns silently (idempotent).

    Parameters
    ----------
    target:
        The project root (same ``target`` passed to :func:`install`).
    provider:
        Provider name whose installation should be removed.
    """
    codex_dir = target / ".codex"
    mf = manifest.read_manifest(codex_dir, provider)
    if mf is None:
        return

    for entry in mf.get("entries", []):
        kind = entry["kind"]
        path_rel = entry["path"]
        full_path = target / path_rel

        if kind in ("symlink", "copy"):
            links.unlink_alias(full_path)

        elif kind == "rendered":
            full_path.unlink(missing_ok=True)

        elif kind == "marker-block":
            markers.strip_block(full_path, provider)

        elif kind == "json-merged":
            keys_to_remove: list[str] = entry.get("keys", [])
            if full_path.exists():
                try:
                    data = json.loads(full_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    data = {}
                for k in keys_to_remove:
                    data.pop(k, None)
                if data:
                    full_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
                else:
                    full_path.unlink(missing_ok=True)

    # Delete the manifest file.
    manifest.delete_manifest(codex_dir, provider)

    # Best-effort cleanup of empty parent directories.
    _cleanup_empty_dirs(target)


def _cleanup_empty_dirs(target: Path) -> None:
    """Remove empty directories that clasr may have created under *target*.

    Tries to remove (in order, deepest first): skill subdirs, then
    .agents/skills, .agents, .codex/agents, .codex itself.
    Only removes directories that are truly empty.
    """
    codex_dir = target / ".codex"
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

    # .codex subdirectories.
    candidates.append(codex_dir / "agents")
    candidates.append(codex_dir / ".clasr-manifest")
    candidates.append(codex_dir)

    for d in candidates:
        try:
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()
        except OSError:
            pass
