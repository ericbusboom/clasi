"""Shared git subprocess helper, anchored to an explicit repository root.

A bare ``subprocess.run(["git", ...])`` call with no ``cwd=`` operates on
whatever directory the *calling process* happens to be in. For CLASI's MCP
server that is not guaranteed to be the project root -- a server launched
from elsewhere, or a process whose cwd drifted for any reason, would run
"git" commands against the wrong repository entirely, silently corrupting
or archiving state that belongs to a different project (see
``docs/reviews/2026-08-reliability/02-mcp-tools.md`` findings F3, F4, F7).

Every git call in the tools layer, ``clasi.sprint``, and
``clasi.design.overlay`` should go through :func:`run_git` rather than
calling ``subprocess.run`` directly, so the working directory is always an
explicit, caller-supplied argument (typically ``project.root``) instead of
an implicit assumption.

Deliberately scoped to exactly this one helper -- not a larger shared
"tools/_common.py" module. That broader decomposition is separate,
not-yet-designed work tracked by the ``uniform-mcp-tool-envelope`` issue.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run ``git <args>`` with an explicit working directory.

    Args:
        args: The git subcommand and its arguments (without the leading
            ``"git"`` itself), e.g. ``["status", "--porcelain"]``.
        cwd: The directory to run the command in. Always required --
            callers must supply it explicitly (typically ``project.root``)
            rather than relying on the calling process's own cwd.

    Returns:
        The completed process, with captured text stdout/stderr. Never
        raises on a non-zero exit code (``check`` is not set) -- callers
        inspect ``.returncode`` themselves, matching the pre-existing
        idiom this helper replaces.
    """
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )
