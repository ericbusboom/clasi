"""
clasi/platforms/_manifest.py

Single-tenant install manifest I/O for the Claude platform installer.

Ported and simplified from the archived `clasr` fork's
`src/clasr/manifest.py` (see `git show archive/clasr:src/clasr/manifest.py`).
`clasr` keyed each manifest by `provider`, because one host directory
(e.g. `.claude/`) could hold content written by several distinct provider
packages layered together. `clasi` has exactly one installer identity, so
that dimension is dropped here: there is one manifest file, not one per
provider, and none of this module's functions take a `provider` argument.

The manifest lives directly inside the platform directory it describes:

    <platform_dir>/.clasi-manifest.json

Schema (version 1)::

    {
        "version": 1,
        "entries": [
            {"path": ".claude/skills/se/SKILL.md", "kind": "skill-alias"},
            {"path": ".claude/agents/team-lead/agent.md", "kind": "agent-file"},
            {"path": ".claude/rules/mcp-required.md", "kind": "rule-file"},
            {"path": "CLAUDE.md", "kind": "marker-block"},
            {"path": ".claude/settings.local.json", "kind": "permission", "value": "mcp__clasi__*"}
        ]
    }

`kind` and any extra fields are defined and interpreted by the caller
(`clasi.platforms.claude`); this module only reads and writes the
document as opaque JSON.

Writes are atomic: serialize to `<file>.tmp` in the same directory, then
`os.replace` onto the final path — the same crash-safety pattern sprint
029 established for frontmatter writes. A crash or interrupt during the
write cannot leave a partial manifest at the final path.

API:
    manifest_path(platform_dir: Path) -> Path
    write_manifest(platform_dir: Path, manifest: dict) -> None
    read_manifest(platform_dir: Path) -> dict | None
    delete_manifest(platform_dir: Path) -> bool

No imports from clasi — this is a leaf module, matching `clasr.manifest`'s
own boundary rule (see `_links.py`, `_markers.py`, `_rules.py` for the
same convention elsewhere in this package).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional


def manifest_path(platform_dir: Path) -> Path:
    """Return the path to the manifest file inside *platform_dir*.

    Path: ``<platform_dir>/.clasi-manifest.json`` — for the Claude
    platform, *platform_dir* is ``<target>/.claude``, so this resolves to
    ``.claude/.clasi-manifest.json``.
    """
    return platform_dir / ".clasi-manifest.json"


def write_manifest(platform_dir: Path, manifest: dict) -> None:
    """Write *manifest* atomically to ``<platform_dir>/.clasi-manifest.json``.

    *platform_dir* is created if it does not exist.

    Atomicity is guaranteed by writing to a ``.tmp`` file in the same
    directory and then calling ``os.replace`` to move it to the final
    path. A crash or interrupt during the write cannot leave a partial
    manifest at the final path.
    """
    final = manifest_path(platform_dir)
    final.parent.mkdir(parents=True, exist_ok=True)

    tmp = final.with_suffix(".tmp")
    tmp.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    os.replace(tmp, final)


def read_manifest(platform_dir: Path) -> Optional[dict]:
    """Return the parsed manifest dict, or ``None`` if it does not exist.

    A malformed manifest (invalid JSON) is NOT swallowed here — this
    mirrors `clasr.manifest.read_manifest`'s own behavior, which only
    catches the missing-file case. Callers that need to treat corrupt
    JSON as "no manifest" (this project's uninstall fallback does) catch
    ``json.JSONDecodeError`` themselves at the call site.
    """
    path = manifest_path(platform_dir)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def delete_manifest(platform_dir: Path) -> bool:
    """Delete the manifest file inside *platform_dir*.

    Returns ``True`` if the file was deleted, ``False`` if it did not
    exist.
    """
    path = manifest_path(platform_dir)
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False
