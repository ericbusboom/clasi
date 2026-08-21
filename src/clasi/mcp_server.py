"""CLASI MCP server — stdio transport.

Provides SE Process Access and Artifact Management tools via MCP.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from clasi.project import Project

logger = logging.getLogger("clasi.mcp")

# NONE-sentinel stripping, the per-call mcp-calls.jsonl trace, and the
# uniform tool-result envelope used to be installed here by monkey-patching
# `_tool_manager.call_tool` (see git history prior to sprint 030 ticket 005
# for the removed `_strip_none_sentinel` / `_write_call_trace` /
# `_build_logged_call_tool`). All three now live in
# `clasi.tools._common.clasi_tool`, applied per-function via
# `@server.tool() @clasi_tool` on every tool in artifact_tools.py,
# process_tools.py, and design_tools.py -- code this package owns, with no
# dependency on `mcp`-library private internals that a future `mcp` 2.x
# upgrade could silently stop patching.


class Clasi:
    """Top-level CLASI object. Owns the MCP server and the active project.

    Replaces the module-level globals (_project, server, _CONTENT_ROOT)
    with instance state. A singleton instance is created at module load
    and accessed via the module-level ``app`` variable.
    """

    def __init__(self) -> None:
        self._project: Project | None = None
        self.server = MCPServer(
            "clasi",
            instructions=(
                "CLASI. "
                "Provides SE process access tools (agents, skills, instructions) "
                "and artifact management tools (sprints, tickets, briefs)."
            ),
        )
        self.content_root = Path(__file__).parent.resolve()

    # -- Project management --------------------------------------------------

    @property
    def project(self) -> Project:
        """Get the active project. Created lazily from cwd at first access."""
        if self._project is None:
            self._project = Project(Path.cwd())
        return self._project

    def set_project(self, root: str | Path) -> Project:
        """Set the active project root."""
        self._project = Project(root)
        return self._project

    def reset_project(self) -> None:
        """Clear the active project (for tests)."""
        self._project = None

    # -- Content paths -------------------------------------------------------

    def content_path(self, *parts: str) -> Path:
        """Resolve a relative path inside the package content directory.

        Examples:
            app.content_path("agents")
            app.content_path("agents", "technical-lead.md")
        """
        return self.content_root.joinpath(*parts)

    # -- Logging -------------------------------------------------------------

    def _setup_logging(self) -> None:
        """Configure file-based logging for the MCP server."""
        log_level = os.environ.get("CLASI_LOG_LEVEL", "INFO").upper()
        logger.setLevel(getattr(logging, log_level, logging.INFO))

        log_dir = self.project.log_dir
        log_file = log_dir / "mcp-server.log"

        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            handler = logging.FileHandler(str(log_file), encoding="utf-8")
            handler.setFormatter(logging.Formatter(
                "%(asctime)s [%(levelname)s] %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            ))
            logger.addHandler(handler)
        except OSError:
            handler = logging.StreamHandler(sys.stderr)
            handler.setFormatter(logging.Formatter(
                "CLASI [%(levelname)s] %(message)s",
            ))
            logger.addHandler(handler)

    # -- Server lifecycle ----------------------------------------------------

    def run(self) -> None:
        """Start the CLASI MCP server (stdio transport)."""
        self.set_project(Path.cwd())
        self._setup_logging()
        # Identify who this MCP server instance is serving
        agent_name = os.environ.get("CLASI_AGENT_NAME", "team-lead")
        agent_tier = os.environ.get("CLASI_AGENT_TIER", "0")
        self._serving_agent = agent_name
        self._serving_tier = agent_tier

        from clasi.schemas import get_active_schema_path

        active_schema = get_active_schema_path(self.project.root)

        logger.info("=" * 60)
        logger.info("CLASI MCP server starting")
        logger.info("  serving: %s (tier %s)", agent_name, agent_tier)
        logger.info("  project_root: %s", self.project.root)
        logger.info("  clasi_dir: %s", self.project.clasi_dir)
        logger.info("  content_root: %s", self.content_root)
        logger.info("  active_schema: %s", active_schema)
        logger.info("  python: %s", sys.executable)
        logger.info("  log_file: %s", self.project.log_dir / "mcp-server.log")

        # Staleness check: warn loudly at startup if this server is running
        # a stale build relative to the project it is serving. See
        # clasi.staleness for what the two signals catch and why the check
        # is safe to run unconditionally (it never fires for ordinary
        # consumer projects).
        from clasi import __version__ as _running_version
        from clasi.staleness import check_staleness

        staleness_report = check_staleness(self.project.root, _running_version)
        if staleness_report.stale:
            for line in staleness_report.warning().splitlines():
                logger.warning(line)
            print(staleness_report.warning(), file=sys.stderr)
            # Also surface in the MCP `instructions` field, which clients
            # typically show/inject at session start — a more durable
            # surface than a stderr line that scrolls past.
            try:
                self.server._lowlevel_server.instructions = (
                    f"{self.server.instructions}\n\n{staleness_report.warning()}"
                )
            except AttributeError:
                logger.warning(
                    "staleness: could not append warning to MCP instructions "
                    "field (MCPServer internals changed)"
                )

        # Preflight: verify all required submodules are importable.
        # Catches stale editable installs or version mismatches at
        # startup rather than producing confusing per-tool errors.
        _required = [
            "clasi.artifact", "clasi.sprint", "clasi.ticket",
            "clasi.issue", "clasi.frontmatter", "clasi.versioning",
        ]
        for _mod in _required:
            try:
                __import__(_mod)
            except ImportError as e:
                msg = (
                    f"CLASI preflight failed: cannot import {_mod} ({e}). "
                    "The MCP server source may be stale — restart the "
                    "session or reinstall the package."
                )
                logger.error(msg)
                print(msg, file=sys.stderr)
                raise SystemExit(1) from e
        logger.info("  preflight: all required submodules importable")

        # Import tool modules to register their tools with the server
        import clasi.tools.process_tools  # noqa: F401
        import clasi.tools.artifact_tools  # noqa: F401
        import clasi.tools.design_tools  # noqa: F401

        # `_tool_manager._tools` is a private attribute of the underlying
        # `mcp` library server object -- structurally unchanged across the
        # mcp 1.x -> 2.x migration (verified against mcp==2.0.0), but with
        # no guarantee it stays that way in a future release. Guarded the
        # same way the staleness-warning instructions-write above is: a
        # missing/renamed attribute degrades to a logged warning and skips
        # the diagnostics, rather than crashing server startup.
        try:
            _tools_dict = self.server._tool_manager._tools
        except AttributeError:
            logger.warning(
                "diagnostics: could not read registered tools "
                "(MCPServer internals changed) -- skipping tool-count and "
                "schema-dump diagnostics"
            )
        else:
            tool_count = len(_tools_dict)
            logger.info("  tools registered: %d", tool_count)

            # Diagnostic: dump every registered tool's input schema, one tool
            # per log line. Lets us confirm exactly what schema the server
            # advertises to clients (and the client passes to the model).
            # See docs/clasi/todo/vscode-extension-close-sprint-empty-params.md
            for _tool_name in sorted(_tools_dict):
                _tool = _tools_dict[_tool_name]
                _schema = getattr(_tool, "parameters", None)
                if _schema is None:
                    _fn = getattr(_tool, "fn", None)
                    _schema = getattr(_fn, "__schema__", None) if _fn else None
                try:
                    _schema_json = json.dumps(_schema, sort_keys=True) if _schema else "<no-schema>"
                except (TypeError, ValueError):
                    _schema_json = repr(_schema)
                logger.info("SCHEMA %s %s", _tool_name, _schema_json)

        # Diagnostic: monkey-patch JSONRPCMessage.model_validate_json so
        # we log every raw incoming JSON-RPC envelope BEFORE Pydantic
        # parses it. Distinguishes "client sent {} on the wire" from
        # "something in our Python mcp library stripped the args before
        # the tool function saw them". Deliberately untouched by sprint
        # 030 ticket 005 -- unrelated debug scaffolding for a closed
        # investigation, not part of the NONE-sentinel/call-logging
        # mechanism that ticket replaced with @clasi_tool. @clasi_tool
        # itself (clasi.tools._common) only ever sees the parsed dict, by
        # which point any wire-level stripping has already happened --
        # this tap is the only place that sees the raw JSON-RPC bytes.
        try:
            import mcp.types as _mt
            _orig_validate = _mt.JSONRPCMessage.model_validate_json

            def _logged_validate(json_data, *a, **kw):
                try:
                    if isinstance(json_data, (bytes, bytearray)):
                        text = bytes(json_data).decode("utf-8", errors="replace")
                    else:
                        text = str(json_data)
                    logger.info("RAW_RPC_IN %s", text[:2000].rstrip())
                except Exception:
                    pass
                return _orig_validate(json_data, *a, **kw)

            _mt.JSONRPCMessage.model_validate_json = _logged_validate
            logger.info("  raw-rpc tap: installed on JSONRPCMessage.model_validate_json")
        except Exception as _exc:
            logger.warning("  raw-rpc tap: failed to install (%s)", _exc)

        logger.info("CLASI MCP server ready")

        self.server.run(transport="stdio")


# ---------------------------------------------------------------------------
# Module-level singleton and convenience accessors
# ---------------------------------------------------------------------------

app = Clasi()
"""The singleton CLASI application instance."""

# Convenience aliases so existing code can do:
#   from clasi.mcp_server import server, get_project, content_path
server = app.server


def get_project() -> Project:
    """Get the active project from the singleton app."""
    return app.project


def set_project(root: str | Path) -> Project:
    """Set the active project on the singleton app."""
    return app.set_project(root)


def reset_project() -> None:
    """Reset the active project on the singleton app (for tests)."""
    app.reset_project()


def content_path(*parts: str) -> Path:
    """Resolve a content path via the singleton app."""
    return app.content_path(*parts)


def run_server() -> None:
    """Start the CLASI MCP server via the singleton app."""
    app.run()
