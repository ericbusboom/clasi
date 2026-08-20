"""Shared MCP tool infrastructure: the ``@clasi_tool`` decorator and
``resolve_artifact_path`` (sprint 030 ticket 005).

Owns three things every ``@server.tool()`` function used to get (if it got
them at all) through a monkey-patch over private ``mcp``-library internals
(``mcp_server.py``'s old ``_tool_manager.call_tool`` wrapper, removed by
this ticket):

1. **"NONE"-sentinel stripping.** Agents pass the literal string
   ``"NONE"`` for an omitted optional parameter, working around a Claude
   Code harness bug that silently drops *all* tool-call arguments when
   any one of them is empty or null (see
   ``.claude/rules/tool-call-empty-args.md``). ``@clasi_tool`` strips
   this sentinel back to ``None`` per-call, in code this package owns —
   no dependency on ``mcp``-library private attributes that a future
   ``mcp`` 2.x upgrade could silently stop patching (that would be a
   fail-open, not a crash: ``"NONE"`` strings would start landing in
   frontmatter and shell commands unnoticed).
2. **A uniform failure envelope.** On success, the wrapped function's
   own return value passes through completely unchanged — this is
   SUC-005's own Main Flow step 3 ("On success, the tool returns its
   normal result") and matches the reliability review's F15 fix
   description verbatim ("converts domain exceptions to a single
   `{"ok": false, "error": {...}}` shape"; nothing there wraps success).
   On a caught exception, ``@clasi_tool`` returns exactly one shape:
   ``{"ok": false, "error": {"type": "<ExceptionClassName>", "message":
   "<str(exc)>"}}``, produced when the wrapped function raises
   ``ValueError``, ``FileNotFoundError``, or one of the artifact model's
   own exception types (``SprintNotFoundError``, ``SprintFrontmatterError``,
   ``SprintIdMismatchError``, ``MalformedFrontmatterError`` — all already
   ``ValueError`` subclasses, so catching ``ValueError`` covers them
   without an explicit import). Any other exception (a genuine bug, not a
   domain error) is left to propagate, surfacing as a real MCP tool
   error — unchanged from today's behavior for that class of failure.

   **Shape decision (sprint.md Open Question 5, left open there
   deliberately, "nested under a key vs. merged alongside existing
   fields"):** that choice is exercised only for the *failure* shape, and
   resolved as nested (``{"error": {...}}``, not fields merged directly
   onto a payload that in the failure case does not exist — the wrapped
   function raised before producing one). On success, nothing is wrapped
   at all, for two concrete reasons found while implementing this ticket,
   not just the Main Flow wording above: (a) **merging is unsafe in
   general** — ``validate_design`` already returns ``{"ok": <did
   validation pass>, "messages": [...], "info": [...]}``; merging an
   envelope-level ``"ok": true`` on top would silently overwrite that
   domain-level ``"ok"`` (whether *validation* passed) the moment the
   *call* succeeded, masking a real validation failure — the exact
   silent-failure class this ticket exists to eliminate, not reintroduce;
   (b) **nesting success uniformly is prohibitively invasive** — a repo
   scan while implementing this ticket found north of 350
   ``json.loads(<tool call>)`` call sites across 28 test files asserting
   directly on today's un-enveloped success shape; renesting every tool's
   success payload would mean rewriting that entire surface for a change
   with no corresponding entry in this ticket's own `Files to modify`
   list, in direct tension with "implement what the plan says, not more."
   Leaving success un-enveloped keeps the postcondition SUC-005 actually
   cares about intact: an agent checks for a top-level ``{"ok": false,
   "error": {...}}`` shape to learn a call failed; its absence means the
   call succeeded and the payload is whatever that specific tool has
   always returned — one failure contract instead of three, without a
   47-tool, 28-test-file payload-schema migration this ticket did not
   scope.
3. **The ``mcp-calls.jsonl`` per-call trace**, reusing
   ``_write_call_trace`` (originally written in sprint 028 specifically
   to be liftable here "without rewriting it" — see its own docstring)
   unchanged, moved rather than duplicated. The E2E run report reads
   this file; its record shape (``ts``, ``agent``, ``tool``, ``args``,
   ``ok``, ``ms``, ``result_len``) is unchanged by this move.

Composition: every tool function is decorated as ``@server.tool()`` over
``@clasi_tool`` over the function body, e.g.::

    @server.tool()
    @clasi_tool
    def some_tool(x: str) -> str:
        ...

``@clasi_tool`` is applied first (innermost), so ``@server.tool()`` sees
the wrapper ``functools.wraps`` produces. FastMCP's own schema
introspection (``inspect.signature(fn, eval_str=True)``, called on the
wrapper) follows ``functools.wraps``' ``__wrapped__`` attribute by
default, so it still sees the *original* function's parameter names,
types, and defaults — the wrapper's own ``(*args, **kwargs)`` signature
is never exposed to callers.

Also holds ``resolve_artifact_path``, relocated verbatim from
``artifact_tools.py`` (already root-anchored since sprint 029 — this is
a pure move, no behavior change). Deliberately does *not* hold
``gitutil.run_git``: see sprint 030's sprint.md Design Rationale for why
that stays a top-level leaf module shared by both the tools layer and
core modules (``sprint.py``, ``design/overlay.py``) instead of being
absorbed here, which would invert the tools-wraps-core dependency
direction.
"""

from __future__ import annotations

import functools
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TypeVar

logger = logging.getLogger("clasi.mcp")

# ValueError covers every "artifact model's own exception type" already
# (SprintNotFoundError, SprintFrontmatterError, SprintIdMismatchError in
# project.py, and MalformedFrontmatterError in frontmatter.py are all
# ValueError subclasses) -- no need to import them explicitly here.
_DOMAIN_EXCEPTIONS = (ValueError, FileNotFoundError)

F = TypeVar("F", bound=Callable[..., str])


def _strip_none_sentinel(arguments: dict) -> dict:
    """Return a new dict with every value equal to the string ``"NONE"`` replaced by ``None``.

    Agents pass the literal string ``"NONE"`` for optional parameters to work
    around the Claude Code harness bug that silently drops all arguments when any
    argument is empty or null.  This helper converts that sentinel back to
    ``None`` so tool functions receive the expected Python value.

    The input dict is never mutated; a new dict is always returned.

    Relocated verbatim from ``mcp_server.py`` (sprint 030 ticket 005) — no
    behavior change, only the owning module.
    """
    return {k: (None if v == "NONE" else v) for k, v in arguments.items()}


def _write_call_trace(
    log_dir: Path,
    *,
    agent: str,
    tool: str,
    args: dict,
    ok: bool,
    ms: int,
    result_len: int | None,
) -> None:
    """Append one JSONL record for a single MCP tool call to ``mcp-calls.jsonl``.

    Relocated verbatim from ``mcp_server.py`` (sprint 030 ticket 005) — this
    is the same self-contained, plain-value helper written in sprint 028
    specifically so it could be lifted into this decorator "without
    rewriting it"; that promise is kept here.

    Ensures ``log_dir`` is covered by the existing log-dir gitignore
    mechanism (``hook_handlers._ensure_log_gitignore``) before writing.
    """
    from clasi.hook_handlers import _ensure_log_gitignore

    log_dir.mkdir(parents=True, exist_ok=True)
    _ensure_log_gitignore(log_dir)

    record = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "agent": agent,
        "tool": tool,
        "args": args,
        "ok": ok,
        "ms": ms,
        "result_len": result_len,
    }
    trace_file = log_dir / "mcp-calls.jsonl"
    with open(trace_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def resolve_artifact_path(path: str) -> Path:
    """Find a file whether it's in its original location or a done/ subdirectory.

    A relative *path* is anchored to ``project.root`` (not the process's
    own cwd) before any existence check runs, so a natural root-relative
    artifact path (e.g. a ticket path returned by another tool) resolves
    correctly regardless of what directory the MCP server process happens
    to be sitting in. Absolute paths are used as-is.

    Resolution order:
    1. Given path as-is
    2. Insert done/ before the filename (e.g., tickets/001.md -> tickets/done/001.md)
    3. Remove done/ from the path (e.g., tickets/done/001.md -> tickets/001.md)

    Returns the resolved Path.
    Raises FileNotFoundError if none of the candidates exist.

    Relocated verbatim from ``artifact_tools.py`` (sprint 030 ticket 005) —
    already root-anchored since sprint 029, so this is a pure move with no
    behavior change.
    """
    from clasi.mcp_server import get_project

    p = Path(path)
    p = p if p.is_absolute() else get_project().root / p
    if p.exists():
        return p

    # Try inserting done/ before the filename
    with_done = p.parent / "done" / p.name
    if with_done.exists():
        return with_done

    # Try removing done/ from the path
    parts = p.parts
    if "done" in parts:
        without_done = Path(*[part for part in parts if part != "done"])
        if without_done.exists():
            return without_done

    raise FileNotFoundError(
        f"Artifact not found: {path} (also checked done/ variants)"
    )


def _summarize_args(args: tuple, kwargs: dict) -> dict:
    """Build the truncated args dict the call trace records.

    Positional args (rare — FastMCP always calls with keyword arguments;
    this only matters for tests/direct calls) are recorded under
    ``arg0``, ``arg1``, etc. so no call is silently untraced.
    """
    summary: dict[str, str] = {}
    for i, a in enumerate(args):
        s = str(a)
        summary[f"arg{i}"] = s[:200] + "..." if len(s) > 200 else s
    for k, v in kwargs.items():
        s = str(v)
        summary[k] = s[:200] + "..." if len(s) > 200 else s
    return summary


def clasi_tool(func: F) -> F:
    """Wrap a tool function with NONE-stripping, the uniform envelope, and call tracing.

    See this module's own docstring for the full contract (envelope shape,
    which exceptions are caught, why). Composed as ``@server.tool()`` over
    ``@clasi_tool`` over the tool function.
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> str:
        from clasi.mcp_server import get_project

        # Strip the "NONE" sentinel in code this package owns -- no
        # monkey-patched mcp-library internal involved. FastMCP always
        # calls tool functions with keyword arguments (see
        # FuncMetadata.call_fn_with_arg_validation), but positional args
        # are stripped too so direct/test calls behave identically.
        args = tuple(None if a == "NONE" else a for a in args)
        kwargs = _strip_none_sentinel(kwargs)

        agent_name = os.environ.get("CLASI_AGENT_NAME", "team-lead")
        args_summary = _summarize_args(args, kwargs)
        tool_name = func.__name__

        start = time.monotonic()
        try:
            raw = func(*args, **kwargs)
        except _DOMAIN_EXCEPTIONS as e:
            ms = int((time.monotonic() - start) * 1000)
            out = json.dumps(
                {"ok": False, "error": {"type": type(e).__name__, "message": str(e)}},
                indent=2,
            )
            _write_call_trace(
                get_project().log_dir, agent=agent_name, tool=tool_name,
                args=args_summary, ok=False, ms=ms, result_len=len(out),
            )
            return out

        ms = int((time.monotonic() - start) * 1000)

        # Success: pass the wrapped function's own return value through
        # unchanged (see this module's docstring, point 2, for why the
        # envelope applies only to the failure shape).
        result_len = len(raw) if isinstance(raw, str) else None
        _write_call_trace(
            get_project().log_dir, agent=agent_name, tool=tool_name,
            args=args_summary, ok=True, ms=ms, result_len=result_len,
        )
        return raw

    return wrapper  # type: ignore[return-value]
