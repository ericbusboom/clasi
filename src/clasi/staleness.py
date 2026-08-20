"""Detect a stale running CLASI install.

``get_version()`` (``clasi.tools.process_tools``) already surfaces
``version`` (cached at import), ``metadata_version`` (live from
``importlib.metadata``), and ``source_path`` (resolved module origin)
"so staleness is detectable" — its own docstring says so. Nothing acted
on that until this module.

Three independent signals are checked. Signals 1 and 3 are general
purpose — they never assume the served project *is* the CLASI repo
itself; only signal 2 does:

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
3. **Same-version drift**: the newest ``.py`` file mtime under the
   *running* ``clasi`` package's own directory
   (``Path(clasi.__file__).parent``) is compared against
   ``clasi._IMPORT_TIME`` (recorded once, when this process first
   imported ``clasi``). Signals 1 and 2 both depend on a version string
   or an install-path mismatch — neither trips for the single most
   common real drift: an editable install whose source was edited
   *after* a long-lived process (``clasi mcp``) imported it, with no
   version bump. ``__version__``/``metadata_version`` stay identical in
   that case, so signals 1 and 2 report a clean bill of health while the
   process keeps serving pre-edit code. Signal 3 needs no hashing and no
   version comparison — any post-import source edit trips it,
   regardless of what the version strings say. Like signal 1, it applies
   to every process that imports ``clasi``, not just CLASI-on-CLASI.

Consumer projects that merely depend on CLASI never satisfy signal 2's
precondition, so they only ever see signals 1 and 3 — both of which are
real staleness conditions worth reporting regardless of which project is
being served.
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import re
from dataclasses import dataclass
from pathlib import Path

import clasi


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


def _newest_source_file_since(
    package_dir: Path, since: float
) -> tuple[str, float] | None:
    """Return ``(path, mtime)`` of the newest ``.py`` file under *package_dir*
    modified after *since*, or None if none is newer (or the scan fails).

    Scoped to *package_dir* only (the running ``clasi`` package's own
    directory, not the whole host repo), so the walk is small and bounded
    regardless of what project this check is serving. ``__pycache__``
    entries are skipped explicitly (belt-and-suspenders — compiled
    ``.pyc`` files never match the ``*.py`` glob anyway, but this keeps
    generated-file directories out of consideration if that ever
    changes).

    Never raises: this is called from ``check_staleness``, which is in
    turn called with no surrounding exception handling from the
    role-guard and mcp-guard hook paths (see ticket 029-007). Any error
    while walking or stat-ing a path — an unreadable directory, a broken
    symlink, a permission error, or anything else — degrades this signal
    to "not available" (returns None) rather than propagating, matching
    the fail-open design of signals 1 and 2 elsewhere in this module.
    """
    try:
        newest_path: str | None = None
        newest_mtime = since
        for py_file in package_dir.rglob("*.py"):
            if "__pycache__" in py_file.parts:
                continue
            try:
                mtime = py_file.stat().st_mtime
            except OSError:
                continue
            if mtime > newest_mtime:
                newest_mtime = mtime
                newest_path = str(py_file)
    except Exception:
        return None
    return (newest_path, newest_mtime) if newest_path is not None else None


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

    # Signal 3: same-version drift — see this module's docstring. Applies
    # unconditionally (not gated on project_root at all: it only looks at
    # the running clasi package's own directory), so unlike signal 2 this
    # fires for consumer projects too, same as signal 1.
    package_file = getattr(clasi, "__file__", None)
    import_time = getattr(clasi, "_IMPORT_TIME", None)
    if package_file and import_time is not None:
        newest = _newest_source_file_since(Path(package_file).parent, import_time)
        if newest is not None:
            newest_path, newest_mtime = newest
            reasons.append(
                f"source file {newest_path} was modified after this "
                f"process imported clasi (mtime {newest_mtime:.0f} > "
                f"import time {import_time:.0f}) — the running process "
                "has stale in-memory code even though its version string "
                "has not changed; restart it."
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
