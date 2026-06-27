"""
clasr/manifest.py

Per-platform per-provider manifest I/O.

Manifests live inside the platform directory they describe:

    <platform_dir>/.clasr-manifest/<provider>.json

Schema (version 1):
    {
        "version": 1,
        "provider": "myprovider",
        "platform": "claude",
        "source": "/abs/path/to/asr",
        "entries": [
            {"path": ".claude/skills/foo/SKILL.md", "kind": "symlink", "target": "..."},
            {"path": ".claude/agents/bar.md",        "kind": "rendered", "from": "..."},
            {"path": ".claude/settings.json",         "kind": "copy",    "from": "..."},
            {"path": "AGENTS.md",                     "kind": "marker-block", "block": "clasr:myprovider"},
            {"path": ".claude/settings.json",         "kind": "json-merged",  "keys": ["key1", "key2"]}
        ]
    }

Writes are atomic: serialize to <file>.tmp, then os.replace to the final path.
Partial writes are impossible even on crash or interrupt.

API:
    manifest_path(platform_dir: Path, provider: str) -> Path
    write_manifest(platform_dir: Path, provider: str, manifest: dict) -> None
    read_manifest(platform_dir: Path, provider: str) -> dict | None
    delete_manifest(platform_dir: Path, provider: str) -> bool

No imports from clasi.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


def manifest_path(platform_dir: Path, provider: str) -> Path:
    """Return the path to the manifest file for *provider* inside *platform_dir*.

    Path: ``<platform_dir>/.clasr-manifest/<provider>.json``
    """
    return platform_dir / ".clasr-manifest" / f"{provider}.json"


def write_manifest(platform_dir: Path, provider: str, manifest: dict) -> None:
    """Write *manifest* atomically to ``<platform_dir>/.clasr-manifest/<provider>.json``.

    The ``.clasr-manifest/`` directory is created if it does not exist.

    Atomicity is guaranteed by writing to a ``.tmp`` file in the same directory
    and then calling ``os.replace`` to move it to the final path.  A crash or
    interrupt during the write cannot leave a partial manifest at the final path.
    """
    final = manifest_path(platform_dir, provider)
    final.parent.mkdir(parents=True, exist_ok=True)

    tmp = final.with_suffix(".tmp")
    tmp.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    os.replace(tmp, final)


def read_manifest(platform_dir: Path, provider: str) -> dict | None:
    """Return the parsed manifest dict, or ``None`` if the manifest does not exist."""
    path = manifest_path(platform_dir, provider)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def delete_manifest(platform_dir: Path, provider: str) -> bool:
    """Delete the manifest file for *provider*.

    Returns ``True`` if the file was deleted, ``False`` if it did not exist.
    """
    path = manifest_path(platform_dir, provider)
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False
