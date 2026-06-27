"""
clasi/platforms/_links.py

Symlink-with-copy-fallback helper for cross-platform alias management.

This module is a leaf node: it has no CLASI imports, no platform knowledge,
and performs only file I/O. All three platform installers (claude.py,
codex.py, copilot.py) use this module.
"""

from __future__ import annotations

import os
import shutil
import warnings
from pathlib import Path


def link_or_copy(
    canonical: Path,
    alias: Path,
    copy: bool = False,
) -> str:
    """Create a symlink from *alias* pointing at *canonical*, or copy as fallback.

    Parameters
    ----------
    canonical:
        The authoritative file path.  Must exist before calling this function.
    alias:
        The path where the symlink (or copy) will be created.  Must not
        already exist; the caller is responsible for removing it first if
        needed.
    copy:
        If ``True``, skip the symlink attempt and use ``shutil.copy2``
        directly.  Useful on Windows without Developer Mode or in
        sandboxed CI environments.

    Returns
    -------
    str
        ``"symlink"`` if a symlink was created, ``"copy"`` if a copy was
        made instead.
    """
    alias.parent.mkdir(parents=True, exist_ok=True)

    if copy:
        shutil.copy2(canonical, alias)
        return "copy"

    try:
        os.symlink(canonical, alias)
        return "symlink"
    except OSError as exc:
        warnings.warn(
            f"symlink({canonical!r} -> {alias!r}) failed ({exc}); "
            "falling back to copy.",
            stacklevel=2,
        )
        shutil.copy2(canonical, alias)
        return "copy"


def unlink_alias(alias: Path) -> bool:
    """Remove the symlink or regular file at *alias*.

    The canonical path is never touched.

    Parameters
    ----------
    alias:
        The symlink or copy to remove.

    Returns
    -------
    bool
        ``True`` if the alias existed and was removed, ``False`` if it did
        not exist.
    """
    try:
        alias.unlink()
        return True
    except FileNotFoundError:
        return False


def migrate_to_symlink(canonical: Path, alias: Path) -> str:
    """Convert a legacy copy at *alias* to a symlink pointing at *canonical*.

    Parameters
    ----------
    canonical:
        The authoritative file.
    alias:
        The path to inspect and potentially convert.

    Returns
    -------
    str
        One of:

        ``"already-symlink"``
            *alias* is already a symlink pointing at *canonical*.  No-op.
        ``"migrated"``
            *alias* was a regular file whose content matched *canonical*
            byte-for-byte; it has been replaced by a symlink.
        ``"conflict"``
            *alias* is a regular file whose content does NOT match
            *canonical*.  No changes made; caller decides how to proceed.
        ``"not-found"``
            *alias* does not exist.
    """
    if not alias.exists() and not alias.is_symlink():
        return "not-found"

    if alias.is_symlink():
        # resolve both sides to compare (handles relative vs absolute)
        if alias.resolve() == canonical.resolve():
            return "already-symlink"
        # It's a symlink but points elsewhere — treat as conflict.
        return "conflict"

    # Regular file: compare content.
    if alias.read_bytes() == canonical.read_bytes():
        alias.unlink()
        os.symlink(canonical, alias)
        return "migrated"

    return "conflict"
