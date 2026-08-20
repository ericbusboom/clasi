"""CLASI.

MCP server for AI-driven software engineering process.
"""

import time

_cached_version = None

_IMPORT_TIME = time.time()
"""Wall-clock time this process first imported ``clasi``.

Consumed by :mod:`clasi.staleness` (signal 3, same-version drift): a
long-lived process (e.g. ``clasi mcp``) that imports ``clasi`` and then
has its source edited on disk — with no version bump — keeps serving the
old in-memory code while ``__version__``/``metadata_version`` stay
identical, so signals 1 and 2 never fire. Comparing on-disk ``.py`` file
mtimes against this timestamp catches that case regardless of version
strings. Set exactly once, at import; never mutated.
"""


def __getattr__(name):
    """Lazily resolve ``__version__`` on first access (PEP 562).

    A plain ``import clasi`` no longer pays the ~33ms
    ``importlib.metadata.version("clasi")`` scan — every `clasi hook
    <event>` CLI invocation is a fresh, one-shot process that imports
    `clasi` at startup regardless of whether that particular hook
    handler ever touches the real version. Some handlers never do
    (``handle_subagent_start``/``_stop``, ``handle_plan_to_issue``,
    ``handle_codex_plan_to_issue``); others only do it conditionally, on
    the branch that actually calls ``clasi.staleness.check_staleness``
    — the sole current consumer of the real version — via ``from clasi
    import __version__`` inside that function.

    Result is cached in ``_cached_version`` after the first resolution,
    so repeated access within the same process (e.g. multiple staleness
    checks in one hook invocation) does not re-scan metadata.

    Falls back to ``"0.0.0-unknown"`` on any resolution failure (e.g.
    running from source with no installed distribution record) — the
    same fallback the previous eager form used.
    """
    if name != "__version__":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    global _cached_version
    if _cached_version is None:
        try:
            from importlib.metadata import version as _pkg_version
            _cached_version = _pkg_version("clasi")
        except Exception:
            _cached_version = "0.0.0-unknown"
    return _cached_version
