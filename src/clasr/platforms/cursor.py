"""
clasr/platforms/cursor.py

Cursor platform installer.

Given an ``asr/`` source directory, installs CLASI-rendered content into
``.cursor/`` in the target directory and records everything in a manifest.

Public API:
    install(source: Path, target: Path, provider: str, copy: bool = False) -> None
    uninstall(target: Path, provider: str) -> None

Source layout expected:
    <source>/agents/<n>.md   — rendered with platform="cursor" → .cursor/rules/<n>.md
    <source>/rules/<n>.md    — rendered with platform="cursor" → .cursor/rules/<n>.mdc

Cursor has no skills support, no companion files, and no settings file.
Rule files use the ``.mdc`` extension instead of ``.md``.

No imports from clasi.
"""

from __future__ import annotations

from pathlib import Path

import clasr.frontmatter as frontmatter
import clasr.links as links
import clasr.manifest as manifest
import clasr.markers as markers
from clasr.integration import (
    ManifestEntry,
    MarkdownIntegration,
)


def _cleanup_empty_dirs(target: Path) -> None:
    """Remove empty directories that clasr may have created under *target*.

    Tries to remove (in order, deepest first): .cursor/rules,
    .cursor/.clasr-manifest, and .cursor itself.
    Only removes directories that are truly empty.
    """
    cursor_dir = target / ".cursor"

    candidates: list[Path] = [
        cursor_dir / "rules",
        cursor_dir / ".clasr-manifest",
        cursor_dir,
    ]

    for d in candidates:
        try:
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()
        except OSError:
            pass


# ---------------------------------------------------------------------------
# CursorIntegration
# ---------------------------------------------------------------------------


class CursorIntegration(MarkdownIntegration):
    """Cursor platform integration.

    Subclasses :class:`~clasr.integration.MarkdownIntegration` for
    YAML-frontmatter agent rendering.

    Installs into ``.cursor/`` within the project root.  Rule files are
    written with a ``.mdc`` extension into ``.cursor/rules/``.

    Cursor has no skills directory, no agent directory distinct from rules,
    no settings file, and no companion files.
    """

    # --- Class-level field declarations ---

    id = "cursor"
    display_name = "Cursor"
    detect_files = [".cursor/"]
    target_root = Path(".cursor")
    command_dir = Path(".cursor/rules")
    rule_dir = Path(".cursor/rules")
    agent_dir = None
    skill_dir = None
    settings_file = None
    command_format = "md"
    frontmatter_dialect = "yaml"
    invoke_separator = "/"
    companion_files: list[str] = []

    # --- render_skill (no-op: Cursor has no skills support) ---

    def render_skill(
        self,
        source: Path,
        target_dir: Path,
        provider: str,
        copy: bool,
    ) -> list[ManifestEntry]:
        """No-op: Cursor does not support skills.

        Returns an empty list.
        """
        return []

    # --- render_rule (override: use .mdc extension) ---

    def render_rule(
        self,
        source: Path,
        target_dir: Path,
        provider: str,
    ) -> list[ManifestEntry]:
        """Render ``.md`` rule files from *source* into *target_dir* as ``.mdc`` files.

        Walks *source* recursively for ``**/*.md`` files, renders each with
        :func:`clasr.frontmatter.render_file` using the ``cursor`` platform key,
        and writes to ``target_dir / <stem>.mdc`` (replacing ``.md`` with ``.mdc``).

        Manifest paths are recorded as ``.cursor/rules/{stem}.mdc``.
        """
        entries: list[ManifestEntry] = []
        for rule_file in sorted(source.glob("**/*.md")):
            rel = rule_file.relative_to(source)
            dest_name = rel.stem + ".mdc"
            dest = target_dir / rel.parent / dest_name
            dest.parent.mkdir(parents=True, exist_ok=True)
            rendered = frontmatter.render_file(rule_file, self.id)
            dest.write_text(rendered, encoding="utf-8")
            dest_rel = (
                f".cursor/rules/{rel.parent / dest_name}"
                if str(rel.parent) != "."
                else f".cursor/rules/{dest_name}"
            )
            entries.append({
                "path": dest_rel,
                "kind": "rendered",
                "from": str(rule_file.resolve()),
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
        """Install the Cursor platform from *source* into *target*.

        Parameters
        ----------
        source:
            Path to the ``asr/`` source directory.
        target:
            The project root where ``.cursor/`` will be created.
        provider:
            Name of the provider (e.g. ``"myprovider"``).  Used for manifest
            naming.
        copy:
            Accepted for interface compliance; unused (Cursor has no skills).
        """
        cursor_dir = target / ".cursor"
        entries: list[ManifestEntry] = []

        # ------------------------------------------------------------------
        # 1. Agents: render source/agents/<n>.md → .cursor/rules/<n>.md
        #    (Cursor has no separate agent directory; agents go into rules/)
        # ------------------------------------------------------------------
        agents_src = source / "agents"
        if agents_src.is_dir():
            rules_dest = cursor_dir / "rules"
            rules_dest.mkdir(parents=True, exist_ok=True)
            entries.extend(self.render_agent(agents_src, rules_dest, provider))

        # ------------------------------------------------------------------
        # 2. Rules: render source/rules/<n>.md → .cursor/rules/<n>.mdc
        # ------------------------------------------------------------------
        rules_src = source / "rules"
        if rules_src.is_dir():
            rules_dest = cursor_dir / "rules"
            rules_dest.mkdir(parents=True, exist_ok=True)
            entries.extend(self.render_rule(rules_src, rules_dest, provider))

        # ------------------------------------------------------------------
        # 3. Write manifest (last — atomic)
        # ------------------------------------------------------------------
        manifest_data = {
            "version": 1,
            "provider": provider,
            "platform": "cursor",
            "source": str(source.resolve()),
            "entries": entries,
        }
        manifest.write_manifest(cursor_dir, provider, manifest_data)

    # --- uninstall ---

    def uninstall(self, target: Path, provider: str) -> None:
        """Uninstall the Cursor platform for *provider* from *target*.

        Reads the manifest at ``.cursor/.clasr-manifest/<provider>.json`` and
        reverses each installation entry.  If the manifest does not exist,
        returns silently (idempotent).

        Parameters
        ----------
        target:
            The project root (same ``target`` passed to :meth:`install`).
        provider:
            Provider name whose installation should be removed.
        """
        cursor_dir = target / ".cursor"
        mf = manifest.read_manifest(cursor_dir, provider)
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

        manifest.delete_manifest(cursor_dir, provider)

        _cleanup_empty_dirs(target)
