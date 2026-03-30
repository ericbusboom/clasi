"""CLASI MCP server — stdio transport.

Provides SE Process Access and Artifact Management tools via MCP.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from claude_agent_skills.project import Project

# ---------------------------------------------------------------------------
# Project singleton — all path resolution flows through here
# ---------------------------------------------------------------------------

_project: Project | None = None


def get_project() -> Project:
    """Get the active project. Created lazily from cwd at first access."""
    global _project
    if _project is None:
        _project = Project(Path.cwd())
    return _project


def set_project(root: str | Path) -> Project:
    """Set the active project root. Used for session management and tests."""
    global _project
    _project = Project(root)
    return _project


def reset_project() -> None:
    """Reset the project singleton (for tests)."""
    global _project
    _project = None


# ---------------------------------------------------------------------------
# Logging setup — writes to docs/clasi/log/mcp-server.log
# Uses stderr for fallback since stdout is reserved for MCP stdio transport.
# ---------------------------------------------------------------------------

logger = logging.getLogger("clasi.mcp")


def _setup_logging() -> None:
    """Configure file-based logging for the MCP server."""
    log_level = os.environ.get("CLASI_LOG_LEVEL", "INFO").upper()
    logger.setLevel(getattr(logging, log_level, logging.INFO))

    log_dir = get_project().log_dir
    log_file = log_dir / "mcp-server.log"

    # Always log to file if the directory exists (or can be created)
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(str(log_file), encoding="utf-8")
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        ))
        logger.addHandler(handler)
    except OSError:
        # Can't create log dir — fall back to stderr
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(
            "CLASI [%(levelname)s] %(message)s",
        ))
        logger.addHandler(handler)


# Create the MCP server instance
server = FastMCP(
    "clasi",
    instructions=(
        "CLASI. "
        "Provides SE process access tools (agents, skills, instructions) "
        "and artifact management tools (sprints, tickets, briefs)."
    ),
)


_CONTENT_ROOT = Path(__file__).parent.resolve()


def content_path(*parts: str) -> Path:
    """Resolve a relative content path to an absolute path inside the package.

    Examples:
        content_path("agents")                       → .../claude_agent_skills/agents/
        content_path("agents", "technical-lead.md")   → .../claude_agent_skills/agents/technical-lead.md
        content_path("instructions", "languages")     → .../claude_agent_skills/instructions/languages/
    """
    return _CONTENT_ROOT.joinpath(*parts)


def run_server() -> None:
    """Start the CLASI MCP server (stdio transport)."""
    project = set_project(Path.cwd())
    _setup_logging()
    logger.info("=" * 60)
    logger.info("CLASI MCP server starting")
    logger.info("  project_root: %s", project.root)
    logger.info("  clasi_dir: %s", project.clasi_dir)
    logger.info("  content_root: %s", _CONTENT_ROOT)
    logger.info("  python: %s", sys.executable)
    logger.info("  log_file: %s", project.log_dir / "mcp-server.log")

    # Import tool modules to register their tools with the server
    import claude_agent_skills.process_tools  # noqa: F401
    import claude_agent_skills.artifact_tools  # noqa: F401
    import claude_agent_skills.dispatch_tools  # noqa: F401

    tool_names = sorted(server._tool_manager._tools.keys())
    logger.info("  tools registered: %d", len(tool_names))
    for name in tool_names:
        logger.info("    - %s", name)
    logger.info("CLASI MCP server ready")

    # Wrap _tool_manager.call_tool to log every invocation
    _tm = server._tool_manager
    _original_call_tool = _tm.call_tool

    async def _logged_call_tool(name, arguments, **kwargs):
        # Truncate large args for readability
        args_summary = {}
        for k, v in arguments.items():
            s = str(v)
            args_summary[k] = s[:200] + "..." if len(s) > 200 else s
        logger.info("CALL %s(%s)", name, json.dumps(args_summary))
        try:
            result = await _original_call_tool(name, arguments, **kwargs)
            # Log result summary
            result_str = str(result)
            if len(result_str) > 500:
                result_str = result_str[:500] + "..."
            logger.info("  OK %s -> %s", name, result_str)
            return result
        except Exception as e:
            logger.error("  FAIL %s -> %s: %s", name, type(e).__name__, e)
            raise

    _tm.call_tool = _logged_call_tool

    server.run(transport="stdio")
