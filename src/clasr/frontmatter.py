"""
clasr/frontmatter.py

Union frontmatter parser and per-platform projector.

The union format allows a single source file to carry frontmatter for all
platforms simultaneously:

    ---
    name: code-review
    description: Review a pull request
    claude:
      tools: [Read, Grep, Bash]
    copilot:
      applyTo: "**/*.ts"
    codex: {}
    ---

API:
    parse_union(source: Path) -> tuple[dict, dict, str]
        Returns (shared_fm, full_fm, body)

    project(full_fm: dict, body: str, platform: str) -> tuple[dict, str]
        Returns (projected_fm, body)

    render_file(source: Path, platform: str) -> str
        Returns full rendered file content (frontmatter + body)

No imports from clasi.
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

import yaml

# The three known platform namespaces stripped from output frontmatter.
_PLATFORM_KEYS = frozenset({"claude", "codex", "copilot"})


def parse_union(source: Path) -> Tuple[dict, dict, str]:
    """Parse union frontmatter from *source*.

    Returns ``(shared_fm, full_fm, body)`` where:

    - ``shared_fm``: top-level frontmatter keys except platform names.
    - ``full_fm``: the complete parsed frontmatter dict (includes platform keys).
    - ``body``: everything after the closing ``---`` delimiter, verbatim.

    If the file has no ``---``-delimited frontmatter, returns
    ``({}, {}, full_content)``.
    """
    content = source.read_text(encoding="utf-8")

    if not content.startswith("---"):
        return {}, {}, content

    # Find the closing --- (must be on its own line after the opening ---)
    first_newline = content.index("\n")
    rest = content[first_newline + 1:]
    # Look for closing --- on its own line
    close_marker = "\n---"
    close_pos = rest.find(close_marker)
    if close_pos == -1:
        # No closing delimiter — treat entire content as body
        return {}, {}, content

    yaml_block = rest[:close_pos]
    # body starts after the closing --- newline
    after_close = rest[close_pos + len(close_marker):]
    # Strip leading newline that follows the closing ---
    if after_close.startswith("\n"):
        body = after_close[1:]
    else:
        body = after_close

    full_fm: dict = yaml.safe_load(yaml_block) or {}

    shared_fm = {k: v for k, v in full_fm.items() if k not in _PLATFORM_KEYS}

    return shared_fm, full_fm, body


def project(full_fm: dict, body: str, platform: str) -> Tuple[dict, str]:
    """Project *full_fm* to a single-platform frontmatter dict.

    The projected dict contains:
    - All shared top-level keys (everything except ``claude``, ``codex``,
      ``copilot``).
    - Merged with the platform-specific nested dict (platform keys override
      shared keys with the same name).
    - All platform-namespace keys are dropped from the output.

    If the platform key is absent in *full_fm*, the output is just the shared
    keys.

    Returns ``(projected_fm, body)``; *body* is returned verbatim.
    """
    shared: dict = {k: v for k, v in full_fm.items() if k not in _PLATFORM_KEYS}
    platform_specific: dict = full_fm.get(platform) or {}
    projected = {**shared, **platform_specific}
    return projected, body


def render_file(source: Path, platform: str) -> str:
    """Render *source* projected to *platform*.

    Returns the complete file content:  YAML frontmatter block delimited by
    ``---``, a blank line, then the verbatim body.

    The output format is::

        ---
        key: value
        ---

        <body>
    """
    _shared_fm, full_fm, body = parse_union(source)
    projected_fm, body = project(full_fm, body, platform)

    yaml_text = yaml.dump(projected_fm, default_flow_style=False, allow_unicode=True)
    # yaml.dump always ends with \n; strip it so we control the delimiter layout.
    yaml_text = yaml_text.rstrip("\n")

    rendered = f"---\n{yaml_text}\n---\n\n{body}"
    return rendered
