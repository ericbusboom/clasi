"""Detect a stale running CLASI install.

``get_version()`` (``clasi.tools.process_tools``) already surfaces
``version`` (cached at import), ``metadata_version`` (live from
``importlib.metadata``), and ``source_path`` (resolved module origin)
"so staleness is detectable" — its own docstring says so. Nothing acted
on that until this module.

Two independent, general-purpose signals are checked, neither of which
assumes the served project *is* the CLASI repo itself:

1. **In-process drift**: ``__version__`` (bound at import time) differs
   from a live ``importlib.metadata.version("clasi")`` lookup. This means
   the package on disk changed after the current process imported it —
   true for any project consuming any package, not just CLASI-on-CLASI.
2. **Dogfooding drift**: when the *served project's own root* looks like
   the CLASI source repo (a ``pyproject.toml`` with ``[project] name =
   "clasi"`` next to a ``src/clasi/__init__.py``), compare the running
   server's resolved ``source_path`` against that repo's editable
   source file, and compare the running ``metadata_version`` against the
   version string declared in that repo's own ``pyproject.toml``. This
   only ever fires when a checkout of CLASI is serving itself — it does
   not fire for consumer projects, where ``source_path`` legitimately
   points into site-packages/a venv rather than the project tree.

Consumer projects that merely depend on CLASI never satisfy signal 2's
precondition, so they only ever see signal 1 — and only when their own
environment drifted mid-process, which is a real staleness condition
worth reporting regardless of which project it is.
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StalenessReport:
    """Result of a staleness check. ``stale`` is True if any signal fired."""

    stale: bool
    reasons: list[str]
    running_version: str
    running_source_path: str
    metadata_version: str
    repo_version: str | None = None
    repo_source_path: str | None = None

    def warning(self) -> str:
        """Return a human-readable warning naming both versions, or "" if not stale."""
        if not self.stale:
            return ""
        lines = ["STALE CLASI INSTALL DETECTED:"]
        lines.extend(f"  - {r}" for r in self.reasons)
        return "\n".join(lines)


def _read_repo_clasi_version(repo_root: Path) -> str | None:
    """Return the ``[project] version`` declared in *repo_root*'s pyproject.toml.

    Returns None if the file is missing, unparseable, or has no version key.
    Deliberately avoids a tomllib/tomli dependency for this cheap read —
    the version line is a simple ``version = "..."`` assignment under
    ``[project]`` by convention in this repo.
    """
    pyproject = repo_root / "pyproject.toml"
    try:
        text = pyproject.read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    return match.group(1) if match else None


def _is_clasi_source_repo(project_root: Path) -> bool:
    """Return True if *project_root* looks like a CLASI source checkout.

    Generic structural check: a ``pyproject.toml`` declaring
    ``[project] name = "clasi"`` sitting next to a ``src/clasi/__init__.py``.
    True for anyone dogfooding CLASI from its own repo; false for every
    consumer project that merely depends on the ``clasi`` package.
    """
    pyproject = project_root / "pyproject.toml"
    init_py = project_root / "src" / "clasi" / "__init__.py"
    if not pyproject.is_file() or not init_py.is_file():
        return False
    try:
        text = pyproject.read_text(encoding="utf-8")
    except OSError:
        return False
    return bool(re.search(r'^\[project\]', text, re.MULTILINE)) and bool(
        re.search(r'^name\s*=\s*"clasi"', text, re.MULTILINE)
    )


def check_staleness(project_root: Path, running_version: str) -> StalenessReport:
    """Compare the running CLASI install against live/on-disk signals.

    Args:
        project_root: Root of the project the running server/hook is
            serving (i.e. ``Project.root``, not necessarily the CLASI repo).
        running_version: The caller's cached ``__version__`` (bound at
            import time), for comparison against a fresh
            ``importlib.metadata`` lookup.

    Never raises — a failure to introspect ``importlib.metadata`` or the
    module spec is reported as unknown, not stale, so this check can
    never itself break startup.
    """
    reasons: list[str] = []

    try:
        metadata_version = importlib.metadata.version("clasi")
    except importlib.metadata.PackageNotFoundError:
        metadata_version = "unknown"

    spec = importlib.util.find_spec("clasi")
    running_source_path = str(spec.origin) if spec and spec.origin else "unknown"

    # Signal 1: in-process drift. Only meaningful when both sides resolved.
    if (
        metadata_version != "unknown"
        and running_version != "0.0.0-unknown"
        and metadata_version != running_version
    ):
        reasons.append(
            f"running process version ({running_version}) differs from the "
            f"live installed package version ({metadata_version}) — this "
            "process imported clasi before the environment was updated; "
            "restart it."
        )

    # Signal 2: dogfooding drift — only checked when project_root IS the
    # CLASI source repo (never fires for consumer projects).
    repo_version: str | None = None
    repo_source_path: str | None = None
    if _is_clasi_source_repo(project_root):
        repo_version = _read_repo_clasi_version(project_root)
        repo_source_path = str((project_root / "src" / "clasi" / "__init__.py").resolve())

        if repo_version is not None and repo_version != metadata_version:
            reasons.append(
                f"this repo's working tree is at version {repo_version} "
                f"(pyproject.toml) but the running server reports "
                f"metadata_version {metadata_version} — the server is not "
                "running this working tree's code."
            )

        try:
            running_resolved = str(Path(running_source_path).resolve())
        except OSError:
            running_resolved = running_source_path
        if running_source_path != "unknown" and running_resolved != repo_source_path:
            reasons.append(
                f"running source_path ({running_source_path}) does not "
                f"match this repo's editable source ({repo_source_path}) — "
                "the server/hook is running an installed build, not this "
                "working tree."
            )

    return StalenessReport(
        stale=bool(reasons),
        reasons=reasons,
        running_version=running_version,
        running_source_path=running_source_path,
        metadata_version=metadata_version,
        repo_version=repo_version,
        repo_source_path=repo_source_path,
    )
