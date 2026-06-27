"""
clasr/integration.py

IntegrationBase ABC and three intermediate classes for clasr platform integrations.

This module defines the typed contract every clasr platform must satisfy.

Classes:
    IntegrationBase   — ABC with all abstract methods every platform must implement.
    MarkdownIntegration — shared render_agent for platforms using YAML-frontmatter .md files.
    TomlIntegration   — shared render_agent for TOML-format platforms (Codex); includes
                         scoped/unscoped rule routing to nested AGENTS.md.
    SkillsIntegration — shared render_skill symlinking/copying SKILL.md into self.skill_dir.

Free function:
    write_marker_blocks(target, provider, content, companion_files) — platform-agnostic
        marker-block writer; reads companion_files from the integration's class variable.

Boundary: imports only clasr.frontmatter, clasr.manifest, clasr.markers, clasr.links.
No platform subclass modules are imported here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Literal

import clasr.frontmatter as frontmatter
import clasr.links as links
import clasr.manifest as manifest
import clasr.markers as markers


# ---------------------------------------------------------------------------
# Type alias for manifest entry dicts
# ---------------------------------------------------------------------------

ManifestEntry = dict[str, Any]


# ---------------------------------------------------------------------------
# Free function
# ---------------------------------------------------------------------------


def write_marker_blocks(
    target: Path,
    provider: str,
    content: str,
    companion_files: list[str],
) -> list[ManifestEntry]:
    """Write *content* as a named marker block into each file in *companion_files*.

    Parameters
    ----------
    target:
        The project root directory.
    provider:
        Provider name used for the marker block identifier (``clasr:<provider>``).
    content:
        Content to place inside the marker delimiters.
    companion_files:
        List of file paths relative to *target* that should receive the block.

    Returns
    -------
    list[ManifestEntry]
        Manifest entries (one per companion file) recording the written blocks.
    """
    block_name = f"clasr:{provider}"
    entries: list[ManifestEntry] = []
    for rel_path in companion_files:
        dest = target / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        markers.write_block(dest, provider, content)
        entries.append({
            "path": rel_path,
            "kind": "marker-block",
            "block": block_name,
        })
    return entries


# ---------------------------------------------------------------------------
# IntegrationBase
# ---------------------------------------------------------------------------


class IntegrationBase(ABC):
    """Abstract base class for all clasr platform integrations.

    Each platform subclass declares class-level fields as class attributes
    (not ``__init__`` parameters) and implements all abstract methods.

    Class-level fields
    ------------------
    id : str
        Short identifier, e.g. ``"claude"``, ``"codex"``.
    display_name : str
        Human-readable name, e.g. ``"Claude Code"``.
    detect_files : list[str]
        Relative paths whose presence implies this platform is installed.
    target_root : Path
        Platform configuration root, e.g. ``Path(".claude")``.
    command_dir : Path | None
        Directory for command files, or ``None`` if unused.
    skill_dir : Path | None
        Directory for installed skills, or ``None`` if unsupported.
    agent_dir : Path | None
        Directory for rendered agent files, or ``None`` if unsupported.
    rule_dir : Path | None
        Directory for rendered rule files, or ``None`` if unsupported.
    settings_file : Path | None
        Path to the platform settings JSON file, or ``None`` if unsupported.
    command_format : Literal["md", "toml", "yaml"]
        File format used for command files.
    frontmatter_dialect : Literal["yaml", "toml", "none"]
        Frontmatter dialect used when projecting source files.
    invoke_separator : str
        Separator used to invoke commands (e.g. ``"/"`` for Claude slash commands).
    companion_files : list[str]
        Paths (relative to project root) that receive marker blocks on install.
    """

    # --- Class-level field declarations (type annotations only; subclasses set values) ---

    id: str
    display_name: str
    detect_files: list[str]
    target_root: Path
    command_dir: Path | None
    skill_dir: Path | None
    agent_dir: Path | None
    rule_dir: Path | None
    settings_file: Path | None
    command_format: Literal["md", "toml", "yaml"]
    frontmatter_dialect: Literal["yaml", "toml", "none"]
    invoke_separator: str
    companion_files: list[str]

    # --- Abstract methods ---

    @abstractmethod
    def render_agent(
        self,
        source: Path,
        target_dir: Path,
        provider: str,
    ) -> list[ManifestEntry]:
        """Render agent files from *source* into *target_dir*.

        Parameters
        ----------
        source:
            Path to ``<asr>/agents/`` source directory.
        target_dir:
            Destination directory for rendered agent files.
        provider:
            Provider name for manifest entry labelling.

        Returns
        -------
        list[ManifestEntry]
            Manifest entries for all rendered agent files.
        """

    @abstractmethod
    def render_skill(
        self,
        source: Path,
        target_dir: Path,
        provider: str,
        copy: bool,
    ) -> list[ManifestEntry]:
        """Install skill files from *source* into *target_dir*.

        Parameters
        ----------
        source:
            Path to ``<asr>/skills/`` source directory.
        target_dir:
            Destination directory for installed skills.
        provider:
            Provider name for manifest entry labelling.
        copy:
            If ``True``, copy files instead of symlinking.

        Returns
        -------
        list[ManifestEntry]
            Manifest entries for all installed skill files.
        """

    @abstractmethod
    def render_rule(
        self,
        source: Path,
        target_dir: Path,
        provider: str,
    ) -> list[ManifestEntry]:
        """Render rule files from *source* into *target_dir*.

        Parameters
        ----------
        source:
            Path to ``<asr>/rules/`` source directory.
        target_dir:
            Destination directory for rendered rule files.
        provider:
            Provider name for manifest entry labelling.

        Returns
        -------
        list[ManifestEntry]
            Manifest entries for all rendered rule files.
        """

    @abstractmethod
    def install(
        self,
        source: Path,
        target: Path,
        provider: str,
        copy: bool = False,
    ) -> None:
        """Install this platform from *source* into *target*.

        Parameters
        ----------
        source:
            Path to the ``asr/`` source directory.
        target:
            The project root where platform files will be installed.
        provider:
            Name of the provider (used for manifest and marker-block naming).
        copy:
            If ``True``, copy files instead of symlinking where applicable.
        """

    @abstractmethod
    def uninstall(self, target: Path, provider: str) -> None:
        """Uninstall this platform for *provider* from *target*.

        Reads the manifest and reverses every installation entry.
        Returns silently (idempotent) if no manifest is found.

        Parameters
        ----------
        target:
            The project root (same ``target`` passed to :meth:`install`).
        provider:
            Provider name whose installation should be removed.
        """


# ---------------------------------------------------------------------------
# MarkdownIntegration
# ---------------------------------------------------------------------------


class MarkdownIntegration(IntegrationBase):
    """Intermediate class for platforms that use YAML-frontmatter ``.md`` agent files.

    Provides a concrete ``render_agent`` that calls
    ``frontmatter.render_file(source, self.id)`` and writes to ``self.agent_dir``
    inside ``target_dir``.

    Subclasses must still implement ``render_skill``, ``render_rule``,
    ``install``, and ``uninstall``.
    """

    def render_agent(
        self,
        source: Path,
        target_dir: Path,
        provider: str,
    ) -> list[ManifestEntry]:
        """Render ``.md`` agent files using ``self.id`` as the platform key.

        Walks ``source`` recursively for ``**/*.md`` files, renders each with
        :func:`clasr.frontmatter.render_file`, and writes to
        ``target_dir / rel`` preserving the relative sub-path.
        """
        entries: list[ManifestEntry] = []
        agent_dir_name = self.agent_dir.name if self.agent_dir else "agents"
        for agent_file in sorted(source.glob("**/*.md")):
            rel = agent_file.relative_to(source)
            dest = target_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            rendered = frontmatter.render_file(agent_file, self.id)
            dest.write_text(rendered, encoding="utf-8")
            entries.append({
                "path": f"{target_dir.name}/{agent_dir_name}/{rel}",
                "kind": "rendered",
                "from": str(agent_file.resolve()),
            })
        return entries

    @abstractmethod
    def render_skill(
        self,
        source: Path,
        target_dir: Path,
        provider: str,
        copy: bool,
    ) -> list[ManifestEntry]: ...

    @abstractmethod
    def render_rule(
        self,
        source: Path,
        target_dir: Path,
        provider: str,
    ) -> list[ManifestEntry]: ...

    @abstractmethod
    def install(
        self,
        source: Path,
        target: Path,
        provider: str,
        copy: bool = False,
    ) -> None: ...

    @abstractmethod
    def uninstall(self, target: Path, provider: str) -> None: ...


# ---------------------------------------------------------------------------
# TomlIntegration
# ---------------------------------------------------------------------------


def _scope_to_dir(scope: str) -> str:
    """Derive a directory path from an applyTo/paths glob pattern.

    Examples::

        "docs/clasi/**"      → "docs/clasi"
        "docs/clasi/**/*.md" → "docs/clasi"
        "docs/clasi"         → "docs/clasi"
    """
    if "/**" in scope:
        return scope[: scope.index("/**")]
    if scope.endswith("/*"):
        return scope[:-2]
    return scope


class TomlIntegration(IntegrationBase):
    """Intermediate class for TOML-format platforms (e.g. Codex).

    Provides a concrete ``render_agent`` that projects using the platform ``id``
    dialect.  Also provides scoped/unscoped rule routing logic in
    :meth:`_collect_rule_bodies` for subclasses to use.

    Subclasses must still implement ``render_skill``, ``render_rule``,
    ``install``, and ``uninstall``.
    """

    def render_agent(
        self,
        source: Path,
        target_dir: Path,
        provider: str,
    ) -> list[ManifestEntry]:
        """Render agent files using the TOML projection for ``self.id``."""
        entries: list[ManifestEntry] = []
        agent_dir_name = self.agent_dir.name if self.agent_dir else "agents"
        for agent_file in sorted(source.glob("**/*.md")):
            rel = agent_file.relative_to(source)
            dest = target_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            rendered = frontmatter.render_file(agent_file, self.id)
            dest.write_text(rendered, encoding="utf-8")
            entries.append({
                "path": f"{target_dir.name}/{agent_dir_name}/{rel}",
                "kind": "rendered",
                "from": str(agent_file.resolve()),
            })
        return entries

    def _collect_rule_bodies(
        self,
        source: Path,
        target: Path,
        provider: str,
    ) -> tuple[list[ManifestEntry], list[str]]:
        """Walk *source* for rule files and route scoped/unscoped rules.

        Scoped rules (those with ``applyTo`` or ``paths`` in projected
        frontmatter) are written to nested ``AGENTS.md`` files inside the
        matched subdirectory of *target*.

        Unscoped rules are returned as a list of body strings for the caller
        to include in the root AGENTS.md marker block.

        Parameters
        ----------
        source:
            Path to ``<asr>/rules/`` source directory.
        target:
            Project root (used to resolve scoped paths).
        provider:
            Provider name for manifest entry labelling.

        Returns
        -------
        tuple[list[ManifestEntry], list[str]]
            A 2-tuple of ``(entries, unscoped_bodies)``.
        """
        entries: list[ManifestEntry] = []
        unscoped_bodies: list[str] = []

        for rule_file in sorted(source.glob("**/*.md")):
            _shared_fm, full_fm, body = frontmatter.parse_union(rule_file)
            projected_fm, body = frontmatter.project(full_fm, body, self.id)

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
                if nested_agents_md.exists():
                    existing = nested_agents_md.read_text(encoding="utf-8")
                    sep = "" if existing.endswith("\n") else "\n"
                    nested_agents_md.write_text(
                        existing + sep + "\n" + body.strip() + "\n",
                        encoding="utf-8",
                    )
                else:
                    nested_agents_md.write_text(body.strip() + "\n", encoding="utf-8")
                entries.append({
                    "path": f"{subdir}/AGENTS.md",
                    "kind": "rendered",
                    "from": str(rule_file.resolve()),
                })
            else:
                unscoped_bodies.append(body.strip())

        return entries, unscoped_bodies

    @abstractmethod
    def render_skill(
        self,
        source: Path,
        target_dir: Path,
        provider: str,
        copy: bool,
    ) -> list[ManifestEntry]: ...

    @abstractmethod
    def render_rule(
        self,
        source: Path,
        target_dir: Path,
        provider: str,
    ) -> list[ManifestEntry]: ...

    @abstractmethod
    def install(
        self,
        source: Path,
        target: Path,
        provider: str,
        copy: bool = False,
    ) -> None: ...

    @abstractmethod
    def uninstall(self, target: Path, provider: str) -> None: ...


# ---------------------------------------------------------------------------
# SkillsIntegration
# ---------------------------------------------------------------------------


class SkillsIntegration(IntegrationBase):
    """Intermediate class for platforms with a SKILL.md convention.

    Provides a concrete ``render_skill`` that symlinks (or copies) each
    ``<source>/skills/<n>/SKILL.md`` into ``self.skill_dir`` inside the
    platform's target directory.

    Subclasses must still implement ``render_agent``, ``render_rule``,
    ``install``, and ``uninstall``.
    """

    def render_skill(
        self,
        source: Path,
        target_dir: Path,
        provider: str,
        copy: bool,
    ) -> list[ManifestEntry]:
        """Symlink or copy each ``SKILL.md`` from *source* into *target_dir*.

        The skill directory used is ``target_dir / self.skill_dir.name`` when
        ``self.skill_dir`` is set, otherwise ``target_dir / "skills"``.

        Parameters
        ----------
        source:
            Path to ``<asr>/skills/`` source directory.
        target_dir:
            Destination parent directory (typically the platform root or .agents).
        provider:
            Provider name for manifest entry labelling.
        copy:
            If ``True``, copy files instead of symlinking.
        """
        entries: list[ManifestEntry] = []
        skill_dir_name = self.skill_dir.name if self.skill_dir else "skills"
        for skill_file in sorted(source.glob("*/SKILL.md")):
            skill_name = skill_file.parent.name
            alias = target_dir / skill_dir_name / skill_name / "SKILL.md"
            alias.parent.mkdir(parents=True, exist_ok=True)
            kind = links.link_or_copy(skill_file.resolve(), alias, copy=copy)
            entries.append({
                "path": f"{target_dir.name}/{skill_dir_name}/{skill_name}/SKILL.md",
                "kind": kind,
                "target": str(skill_file.resolve()),
            })
        return entries

    @abstractmethod
    def render_agent(
        self,
        source: Path,
        target_dir: Path,
        provider: str,
    ) -> list[ManifestEntry]: ...

    @abstractmethod
    def render_rule(
        self,
        source: Path,
        target_dir: Path,
        provider: str,
    ) -> list[ManifestEntry]: ...

    @abstractmethod
    def install(
        self,
        source: Path,
        target: Path,
        provider: str,
        copy: bool = False,
    ) -> None: ...

    @abstractmethod
    def uninstall(self, target: Path, provider: str) -> None: ...
