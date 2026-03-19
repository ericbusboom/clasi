"""Versioning utilities for the CLASI project.

Supports configurable version formats via docs/clasi/settings.yaml.

Default format: X+.YYYYMMDD.R+

Format tokens:
    X      — manual segment, exactly 1 digit
    XX     — manual segment, exactly 2 digits
    X+     — manual segment, one or more digits (variable width)
    0XX    — manual segment, exactly 2 digits, zero-padded
    0XXX   — manual segment, exactly 3 digits, zero-padded
    YYYY   — four-digit year
    MM     — two-digit month
    DD     — two-digit day
    R      — auto-incrementing revision, exactly 1 digit
    RR     — revision, exactly 2 digits
    R+     — revision, one or more digits (variable width)
    0RR    — revision, exactly 2 digits, zero-padded
    0RRR   — revision, exactly 3 digits, zero-padded
    .      — literal dot separator

Fully manual formats (no R or date tokens) produce X.X.X style versions
that are not auto-computed.
"""

import json
import re
import subprocess
from datetime import date
from pathlib import Path

import yaml

DEFAULT_FORMAT = "X+.YYYYMMDD.R+"

# Priority-ordered list of version file names and their types.
_VERSION_FILES: list[tuple[str, str]] = [
    ("pyproject.toml", "pyproject"),
    ("package.json", "package_json"),
]

# --- Format parsing ---

# Token pattern: longest match first.
# Order matters: try 0-prefixed multi-char first, then multi-char, then
# single+plus, then single, then date tokens, then dot.
_TOKEN_RE = re.compile(
    r"(0X{2,}|0R{2,}|X{2,}|R{2,}|X\+|R\+|X|R|YYYY|MM|DD|\.)"
)


def _classify_token(tok: str) -> tuple[str, int, bool]:
    """Classify a format token.

    Returns (kind, width, zero_pad).
    kind: 'manual', 'year', 'month', 'day', 'rev', 'dot'
    width: exact digit count, or 0 for variable-width (+ suffix)
    zero_pad: True if the output should be zero-padded to width
    """
    if tok == ".":
        return ("dot", 0, False)
    if tok == "YYYY":
        return ("year", 4, True)
    if tok == "MM":
        return ("month", 2, True)
    if tok == "DD":
        return ("day", 2, True)
    # X+ or R+ — variable width
    if tok == "X+":
        return ("manual", 0, False)
    if tok == "R+":
        return ("rev", 0, False)
    # 0XX, 0XXX — zero-padded manual
    if tok.startswith("0") and all(c == "X" for c in tok[1:]):
        return ("manual", len(tok) - 1, True)
    # XX, XXX — exact width manual
    if all(c == "X" for c in tok):
        return ("manual", len(tok), False)
    # 0RR, 0RRR — zero-padded rev
    if tok.startswith("0") and all(c == "R" for c in tok[1:]):
        return ("rev", len(tok) - 1, True)
    # RR, RRR — exact width rev
    if all(c == "R" for c in tok):
        return ("rev", len(tok), False)
    raise ValueError(f"Unknown version format token: {tok}")


def parse_format(fmt: str) -> list[tuple[str, int, bool]]:
    """Parse a version format string into classified tokens."""
    tokens = _TOKEN_RE.findall(fmt)
    # Verify we consumed the entire format string
    reconstructed = "".join(tokens)
    if reconstructed != fmt:
        raise ValueError(
            f"Invalid version format: {fmt!r} — unrecognized characters "
            f"(parsed as {reconstructed!r})"
        )
    return [_classify_token(t) for t in tokens]


def format_has_auto(parsed: list[tuple[str, int, bool]]) -> bool:
    """Check if the format has any auto-computed segments (date or rev)."""
    return any(k in ("year", "month", "day", "rev") for k, _, _ in parsed)


def _format_segment(value: int, width: int, zero_pad: bool) -> str:
    """Format a numeric segment with optional zero-padding.

    width=0 means variable width (no padding, no truncation).
    width>0 means exactly that many digits — zero-pad if zero_pad is True,
    otherwise just str(value) (may exceed width if the value is large).
    """
    if width == 0:
        return str(value)
    if zero_pad:
        return str(value).zfill(width)
    return str(value)


def build_version(
    parsed: list[tuple[str, int, bool]],
    manual_values: list[int],
    rev: int = 1,
    today: date | None = None,
) -> str:
    """Build a version string from parsed format, manual values, and auto values."""
    if today is None:
        today = date.today()

    parts = []
    manual_idx = 0
    for kind, width, zero_pad in parsed:
        if kind == "dot":
            parts.append(".")
        elif kind == "manual":
            val = manual_values[manual_idx] if manual_idx < len(manual_values) else 0
            manual_idx += 1
            parts.append(_format_segment(val, width, zero_pad))
        elif kind == "year":
            parts.append(str(today.year))
        elif kind == "month":
            parts.append(f"{today.month:02d}")
        elif kind == "day":
            parts.append(f"{today.day:02d}")
        elif kind == "rev":
            parts.append(_format_segment(rev, width, zero_pad))
    return "".join(parts)


def build_tag_regex(parsed: list[tuple[str, int, bool]]) -> re.Pattern:
    """Build a regex that matches version tags for this format.

    Returns a compiled pattern with named groups for manual segments
    (manual_0, manual_1, ...), date segments (year, month, day),
    and revision (rev).
    """
    parts = ["^v?"]
    manual_idx = 0
    for kind, width, zero_pad in parsed:
        if kind == "dot":
            parts.append(r"\.")
        elif kind == "manual":
            if width == 0:
                parts.append(f"(?P<manual_{manual_idx}>\\d+)")
            else:
                parts.append(f"(?P<manual_{manual_idx}>\\d{{{width}}})")
            manual_idx += 1
        elif kind == "year":
            parts.append(r"(?P<year>\d{4})")
        elif kind == "month":
            parts.append(r"(?P<month>\d{2})")
        elif kind == "day":
            parts.append(r"(?P<day>\d{2})")
        elif kind == "rev":
            if width == 0:
                parts.append(r"(?P<rev>\d+)")
            else:
                parts.append(f"(?P<rev>\\d{{{width}}})")
    parts.append("$")
    return re.compile("".join(parts))


# --- Settings ---

def load_version_format(project_root: Path | None = None) -> str:
    """Load the version format from docs/clasi/settings.yaml.

    Falls back to DEFAULT_FORMAT if the file or key doesn't exist.
    """
    if project_root is None:
        project_root = Path.cwd()

    settings_path = project_root / "docs" / "clasi" / "settings.yaml"
    if not settings_path.exists():
        # Try legacy path
        settings_path = project_root / "docs" / "plans" / "settings.yaml"
    if not settings_path.exists():
        return DEFAULT_FORMAT

    try:
        data = yaml.safe_load(settings_path.read_text(encoding="utf-8"))
    except Exception:
        return DEFAULT_FORMAT

    if not isinstance(data, dict):
        return DEFAULT_FORMAT

    return data.get("version_format", DEFAULT_FORMAT)


# --- Legacy compat ---

# Keep VERSION_PATTERN for backward compatibility with existing code
# that imports it directly
VERSION_PATTERN = re.compile(r"^v?(\d+)\.(\d{8})\.(\d+)$")


# --- Core API ---

def _get_existing_tags() -> list[str]:
    """Return all git tags in the current repository."""
    result = subprocess.run(
        ["git", "tag", "-l"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def compute_next_version(major: int = 0) -> str:
    """Compute the next version string based on existing git tags.

    Reads the version format from project settings. For formats with
    auto-computed segments (date, revision), scans git tags to find
    the next revision number. For fully manual formats, returns the
    major values joined by dots.
    """
    fmt = load_version_format()
    parsed = parse_format(fmt)

    if not format_has_auto(parsed):
        # Fully manual format — return manual values as-is
        manual_count = sum(1 for k, _, _ in parsed if k == "manual")
        values = [major] + [0] * (manual_count - 1)
        return build_version(parsed, values)

    today = date.today()
    today_str = today.strftime("%Y%m%d")
    tag_pattern = build_tag_regex(parsed)

    max_rev = 0
    for tag in _get_existing_tags():
        m = tag_pattern.match(tag.lstrip("v"))
        if not m:
            continue

        # Check manual segments match
        manual_idx = 0
        match = True
        for kind, _, _ in parsed:
            if kind == "manual":
                tag_val = int(m.group(f"manual_{manual_idx}"))
                expected = major if manual_idx == 0 else 0
                if tag_val != expected:
                    match = False
                    break
                manual_idx += 1
        if not match:
            continue

        # Check date segments match today
        tag_date = ""
        if "year" in m.groupdict():
            tag_date += m.group("year")
        if "month" in m.groupdict():
            tag_date += m.group("month")
        if "day" in m.groupdict():
            tag_date += m.group("day")

        if tag_date and tag_date != today_str[:len(tag_date)]:
            continue

        if "rev" in m.groupdict():
            max_rev = max(max_rev, int(m.group("rev")))

    manual_count = sum(1 for k, _, _ in parsed if k == "manual")
    values = [major] + [0] * (manual_count - 1)
    return build_version(parsed, values, rev=max_rev + 1, today=today)


def detect_version_file(project_root: Path) -> tuple[Path, str] | None:
    """Detect the project's version file by checking known filenames.

    Returns (path, file_type) or None if no version file is found.
    Checks in priority order: pyproject.toml, package.json.
    """
    for filename, file_type in _VERSION_FILES:
        path = project_root / filename
        if path.exists():
            return (path, file_type)
    return None


def update_pyproject_version(version: str, pyproject_path: Path) -> None:
    """Update the version field in pyproject.toml."""
    content = pyproject_path.read_text(encoding="utf-8")
    updated = re.sub(
        r'^version\s*=\s*"[^"]*"',
        f'version = "{version}"',
        content,
        count=1,
        flags=re.MULTILINE,
    )
    if updated == content:
        raise ValueError(f"Could not find version field in {pyproject_path}")
    pyproject_path.write_text(updated, encoding="utf-8")


def update_package_json_version(version: str, package_path: Path) -> None:
    """Update the version field in package.json."""
    content = package_path.read_text(encoding="utf-8")
    data = json.loads(content)
    if "version" not in data:
        raise ValueError(f"No 'version' field in {package_path}")
    data["version"] = version
    package_path.write_text(
        json.dumps(data, indent=2) + "\n", encoding="utf-8"
    )


def update_version_file(path: Path, file_type: str, version: str) -> None:
    """Update the version in the detected file, dispatching by type."""
    if file_type == "pyproject":
        update_pyproject_version(version, path)
    elif file_type == "package_json":
        update_package_json_version(version, path)
    else:
        raise ValueError(f"Unknown version file type: {file_type}")


def create_version_tag(version: str) -> None:
    """Create a git tag for the given version."""
    tag_name = f"v{version}"
    result = subprocess.run(
        ["git", "tag", tag_name],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to create tag {tag_name}: {result.stderr.strip()}")
