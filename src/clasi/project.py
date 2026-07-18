"""Project root object for CLASI. All path resolution flows through here."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from clasi.agent import Agent
    from clasi.sprint import Sprint
    from clasi.state_db_class import StateDB
    from clasi.issue import Issue

log = logging.getLogger(__name__)

# Default root-relative paths for each artifact category.
# These are the NEW visible layout defaults for fresh installs.
# Existing installs can override any entry via .clasi/config.yaml paths: map.
ARTIFACT_PATH_DEFAULTS: dict[str, str] = {
    "issues": "clasi/issues",
    "sprints": "clasi/sprints",
    "reflections": "clasi/reflections",
    "design": "docs/design",
    "logs": ".clasi/log",
    "db": ".clasi/.clasi.db",
}


def _load_config(root: Path) -> dict:
    """Read .clasi/config.yaml and return the full parsed mapping.

    Returns the parsed dict when top-level YAML is a dict, returns {} on
    FileNotFoundError, YAMLError, wrong top-level type, or any other
    exception. Never raises.
    """
    config_path = root / ".clasi" / "config.yaml"
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
        return {}
    except FileNotFoundError:
        return {}
    except yaml.YAMLError:
        return {}
    except Exception:  # noqa: BLE001
        return {}


def _load_paths_config(root: Path) -> dict:
    """Read .clasi/config.yaml and return the paths: mapping.

    Returns data["paths"] when it is a dict[str, str], returns {} on
    FileNotFoundError, YAMLError, or wrong type. Never raises.
    """
    data = _load_config(root)
    paths = data.get("paths")
    if isinstance(paths, dict):
        return paths
    return {}


def _load_sources_config(root: Path) -> list:
    """Read .clasi/config.yaml and return the sources: list.

    Returns data["sources"] when it is a list, returns [] on any error
    or wrong type (missing key, malformed YAML, non-list value). Never
    raises.
    """
    data = _load_config(root)
    sources = data.get("sources")
    if isinstance(sources, list):
        return sources
    return []


def _load_protected_paths_config(root: Path) -> list:
    """Read .clasi/config.yaml and return the protected_paths: list.

    Returns data["protected_paths"] when it is a list, returns [] on any
    error or wrong type (missing key, malformed YAML, non-list value).
    Never raises. An empty return means "not configured" — callers must
    treat that as distinct from an explicit empty list, since role-guard
    falls back to its pre-existing allow-list-based blocking when this is
    empty, rather than allowing everything.
    """
    data = _load_config(root)
    protected = data.get("protected_paths")
    if isinstance(protected, list):
        return protected
    return []


def _load_excluded_paths_config(root: Path) -> list:
    """Read .clasi/config.yaml and return the excluded_paths: list.

    Returns data["excluded_paths"] when it is a list, returns [] on any
    error or wrong type. Never raises. Carves out subdirectories of a
    protected_paths prefix that are not actually source/tests — e.g. a
    project whose tests/ is protected but that also has a
    tests/e2e/ Docker test-harness (scripts, Dockerfile, fixtures) which
    is tooling, not the test suite itself.
    """
    data = _load_config(root)
    excluded = data.get("excluded_paths")
    if isinstance(excluded, list):
        return excluded
    return []


def _load_design_docs_opt_in(root: Path) -> str | None:
    """Read .clasi/config.yaml and return the design_docs opt-in tri-state.

    Returns the raw string value of the top-level ``design_docs`` key
    (expected ``"enabled"`` or ``"disabled"``) when present, or ``None``
    when the key is absent, the config is missing/malformed, or the value
    is not a string. ``None`` represents "unset" — distinct from an
    explicit opt-out. Never raises.
    """
    data = _load_config(root)
    value = data.get("design_docs")
    if isinstance(value, str):
        return value
    return None


class SprintNotFoundError(ValueError):
    """Raised when no sprint directory matches the requested sprint ID."""


class SprintFrontmatterError(ValueError):
    """Raised when a sprint directory exists but its frontmatter is malformed."""


class SprintIdMismatchError(ValueError):
    """Raised when a sprint's frontmatter is valid but the id field is absent or wrong."""


class Project:
    """Root object for a CLASI project. All path resolution flows through here."""

    def __init__(self, root: str | Path):
        self._root = Path(root).resolve()
        self._db: StateDB | None = None
        self._paths: dict | None = None
        self._sources: list | None = None

    @property
    def root(self) -> Path:
        return self._root

    @property
    def clasi_dir(self) -> Path:
        """.clasi/ directory — fixed hidden state anchor; not configurable."""
        return self._root / ".clasi"

    # --- Configurable path resolution ---

    def _path_config(self) -> dict:
        """Return the paths: mapping from .clasi/config.yaml (lazy, cached)."""
        if self._paths is None:
            self._paths = _load_paths_config(self._root)
        return self._paths

    def _resolve_dir(self, key: str) -> Path:
        """Return the root-relative path for *key* honoring config overrides."""
        override = self._path_config().get(key)
        rel = override if override else ARTIFACT_PATH_DEFAULTS[key]
        return self._root / rel

    # --- Category path properties ---

    @property
    def issues_dir(self) -> Path:
        """Pending pool directory (default: clasi/issues/)."""
        return self._resolve_dir("issues")

    @property
    def sprints_dir(self) -> Path:
        """Sprints directory (default: clasi/sprints/)."""
        return self._resolve_dir("sprints")

    @property
    def reflections_dir(self) -> Path:
        """Reflections directory (default: clasi/reflections/)."""
        return self._resolve_dir("reflections")

    @property
    def design_dir(self) -> Path:
        """Design documents directory (default: docs/design/)."""
        return self._resolve_dir("design")

    @property
    def log_dir(self) -> Path:
        """Log directory (default: .clasi/log/)."""
        return self._resolve_dir("logs")

    @property
    def db_path(self) -> Path:
        """Path to the SQLite database file (default: .clasi/.clasi.db)."""
        return self._resolve_dir("db")

    @property
    def mcp_config_path(self) -> Path:
        """Path to .mcp.json in the project root."""
        return self._root / ".mcp.json"

    # --- Persistent design-doc-set config (sprint 021) ---

    @property
    def sources(self) -> list[Path]:
        """Resolved source-tree roots for the persistent design-doc set.

        Reads the top-level ``sources:`` list from ``.clasi/config.yaml``
        (repo-relative directory paths, e.g. ``[src]`` or
        ``[src, tests]``). Missing or malformed config yields an empty
        list — "no sources declared" is not an error; callers (validator,
        bootstrap) are responsible for treating that as "doc-set not
        usable yet." Whether a single or multiple source roots are
        configured is derivable from the length of this list.

        Returns absolute, resolved ``Path`` objects, one per configured
        root, in config order.
        """
        if self._sources is None:
            self._sources = _load_sources_config(self._root)
        return [(self._root / rel).resolve() for rel in self._sources]

    @property
    def protected_paths(self) -> list[str]:
        """Root-relative directory prefixes role-guard treats as source/tests.

        Reads the top-level ``protected_paths:`` list from
        ``.clasi/config.yaml`` (e.g. ``[src, tests]``), set by ``clasi
        init`` when it detects (or is told) the project's source and test
        directories. Each entry is normalized to a root-relative string
        with a trailing slash, suitable for ``str.startswith()`` prefix
        checks against the same normalized paths role-guard already uses.

        An empty list means "not configured" — role-guard must treat this
        as distinct from an explicit empty list of protected paths: it
        falls back to its pre-``protected_paths`` behavior (block anything
        not on the artifact allow-list) rather than allowing everything,
        so existing projects that have not re-run ``clasi init`` keep
        their current enforcement instead of silently losing it.
        """
        raw = _load_protected_paths_config(self._root)
        result = []
        for rel in raw:
            rel = str(rel).strip("/")
            if rel:
                result.append(rel + "/")
        return result

    @property
    def excluded_paths(self) -> list[str]:
        """Root-relative prefixes carved out of protected_paths.

        Reads the top-level ``excluded_paths:`` list from
        ``.clasi/config.yaml`` (e.g. ``[tests/e2e]``). A path under one of
        these prefixes is allowed even if it also falls under a
        ``protected_paths`` prefix — e.g. a project that protects ``tests/``
        broadly but has a ``tests/e2e/`` Docker test-harness (scripts,
        Dockerfile, fixtures — tooling, not the test suite itself) that
        should stay editable without an OOP bypass.

        Normalized the same way as ``protected_paths`` (root-relative,
        trailing slash). Only meaningful when ``protected_paths`` is also
        configured — with no protected_paths, role-guard never reaches the
        prefix check this feeds into.
        """
        raw = _load_excluded_paths_config(self._root)
        result = []
        for rel in raw:
            rel = str(rel).strip("/")
            if rel:
                result.append(rel + "/")
        return result

    @property
    def design_docs_opt_in(self) -> bool | None:
        """The stakeholder's opt-in/opt-out/unset decision for the design-doc set.

        Reads the top-level ``design_docs:`` key from
        ``.clasi/config.yaml``: ``"enabled"`` -> ``True``, ``"disabled"``
        -> ``False``, absent or any other value -> ``None`` ("unset").
        ``None`` is distinguishable from an explicit ``False`` so the
        team-lead knows whether to prompt the stakeholder rather than
        silently assuming opt-out.
        """
        value = _load_design_docs_opt_in(self._root)
        if value == "enabled":
            return True
        if value == "disabled":
            return False
        return None

    def set_design_docs_opt_in(self, enabled: bool) -> None:
        """Record the stakeholder's opt-in/opt-out decision in config.yaml.

        Writes ``design_docs: enabled`` or ``design_docs: disabled`` at
        the top level of ``.clasi/config.yaml``, preserving any other
        existing keys (``paths:``, ``sources:``, ``process:``, etc.).
        Creates ``.clasi/config.yaml`` (and ``.clasi/`` if needed) when it
        does not yet exist.
        """
        data = _load_config(self._root)
        data["design_docs"] = "enabled" if enabled else "disabled"

        config_dir = self._root / ".clasi"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = config_dir / "config.yaml"
        config_path.write_text(
            yaml.safe_dump(data, sort_keys=False), encoding="utf-8"
        )

    @property
    def db(self) -> StateDB:
        """Lazily-initialized StateDB instance."""
        if self._db is None:
            from clasi.state_db_class import StateDB

            self._db = StateDB(self.db_path)
        return self._db

    # --- Sprint management ---

    def get_sprint(self, sprint_id: str) -> Sprint:
        """Find a sprint by its ID (checks active and done directories).

        When a directory whose name starts with ``{sprint_id}-`` is found, the
        frontmatter is validated strictly: a malformed fence raises
        ``SprintFrontmatterError`` and an absent or mismatched ``id:`` field
        raises ``SprintIdMismatchError``.  Directories that clearly belong to a
        different sprint (different name prefix) are skipped silently.

        Raises:
            SprintFrontmatterError: If the candidate sprint.md has malformed frontmatter.
            SprintIdMismatchError: If frontmatter parses but id is absent or wrong.
            SprintNotFoundError: If no sprint directory with the given ID exists.
        """
        from clasi.sprint import Sprint
        from clasi.frontmatter import read_frontmatter, MalformedFrontmatterError

        for location in [self.sprints_dir, self.sprints_dir / "done"]:
            if not location.exists():
                continue
            for d in sorted(location.iterdir()):
                if not d.is_dir():
                    continue
                sprint_file = d / "sprint.md"
                if not sprint_file.exists():
                    continue

                # Determine whether this directory is the candidate for sprint_id.
                # Directory names follow the pattern "{id}-{slug}", so a directory
                # whose name starts with "{sprint_id}-" (or equals sprint_id) is the
                # candidate.  Others are silently skipped.
                dir_name = d.name
                is_candidate = dir_name == sprint_id or dir_name.startswith(f"{sprint_id}-")

                try:
                    fm = read_frontmatter(sprint_file)
                except MalformedFrontmatterError as exc:
                    if is_candidate:
                        raise SprintFrontmatterError(
                            f"Malformed frontmatter in {sprint_file}: {exc}"
                        ) from exc
                    # Not our candidate — skip
                    continue

                if is_candidate:
                    found_id = fm.get("id")
                    if not found_id:
                        raise SprintIdMismatchError(
                            f"Sprint file {sprint_file!r} has no 'id' field in frontmatter"
                        )
                    if found_id != sprint_id:
                        raise SprintIdMismatchError(
                            f"Sprint file {sprint_file!r} has id {found_id!r}, "
                            f"but requested id {sprint_id!r}"
                        )
                    return Sprint(d, self)

                # Not a candidate — check for exact id match as fallback
                # (handles directories not following the naming convention).
                if fm.get("id") == sprint_id:
                    return Sprint(d, self)

        raise SprintNotFoundError(f"Sprint '{sprint_id}' not found")

    def list_sprints(self, status: str | None = None) -> list[Sprint]:
        """List all sprints, optionally filtered by status.

        Corrupt sprint files (malformed frontmatter) are logged as warnings
        and skipped rather than halting iteration.
        """
        from clasi.sprint import Sprint
        from clasi.frontmatter import read_frontmatter, MalformedFrontmatterError

        results: list[Sprint] = []
        for location in [self.sprints_dir, self.sprints_dir / "done"]:
            if not location.exists():
                continue
            for d in sorted(location.iterdir()):
                if not d.is_dir():
                    continue
                sprint_file = d / "sprint.md"
                if not sprint_file.exists():
                    continue
                try:
                    fm = read_frontmatter(sprint_file)
                except MalformedFrontmatterError as exc:
                    log.warning("Skipping sprint file with malformed frontmatter: %s (%s)", sprint_file, exc)
                    continue
                sprint_status = fm.get("status", "unknown")
                if status and sprint_status != status:
                    continue
                results.append(Sprint(d, self))
        return results

    def create_sprint(self, title: str) -> Sprint:
        """Create a new sprint directory with only sprint.md (roadmap phase).

        Writes only sprint.md; usecases.md, architecture-update.md, and the
        tickets/ directory tree are created later during detail planning.
        """
        from clasi.sprint import Sprint
        from clasi.templates import (
            SPRINT_TEMPLATE,
            slugify,
        )

        sprint_id = self._next_sprint_id()
        slug = slugify(title)
        sprint_dir = self.sprints_dir / f"{sprint_id}-{slug}"

        if sprint_dir.exists():
            raise ValueError(f"Sprint directory already exists: {sprint_dir}")

        sprint_dir.mkdir(parents=True, exist_ok=True)
        sprint = Sprint(sprint_dir, self)

        fmt = {"id": sprint_id, "title": title, "slug": slug}
        sprint.sprint_md.write_text(
            SPRINT_TEMPLATE.format(**fmt), encoding="utf-8"
        )

        return sprint

    def _next_sprint_id(self) -> str:
        """Determine the next sprint number (NNN format)."""
        from clasi.frontmatter import read_frontmatter

        max_id = 0
        for location in [self.sprints_dir, self.sprints_dir / "done"]:
            if not location.exists():
                continue
            for d in location.iterdir():
                if d.is_dir() and (d / "sprint.md").exists():
                    fm = read_frontmatter(d / "sprint.md")
                    try:
                        num = int(fm.get("id", "0"))
                        max_id = max(max_id, num)
                    except (ValueError, TypeError):
                        pass
        return f"{max_id + 1:03d}"

    # --- Agent management ---

    @property
    def _agents_dir(self) -> Path:
        """Path to the agents directory inside the package."""
        return Path(__file__).parent.resolve() / "plugin" / "agents"

    def get_agent(self, name: str) -> Agent:
        """Find agent by name in the flat clasi/plugin/agents/ directory.

        Only active agents are searched. Archived agents in ``old/`` are not
        accessible by name; use the directory directly if needed.

        Raises:
            ValueError: If no agent with the given name is found.
        """
        from clasi.agent import Agent

        agents_dir = self._agents_dir
        if not agents_dir.exists():
            raise ValueError(f"Agents directory not found: {agents_dir}")

        agent_dir = agents_dir / name
        if agent_dir.is_dir():
            return Agent(agent_dir, self)

        # Build available list for error message
        available = sorted(
            d.name for d in agents_dir.iterdir() if d.is_dir() and d.name != "old"
        )
        raise ValueError(
            f"No agent found with name '{name}'. "
            f"Available: {', '.join(available)}"
        )

    def list_agents(self) -> list[Agent]:
        """List all agents in the flat clasi/plugin/agents/ directory."""
        from clasi.agent import Agent

        agents_dir = self._agents_dir
        if not agents_dir.exists():
            return []

        results: list[Agent] = []
        for agent_dir in sorted(agents_dir.iterdir()):
            if agent_dir.is_dir() and agent_dir.name != "old":
                results.append(Agent(agent_dir, self))
        return results

    # --- Issue management ---

    def get_issue(self, filename: str) -> Issue:
        """Get an issue by its filename.

        Search order:
        1. Pending pool: ``.clasi/issues/<filename>``
        2. Sprint-scoped issues: ``<sprint>/issues/<filename>`` for every sprint
        """
        from clasi.issue import Issue

        # Check pending pool
        path = self.issues_dir / filename
        if path.exists():
            return Issue(path, self)

        # Check sprint-scoped issues directories (<sprint>/issues/<filename>)
        for sprint in self.list_sprints():
            path = sprint.path / "issues" / filename
            if path.exists():
                return Issue(path, self)
            path = sprint.path / "issues" / "done" / filename
            if path.exists():
                return Issue(path, self)

        raise ValueError(f"Issue '{filename}' not found")

    def list_issues(self) -> list[Issue]:
        """List all pending pool issues (``.clasi/issues/*.md``).

        Returns only files in the top-level pending pool directory.
        Sprint-scoped in-progress issues are retrieved via ``Sprint.list_issues()``.
        """
        from clasi.issue import Issue

        if not self.issues_dir.exists():
            return []
        return [Issue(f, self) for f in sorted(self.issues_dir.glob("*.md"))]
