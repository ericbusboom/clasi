"""Serialization helpers for the CLASI status output dict.

Two public functions:

- :func:`to_yaml` — serialize to YAML (default for CLI and hook surfaces).
- :func:`to_json` — serialize to JSON (default for MCP surface).

Both functions are pure: they accept any dict and return a str.
"""

from __future__ import annotations

import json

import yaml


def to_yaml(d: dict) -> str:
    """Serialize *d* to a YAML string.

    Uses ``sort_keys=False`` to preserve insertion order and
    ``allow_unicode=True`` so non-ASCII characters are not escaped.

    Args:
        d: The status dict (or any serializable dict).

    Returns:
        A YAML string parseable by ``yaml.safe_load``.
    """
    return yaml.dump(d, sort_keys=False, allow_unicode=True)


def to_json(d: dict) -> str:
    """Serialize *d* to a pretty-printed JSON string.

    Uses ``indent=2`` and ``default=str`` so non-JSON-serializable values
    (e.g. ``datetime``, ``Path``) are coerced to their string representation
    rather than raising ``TypeError``.

    Args:
        d: The status dict (or any serializable dict).

    Returns:
        A JSON string parseable by ``json.loads``.
    """
    return json.dumps(d, indent=2, default=str)
