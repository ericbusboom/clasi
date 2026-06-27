"""
clasr/links.py

Symlink-with-copy-fallback helper for cross-platform alias management.

This module is a leaf node: it has no clasr or clasi imports, no platform
knowledge, and performs only file I/O. All clasr platform installers use
this module.
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

    # If the alias already exists or is a symlink, remove it first so we can
    # re-create it cleanly (idempotent re-install for the same provider).
    if alias.exists() or alias.is_symlink():
        alias.unlink()

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
