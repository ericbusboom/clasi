"""Versioning utilities for the CLASI project.

Thin shim over ``dotconfig.versioning``.  Shared computation (format
parsing, version building, file updating, tagging) lives in dotconfig.
This module retains only clasi-specific helpers that read
``.clasi/settings.yaml`` and a wrapper for ``compute_next_version``
that honours the clasi config-file authority.

Default format: X+.YYYYMMDD.R+
"""

import re
from datetime import date
from pathlib import Path

import json
import yaml

# ---------------------------------------------------------------------------
# Re-exports from dotconfig (no clasi implementation retained)
# ---------------------------------------------------------------------------
from dotconfig.versioning import (
    parse_format,
    format_has_auto,
    build_version,
    build_tag_regex,
    create_version_tag,
    update_version_file,
    update_pyproject_version,
    update_package_json_version,
)

# ---------------------------------------------------------------------------
# Compat constants
# ---------------------------------------------------------------------------

DEFAULT_FORMAT = "X+.YYYYMMDD.R+"
DEFAULT_TRIGGER = "every_change"
VALID_TRIGGERS = ("manual", "every_sprint", "every_change")

# Kept for backward compatibility with callers that import it directly.
VERSION_PATTERN = re.compile(r"^v?(\d+)\.(\d{8})\.(\d+)$")

# Priority-ordered list of version file names and their types.
_VERSION_FILES: list[tuple[str, str]] = [
    ("pyproject.toml", "pyproject"),
    ("package.json", "package_json"),
]

# ---------------------------------------------------------------------------
# Clasi-specific settings helpers (read .clasi/settings.yaml)
# ---------------------------------------------------------------------------


def _load_settings(project_root: Path | None = None) -> dict:
    """Load .clasi/settings.yaml as a dict.

    Falls back to legacy locations for repos that have not yet migrated.
    Returns an empty dict if the file doesn't exist or can't be parsed.
    """
    if project_root is None:
        project_root = Path.cwd()

    settings_path = project_root / ".clasi" / "settings.yaml"
    if not settings_path.exists():
        settings_path = project_root / "docs" / "clasi" / "settings.yaml"
    if not settings_path.exists():
        settings_path = project_root / "docs" / "plans" / "settings.yaml"
    if not settings_path.exists():
        return {}

    try:
        data = yaml.safe_load(settings_path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    return data if isinstance(data, dict) else {}


def load_version_format(project_root: Path | None = None) -> str:
    """Load the version format from .clasi/settings.yaml.

    Falls back to DEFAULT_FORMAT if the file or key doesn't exist.
    """
    return _load_settings(project_root).get("version_format", DEFAULT_FORMAT)


def load_version_trigger(project_root: Path | None = None) -> str:
    """Load the version trigger from .clasi/settings.yaml.

    Returns one of: 'manual', 'every_sprint', 'every_change'.
    Falls back to DEFAULT_TRIGGER ('every_change') if not set.
    """
    trigger = _load_settings(project_root).get("version_trigger", DEFAULT_TRIGGER)
    if trigger not in VALID_TRIGGERS:
        return DEFAULT_TRIGGER
    return trigger


def should_version(trigger: str, context: str) -> bool:
    """Determine whether to update the version based on trigger and context.

    Args:
        trigger: The version_trigger setting value.
        context: What just happened — 'sprint_close' or 'change'.

    Returns True if the version should be updated.
    """
    if trigger == "manual":
        return False
    if trigger == "every_sprint":
        return context == "sprint_close"
    if trigger == "every_change":
        return True
    return False


def load_version_source(project_root: Path | None = None) -> str | None:
    """Load the version_source setting.

    Returns the configured source file path, or None for auto-detect.
    """
    return _load_settings(project_root).get("version_source")


def load_version_sync(project_root: Path | None = None) -> list[str]:
    """Load the version_sync setting.

    Returns a list of file paths to sync the version into after a bump.
    """
    val = _load_settings(project_root).get("version_sync")
    if isinstance(val, list):
        return [str(v) for v in val]
    return []


# ---------------------------------------------------------------------------
# Clasi-specific version file detection
# ---------------------------------------------------------------------------


def _file_type_for(path: Path) -> str:
    """Determine the version file type from a file path."""
    name = path.name
    if name == "pyproject.toml":
        return "pyproject"
    if name == "package.json":
        return "package_json"
    raise ValueError(f"Unknown version file type for {name}")


def detect_version_file(project_root: Path) -> tuple[Path, str] | None:
    """Detect the project's version file by checking known filenames.

    Checks version_source setting first, then falls back to auto-detect
    in priority order: pyproject.toml, package.json.
    """
    source = load_version_source(project_root)
    if source:
        path = project_root / source
        if path.exists():
            return (path, _file_type_for(path))

    for filename, file_type in _VERSION_FILES:
        path = project_root / filename
        if path.exists():
            return (path, file_type)
    return None


def read_current_version(project_root: Path | None = None) -> str | None:
    """Read the current version string from the project's version file.

    Returns the version string, or None if no version file is found.
    """
    if project_root is None:
        project_root = Path.cwd()

    result = detect_version_file(project_root)
    if result is None:
        return None

    path, file_type = result
    if file_type == "pyproject":
        content = path.read_text(encoding="utf-8")
        m = re.search(r'^version\s*=\s*"([^"]*)"', content, re.MULTILINE)
        return m.group(1) if m else None
    elif file_type == "package_json":
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("version")
    return None


def sync_version(version: str, project_root: Path | None = None) -> list[str]:
    """Write the version to all sync files listed in settings.

    Returns a list of paths that were updated.
    """
    if project_root is None:
        project_root = Path.cwd()

    sync_files = load_version_sync(project_root)
    updated = []
    for rel_path in sync_files:
        path = project_root / rel_path
        if not path.exists():
            continue
        file_type = _file_type_for(path)
        update_version_file(path, file_type, version)
        updated.append(rel_path)
    return updated


# ---------------------------------------------------------------------------
# compute_next_version wrapper
#
# Dotconfig's compute_next_version reads format from config/dotconfig.yaml.
# Clasi projects store format in .clasi/settings.yaml.  This wrapper reads
# the clasi format and calls dotconfig's lower-level helpers directly so
# that the clasi config wins without any monkey-patching.
# ---------------------------------------------------------------------------


def _get_existing_tags(project_root: Path | None = None) -> list[str]:
    """Return all git tags in the repository rooted at *project_root*.

    Args:
        project_root: Repository root to run ``git tag -l`` in. Defaults
            to ``Path.cwd()`` when omitted, matching the previous
            implicit-cwd behavior for standalone callers -- but any
            caller that already has a resolved project root (e.g.
            :func:`compute_next_version`) should pass it explicitly
            rather than relying on the MCP server process's own working
            directory happening to already be the project root.
    """
    from clasi.gitutil import run_git

    cwd = project_root if project_root is not None else Path.cwd()
    result = run_git(["tag", "-l"], cwd=cwd)
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def compute_next_version(major: int = 0, project_root: Path | None = None) -> str:
    """Compute the next version string based on existing git tags.

    Reads the version format from .clasi/settings.yaml (clasi-specific).
    For formats with auto-computed segments (date, revision), scans git
    tags to find the next revision number.  For fully manual formats,
    returns the major values joined by dots.

    Args:
        major: Major version segment.
        project_root: Repository/project root to resolve the version
            format setting, git tags, and the current version file
            against. Defaults to ``Path.cwd()`` when omitted -- callers
            that already have a ``Project`` (e.g. the MCP tools layer)
            should pass ``project.root`` explicitly instead of relying
            on the server process's own cwd matching the project.
    """
    fmt = load_version_format(project_root)
    parsed = parse_format(fmt)

    if not format_has_auto(parsed):
        # Fully manual format — return manual values as-is
        manual_count = sum(1 for k, _, _ in parsed if k == "manual")
        values = [major] + [0] * (manual_count - 1)
        return build_version(parsed, values)

    today = date.today()
    today_str = today.strftime("%Y%m%d")
    tag_pattern = build_tag_regex(parsed)

    def _extract_rev(candidate: str) -> int | None:
        m = tag_pattern.match(candidate.lstrip("v"))
        if not m:
            return None

        # Check manual segments match
        manual_idx = 0
        for kind, _, _ in parsed:
            if kind == "manual":
                tag_val = int(m.group(f"manual_{manual_idx}"))
                expected = major if manual_idx == 0 else 0
                if tag_val != expected:
                    return None
                manual_idx += 1

        # Check date segments match today
        tag_date = ""
        if "year" in m.groupdict():
            tag_date += m.group("year")
        if "month" in m.groupdict():
            tag_date += m.group("month")
        if "day" in m.groupdict():
            tag_date += m.group("day")

        if tag_date and tag_date != today_str[: len(tag_date)]:
            return None

        if "rev" in m.groupdict():
            return int(m.group("rev"))
        return None

    max_rev = 0
    for tag in _get_existing_tags(project_root):
        rev = _extract_rev(tag)
        if rev is not None:
            max_rev = max(max_rev, rev)

    # Also consider the version currently in the project's version file,
    # so consecutive bumps advance even when --tag is not used.
    current = read_current_version(project_root)
    if current:
        rev = _extract_rev(current)
        if rev is not None:
            max_rev = max(max_rev, rev)

    manual_count = sum(1 for k, _, _ in parsed if k == "manual")
    values = [major] + [0] * (manual_count - 1)
    return build_version(parsed, values, rev=max_rev + 1, today=today)


# ---------------------------------------------------------------------------
# bump_version adapter (retained for external callers)
# ---------------------------------------------------------------------------


def bump_version(major: int = 0, tag: bool = False) -> dict:
    """Compute the next version, update all version files, and optionally tag.

    This is the main entry point for ``clasi version bump``.

    Returns a dict with keys: version, source, synced, tag.
    """
    project_root = Path.cwd()
    version = compute_next_version(major, project_root)

    # Update source file
    result = detect_version_file(project_root)
    source_path = None
    if result:
        path, file_type = result
        update_version_file(path, file_type, version)
        source_path = str(path.relative_to(project_root))

    # Sync to other files
    synced = sync_version(version, project_root)

    # Tag
    tag_name = None
    if tag:
        create_version_tag(version)
        tag_name = f"v{version}"

    return {
        "version": version,
        "source": source_path,
        "synced": synced,
        "tag": tag_name,
    }
